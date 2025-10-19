from __future__ import annotations

import logging
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from ospra_os.forecaster.prophet_forecaster import make_forecast_points, persist_forecast_rows

logger = logging.getLogger("oubon_mailbot")
router = APIRouter()


@router.get(
    "/forecast/test",
    summary="Forecast Test",
    description="Return an on-demand synthetic forecast.",
)
def forecast_test(h: int = Query(14, ge=1, le=60)):
    try:
        points = make_forecast_points(h=h, sku="SKU-DEMO")
        return {"ok": True, "horizon": h, "points": points}
    except Exception as exc:  # pragma: no cover - defensive path
        logger.exception("forecast_test failed: %s", exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=200)


@router.post(
    "/admin/forecast/run",
    summary="Forecast Run",
    description="Generate and persist a synthetic forecast into SQLite.",
)
def admin_forecast_run(h: int = Query(14, ge=1, le=60), sku: str = "SKU-DEMO"):
    try:
        points = make_forecast_points(h=h, sku=sku)
        written = persist_forecast_rows(points, db_path="data/forecast_metrics.db")
        return {"ok": True, "horizon": h, "sku": sku, "written": int(written)}
    except Exception as exc:  # pragma: no cover - defensive path
        logger.exception("admin_forecast_run failed: %s", exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=200)
