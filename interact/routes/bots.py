"""Bot CRUD endpoints."""
from __future__ import annotations

from flask import jsonify, request

from core.runtime import registry
from data import create_bot, delete_bot, get_bot, list_bots
from interact.security import login_required
from interact.socket import push_status_for_user
from interact.utils import mask_token

from . import api_bp


@api_bp.get("/bots")
@login_required
def api_list_bots():
    from flask import g

    bots = list_bots(g.user["id"])
    items = []
    for bot in bots:
        items.append(
            {
                "id": bot["id"],
                "name": bot["name"],
                "token_mask": mask_token(bot.get("token")),
                "created_at": bot["created_at"],
            }
        )
    return jsonify({"items": items})


@api_bp.post("/bots")
@login_required
def api_add_bot():
    from flask import g

    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    token = data.get("token", "").strip()
    user_id = g.user["id"]
    ok, err = create_bot(user_id, name, token)
    if ok:
        push_status_for_user(user_id)
    return jsonify({"ok": ok, "error": err})


@api_bp.delete("/bots/<int:bot_id>")
@login_required
def api_delete_bot(bot_id: int):
    from flask import g

    registry.stop(bot_id)
    user_id = g.user["id"]
    ok, err = delete_bot(user_id, bot_id)
    if ok:
        push_status_for_user(user_id)
    status = 200 if ok else 404
    return jsonify({"ok": ok, "error": err}), status
