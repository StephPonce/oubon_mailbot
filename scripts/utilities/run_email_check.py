#!/usr/bin/env python3
"""
Cron job script: Check Gmail and process new emails.
Runs every 5 minutes via Render Cron Job.
"""
import json
from datetime import datetime
from app.email_processor import EmailProcessor
from app.settings import get_settings


def main():
    """Check Gmail inbox and process new emails with smart replies."""
    print(f"[TIME] [{datetime.now()}] Starting email check...")

    try:
        # Initialize
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
            max_messages=25,  # Check last 25 emails
            rules=rules,
            templates=templates,
        )

        # Log results
        print(f"[SUCCESS] Processed: {result['processed']} emails")
        print(f"[EMAIL] Replied: {result['replied']} emails")
        print(f"  Labeled: {result['labeled']} emails")

        if result['replied'] > 0:
            print(" Replies sent:")
            for detail in result['details']:
                if detail.get('replied'):
                    print(f"   - {detail.get('from')}: {detail.get('subject')}")

        print(f"[SUCCESS] [{datetime.now()}] Email check complete!")

    except Exception as e:
        print(f"[ERROR] Error checking emails: {e}")
        import traceback
        traceback.print_exc()
        raise  # Re-raise so Render logs the error


if __name__ == "__main__":
    main()
