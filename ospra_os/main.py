from __future__ import annotations
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from ospra_os.analytics.dashboard import router as admin_router
from ospra_os.core.db import log_event
from ospra_os.core.settings import get_settings
from ospra_os.forecaster import write_demo_forecast
from ospra_os.forecaster.routes import router as forecast_router
from ospra_os.research import init_research_schema, router as research_router
from ospra_os.core.branding import get_branding

BRAND = get_branding()

app = FastAPI(title=f"{BRAND.OS_BRAND} API", version="0.1")

# CORS — allow your Shopify domain if set
s = get_settings()
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
def on_startup():
    init_research_schema()
    log_event("app.start", "ospra_os", {"env": s.ENV})
    # Seed a tiny demo forecast so admin dashboard has data
    n = write_demo_forecast(horizon=7)
    log_event("forecast.seeded", "forecaster", {"rows": n})


@app.get("/health")
def health():
    return JSONResponse({"status": "ok", "env": s.ENV})


# Mount admin router
app.include_router(admin_router)

# Mount synthetic forecast routes
app.include_router(forecast_router)

# Mount research admin routes
app.include_router(research_router)
