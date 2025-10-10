"""Authentication helpers for the Flask interface."""
from __future__ import annotations

from functools import wraps
from typing import Callable, TypeVar

from flask import g, jsonify

F = TypeVar("F", bound=Callable[..., object])


def login_required(func: F) -> F:
    @wraps(func)
    def wrapper(*args, **kwargs):  # type: ignore[misc]
        if not getattr(g, "user", None):
            return jsonify({"ok": False, "error": "未登录"}), 401
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


__all__ = ["login_required"]
