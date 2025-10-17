from __future__ import annotations
import os, sqlite3, json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from oubon_os.core.settings import get_settings


def _ensure_dir(path: str) -> None:
    Path(os.path.dirname(path) or ".").mkdir(parents=True, exist_ok=True)


def get_conn() -> sqlite3.Connection:
    db_path = get_settings().DATABASE_PATH
    _ensure_dir(db_path)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS event_log (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          type TEXT,
          source TEXT,
          details TEXT,
          ts TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS forecast_metrics (
          ts TEXT,
          sku TEXT,
          yhat REAL,
          p10 REAL,
          p50 REAL,
          p90 REAL
        )
    """)
    conn.commit()
    conn.close()


_init()


def log_event(evt_type: str, source: str, details: Dict[str, Any]) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO event_log (type, source, details, ts) VALUES (?, ?, ?, ?)",
        (evt_type, source, json.dumps(details, ensure_ascii=False), datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def recent_events(limit: int = 50) -> List[sqlite3.Row]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, type, source, details, ts FROM event_log ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def latest_forecast(sku: Optional[str] = None, limit: int = 14) -> List[sqlite3.Row]:
    conn = get_conn()
    cur = conn.cursor()
    if sku:
        cur.execute(
            "SELECT ts, sku, yhat, p10, p50, p90 FROM forecast_metrics WHERE sku = ? ORDER BY ts DESC LIMIT ?",
            (sku, limit)
        )
    else:
        cur.execute(
            "SELECT ts, sku, yhat, p10, p50, p90 FROM forecast_metrics ORDER BY ts DESC LIMIT ?",
            (limit,)
        )
    rows = cur.fetchall()
    conn.close()
    return rows


def persist_forecast_points(points: Iterable[Tuple[str, str, float, float, float, float]]) -> int:
    """points: iterable of (ts, sku, yhat, p10, p50, p90)"""
    conn = get_conn()
    cur = conn.cursor()
    cur.executemany(
        "INSERT INTO forecast_metrics (ts, sku, yhat, p10, p50, p90) VALUES (?, ?, ?, ?, ?, ?)",
        list(points)
    )
    conn.commit()
    n = cur.rowcount
    conn.close()
    return n
