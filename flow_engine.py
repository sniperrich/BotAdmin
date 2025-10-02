# flow_engine.py
import asyncio, json, re, time
from typing import List, Dict, Any, Optional

from telegram import Update
from telegram.ext import ContextTypes, Application

# 依赖你的 db.py
from db import list_flows as _list_flows, kv_get, kv_set

# ------------- 小工具：模板渲染 -------------
_token_pat = re.compile(r"\{\{\s*([\w\.]+)\s*\}\}")

def _resolve_path(d: Any, path: str):
    cur = d
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return ""
    return "" if cur is None else cur

def _render_with_vars(tpl: str | None, base_ctx: dict, bot_id: int, chat_id: str|None, user_id: str|None, kv_cache: dict):
    """支持 {{vars.chat.key}} / {{vars.user.key}} / {{vars.bot.key}} / {{local.x}} 等"""
    if not tpl: return ""
    def _sub(m):
        key = m.group(1).strip()
        if key.startswith("vars."):
            # vars.scope.key
            parts = key.split(".")
            if len(parts) >= 3:
                scope, k = parts[1], ".".join(parts[2:])
                cache_bucket = kv_cache.setdefault(scope, {})
                if k not in cache_bucket:
                    cache_bucket[k] = kv_get(bot_id, scope, chat_id if scope!="bot" else None,
                                             user_id if scope=="user" else None, k)
                return "" if cache_bucket[k] is None else str(cache_bucket[k])
        return str(_resolve_path(base_ctx, key))
    return _token_pat.sub(_sub, tpl)

# ------------- FlowVM -------------
class FlowVM:
    def __init__(self, bot_id: int, blocks: dict):
        self.bot_id = bot_id
        self.blocks = blocks or {"entries":[]}

    async def run_entry(self, app: Application, update: Update, ctx: ContextTypes.DEFAULT_TYPE, entry: dict):
        """执行一个入口的主链"""
        message = update.effective_message
        user = update.effective_user
        chat = update.effective_chat
        args = (ctx.args or [])
        chat_id = str(chat.id) if chat else None
        user_id = str(user.id) if user else None

        locals_map: Dict[str, Any] = {}
        kv_cache: Dict[str, dict] = {}   # 渲染时懒加载 vars.*

        base_ctx = {
            "args": " ".join(args),
            "arg0": args[0] if args else "",
            "input": {"text": message.text if message else ""},
            "user": {
                "id": user.id if user else "", "username": user.username if user else "",
                "first_name": user.first_name if user else "", "last_name": user.last_name if user else "",
            },
            "chat": {"id": chat.id if chat else "", "type": chat.type if chat else ""},
            "local": locals_map
        }

        async def send_text(text: str, parse_mode: Optional[str], no_preview: bool):
            t = _render_with_vars(text, base_ctx, self.bot_id, chat_id, user_id, kv_cache)
            await message.reply_text(t, parse_mode=parse_mode or None,
                                     disable_web_page_preview=bool(no_preview))

        async def send_media(kind: str, url: str, caption: str, parse_mode: Optional[str]):
            u = _render_with_vars(url, base_ctx, self.bot_id, chat_id, user_id, kv_cache)
            c = _render_with_vars(caption, base_ctx, self.bot_id, chat_id, user_id, kv_cache)
            if kind == "photo":
                await message.bot.send_photo(chat_id=chat.id, photo=u, caption=c, parse_mode=parse_mode or None)
            elif kind == "document":
                await message.bot.send_document(chat_id=chat.id, document=u, caption=c, parse_mode=parse_mode or None)
            elif kind == "animation":
                await message.bot.send_animation(chat_id=chat.id, animation=u, caption=c, parse_mode=parse_mode or None)

        async def http_call(node: dict):
            import aiohttp
            method = (node.get("method") or "GET").upper()
            url = _render_with_vars(node.get("url",""), base_ctx, self.bot_id, chat_id, user_id, kv_cache)
            headers_txt = _render_with_vars(node.get("headers") or "", base_ctx, self.bot_id, chat_id, user_id, kv_cache)
            body_txt = _render_with_vars(node.get("body") or "", base_ctx, self.bot_id, chat_id, user_id, kv_cache)
            try:
                headers = json.loads(headers_txt) if headers_txt else {}
            except Exception:
                headers = {}
            try:
                data = json.loads(body_txt) if body_txt else None
            except Exception:
                data = body_txt.encode("utf-8") if body_txt else None

            async with aiohttp.ClientSession() as sess:
                async with sess.request(method, url, headers=headers or None, json=(data if isinstance(data, dict) else None),
                                        data=(data if isinstance(data, (bytes, str)) else None), timeout=15) as resp:
                    raw = await resp.text()
                    val: Any = raw
                    # 尝试解析 JSON
                    try:
                        j = json.loads(raw)
                        jpath = (node.get("json_path") or "").strip()
                        if jpath:
                            # 简单 JSON 路径 a.b.c
                            cur = j
                            for part in jpath.split("."):
                                if part=="":
                                    continue
                                if isinstance(cur, dict) and part in cur:
                                    cur = cur[part]
                                else:
                                    cur = None; break
                            val = cur
                        else:
                            val = j
                    except Exception:
                        pass

            save = node.get("save_to") or {}
            scope = save.get("scope") or "chat"
            key = save.get("key") or "resp"
            kv_set(self.bot_id, scope, chat_id if scope!="bot" else None, user_id if scope=="user" else None, key, val)
            # 更新渲染缓存
            kv_cache.setdefault(scope, {})[key] = val

        # 顺序执行节点
        for n in (entry.get("nodes") or []):
            t = n.get("type")
            if t == "send_text":
                await send_text(n.get("text") or "", n.get("parse_mode") or None, bool(n.get("disable_preview")))
            elif t in ("send_photo", "send_document", "send_animation"):
                await send_media(t.split("_",1)[1], n.get("url") or "", n.get("caption") or "", None)
            elif t == "set_var":
                mode = n.get("mode") or "text"
                scope, key = (n.get("scope") or "chat"), (n.get("key") or "k")
                if mode == "random":
                    lo = int(n.get("random",{}).get("min", 1))
                    hi = int(n.get("random",{}).get("max", 100))
                    val = int(lo + (time.time_ns() % (max(1, hi - lo + 1))) )
                else:
                    val = _render_with_vars(n.get("value") or "", base_ctx, self.bot_id, chat_id, user_id, kv_cache)
                kv_set(self.bot_id, scope, chat_id if scope!="bot" else None, user_id if scope=="user" else None, key, val)
                kv_cache.setdefault(scope, {})[key] = val
            elif t == "inc_var":
                scope, key = (n.get("scope") or "chat"), (n.get("key") or "count")
                step = int(n.get("step") or 1)
                cur = kv_get(self.bot_id, scope, chat_id if scope!="bot" else None, user_id if scope=="user" else None, key)
                try:
                    cur = int(cur or 0)
                except Exception:
                    cur = 0
                val = cur + step
                kv_set(self.bot_id, scope, chat_id if scope!="bot" else None, user_id if scope=="user" else None, key, val)
                kv_cache.setdefault(scope, {})[key] = val
            elif t == "get_var":
                scope, key, alias = (n.get("scope") or "chat"), (n.get("key") or "k"), (n.get("alias") or "x")
                val = kv_get(self.bot_id, scope, chat_id if scope!="bot" else None, user_id if scope=="user" else None, key)
                locals_map[alias] = val
            elif t == "set_local_from_input":
                alias = n.get("alias") or "x"
                locals_map[alias] = base_ctx["input"]["text"]
            elif t == "if_var":
                # 左：local.var；右：常量文本（会尝试转数值）
                def _asnum(x):
                    try:
                        if isinstance(x, str) and x.strip()!='' and re.fullmatch(r"-?\d+(\.\d+)?", x.strip()):
                            return float(x) if "." in x else int(x)
                        return float(x) if isinstance(x,(int,float)) else x
                    except Exception:
                        return x
                left = locals_map.get((n.get("left") or {}).get("var","x"))
                right_raw = (n.get("right") or {}).get("text","")
                right = right_raw
                # 模板渲染（允许 {{vars.*}} 或 {{local.*}}）
                right = _render_with_vars(str(right_raw), base_ctx, self.bot_id, chat_id, user_id, kv_cache)
                L = _asnum(left); R = _asnum(right)
                op = n.get("op") or "eq"
                ok=False
                if op=="eq": ok = (L==R)
                elif op=="ne": ok = (L!=R)
                elif op=="contains": ok = (str(left) in str(right)) if False else (str(right) in str(left))
                elif op=="gt":
                    try: ok = (float(L) > float(R))
                    except: ok = False
                elif op=="lt":
                    try: ok = (float(L) < float(R))
                    except: ok = False
                branch = (n.get("then") if ok else n.get("else")) or []
                # 简化：then/else 里只放基础动作
                for bn in branch:
                    bt = bn.get("type")
                    if bt=="send_text":
                        await send_text(bn.get("text") or "", bn.get("parse_mode") or None, bool(bn.get("disable_preview")))
                    elif bt in ("send_photo","send_document","send_animation"):
                        await send_media(bt.split("_",1)[1], bn.get("url") or "", bn.get("caption") or "", None)
                # 继续主链
            elif t == "http":
                await http_call(n)
            elif t == "wait_next":
                # 保存续跑状态
                await_key = f"await_{entry.get('id')}"
                kv_set(self.bot_id, "chat", chat_id, None, await_key, {
                    "expect": (n.get("expect") or "any"),
                    "next": n.get("next") or []
                })
                prompt = n.get("prompt") or ""
                if prompt:
                    await send_text(prompt, None, False)
                # 中断主链，等待下一条消息
                break

    async def maybe_resume(self, app: Application, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """如果当前 chat 存在等待状态，续跑它；返回是否处理。"""
        message = update.effective_message
        user = update.effective_user
        chat = update.effective_chat
        chat_id = str(chat.id) if chat else None
        user_id = str(user.id) if user else None

        # 逐个入口检查 await_{entry_id}
        for entry in (self.blocks.get("entries") or []):
            await_key = f"await_{entry.get('id')}"
            st = kv_get(self.bot_id, "chat", chat_id, None, await_key)
            if not st:
                continue

            expect = st.get("expect") or "any"
            nxt: List[dict] = st.get("next") or []

            text = message.text or ""
            # 简单校验
            if expect == "number":
                if not re.fullmatch(r"-?\d+", text.strip() or ""):
                    return False  # 不吃掉这条消息，让别的 handler 处理
                try:
                    num = int(text.strip())
                except Exception:
                    num = None
            else:
                num = None

            # 清掉等待状态
            kv_set(self.bot_id, "chat", chat_id, None, await_key, None)

            # 复用 run 里的环境（最小实现：拼一个伪 entry 来跑 next）
            fake_entry = {"id": entry.get("id"), "nodes": nxt}
            # 注入本次输入到 local
            class _DummyCtx:
                pass
            # 构造一个简化的 ctx，带 args
            ctx.args = (message.text or "").split()[1:] if (message.text or "").startswith("/") else []

            # 让 run_entry 使用当前 message 作为 base_ctx.input
            await self.run_entry(app, update, ctx, fake_entry)
            return True

        return False


# ------------- 装载 -------------
def load_vms_for_bot(bot_id: int) -> List[FlowVM]:
    vms: List[FlowVM] = []
    for row in _list_flows(bot_id):
        if int(row.get("active", 1)) != 1:
            continue
        try:
            blocks = json.loads(row.get("blocks_json") or "{}")
        except Exception:
            blocks = {"entries":[]}
        vms.append(FlowVM(bot_id, blocks))
    return vms
