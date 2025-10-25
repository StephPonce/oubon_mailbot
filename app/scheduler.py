"""Background scheduler for automatic email checking and follow-ups."""
import json
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from app.email_processor import EmailProcessor
from app.settings import get_settings
from app.business_hours import BusinessHours
from app.models import EmailFollowup, get_followup_session
from app.gmail_client import GmailClient
from app.ai_client import AIClient


def check_emails_job():
    """Job that checks Gmail and processes new emails."""
    print(f"🕐 [{datetime.now()}] Running scheduled email check...")

    try:
        settings = get_settings()
        processor = EmailProcessor(settings)

        # Load rules and templates
        with open("data/rules.json", "r") as f:
            rules = json.load(f)

        with open("data/templates.json", "r") as f:
            templates = json.load(f)

        # Process inbox
        result = processor.process_inbox(
            auto_reply=True,
            max_messages=25,
            rules=rules,
            templates=templates,
        )

        print(f"✅ Processed {result['processed']} emails, replied to {result['replied']}")

        # Also check for follow-ups to send
        process_followups_job()

    except Exception as e:
        print(f"❌ Error in scheduled email check: {e}")
        import traceback
        traceback.print_exc()


def process_followups_job():
    """Send AI follow-ups to emails that received templates during quiet hours."""
    try:
        settings = get_settings()

        # Check if we're in operating hours
        business_hours = BusinessHours(
            weekday_start=datetime.strptime("07:00", "%H:%M").time(),
            weekday_end=datetime.strptime("21:00", "%H:%M").time(),
            weekend_start=datetime.strptime("10:00", "%H:%M").time(),
            weekend_end=datetime.strptime("19:00", "%H:%M").time(),
            timezone="America/New_York",
        )

        response_mode = business_hours.get_response_mode()

        # Only send AI follow-ups during operating hours
        if response_mode != "ai":
            return

        print(f"🤖 [{datetime.now()}] Checking for follow-ups to send...")

        # Get emails that need follow-up
        session = get_followup_session(settings.database_url)
        pending_followups = session.query(EmailFollowup).filter_by(
            needs_followup=True,
            followup_sent=False
        ).all()

        if not pending_followups:
            session.close()
            return

        print(f"📧 Found {len(pending_followups)} emails needing AI follow-up")

        # Initialize clients
        gmail_client = GmailClient(settings)
        ai_client = AIClient(settings)

        sent_count = 0

        for followup in pending_followups:
            try:
                # Generate AI response
                ai_response = ai_client.draft_reply(
                    subject=followup.subject,
                    body=followup.body
                )

                # Send the AI follow-up
                gmail_client.send_simple_email(
                    to=followup.customer_email,
                    subject=f"Re: {followup.subject}",
                    body=ai_response,
                )

                # Mark as sent
                followup.followup_sent = True
                followup.followup_sent_at = datetime.utcnow()
                session.commit()

                sent_count += 1
                print(f"✅ Sent AI follow-up to: {followup.customer_email}")

            except Exception as e:
                print(f"❌ Error sending follow-up to {followup.customer_email}: {e}")

        session.close()

        if sent_count > 0:
            print(f"✅ Sent {sent_count} AI follow-ups")

    except Exception as e:
        print(f"❌ Error in follow-up processing: {e}")
        import traceback
        traceback.print_exc()


def start_scheduler():
    """Start the background scheduler for email checking."""
    scheduler = BackgroundScheduler()

    # Run every 5 minutes
    scheduler.add_job(
        check_emails_job,
        'interval',
        minutes=5,
        id='email_check',
        replace_existing=True
    )

    scheduler.start()
    print("✅ Email checker scheduler started (runs every 5 minutes)")

    return scheduler
