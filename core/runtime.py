"""Bot runtime management."""
import asyncio, threading, time, json, re
from typing import Dict, Optional, List
from collections import deque

from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from .flows import load_vms_for_bot
from data.database import list_pro_scripts, kv_get, kv_set


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
    """单个 Bot 的运行进程（线程+事件循环），支持固定命令 + Flow + Pro 脚本。"""

    def __init__(self, bot_id: int, token: str, command_specs: List[dict], *, auto_restart: bool = True):
        self.bot_id = bot_id
        self.token = token
        self.specs = self._filter_active_specs(command_specs)
        self.state = "stopped"
        self.last_error: Optional[str] = None
        self.started_at: Optional[float] = None
        self.auto_restart = auto_restart

        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._app: Optional[Application] = None
        self._stop_evt: Optional[asyncio.Event] = None

        self._vms = []
        self._pro_scripts = []

        self.events = deque(maxlen=200)
        self.stats = {"messages": 0, "errors": 0}
        self._log("process created")

    @staticmethod
    def _filter_active_specs(specs: List[dict]) -> List[dict]:
        filtered: List[dict] = []
        for spec in specs or []:
            if not isinstance(spec, dict):
                continue
            raw_flag = spec.get("active", 1)
            try:
                flag_val = int(raw_flag)
            except (TypeError, ValueError):
                flag_val = 1 if raw_flag else 0
            if flag_val == 1:
                group_flag = spec.get("group_active")
                if group_flag is not None:
                    try:
                        if int(group_flag) != 1:
                            continue
                    except (TypeError, ValueError):
                        if not group_flag:
                            continue
                filtered.append(spec)
        return filtered

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
            "flows_count": len(getattr(self, "_vms", [])),
            "pro_scripts_count": len(getattr(self, "_pro_scripts", [])),
        }

    def recent_logs(self, n: int = 100):
        return list(self.events)[-n:]

    def _make_handlers(self):
        handlers: List[CommandHandler] = []

        async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            await update.message.reply_text("Bot 已上线～ /help 查看命令")

        async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            lines = [f"{s['command']} → {s.get('reply') or s.get('kind', 'text')}" for s in self.specs]
            for vm in self._vms:
                for entry in vm.blocks.get("entries", []):
                    if entry.get("type") == "on_command" and entry.get("command"):
                        lines.append(f"{entry['command']} → flow")
            for script in self._pro_scripts:
                lines.append(f"{script['command']} → pro_script")

            txt = "可用命令：\n" + ("\n".join(sorted(set(lines))) if lines else "暂无")
            await update.message.reply_text(txt)

        handlers.append(CommandHandler("start", start))
        handlers.append(CommandHandler("help", help_cmd))

        for spec in self.specs:
            cmd = spec["command"].lstrip("/")
            kind = (spec.get("kind") or "text").lower()
            reply = spec.get("reply") or ""
            payload_raw = spec.get("payload")
            parse_mode = spec.get("parse_mode") or None
            disable_preview = bool(spec.get("disable_preview", 0))
            try:
                payload = json.loads(payload_raw) if (payload_raw and isinstance(payload_raw, str)) else (
                            payload_raw or {})
            except Exception:
                payload = {}

            async def _h(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                         _kind=kind, _reply=reply, _payload=payload,
                         _parse=parse_mode, _no_preview=disable_preview):
                self.stats["messages"] += 1
                try:
                    message = update.message or update.effective_message
                    user = update.effective_user
                    chat = update.effective_chat
                    args = ctx.args or []
                    context = {
                        "args": " ".join(args), "arg0": args[0] if args else "",
                        "user": {"id": user.id, "username": user.username, "first_name": user.first_name,
                                 "last_name": user.last_name} if user else {},
                        "chat": {"id": chat.id, "type": chat.type} if chat else {},
                    }

                    if _kind == "text":
                        text = _render((_payload.get("text") if isinstance(_payload, dict) else None) or _reply,
                                       context)
                        await message.reply_text(text, parse_mode=_parse, disable_web_page_preview=_no_preview)
                    elif _kind == "photo":
                        url = _render(_payload.get("url"), context)
                        caption = _render(_payload.get("caption"), context)
                        await ctx.bot.send_photo(chat_id=chat.id, photo=url, caption=caption, parse_mode=_parse)
                    elif _kind == "document":
                        url = _render(_payload.get("url"), context)
                        caption = _render(_payload.get("caption"), context)
                        await ctx.bot.send_document(chat_id=chat.id, document=url, caption=caption, parse_mode=_parse)
                    elif _kind == "animation":
                        url = _render(_payload.get("url"), context)
                        caption = _render(_payload.get("caption"), context)
                        await ctx.bot.send_animation(chat_id=chat.id, animation=url, caption=caption, parse_mode=_parse)
                    else:
                        await message.reply_text(f"未知回应类型：{_kind}")
                except Exception as e:
                    self.stats["errors"] += 1;
                    self.last_error = repr(e)
                    self._log(self.last_error, level="error");
                    raise

            handlers.append(CommandHandler(cmd, _h))
        return handlers

    async def _make_pro_script_handlers(self):
        handlers = []
        self._pro_scripts = []
        for script in await list_pro_scripts(self.bot_id):
            if not script.get('active'):
                continue
            group_flag = script.get('group_active')
            if group_flag is not None:
                try:
                    if int(group_flag) != 1:
                        continue
                except (TypeError, ValueError):
                    if not group_flag:
                        continue
            self._pro_scripts.append(script)
        self._log(f"pro scripts loaded: {len(self._pro_scripts)}")

        for script in self._pro_scripts:
            cmd = script["command"].lstrip("/")
            code = script["code"]

            async def make_handler(user_code, command_name):
                sandbox_log = lambda msg: self._log(f"[script:{command_name}] {msg}")
                wrapped_code = (
                    "async def user_handler(bot, update, context, log):\n"
                    "    db = getattr(context, 'db', None)\n"
                )
                for line in user_code.splitlines():
                    wrapped_code += f"    {line}\n"

                # 1. AST 静态安全检查
                from .sandbox import validate_script_safety
                is_safe, error_msg = validate_script_safety(code)
                if not is_safe:
                    raise ValueError(f"Security Check Failed:\n{error_msg}")

                # 2. 构建受限的沙箱环境
                safe_builtins = {
                    "True": True, "False": False, "None": None,
                    "abs": abs, "all": all, "any": any, "ascii": ascii, "bin": bin, "bool": bool,
                    "bytearray": bytearray, "bytes": bytes, "chr": chr, "complex": complex,
                    "dict": dict, "dir": dir, "divmod": divmod, "enumerate": enumerate,
                    "filter": filter, "float": float, "format": format, "frozenset": frozenset,
                    "getattr": getattr, "hasattr": hasattr, "hash": hash, "hex": hex, "id": id,
                    "int": int, "isinstance": isinstance, "issubclass": issubclass, "iter": iter,
                    "len": len, "list": list, "map": map, "max": max, "min": min, "next": next,
                    "object": object, "oct": oct, "ord": ord, "pow": pow, "print": sandbox_log, # 重定向 print 到 log
                    "range": range, "repr": repr, "reversed": reversed, "round": round,
                    "set": set, "setattr": setattr, "slice": slice, "sorted": sorted,
                    "str": str, "sum": sum, "super": super, "tuple": tuple, "type": type, "zip": zip,
                    "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError,
                    "KeyError": KeyError, "IndexError": IndexError, "AttributeError": AttributeError,
                }
                
                sandbox_globals = {
                    "__builtins__": safe_builtins,
                    "asyncio": asyncio,
                    "aiohttp": __import__("aiohttp"), # 白名单库
                    "json": __import__("json"),
                    "re": __import__("re"),
                    "random": __import__("random"),
                    "math": __import__("math"),
                    "datetime": __import__("datetime"),
                    "time": __import__("time"),
                }

                local_scope = {}
                exec(wrapped_code, sandbox_globals, local_scope)

                async def final_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
                    self.stats["messages"] += 1
                    try:
                        chat = update.effective_chat
                        chat_id = str(chat.id) if chat else None
                        user = update.effective_user
                        user_id = str(user.id) if user else None

                        async def _kv_get(scope: str, key: str, *, default=None):
                            value = await kv_get(
                                self.bot_id,
                                scope,
                                chat_id if scope != 'bot' else None,
                                user_id if scope == 'user' else None,
                                key,
                            )
                            return default if value is None else value

                        async def _kv_set(scope: str, key: str, value):
                            await kv_set(
                                self.bot_id,
                                scope,
                                chat_id if scope != 'bot' else None,
                                user_id if scope == 'user' else None,
                                key,
                                value,
                            )

                        async def _kv_delete(scope: str, key: str):
                            await kv_set(
                                self.bot_id,
                                scope,
                                chat_id if scope != 'bot' else None,
                                user_id if scope == 'user' else None,
                                key,
                                None,
                            )

                        ctx.db = {
                            'get': _kv_get,
                            'set': _kv_set,
                            'delete': _kv_delete,
                            'bot_id': self.bot_id,
                            'chat_id': chat_id,
                            'user_id': user_id,
                        }

                        await local_scope['user_handler'](ctx.bot, update, ctx, sandbox_log)
                    except Exception as e:
                        self.stats["errors"] += 1;
                        self.last_error = f"Script {cmd} error: {repr(e)}"
                        self._log(self.last_error, level="error")
                        try:
                            await update.effective_message.reply_text(f"脚本执行出错：{e}")
                        except Exception:
                            pass

                return final_handler

            try:
                handler_func = await make_handler(code, cmd)
                handlers.append(CommandHandler(cmd, handler_func))
            except Exception as e:
                self._log(f"Failed to compile script for /{cmd}: {e}", level="error")
        return handlers

    async def _build_app(self):
        app = Application.builder().token(self.token).build()

        self._vms = await load_vms_for_bot(self.bot_id)
        self._log(f"flows loaded: {len(self._vms)}")

        for h in self._make_handlers():
            app.add_handler(h)

        # 核心修复: 在调用 async def 函数时添加 await
        for h in await self._make_pro_script_handlers():
            app.add_handler(h)

        flow_cmds = {entry["command"].lstrip("/") for vm in self._vms for entry in vm.blocks.get("entries", []) if
                     entry.get("type") == "on_command" and entry.get("command")}

        async def _dynamic_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            self.stats["messages"] += 1
            try:
                cmd = (update.effective_message.text or "").split()[0].lstrip("/")
                for vm in self._vms:
                    for entry in vm.blocks.get("entries", []):
                        if entry.get("type") == "on_command" and entry.get("command", "").lstrip("/") == cmd:
                            await vm.run_entry(app, update, ctx, entry)
            except Exception as e:
                self.stats["errors"] += 1;
                self.last_error = repr(e)
                self._log(self.last_error, level="error");
                raise

        if flow_cmds:
            app.add_handler(CommandHandler(list(flow_cmds), _dynamic_command))
        self._log(f"flow commands: {sorted(list(flow_cmds))}")

        async def _resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            self.stats["messages"] += 1
            try:
                for vm in self._vms:
                    if await vm.maybe_resume(app, update, ctx): return
            except Exception as e:
                self.stats["errors"] += 1;
                self.last_error = repr(e)
                self._log(self.last_error, level="error");
                raise

        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), _resume))

        async def _on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
            self.stats["errors"] += 1;
            self.last_error = repr(context.error)
            self._log(self.last_error, level="error")

        app.add_error_handler(_on_error)

        all_cmds: Dict[str, str] = {}
        for s in self.specs: all_cmds[s["command"].lstrip("/")] = (s.get("reply") or s.get("kind") or "cmd")[:32]
        for c in flow_cmds: all_cmds.setdefault(c, "flow")
        for s in self._pro_scripts: all_cmds.setdefault(s["command"].lstrip("/"), s.get("name", "pro_script")[:32])

        cmds = [BotCommand(k, v) for k, v in list(all_cmds.items())[:100]]
        await app.bot.set_my_commands(cmds)
        self._log(f"commands set: {len(cmds)}")

        return app

    async def _runner(self):
        self.state = "starting";
        self.last_error = None
        self._stop_evt = asyncio.Event()
        self._log("starting")
        self._app = await self._build_app()
        try:
            await self._app.initialize()
            await self._app.start()
            await self._app.updater.start_polling(drop_pending_updates=True)
            self.state = "running";
            self.started_at = time.time()
            self._log("running")
            await self._stop_evt.wait()
        except Exception as e:
            self.last_error = repr(e);
            self.state = "errored"
            self._log(self.last_error, level="error")
            raise
        finally:
            try:
                if self._app:
                    await self._app.updater.stop()
                    await self._app.stop()
                    await self._app.shutdown()
            finally:
                self.state = "stopped";
                self.started_at = None
                self._app = None;
                self._stop_evt = None
                self._log("stopped")

    # --- start, stop, reload, sync 等生命周期函数保持不变 ---
    def start(self):
        if self._thread and self._thread.is_alive(): return True, "已在运行"
        self._loop = asyncio.new_event_loop()
        self._log("start requested")

        def _target():
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_until_complete(self._runner())
            finally:
                tasks = asyncio.all_tasks(loop=self._loop)
                for t in tasks: t.cancel()
                try:
                    self._loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
                except:
                    pass
                self._loop.close()

        self._thread = threading.Thread(target=_target, daemon=True)
        self._thread.start()
        return True, "已启动"

    def reload(self, token: str, specs: List[dict]):
        self._log("reload requested")
        self.stop()
        self.token = token
        self.specs = self._filter_active_specs(specs)
        return self.start()

    def stop(self, timeout=6.0):
        self._log("stop requested")
        if not (self._thread and self._thread.is_alive()):
            self.state = "stopped";
            return True, "未在运行"
        if self._loop and self._stop_evt:
            self._loop.call_soon_threadsafe(self._stop_evt.set)
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            self.state = "stopping";
            return False, "停止超时"
        self._thread = None;
        self._loop = None
        return True, "已停止"

    def sync_commands(self):
        if not (self._loop and self._app): return False, "未在运行"

        async def _set():
            all_cmds: Dict[str, str] = {}
            for s in self.specs: all_cmds[s["command"].lstrip("/")] = (s.get("reply") or s.get("kind") or "cmd")[:32]
            flow_cmds = {e["command"].lstrip("/") for vm in self._vms for e in vm.blocks.get("entries", []) if
                         e.get("type") == "on_command" and e.get("command")}
            for c in flow_cmds: all_cmds.setdefault(c, "flow")
            for s in self._pro_scripts: all_cmds.setdefault(s["command"].lstrip("/"), s.get("name", "pro_script")[:32])
            cmds = [BotCommand(k, v) for k, v in list(all_cmds.items())[:100]]
            await self._app.bot.set_my_commands(cmds)
            self._log(f"commands synced: {len(cmds)}")

        fut = asyncio.run_coroutine_threadsafe(_set(), self._loop)
        fut.result(timeout=5);
        return True, "已同步"

    def is_thread_alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def needs_restart(self) -> bool:
        if not self.auto_restart: return False
        if self.state in ("errored", "stopped"): return True
        if self.state == "running" and not self.is_thread_alive(): return True
        return False

    def restart(self):
        self._log("auto restart triggered")
        if self.is_thread_alive(): self.stop()
        return self.start()


class BotRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._procs: Dict[int, BotProcess] = {}

    def status(self, bot_id: int):
        with self._lock:
            self._ensure_process_health(bot_id)
            p = self._procs.get(bot_id)
            if not p:
                return {
                    "bot_id": bot_id, "state": "stopped", "started_at": None, "uptime": 0,
                    "last_error": None, "stats": {"messages": 0, "errors": 0},
                    "specs_count": 0, "flows_count": 0, "pro_scripts_count": 0,
                }
            snap = p.snapshot()
            snap.setdefault("bot_id", bot_id)
            if "stats" not in snap or not isinstance(snap.get("stats"), dict):
                snap["stats"] = {"messages": 0, "errors": 0}
            snap.setdefault("uptime", 0)
            return snap

    def start(self, bot_id: int, token: str, specs: List[dict]):
        with self._lock:
            p = self._procs.get(bot_id)
            if p: return p.reload(token, specs)
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

    def status_all(self):
        with self._lock:
            self._ensure_process_health()
            return {bid: p.snapshot() for bid, p in self._procs.items()}

    def logs(self, bot_id: int, lines: int = 100):
        with self._lock:
            p = self._procs.get(bot_id)
            if not p: return []
            return p.recent_logs(lines)

    def _ensure_process_health(self, bot_id: Optional[int] = None):
        items = [(bot_id, self._procs.get(bot_id))] if bot_id is not None else list(self._procs.items())
        for bid, proc in items:
            if not proc: continue
            if proc.needs_restart():
                ok, msg = proc.restart()
                if not ok:
                    proc._log(f"auto restart failed: {msg}", level="error")


registry = BotRegistry()


__all__ = ["BotProcess", "BotRegistry", "registry"]
