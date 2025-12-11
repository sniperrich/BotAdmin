"""Flow runtime helpers."""
import asyncio, json, re, time
from typing import List, Dict, Any, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, Application

# 导入所有需要的异步数据库函数
from data.database import list_flows as _list_flows, kv_get, kv_set

_token_pat = re.compile(r"\{\{\s*([\w\.]+)\s*\}\}")
_var_pat = re.compile(r"\{\{\s*vars\.([\w\.]+)\s*\}\}")


def _resolve_path(d: Any, path: str):
    cur = d
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return ""
    return "" if cur is None else cur


async def _prefetch_vars(tpl: str | None, bot_id: int, chat_id: str | None, user_id: str | None, kv_cache: dict):
    """Scan template for {{ vars... }} and pre-fetch them into kv_cache."""
    if not tpl:
        return
    
    tasks = []
    
    async def _fetch(full_key_path):
        # path is like "scope.key" or "scope.sub.key"
        parts = full_key_path.split(".")
        if len(parts) >= 2:
            scope = parts[0]
            key = ".".join(parts[1:])
            
            # Check if already in cache
            if scope in kv_cache and key in kv_cache[scope]:
                return

            val = await kv_get(bot_id, scope, chat_id if scope != "bot" else None,
                               user_id if scope == "user" else None, key)
            kv_cache.setdefault(scope, {})[key] = val

    # Find all matches
    matches = _var_pat.findall(tpl)
    for m in matches:
        tasks.append(_fetch(m))
    
    if tasks:
        await asyncio.gather(*tasks)


def _render_synch(tpl: str | None, base_ctx: dict, kv_cache: dict):
    """Synchronous render using pre-fetched cache."""
    if not tpl: return ""

    def _sub(m):
        key = m.group(1).strip()
        if key.startswith("vars."):
            # key is like "vars.scope.key"
            parts = key.split(".")
            if len(parts) >= 3:
                scope = parts[1]
                k = ".".join(parts[2:])
                # Try cache
                bucket = kv_cache.get(scope, {})
                val = bucket.get(k)
                if val is not None:
                    return str(val)
                return "" # Default empty if not found/fetched
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
        kv_cache: Dict[str, dict] = {} # scope -> {key: val}

        base_ctx = {
            "args": " ".join(args),
            "arg0": args[0] if args else "",
            "input": {"text": message.text if message else ""},
            "user": {"id": user.id if user else "", "username": user.username if user else "",
                     "first_name": user.first_name if user else "", "last_name": user.last_name if user else ""},
            "chat": {"id": chat.id if chat else "", "type": chat.type if chat else ""},
            "local": locals_map
        }

        # Helper to render async
        async def _render(text: str) -> str:
            await _prefetch_vars(text, self.bot_id, chat_id, user_id, kv_cache)
            return _render_synch(text, base_ctx, kv_cache)

        async def send_text(text: str, parse_mode: Optional[str], no_preview: bool):
            t = await _render(text)
            if message:
                await message.reply_text(t, parse_mode=parse_mode or None, disable_web_page_preview=bool(no_preview))

        def _build_keyboard_markup(rows_data: List):
             # This assumes rows_data is already fully rendered objects/dicts
            if not isinstance(rows_data, list): return None
            rows: List[List[InlineKeyboardButton]] = []
            for row in rows_data:
                if not isinstance(row, list): continue
                btns: List[InlineKeyboardButton] = []
                for btn in row:
                    if not isinstance(btn, dict): continue
                    text_val = str(btn.get("text") or "")
                    if not text_val: continue
                    url_val = btn.get("url")
                    cb_val = btn.get("callback_data")
                    if url_val:
                        btns.append(InlineKeyboardButton(text=text_val, url=url_val))
                    else:
                        if not cb_val: cb_val = text_val[:64]
                        btns.append(InlineKeyboardButton(text=text_val, callback_data=cb_val[:64]))
                if btns: rows.append(btns)
            if rows: return InlineKeyboardMarkup(rows)
            return None

        async def send_text_keyboard(text: str, parse_mode: Optional[str], no_preview: bool, keyboard_raw: Any):
            t = await _render(text)
            
            # Rendering keyboard JSON structure...
            # If keyboard_raw is string, render it then parse
            markup = None
            if keyboard_raw:
                data = keyboard_raw
                if isinstance(keyboard_raw, str):
                    rendered_json = await _render(keyboard_raw)
                    if rendered_json.strip():
                        try:
                            data = json.loads(rendered_json)
                        except:
                            data = None
                
                # Now we have data (list or dict), but inside it might be strings that need rendering?
                # For simplicity, we assume if it came from JSON string it is resolved.
                # If it is a python object structure (from YAML/JSON loaded flows), we might need deep render.
                # Let's do a deep render pass on the data structure if needed.
                # ACTUALLY, _build_keyboard logic in original code did render each button text.
                # So we must recreate that logic async.
                
                if isinstance(data, list):
                    # Deep render the buttons
                    new_rows = []
                    for row in data:
                        if not isinstance(row, list): continue
                        new_row = []
                        for btn in row:
                             if not isinstance(btn, dict): continue
                             
                             # Render fields
                             b_text = await _render(str(btn.get("text") or ""))
                             b_url = await _render(str(btn.get("url") or "")) if btn.get("url") else None
                             b_cb = await _render(str(btn.get("callback_data") or "")) if btn.get("callback_data") else None
                             
                             new_btn = {"text": b_text}
                             if b_url: new_btn["url"] = b_url
                             if b_cb: new_btn["callback_data"] = b_cb
                             new_row.append(new_btn)
                        new_rows.append(new_row)
                    markup = _build_keyboard_markup(new_rows)
            
            if message:
                await message.reply_text(t, parse_mode=parse_mode or None, disable_web_page_preview=bool(no_preview),
                                         reply_markup=markup)

        async def send_media(kind: str, url: str, caption: str, parse_mode: Optional[str]):
            u = await _render(url)
            c = await _render(caption)
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

        async def http_call(node: dict):
            import aiohttp
            method = (node.get("method") or "GET").upper()
            url = await _render(node.get("url", ""))
            headers_txt = await _render(node.get("headers") or "")
            body_txt = await _render(node.get("body") or "")
            
            try:
                headers = json.loads(headers_txt) if headers_txt else {}
            except Exception:
                headers = {}
            try:
                data = json.loads(body_txt) if body_txt else None
            except Exception:
                data = body_txt.encode("utf-8") if body_txt else None

            async with aiohttp.ClientSession() as sess:
                try:
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
                except Exception as e:
                    # Log error?
                    val = str(e)

            save = node.get("save_to") or {};
            scope = save.get("scope") or "chat";
            key = save.get("key") or "resp"
            
            await kv_set(self.bot_id, scope, chat_id if scope != "bot" else None, user_id if scope == "user" else None, key,
                   val)
            kv_cache.setdefault(scope, {})[key] = val

        # --- Node Execution Loop ---
        for n in (entry.get("nodes") or []):
            try:
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
                elif t == "set_var":
                    mode = n.get("mode") or "text";
                    scope, key = (n.get("scope") or "chat"), (n.get("key") or "k")
                    if mode == "random":
                        lo = int(n.get("random", {}).get("min", 1));
                        hi = int(n.get("random", {}).get("max", 100))
                        val = int(lo + (time.time_ns() % (max(1, hi - lo + 1))))
                    else:
                        val = await _render(n.get("value") or "")
                    await kv_set(self.bot_id, scope, chat_id if scope != "bot" else None, user_id if scope == "user" else None,
                           key, val);
                    kv_cache.setdefault(scope, {})[key] = val
                elif t == "inc_var":
                    scope, key = (n.get("scope") or "chat"), (n.get("key") or "count");
                    step = int(n.get("step") or 1)
                    cur = await kv_get(self.bot_id, scope, chat_id if scope != "bot" else None,
                                 user_id if scope == "user" else None, key)
                    try:
                        cur = int(cur or 0)
                    except Exception:
                        cur = 0
                    val = cur + step
                    await kv_set(self.bot_id, scope, chat_id if scope != "bot" else None, user_id if scope == "user" else None,
                           key, val);
                    kv_cache.setdefault(scope, {})[key] = val
                elif t == "get_var":
                    scope, key, alias = (n.get("scope") or "chat"), (n.get("key") or "k"), (n.get("alias") or "x")
                    val = await kv_get(self.bot_id, scope, chat_id if scope != "bot" else None,
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
                    
                    # Async render for right side
                    right = await _render(str(right_raw))
                    
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
                    
                    # Recursive branch execution (simplified duplicate logic)
                    # Ideally we should split execution logic to a reusable async method, but for now inline is safer for conversion.
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
                    await kv_set(self.bot_id, "chat", chat_id, None, await_key,
                           json.dumps({"expect": (n.get("expect") or "any"), "next": n.get("next") or []}))
                    prompt = n.get("prompt") or ""
                    if prompt: await send_text(prompt, None, False)
                    break 
            except Exception as e:
                # Log error? 
                print(f"Flow error: {e}")
                pass

    async def maybe_resume(self, app: Application, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        message = update.effective_message;
        user = update.effective_user;
        chat = update.effective_chat
        
        if not message: return False
        
        chat_id = str(chat.id) if chat else None;
        # user_id = str(user.id) if user else None

        for entry in (self.blocks.get("entries") or []):
            await_key = f"await_{entry.get('id')}"
            st = await kv_get(self.bot_id, "chat", chat_id, None, await_key)
            if not st: continue

            st = json.loads(st) if isinstance(st, str) else st  # kv_store returns string
            expect = st.get("expect") or "any";
            nxt: List[dict] = st.get("next") or []
            text = message.text or ""

            if expect == "number" and not re.fullmatch(r"-?\d+", text.strip() or ""): return False

            await kv_set(self.bot_id, "chat", chat_id, None, await_key, None)

            fake_entry = {"id": entry.get("id"), "nodes": nxt}
            ctx.args = (message.text or "").split()[1:] if (message.text or "").startswith("/") else (
                        message.text or "").split()
            await self.run_entry(app, update, ctx, fake_entry)
            return True
        return False


async def load_vms_for_bot(bot_id: int) -> List[FlowVM]:
    vms: List[FlowVM] = []
    # list_flows is now async/awaitable
    for row in await _list_flows(bot_id):
        if int(row.get("active", 1)) != 1: continue
        group_flag = row.get("group_active")
        if group_flag is not None:
            try:
                if int(group_flag) != 1:
                    continue
            except (TypeError, ValueError):
                if not group_flag:
                    continue
        try:
            blocks = json.loads(row.get("blocks_json") or "{}")
            if isinstance(blocks, str): blocks = json.loads(blocks)
        except Exception:
            blocks = {"entries": []}
        vms.append(FlowVM(bot_id, blocks))
    return vms

__all__ = ["FlowVM", "load_vms_for_bot"]
