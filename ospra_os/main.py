from __future__ import annotations
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from ospra_os.analytics.dashboard import router as admin_router
from ospra_os.ai.routes import router as ai_router
from ospra_os.catalog.routes import router as catalog_router
from ospra_os.core.db import log_event
from ospra_os.core.settings import get_settings
from ospra_os.forecaster import write_demo_forecast
from ospra_os.forecaster.routes import router as forecast_router
from ospra_os.gmail.routes import router as gmail_router
from ospra_os.gmail.worker import get_worker
from ospra_os.research import init_research_schema, router as research_router
from ospra_os.core.branding import get_branding

BRAND = get_branding()

app = FastAPI(title=f"{BRAND.OS_BRAND} API", version="0.1")

# CORS — allow your Shopify domain if set
s = get_settings()
_inbox_worker = get_worker(s)
allow_origin = s.ALLOWED_ORIGIN or (f"https://{s.STORE_DOMAIN}" if s.STORE_DOMAIN else None)
cors_origins = [allow_origin] if allow_origin else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    init_research_schema()
    log_event("app.start", "ospra_os", {"env": s.ENV})
    # Seed a tiny demo forecast so admin dashboard has data
    n = write_demo_forecast(horizon=7)
    log_event("forecast.seeded", "forecaster", {"rows": n})
    await _inbox_worker.start()


@app.get("/health")
def health():
    worker_status = {}
    try:
        worker_status = _inbox_worker.status()
    except Exception:  # pragma: no cover - defensive
        worker_status = {"running": False}
    return JSONResponse({"status": "ok", "env": s.ENV, "gmail_worker": worker_status})


# Mount admin router
app.include_router(admin_router)

# Mount synthetic forecast routes
app.include_router(forecast_router)

# Mount research admin routes
app.include_router(research_router)

# Mount AI preview routes
app.include_router(ai_router)

# Mount Gmail routes
app.include_router(gmail_router)
app.include_router(catalog_router)


@app.on_event("shutdown")
async def on_shutdown():
    await _inbox_worker.stop()
