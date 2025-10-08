# app.py
import os
import json
from functools import wraps
from flask import Flask, request, jsonify, session, g, send_from_directory

from db import (
    init_db, create_user, get_user_by_username, get_user_by_id, hash_password,
    create_bot, list_bots, get_bot, delete_bot,
    list_commands, upsert_command, delete_command, erase_commands,
    list_flows, upsert_flow, delete_flow,
    list_pseudocode, upsert_pseudocode, delete_pseudocode, get_pseudocode,
    # 新增
    list_pro_scripts, upsert_pro_script, delete_pro_script
)
from bot_registry import registry
from pseudo_convert import (
    generate_flow_from_pseudocode,
    simulate_flow,
)
from ai_client import (
    generate_pseudocode as ai_generate_pseudocode,
    generate_command as ai_generate_command,
)

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


def _normalize_flow_blocks(raw):
    """Accept either a JSON string or dict and return a canonical JSON string."""
    if raw is None:
        return None
    obj = raw
    if isinstance(raw, str):
        txt = raw.strip()
        if not txt:
            return None
        try:
            obj = json.loads(txt)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid blocks_json: {exc}") from exc
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid blocks_json inner string: {exc}") from exc
    if not isinstance(obj, dict):
        raise ValueError("blocks_json must be a JSON object")
    return json.dumps(obj, ensure_ascii=False)

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
    return send_from_directory(STATIC_DIR, "index.html")


# ---------------- auth ----------------
@app.get("/api/me")
def api_me():
    u = g.user
    return jsonify({"user": ({"id": u["id"], "username": u["username"]} if u else None)})

@app.post("/api/register")
def api_register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    ok, err = create_user(username, password)
    return jsonify({"ok": ok, "error": err})

@app.post("/api/login")
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    u = get_user_by_username(username)
    if not u:
        return jsonify({"ok": False, "error": "用户不存在"})
    if u["password_hash"] != hash_password(password):
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
    items = list_flows(bot_id)
    for item in items:
        bj = item.get("blocks_json")
        parsed = None
        if isinstance(bj, str) and bj.strip():
            try:
                parsed = json.loads(bj)
                if isinstance(parsed, str):
                    parsed = json.loads(parsed)
            except Exception:
                parsed = None
        item["blocks_compiled"] = parsed
    return jsonify({"items": items})

@app.post("/api/bots/<int:bot_id>/flows")
@login_required
def api_upsert_flow(bot_id: int):
    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    data = request.get_json(silent=True) or {}
    flow_id = data.get("id")
    name = (data.get("name") or "").strip()
    try:
        normalized = _normalize_flow_blocks(data.get("blocks_json"))
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    if not normalized:
        return jsonify({"ok": False, "error": "blocks_json 不能为空"}), 400
    active = int(bool(data.get("active", 1)))
    ok, err, fid = upsert_flow(bot_id, name, normalized, flow_id, active)
    return jsonify({"ok": ok, "error": err, "id": fid})

@app.delete("/api/bots/<int:bot_id>/flows/<int:flow_id>")
@login_required
def api_delete_flow(bot_id: int, flow_id: int):
    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    ok, err = delete_flow(bot_id, flow_id)
    return jsonify({"ok": ok, "error": err})


# ---------------- pro scripts (新增) ----------------
@app.get("/api/bots/<int:bot_id>/pro_scripts")
@login_required
def api_list_pro_scripts(bot_id: int):
    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限", "items": []}), 403
    return jsonify({"ok": True, "items": list_pro_scripts(bot_id)})

@app.post("/api/bots/<int:bot_id>/pro_scripts")
@login_required
def api_upsert_pro_script(bot_id: int):
    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    data = request.get_json(silent=True) or {}
    script_id = data.get("id")
    name = data.get("name", "").strip()
    command = data.get("command", "").strip()
    code = data.get("code", "").strip()
    active = int(bool(data.get("active", True)))

    ok, err, sid = upsert_pro_script(bot_id, name, command, code, script_id, active)
    status = 200 if ok else 400
    return jsonify({"ok": ok, "error": err, "id": sid}), status

@app.delete("/api/bots/<int:bot_id>/pro_scripts/<int:script_id>")
@login_required
def api_delete_pro_script(bot_id: int, script_id: int):
    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    ok, err = delete_pro_script(bot_id, script_id)
    status = 200 if ok else 404
    return jsonify({"ok": ok, "error": err}), status


# ---------------- pseudocode ----------------
@app.get("/api/bots/<int:bot_id>/pseudocode")
@login_required
def api_list_pseudocode(bot_id: int):
    if not get_bot(g.user["id"], bot_id):
        return jsonify({"items": []})
    return jsonify({"items": list_pseudocode(bot_id)})


@app.post("/api/bots/<int:bot_id>/pseudocode")
@login_required
def api_upsert_pseudocode(bot_id: int):
    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    data = request.get_json(silent=True) or {}
    pseudo_id = data.get("id")
    title = data.get("title") or ""
    content = data.get("content") or ""
    ok, err, pid = upsert_pseudocode(bot_id, title, content, pseudo_id)
    status = 200 if ok else 400
    return jsonify({"ok": ok, "error": err, "id": pid}), status


@app.delete("/api/bots/<int:bot_id>/pseudocode/<int:item_id>")
@login_required
def api_delete_pseudocode(bot_id: int, item_id: int):
    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    ok, err = delete_pseudocode(bot_id, item_id)
    status = 200 if ok else 404
    return jsonify({"ok": ok, "error": err}), status


@app.post("/api/ai/generate")
@login_required
def api_ai_generate():
    data = request.get_json(silent=True) or {}
    mode = (data.get("mode") or "pseudocode").strip().lower()
    prompt = (data.get("prompt") or "").strip()
    if mode == "pseudocode":
        result, meta = ai_generate_pseudocode(prompt)
        return jsonify({"ok": True, "result": result, "meta": meta})
    if mode == "command":
        result, meta = ai_generate_command(prompt)
        return jsonify({"ok": True, "result": result, "meta": meta})
    return jsonify({"ok": False, "error": "暂不支持的生成模式", "meta": {"api_key_configured": bool(os.environ.get("AI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"))}}), 400


@app.post("/api/bots/<int:bot_id>/pseudocode/<int:item_id>/generate_flow")
@login_required
def api_generate_flow_from_pseudo(bot_id: int, item_id: int):
    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    pseudo = get_pseudocode(bot_id, item_id)
    if not pseudo:
        return jsonify({"ok": False, "error": "伪代码不存在"}), 404
    result = generate_flow_from_pseudocode(pseudo["title"], pseudo["content"])
    compiled_json = json.dumps(result["compiled"], ensure_ascii=False)
    ok, err, fid = upsert_flow(bot_id, result["name"], compiled_json, None, 1)
    if not ok:
        return jsonify({"ok": False, "error": err or "保存流程失败"}), 400
    return jsonify({
        "ok": True,
        "id": fid,
        "flow": result["compiled"],
        "summary": result["summary"],
        "command": result["command"],
        "name": result["name"],
    })


@app.post("/api/bots/<int:bot_id>/pseudocode/<int:item_id>/sandbox")
@login_required
def api_sandbox_pseudocode(bot_id: int, item_id: int):
    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    pseudo = get_pseudocode(bot_id, item_id)
    if not pseudo:
        return jsonify({"ok": False, "error": "伪代码不存在"}), 404
    data = request.get_json(silent=True) or {}
    result = generate_flow_from_pseudocode(pseudo["title"], pseudo["content"])
    sim = simulate_flow(result["compiled"], data.get("input", "/demo"))
    return jsonify({
        "ok": True,
        "actions": sim["actions"],
        "summary": sim["summary"],
        "analysis": result["summary"],
        "command": result["command"],
    })


# ---------------- process control ----------------
@app.post("/api/bots/<int:bot_id>/start")
@login_required
def api_bot_start(bot_id: int):
    b = get_bot(g.user["id"], bot_id)
    if not b:
        return jsonify({"ok": False, "error": "无权限"}), 403
    specs = list_commands(bot_id)
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
def api_bot_status_view(bot_id: int):
    b = get_bot(g.user["id"], bot_id)
    status = dict(registry.status(bot_id))
    if b:
        status.setdefault("bot_id", b["id"])
        status.setdefault("name", b["name"])
    return jsonify({"status": status})


@app.get("/api/bots/<int:bot_id>/logs")
@login_required
def api_bot_logs(bot_id: int):
    b = get_bot(g.user["id"], bot_id)
    if not b:
        return jsonify({"ok": False, "items": [], "error": "无权限"}), 403
    try:
        lines = int(request.args.get("lines", 100))
    except (TypeError, ValueError):
        lines = 100
    lines = max(10, min(lines, 500))
    items = [dict(evt) for evt in registry.logs(bot_id, lines) or []]
    return jsonify({"ok": True, "items": items})


@app.get("/api/bots/status_all")
@login_required
def api_bot_status_all():
    bots = list_bots(g.user["id"])
    running = registry.status_all()
    items = []
    for bot in bots:
        bid = bot["id"]
        snap = running.get(bid)
        if snap is None:
            snap = registry.status(bid)
        snap = dict(snap)
        snap.setdefault("bot_id", bid)
        snap.setdefault("state", "stopped")
        snap.setdefault("uptime", 0)
        snap.setdefault("stats", {"messages": 0, "errors": 0})
        snap["name"] = bot["name"]
        snap["token_mask"] = _mask_token(bot.get("token")) if bot.get("token") else ""
        items.append(snap)
    return jsonify({"items": items})
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8000, debug=True)