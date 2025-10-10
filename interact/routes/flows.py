"""Flow management endpoints."""
from __future__ import annotations

import json

from flask import jsonify, request

from data.database import delete_flow, get_bot, list_flows, upsert_flow
from interact.security import login_required
from interact.utils import normalize_flow_blocks

from . import api_bp


@api_bp.get("/bots/<int:bot_id>/flows")
@login_required
def api_list_flows(bot_id: int):
    from flask import g

    if not get_bot(g.user["id"], bot_id):
        return jsonify({"items": []})
    items = list_flows(bot_id)
    for item in items:
        blocks_json = item.get("blocks_json")
        parsed = None
        if isinstance(blocks_json, str) and blocks_json.strip():
            try:
                parsed = json.loads(blocks_json)
                if isinstance(parsed, str):
                    parsed = json.loads(parsed)
            except Exception:
                parsed = None
        item["blocks_compiled"] = parsed
    return jsonify({"items": items})


@api_bp.post("/bots/<int:bot_id>/flows")
@login_required
def api_upsert_flow(bot_id: int):
    from flask import g

    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    data = request.get_json(silent=True) or {}
    flow_id = data.get("id")
    name = (data.get("name") or "").strip()
    try:
        normalized = normalize_flow_blocks(data.get("blocks_json"))
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    if not normalized:
        return jsonify({"ok": False, "error": "blocks_json 不能为空"}), 400
    active = int(bool(data.get("active", 1)))
    ok, err, fid = upsert_flow(bot_id, name, normalized, flow_id, active)
    status = 200 if ok else 400
    return jsonify({"ok": ok, "error": err, "id": fid}), status


@api_bp.delete("/bots/<int:bot_id>/flows/<int:flow_id>")
@login_required
def api_delete_flow(bot_id: int, flow_id: int):
    from flask import g

    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    ok, err = delete_flow(bot_id, flow_id)
    status = 200 if ok else 404
    return jsonify({"ok": ok, "error": err}), status
