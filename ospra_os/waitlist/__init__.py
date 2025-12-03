"""
OSPRA INTELLIGENCE - Waitlist Module
====================================
"""
from .stratosphere_waitlist import (
    WaitlistEntry,
    WaitlistStats,
    WaitlistSource,
    waitlist,
    join_waitlist,
    get_waitlist_confirmation_email,
    get_waitlist_launch_email,
    FOUNDING_MEMBER_LIMIT
)

from .routes import router as waitlist_router

__all__ = [
    "WaitlistEntry",
    "WaitlistStats",
    "WaitlistSource",
    "waitlist",
    "join_waitlist",
    "get_waitlist_confirmation_email",
    "get_waitlist_launch_email",
    "FOUNDING_MEMBER_LIMIT",
    "waitlist_router"
]
