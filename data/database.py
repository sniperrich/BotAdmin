"""SQLite access helpers for the BotAdmin project."""
from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from typing import Dict, List, Optional, Tuple

from config import get_settings

SETTINGS = get_settings()

_FEATURE_GROUP_KINDS = {
    "command": "command",
    "commands": "command",
    "flow": "flow",
    "flows": "flow",
    "pro": "pro_script",
    "pro_scripts": "pro_script",
    "pro_script": "pro_script",
    "pseudocode": "pseudocode",
    "pseudo": "pseudocode",
}


_GROUP_KIND_TABLE = {
    "command": "commands",
    "flow": "flows",
    "pro_script": "pro_scripts",
    "pseudocode": "pseudocode",
}


def _normalize_group_kind(kind: str) -> str:
    key = (kind or "").strip().lower()
    if key not in _FEATURE_GROUP_KINDS:
        raise ValueError(f"不支持的分组类型: {kind}")
    return _FEATURE_GROUP_KINDS[key]


def _resolve_group_id(con, bot_id: int, kind: str, group_id) -> Optional[int]:
    if group_id is None:
        return None
    try:
        gid = int(group_id)
    except (TypeError, ValueError):
        return None
    norm_kind = _normalize_group_kind(kind)
    cur = con.execute(
        "SELECT id FROM feature_groups WHERE id=? AND bot_id=? AND kind=?",
        (gid, bot_id, norm_kind),
    )
    row = cur.fetchone()
    return gid if row else None


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

            CREATE TABLE IF NOT EXISTS feature_groups(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(bot_id, kind, name),
                FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE
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
                active INTEGER DEFAULT 1,
                group_id INTEGER,
                UNIQUE(bot_id, command),
                FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE,
                FOREIGN KEY(group_id) REFERENCES feature_groups(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS flows(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                blocks_json TEXT NOT NULL,
                active INTEGER DEFAULT 1,
                group_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE,
                FOREIGN KEY(group_id) REFERENCES feature_groups(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS pro_scripts(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                command TEXT NOT NULL,
                code TEXT NOT NULL,
                active INTEGER DEFAULT 1,
                group_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(bot_id, command),
                FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE,
                FOREIGN KEY(group_id) REFERENCES feature_groups(id) ON DELETE SET NULL
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
                active INTEGER DEFAULT 1,
                group_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE,
                FOREIGN KEY(group_id) REFERENCES feature_groups(id) ON DELETE SET NULL
            );
            """
        )
        for ddl in (
            "ALTER TABLE commands ADD COLUMN active INTEGER DEFAULT 1",
            "ALTER TABLE pseudocode ADD COLUMN active INTEGER DEFAULT 1",
        ):
            try:
                con.execute(ddl)
            except sqlite3.OperationalError as exc:  # pragma: no cover - schema already upgraded
                if "duplicate column" not in str(exc).lower():
                    raise
        for ddl in (
            "ALTER TABLE commands ADD COLUMN group_id INTEGER",
            "ALTER TABLE flows ADD COLUMN group_id INTEGER",
            "ALTER TABLE pro_scripts ADD COLUMN group_id INTEGER",
            "ALTER TABLE pseudocode ADD COLUMN group_id INTEGER",
        ):
            try:
                con.execute(ddl)
            except sqlite3.OperationalError as exc:  # pragma: no cover - schema already upgraded
                if "duplicate column" not in str(exc).lower():
                    raise
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
            "SELECT c.id, c.command, c.kind, c.reply, c.payload, c.parse_mode, c.disable_preview, c.active,"
            " c.group_id, fg.name AS group_name, fg.active AS group_active "
            "FROM commands AS c "
            "LEFT JOIN feature_groups AS fg ON fg.id = c.group_id "
            "WHERE c.bot_id=? ORDER BY c.command",
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
    active: int = 1,
    group_id: Optional[int] = None,
) -> Tuple[bool, Optional[str]]:
    if not command:
        return False, "command 不能为空"
    if not command.startswith("/"):
        command = "/" + command
    with get_conn() as con:
        resolved_group = _resolve_group_id(con, bot_id, "command", group_id)
        con.execute(
            """
            INSERT INTO commands(bot_id,command,kind,reply,payload,parse_mode,disable_preview,active,group_id)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(bot_id,command) DO UPDATE SET
              kind=excluded.kind,
              reply=excluded.reply,
              payload=excluded.payload,
              parse_mode=excluded.parse_mode,
              disable_preview=excluded.disable_preview,
              active=excluded.active,
              group_id=excluded.group_id
            """,
            (
                bot_id,
                command,
                kind or "text",
                reply,
                payload,
                parse_mode,
                int(bool(disable_preview)),
                int(bool(active)),
                resolved_group,
            ),
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


def set_command_active(bot_id: int, command_id: int, active: int) -> Tuple[bool, Optional[str]]:
    with get_conn() as con:
        cur = con.execute(
            "UPDATE commands SET active=? WHERE id=? AND bot_id=?",
            (int(bool(active)), command_id, bot_id),
        )
        if cur.rowcount == 0:
            return False, "未找到该命令"
    return True, None


def set_command_group(bot_id: int, command_id: int, group_id) -> Tuple[bool, Optional[str]]:
    with get_conn() as con:
        resolved = _resolve_group_id(con, bot_id, "command", group_id)
        cur = con.execute(
            "UPDATE commands SET group_id=? WHERE id=? AND bot_id=?",
            (resolved, command_id, bot_id),
        )
        if cur.rowcount == 0:
            return False, "未找到该命令"
    return True, None


def list_flows(bot_id: int) -> List[Dict]:
    with get_conn() as con:
        cur = con.execute(
            "SELECT f.id, f.name, f.blocks_json, f.active, f.group_id, f.created_at, f.updated_at,"
            " fg.name AS group_name, fg.active AS group_active "
            "FROM flows AS f "
            "LEFT JOIN feature_groups AS fg ON fg.id = f.group_id "
            "WHERE f.bot_id=? ORDER BY f.id DESC",
            (bot_id,),
        )
        return cur.fetchall() or []


def upsert_flow(
    bot_id: int,
    name: str,
    blocks_json: str,
    flow_id: Optional[int] = None,
    active: int = 1,
    group_id: Optional[int] = None,
) -> Tuple[bool, Optional[str], Optional[int]]:
    if not name or not blocks_json:
        return False, "name/blocks_json 不能为空", None
    with get_conn() as con:
        resolved_group = _resolve_group_id(con, bot_id, "flow", group_id)
        if flow_id:
            con.execute(
                "UPDATE flows SET name=?, blocks_json=?, active=?, group_id=?, updated_at=CURRENT_TIMESTAMP "
                "WHERE id=? AND bot_id=?",
                (name, blocks_json, int(bool(active)), resolved_group, flow_id, bot_id),
            )
            return True, None, flow_id
        cur = con.execute(
            "INSERT INTO flows(bot_id,name,blocks_json,active,group_id) VALUES(?,?,?,?,?)",
            (bot_id, name, blocks_json, int(bool(active)), resolved_group),
        )
        return True, None, cur.lastrowid


def delete_flow(bot_id: int, flow_id: int) -> Tuple[bool, Optional[str]]:
    with get_conn() as con:
        cur = con.execute("DELETE FROM flows WHERE id=? AND bot_id=?", (flow_id, bot_id))
        if cur.rowcount == 0:
            return False, "未找到该流程"
    return True, None


def set_flow_active(bot_id: int, flow_id: int, active: int) -> Tuple[bool, Optional[str]]:
    with get_conn() as con:
        cur = con.execute(
            "UPDATE flows SET active=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND bot_id=?",
            (int(bool(active)), flow_id, bot_id),
        )
        if cur.rowcount == 0:
            return False, "未找到该流程"
    return True, None


def set_flow_group(bot_id: int, flow_id: int, group_id) -> Tuple[bool, Optional[str]]:
    with get_conn() as con:
        resolved = _resolve_group_id(con, bot_id, "flow", group_id)
        cur = con.execute(
            "UPDATE flows SET group_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND bot_id=?",
            (resolved, flow_id, bot_id),
        )
        if cur.rowcount == 0:
            return False, "未找到该流程"
    return True, None


def list_pro_scripts(bot_id: int) -> List[Dict]:
    with get_conn() as con:
        cur = con.execute(
            "SELECT p.id, p.name, p.command, p.code, p.active, p.group_id, p.created_at, p.updated_at,"
            " fg.name AS group_name, fg.active AS group_active "
            "FROM pro_scripts AS p "
            "LEFT JOIN feature_groups AS fg ON fg.id = p.group_id "
            "WHERE p.bot_id=? ORDER BY p.command",
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
    group_id: Optional[int] = None,
) -> Tuple[bool, Optional[str], Optional[int]]:
    name = (name or "").strip()
    command = (command or "").strip()
    code = (code or "").strip()
    if not all([name, command, code]):
        return False, "名称、命令和代码都不能为空", None
    if not command.startswith("/"):
        command = "/" + command

    with get_conn() as con:
        resolved_group = _resolve_group_id(con, bot_id, "pro_script", group_id)
        try:
            if script_id:
                cur = con.execute(
                    "UPDATE pro_scripts SET name=?, command=?, code=?, active=?, group_id=?, updated_at=CURRENT_TIMESTAMP "
                    "WHERE id=? AND bot_id=?",
                    (name, command, code, int(bool(active)), resolved_group, script_id, bot_id),
                )
                if cur.rowcount == 0:
                    return False, "未找到该脚本或无权限", script_id
                return True, None, script_id
            cur = con.execute(
                "INSERT INTO pro_scripts(bot_id, name, command, code, active, group_id) VALUES(?,?,?,?,?,?)",
                (bot_id, name, command, code, int(bool(active)), resolved_group),
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


def set_pro_script_active(bot_id: int, script_id: int, active: int) -> Tuple[bool, Optional[str]]:
    with get_conn() as con:
        cur = con.execute(
            "UPDATE pro_scripts SET active=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND bot_id=?",
            (int(bool(active)), script_id, bot_id),
        )
        if cur.rowcount == 0:
            return False, "未找到该脚本"
    return True, None


def set_pro_script_group(bot_id: int, script_id: int, group_id) -> Tuple[bool, Optional[str]]:
    with get_conn() as con:
        resolved = _resolve_group_id(con, bot_id, "pro_script", group_id)
        cur = con.execute(
            "UPDATE pro_scripts SET group_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND bot_id=?",
            (resolved, script_id, bot_id),
        )
        if cur.rowcount == 0:
            return False, "未找到该脚本"
    return True, None


def list_pseudocode(bot_id: int) -> List[Dict]:
    with get_conn() as con:
        cur = con.execute(
            "SELECT ps.id, ps.title, ps.content, ps.active, ps.group_id, ps.created_at, ps.updated_at,"
            " fg.name AS group_name, fg.active AS group_active "
            "FROM pseudocode AS ps "
            "LEFT JOIN feature_groups AS fg ON fg.id = ps.group_id "
            "WHERE ps.bot_id=? ORDER BY ps.id DESC",
            (bot_id,),
        )
        return cur.fetchall() or []


def upsert_pseudocode(
    bot_id: int,
    title: str,
    content: str,
    pseudo_id: Optional[int] = None,
    active: Optional[int] = None,
    group_id: Optional[int] = None,
) -> Tuple[bool, Optional[str], Optional[int]]:
    title = (title or "").strip()
    content = (content or "").strip()
    if not title or not content:
        return False, "标题/内容不能为空", None
    with get_conn() as con:
        resolved_group = _resolve_group_id(con, bot_id, "pseudocode", group_id)
        if pseudo_id:
            fields = ["title=?", "content=?", "group_id=?"]
            params: List = [title, content, resolved_group]
            if active is not None:
                fields.append("active=?")
                params.append(int(bool(active)))
            params.extend([pseudo_id, bot_id])
            sql = (
                "UPDATE pseudocode SET "
                + ", ".join(fields)
                + ", updated_at=CURRENT_TIMESTAMP WHERE id=? AND bot_id=?"
            )
            cur = con.execute(sql, tuple(params))
            if cur.rowcount == 0:
                return False, "未找到该伪代码", None
            return True, None, pseudo_id
        active_flag = 1 if active is None else int(bool(active))
        cur = con.execute(
            "INSERT INTO pseudocode(bot_id, title, content, active, group_id) VALUES (?,?,?,?,?)",
            (bot_id, title, content, active_flag, resolved_group),
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
            "SELECT ps.id, ps.title, ps.content, ps.active, ps.group_id, ps.created_at, ps.updated_at,"
            " fg.name AS group_name, fg.active AS group_active "
            "FROM pseudocode AS ps "
            "LEFT JOIN feature_groups AS fg ON fg.id = ps.group_id "
            "WHERE ps.id=? AND ps.bot_id=?",
            (pseudo_id, bot_id),
        )
        return cur.fetchone()


def set_pseudocode_active(bot_id: int, pseudo_id: int, active: int) -> Tuple[bool, Optional[str]]:
    with get_conn() as con:
        cur = con.execute(
            "UPDATE pseudocode SET active=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND bot_id=?",
            (int(bool(active)), pseudo_id, bot_id),
        )
        if cur.rowcount == 0:
            return False, "未找到该伪代码"
    return True, None


def set_pseudocode_group(bot_id: int, pseudo_id: int, group_id) -> Tuple[bool, Optional[str]]:
    with get_conn() as con:
        resolved = _resolve_group_id(con, bot_id, "pseudocode", group_id)
        cur = con.execute(
            "UPDATE pseudocode SET group_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND bot_id=?",
            (resolved, pseudo_id, bot_id),
        )
        if cur.rowcount == 0:
            return False, "未找到该伪代码"
    return True, None


def list_feature_groups(bot_id: int, kind: str) -> List[Dict]:
    norm_kind = _normalize_group_kind(kind)
    table_name = _GROUP_KIND_TABLE[norm_kind]
    with get_conn() as con:
        sql = f"""
            SELECT fg.id, fg.bot_id, fg.kind, fg.name, fg.description, fg.active,
                   fg.created_at, fg.updated_at,
                   COALESCE(cnt.total, 0) AS item_count,
                   COALESCE(cnt.active_total, 0) AS active_item_count
            FROM feature_groups AS fg
            LEFT JOIN (
                SELECT group_id,
                       COUNT(*) AS total,
                       SUM(CASE WHEN active=1 THEN 1 ELSE 0 END) AS active_total
                FROM {table_name}
                WHERE bot_id=?
                GROUP BY group_id
            ) AS cnt ON cnt.group_id = fg.id
            WHERE fg.bot_id=? AND fg.kind=?
            ORDER BY fg.id DESC
        """
        cur = con.execute(sql, (bot_id, bot_id, norm_kind))
        return cur.fetchall() or []


def upsert_feature_group(
    bot_id: int,
    kind: str,
    name: str,
    description: Optional[str] = None,
    group_id: Optional[int] = None,
    active: int = 1,
) -> Tuple[bool, Optional[str], Optional[int]]:
    norm_kind = _normalize_group_kind(kind)
    name = (name or "").strip()
    description = (description or "").strip()
    if not name:
        return False, "分组名称不能为空", None
    with get_conn() as con:
        if group_id:
            cur = con.execute(
                "UPDATE feature_groups SET name=?, description=?, active=?, updated_at=CURRENT_TIMESTAMP "
                "WHERE id=? AND bot_id=? AND kind=?",
                (name, description, int(bool(active)), group_id, bot_id, norm_kind),
            )
            if cur.rowcount == 0:
                return False, "未找到该分组", None
            return True, None, group_id
        cur = con.execute(
            """
            INSERT INTO feature_groups(bot_id, kind, name, description, active)
            VALUES (?,?,?,?,?)
            """,
            (bot_id, norm_kind, name, description, int(bool(active))),
        )
        return True, None, cur.lastrowid


def set_feature_group_active(bot_id: int, group_id: int, active: int) -> Tuple[bool, Optional[str]]:
    with get_conn() as con:
        cur = con.execute(
            "UPDATE feature_groups SET active=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND bot_id=?",
            (int(bool(active)), group_id, bot_id),
        )
        if cur.rowcount == 0:
            return False, "未找到该分组"
    return True, None


def delete_feature_group(bot_id: int, group_id: int) -> Tuple[bool, Optional[str]]:
    with get_conn() as con:
        cur = con.execute(
            "DELETE FROM feature_groups WHERE id=? AND bot_id=?",
            (group_id, bot_id),
        )
        if cur.rowcount == 0:
            return False, "未找到该分组"
    return True, None


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
    "set_command_active",
    "set_command_group",
    "list_flows",
    "upsert_flow",
    "delete_flow",
    "set_flow_active",
    "set_flow_group",
    "list_pro_scripts",
    "upsert_pro_script",
    "delete_pro_script",
    "set_pro_script_active",
    "set_pro_script_group",
    "list_pseudocode",
    "upsert_pseudocode",
    "delete_pseudocode",
    "get_pseudocode",
    "set_pseudocode_active",
    "set_pseudocode_group",
    "list_feature_groups",
    "upsert_feature_group",
    "set_feature_group_active",
    "delete_feature_group",
    "kv_get",
    "kv_set",
]
