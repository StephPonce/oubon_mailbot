#!/usr/bin/env python3
"""
🧪 LIVE EMAIL TEST - Ospra Intelligence

This script tests the full email automation pipeline with real Gmail:
1. Connects to Gmail via OAuth
2. Fetches recent unread emails
3. Classifies them using rule-based system
4. Generates AI responses using the model router
5. Optionally sends responses (requires confirmation)

Usage:
    python scripts/test_live_email.py
    python scripts/test_live_email.py --dry-run  # Don't send any emails
    python scripts/test_live_email.py --limit 5   # Process max 5 emails

Author: OspraOS
Date: December 2025
"""

import asyncio
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()


def print_header(text: str):
    """Print a styled header."""
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}\n")


def print_section(text: str):
    """Print a section divider."""
    print(f"\n{'─'*70}")
    print(f"  {text}")
    print(f"{'─'*70}")


async def test_gmail_connection():
    """Test Gmail OAuth connection."""
    print_section("📧 Testing Gmail Connection")
    
    try:
        from app.gmail_client import GmailClient
        from app.settings import Settings
        
        settings = Settings()
        client = GmailClient(settings)
        
        # Try to get profile
        service = client._service() if callable(getattr(client, '_service', None)) else client.service
        profile = service.users().getProfile(userId='me').execute()
        
        print(f"✅ Connected to Gmail!")
        print(f"   Email: {profile.get('emailAddress')}")
        print(f"   Messages: {profile.get('messagesTotal', 0):,}")
        print(f"   Threads: {profile.get('threadsTotal', 0):,}")
        
        return client, service
        
    except Exception as e:
        print(f"❌ Gmail connection failed: {e}")
        print("\n⚠️  Make sure you have:")
        print("   1. .secrets/gmail_client_secret.json")
        print("   2. .secrets/gmail_token.json (run OAuth flow first)")
        return None, None


async def fetch_unread_emails(service, limit: int = 10):
    """Fetch recent unread emails."""
    print_section(f"📬 Fetching Unread Emails (limit: {limit})")
    
    try:
        # Search for unread emails
        results = service.users().messages().list(
            userId='me',
            q='is:unread -from:noreply -from:no-reply',
            maxResults=limit
        ).execute()
        
        messages = results.get('messages', [])
        print(f"   Found {len(messages)} unread emails")
        
        emails = []
        for msg in messages:
            # Get full message
            full_msg = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='full'
            ).execute()
            
            # Extract headers
            headers = {h['name'].lower(): h['value'] for h in full_msg.get('payload', {}).get('headers', [])}
            
            # Extract body
            body = ""
            payload = full_msg.get('payload', {})
            if 'body' in payload and payload['body'].get('data'):
                import base64
                body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
            elif 'parts' in payload:
                for part in payload['parts']:
                    if part.get('mimeType') == 'text/plain' and part.get('body', {}).get('data'):
                        import base64
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                        break
            
            emails.append({
                'id': msg['id'],
                'thread_id': full_msg.get('threadId'),
                'from': headers.get('from', 'Unknown'),
                'subject': headers.get('subject', 'No Subject'),
                'body': body[:1000],  # Truncate
                'date': headers.get('date', ''),
                'snippet': full_msg.get('snippet', '')
            })
        
        return emails
        
    except Exception as e:
        print(f"❌ Failed to fetch emails: {e}")
        return []


async def process_emails(emails: list, dry_run: bool = True):
    """Process emails through the AI pipeline."""
    print_section("🤖 Processing with AI")
    
    try:
        from ospra_os.email_automation.ai_responder import EmailAutomationAI
        
        ai = EmailAutomationAI()
        results = []
        
        for i, email in enumerate(emails, 1):
            print(f"\n📧 Email {i}/{len(emails)}")
            print(f"   From: {email['from'][:50]}")
            print(f"   Subject: {email['subject'][:60]}")
            
            # Extract name from email
            from_addr = email['from']
            from_name = from_addr.split('<')[0].strip().strip('"') if '<' in from_addr else from_addr.split('@')[0]
            email_addr = from_addr.split('<')[1].rstrip('>') if '<' in from_addr else from_addr
            
            # Process through AI
            result = await ai.process_email(
                email_id=email['id'],
                from_address=email_addr,
                from_name=from_name,
                subject=email['subject'],
                body=email['body'],
                received_at=datetime.now()
            )
            
            results.append({
                'email': email,
                'result': result
            })
            
            # Print result
            if result.get('should_respond'):
                print(f"   ✅ Category: {result['category']}")
                print(f"   ⚡ Urgency: {result['urgency']}")
                print(f"   😊 Sentiment: {result['sentiment']}")
                if result.get('order_number'):
                    print(f"   🔢 Order: #{result['order_number']}")
                print(f"\n   📝 Generated Response:")
                print(f"   {'-'*60}")
                for line in result['response_text'].split('\n')[:8]:
                    print(f"   {line}")
                if len(result['response_text'].split('\n')) > 8:
                    print(f"   ... (truncated)")
                print(f"   {'-'*60}")
            else:
                print(f"   ⏭️  AUTO-IGNORED: {result.get('reason', 'N/A')}")
        
        return results
        
    except Exception as e:
        print(f"❌ Processing failed: {e}")
        import traceback
        traceback.print_exc()
        return []


async def send_responses(service, results: list, dry_run: bool = True):
    """Send AI-generated responses (with confirmation)."""
    print_section("📤 Sending Responses")
    
    if dry_run:
        print("   🔒 DRY RUN MODE - No emails will be sent")
        print("   Run without --dry-run to send emails")
        return
    
    responses_to_send = [r for r in results if r['result'].get('should_respond')]
    
    if not responses_to_send:
        print("   No responses to send")
        return
    
    print(f"   Found {len(responses_to_send)} emails to respond to")
    
    # Confirm before sending
    confirm = input("\n   ⚠️  Send these responses? (yes/no): ")
    if confirm.lower() != 'yes':
        print("   ❌ Cancelled")
        return
    
    # Send responses
    for r in responses_to_send:
        email = r['email']
        response = r['result']['response_text']
        
        try:
            import base64
            from email.mime.text import MIMEText
            
            message = MIMEText(response)
            message['to'] = email['from']
            message['subject'] = f"Re: {email['subject']}"
            
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            service.users().messages().send(
                userId='me',
                body={'raw': raw, 'threadId': email['thread_id']}
            ).execute()
            
            print(f"   ✅ Sent reply to: {email['from'][:40]}")
            
        except Exception as e:
            print(f"   ❌ Failed to send: {e}")


def print_summary(results: list):
    """Print test summary."""
    print_header("📊 TEST SUMMARY")
    
    total = len(results)
    responded = sum(1 for r in results if r['result'].get('should_respond'))
    ignored = total - responded
    
    categories = {}
    urgencies = {'low': 0, 'medium': 0, 'high': 0, 'critical': 0}
    
    for r in results:
        if r['result'].get('should_respond'):
            cat = r['result'].get('category', 'unknown')
            categories[cat] = categories.get(cat, 0) + 1
            
            urg = r['result'].get('urgency', 'medium')
            urgencies[urg] = urgencies.get(urg, 0) + 1
    
    print(f"   Total Emails Processed: {total}")
    print(f"   ✅ Responses Generated:  {responded}")
    print(f"   ⏭️  Auto-Ignored:         {ignored}")
    print()
    
    if categories:
        print("   📁 Categories:")
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            print(f"      {cat}: {count}")
        print()
    
    if any(urgencies.values()):
        print("   ⚡ Urgency Levels:")
        for urg, count in urgencies.items():
            if count > 0:
                emoji = {'low': '🟢', 'medium': '🟡', 'high': '🟠', 'critical': '🔴'}[urg]
                print(f"      {emoji} {urg}: {count}")


async def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description='Test Ospra Email Automation with Live Gmail')
    parser.add_argument('--dry-run', action='store_true', help="Don't send any emails")
    parser.add_argument('--limit', type=int, default=5, help='Max emails to process')
    args = parser.parse_args()
    
    print_header("🧪 OSPRA INTELLIGENCE - LIVE EMAIL TEST")
    print(f"   Mode: {'DRY RUN (safe)' if args.dry_run else '⚠️  LIVE (will send emails)'}")
    print(f"   Limit: {args.limit} emails")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Connect to Gmail
    client, service = await test_gmail_connection()
    if not service:
        print("\n❌ Cannot proceed without Gmail connection")
        return
    
    # Step 2: Fetch emails
    emails = await fetch_unread_emails(service, limit=args.limit)
    if not emails:
        print("\n✅ No unread emails to process!")
        return
    
    # Step 3: Process with AI
    results = await process_emails(emails, dry_run=args.dry_run)
    
    # Step 4: Send responses (if not dry run)
    if not args.dry_run and results:
        await send_responses(service, results, dry_run=args.dry_run)
    
    # Step 5: Summary
    if results:
        print_summary(results)
    
    print_header("✅ TEST COMPLETE")


if __name__ == "__main__":
    asyncio.run(main())
