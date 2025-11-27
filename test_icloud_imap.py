#!/usr/bin/env python3
"""
iCloud IMAP Connection Diagnostic Tool

Tests iCloud IMAP connection and provides detailed error information.
"""

import imaplib
import ssl
import sys

def test_icloud_connection(email: str, password: str):
    """
    Test iCloud IMAP connection with detailed error reporting.

    Args:
        email: iCloud email address (e.g., user@icloud.com)
        password: App-specific password from appleid.apple.com
    """
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🔍 iCloud IMAP Connection Diagnostics")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()

    # Strip whitespace
    email = email.strip()
    password = password.strip()

    print(f"📧 Email: {email}")
    print(f"🔐 Password: {'*' * len(password)} ({len(password)} characters)")
    print(f"🖥️  IMAP Server: imap.mail.me.com:993")
    print()

    # Check email format
    if not email.endswith('@icloud.com') and not email.endswith('@me.com') and not email.endswith('@mac.com'):
        print("⚠️  WARNING: Email doesn't appear to be an iCloud email")
        print("   iCloud emails end with @icloud.com, @me.com, or @mac.com")
        print()

    # Check password length
    if len(password) < 16:
        print("⚠️  WARNING: Password seems short for an app-specific password")
        print("   iCloud app-specific passwords are usually 16+ characters")
        print("   Format: xxxx-xxxx-xxxx-xxxx")
        print()

    print("🔌 Testing connection...")
    print()

    try:
        # Create SSL context
        context = ssl.create_default_context()

        # Connect to iCloud IMAP
        print("  1️⃣  Creating SSL connection...")
        imap = imaplib.IMAP4_SSL("imap.mail.me.com", 993, ssl_context=context)
        print("     ✅ SSL connection established")
        print()

        # Attempt login
        print("  2️⃣  Attempting login...")
        imap.login(email, password)
        print("     ✅ Login successful!")
        print()

        # Get mailbox list
        print("  3️⃣  Fetching mailboxes...")
        status, folders = imap.list()
        if status == 'OK':
            print(f"     ✅ Found {len(folders)} mailboxes")
        print()

        # Select INBOX
        print("  4️⃣  Selecting INBOX...")
        status, messages = imap.select("INBOX")
        if status == 'OK':
            count = int(messages[0])
            print(f"     ✅ INBOX has {count} messages")
        print()

        # Logout
        imap.logout()

        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("✅ SUCCESS: iCloud IMAP connection working correctly!")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        return True

    except imaplib.IMAP4.error as e:
        error_msg = str(e)
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("❌ IMAP ERROR")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()
        print(f"Error: {error_msg}")
        print()

        if 'AUTHENTICATIONFAILED' in error_msg or 'Authentication Failed' in error_msg:
            print("🔍 DIAGNOSIS: Authentication Failed")
            print()
            print("Common causes:")
            print()
            print("1️⃣  Using regular password instead of app-specific password")
            print("   → iCloud requires app-specific passwords for IMAP access")
            print("   → Generate one at: https://appleid.apple.com")
            print()
            print("2️⃣  App-specific password is incorrect or expired")
            print("   → Double-check the password you generated")
            print("   → Try generating a new one")
            print()
            print("3️⃣  Two-Factor Authentication (2FA) not enabled")
            print("   → iCloud requires 2FA to be enabled")
            print("   → Enable at: https://appleid.apple.com/account/manage")
            print()
            print("4️⃣  Whitespace in email or password")
            print("   → Make sure there are no spaces before/after")
            print("   → Copy-paste carefully")
            print()
            print("📚 HOW TO GENERATE APP-SPECIFIC PASSWORD:")
            print("   1. Go to https://appleid.apple.com")
            print("   2. Sign in with your Apple ID")
            print("   3. Go to 'Security' section")
            print("   4. Click 'Generate Password' under App-Specific Passwords")
            print("   5. Enter a label (e.g., 'Ospra OS Email')")
            print("   6. Copy the 16-character password (format: xxxx-xxxx-xxxx-xxxx)")
            print("   7. Use this password (without dashes) in the login form")
            print()

        elif 'UNAVAILABLE' in error_msg:
            print("🔍 DIAGNOSIS: Server Unavailable")
            print()
            print("   → iCloud IMAP server might be down")
            print("   → Check your internet connection")
            print("   → Try again in a few minutes")
            print()

        return False

    except ssl.SSLError as e:
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("❌ SSL ERROR")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()
        print(f"Error: {str(e)}")
        print()
        print("   → Check your internet connection")
        print("   → Firewall might be blocking port 993")
        print()
        return False

    except Exception as e:
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("❌ UNEXPECTED ERROR")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()
        print(f"Error: {str(e)}")
        print(f"Type: {type(e).__name__}")
        print()
        return False


if __name__ == "__main__":
    print()
    if len(sys.argv) == 3:
        email = sys.argv[1]
        password = sys.argv[2]
        test_icloud_connection(email, password)
    else:
        print("Usage: python3 test_icloud_imap.py <email> <app-specific-password>")
        print()
        print("Example:")
        print("  python3 test_icloud_imap.py user@icloud.com xxxx-xxxx-xxxx-xxxx")
        print()
        print("⚠️  DO NOT commit your password to git!")
        print()
