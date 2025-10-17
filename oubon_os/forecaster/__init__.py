from __future__ import annotations
from datetime import date, timedelta
from typing import List, Tuple

from oubon_os.core.db import persist_forecast_points


def write_demo_forecast(sku: str = "SKU-DEMO", horizon: int = 14) -> int:
    """
    Writes a synthetic forecast (demo) so the dashboard isn't empty.
    """
    today = date.today()
    points: List[Tuple[str, str, float, float, float, float]] = []
    for i in range(horizon):
        ts = (today + timedelta(days=i)).isoformat()
        yhat = 100.0 + i * 1.5
        p10 = yhat * 0.92
        p50 = yhat
        p90 = yhat * 1.08
        points.append((ts, sku, yhat, p10, p50, p90))
    return persist_forecast_points(points)
