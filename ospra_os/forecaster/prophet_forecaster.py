"""Forecasting utilities used across Oubon OS.

Includes lightweight synthetic forecasting helpers plus a tiny additive model
that can generate DataFrame outputs for orchestrations and backtests.
"""

from __future__ import annotations

import logging
import math
import os
import random
import sqlite3
from datetime import date, datetime, timedelta
from typing import Dict, List, Tuple

import pandas as pd


logger = logging.getLogger(__name__)


# --- Simple additive forecaster -------------------------------------------------

class ForecastPoint:
    """Minimal container for forecast results."""

    def __init__(self, ts: datetime, yhat: float, p10: float, p90: float):
        self.ts = ts
        self.yhat = yhat
        self.p10 = p10
        self.p90 = p90


class SimpleAdditiveForecaster:
    """Linear trend + optional weekly seasonality with basic uncertainty bands."""

    def __init__(self, history_days: int = 120):
        self.history_days = history_days
        self.fitted = False

    def fit(self, series: List[Tuple[datetime, float]]):
        if not series:
            raise ValueError("Empty series")

        series = sorted(series, key=lambda x: x[0])
        if len(series) > self.history_days:
            series = series[-self.history_days :]

        self.dates = [x[0] for x in series]
        self.values = [x[1] for x in series]
        n = len(self.values)

        x = list(range(n))
        y = self.values
        x_mean = sum(x) / n
        y_mean = sum(y) / n
        num = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
        den = sum((xi - x_mean) ** 2 for xi in x)
        self.slope = _safe_div(num, den, default=0.0)
        self.intercept = y_mean - self.slope * x_mean

        self.seasonality: Dict[int, float] | None = {}
        if n >= 14:
            dow_vals = {i: [] for i in range(7)}
            for dt, val in zip(self.dates, self.values):
                dow_vals[dt.weekday()].append(val)
            for dow in range(7):
                vals = dow_vals[dow]
                if vals:
                    self.seasonality[dow] = sum(vals) / len(vals)
                else:
                    self.seasonality[dow] = y_mean
            mean_season = sum(self.seasonality.values()) / 7
            for dow in range(7):
                self.seasonality[dow] -= mean_season
        else:
            self.seasonality = None

        preds = []
        for i, (dt, _) in enumerate(zip(self.dates, self.values)):
            pred = self.intercept + self.slope * i
            if self.seasonality:
                pred += self.seasonality.get(dt.weekday(), 0.0)
            preds.append(pred)
        residuals = [abs(v - p) for v, p in zip(self.values, preds)]
        self.mad = sum(residuals) / len(residuals) if residuals else 0.0
        self.last_date = self.dates[-1]
        self.fitted = True

    def forecast(self, horizon: int) -> List[ForecastPoint]:
        if not self.fitted:
            raise RuntimeError("Call fit() first")

        results: List[ForecastPoint] = []
        base_idx = len(self.values)
        for i in range(1, horizon + 1):
            ts = self.last_date + timedelta(days=i)
            idx = base_idx + (i - 1)
            yhat = self.intercept + self.slope * idx
            if self.seasonality:
                yhat += self.seasonality.get(ts.weekday(), 0.0)
            band = 0.1 * self.mad
            results.append(ForecastPoint(ts=ts, yhat=yhat, p10=yhat - band, p90=yhat + band))
        return results


def generate_dummy_daily_series(days: int = 120, *, base: float = 100.0, seasonal_amp: float = 10.0) -> List[Tuple[datetime, float]]:
    """Create deterministic-but-varied synthetic daily demand for demos/tests."""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    start = today - timedelta(days=days - 1)
    series: List[Tuple[datetime, float]] = []
    for i in range(days):
        ts = start + timedelta(days=i)
        trend = base + 0.3 * i
        season = seasonal_amp * random.uniform(-1.0, 1.0)
        val = max(0.0, trend + season)
        series.append((ts, val))
    return series


class ProphetPredictor:
    """Thin adapter that produces forecasts for product DataFrames."""

    def __init__(self, horizon: int = 14, history_days: int = 120):
        self.horizon = horizon
        self.history_days = history_days

    def _series_for_product(self, product: pd.Series) -> List[Tuple[datetime, float]]:
        seed_base = float(product.get("score") or product.get("baseline", 80.0))
        return generate_dummy_daily_series(days=self.history_days, base=seed_base)

    def predict_demand(self, products: pd.DataFrame) -> pd.DataFrame:
        if products is None or products.empty:
            return pd.DataFrame(columns=["sku", "ts", "yhat", "p10", "p90"])

        rows = []
        for _, product in products.iterrows():
            sku = str(product.get("sku") or product.get("id") or product.get("title") or "UNKNOWN")
            history = self._series_for_product(product)

            model = SimpleAdditiveForecaster(history_days=self.history_days)
            model.fit(history)
            for point in model.forecast(self.horizon):
                rows.append(
                    {
                        "sku": sku,
                        "ts": point.ts,
                        "yhat": point.yhat,
                        "p10": point.p10,
                        "p90": point.p90,
                    }
                )
        return pd.DataFrame(rows)


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    try:
        return a / b if b != 0 else default
    except Exception:
        return default


def _winkler_score(y: float, lo: float, hi: float, alpha: float = 0.2) -> float:
    """
    Winkler interval score (lower is better) for a (1-alpha) interval.
    If y in [lo, hi]: width = hi - lo. Else penalize distance outside by 2/alpha.
    """
    width = max(0.0, hi - lo)
    if lo <= y <= hi:
        return width
    if y < lo:
        return width + (2.0 / alpha) * (lo - y)
    return width + (2.0 / alpha) * (y - hi)


def backtest_forecaster_on_series(
    series: List[Tuple[datetime, float]], test_days: int = 28, min_train_days: int = 60, alpha: float = 0.2
) -> Dict[str, float]:
    """
    Walk-forward 1-step backtest with expanding window.
    Returns aggregate metrics for the last `test_days`.
    """
    if not series or len(series) < (min_train_days + test_days):
        raise ValueError("insufficient history for backtest")

    series = sorted(series, key=lambda x: x[0])
    start_idx = len(series) - test_days
    errs: List[float] = []
    winklers: List[float] = []
    widths: List[float] = []
    hits = 0
    abs_pct: List[float] = []

    train_vals = [y for _, y in series[:start_idx]]
    naive_train_mae = 0.0
    if len(train_vals) >= 2:
        naive_train_mae = sum(abs(train_vals[i] - train_vals[i - 1]) for i in range(1, len(train_vals))) / (len(train_vals) - 1)

    for i in range(start_idx, len(series)):
        train = series[:i]
        target_ts, y = series[i]

        model = SimpleAdditiveForecaster(history_days=max(120, min_train_days))
        model.fit(train)
        fcst = model.forecast(1)[0]
        yhat = fcst.yhat
        p10, p90 = fcst.p10, fcst.p90

        errs.append(abs(y - yhat))
        widths.append(max(0.0, p90 - p10))
        winklers.append(_winkler_score(y, p10, p90, alpha=alpha))
        if p10 <= y <= p90:
            hits += 1

        if y != 0:
            abs_pct.append(abs((y - yhat) / y))

    n = len(errs)
    mae = sum(errs) / n if n else 0.0
    mape = sum(abs_pct) / len(abs_pct) if abs_pct else 0.0

    mase = _safe_div(mae, naive_train_mae, default=0.0)
    coverage = _safe_div(hits, n, default=0.0)
    avg_width = sum(widths) / n if n else 0.0
    winkler = sum(winklers) / n if n else 0.0

    return {
        "mae": mae,
        "mape": mape,
        "mase": mase,
        "coverage": coverage,
        "avg_width": avg_width,
        "winkler": winkler,
        "n": float(n),
    }


# --- Dict-based helpers used by HTTP routes / jobs ------------------------------

def make_forecast_points(h: int = 14, sku: str = "SKU-DEMO") -> List[Dict[str, float]]:
    """Generate a simple synthetic daily forecast."""
    today = date.today()
    points: List[Dict[str, float]] = []
    for i in range(h):
        current = today + timedelta(days=i)
        seasonal = 10.0 * math.sin(2.0 * math.pi * (i % 7) / 7.0)
        trend = 0.3 * i
        yhat = 100.0 + seasonal + trend
        spread = max(8.0, 0.1 * yhat)
        points.append(
            {
                "ts": f"{current.isoformat()}T00:00:00",
                "sku": sku,
                "yhat": float(yhat),
                "p10": float(yhat - spread),
                "p50": float(yhat),
                "p90": float(yhat + spread),
            }
        )
    return points


def _ensure_db(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS forecast_metrics (
            ts   TEXT NOT NULL,
            sku  TEXT NOT NULL,
            yhat REAL,
            p10  REAL,
            p50  REAL,
            p90  REAL,
            PRIMARY KEY (ts, sku)
        )
        """
    )
    conn.commit()


def persist_forecast_rows(points: List[Dict[str, float]], db_path: str = "data/forecast_metrics.db") -> int:
    """Upsert forecast points into the forecast_metrics SQLite table."""
    if not points:
        return 0

    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        _ensure_db(conn)
        cur = conn.cursor()
        written = 0
        for p in points:
            cur.execute(
                """
                INSERT OR REPLACE INTO forecast_metrics (ts, sku, yhat, p10, p50, p90)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    p["ts"],
                    p.get("sku", "SKU-DEMO"),
                    float(p["yhat"]),
                    float(p["p10"]),
                    float(p["p50"]),
                    float(p["p90"]),
                ),
            )
            written += 1
        conn.commit()
        logger.info(
            "Forecast persisted: sku=%s horizon=%d rows=%d",
            points[0].get("sku", "SKU-DEMO"),
            len(points),
            written,
        )
        return written
    finally:
        conn.close()
