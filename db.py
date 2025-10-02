# db.py
import os
import sqlite3
import hashlib
from contextlib import contextmanager
from typing import List, Dict, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "bot_admin.db")


# ---------------- basics ----------------
def _row_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

@contextmanager
def get_conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = _row_factory
    con.execute("PRAGMA foreign_keys = ON;")
    try:
        yield con
        con.commit()
    finally:
        con.close()


# ---------------- init ----------------
def init_db():
    with get_conn() as con:
        con.executescript("""
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
            payload TEXT,                -- JSON string (or NULL)
            parse_mode TEXT,             -- 'HTML' | 'MarkdownV2' | NULL
            disable_preview INTEGER DEFAULT 0,  -- 0/1
            UNIQUE(bot_id, command),
            FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS flows(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            blocks_json TEXT NOT NULL,   -- compiled flow + __xml
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS kv_store(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id INTEGER NOT NULL,
            scope TEXT NOT NULL,         -- 'chat' | 'user' | 'bot'
            chat_id TEXT DEFAULT '',     -- use '' as None
            user_id TEXT DEFAULT '',     -- use '' as None
            key TEXT NOT NULL,
            value TEXT,
            UNIQUE(bot_id, scope, chat_id, user_id, key),
            FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE
        );
        """)
    return True


# ---------------- users ----------------
def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()

def create_user(username: str, password: str) -> (bool, Optional[str]):
    if not username or not password:
        return False, "用户名/密码不能为空"
    with get_conn() as con:
        try:
            con.execute(
                "INSERT INTO users(username, password_hash) VALUES (?,?)",
                (username, _hash(password)),
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


# ---------------- bots ----------------
def create_bot(user_id: int, name: str, token: str) -> (bool, Optional[str]):
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

def delete_bot(user_id: int, bot_id: int) -> (bool, Optional[str]):
    with get_conn() as con:
        cur = con.execute("DELETE FROM bots WHERE id=? AND user_id=?", (bot_id, user_id))
        if cur.rowcount == 0:
            return False, "无此 bot 或无权限"
    return True, None


# ---------------- commands ----------------
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
) -> (bool, Optional[str]):
    if not command:
        return False, "command 不能为空"
    # 统一命令前缀
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

def delete_command(bot_id: int, command: str) -> (bool, Optional[str]):
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

def erase_commands(bot_id: int) -> (bool, Optional[str]):
    with get_conn() as con:
        con.execute("DELETE FROM commands WHERE bot_id=?", (bot_id,))
    return True, None


# ---------------- flows ----------------
def list_flows(bot_id: int) -> List[Dict]:
    with get_conn() as con:
        cur = con.execute(
            "SELECT id,name,blocks_json,active,created_at,updated_at "
            "FROM flows WHERE bot_id=? ORDER BY id DESC",
            (bot_id,),
        )
        return cur.fetchall() or []

def upsert_flow(bot_id: int, name: str, blocks_json: str, flow_id: Optional[int] = None, active: int = 1) -> (bool, Optional[str], Optional[int]):
    if not name or not blocks_json:
        return False, "name/blocks_json 不能为空", None
    with get_conn() as con:
        if flow_id:
            con.execute(
                "UPDATE flows SET name=?, blocks_json=?, active=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND bot_id=?",
                (name, blocks_json, int(bool(active)), flow_id, bot_id),
            )
            return True, None, flow_id
        else:
            cur = con.execute(
                "INSERT INTO flows(bot_id,name,blocks_json,active) VALUES(?,?,?,?)",
                (bot_id, name, blocks_json, int(bool(active))),
            )
            return True, None, cur.lastrowid

def delete_flow(bot_id: int, flow_id: int) -> (bool, Optional[str]):
    with get_conn() as con:
        cur = con.execute("DELETE FROM flows WHERE id=? AND bot_id=?", (flow_id, bot_id))
        if cur.rowcount == 0:
            return False, "未找到该流程"
    return True, None


# ---------------- kv_store for flows ----------------
def _nz(x: Optional[str]) -> str:
    return "" if x is None else str(x)

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
