# app.py
import os
import json
from functools import wraps
from flask import Flask, request, jsonify, session, g, send_from_directory

from db import (
    init_db, create_user, get_user_by_username, get_user_by_id,
    create_bot, list_bots, get_bot, delete_bot,
    list_commands, upsert_command, delete_command, erase_commands,
    list_flows, upsert_flow, delete_flow,
)
from bot_registry import registry

APP_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(APP_DIR, "static")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")
app.secret_key = os.environ.get("APP_SECRET", "dev-secret")
app.config.update(
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_HTTPONLY=True,
)


# ---------------- helpers ----------------
def _mask_token(tok: str) -> str:
    if not tok:
        return ""
    t = tok.strip()
    if len(t) <= 12:
        return t[:2] + "****" + t[-2:]
    return t[:8] + "****" + t[-4:]

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not getattr(g, "user", None):
            return jsonify({"ok": False, "error": "未登录"}), 401
        return f(*args, **kwargs)
    return wrapper

@app.before_request
def load_user():
    uid = session.get("user_id")
    g.user = get_user_by_id(uid) if uid else None


# ---------------- static index ----------------
@app.get("/")
def index_html():
    # 直接把你的前端 index.html 放在 /static 下的话：
    return send_from_directory(STATIC_DIR, "index.html")


# ---------------- auth ----------------
@app.get("/api/me")
def api_me():
    u = g.user
    # 未登录返回 user: None（避免前端取字段时报错）
    return jsonify({"user": ({"id": u["id"], "username": u["username"]} if u else None)})

@app.post("/api/register")
def api_register():
    data = request.get_json(silent=True) or {}
    ok, err = create_user(data.get("username","").strip(), data.get("password",""))
    return jsonify({"ok": ok, "error": err})

@app.post("/api/login")
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username","").strip()
    password = data.get("password","")
    u = get_user_by_username(username)
    if not u:
        return jsonify({"ok": False, "error": "用户不存在"})
    import hashlib
    if u["password_hash"] != hashlib.sha256(password.encode("utf-8")).hexdigest():
        return jsonify({"ok": False, "error": "密码错误"})
    session["user_id"] = u["id"]
    return jsonify({"ok": True})

@app.post("/api/logout")
def api_logout():
    session.clear()
    return jsonify({"ok": True})


# ---------------- bots ----------------
@app.get("/api/bots")
@login_required
def api_list_bots():
    bots = list_bots(g.user["id"])
    items = []
    for b in bots:
        items.append({
            "id": b["id"],
            "name": b["name"],
            "token_mask": _mask_token(b["token"]),
            "created_at": b["created_at"],
        })
    return jsonify({"items": items})

@app.post("/api/bots")
@login_required
def api_add_bot():
    data = request.get_json(silent=True) or {}
    ok, err = create_bot(g.user["id"], data.get("name","").strip(), data.get("token","").strip())
    return jsonify({"ok": ok, "error": err})

@app.delete("/api/bots/<int:bot_id>")
@login_required
def api_del_bot(bot_id: int):
    # 停掉进程
    registry.stop(bot_id)
    ok, err = delete_bot(g.user["id"], bot_id)
    return jsonify({"ok": ok, "error": err})


# ---------------- commands ----------------
@app.get("/api/bots/<int:bot_id>/commands")
@login_required
def api_list_cmds(bot_id: int):
    if not get_bot(g.user["id"], bot_id):
        return jsonify({"items": []})
    return jsonify({"items": list_commands(bot_id)})

@app.post("/api/bots/<int:bot_id>/commands")
@login_required
def api_upsert_cmd(bot_id: int):
    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    data = request.get_json(silent=True) or {}
    command = (data.get("command") or "").strip()
    kind = (data.get("kind") or "text").strip()
    reply = data.get("reply")
    payload_obj = data.get("payload")
    payload = json.dumps(payload_obj, ensure_ascii=False) if isinstance(payload_obj, (dict, list)) else (payload_obj if isinstance(payload_obj, str) else None)
    parse_mode = (data.get("parse_mode") or None)
    disable_preview = 1 if data.get("disable_preview") else 0
    ok, err = upsert_command(bot_id, command, kind, reply, payload, parse_mode, disable_preview)
    return jsonify({"ok": ok, "error": err})

@app.delete("/api/bots/<int:bot_id>/commands/<command>")
@login_required
def api_del_cmd(bot_id: int, command: str):
    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    ok, err = delete_command(bot_id, "/" + command.lstrip("/"))
    return jsonify({"ok": ok, "error": err})

@app.delete("/api/bots/<int:bot_id>/commands")
@login_required
def api_erase_cmds(bot_id: int):
    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    ok, err = erase_commands(bot_id)
    return jsonify({"ok": ok, "error": err})


# ---------------- flows ----------------
@app.get("/api/bots/<int:bot_id>/flows")
@login_required
def api_list_flows(bot_id: int):
    if not get_bot(g.user["id"], bot_id):
        return jsonify({"items": []})
    return jsonify({"items": list_flows(bot_id)})

@app.post("/api/bots/<int:bot_id>/flows")
@login_required
def api_upsert_flow(bot_id: int):
    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    data = request.get_json(silent=True) or {}
    flow_id = data.get("id")
    name = (data.get("name") or "").strip()
    blocks_json = data.get("blocks_json") or ""
    active = int(bool(data.get("active", 1)))
    ok, err, fid = upsert_flow(bot_id, name, blocks_json, flow_id, active)
    return jsonify({"ok": ok, "error": err, "id": fid})

@app.delete("/api/bots/<int:bot_id>/flows/<int:flow_id>")
@login_required
def api_delete_flow(bot_id: int, flow_id: int):
    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    ok, err = delete_flow(bot_id, flow_id)
    return jsonify({"ok": ok, "error": err})


# ---------------- process control ----------------
@app.post("/api/bots/<int:bot_id>/start")
@login_required
def api_bot_start(bot_id: int):
    b = get_bot(g.user["id"], bot_id)
    if not b:
        return jsonify({"ok": False, "error": "无权限"}), 403
    specs = list_commands(bot_id)  # [{command,kind,reply,payload,parse_mode,disable_preview}]
    ok, msg = registry.start(bot_id, b["token"], specs)
    return jsonify({"ok": ok, "msg": msg})

@app.post("/api/bots/<int:bot_id>/stop")
@login_required
def api_bot_stop(bot_id: int):
    b = get_bot(g.user["id"], bot_id)
    if not b:
        return jsonify({"ok": False, "error": "无权限"}), 403
    ok, msg = registry.stop(bot_id)
    return jsonify({"ok": ok, "msg": msg})

@app.post("/api/bots/<int:bot_id>/sync")
@login_required
def api_bot_sync(bot_id: int):
    b = get_bot(g.user["id"], bot_id)
    if not b:
        return jsonify({"ok": False, "error": "无权限"}), 403
    ok, msg = registry.sync(bot_id)
    return jsonify({"ok": ok, "msg": msg})

@app.get("/api/bots/<int:bot_id>/status")
@login_required
def api_bot_status_view(bot_id: int):  # 注意函数名别和别处重复
    b = get_bot(g.user["id"], bot_id)
    if not b:
        return jsonify({"state": "stopped"})
    return jsonify(registry.status(bot_id))


if __name__ == "__main__":
    init_db()
    # 静态文件：把你的 index.html / blocks.html 放到 ./static 目录下
    app.run(host="0.0.0.0", port=8000, debug=True)
