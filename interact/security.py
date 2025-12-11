import inspect
from functools import wraps
from typing import Callable, TypeVar

from flask import g, jsonify

F = TypeVar("F", bound=Callable[..., object])


def login_required(func: F) -> F:
    if inspect.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not getattr(g, "user", None):
                return jsonify({"ok": False, "error": "未登录"}), 401
            return await func(*args, **kwargs)
        return async_wrapper  # type: ignore[return-value]

    @wraps(func)
    def wrapper(*args, **kwargs):  # type: ignore[misc]
        if not getattr(g, "user", None):
            return jsonify({"ok": False, "error": "未登录"}), 401
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


__all__ = ["login_required"]
