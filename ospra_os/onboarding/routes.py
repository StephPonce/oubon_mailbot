"""
OSPRA INTELLIGENCE - Onboarding API Routes
==========================================
Endpoints for Stratosphere white-glove onboarding
"""
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict
from datetime import datetime
import logging

from .stratosphere_onboarding import (
    handle_stratosphere_signup,
    process_onboarding_form,
    ONBOARDING_FORM_SCHEMA,
    CALENDLY_ONBOARDING_LINK,
    OnboardingChecklist
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


# ==================== REQUEST MODELS ====================

class OnboardingFormSubmission(BaseModel):
    """Stratosphere onboarding form submission"""
    niches: List[str]
    other_niches: Optional[str] = None
    store_url: str
    additional_stores: Optional[int] = 0
    revenue_goal: str
    current_revenue: str
    challenge: str
    product_volume: str
    ad_platforms: List[str]
    timezone: str
    preferred_contact: str
    whatsapp: Optional[str] = None
    anything_else: Optional[str] = None


class CallScheduledNotification(BaseModel):
    """Webhook from Calendly when call is booked"""
    event_type: str  # "invitee.created"
    user_email: str
    scheduled_time: datetime
    event_name: str


# ==================== ENDPOINTS ====================

@router.get("/form-schema")
async def get_onboarding_form_schema():
    """
    Get the onboarding form schema for frontend rendering
    """
    return ONBOARDING_FORM_SCHEMA


@router.post("/form/{user_id}")
async def submit_onboarding_form(
    user_id: str,
    form_data: OnboardingFormSubmission,
    background_tasks: BackgroundTasks
):
    """
    Submit completed onboarding form
    
    Returns Calendly booking link for next step
    """
    try:
        # Process form in background
        background_tasks.add_task(
            process_onboarding_form,
            user_id,
            form_data.dict()
        )
        
        return {
            "success": True,
            "message": "Thanks for completing the form! Let's book your onboarding call.",
            "next_step": "schedule_call",
            "calendly_url": CALENDLY_ONBOARDING_LINK,
            "data": {
                "niches": form_data.niches,
                "store_url": form_data.store_url
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Form submission error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/checklist/{user_id}")
async def get_onboarding_checklist(user_id: str):
    """
    Get onboarding checklist for dashboard display
    """
    # TODO: Fetch from database based on user's actual progress
    checklist = OnboardingChecklist()
    
    return {
        "user_id": user_id,
        "tier": "stratosphere",
        "checklist": checklist.items,
        "completed_count": sum(1 for item in checklist.items if item["completed"]),
        "total_count": len(checklist.items)
    }


@router.post("/checklist/{user_id}/{item_id}")
async def update_checklist_item(user_id: str, item_id: str, completed: bool = True):
    """
    Mark a checklist item as completed
    """
    # TODO: Update in database
    
    return {
        "success": True,
        "item_id": item_id,
        "completed": completed
    }


@router.post("/calendly-webhook")
async def handle_calendly_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Webhook from Calendly when onboarding call is scheduled
    """
    try:
        payload = await request.json()
        event_type = payload.get("event")
        
        if event_type == "invitee.created":
            # Call was booked
            invitee = payload.get("payload", {}).get("invitee", {})
            email = invitee.get("email")
            scheduled_time = payload.get("payload", {}).get("event", {}).get("start_time")
            
            logger.info(f"📅 Onboarding call scheduled: {email} at {scheduled_time}")
            
            # TODO: Update customer status
            # TODO: Send confirmation email
            # TODO: Add to your calendar
            
            return {"status": "received", "action": "call_scheduled"}
        
        return {"status": "ignored", "event": event_type}
        
    except Exception as e:
        logger.error(f"❌ Calendly webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{user_id}")
async def get_onboarding_status(user_id: str):
    """
    Get current onboarding status for a Stratosphere customer
    """
    # TODO: Fetch from database
    
    return {
        "user_id": user_id,
        "tier": "stratosphere",
        "status": "welcomed",
        "progress_percent": 25,
        "next_action": {
            "type": "complete_form",
            "label": "Complete onboarding questionnaire",
            "url": f"/onboarding/stratosphere?user={user_id}"
        },
        "success_manager": {
            "name": "Steph",
            "email": "steph@ospra.io",
            "calendly": CALENDLY_ONBOARDING_LINK
        }
    }


# ==================== ADMIN ENDPOINTS ====================

@router.get("/admin/customers")
async def list_stratosphere_customers():
    """
    Admin: List all Stratosphere customers and their onboarding status
    """
    # TODO: Fetch from database
    
    return {
        "customers": [],
        "total": 0,
        "needs_attention": 0  # Customers stuck in onboarding
    }


@router.get("/admin/customers/{user_id}")
async def get_stratosphere_customer_detail(user_id: str):
    """
    Admin: Get detailed info about a Stratosphere customer
    """
    # TODO: Fetch from database
    
    return {
        "user_id": user_id,
        "status": "Not found"
    }
