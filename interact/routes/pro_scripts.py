"""Pro script management endpoints."""
from __future__ import annotations

from flask import jsonify, request

from data.database import (
    delete_pro_script,
    get_bot,
    list_pro_scripts,
    set_pro_script_active,
    set_pro_script_group,
    upsert_pro_script,
)
from interact.security import login_required

from . import api_bp


@api_bp.get("/bots/<int:bot_id>/pro_scripts")
@login_required
def api_list_pro_scripts(bot_id: int):
    from flask import g

    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限", "items": []}), 403
    return jsonify({"ok": True, "items": list_pro_scripts(bot_id)})


@api_bp.post("/bots/<int:bot_id>/pro_scripts")
@login_required
def api_upsert_pro_script(bot_id: int):
    from flask import g

    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    data = request.get_json(silent=True) or {}
    script_id = data.get("id")
    name = (data.get("name") or "").strip()
    command = (data.get("command") or "").strip()
    code = (data.get("code") or "").strip()
    active = int(bool(data.get("active", True)))
    group_id = data.get("group_id")
    ok, err, sid = upsert_pro_script(bot_id, name, command, code, script_id, active, group_id)
    status = 200 if ok else 400
    return jsonify({"ok": ok, "error": err, "id": sid}), status


@api_bp.delete("/bots/<int:bot_id>/pro_scripts/<int:script_id>")
@login_required
def api_delete_pro_script(bot_id: int, script_id: int):
    from flask import g

    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    ok, err = delete_pro_script(bot_id, script_id)
    status = 200 if ok else 404
    return jsonify({"ok": ok, "error": err}), status


@api_bp.patch("/bots/<int:bot_id>/pro_scripts/<int:script_id>/active")
@login_required
def api_set_pro_script_active(bot_id: int, script_id: int):
    from flask import g

    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    data = request.get_json(silent=True) or {}
    active = 1 if data.get("active", True) else 0
    ok, err = set_pro_script_active(bot_id, script_id, active)
    status = 200 if ok else 404
    return jsonify({"ok": ok, "error": err}), status


@api_bp.patch("/bots/<int:bot_id>/pro_scripts/<int:script_id>/group")
@login_required
def api_set_pro_script_group(bot_id: int, script_id: int):
    from flask import g

    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    data = request.get_json(silent=True) or {}
    group_id = data.get("group_id")
    ok, err = set_pro_script_group(bot_id, script_id, group_id)
    status = 200 if ok else 404
    return jsonify({"ok": ok, "error": err}), status
