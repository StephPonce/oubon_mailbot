"""
OSPRA INTELLIGENCE - Waitlist API Routes
========================================
Endpoints for Stratosphere waitlist management
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr
from typing import Optional
import logging

from .stratosphere_waitlist import (
    join_waitlist,
    waitlist,
    get_waitlist_confirmation_email,
    WaitlistSource
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/waitlist", tags=["waitlist"])


# ==================== REQUEST MODELS ====================

class WaitlistSignup(BaseModel):
    """Waitlist signup request"""
    email: str
    name: Optional[str] = None
    source: Optional[str] = "pricing_page"


class WaitlistCheck(BaseModel):
    """Check waitlist status"""
    email: str


# ==================== PUBLIC ENDPOINTS ====================

@router.post("/join")
async def join_stratosphere_waitlist(
    signup: WaitlistSignup,
    background_tasks: BackgroundTasks
):
    """
    Join the Stratosphere waitlist
    
    Returns position and founding member status
    """
    try:
        result = await join_waitlist(
            email=signup.email,
            name=signup.name,
            source=signup.source
        )
        
        # TODO: Send confirmation email in background
        # if result["is_new"]:
        #     background_tasks.add_task(send_confirmation_email, signup.email)
        
        return result
        
    except Exception as e:
        logger.error(f"[ERROR] Waitlist signup error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check")
async def check_waitlist_status(check: WaitlistCheck):
    """
    Check if an email is already on the waitlist
    """
    entry = await waitlist.check_email(check.email)
    
    if entry:
        return {
            "on_waitlist": True,
            "position": entry.position,
            "is_founding_member": entry.is_founding_member,
            "signed_up_at": entry.signed_up_at.isoformat() if entry.signed_up_at else None
        }
    else:
        return {
            "on_waitlist": False
        }


@router.get("/stats")
async def get_waitlist_stats():
    """
    Get public waitlist stats (for displaying FOMO on pricing page)
    """
    stats = waitlist.get_stats()
    
    return {
        "founding_spots_remaining": stats.founding_spots_remaining,
        "total_signups": stats.total_signups,
        "founding_spots_total": 50
    }


# ==================== ADMIN ENDPOINTS ====================

@router.get("/admin/entries")
async def list_waitlist_entries():
    """
    Admin: Get all waitlist entries
    """
    # TODO: Add admin authentication
    
    entries = waitlist.get_all_entries()
    stats = waitlist.get_stats()
    
    return {
        "entries": [
            {
                "email": e.email,
                "name": e.name,
                "position": e.position,
                "is_founding_member": e.is_founding_member,
                "current_tier": e.current_tier,
                "source": e.source.value if e.source else None,
                "signed_up_at": e.signed_up_at.isoformat() if e.signed_up_at else None,
                "converted": e.converted
            }
            for e in entries
        ],
        "stats": {
            "total": stats.total_signups,
            "founding_remaining": stats.founding_spots_remaining,
            "from_existing_customers": stats.from_existing_customers,
            "from_new_signups": stats.from_new_signups
        }
    }


@router.get("/admin/founding-members")
async def list_founding_members():
    """
    Admin: Get just the founding members (first 50)
    """
    # TODO: Add admin authentication
    
    founders = waitlist.get_founding_members()
    
    return {
        "founding_members": [
            {
                "position": e.position,
                "email": e.email,
                "name": e.name,
                "signed_up_at": e.signed_up_at.isoformat() if e.signed_up_at else None
            }
            for e in founders
        ],
        "count": len(founders),
        "spots_remaining": 50 - len(founders)
    }
