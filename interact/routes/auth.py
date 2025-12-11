"""Authentication related routes."""
from __future__ import annotations

from flask import jsonify, request, session

from data.database import create_user, get_user_by_id, get_user_by_username, get_user_settings, hash_password

from . import api_bp


@api_bp.get("/me")
async def api_me():
    from flask import g

    user = getattr(g, "user", None)
    if user:
        settings = await get_user_settings(user["id"])
        return jsonify(
            {
                "user": {
                    "id": user["id"],
                    "username": user["username"],
                },
                "preferences": settings,
            }
        )
    return jsonify({"user": None})


@api_bp.post("/register")
async def api_register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    ok, err = await create_user(username, password)
    return jsonify({"ok": ok, "error": err})


@api_bp.post("/login")
async def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    user = await get_user_by_username(username)
    if not user:
        return jsonify({"ok": False, "error": "用户不存在"})
    if user["password_hash"] != hash_password(password):
        return jsonify({"ok": False, "error": "密码错误"})
    session["user_id"] = user["id"]
    return jsonify({"ok": True})


@api_bp.post("/logout")
def api_logout():
    session.clear()
    return jsonify({"ok": True})
