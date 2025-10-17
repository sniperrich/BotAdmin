"""Flask application factory."""
from __future__ import annotations

from flask import Flask, g, send_from_directory, session

from config import get_settings
from data import get_user_by_id, init_db

from .routes import api_bp
from .routes.sandbox import sandbox_bp
from .socket import init_socketio, socketio


def create_app() -> Flask:
    settings = get_settings()
    app = Flask(
        __name__,
        static_folder=settings.static_dir_str,
        static_url_path="/static",
    )
    app.secret_key = settings.secret_key
    app.config.update(
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_HTTPONLY=True,
    )

    init_db()

    @app.before_request
    def load_user():
        uid = session.get("user_id")
        g.user = get_user_by_id(uid) if uid else None

    @app.get("/")
    def index_html():
        return send_from_directory(settings.static_dir_str, "index.html")

    @app.get("/sandbox.html")
    def sandbox_html():
        return send_from_directory(settings.static_dir_str, "sandbox.html")

    app.register_blueprint(api_bp)
    app.register_blueprint(sandbox_bp)

    init_socketio(app)
    return app


__all__ = ["create_app", "socketio"]
