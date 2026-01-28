"""
Daily Brief API Routes

Endpoints for accessing personalized daily briefs.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from ospra_os.database import get_db, User
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.intelligence.daily_brief import get_daily_brief_generator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["daily-brief"])


@router.get("/daily-brief")
async def get_daily_brief(
    store_id: Optional[int] = Query(None, description="Optional store ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get personalized daily brief for the current user.

    Returns:
        {
            "timestamp": "2025-12-09T08:00:00",
            "greeting": "Good morning",
            "summary_text": "AI-generated summary...",
            "pending_actions": {
                "count": 4,
                "high_confidence": 2,
                "actions": [...]
            },
            "performance": {...},
            "opportunities": {...},
            "priorities": [...]
        }
    """
    try:
        logger.info(f"Generating daily brief for user {current_user.id}")

        generator = get_daily_brief_generator(db)
        brief = await generator.generate_daily_brief(
            user_id=current_user.id,
            store_id=store_id
        )

        return brief

    except Exception as e:
        logger.error(f"Error generating daily brief: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate daily brief. Please try again.")


@router.post("/daily-brief/send-email")
async def send_daily_brief_email(
    email: Optional[str] = Query(None, description="Email address (defaults to user's email)"),
    store_id: Optional[int] = Query(None, description="Optional store ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Send daily brief as an email.

    This endpoint generates the daily brief and sends it to the user's email.
    In production, this would be scheduled to run every morning.

    Args:
        email: Optional email address (defaults to current user's email)
        store_id: Optional store ID

    Returns:
        {
            "success": true,
            "message": "Daily brief sent to user@example.com",
            "brief_summary": "..."
        }
    """
    try:
        logger.info(f"Sending daily brief email for user {current_user.id}")

        # Generate brief
        generator = get_daily_brief_generator(db)
        brief = await generator.generate_daily_brief(
            user_id=current_user.id,
            store_id=store_id
        )

        # Get recipient email
        recipient_email = email or current_user.email

        # TODO: Implement email sending
        # For now, just return the brief data
        # In production, this would:
        # 1. Format brief as HTML email
        # 2. Send via email service (SendGrid, AWS SES, etc.)
        # 3. Log sent email

        logger.info(f"Would send daily brief to {recipient_email}")

        return {
            "success": True,
            "message": f"Daily brief would be sent to {recipient_email}",
            "brief_summary": brief.get("summary_text", ""),
            "action_count": brief.get("pending_actions", {}).get("count", 0),
            "note": "Email sending not yet implemented. This endpoint generates the brief and returns it."
        }

    except Exception as e:
        logger.error(f"Error sending daily brief email: {e}")
        raise HTTPException(status_code=500, detail="Failed to send daily brief. Please try again.")


@router.get("/daily-brief/preview")
async def preview_daily_brief(
    store_id: Optional[int] = Query(None, description="Optional store ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Preview daily brief without sending email.

    Same as GET /daily-brief but explicitly named for clarity.
    Useful for testing or showing preview in UI.
    """
    try:
        logger.info(f"Previewing daily brief for user {current_user.id}")

        generator = get_daily_brief_generator(db)
        brief = await generator.generate_daily_brief(
            user_id=current_user.id,
            store_id=store_id
        )

        return brief

    except Exception as e:
        logger.error(f"Error previewing daily brief: {e}")
        raise HTTPException(status_code=500, detail="Failed to preview daily brief. Please try again.")
