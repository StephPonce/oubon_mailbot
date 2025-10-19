"""
Mock ad scheduling module for OubonOS Phase 4.

This module simulates scheduling campaigns across TikTok, Instagram,
and Google Ads, storing plans in SQLite.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, Iterable, List

from app.database import conn

logger = logging.getLogger(__name__)

AD_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ad_schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    sku TEXT NOT NULL,
    platform TEXT NOT NULL,
    start_date TEXT NOT NULL,
    budget REAL NOT NULL,
    status TEXT NOT NULL,
    performance TEXT
)
"""

conn.execute(AD_TABLE_SQL)
conn.commit()

SUPPORTED_PLATFORMS = ("tiktok", "instagram", "google_ads")


def plan_campaigns(
    skus: Iterable[str],
    *,
    daily_budget: float = 100.0,
    start_days_ahead: int = 1,
) -> List[Dict[str, str]]:
    """
    Create mock campaigns for the provided SKUs across platforms.
    Returns the inserted campaign metadata.
    """
    campaigns: List[Dict[str, str]] = []
    start = datetime.utcnow() + timedelta(days=start_days_ahead)
    for sku in skus:
        for platform in SUPPORTED_PLATFORMS:
            start_date = start.isoformat()
            conn.execute(
                "INSERT INTO ad_schedule (created_at, sku, platform, start_date, budget, status, performance) "
                "VALUES (datetime('now'), ?, ?, ?, ?, ?, ?)",
                (
                    sku,
                    platform,
                    start_date,
                    daily_budget,
                    "scheduled",
                    "",
                ),
            )
            campaigns.append(
                {
                    "sku": sku,
                    "platform": platform,
                    "start_date": start_date,
                    "budget": daily_budget,
                    "status": "scheduled",
                }
            )
    conn.commit()
    logger.info("Scheduled %s ad campaigns.", len(campaigns))
    return campaigns


def list_ad_schedule(limit: int = 50) -> List[Dict[str, str]]:
    rows = conn.execute(
        "SELECT id, created_at, sku, platform, start_date, budget, status, performance FROM ad_schedule "
        "ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [
        {
            "id": r[0],
            "created_at": r[1],
            "sku": r[2],
            "platform": r[3],
            "start_date": r[4],
            "budget": r[5],
            "status": r[6],
            "performance": r[7],
        }
        for r in rows
    ]
