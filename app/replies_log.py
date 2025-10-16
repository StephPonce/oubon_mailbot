# app/replies_log.py
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

_DB_PATH = os.environ.get("MAILBOT_SQLITE_PATH", "data/mailbot.db")

def _conn():
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS replies_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT NOT NULL,
            message_id TEXT NOT NULL,
            to_addr TEXT,
            template_id TEXT,
            replied_at DATETIME NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS ix_replies_thread ON replies_log(thread_id)")
    return conn

def record_reply(thread_id: str, message_id: str, to_addr: Optional[str], template_id: Optional[str]) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO replies_log (thread_id, message_id, to_addr, template_id, replied_at) VALUES (?,?,?,?,?)",
            (thread_id, message_id, to_addr, template_id, datetime.utcnow().isoformat())
        )

def replied_recently(thread_id: str, hours: int = 24) -> bool:
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    with _conn() as c:
        row = c.execute(
            "SELECT 1 FROM replies_log WHERE thread_id = ? AND replied_at >= ? LIMIT 1",
            (thread_id, cutoff.isoformat())
        ).fetchone()
    return row is not None
