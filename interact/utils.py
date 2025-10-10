"""Shared utility helpers for Flask routes."""
from __future__ import annotations

import json
from typing import Any, Dict


def mask_token(token: str) -> str:
    if not token:
        return ""
    value = token.strip()
    if len(value) <= 12:
        return value[:2] + "****" + value[-2:]
    return value[:8] + "****" + value[-4:]


def normalize_flow_blocks(raw: Any) -> str | None:
    if raw is None:
        return None
    obj = raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid blocks_json: {exc}") from exc
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid blocks_json inner string: {exc}") from exc
    if not isinstance(obj, Dict):
        raise ValueError("blocks_json must be a JSON object")
    return json.dumps(obj, ensure_ascii=False)


__all__ = ["mask_token", "normalize_flow_blocks"]
