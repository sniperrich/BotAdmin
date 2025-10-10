"""SQLite access helpers for the BotAdmin project."""
from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from typing import Dict, List, Optional, Tuple

from config import get_settings

SETTINGS = get_settings()


def _row_factory(cursor, row):
    mapped = {}
    for idx, col in enumerate(cursor.description):
        mapped[col[0]] = row[idx]
    return mapped


@contextmanager
def get_conn():
    settings = SETTINGS
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(settings.db_path_str)
    con.row_factory = _row_factory
    con.execute("PRAGMA foreign_keys = ON;")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> bool:
    with get_conn() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS bots(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                token TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS commands(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                command TEXT NOT NULL,
                kind TEXT DEFAULT 'text',
                reply TEXT,
                payload TEXT,
                parse_mode TEXT,
                disable_preview INTEGER DEFAULT 0,
                UNIQUE(bot_id, command),
                FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS flows(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                blocks_json TEXT NOT NULL,
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS pro_scripts(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                command TEXT NOT NULL,
                code TEXT NOT NULL,
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(bot_id, command),
                FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS kv_store(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                scope TEXT NOT NULL,
                chat_id TEXT DEFAULT '',
                user_id TEXT DEFAULT '',
                key TEXT NOT NULL,
                value TEXT,
                UNIQUE(bot_id, scope, chat_id, user_id, key),
                FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS pseudocode(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE
            );
            """
        )
    return True


def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def create_user(username: str, password: str) -> Tuple[bool, Optional[str]]:
    username = (username or "").strip()
    password = (password or "").strip()
    if not username or not password:
        return False, "用户名/密码不能为空"
    with get_conn() as con:
        try:
            con.execute(
                "INSERT INTO users(username, password_hash) VALUES (?,?)",
                (username, hash_password(password)),
            )
            return True, None
        except sqlite3.IntegrityError:
            return False, "用户名已存在"


def get_user_by_username(username: str) -> Optional[Dict]:
    with get_conn() as con:
        cur = con.execute("SELECT * FROM users WHERE username=?", (username,))
        return cur.fetchone()


def get_user_by_id(uid: int) -> Optional[Dict]:
    with get_conn() as con:
        cur = con.execute("SELECT * FROM users WHERE id=?", (uid,))
        return cur.fetchone()


def create_bot(user_id: int, name: str, token: str) -> Tuple[bool, Optional[str]]:
    if not name or not token:
        return False, "name/token 必填"
    with get_conn() as con:
        con.execute(
            "INSERT INTO bots(user_id,name,token) VALUES (?,?,?)",
            (user_id, name, token),
        )
    return True, None


def list_bots(user_id: int) -> List[Dict]:
    with get_conn() as con:
        cur = con.execute(
            "SELECT id,name,token,created_at FROM bots WHERE user_id=? ORDER BY id DESC",
            (user_id,),
        )
        return cur.fetchall() or []


def get_bot(user_id: int, bot_id: int) -> Optional[Dict]:
    with get_conn() as con:
        cur = con.execute(
            "SELECT * FROM bots WHERE id=? AND user_id=?",
            (bot_id, user_id),
        )
        return cur.fetchone()


def get_bot_by_id(bot_id: int) -> Optional[Dict]:
    with get_conn() as con:
        cur = con.execute("SELECT * FROM bots WHERE id=?", (bot_id,))
        return cur.fetchone()


def delete_bot(user_id: int, bot_id: int) -> Tuple[bool, Optional[str]]:
    with get_conn() as con:
        cur = con.execute("DELETE FROM bots WHERE id=? AND user_id=?", (bot_id, user_id))
        if cur.rowcount == 0:
            return False, "无此 bot 或无权限"
    return True, None


def list_commands(bot_id: int) -> List[Dict]:
    with get_conn() as con:
        cur = con.execute(
            "SELECT id,command,kind,reply,payload,parse_mode,disable_preview "
            "FROM commands WHERE bot_id=? ORDER BY command",
            (bot_id,),
        )
        return cur.fetchall() or []


def upsert_command(
    bot_id: int,
    command: str,
    kind: str,
    reply: Optional[str],
    payload: Optional[str],
    parse_mode: Optional[str],
    disable_preview: int,
) -> Tuple[bool, Optional[str]]:
    if not command:
        return False, "command 不能为空"
    if not command.startswith("/"):
        command = "/" + command
    with get_conn() as con:
        con.execute(
            """
            INSERT INTO commands(bot_id,command,kind,reply,payload,parse_mode,disable_preview)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(bot_id,command) DO UPDATE SET
              kind=excluded.kind,
              reply=excluded.reply,
              payload=excluded.payload,
              parse_mode=excluded.parse_mode,
              disable_preview=excluded.disable_preview
            """,
            (bot_id, command, kind or "text", reply, payload, parse_mode, int(bool(disable_preview))),
        )
    return True, None


def delete_command(bot_id: int, command: str) -> Tuple[bool, Optional[str]]:
    if not command:
        return False, "command 不能为空"
    if not command.startswith("/"):
        command = "/" + command
    with get_conn() as con:
        cur = con.execute(
            "DELETE FROM commands WHERE bot_id=? AND command=?",
            (bot_id, command),
        )
        if cur.rowcount == 0:
            return False, "未找到该命令"
    return True, None


def erase_commands(bot_id: int) -> Tuple[bool, Optional[str]]:
    with get_conn() as con:
        con.execute("DELETE FROM commands WHERE bot_id=?", (bot_id,))
    return True, None


def list_flows(bot_id: int) -> List[Dict]:
    with get_conn() as con:
        cur = con.execute(
            "SELECT id,name,blocks_json,active,created_at,updated_at "
            "FROM flows WHERE bot_id=? ORDER BY id DESC",
            (bot_id,),
        )
        return cur.fetchall() or []


def upsert_flow(
    bot_id: int,
    name: str,
    blocks_json: str,
    flow_id: Optional[int] = None,
    active: int = 1,
) -> Tuple[bool, Optional[str], Optional[int]]:
    if not name or not blocks_json:
        return False, "name/blocks_json 不能为空", None
    with get_conn() as con:
        if flow_id:
            con.execute(
                "UPDATE flows SET name=?, blocks_json=?, active=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND bot_id=?",
                (name, blocks_json, int(bool(active)), flow_id, bot_id),
            )
            return True, None, flow_id
        cur = con.execute(
            "INSERT INTO flows(bot_id,name,blocks_json,active) VALUES(?,?,?,?)",
            (bot_id, name, blocks_json, int(bool(active))),
        )
        return True, None, cur.lastrowid


def delete_flow(bot_id: int, flow_id: int) -> Tuple[bool, Optional[str]]:
    with get_conn() as con:
        cur = con.execute("DELETE FROM flows WHERE id=? AND bot_id=?", (flow_id, bot_id))
        if cur.rowcount == 0:
            return False, "未找到该流程"
    return True, None


def list_pro_scripts(bot_id: int) -> List[Dict]:
    with get_conn() as con:
        cur = con.execute(
            "SELECT id, name, command, code, active, created_at, updated_at "
            "FROM pro_scripts WHERE bot_id=? ORDER BY command",
            (bot_id,),
        )
        return cur.fetchall() or []


def upsert_pro_script(
    bot_id: int,
    name: str,
    command: str,
    code: str,
    script_id: Optional[int] = None,
    active: int = 1,
) -> Tuple[bool, Optional[str], Optional[int]]:
    name = (name or "").strip()
    command = (command or "").strip()
    code = (code or "").strip()
    if not all([name, command, code]):
        return False, "名称、命令和代码都不能为空", None
    if not command.startswith("/"):
        command = "/" + command

    with get_conn() as con:
        try:
            if script_id:
                cur = con.execute(
                    "UPDATE pro_scripts SET name=?, command=?, code=?, active=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND bot_id=?",
                    (name, command, code, int(bool(active)), script_id, bot_id),
                )
                if cur.rowcount == 0:
                    return False, "未找到该脚本或无权限", script_id
                return True, None, script_id
            cur = con.execute(
                "INSERT INTO pro_scripts(bot_id, name, command, code, active) VALUES(?,?,?,?,?)",
                (bot_id, name, command, code, int(bool(active))),
            )
            return True, None, cur.lastrowid
        except sqlite3.IntegrityError:
            return False, f"命令 '{command}' 已存在，请使用其他命令", None


def delete_pro_script(bot_id: int, script_id: int) -> Tuple[bool, Optional[str]]:
    with get_conn() as con:
        cur = con.execute("DELETE FROM pro_scripts WHERE id=? AND bot_id=?", (script_id, bot_id))
        if cur.rowcount == 0:
            return False, "未找到该脚本"
    return True, None


def list_pseudocode(bot_id: int) -> List[Dict]:
    with get_conn() as con:
        cur = con.execute(
            "SELECT id, title, content, created_at, updated_at FROM pseudocode "
            "WHERE bot_id=? ORDER BY id DESC",
            (bot_id,),
        )
        return cur.fetchall() or []


def upsert_pseudocode(
    bot_id: int,
    title: str,
    content: str,
    pseudo_id: Optional[int] = None,
) -> Tuple[bool, Optional[str], Optional[int]]:
    title = (title or "").strip()
    content = (content or "").strip()
    if not title or not content:
        return False, "标题/内容不能为空", None
    with get_conn() as con:
        if pseudo_id:
            cur = con.execute(
                "UPDATE pseudocode SET title=?, content=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND bot_id=?",
                (title, content, pseudo_id, bot_id),
            )
            if cur.rowcount == 0:
                return False, "未找到该伪代码", None
            return True, None, pseudo_id
        cur = con.execute(
            "INSERT INTO pseudocode(bot_id, title, content) VALUES (?,?,?)",
            (bot_id, title, content),
        )
        return True, None, cur.lastrowid


def delete_pseudocode(bot_id: int, pseudo_id: int) -> Tuple[bool, Optional[str]]:
    with get_conn() as con:
        cur = con.execute(
            "DELETE FROM pseudocode WHERE id=? AND bot_id=?",
            (pseudo_id, bot_id),
        )
        if cur.rowcount == 0:
            return False, "未找到该伪代码"
    return True, None


def get_pseudocode(bot_id: int, pseudo_id: int) -> Optional[Dict]:
    with get_conn() as con:
        cur = con.execute(
            "SELECT id, title, content, created_at, updated_at FROM pseudocode WHERE id=? AND bot_id=?",
            (pseudo_id, bot_id),
        )
        return cur.fetchone()


def _nz(value: Optional[str]) -> str:
    return "" if value is None else str(value)


def kv_get(bot_id: int, scope: str, chat_id: Optional[str], user_id: Optional[str], key: str) -> Optional[str]:
    with get_conn() as con:
        cur = con.execute(
            "SELECT value FROM kv_store WHERE bot_id=? AND scope=? AND chat_id=? AND user_id=? AND key=?",
            (bot_id, scope, _nz(chat_id), _nz(user_id), key),
        )
        row = cur.fetchone()
        return None if not row else row["value"]


def kv_set(bot_id: int, scope: str, chat_id: Optional[str], user_id: Optional[str], key: str, value) -> None:
    with get_conn() as con:
        if value is None:
            con.execute(
                "DELETE FROM kv_store WHERE bot_id=? AND scope=? AND chat_id=? AND user_id=? AND key=?",
                (bot_id, scope, _nz(chat_id), _nz(user_id), key),
            )
            return
        con.execute(
            """
            INSERT INTO kv_store(bot_id,scope,chat_id,user_id,key,value)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(bot_id,scope,chat_id,user_id,key) DO UPDATE SET
              value=excluded.value
            """,
            (bot_id, scope, _nz(chat_id), _nz(user_id), key, str(value)),
        )


__all__ = [
    "get_conn",
    "init_db",
    "hash_password",
    "create_user",
    "get_user_by_username",
    "get_user_by_id",
    "create_bot",
    "list_bots",
    "get_bot",
    "get_bot_by_id",
    "delete_bot",
    "list_commands",
    "upsert_command",
    "delete_command",
    "erase_commands",
    "list_flows",
    "upsert_flow",
    "delete_flow",
    "list_pro_scripts",
    "upsert_pro_script",
    "delete_pro_script",
    "list_pseudocode",
    "upsert_pseudocode",
    "delete_pseudocode",
    "get_pseudocode",
    "kv_get",
    "kv_set",
]
