#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pack a project's .py and .html files into a single TXT prompt.
- Shows a tree (only included file types)
- Appends each file's content with clear delimiters
- Uses input() for a simple, zero-deps UX
"""

from __future__ import annotations
import os
import sys
import time
from typing import Dict, List, Tuple

SEP = os.sep

def ask(prompt: str, default: str | None = None) -> str:
    if default is None:
        return input(prompt).strip()
    val = input(f"{prompt} [默认: {default}] ").strip()
    return val or default

def human_bytes(n: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024.0:
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}{unit}"
        n /= 1024.0
    return f"{n:.1f}TB"

def build_tree(paths: List[str]) -> Dict:
    """
    Build a nested dict tree from a list of relative file paths.
    Directories are dicts; files are stored as None values.
    """
    root: Dict = {}
    for rel in paths:
        parts = rel.split(SEP)
        cur = root
        for i, p in enumerate(parts):
            if i == len(parts) - 1:
                cur.setdefault("__files__", set()).add(p)
            else:
                cur = cur.setdefault(p, {})
    return root

def render_tree(tree: Dict, prefix: str = "") -> str:
    """
    Render the nested dict into an ASCII tree (only included files).
    """
    lines: List[str] = []
    # separate directories and files
    dirs = sorted([k for k in tree.keys() if k != "__files__"])
    files = sorted(list(tree.get("__files__", [])))

    def draw(items, pref: str):
        for idx, (name, is_dir) in enumerate(items):
            is_last = idx == len(items) - 1
            branch = "└── " if is_last else "├── "
            lines.append(pref + branch + name)
            if is_dir:
                child = tree[name]
                continuation = pref + ("    " if is_last else "│   ")
                sub = render_tree(child, continuation)
                if sub:
                    lines.append(sub)

    mixed = [(d, True) for d in dirs] + [(f, False) for f in files]
    draw(mixed, prefix)
    return "\n".join([s for s in lines if s != ""])

def collect_files(root_dir: str, ex_dirs: List[str], max_bytes: int) -> List[str]:
    chosen: List[str] = []
    ex_set = set(d.strip() for d in ex_dirs if d.strip())
    for cur, dirs, files in os.walk(root_dir):
        # prune excluded directories by name match at each depth
        dirs[:] = [d for d in dirs if d not in ex_set]
        for fn in files:
            low = fn.lower()
            if not (low.endswith(".py") or low.endswith(".html")):
                continue
            path = os.path.join(cur, fn)
            try:
                if os.path.getsize(path) > max_bytes:
                    continue
            except OSError:
                continue
            rel = os.path.relpath(path, root_dir)
            chosen.append(rel)
    chosen.sort()
    return chosen

def read_text(path: str) -> Tuple[str, int]:
    """
    Read text as UTF-8 with replacement to avoid crashes on odd encodings.
    Returns (content, line_count)
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            txt = f.read()
    except Exception as e:
        txt = f"<<读取失败: {e}>>"
    return txt, txt.count("\n") + (1 if txt and not txt.endswith("\n") else 0)

def main():
    print("🧰 项目打包为 TXT Prompt（仅 .py / .html）")
    root_dir = ask("请输入项目根目录路径", os.getcwd())
    out_path = ask("输出文件名（含路径）", "project_prompt.txt")
    ex_default = ".git,.idea,.vscode,__pycache__,dist,build,node_modules,venv,.venv"
    ex_dirs = [s.strip() for s in ask("要排除的目录名（逗号分隔）", ex_default).split(",")]
    max_kb = ask("单文件大小上限（KB）", "512")
    try:
        max_bytes = int(float(max_kb) * 1024)
    except ValueError:
        print("⚠️ 大小上限无效，使用 512KB")
        max_bytes = 512 * 1024

    if not os.path.isdir(root_dir):
        print("❌ 根目录不存在。")
        sys.exit(1)

    print("🔎 扫描中……")
    files = collect_files(root_dir, ex_dirs, max_bytes)
    if not files:
        print("😶 没找到需要打包的文件（只包含 .py / .html 且不超过大小上限）。")
        sys.exit(0)

    # Build structure tree
    tree = build_tree(files)
    tree_txt = render_tree(tree)

    total_bytes = 0
    total_lines = 0

    tstamp = time.strftime("%Y-%m-%d %H:%M:%S")
    header_lines = [
        f"# Project Prompt Export",
        f"# Time: {tstamp}",
        f"# Root: {os.path.abspath(root_dir)}",
        f"# Include: *.py, *.html",
        f"# Excluded dirs: {', '.join(ex_dirs)}",
        f"# Per-file size cap: {human_bytes(max_bytes)}",
        "",
        "## Project Structure (仅包含被打包的文件)",
        "```",
        tree_txt,
        "```",
        "",
        "## Files",
        ""
    ]

    with open(out_path, "w", encoding="utf-8", errors="replace") as out:
        out.write("\n".join(header_lines))
        for rel in files:
            abs_path = os.path.join(root_dir, rel)
            try:
                size = os.path.getsize(abs_path)
            except OSError:
                size = -1
            content, n_lines = read_text(abs_path)
            total_bytes += max(0, size)
            total_lines += n_lines

            out.write(f"\n\n----- BEGIN FILE: {rel} -----\n")
            out.write(f"# Size: {human_bytes(size if size >=0 else 0)} | Lines: {n_lines}\n")
            fence = "```html" if rel.lower().endswith(".html") else "```python"
            out.write(f"{fence}\n{content}\n```\n")
            out.write(f"----- END FILE: {rel} -----\n")

        out.write("\n\n## Summary\n")
        out.write(f"Total files: {len(files)}\n")
        out.write(f"Total size: {human_bytes(total_bytes)}\n")
        out.write(f"Total lines: {total_lines}\n")

    print(f"✅ 完成：{out_path}")
    print(f"📦 共 {len(files)} 个文件，{human_bytes(total_bytes)}，约 {total_lines} 行。")

if __name__ == "__main__":
    main()
