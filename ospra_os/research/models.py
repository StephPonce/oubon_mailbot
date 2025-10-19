from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Optional

from ospra_os.core.db import get_conn


def init_research_schema() -> None:
    """Create research tables if they do not exist."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS research_queue (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              term TEXT NOT NULL,
              created_at REAL NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS product_candidates (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              title TEXT NOT NULL,
              source TEXT NOT NULL,
              score REAL NOT NULL,
              url TEXT,
              image TEXT,
              price_estimate REAL,
              status TEXT NOT NULL DEFAULT 'queued',
              meta_json TEXT,
              created_at REAL NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def enqueue_terms(terms: Iterable[str]) -> int:
    """Insert new research terms into the queue. Returns total queue length."""
    now = time.time()
    conn = get_conn()
    inserted = 0
    try:
        cur = conn.cursor()
        for raw in terms:
            term = (raw or "").strip()
            if not term:
                continue
            cur.execute(
                "INSERT INTO research_queue (term, created_at) VALUES (?, ?)",
                (term, now),
            )
            inserted += 1
        conn.commit()
        (total,) = cur.execute("SELECT COUNT(*) FROM research_queue").fetchone()
        return int(total)
    finally:
        conn.close()


def list_queue(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT id, term, created_at FROM research_queue ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"id": row["id"], "term": row["term"], "created_at": row["created_at"]}
            for row in rows
        ]
    finally:
        conn.close()


def _insert_candidate(payload: Dict[str, Any]) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO product_candidates
              (title, source, score, url, image, price_estimate, status, meta_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("title"),
                payload.get("source", "demo"),
                float(payload.get("score", 0.0)),
                payload.get("url"),
                payload.get("image"),
                payload.get("price_estimate"),
                payload.get("status", "queued"),
                payload.get("meta_json"),
                time.time(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def run_research_once(max_terms: int, max_candidates_per_term: int) -> int:
    """Consume a slice of the research queue and synthesize demo candidates."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, term FROM research_queue ORDER BY id ASC LIMIT ?",
            (max_terms,),
        ).fetchall()
        ids = [row["id"] for row in rows]
        if ids:
            conn.execute(
                f"DELETE FROM research_queue WHERE id IN ({','.join(['?'] * len(ids))})",
                ids,
            )
            conn.commit()
    finally:
        conn.close()

    created = 0
    for row in rows:
        term = (row["term"] or "").strip()
        if not term:
            continue
        for idx in range(max_candidates_per_term):
            _insert_candidate(
                {
                    "title": f"{term} Product Idea #{idx + 1}",
                    "source": "demo",
                    "score": 0.6 + (idx * 0.1),
                    "url": f"https://example.com/{term.replace(' ', '-')}/{idx + 1}",
                    "image": "https://via.placeholder.com/300",
                    "price_estimate": 24.99 + idx,
                    "status": "queued",
                    "meta_json": None,
                }
            )
            created += 1
    return created


def list_candidates(status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        base = "SELECT id, title, source, score, url, image, price_estimate, status, created_at FROM product_candidates"
        params: List[Any] = []
        if status:
            base += " WHERE status = ?"
            params.append(status)
        base += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(base, params).fetchall()
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "source": row["source"],
                "score": row["score"],
                "url": row["url"],
                "image": row["image"],
                "price_estimate": row["price_estimate"],
                "status": row["status"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    finally:
        conn.close()


def update_candidate_status(cid: int, status: str) -> bool:
    if status not in {"approved", "rejected", "queued"}:
        return False
    conn = get_conn()
    try:
        cur = conn.execute(
            "UPDATE product_candidates SET status = ? WHERE id = ?",
            (status, cid),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
