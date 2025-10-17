from __future__ import annotations
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from oubon_os.core.settings import get_settings
from oubon_os.core.db import log_event
from oubon_os.analytics.dashboard import router as admin_router
from oubon_os.forecaster import write_demo_forecast

app = FastAPI(title="Oubon OS", version="0.1")

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
    log_event("app.start", "oubon_os", {"env": s.ENV})
    # Seed a tiny demo forecast so admin dashboard has data
    n = write_demo_forecast(horizon=7)
    log_event("forecast.seeded", "forecaster", {"rows": n})


@app.get("/health")
def health():
    return JSONResponse({"status": "ok", "env": s.ENV})


# Mount admin router
app.include_router(admin_router)
