from datetime import datetime
import os
import pytz
from app.settings import get_settings


def _as_int(val, default):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def is_quiet_hours(now: datetime | None = None) -> bool:
    """
    Return True if local time is within quiet hours.
    Test overrides:
      - FORCE_DAY=1      -> always open hours (returns False)
      - FORCE_QUIET=1    -> always quiet hours (returns True)
      - AI_MODE=day|night (day->False, night->True)
    """
    # --- explicit overrides for testing ---
    if os.getenv("FORCE_DAY", "").lower() in ("1", "true", "yes"):
        return False
    if os.getenv("FORCE_QUIET", "").lower() in ("1", "true", "yes"):
        return True
    mode = os.getenv("AI_MODE", "").lower().strip()
    if mode == "day":
        return False
    if mode in ("night", "quiet"):
        return True

    # --- normal behavior ---
    s = get_settings()
    tz_name = (
        getattr(s, "STORE_TIMEZONE", None)
        or getattr(s, "store_timezone", None)
        or "America/Chicago"
    )
    try:
        tz = pytz.timezone(tz_name)
    except pytz.UnknownTimeZoneError:
        tz = pytz.timezone("America/Chicago")  # robust fallback

    now = now or datetime.now(tz)
    start = _as_int(getattr(s, "QUIET_HOURS_START", 22), 22)
    end = _as_int(getattr(s, "QUIET_HOURS_END", 7), 7)
    if start < end:
        return start <= now.hour < end
    # overnight window (e.g., 22–7)
    return now.hour >= start or now.hour < end
