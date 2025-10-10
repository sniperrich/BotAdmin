"""Legacy shim for AI helpers."""
from core.ai import *  # noqa: F401,F403
import core.ai as _ai

__all__ = list(_ai.__all__)
