"""
Simple SQLite helper for multi-store metadata.

This module keeps a shared connection to data/mailbot.db, ensures the stores table
exists, and exposes a lightweight cursor via get_db().
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

_CONNECTION: Optional[sqlite3.Connection] = None


def _ensure_connection() -> sqlite3.Connection:
    global _CONNECTION
    if _CONNECTION is None:
        db_path = Path("data") / "mailbot.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _CONNECTION = sqlite3.connect(db_path, check_same_thread=False)
        _CONNECTION.row_factory = sqlite3.Row
        _CONNECTION.execute(
            "CREATE TABLE IF NOT EXISTS stores (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, token TEXT)"
        )
        _CONNECTION.commit()
    return _CONNECTION


def get_db() -> sqlite3.Cursor:
    """
    Return a cursor bound to the shared SQLite connection.
    Callers are responsible for closing the cursor if they open long-lived ones.
    """
    connection = _ensure_connection()
    return connection.cursor()


def insert_store(name: str, token: str) -> None:
    """
    Convenience helper for tests or scripts that need to seed the stores table quickly.
    """
    connection = _ensure_connection()
    connection.execute("INSERT INTO stores (name, token) VALUES (?, ?)", (name, token))
    connection.commit()


conn = _ensure_connection()


def get_connection() -> sqlite3.Connection:
    return _ensure_connection()


__all__ = ["conn", "get_connection", "get_db", "insert_store"]
