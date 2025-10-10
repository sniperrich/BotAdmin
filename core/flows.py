"""Flow runtime helpers."""
import asyncio, json, re, time
from typing import List, Dict, Any, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, Application

from data.database import list_flows as _list_flows, kv_get, kv_set

# ... (模板渲染部分不变)
_token_pat = re.compile(r"\{\{\s*([\w\.]+)\s*\}\}")


def _resolve_path(d: Any, path: str):
    cur = d
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return ""
    return "" if cur is None else cur


def _render_with_vars(tpl: str | None, base_ctx: dict, bot_id: int, chat_id: str | None, user_id: str | None,
                      kv_cache: dict):
    if not tpl: return ""

    def _sub(m):
        key = m.group(1).strip()
        if key.startswith("vars."):
            parts = key.split(".")
            if len(parts) >= 3:
                scope, k = parts[1], ".".join(parts[2:])
                cache_bucket = kv_cache.setdefault(scope, {})
                if k not in cache_bucket:
                    cache_bucket[k] = kv_get(bot_id, scope, chat_id if scope != "bot" else None,
                                             user_id if scope == "user" else None, k)
                return "" if cache_bucket[k] is None else str(cache_bucket[k])
        return str(_resolve_path(base_ctx, key))

    return _token_pat.sub(_sub, tpl)


class FlowVM:
    def __init__(self, bot_id: int, blocks: dict):
        self.bot_id = bot_id
        self.blocks = blocks or {"entries": []}

    async def run_entry(self, app: Application, update: Update, ctx: ContextTypes.DEFAULT_TYPE, entry: dict):
        message = update.effective_message
        user = update.effective_user
        chat = update.effective_chat
        args = (ctx.args or [])
        chat_id = str(chat.id) if chat else None
        user_id = str(user.id) if user else None

        locals_map: Dict[str, Any] = {}
        kv_cache: Dict[str, dict] = {}

        base_ctx = {
            "args": " ".join(args),
            "arg0": args[0] if args else "",
            "input": {"text": message.text if message else ""},
            "user": {"id": user.id if user else "", "username": user.username if user else "",
                     "first_name": user.first_name if user else "", "last_name": user.last_name if user else ""},
            "chat": {"id": chat.id if chat else "", "type": chat.type if chat else ""},
            "local": locals_map
        }

        async def send_text(text: str, parse_mode: Optional[str], no_preview: bool):
            t = _render_with_vars(text, base_ctx, self.bot_id, chat_id, user_id, kv_cache)
            await message.reply_text(t, parse_mode=parse_mode or None, disable_web_page_preview=bool(no_preview))

        def _build_keyboard(raw: Any):
            # ... (这部分不变)
            if raw is None: return None
            data = raw
            if isinstance(raw, str):
                rendered = _render_with_vars(raw, base_ctx, self.bot_id, chat_id, user_id, kv_cache)
                txt = (rendered or "").strip()
                if not txt: return None
                try:
                    data = json.loads(txt)
                except Exception:
                    return None
            if not isinstance(data, list): return None
            rows: List[List[InlineKeyboardButton]] = []
            for row in data:
                if not isinstance(row, list): continue
                btns: List[InlineKeyboardButton] = []
                for btn in row:
                    if not isinstance(btn, dict): continue
                    text_raw = btn.get("text") or ""
                    text_val = _render_with_vars(str(text_raw), base_ctx, self.bot_id, chat_id, user_id,
                                                 kv_cache).strip()
                    if not text_val: continue
                    url_raw = btn.get("url")
                    cb_raw = btn.get("callback_data")
                    url_val = _render_with_vars(str(url_raw), base_ctx, self.bot_id, chat_id, user_id,
                                                kv_cache).strip() if url_raw else None
                    cb_val = _render_with_vars(str(cb_raw), base_ctx, self.bot_id, chat_id, user_id,
                                               kv_cache).strip() if cb_raw else None
                    if url_val:
                        btns.append(InlineKeyboardButton(text=text_val, url=url_val))
                    else:
                        if not cb_val: cb_val = text_val[:64]
                        btns.append(InlineKeyboardButton(text=text_val, callback_data=cb_val[:64]))
                if btns: rows.append(btns)
            if rows: return InlineKeyboardMarkup(rows)
            return None

        async def send_text_keyboard(text: str, parse_mode: Optional[str], no_preview: bool, keyboard_raw: Any):
            t = _render_with_vars(text, base_ctx, self.bot_id, chat_id, user_id, kv_cache)
            markup = _build_keyboard(keyboard_raw)
            await message.reply_text(t, parse_mode=parse_mode or None, disable_web_page_preview=bool(no_preview),
                                     reply_markup=markup)

        # Bug 修复：使用 app.bot 而不是 message.bot
        async def send_media(kind: str, url: str, caption: str, parse_mode: Optional[str]):
            u = _render_with_vars(url, base_ctx, self.bot_id, chat_id, user_id, kv_cache)
            c = _render_with_vars(caption, base_ctx, self.bot_id, chat_id, user_id, kv_cache)
            if kind == "photo":
                await app.bot.send_photo(chat_id=chat.id, photo=u, caption=c, parse_mode=parse_mode or None)
            elif kind == "document":
                await app.bot.send_document(chat_id=chat.id, document=u, caption=c, parse_mode=parse_mode or None)
            elif kind == "animation":
                await app.bot.send_animation(chat_id=chat.id, animation=u, caption=c, parse_mode=parse_mode or None)
            elif kind == "voice":
                await app.bot.send_voice(chat_id=chat.id, voice=u, caption=c, parse_mode=parse_mode or None)
            elif kind == "sticker":
                await app.bot.send_sticker(chat_id=chat.id, sticker=u)

        # ... (其余逻辑如 http_call, 顺序执行节点等基本不变，除了 send_media 的调用)
        async def http_call(node: dict):
            import aiohttp
            method = (node.get("method") or "GET").upper()
            url = _render_with_vars(node.get("url", ""), base_ctx, self.bot_id, chat_id, user_id, kv_cache)
            headers_txt = _render_with_vars(node.get("headers") or "", base_ctx, self.bot_id, chat_id, user_id,
                                            kv_cache)
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
                async with sess.request(method, url, headers=headers or None,
                                        json=(data if isinstance(data, dict) else None),
                                        data=(data if isinstance(data, (bytes, str)) else None), timeout=15) as resp:
                    raw = await resp.text()
                    val: Any = raw
                    try:
                        j = json.loads(raw)
                        jpath = (node.get("json_path") or "").strip()
                        if jpath:
                            cur = j
                            for part in jpath.split("."):
                                if part == "": continue
                                if isinstance(cur, dict) and part in cur:
                                    cur = cur[part]
                                else:
                                    cur = None; break
                            val = cur
                        else:
                            val = j
                    except Exception:
                        pass
            save = node.get("save_to") or {};
            scope = save.get("scope") or "chat";
            key = save.get("key") or "resp"
            kv_set(self.bot_id, scope, chat_id if scope != "bot" else None, user_id if scope == "user" else None, key,
                   val)
            kv_cache.setdefault(scope, {})[key] = val

        for n in (entry.get("nodes") or []):
            t = n.get("type")
            if t == "send_text":
                await send_text(n.get("text") or "", n.get("parse_mode") or None, bool(n.get("disable_preview")))
            elif t in ("send_photo", "send_document", "send_animation"):
                await send_media(t.split("_", 1)[1], n.get("url") or "", n.get("caption") or "", n.get("parse_mode"))
            elif t == "send_voice":
                await send_media("voice", n.get("url") or "", n.get("caption") or "", n.get("parse_mode"))
            elif t == "send_sticker":
                await send_media("sticker", n.get("file_id") or n.get("sticker") or "", "", None)
            elif t == "send_text_keyboard":
                await send_text_keyboard(n.get("text") or "", n.get("parse_mode") or None,
                                         bool(n.get("disable_preview")),
                                         n.get("keyboard") or n.get("keyboard_json") or n.get("buttons"))
            # ... (变量、条件、延迟等逻辑不变)
            elif t == "set_var":
                mode = n.get("mode") or "text";
                scope, key = (n.get("scope") or "chat"), (n.get("key") or "k")
                if mode == "random":
                    lo = int(n.get("random", {}).get("min", 1));
                    hi = int(n.get("random", {}).get("max", 100))
                    val = int(lo + (time.time_ns() % (max(1, hi - lo + 1))))
                else:
                    val = _render_with_vars(n.get("value") or "", base_ctx, self.bot_id, chat_id, user_id, kv_cache)
                kv_set(self.bot_id, scope, chat_id if scope != "bot" else None, user_id if scope == "user" else None,
                       key, val);
                kv_cache.setdefault(scope, {})[key] = val
            elif t == "inc_var":
                scope, key = (n.get("scope") or "chat"), (n.get("key") or "count");
                step = int(n.get("step") or 1)
                cur = kv_get(self.bot_id, scope, chat_id if scope != "bot" else None,
                             user_id if scope == "user" else None, key)
                try:
                    cur = int(cur or 0)
                except Exception:
                    cur = 0
                val = cur + step
                kv_set(self.bot_id, scope, chat_id if scope != "bot" else None, user_id if scope == "user" else None,
                       key, val);
                kv_cache.setdefault(scope, {})[key] = val
            elif t == "get_var":
                scope, key, alias = (n.get("scope") or "chat"), (n.get("key") or "k"), (n.get("alias") or "x")
                val = kv_get(self.bot_id, scope, chat_id if scope != "bot" else None,
                             user_id if scope == "user" else None, key);
                locals_map[alias] = val
            elif t == "set_local_from_input":
                alias = n.get("alias") or "x";
                locals_map[alias] = base_ctx["input"]["text"]
            elif t == "if_var":
                def _asnum(x):
                    try:
                        if isinstance(x, str) and x.strip() != '' and re.fullmatch(r"-?\d+(\.\d+)?",
                                                                                   x.strip()): return float(
                            x) if "." in x else int(x)
                        return float(x) if isinstance(x, (int, float)) else x
                    except Exception:
                        return x

                left = locals_map.get((n.get("left") or {}).get("var", "x"));
                right_raw = (n.get("right") or {}).get("text", "");
                right = _render_with_vars(str(right_raw), base_ctx, self.bot_id, chat_id, user_id, kv_cache)
                L = _asnum(left);
                R = _asnum(right);
                op = n.get("op") or "eq";
                ok = False
                if op == "eq":
                    ok = (L == R)
                elif op == "ne":
                    ok = (L != R)
                elif op == "contains":
                    ok = (str(left) in str(right)) if False else (str(right) in str(left))
                elif op == "gt":
                    try:
                        ok = (float(L) > float(R))
                    except:
                        ok = False
                elif op == "lt":
                    try:
                        ok = (float(L) < float(R))
                    except:
                        ok = False
                branch = (n.get("then") if ok else n.get("else")) or []
                for bn in branch:
                    bt = bn.get("type")
                    if bt == "send_text":
                        await send_text(bn.get("text") or "", bn.get("parse_mode") or None,
                                        bool(bn.get("disable_preview")))
                    elif bt in ("send_photo", "send_document", "send_animation"):
                        await send_media(bt.split("_", 1)[1], bn.get("url") or "", bn.get("caption") or "", None)
            elif t == "http":
                await http_call(n)
            elif t == "delay":
                try:
                    sec = float(n.get("seconds") or 0)
                except Exception:
                    sec = 0
                if sec > 0: await asyncio.sleep(min(sec, 300))
            elif t == "wait_next":
                await_key = f"await_{entry.get('id')}";
                kv_set(self.bot_id, "chat", chat_id, None, await_key,
                       {"expect": (n.get("expect") or "any"), "next": n.get("next") or []})
                prompt = n.get("prompt") or ""
                if prompt: await send_text(prompt, None, False)
                break

    # ... (maybe_resume 不变)
    async def maybe_resume(self, app: Application, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        message = update.effective_message;
        user = update.effective_user;
        chat = update.effective_chat
        chat_id = str(chat.id) if chat else None;
        user_id = str(user.id) if user else None

        for entry in (self.blocks.get("entries") or []):
            await_key = f"await_{entry.get('id')}"
            st = kv_get(self.bot_id, "chat", chat_id, None, await_key)
            if not st: continue

            st = json.loads(st) if isinstance(st, str) else st  # kv_store returns string
            expect = st.get("expect") or "any";
            nxt: List[dict] = st.get("next") or []
            text = message.text or ""

            if expect == "number" and not re.fullmatch(r"-?\d+", text.strip() or ""): return False

            kv_set(self.bot_id, "chat", chat_id, None, await_key, None)

            fake_entry = {"id": entry.get("id"), "nodes": nxt}
            ctx.args = (message.text or "").split()[1:] if (message.text or "").startswith("/") else (
                        message.text or "").split()
            await self.run_entry(app, update, ctx, fake_entry)
            return True
        return False


def load_vms_for_bot(bot_id: int) -> List[FlowVM]:
    vms: List[FlowVM] = []
    for row in _list_flows(bot_id):
        if int(row.get("active", 1)) != 1: continue
        try:
            blocks = json.loads(row.get("blocks_json") or "{}")
            if isinstance(blocks, str): blocks = json.loads(blocks)
        except Exception:
            blocks = {"entries": []}
        vms.append(FlowVM(bot_id, blocks))
    return vms

__all__ = ["FlowVM", "load_vms_for_bot"]
