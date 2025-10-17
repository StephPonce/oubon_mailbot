from __future__ import annotations
from datetime import datetime
from random import random

from oubon_os.core.db import log_event


def daily_health_probe() -> None:
    # Minimal signal to verify scheduler wiring in Phase 4.
    log_event("health.probe", "scheduler", {"heartbeat": datetime.utcnow().isoformat(), "cpu": round(50 + 50*random(), 2)})
