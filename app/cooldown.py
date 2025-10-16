from datetime import datetime
from typing import Any

from app.database import conn

conn.execute(
    """
    CREATE TABLE IF NOT EXISTS replies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT NOT NULL,
        thread_id TEXT,
        replied_at TEXT NOT NULL
    )
    """
)
conn.execute(
    "CREATE INDEX IF NOT EXISTS idx_replies_sender_thread ON replies(sender, IFNULL(thread_id,''))"
)
conn.commit()


def _s(v: Any) -> str:
    try:
        return v if isinstance(v, str) else "" if v is None else str(v)
    except Exception:
        return ""


def last_replied_at(sender, thread_id=None):
    s = _s(sender).lower().strip()
    t = _s(thread_id).strip()
    row = conn.execute(
        "SELECT replied_at FROM replies WHERE sender=? AND IFNULL(thread_id,'')=? ORDER BY replied_at DESC LIMIT 1",
        (s, t),
    ).fetchone()
    return row[0] if row else None


def mark_replied(sender, thread_id=None):
    s = _s(sender).lower().strip()
    t = _s(thread_id).strip()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO replies (sender, thread_id, replied_at) VALUES (?,?,?)",
        (s, t, now),
    )
    conn.commit()


def is_on_cooldown(sender, hours, thread_id=None):
    last = last_replied_at(sender, thread_id)
    if not last:
        return False
    try:
        last_dt = datetime.fromisoformat(last)
    except Exception:
        return False
    return (datetime.utcnow() - last_dt).total_seconds() < hours * 3600
