"""Fixed command management endpoints."""
from __future__ import annotations

import json

from flask import jsonify, request

from data.database import (
    delete_command,
    erase_commands,
    get_bot,
    list_commands,
    set_command_active,
    set_command_group,
    upsert_command,
)
from interact.security import login_required

from . import api_bp


@api_bp.get("/bots/<int:bot_id>/commands")
@login_required
async def api_list_commands(bot_id: int):
    from flask import g

    if not await get_bot(g.user["id"], bot_id):
        return jsonify({"items": []})
    return jsonify({"items": await list_commands(bot_id)})


@api_bp.post("/bots/<int:bot_id>/commands")
@login_required
async def api_upsert_command(bot_id: int):
    from flask import g

    if not await get_bot(g.user["id"], bot_id):
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
    active = 1 if data.get("active", True) else 0
    group_id_raw = data.get("group_id")
    group_id = None
    if isinstance(group_id_raw, (int, float)):
        group_id = int(group_id_raw)
    elif isinstance(group_id_raw, str) and group_id_raw.strip():
        try:
            group_id = int(group_id_raw)
        except ValueError:
            group_id = None
    ok, err = await upsert_command(
        bot_id,
        command,
        kind,
        reply,
        payload,
        parse_mode,
        disable_preview,
        active,
        group_id,
    )
    status = 200 if ok else 400
    return jsonify({"ok": ok, "error": err}), status


@api_bp.delete("/bots/<int:bot_id>/commands/<command>")
@login_required
async def api_delete_command(bot_id: int, command: str):
    from flask import g

    if not await get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    ok, err = await delete_command(bot_id, "/" + command.lstrip("/"))
    status = 200 if ok else 404
    return jsonify({"ok": ok, "error": err}), status


@api_bp.delete("/bots/<int:bot_id>/commands")
@login_required
async def api_erase_commands(bot_id: int):
    from flask import g

    if not await get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    ok, err = await erase_commands(bot_id)
    return jsonify({"ok": ok, "error": err})


@api_bp.patch("/bots/<int:bot_id>/commands/<int:command_id>/active")
@login_required
async def api_set_command_active(bot_id: int, command_id: int):
    from flask import g

    if not await get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    data = request.get_json(silent=True) or {}
    active = 1 if data.get("active", True) else 0
    ok, err = await set_command_active(bot_id, command_id, active)
    status = 200 if ok else 404
    return jsonify({"ok": ok, "error": err}), status


@api_bp.patch("/bots/<int:bot_id>/commands/<int:command_id>/group")
@login_required
async def api_set_command_group(bot_id: int, command_id: int):
    from flask import g

    if not await get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    data = request.get_json(silent=True) or {}
    group_id = data.get("group_id")
    ok, err = await set_command_group(bot_id, command_id, group_id)
    status = 200 if ok else 404
    return jsonify({"ok": ok, "error": err}), status
