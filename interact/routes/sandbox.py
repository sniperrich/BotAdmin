"""Sandbox execution endpoint."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from core.sandbox import execute_in_sandbox
from core.pseudo import generate_flow_from_pseudocode, simulate_flow
from interact.security import login_required

sandbox_bp = Blueprint("sandbox", __name__, url_prefix="/api/sandbox")


@sandbox_bp.post("/execute")
@login_required
def execute():
    data = request.get_json(silent=True) or {}
    code = data.get("code", "").strip()
    timeout = data.get("timeout", 5)
    input_text = data.get("input", "")

    if not code:
        return jsonify({"ok": False, "error": "No code to execute."}), 400

    result = execute_in_sandbox(code, timeout=timeout, input_text=input_text)

    return jsonify({
        "ok": result["error"] is None,
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "error": result["error"],
    })

@sandbox_bp.post("/pseudo/execute")
@login_required
def execute_pseudo():
    data = request.get_json(silent=True) or {}
    content = data.get("content", "").strip()
    user_input = data.get("input", "")

    if not content:
        return jsonify({"ok": False, "error": "No content to execute."}), 400

    try:
        result = generate_flow_from_pseudocode("sandbox", content)
        sim = simulate_flow(result["compiled"], user_input)
        return jsonify(
            {
                "ok": True,
                "actions": sim["actions"],
                "summary": sim["summary"],
                "analysis": result["summary"],
                "command": result["command"],
            }
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
