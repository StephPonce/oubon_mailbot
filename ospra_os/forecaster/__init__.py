from __future__ import annotations
from datetime import date, timedelta
from typing import List, Tuple

from fastapi import APIRouter

from ospra_os.core.db import persist_forecast_points
from ospra_os.forecaster.ingestor import build_daily_series_by_sku, fill_gaps, iso_day
from ospra_os.forecaster.prophet_forecaster import (
    ForecastPoint,
    ProphetPredictor,
    SimpleAdditiveForecaster,
    backtest_forecaster_on_series,
    generate_dummy_daily_series,
    make_forecast_points,
    persist_forecast_rows,
)
from ospra_os.forecaster.routes import router as _forecast_router

__all__ = [
    "ForecastPoint",
    "ProphetPredictor",
    "SimpleAdditiveForecaster",
    "backtest_forecaster_on_series",
    "build_daily_series_by_sku",
    "fill_gaps",
    "generate_dummy_daily_series",
    "make_forecast_points",
    "persist_forecast_rows",
    "get_forecaster_router",
    "iso_day",
    "write_demo_forecast",
]


def get_forecaster_router() -> APIRouter:
    """Expose the forecast router so callers can mount it easily."""
    return _forecast_router


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
