"""Feature group management endpoints."""
from __future__ import annotations

from flask import jsonify, request

from data.database import (
    delete_feature_group,
    get_bot,
    list_feature_groups,
    set_feature_group_active,
    upsert_feature_group,
)
from interact.security import login_required

from . import api_bp


@api_bp.get("/bots/<int:bot_id>/groups/<string:kind>")
@login_required
def api_list_feature_groups(bot_id: int, kind: str):
    from flask import g

    if not get_bot(g.user["id"], bot_id):
        return jsonify({"items": []})
    groups = list_feature_groups(bot_id, kind)
    return jsonify({"items": groups})


@api_bp.post("/bots/<int:bot_id>/groups/<string:kind>")
@login_required
def api_upsert_feature_group(bot_id: int, kind: str):
    from flask import g

    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    data = request.get_json(silent=True) or {}
    group_id = data.get("id")
    name = data.get("name") or ""
    description = data.get("description") or ""
    active = data.get("active", True)
    ok, err, gid = upsert_feature_group(bot_id, kind, name, description, group_id, active)
    status = 200 if ok else 400
    return jsonify({"ok": ok, "error": err, "id": gid}), status


@api_bp.patch("/bots/<int:bot_id>/groups/<int:group_id>/active")
@login_required
def api_set_feature_group_active(bot_id: int, group_id: int):
    from flask import g

    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    data = request.get_json(silent=True) or {}
    active = data.get("active", True)
    ok, err = set_feature_group_active(bot_id, group_id, active)
    status = 200 if ok else 404
    return jsonify({"ok": ok, "error": err}), status


@api_bp.delete("/bots/<int:bot_id>/groups/<int:group_id>")
@login_required
def api_delete_feature_group(bot_id: int, group_id: int):
    from flask import g

    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    ok, err = delete_feature_group(bot_id, group_id)
    status = 200 if ok else 404
    return jsonify({"ok": ok, "error": err}), status
