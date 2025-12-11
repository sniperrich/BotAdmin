"""User settings and profile endpoints."""
from __future__ import annotations

from flask import jsonify, request

from data.database import (
    get_user_by_id,
    get_user_settings,
    hash_password,
    upsert_user_settings,
    update_user_password,
)
from interact.security import login_required

from . import api_bp

_HOT_RELOAD_LABELS = {"auto", "confirm", "manual"}
_THEME_LABELS = {"light", "dark"}


@api_bp.get("/settings")
@login_required
async def api_get_settings():
    from flask import g

    prefs = await get_user_settings(g.user["id"])
    return jsonify({"preferences": prefs})


@api_bp.post("/settings/preferences")
@login_required
async def api_update_preferences():
    from flask import g

    data = request.get_json(silent=True) or {}
    mode = data.get("hot_reload_mode")
    theme = data.get("theme")
    language = data.get("language")
    try:
        prefs = await upsert_user_settings(
            g.user["id"],
            hot_reload_mode=mode,
            theme=theme,
            language=language,
        )
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "preferences": prefs})


@api_bp.post("/settings/password")
@login_required
async def api_change_password():
    from flask import g

    data = request.get_json(silent=True) or {}
    current_password = (data.get("current_password") or "").strip()
    new_password = (data.get("new_password") or "").strip()
    if not current_password or not new_password:
        return jsonify({"ok": False, "error": "请填写当前密码和新密码"}), 400
    user = await get_user_by_id(g.user["id"])
    if not user or user["password_hash"] != hash_password(current_password):
        return jsonify({"ok": False, "error": "当前密码不正确"}), 400
    ok, err = await update_user_password(g.user["id"], new_password)
    if not ok:
        return jsonify({"ok": False, "error": err}), 400
    return jsonify({"ok": True})
