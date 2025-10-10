"""Fixed command management endpoints."""
from __future__ import annotations

import json

from flask import jsonify, request

from data.database import delete_command, erase_commands, get_bot, list_commands, upsert_command
from interact.security import login_required

from . import api_bp


@api_bp.get("/bots/<int:bot_id>/commands")
@login_required
def api_list_commands(bot_id: int):
    from flask import g

    if not get_bot(g.user["id"], bot_id):
        return jsonify({"items": []})
    return jsonify({"items": list_commands(bot_id)})


@api_bp.post("/bots/<int:bot_id>/commands")
@login_required
def api_upsert_command(bot_id: int):
    from flask import g

    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    data = request.get_json(silent=True) or {}
    command = (data.get("command") or "").strip()
    kind = (data.get("kind") or "text").strip()
    reply = data.get("reply")
    payload_obj = data.get("payload")
    if isinstance(payload_obj, (dict, list)):
        payload = json.dumps(payload_obj, ensure_ascii=False)
    elif isinstance(payload_obj, str):
        payload = payload_obj
    else:
        payload = None
    parse_mode = (data.get("parse_mode") or None)
    disable_preview = 1 if data.get("disable_preview") else 0
    ok, err = upsert_command(bot_id, command, kind, reply, payload, parse_mode, disable_preview)
    status = 200 if ok else 400
    return jsonify({"ok": ok, "error": err}), status


@api_bp.delete("/bots/<int:bot_id>/commands/<command>")
@login_required
def api_delete_command(bot_id: int, command: str):
    from flask import g

    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    ok, err = delete_command(bot_id, "/" + command.lstrip("/"))
    status = 200 if ok else 404
    return jsonify({"ok": ok, "error": err}), status


@api_bp.delete("/bots/<int:bot_id>/commands")
@login_required
def api_erase_commands(bot_id: int):
    from flask import g

    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    ok, err = erase_commands(bot_id)
    return jsonify({"ok": ok, "error": err})
