"""WebSocket (Socket.IO) helpers for real-time bot state updates."""
from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from typing import Dict, Iterable, Optional

from flask import request, session
from flask_socketio import SocketIO, emit

from core.runtime import registry
from data.database import list_bots
from interact.utils import mask_token

socketio = SocketIO(async_mode="threading", cors_allowed_origins="*")

_subscriptions: Dict[int, set[str]] = defaultdict(set)
_lock = Lock()
_background_started = False


def init_socketio(app) -> None:
    """Attach Socket.IO to the Flask app and spawn the status updater."""
    global _background_started
    socketio.init_app(app)
    if not _background_started:
        socketio.start_background_task(_status_loop)
        _background_started = True


def _status_loop():  # pragma: no cover - background thread
    while True:
        socketio.sleep(0.5)
        with _lock:
            user_ids = list(_subscriptions.keys())
        for user_id in user_ids:
            push_status_for_user(user_id)


def _build_payload(user_id: int) -> Dict[str, object]:
    bots = list_bots(user_id)
    global_status = registry.status_all()
    items = []
    for bot in bots:
        bot_id = bot["id"]
        snapshot = dict(global_status.get(bot_id) or registry.status(bot_id))
        snapshot["bot_id"] = bot_id
        snapshot["name"] = bot["name"]
        snapshot["token_mask"] = mask_token(bot.get("token")) if bot.get("token") else ""
        snapshot["created_at"] = bot.get("created_at")
        snapshot.setdefault("stats", {"messages": 0, "errors": 0})
        snapshot.setdefault("state", "stopped")
        snapshot.setdefault("uptime", 0)
        items.append(snapshot)
    return {"items": items, "ts": time.time()}


def push_status_for_user(user_id: int, *, room: Optional[str] = None) -> None:
    payload = _build_payload(user_id)
    targets: Iterable[str]
    if room:
        targets = [room]
    else:
        with _lock:
            targets = list(_subscriptions.get(user_id, set()))
    for sid in targets:
        socketio.emit("bot_status", payload, room=sid)


@socketio.on("connect")
def handle_connect():
    user_id = session.get("user_id")
    if not user_id:
        emit("auth_error", {"error": "未登录，无法订阅实时状态"})
        return
    emit("connected", {"ok": True})


@socketio.on("subscribe_status")
def handle_subscribe():  # noqa: D401 - event handler
    user_id = session.get("user_id")
    if not user_id:
        emit("auth_error", {"error": "未登录，无法订阅实时状态"})
        return
    sid = request.sid
    with _lock:
        _subscriptions[user_id].add(sid)
    emit("subscribed", {"ok": True})
    push_status_for_user(user_id, room=sid)


@socketio.on("unsubscribe_status")
def handle_unsubscribe():
    sid = request.sid
    with _lock:
        for user_id, sids in list(_subscriptions.items()):
            if sid in sids:
                sids.remove(sid)
                if not sids:
                    _subscriptions.pop(user_id, None)
                break
    emit("unsubscribed", {"ok": True})


@socketio.on("disconnect")
def handle_disconnect():
    handle_unsubscribe()


__all__ = ["socketio", "init_socketio", "push_status_for_user"]
