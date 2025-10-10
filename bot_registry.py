"""Legacy shim for bot runtime management."""
from core.runtime import *  # noqa: F401,F403
import core.runtime as _runtime

__all__ = list(_runtime.__all__)
