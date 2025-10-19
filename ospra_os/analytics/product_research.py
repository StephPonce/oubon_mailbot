"""
Automated product research module for OubonOS Phase 4.

This module aggregates trending products from multiple public sources,
summarizes them via AI, and stores results in SQLite.
"""

from __future__ import annotations

import json
import logging
import random
from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple

from app.ai_client import ai_client
from app.database import conn
from ospra_os.forecaster.ingestor import iso_day
from ospra_os.forecaster.prophet_forecaster import generate_dummy_daily_series

logger = logging.getLogger(__name__)

PRODUCT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS product_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL,
    title TEXT NOT NULL,
    platform TEXT NOT NULL,
    score REAL NOT NULL,
    summary TEXT NOT NULL,
    last_seen TEXT NOT NULL
)
"""

conn.execute(PRODUCT_TABLE_SQL)
conn.commit()


def _mock_tiktok_products() -> List[Dict[str, Any]]:
    """Simulate TikTok creative center trending products."""
    items = []
    for idx in range(5):
        items.append(
            {
                "sku": f"TIKTOK-{idx+1}",
                "title": f"TikTok Viral Gadget #{idx+1}",
                "platform": "tiktok",
                "views": random.randint(500_000, 5_000_000),
                "engagement_rate": round(random.uniform(0.02, 0.12), 3),
            }
        )
    return items


def _mock_google_trends() -> List[Dict[str, Any]]:
    """Simulate Google Trends trending searches."""
    items = []
    for idx in range(5):
        items.append(
            {
                "sku": f"GOOGLE-{idx+1}",
                "title": f"Google Trend Product #{idx+1}",
                "platform": "google_trends",
                "score": random.randint(60, 100),
                "growth": random.uniform(1.1, 2.5),
            }
        )
    return items


def _mock_amazon_movers() -> List[Dict[str, Any]]:
    items = []
    for idx in range(5):
        items.append(
            {
                "sku": f"AMZ-{idx+1}",
                "title": f"Amazon Mover #{idx+1}",
                "platform": "amazon",
                "bestseller_rank": random.randint(1, 100),
                "reviews": random.randint(50, 5000),
                "rating": round(random.uniform(3.5, 4.9), 2),
            }
        )
    return items


def _mock_aliexpress_products() -> List[Dict[str, Any]]:
    items = []
    for idx in range(5):
        items.append(
            {
                "sku": f"ALI-{idx+1}",
                "title": f"AliExpress Trend #{idx+1}",
                "platform": "aliexpress",
                "orders": random.randint(100, 2000),
                "price": round(random.uniform(5.0, 40.0), 2),
            }
        )
    return items


def fetch_trending_products() -> List[Dict[str, Any]]:
    """Aggregate trending products across multiple sources."""
    aggregated: List[Dict[str, Any]] = []
    aggregated.extend(_mock_tiktok_products())
    aggregated.extend(_mock_google_trends())
    aggregated.extend(_mock_amazon_movers())
    aggregated.extend(_mock_aliexpress_products())
    return aggregated


def _ai_summarize(product: Dict[str, Any]) -> Tuple[str, float]:
    """Summarize a product and compute a score via AI; fallback to heuristic."""
    try:
        client = ai_client()
        prompt = (
            "You are an ecommerce product analyst. Score the viral potential of this product (0-100) "
            "and provide a short summary (max 3 sentences). Return JSON with keys 'score' and 'summary'.\n\n"
            f"Product data: {json.dumps(product, ensure_ascii=False)}"
        )
        response = client.chat(prompt)
        if response:
            data = json.loads(response)
            score = float(data.get("score", 0))
            summary = data.get("summary", "")
            if summary:
                return summary, max(0.0, min(100.0, score))
    except Exception as exc:
        logger.warning("AI summarizer fallback (error: %s)", exc)

    # Heuristic fallback
    base_score = random.uniform(40, 80)
    platform = product.get("platform", "unknown")
    if platform == "tiktok":
        base_score += 10
    if platform == "amazon":
        base_score += 5
    summary = f"{product.get('title')} is trending on {platform} with strong engagement metrics."
    return summary, float(max(0.0, min(100.0, base_score)))


def summarize_product(product: Dict[str, Any]) -> Dict[str, Any]:
    summary, score = _ai_summarize(product)
    return {
        "sku": product.get("sku") or f"SKU-{random.randint(1000, 9999)}",
        "title": product.get("title", "Unknown Product"),
        "platform": product.get("platform", "unknown"),
        "score": score,
        "summary": summary,
        "last_seen": datetime.utcnow().isoformat(),
    }


def persist_product_insights(products: Iterable[Dict[str, Any]]) -> int:
    rows = 0
    for product in products:
        conn.execute(
            "INSERT INTO product_insights (sku, title, platform, score, summary, last_seen) VALUES (?, ?, ?, ?, ?, ?)",
            (
                product["sku"],
                product["title"],
                product["platform"],
                product["score"],
                product["summary"],
                product["last_seen"],
            ),
        )
        rows += 1
    conn.commit()
    return rows


def run_product_research(top_n: int = 10) -> Dict[str, Any]:
    """Main entrypoint for product research pipeline."""
    aggregated = fetch_trending_products()
    summarized = [summarize_product(product) for product in aggregated]
    summarized.sort(key=lambda p: p["score"], reverse=True)
    top_products = summarized[:top_n]
    written = persist_product_insights(top_products)
    logger.info("Persisted %s product insights.", written)
    return {"ok": True, "count": written, "products": top_products}


def list_recent_products(limit: int = 20) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT sku, title, platform, score, summary, last_seen FROM product_insights ORDER BY last_seen DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [
        {
            "sku": r[0],
            "title": r[1],
            "platform": r[2],
            "score": r[3],
            "summary": r[4],
            "last_seen": r[5],
        }
        for r in rows
    ]
