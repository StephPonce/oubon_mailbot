"""
Email OAuth API Routes

FastAPI endpoints for multi-provider email OAuth flow and account management.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel
import secrets
from datetime import datetime

from .gmail_oauth import GmailOAuthHandler
from .outlook_oauth import OutlookOAuthHandler
from .icloud_oauth import iCloudOAuthHandler
from .imap_smtp_handler import IMAPSMTPHandler
from ospra_os.database.multi_store_models import UserEmailAccount, Email, get_multi_store_session


router = APIRouter(prefix="/api/email-oauth", tags=["Email OAuth"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class EmailAccountResponse(BaseModel):
    """Email account information"""
    id: int
    provider: str
    email_address: str
    is_active: bool
    is_primary: bool
    last_synced: Optional[str]
    sync_status: str
    created_at: str


class OAuthUrlResponse(BaseModel):
    """OAuth authorization URL response"""
    authorization_url: str
    state: str


class IMAPSMTPCredentials(BaseModel):
    """IMAP/SMTP credentials for direct email access"""
    email: str
    password: str  # App-specific password recommended
    preset: str = "custom"  # icloud, yahoo, zoho, protonmail, custom
    imap_host: Optional[str] = None
    imap_port: Optional[int] = 993
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = 587


# ============================================================================
# OAUTH HANDLERS
# ============================================================================

def get_oauth_handler(provider: str):
    """
    Get OAuth handler for specified provider.

    Args:
        provider: Email provider ('gmail', 'outlook', 'icloud', 'yahoo', 'zoho', 'protonmail', 'custom')

    Returns:
        EmailOAuthHandler instance

    Raises:
        HTTPException: If provider is unsupported
    """
    handlers = {
        'gmail': GmailOAuthHandler,
        'outlook': OutlookOAuthHandler,
        'icloud': IMAPSMTPHandler,  # iCloud uses IMAP/SMTP with app password
        'yahoo': IMAPSMTPHandler,   # Yahoo uses IMAP/SMTP
        'zoho': IMAPSMTPHandler,    # Zoho uses IMAP/SMTP
        'protonmail': IMAPSMTPHandler,  # ProtonMail Bridge
        'custom': IMAPSMTPHandler,  # Custom IMAP/SMTP server
    }

    handler_class = handlers.get(provider.lower())
    if not handler_class:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported email provider: {provider}. Supported: {', '.join(handlers.keys())}"
        )

    try:
        return handler_class()
    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail=f"OAuth configuration error for {provider}: {str(e)}"
        )


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/{provider}/connect", response_model=OAuthUrlResponse)
async def connect_email_provider(
    provider: str,
    user_id: int = Query(..., description="User ID connecting email account")
):
    """
    Start OAuth flow for email provider.

    Generates authorization URL for user to grant email access.

    Example:
        GET /api/email-oauth/gmail/connect?user_id=1

    Returns:
        Authorization URL and state parameter for OAuth flow
    """
    handler = get_oauth_handler(provider)

    # Generate CSRF state token
    state = secrets.token_urlsafe(32)

    # TODO: Store state in session/cache with user_id for verification
    # For now, encode user_id in state (production should use secure session)
    state_with_user = f"{user_id}:{state}"

    # OAuth redirect URI (must match configured redirect URI)
    redirect_uri = f"http://localhost:8001/api/email-oauth/{provider}/callback"

    try:
        authorization_url = await handler.get_authorization_url(state_with_user, redirect_uri)

        return OAuthUrlResponse(
            authorization_url=authorization_url,
            state=state_with_user
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate authorization URL: {str(e)}"
        )


@router.post("/{provider}/connect-imap")
async def connect_imap_smtp_provider(
    provider: str,
    credentials: IMAPSMTPCredentials,
    user_id: int = Query(..., description="User ID connecting email account")
):
    """
    Connect IMAP/SMTP email provider (iCloud, Yahoo, Zoho, custom).

    Use this for providers that don't support OAuth or where IMAP/SMTP is simpler.

    Example:
        POST /api/email-oauth/icloud/connect-imap?user_id=1
        {
            "email": "user@icloud.com",
            "password": "app-specific-password",
            "preset": "icloud"
        }

    Returns:
        Success message and email account details
    """
    handler = IMAPSMTPHandler()

    # Get preset configuration if using preset
    if credentials.preset != "custom":
        preset = IMAPSMTPHandler.get_preset(credentials.preset)
        credentials.imap_host = preset["imap_host"]
        credentials.imap_port = preset["imap_port"]
        credentials.smtp_host = preset["smtp_host"]
        credentials.smtp_port = preset["smtp_port"]

    # Build credentials dict
    creds_dict = {
        "email": credentials.email,
        "password": credentials.password,
        "imap_host": credentials.imap_host,
        "imap_port": credentials.imap_port,
        "smtp_host": credentials.smtp_host,
        "smtp_port": credentials.smtp_port
    }

    try:
        # Exchange (test connection and get tokens)
        import json
        tokens = await handler.exchange_code_for_token(json.dumps(creds_dict), "")

        # Encrypt credentials
        encrypted_credentials = handler.encrypt_credentials(tokens)

        # Save to database
        session = get_multi_store_session()

        try:
            # Check if account already exists
            existing = session.query(UserEmailAccount).filter(
                UserEmailAccount.user_id == user_id,
                UserEmailAccount.provider == provider,
                UserEmailAccount.email_address == credentials.email
            ).first()

            if existing:
                # Update existing account
                existing.encrypted_credentials = encrypted_credentials
                existing.is_active = True
                existing.sync_status = 'active'
                existing.updated_at = datetime.utcnow()
                email_account = existing
            else:
                # Check if this is user's first email account (make it primary)
                account_count = session.query(UserEmailAccount).filter(
                    UserEmailAccount.user_id == user_id
                ).count()

                is_primary = (account_count == 0)

                # Create new account
                email_account = UserEmailAccount(
                    user_id=user_id,
                    provider=provider,
                    email_address=credentials.email,
                    encrypted_credentials=encrypted_credentials,
                    is_active=True,
                    is_primary=is_primary,
                    sync_status='active'
                )
                session.add(email_account)

            session.commit()
            session.refresh(email_account)

            return {
                'success': True,
                'message': f'Successfully connected {provider} account: {credentials.email}',
                'account': {
                    'id': email_account.id,
                    'provider': email_account.provider,
                    'email': email_account.email_address,
                    'is_primary': email_account.is_primary
                }
            }

        finally:
            session.close()

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect email account: {str(e)}"
        )


@router.get("/{provider}/callback")
async def email_oauth_callback(
    provider: str,
    code: str = Query(..., description="Authorization code from OAuth provider"),
    state: str = Query(..., description="CSRF state parameter")
):
    """
    Handle OAuth callback from email provider.

    Exchanges authorization code for access/refresh tokens and saves
    encrypted credentials to database.

    Example:
        GET /api/email-oauth/gmail/callback?code=AUTH_CODE&state=STATE_TOKEN

    Returns:
        Success message and email account details
    """
    handler = get_oauth_handler(provider)

    # Extract user_id from state (production should verify against session)
    try:
        user_id_str = state.split(':')[0]
        user_id = int(user_id_str)
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    # OAuth redirect URI (must match the one used in connect)
    redirect_uri = f"http://localhost:8001/api/email-oauth/{provider}/callback"

    try:
        # Exchange code for tokens
        tokens = await handler.exchange_code_for_token(code, redirect_uri)

        # Get user profile/email address
        profile = await handler.get_user_profile(tokens['access_token'])
        email_address = profile['email']

        # Encrypt credentials
        encrypted_credentials = handler.encrypt_credentials(tokens)

        # Save to database
        session = get_multi_store_session()

        try:
            # Check if account already exists
            existing = session.query(UserEmailAccount).filter(
                UserEmailAccount.user_id == user_id,
                UserEmailAccount.provider == provider,
                UserEmailAccount.email_address == email_address
            ).first()

            if existing:
                # Update existing account
                existing.encrypted_credentials = encrypted_credentials
                existing.is_active = True
                existing.sync_status = 'active'
                existing.updated_at = datetime.utcnow()
                email_account = existing
            else:
                # Check if this is user's first email account (make it primary)
                account_count = session.query(UserEmailAccount).filter(
                    UserEmailAccount.user_id == user_id
                ).count()

                is_primary = (account_count == 0)

                # Create new account
                email_account = UserEmailAccount(
                    user_id=user_id,
                    provider=provider,
                    email_address=email_address,
                    encrypted_credentials=encrypted_credentials,
                    is_active=True,
                    is_primary=is_primary,
                    sync_status='active'
                )
                session.add(email_account)

            session.commit()
            session.refresh(email_account)

            return {
                'success': True,
                'message': f'Successfully connected {provider} account: {email_address}',
                'account': {
                    'id': email_account.id,
                    'provider': email_account.provider,
                    'email': email_account.email_address,
                    'is_primary': email_account.is_primary
                }
            }

        finally:
            session.close()

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to complete OAuth flow: {str(e)}"
        )


@router.get("/accounts", response_model=List[EmailAccountResponse])
async def get_user_email_accounts(
    user_id: int = Query(..., description="User ID to fetch accounts for")
):
    """
    List all email accounts for a user.

    Example:
        GET /api/email-oauth/accounts?user_id=1

    Returns:
        List of connected email accounts
    """
    session = get_multi_store_session()

    try:
        accounts = session.query(UserEmailAccount).filter(
            UserEmailAccount.user_id == user_id
        ).order_by(
            UserEmailAccount.is_primary.desc(),
            UserEmailAccount.created_at.desc()
        ).all()

        return [EmailAccountResponse(
            id=acc.id,
            provider=acc.provider,
            email_address=acc.email_address,
            is_active=acc.is_active,
            is_primary=acc.is_primary,
            last_synced=acc.last_synced.isoformat() if acc.last_synced else None,
            sync_status=acc.sync_status,
            created_at=acc.created_at.isoformat()
        ) for acc in accounts]

    finally:
        session.close()


@router.delete("/accounts/{account_id}")
async def delete_email_account(
    account_id: int,
    user_id: int = Query(..., description="User ID (for authorization)")
):
    """
    Permanently delete an email account.

    Example:
        DELETE /api/email-oauth/accounts/123?user_id=1

    Returns:
        Success confirmation
    """
    session = get_multi_store_session()

    try:
        account = session.query(UserEmailAccount).filter(
            UserEmailAccount.id == account_id,
            UserEmailAccount.user_id == user_id
        ).first()

        if not account:
            raise HTTPException(status_code=404, detail="Email account not found")

        # Store account info for response message
        provider = account.provider
        email_address = account.email_address

        # If this was primary, assign another account as primary before deleting
        if account.is_primary:
            # Find another active account to make primary
            other_account = session.query(UserEmailAccount).filter(
                UserEmailAccount.user_id == user_id,
                UserEmailAccount.id != account_id
            ).first()

            if other_account:
                other_account.is_primary = True

        # Delete all associated emails first to avoid foreign key constraint error
        session.query(Email).filter(Email.email_account_id == account_id).delete(synchronize_session=False)

        # Permanently delete the account using raw SQL to avoid ORM cascade issues
        session.query(UserEmailAccount).filter(UserEmailAccount.id == account_id).delete(synchronize_session=False)
        session.commit()

        return {
            'success': True,
            'message': f'Permanently deleted {provider} account: {email_address}'
        }

    finally:
        session.close()


@router.post("/accounts/{account_id}/set-primary")
async def set_primary_email(
    account_id: int,
    user_id: int = Query(..., description="User ID (for authorization)")
):
    """
    Set an email account as primary.

    Example:
        POST /api/email-oauth/accounts/123/set-primary?user_id=1

    Returns:
        Success confirmation
    """
    session = get_multi_store_session()

    try:
        account = session.query(UserEmailAccount).filter(
            UserEmailAccount.id == account_id,
            UserEmailAccount.user_id == user_id,
            UserEmailAccount.is_active == True
        ).first()

        if not account:
            raise HTTPException(status_code=404, detail="Email account not found or inactive")

        # Unset primary on all other accounts
        session.query(UserEmailAccount).filter(
            UserEmailAccount.user_id == user_id,
            UserEmailAccount.id != account_id
        ).update({'is_primary': False})

        # Set this account as primary
        account.is_primary = True
        account.updated_at = datetime.utcnow()

        session.commit()

        return {
            'success': True,
            'message': f'Set {account.provider} account as primary: {account.email_address}'
        }

    finally:
        session.close()


@router.get("/providers/presets")
async def get_imap_smtp_presets():
    """
    Get preset IMAP/SMTP configurations for common email providers.

    Returns:
        Dict of provider presets with server settings
    """
    return IMAPSMTPHandler.PRESETS
