"""Email automation API routes for OspraOS."""
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from ospra_os.core.settings import Settings, get_settings
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User
from ospra_os.email_automation.email_processor import EmailProcessor
from ospra_os.email_automation.gmail_client import GmailClient
from ospra_os.analytics.email_analytics import Analytics


router = APIRouter(prefix="/api/email-automation", tags=["Email Automation"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ProcessInboxRequest(BaseModel):
    """Request to process inbox with auto-replies."""
    max_messages: int = 10
    label_filter: Optional[str] = None


class ProcessInboxResponse(BaseModel):
    """Response from processing inbox."""
    success: bool
    processed: int
    replied: int
    errors: int
    messages: list


class SendEmailRequest(BaseModel):
    """Request to send an email."""
    to: str
    subject: str
    body: str


class WatchStatusResponse(BaseModel):
    """Gmail watch status response."""
    active: bool
    history_id: Optional[str] = None
    expiration: Optional[int] = None


# ============================================================================
# EMAIL PROCESSING ENDPOINTS
# ============================================================================

@router.post("/process-inbox", response_model=ProcessInboxResponse)
async def process_inbox(
    request: ProcessInboxRequest,
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
):
    """
    Process inbox with intelligent auto-replies.

    Uses SmartReplySystem for:
    - AI-powered responses during business hours
    - Template-based responses during quiet hours
    - Order tracking integration with Shopify
    - Automated refund processing (with safety limits)
    - Email classification and labeling
    """
    try:
        processor = EmailProcessor(settings)

        result = processor.process_inbox(
            max_messages=request.max_messages,
            label_filter=request.label_filter,
        )

        return ProcessInboxResponse(
            success=True,
            processed=result.get("processed", 0),
            replied=result.get("replied", 0),
            errors=result.get("errors", 0),
            messages=result.get("messages", []),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error processing inbox. Please try again.")


@router.post("/gmail/pubsub/webhook")
async def gmail_pubsub_webhook(
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(get_settings),
):
    """
    Gmail Pub/Sub webhook endpoint.

    Google Cloud Pub/Sub calls this endpoint when new emails arrive.
    This triggers automatic email processing in the background.

    Setup instructions:
    1. Enable Gmail API push notifications in Google Cloud Console
    2. Create a Pub/Sub topic (e.g., "gmail-notifications")
    3. Grant Gmail service account publish permissions
    4. Set up Gmail watch with: POST /api/email-automation/gmail/watch/start
    """
    # Process emails in background (don't block webhook response)
    background_tasks.add_task(process_emails_background, settings)

    return {"status": "queued", "message": "Email processing started in background"}


async def process_emails_background(settings: Settings):
    """Background task to process new emails."""
    try:
        processor = EmailProcessor(settings)

        result = processor.process_inbox(
            max_messages=10,  # Process recent emails
        )

        print(f"[SUCCESS] Processed {result['processed']} emails, replied to {result['replied']}")

    except Exception as e:
        print(f"[ERROR] Error in background email processing: {e}")


# ============================================================================
# GMAIL MANAGEMENT ENDPOINTS
# ============================================================================

@router.post("/gmail/send")
async def send_email(
    request: SendEmailRequest,
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
):
    """Send a simple email via Gmail."""
    try:
        gmail_client = GmailClient(settings)
        gmail_client.send_simple_email(
            to=request.to,
            subject=request.subject,
            body=request.body,
        )

        return {"success": True, "message": "Email sent successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error sending email. Please try again.")


@router.post("/gmail/watch/start")
async def start_gmail_watch(
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user)
):
    """
    Start Gmail push notifications via Pub/Sub.

    This enables real-time email processing by setting up a Gmail watch
    that notifies your webhook endpoint when new emails arrive.
    """
    try:
        gmail_client = GmailClient(settings)

        # Set up Gmail watch
        watch_request = {
            "labelIds": ["INBOX"],
            "topicName": f"projects/{settings.GOOGLE_CLOUD_PROJECT_ID}/topics/{settings.GMAIL_PUBSUB_TOPIC}",
        }

        result = gmail_client.service.users().watch(
            userId="me",
            body=watch_request,
        ).execute()

        return {
            "success": True,
            "history_id": result.get("historyId"),
            "expiration": result.get("expiration"),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error starting Gmail watch. Please try again.")


@router.post("/gmail/watch/stop")
async def stop_gmail_watch(
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user)
):
    """Stop Gmail push notifications."""
    try:
        gmail_client = GmailClient(settings)

        gmail_client.service.users().stop(userId="me").execute()

        return {"success": True, "message": "Gmail watch stopped"}

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error stopping Gmail watch. Please try again.")


@router.get("/gmail/watch/status", response_model=WatchStatusResponse)
async def get_gmail_watch_status(
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user)
):
    """Get current Gmail watch status."""
    try:
        gmail_client = GmailClient(settings)

        # Try to get watch status (will fail if no active watch)
        try:
            profile = gmail_client.service.users().getProfile(userId="me").execute()

            # Check if watch is active
            return WatchStatusResponse(
                active=True,
                history_id=profile.get("historyId"),
            )

        except Exception:
            # Gmail API returns error if no watch is active - this is expected
            return WatchStatusResponse(active=False)

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error getting watch status. Please try again.")


# ============================================================================
# ANALYTICS ENDPOINTS
# ============================================================================

@router.get("/stats/today")
async def get_today_stats(
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user)
):
    """Get today's email processing statistics."""
    try:
        analytics = Analytics(settings.DATABASE_PATH)
        stats = analytics.get_daily_stats()

        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching stats. Please try again.")


@router.get("/stats/weekly")
async def get_weekly_stats(
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user)
):
    """Get last 7 days of email processing statistics."""
    try:
        analytics = Analytics(settings.DATABASE_PATH)
        stats = analytics.get_weekly_stats()

        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching weekly stats. Please try again.")


@router.get("/stats/top-labels")
async def get_top_labels(
    days: int = 7,
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user)
):
    """Get most common email categories."""
    try:
        analytics = Analytics(settings.DATABASE_PATH)
        labels = analytics.get_top_labels(days=days)

        return {"labels": labels}

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching labels. Please try again.")


@router.get("/stats/costs")
async def get_ai_costs(
    days: int = 30,
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user)
):
    """Get AI usage cost breakdown."""
    try:
        analytics = Analytics(settings.DATABASE_PATH)
        costs = analytics.get_cost_breakdown(days=days)

        return costs

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching costs. Please try again.")


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def health_check(settings: Settings = Depends(get_settings)):
    """Health check for email automation system."""
    status = {
        "status": "healthy",
        "gmail_configured": bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
        "ai_configured": {
            "claude": bool(settings.CLAUDE_API_KEY),
            "openai": bool(settings.OPENAI_API_KEY),
        },
        "shopify_configured": bool(settings.SHOPIFY_STORE and settings.SHOPIFY_API_TOKEN),
        "pubsub_configured": bool(settings.GOOGLE_CLOUD_PROJECT_ID and settings.GMAIL_PUBSUB_TOPIC),
    }

    return status
