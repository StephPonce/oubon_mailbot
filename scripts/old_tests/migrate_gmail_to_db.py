#!/usr/bin/env python3
"""
Migration script to import existing Gmail tokens into the database.

This script reads the Gmail token from the file system and adds it to the
user_email_accounts table so it appears in the EmailSyncButton component.
"""

import os
import json
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from cryptography.fernet import Fernet

# Import database models
from ospra_os.database.multi_store_models import User, UserEmailAccount, get_multi_store_session

def migrate_gmail_token():
    """Migrate Gmail token from file to database"""

    # Get token path
    token_path = os.getenv("OUBONSHOP_GMAIL_TOKEN_PATH", "/data/gmail/token.json")

    if not os.path.exists(token_path):
        print(f"❌ No Gmail token found at {token_path}")
        print("   Gmail is not connected, or token is in a different location.")
        return False

    print(f"✅ Found Gmail token at {token_path}")

    # Load token
    try:
        with open(token_path, 'r') as f:
            token_data = json.load(f)
        print(f"✅ Loaded token data")
    except Exception as e:
        print(f"❌ Failed to load token: {e}")
        return False

    # Get Gmail email address
    try:
        creds = Credentials(
            token=token_data['token'],
            refresh_token=token_data.get('refresh_token'),
            token_uri=token_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
            client_id=token_data.get('client_id'),
            client_secret=token_data.get('client_secret'),
            scopes=token_data.get('scopes', [])
        )

        service = build('gmail', 'v1', credentials=creds)
        profile = service.users().getProfile(userId='me').execute()
        email_address = profile['emailAddress']
        print(f"✅ Gmail email: {email_address}")
    except Exception as e:
        print(f"❌ Failed to get Gmail email address: {e}")
        return False

    # Save to database
    session = get_multi_store_session()
    try:
        # Get or create user (default user_id=1)
        user = session.query(User).filter(User.id == 1).first()
        if not user:
            user = User(id=1, email=email_address, name="Default User", created_at=datetime.utcnow())
            session.add(user)
            session.commit()
            print(f"✅ Created user: {email_address}")
        else:
            print(f"✅ Using existing user: {user.email}")

        # Check if Gmail account already exists
        existing = session.query(UserEmailAccount).filter(
            UserEmailAccount.user_id == user.id,
            UserEmailAccount.provider == 'gmail',
            UserEmailAccount.email_address == email_address
        ).first()

        # Setup encryption
        encryption_key = os.getenv('EMAIL_OAUTH_ENCRYPTION_KEY')
        if not encryption_key:
            encryption_key = Fernet.generate_key().decode()
            print(f"⚠️  Generated new encryption key. Set EMAIL_OAUTH_ENCRYPTION_KEY={encryption_key}")

        fernet = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)

        # Prepare credentials dict
        creds_dict = {
            'access_token': token_data['token'],
            'refresh_token': token_data.get('refresh_token'),
            'token_uri': token_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
            'client_id': token_data.get('client_id'),
            'client_secret': token_data.get('client_secret'),
            'scopes': token_data.get('scopes', [])
        }
        encrypted_creds = fernet.encrypt(json.dumps(creds_dict).encode()).decode()

        if existing:
            print(f"⚠️  Gmail account already exists in database (ID: {existing.id})")
            print(f"   Updating credentials...")

            existing.encrypted_credentials = encrypted_creds
            existing.is_active = True
            existing.sync_status = 'active'
            session.commit()
            print(f"✅ Updated Gmail account in database")
        else:
            # Create new account record
            new_account = UserEmailAccount(
                user_id=user.id,
                provider='gmail',
                email_address=email_address,
                encrypted_credentials=encrypted_creds,
                is_active=True,
                is_primary=False,
                sync_status='active',
                created_at=datetime.utcnow()
            )
            session.add(new_account)
            session.commit()
            print(f"✅ Added Gmail account to database (ID: {new_account.id})")

        return True

    except Exception as e:
        session.rollback()
        print(f"❌ Database error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()

if __name__ == '__main__':
    print("=" * 60)
    print("Gmail Token Migration Script")
    print("=" * 60)
    print()

    success = migrate_gmail_token()

    print()
    if success:
        print("✅ Migration complete!")
        print("   Gmail account should now appear in the EmailSyncButton modal.")
        print("   Refresh your browser to see the changes.")
    else:
        print("❌ Migration failed.")
        print("   You may need to reconnect Gmail via OAuth.")
    print()
