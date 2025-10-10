"""API blueprint and route registrations."""
from __future__ import annotations

from flask import Blueprint

api_bp = Blueprint("api", __name__, url_prefix="/api")

# Import modules to register routes on the blueprint
from . import auth  # noqa: E402,F401
from . import bots  # noqa: E402,F401
from . import commands  # noqa: E402,F401
from . import flows  # noqa: E402,F401
from . import pseudocode  # noqa: E402,F401
from . import pro_scripts  # noqa: E402,F401
from . import ai  # noqa: E402,F401
from . import runtime  # noqa: E402,F401

__all__ = ["api_bp"]
