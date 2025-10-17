"""Prophet-like forecasting utilities: model and pure backtesting helpers.
This module must remain framework-agnostic (no DB, no FastAPI).
"""

from __future__ import annotations
from datetime import datetime, timedelta


# Small dataclass for forecast results
class ForecastPoint:
    def __init__(self, ts: datetime, yhat: float, p10: float, p90: float):
        self.ts = ts
        self.yhat = yhat
        self.p10 = p10
        self.p90 = p90


# Lightweight forecaster: linear trend + simple seasonality, with uncertainty bands
class SimpleAdditiveForecaster:
    def __init__(self, history_days: int = 120):
        self.history_days = history_days
        self.fitted = False

    def fit(self, series: list[tuple[datetime, float]]):
        if not series:
            raise ValueError("Empty series")
        # Use only the last `history_days` of data if possible
        series = sorted(series, key=lambda x: x[0])
        if len(series) > self.history_days:
            series = series[-self.history_days :]
        self.dates = [x[0] for x in series]
        self.values = [x[1] for x in series]
        n = len(self.values)
        # Linear trend estimation: least squares
        # x: 0,1,2,...,n-1; y: values
        x = list(range(n))
        y = self.values
        x_mean = sum(x) / n
        y_mean = sum(y) / n
        num = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
        den = sum((xi - x_mean) ** 2 for xi in x)
        self.slope = _safe_div(num, den, default=0.0)
        self.intercept = y_mean - self.slope * x_mean
        # Estimate seasonality: simple weekly average if possible
        # Assume daily data, group by day-of-week (0=Monday)
        self.seasonality = {}
        if n >= 14:
            dow_vals = {i: [] for i in range(7)}
            for dt, val in zip(self.dates, self.values):
                dow = dt.weekday()
                dow_vals[dow].append(val)
            for dow in range(7):
                vals = dow_vals[dow]
                if vals:
                    self.seasonality[dow] = sum(vals) / len(vals)
                else:
                    self.seasonality[dow] = y_mean
            # Center seasonality so mean is zero
            mean_season = sum(self.seasonality.values()) / 7
            for dow in range(7):
                self.seasonality[dow] -= mean_season
        else:
            self.seasonality = None
        # Residuals for uncertainty
        preds = []
        for i, (dt, val) in enumerate(zip(self.dates, self.values)):
            pred = self.intercept + self.slope * i
            if self.seasonality:
                pred += self.seasonality.get(dt.weekday(), 0.0)
            preds.append(pred)
        residuals = [abs(v - p) for v, p in zip(self.values, preds)]
        mad = sum(residuals) / len(residuals) if residuals else 0.0
        self.mad = mad
        self.last_date = self.dates[-1]
        self.fitted = True

    def forecast(self, horizon: int):
        if not self.fitted:
            raise RuntimeError("Call fit() first")
        results = []
        base_idx = len(self.values)
        base_val = self.values[-1]
        for i in range(1, horizon + 1):
            ts = self.last_date + timedelta(days=i)
            idx = base_idx + (i - 1)
            yhat = self.intercept + self.slope * idx
            if self.seasonality:
                yhat += self.seasonality.get(ts.weekday(), 0.0)
            # Uncertainty: ±10% of MAD
            band = 0.1 * self.mad
            results.append(ForecastPoint(ts=ts, yhat=yhat, p10=yhat - band, p90=yhat + band))
        return results


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    try:
        return a / b if b != 0 else default
    except Exception:
        return default


def _winkler_score(y: float, lo: float, hi: float, alpha: float = 0.2) -> float:
    """
    Winkler interval score (lower is better) for a (1-alpha) interval.
    If y in [lo, hi]: width = hi - lo
    Else penalize distance outside by 2/alpha factor.
    """
    width = max(0.0, hi - lo)
    if lo <= y <= hi:
        return width
    elif y < lo:
        return width + (2.0 / alpha) * (lo - y)
    else:
        return width + (2.0 / alpha) * (y - hi)


def backtest_forecaster_on_series(series: list[tuple[datetime, float]], test_days: int = 28, min_train_days: int = 60, alpha: float = 0.2) -> dict:
    """
    Walk-forward 1-step backtest with expanding window.
    Returns aggregate metrics for the last `test_days`.
    """
    if not series or len(series) < (min_train_days + test_days):
        raise ValueError("insufficient history for backtest")
    # ensure sorted and contiguous (assume upstream fill_gaps if needed)
    series = sorted(series, key=lambda x: x[0])
    start_idx = len(series) - test_days
    errs = []
    winklers = []
    widths = []
    hits = 0
    n = 0
    abs_pct: list[float] = []

    # baseline for MASE: naive one-step MAE on training region
    train_vals = [y for _, y in series[:start_idx]]
    naive_train_mae = 0.0
    if len(train_vals) >= 2:
        naive_train_mae = sum(abs(train_vals[i] - train_vals[i - 1]) for i in range(1, len(train_vals))) / (len(train_vals) - 1)

    for i in range(start_idx, len(series)):
        train = series[:i]
        target_ts, y = series[i]

        model = SimpleAdditiveForecaster(history_days=max(120, min_train_days))
        model.fit(train)
        fcst = model.forecast(1)[0]  # one-step ahead
        yhat = fcst.yhat
        p10, p90 = fcst.p10, fcst.p90

        err = abs(y - yhat)
        errs.append(err)
        widths.append(max(0.0, p90 - p10))
        winklers.append(_winkler_score(y, p10, p90, alpha=alpha))
        if p10 <= y <= p90:
            hits += 1
        n += 1

        if y != 0:
            abs_pct.append(abs((y - yhat) / y))

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
        "n": n,
    }
