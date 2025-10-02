# bot_registry.py
import asyncio, threading, time, json, re
from typing import Dict, Optional, List
from collections import deque

from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from flow_engine import load_vms_for_bot


def _resolve_path(ctx: dict, path: str):
    cur = ctx
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return ""
    return "" if cur is None else cur

def _render(tpl: str | None, ctx: dict) -> str:
    if not tpl:
        return ""
    def _sub(m):
        key = m.group(1).strip()
        val = _resolve_path(ctx, key)
        return str(val)
    return re.sub(r"\{\{\s*([\w\.]+)\s*\}\}", _sub, tpl)


class BotProcess:
    """单个 Bot 的运行进程（线程+事件循环），支持固定命令 + Flow(Blockly) 命令。"""
    def __init__(self, bot_id: int, token: str, command_specs: List[dict]):
        self.bot_id = bot_id
        self.token = token
        self.specs = list(command_specs)     # [{command, kind, reply, payload, parse_mode, disable_preview}]
        self.state = "stopped"
        self.last_error: Optional[str] = None
        self.started_at: Optional[float] = None

        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._app: Optional[Application] = None
        self._stop_evt: Optional[asyncio.Event] = None

        self._vms = []   # FlowVM 列表（可视化流程）

        # 运行观测
        self.events = deque(maxlen=200)              # 最近事件/日志
        self.stats = {"messages": 0, "errors": 0}    # 计数
        self._log("process created")

    # ----------------- 监控/日志 -----------------
    def _log(self, msg: str, level: str = "info"):
        self.events.append({"ts": time.time(), "level": level, "msg": msg})

    def snapshot(self):
        uptime = (time.time() - self.started_at) if (self.started_at and self.state == "running") else 0
        return {
            "bot_id": self.bot_id,
            "state": self.state,
            "started_at": self.started_at,
            "uptime": int(uptime),
            "last_error": self.last_error,
            "stats": dict(self.stats),
            "specs_count": len(self.specs),
            "flows_count": len(self._vms) if getattr(self, "_vms", None) else 0,
        }

    def recent_logs(self, n: int = 100):
        return list(self.events)[-n:]

    # ----------------- 固定指令 handlers -----------------
    def _make_handlers(self):
        handlers: List[CommandHandler] = []

        async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            await update.message.reply_text("Bot 已上线～ /help 查看命令")

        async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            lines = [f"{s['command']} → {s.get('reply') or s.get('kind','text')}" for s in self.specs]
            # 把 Flow 里的命令也列上
            for vm in self._vms:
                for entry in vm.blocks.get("entries", []):
                    if entry.get("type") == "on_command" and entry.get("command"):
                        lines.append(f"{entry['command']} → flow")
            txt = "可用命令：\n" + ("\n".join(sorted(set(lines))) if lines else "暂无")
            await update.message.reply_text(txt)

        handlers.append(CommandHandler("start", start))
        handlers.append(CommandHandler("help", help_cmd))

        # 为每个自定义命令生成 handler
        for spec in self.specs:
            cmd = spec["command"].lstrip("/")
            kind = (spec.get("kind") or "text").lower()
            reply = spec.get("reply") or ""     # 兼容老数据
            payload_raw = spec.get("payload")
            parse_mode = spec.get("parse_mode") or None
            disable_preview = bool(spec.get("disable_preview", 0))
            try:
                payload = json.loads(payload_raw) if (payload_raw and isinstance(payload_raw, str)) else (payload_raw or {})
            except Exception:
                payload = {}

            async def _h(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                         _kind=kind, _reply=reply, _payload=payload,
                         _parse=parse_mode, _no_preview=disable_preview):
                # 计数/日志在执行时做（而不是注册时）
                self.stats["messages"] += 1
                try:
                    message = update.message or update.effective_message
                    user = update.effective_user
                    chat = update.effective_chat
                    # 组装模板上下文
                    args = ctx.args or []
                    context = {
                        "args": " ".join(args),
                        "arg0": args[0] if args else "",
                        "user": {
                            "id": user.id if user else "",
                            "username": user.username if user else "",
                            "first_name": user.first_name if user else "",
                            "last_name": user.last_name if user else "",
                        },
                        "chat": {"id": chat.id if chat else "", "type": chat.type if chat else ""},
                    }

                    if _kind == "text":
                        text = _render((_payload.get("text") if isinstance(_payload, dict) else None) or _reply, context)
                        await message.reply_text(text, parse_mode=_parse, disable_web_page_preview=_no_preview)
                    elif _kind == "photo":
                        url = _render(_payload.get("url"), context)
                        caption = _render(_payload.get("caption"), context)
                        await message.bot.send_photo(chat_id=chat.id, photo=url, caption=caption, parse_mode=_parse)
                    elif _kind == "document":
                        url = _render(_payload.get("url"), context)
                        caption = _render(_payload.get("caption"), context)
                        await message.bot.send_document(chat_id=chat.id, document=url, caption=caption, parse_mode=_parse)
                    elif _kind == "animation":
                        url = _render(_payload.get("url"), context)
                        caption = _render(_payload.get("caption"), context)
                        await message.bot.send_animation(chat_id=chat.id, animation=url, caption=caption, parse_mode=_parse)
                    else:
                        await message.reply_text(f"未知回应类型：{_kind}")
                except Exception as e:
                    self.stats["errors"] += 1
                    self.last_error = repr(e)
                    self._log(self.last_error, level="error")
                    raise

            handlers.append(CommandHandler(cmd, _h))

        return handlers

    # ----------------- 构建应用（含 Flow 注册） -----------------
    async def _build_app(self):
        app = Application.builder().token(self.token).build()

        # 1) 先加载可视化流程（FlowVM）
        self._vms = load_vms_for_bot(self.bot_id)
        self._log(f"flows loaded: {len(self._vms)}")

        # 2) 固定指令
        for h in self._make_handlers():
            app.add_handler(h)

        # 3) Flow 的 on_command 动态触发
        flow_cmds = set()
        for vm in self._vms:
            for entry in vm.blocks.get("entries", []):
                if entry.get("type") == "on_command" and entry.get("command"):
                    flow_cmds.add(entry["command"].lstrip("/"))

        async def _dynamic_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            self.stats["messages"] += 1
            try:
                cmd = (update.effective_message.text or "").split()[0].lstrip("/")
                # 找到匹配的 entry 执行
                for vm in self._vms:
                    for entry in vm.blocks.get("entries", []):
                        if entry.get("type") == "on_command" and entry.get("command","").lstrip("/") == cmd:
                            await vm.run_entry(app, update, ctx, entry)
            except Exception as e:
                self.stats["errors"] += 1
                self.last_error = repr(e)
                self._log(self.last_error, level="error")
                raise

        if flow_cmds:
            app.add_handler(CommandHandler(list(flow_cmds), _dynamic_command))
        self._log(f"flow commands: {sorted(list(flow_cmds))}")

        # 4) Flow 的续跑（等待下一条消息）
        async def _resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            self.stats["messages"] += 1
            try:
                for vm in self._vms:
                    resumed = await vm.maybe_resume(app, update, ctx)
                    if resumed:
                        return
            except Exception as e:
                self.stats["errors"] += 1
                self.last_error = repr(e)
                self._log(self.last_error, level="error")
                raise

        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), _resume))

        # 5) 全局错误处理（兜底）
        async def _on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
            self.stats["errors"] += 1
            self.last_error = repr(context.error)
            self._log(self.last_error, level="error")
        app.add_error_handler(_on_error)

        # 6) 合并设置命令菜单：固定指令 + Flow 命令
        all_cmds: Dict[str, str] = {}
        for s in self.specs:
            name = s["command"].lstrip("/")
            desc = (s.get("reply") or s.get("kind") or "cmd")[:32]
            all_cmds[name] = desc
        for c in flow_cmds:
            all_cmds.setdefault(c, "flow")

        # Telegram 菜单最多一百条，这里做个保护
        cmds = [BotCommand(k, v) for k, v in list(all_cmds.items())[:100]]
        await app.bot.set_my_commands(cmds)
        self._log(f"commands set: {len(cmds)}")

        return app

    # ----------------- 生命周期 -----------------
    async def _runner(self):
        self.state = "starting"; self.last_error = None
        self._stop_evt = asyncio.Event()
        self._log("starting")
        self._app = await self._build_app()
        try:
            await self._app.initialize()
            await self._app.start()
            await self._app.updater.start_polling(drop_pending_updates=True)
            self.state = "running"; self.started_at = time.time()
            self._log("running")
            await self._stop_evt.wait()
        except Exception as e:
            self.last_error = repr(e); self.state = "errored"
            self._log(self.last_error, level="error")
            raise
        finally:
            try:
                if self._app:
                    await self._app.updater.stop()
                    await self._app.stop()
                    await self._app.shutdown()
            finally:
                self.state = "stopped"; self.started_at = None
                self._app = None; self._stop_evt = None
                self._log("stopped")

    def start(self):
        if self._thread and self._thread.is_alive():
            return True, "已在运行"
        self._loop = asyncio.new_event_loop()
        self._log("start requested")
        def _target():
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_until_complete(self._runner())
            finally:
                pending = asyncio.all_tasks(loop=self._loop)
                for t in pending: t.cancel()
                try:
                    self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception:
                    pass
                self._loop.close()
        self._thread = threading.Thread(target=_target, daemon=True)
        self._thread.start()
        return True, "已启动"

    def reload(self, token: str, specs: List[dict]):
        self._log("reload requested")
        self.stop()
        self.token = token
        self.specs = list(specs)
        return self.start()

    def stop(self, timeout=6.0):
        self._log("stop requested")
        if not (self._thread and self._thread.is_alive()):
            self.state = "stopped"; return True, "未在运行"
        if self._loop and self._stop_evt:
            self._loop.call_soon_threadsafe(self._stop_evt.set)
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            self.state = "stopping"; return False, "停止超时"
        self._thread = None; self._loop = None
        return True, "已停止"

    def sync_commands(self):
        if not (self._loop and self._app): return False, "未在运行"
        async def _set():
            # 重新合并固定+Flow命令
            all_cmds: Dict[str, str] = {}
            for s in self.specs:
                name = s["command"].lstrip("/")
                desc = (s.get("reply") or s.get("kind") or "cmd")[:32]
                all_cmds[name] = desc
            # flow 命令来自当前加载的 vms
            flow_cmds = set()
            for vm in self._vms:
                for entry in vm.blocks.get("entries", []):
                    if entry.get("type") == "on_command" and entry.get("command"):
                        flow_cmds.add(entry["command"].lstrip("/"))
            for c in flow_cmds:
                all_cmds.setdefault(c, "flow")
            cmds = [BotCommand(k, v) for k, v in list(all_cmds.items())[:100]]
            await self._app.bot.set_my_commands(cmds)
            self._log(f"commands synced: {len(cmds)}")
        fut = asyncio.run_coroutine_threadsafe(_set(), self._loop)
        fut.result(timeout=5); return True, "已同步"


class BotRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._procs: Dict[int, BotProcess] = {}

    def status(self, bot_id: int):
        with self._lock:
            p = self._procs.get(bot_id)
            if not p: return {"state": "stopped"}
            return {"state": p.state, "started_at": p.started_at, "last_error": p.last_error}

    def start(self, bot_id: int, token: str, specs: List[dict]):
        with self._lock:
            p = self._procs.get(bot_id)
            if p:
                return p.reload(token, specs)
            p = BotProcess(bot_id, token, specs)
            self._procs[bot_id] = p
            return p.start()

    def stop(self, bot_id: int):
        with self._lock:
            p = self._procs.get(bot_id)
            if not p: return True, "未在运行"
            ok, msg = p.stop()
            if ok: self._procs.pop(bot_id, None)
            return ok, msg

    def sync(self, bot_id: int):
        with self._lock:
            p = self._procs.get(bot_id)
            if not p: return False, "未在运行"
            return p.sync_commands()

    # ---- 新增：全量状态与日志 ----
    def status_all(self):
        with self._lock:
            out = {}
            for bid, p in self._procs.items():
                out[bid] = p.snapshot()
            return out

    def logs(self, bot_id: int, lines: int = 100):
        with self._lock:
            p = self._procs.get(bot_id)
            if not p: return []
            return p.recent_logs(lines)


registry = BotRegistry()
