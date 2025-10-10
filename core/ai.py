"""DeepSeek AI integration with graceful fallback to local templates."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Tuple

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore

from .pseudo import (
    ai_generate_pseudocode as _fallback_pseudo,
    ai_generate_command_skeleton as _fallback_command,
)

_client_cache: Tuple[str, str, Any] | None = None


def _get_client():
    if OpenAI is None:
        return None, "未安装 openai SDK (pip install openai)"
    key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("AI_API_KEY")
    if not key:
        return None, "缺少 DEEPSEEK_API_KEY 或 AI_API_KEY"
    base_url = os.environ.get("DEEPSEEK_BASE_URL") or os.environ.get("AI_BASE_URL") or "https://api.deepseek.com"
    global _client_cache
    if _client_cache and _client_cache[0] == key and _client_cache[1] == base_url:
        return _client_cache[2], None
    client = OpenAI(api_key=key, base_url=base_url)
    _client_cache = (key, base_url, client)
    return client, None


def _chat(client, messages, max_tokens=800, temperature=0.4):
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    return client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )


def generate_pseudocode(prompt: str) -> Tuple[Dict[str, str], Dict[str, Any]]:
    fallback_meta = {"source": "fallback", "api_key_configured": False}
    client, err = _get_client()
    if not client:
        result = _fallback_pseudo(prompt)
        fallback_meta["error"] = err
        return result, fallback_meta

    meta = {"source": "deepseek", "api_key_configured": True}
    system_msg = (
        "你是一名自动化流程设计师，返回 JSON 对象 {title, command, steps}。"\
        "steps 是字符串数组，每个元素是详细的中文伪代码步骤。命令以 / 开头。"
    )
    user_prompt = prompt.strip() or "欢迎流程"
    try:
        resp = _chat(client, [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_prompt},
        ], max_tokens=900, temperature=0.5)
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)
        title = data.get("title") or f"{user_prompt} 自动化流程"
        command = data.get("command") or "/auto"
        steps = data.get("steps") or []
        if isinstance(steps, str):
            steps = steps.splitlines()
        steps = [str(s).strip() for s in steps if str(s).strip()]
        pseudo_text = "\n".join(f"{i+1}. {step}" for i, step in enumerate(steps)) or "1. 机器人发送欢迎消息"
        return {"title": title, "content": pseudo_text, "command": command}, meta
    except Exception as exc:  # pragma: no cover
        meta = {"source": "fallback", "api_key_configured": True, "error": str(exc)}
        result = _fallback_pseudo(prompt)
        return result, meta


def generate_command(prompt: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    fallback_meta = {"source": "fallback", "api_key_configured": False}
    client, err = _get_client()
    if not client:
        result = _fallback_command(prompt)
        fallback_meta["error"] = err
        return result, fallback_meta

    meta = {"source": "deepseek", "api_key_configured": True}
    system_msg = (
        "你是一名聊天机器人的指令编写助手，返回 JSON {command, reply, parse_mode, disable_preview}."
        "command 必须以 / 开头，reply 是文本回复，可包含 {{args}} 变量。"
    )
    user_prompt = prompt.strip() or "欢迎访客"
    try:
        resp = _chat(client, [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_prompt},
        ], max_tokens=400, temperature=0.4)
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)
        command = data.get("command") or "/auto"
        reply = data.get("reply") or f"{user_prompt}: 感谢关注！"
        parse_mode = data.get("parse_mode") or ""
        disable_preview = bool(data.get("disable_preview", False))
        return {
            "command": command,
            "kind": "text",
            "reply": reply,
            "parse_mode": parse_mode,
            "disable_preview": disable_preview,
        }, meta
    except Exception as exc:  # pragma: no cover
        meta = {"source": "fallback", "api_key_configured": True, "error": str(exc)}
        result = _fallback_command(prompt)
        return result, meta


__all__ = ["generate_pseudocode", "generate_command"]