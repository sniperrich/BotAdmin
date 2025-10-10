"""Legacy shim for data access; use `data.database` instead."""
from data.database import *  # noqa: F401,F403
import data.database as _database

__all__ = list(_database.__all__)
