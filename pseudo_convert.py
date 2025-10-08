"""Utility helpers for turning Chinese-style pseudocode into flow definitions
and providing simple AI-like scaffolding/sandbox previews without external APIs."""
from __future__ import annotations

import json
import random
import re
from typing import Any, Dict, List, Tuple


def _clean_line(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^[-\d\.)\s]+", "", line)  # remove numeric/bullet prefixes
    return line.strip()


def _extract_command(tokens: List[str]) -> str | None:
    for tok in tokens:
        m = re.search(r"/(?:[a-zA-Z0-9_]+)", tok)
        if m:
            return m.group(0)
    return None


def _extract_between(text: str, left: str, right: str) -> str | None:
    try:
        start = text.index(left) + len(left)
        end = text.index(right, start)
        return text[start:end].strip()
    except ValueError:
        return None


def _split_options(text: str) -> List[str]:
    if not text:
        return []
    opts = []
    # First try bracketed groups 「选项」
    opts.extend(re.findall(r"「([^」]+)」", text))
    if opts:
        return [o.strip() for o in opts if o.strip()]
    # Fallback split by punctuation
    for sep in ("/", "、", "，", " "):
        if sep in text:
            pieces = [p.strip() for p in text.split(sep) if p.strip()]
            if len(pieces) > 1:
                return pieces
    return [text.strip()]


def generate_flow_from_pseudocode(title: str, content: str) -> Dict[str, Any]:
    lines = [ln for ln in (content or "").splitlines() if ln.strip()]
    nodes: List[Dict[str, Any]] = []
    command = None
    summary: List[str] = []

    for raw in lines:
        line = _clean_line(raw)
        if not line:
            continue
        lower = line.lower()
        pieces = line.split()
        if command is None and ("用户" in line or "命令" in line):
            cmd = _extract_command(pieces)
            if cmd:
                command = cmd
                summary.append(f"✅ 识别命令 {cmd}")
                continue
        if "机器人" in line and ("发送" in line or "回复" in line):
            text = _extract_between(line, "「", "」")
            if not text:
                text = re.split(r"[:,：]", line, 1)[-1].strip()
            nodes.append({
                "type": "send_text",
                "text": text or line,
                "parse_mode": "",
                "disable_preview": False,
            })
            summary.append("📝 添加发送文本动作")
            continue
        if "按钮" in line or "选项" in line or "菜单" in line:
            options = _split_options(_extract_between(line, "[", "]") or _extract_between(line, "「", "」") or line)
            if not options:
                options = ["功能介绍", "联系客服", "常见问题"]
            keyboard = [[{"text": opt, "callback_data": opt[:32]}] for opt in options]
            text = _extract_between(line, "：", "") or "请选择服务"
            nodes.append({
                "type": "send_text_keyboard",
                "text": text or "请选择服务",
                "keyboard": keyboard,
                "parse_mode": "",
                "disable_preview": False,
            })
            summary.append("🔘 添加按钮菜单")
            continue
        if "等待" in line:
            expect = "number" if ("数字" in line or "评分" in line) else "any"
            prompt = _extract_between(line, "「", "」") or re.split(r"[:,：]", line, 1)[-1].strip()
            nodes.append({
                "type": "wait_next",
                "expect": expect,
                "prompt": prompt or "请回复消息",
                "next": [],
            })
            summary.append("⏳ 添加等待下一条消息")
            continue
        if "延迟" in line or "等待" in line and "秒" in line:
            match = re.search(r"(\d+(?:\.\d+)?)", line)
            seconds = float(match.group(1)) if match else 1.5
            nodes.append({"type": "delay", "seconds": seconds})
            summary.append(f"⏱️ 延迟 {seconds} 秒")
            continue
        if "贴纸" in line:
            nodes.append({"type": "send_sticker", "file_id": "CAACAgUAAxkBAAIDlmDemoSticker"})
            summary.append("🎟️ 发送贴纸")
            continue
        if "语音" in line:
            nodes.append({"type": "send_voice", "url": "https://example.com/demo.ogg", "caption": "", "parse_mode": ""})
            summary.append("🎤 发送语音")
            continue
        if "http" in lower or "请求" in line:
            url = _extract_between(line, "http", "") or "https://api.example.com"  # crude fallback
            nodes.append({
                "type": "http",
                "method": "GET",
                "url": url.strip() or "https://api.example.com",
                "headers": "{}",
                "body": "",
                "save_to": {"scope": "chat", "key": "resp"},
            })
            summary.append("🌐 添加 HTTP 请求")
            continue

    if not nodes:
        nodes.append({"type": "send_text", "text": "你好，我是机器人～", "parse_mode": "", "disable_preview": False})
        summary.append("⚠️ 未识别伪代码，生成默认欢迎文本")

    command = command or "/auto"  # fallback
    compiled = {
        "version": 1,
        "entries": [
            {
                "id": "auto1",
                "type": "on_command",
                "command": command,
                "nodes": nodes,
            }
        ],
    }
    flow_name = title.strip() or f"伪代码流程 {command}"
    explanation = "\n".join(summary)
    return {"name": flow_name, "compiled": compiled, "summary": explanation, "command": command}


def simulate_flow(compiled: Dict[str, Any], user_text: str = "/demo") -> Dict[str, Any]:
    entries = (compiled or {}).get("entries") or []
    if not entries:
        return {"actions": [], "summary": "未找到入口，无法模拟。"}
    nodes = entries[0].get("nodes") or []
    actions: List[Dict[str, Any]] = []
    for node in nodes:
        t = (node or {}).get("type")
        if t == "send_text":
            actions.append({"type": "send_text", "text": node.get("text", "")})
        elif t == "send_text_keyboard":
            actions.append({
                "type": "send_text_keyboard",
                "text": node.get("text", ""),
                "buttons": node.get("keyboard", []),
            })
        elif t == "send_voice":
            actions.append({"type": "send_voice", "url": node.get("url"), "caption": node.get("caption", "")})
        elif t == "send_sticker":
            actions.append({"type": "send_sticker", "file_id": node.get("file_id")})
        elif t == "wait_next":
            actions.append({"type": "wait_next", "expect": node.get("expect", "any"), "prompt": node.get("prompt", "")})
        elif t == "delay":
            actions.append({"type": "delay", "seconds": node.get("seconds", 1)})
        elif t == "http":
            actions.append({"type": "http", "method": node.get("method"), "url": node.get("url")})
        else:
            actions.append({"type": t or "unknown", "detail": node})
    summary = f"共模拟 {len(actions)} 步动作。"
    return {"actions": actions, "summary": summary}


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower()) or "flow"


def ai_generate_pseudocode(prompt: str) -> Dict[str, str]:
    base = prompt.strip() or "智能助手"
    slug = _slugify(base)[:10]
    command = f"/{slug or 'auto'}"
    title = f"{base} 自动化流程"
    buttons = ["功能介绍", "价格方案", "转人工"]
    pseudo = [
        f"1. 当用户发送 {command}",
        f"2. 机器人发送文本「你好，感谢关注{base}」",
        "3. 机器人发送文本并附带按钮，按钮包括「功能介绍」「价格方案」「转人工」",
        "4. 等待下一条消息（数字），提示「请回复 1-3 选择服务」",
        "5. 如果用户输入 1，机器人发送文本「这里是功能介绍」",
        "6. 如果用户输入 2，机器人发送文本「我们的销售团队会联系你」",
        "7. 如果用户输入 3，机器人发送文本「正在为你转接人工」",
    ]
    return {"title": title, "content": "\n".join(pseudo), "command": command, "buttons": buttons}


def ai_generate_command_skeleton(prompt: str) -> Dict[str, Any]:
    base = prompt.strip() or "示例指令"
    slug = _slugify(base)[:12]
    cmd = f"/{slug or 'cmd'}"
    text = f"{base}：这是自动生成的回复，包含关键词 {{args}}"
    return {
        "command": cmd,
        "kind": "text",
        "reply": text,
        "parse_mode": "",
        "disable_preview": False,
    }


__all__ = [
    "generate_flow_from_pseudocode",
    "simulate_flow",
    "ai_generate_pseudocode",
    "ai_generate_command_skeleton",
]
