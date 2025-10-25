"""Background scheduler for automatic email checking."""
import json
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from app.email_processor import EmailProcessor
from app.settings import get_settings


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

    except Exception as e:
        print(f"❌ Error in scheduled email check: {e}")
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
