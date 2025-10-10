"""AI integration endpoints."""
from __future__ import annotations

import os

from flask import jsonify, request

from core.ai import generate_command as ai_generate_command
from core.ai import generate_pseudocode as ai_generate_pseudocode
from interact.security import login_required

from . import api_bp


@api_bp.post("/ai/generate")
@login_required
def api_ai_generate():
    data = request.get_json(silent=True) or {}
    mode = (data.get("mode") or "pseudocode").strip().lower()
    prompt = (data.get("prompt") or "").strip()
    if mode == "pseudocode":
        result, meta = ai_generate_pseudocode(prompt)
        return jsonify({"ok": True, "result": result, "meta": meta})
    if mode == "command":
        result, meta = ai_generate_command(prompt)
        return jsonify({"ok": True, "result": result, "meta": meta})
    configured = bool(os.environ.get("AI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"))
    return jsonify({"ok": False, "error": "暂不支持的生成模式", "meta": {"api_key_configured": configured}}), 400
