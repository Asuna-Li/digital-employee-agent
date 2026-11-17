#短期会话记忆：本地模式落 SQLite，云端模式只留内存

import os
import sqlite3
import threading
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "memory.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# SQLite 多线程写入加锁，避免并发问题
_lock = threading.Lock()

# 云端会话：只存内存，程序退出即消失
_cloud_sessions = {}


def _connect():
    """打开 SQLite 连接"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """创建消息表（幂等，重复调用安全）"""
    with _lock, _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                privacy_scope TEXT NOT NULL DEFAULT 'local',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session
            ON messages(session_id, id)
        """)
        conn.commit()


def append_message(session_id: str, role: str, content: str,
                   privacy_scope: str = "local"):
    """追加一条消息；cloud 模式只写内存，不落盘"""
    now = datetime.now().isoformat(timespec="seconds")

    if privacy_scope == "cloud":
        _cloud_sessions.setdefault(session_id, []).append({
            "role": role,
            "content": content,
            "privacy_scope": "cloud",
            "created_at": now,
        })
        return

    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO messages"
            "(session_id, role, content, privacy_scope, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, privacy_scope, now),
        )
        conn.commit()


def get_recent_messages(session_id: str, limit: int = 10) -> list:
    """读取最近 N 条消息：SQLite 本地消息 + 内存里的云端消息，按时间合并"""
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT role, content, privacy_scope, created_at "
            "FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()

    messages = [dict(r) for r in reversed(rows)]     # 恢复成时间正序

    # 合并云端内存消息
    messages.extend(_cloud_sessions.get(session_id, []))
    messages.sort(key=lambda m: m.get("created_at", ""))
    return messages[-limit:]


def clear_session(session_id: str):
    """清空某个会话（本地 + 云端）"""
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?",
                     (session_id,))
        conn.commit()
    _cloud_sessions.pop(session_id, None)


# 模块导入时自动建表
init_db()