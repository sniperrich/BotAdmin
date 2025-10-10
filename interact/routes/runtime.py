"""Bot runtime orchestration endpoints."""
from __future__ import annotations

from flask import jsonify, request

from core.runtime import registry
from data import get_bot, list_bots, list_commands
from interact.security import login_required
from interact.socket import push_status_for_user
from interact.utils import mask_token

from . import api_bp


@api_bp.post("/bots/<int:bot_id>/start")
@login_required
def api_bot_start(bot_id: int):
    from flask import g

    bot = get_bot(g.user["id"], bot_id)
    if not bot:
        return jsonify({"ok": False, "error": "无权限"}), 403
    specs = list_commands(bot_id)
    ok, msg = registry.start(bot_id, bot["token"], specs)
    push_status_for_user(g.user["id"])
    return jsonify({"ok": ok, "msg": msg})


@api_bp.post("/bots/<int:bot_id>/stop")
@login_required
def api_bot_stop(bot_id: int):
    from flask import g

    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    ok, msg = registry.stop(bot_id)
    push_status_for_user(g.user["id"])
    return jsonify({"ok": ok, "msg": msg})


@api_bp.post("/bots/<int:bot_id>/sync")
@login_required
def api_bot_sync(bot_id: int):
    from flask import g

    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "error": "无权限"}), 403
    ok, msg = registry.sync(bot_id)
    push_status_for_user(g.user["id"])
    return jsonify({"ok": ok, "msg": msg})


@api_bp.get("/bots/<int:bot_id>/status")
@login_required
def api_bot_status(bot_id: int):
    from flask import g

    bot = get_bot(g.user["id"], bot_id)
    status = dict(registry.status(bot_id))
    if bot:
        status.setdefault("bot_id", bot["id"])
        status.setdefault("name", bot["name"])
    return jsonify({"status": status})


@api_bp.get("/bots/<int:bot_id>/logs")
@login_required
def api_bot_logs(bot_id: int):
    from flask import g

    if not get_bot(g.user["id"], bot_id):
        return jsonify({"ok": False, "items": [], "error": "无权限"}), 403
    try:
        lines = int(request.args.get("lines", 100))
    except (TypeError, ValueError):
        lines = 100
    lines = max(10, min(lines, 500))
    items = [dict(evt) for evt in registry.logs(bot_id, lines) or []]
    return jsonify({"ok": True, "items": items})


@api_bp.get("/bots/status_all")
@login_required
def api_bot_status_all():
    from flask import g

    bots = list_bots(g.user["id"])
    running = registry.status_all()
    items = []
    for bot in bots:
        bot_id = bot["id"]
        snapshot = running.get(bot_id)
        if snapshot is None:
            snapshot = registry.status(bot_id)
        snapshot = dict(snapshot)
        snapshot.setdefault("bot_id", bot_id)
        snapshot.setdefault("state", "stopped")
        snapshot.setdefault("uptime", 0)
        snapshot.setdefault("stats", {"messages": 0, "errors": 0})
        snapshot["name"] = bot["name"]
        snapshot["token_mask"] = mask_token(bot.get("token")) if bot.get("token") else ""
        items.append(snapshot)
    return jsonify({"items": items})
