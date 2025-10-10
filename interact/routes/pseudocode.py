"""Pseudocode endpoints."""
from __future__ import annotations

import json

from flask import jsonify, request

from core.pseudo import generate_flow_from_pseudocode, simulate_flow
from data.database import (
    get_bot,
    get_pseudocode,
    list_pseudocode,
    upsert_flow,
    upsert_pseudocode,
    delete_pseudocode,
)
from interact.security import login_required

from . import api_bp


@api_bp.get("/bots/<int:bot_id>/pseudocode")
@login_required
def api_list_pseudocode(bot_id: int):
    from flask import g

    if not get_bot(g.user["id"], bot_id):
        return jsonify({"items": []})
    return jsonify({"items": list_pseudocode(bot_id)})


@api_bp.post("/bots/<int:bot_id>/pseudocode")
@login_required
def api_upsert_pseudocode(bot_id: int):
    from flask import g

    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    data = request.get_json(silent=True) or {}
    pseudo_id = data.get("id")
    title = data.get("title") or ""
    content = data.get("content") or ""
    ok, err, pid = upsert_pseudocode(bot_id, title, content, pseudo_id)
    status = 200 if ok else 400
    return jsonify({"ok": ok, "error": err, "id": pid}), status


@api_bp.delete("/bots/<int:bot_id>/pseudocode/<int:item_id>")
@login_required
def api_delete_pseudocode(bot_id: int, item_id: int):
    from flask import g

    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    ok, err = delete_pseudocode(bot_id, item_id)
    status = 200 if ok else 404
    return jsonify({"ok": ok, "error": err}), status


@api_bp.post("/bots/<int:bot_id>/pseudocode/<int:item_id>/generate_flow")
@login_required
def api_generate_flow_from_pseudo(bot_id: int, item_id: int):
    from flask import g

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
    return jsonify(
        {
            "ok": True,
            "id": fid,
            "flow": result["compiled"],
            "summary": result["summary"],
            "command": result["command"],
            "name": result["name"],
        }
    )


@api_bp.post("/bots/<int:bot_id>/pseudocode/<int:item_id>/sandbox")
@login_required
def api_sandbox_pseudocode(bot_id: int, item_id: int):
    from flask import g

    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    pseudo = get_pseudocode(bot_id, item_id)
    if not pseudo:
        return jsonify({"ok": False, "error": "伪代码不存在"}), 404
    data = request.get_json(silent=True) or {}
    result = generate_flow_from_pseudocode(pseudo["title"], pseudo["content"])
    sim = simulate_flow(result["compiled"], data.get("input", "/demo"))
    return jsonify(
        {
            "ok": True,
            "actions": sim["actions"],
            "summary": sim["summary"],
            "analysis": result["summary"],
            "command": result["command"],
        }
    )
