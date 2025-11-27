"""
Email Sync API Routes

FastAPI endpoints for syncing and fetching emails from connected accounts.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from ospra_os.email_automation.email_sync import EmailSyncService
from ospra_os.email_automation.email_action_executor import EmailActionExecutor
from ospra_os.database.multi_store_models import Email, UserEmailAccount, get_multi_store_session


router = APIRouter(prefix="/api/emails", tags=["Email Sync"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class EmailResponse(BaseModel):
    """Email response model"""
    id: int
    from_address: str
    from_name: Optional[str]
    subject: Optional[str]
    snippet: Optional[str]
    received_at: str
    is_read: bool
    is_starred: bool
    is_important: bool
    has_attachments: bool
    labels: Optional[List[str]]

    class Config:
        from_attributes = True


class EmailDetailResponse(BaseModel):
    """Detailed email response with body"""
    id: int
    from_address: str
    from_name: Optional[str]
    to_addresses: Optional[List[str]]
    subject: Optional[str]
    body_plain: Optional[str]
    body_html: Optional[str]
    snippet: Optional[str]
    received_at: str
    is_read: bool
    is_starred: bool
    is_important: bool
    has_attachments: bool
    labels: Optional[List[str]]
    provider: str
    email_account_email: str

    class Config:
        from_attributes = True


class SyncResponse(BaseModel):
    """Sync operation response"""
    success: bool
    emails_synced: int
    provider: Optional[str]
    message: Optional[str]
    error: Optional[str]


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.post("/sync")
async def sync_emails(
    user_id: int = Query(..., description="User ID"),
    account_id: Optional[int] = Query(None, description="Specific account ID to sync (optional)"),
    max_emails: int = Query(500, ge=1, le=5000, description="Max emails to fetch per account"),
    days_back: int = Query(365, ge=1, le=3650, description="How many days back to fetch (default: 1 year, max: 10 years)")
):
    """
    Sync emails from connected email accounts.

    If account_id is provided, sync only that account.
    Otherwise, sync all active accounts for the user.

    Example:
        POST /api/emails/sync?user_id=1
        POST /api/emails/sync?user_id=1&account_id=5&max_emails=100

    Returns:
        Sync results for each account
    """
    sync_service = EmailSyncService()
    session = get_multi_store_session()

    try:
        # Get accounts to sync
        if account_id:
            accounts = session.query(UserEmailAccount).filter(
                UserEmailAccount.id == account_id,
                UserEmailAccount.user_id == user_id,
                UserEmailAccount.is_active == True
            ).all()
        else:
            accounts = session.query(UserEmailAccount).filter(
                UserEmailAccount.user_id == user_id,
                UserEmailAccount.is_active == True
            ).all()

        if not accounts:
            return {
                'success': False,
                'error': 'No active email accounts found'
            }

        results = []

        for account in accounts:
            result = await sync_service.sync_account(
                account_id=account.id,
                max_emails=max_emails,
                days_back=days_back
            )

            results.append({
                'account_id': account.id,
                'email_address': account.email_address,
                'provider': account.provider,
                **result
            })

        total_synced = sum(r.get('emails_synced', 0) for r in results)

        return {
            'success': True,
            'total_emails_synced': total_synced,
            'accounts_synced': len(results),
            'results': results
        }

    finally:
        session.close()


@router.get("/list", response_model=List[EmailResponse])
async def list_emails(
    user_id: int = Query(..., description="User ID"),
    account_id: Optional[int] = Query(None, description="Filter by account ID"),
    label: Optional[str] = Query(None, description="Filter by label (e.g., INBOX, SENT, TRASH)"),
    limit: int = Query(50, ge=1, le=200, description="Number of emails to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    unread_only: bool = Query(False, description="Show only unread emails"),
    group_threads: bool = Query(True, description="Group by thread (Gmail-style)")
):
    """
    List emails for a user.

    Example:
        GET /api/emails/list?user_id=1&limit=50
        GET /api/emails/list?user_id=1&account_id=5&unread_only=true
        GET /api/emails/list?user_id=1&label=INBOX

    Returns:
        List of emails ordered by received date (newest first).
        By default, groups conversation threads (like Gmail) to show only the
        most recent email from each thread.
    """
    session = get_multi_store_session()

    try:
        query = session.query(Email).filter(Email.user_id == user_id)

        if account_id:
            query = query.filter(Email.email_account_id == account_id)

        if unread_only:
            query = query.filter(Email.is_read == False)

        query = query.order_by(Email.received_at.desc())

        emails = query.all()

        # Filter by label if specified
        if label:
            import json
            filtered_emails = []
            for email in emails:
                email_labels = (
                    email.labels if isinstance(email.labels, list)
                    else json.loads(email.labels) if isinstance(email.labels, str) and email.labels
                    else []
                )
                if label in email_labels:
                    filtered_emails.append(email)
            emails = filtered_emails

        # Group by thread_id (Gmail-style conversation view)
        if group_threads:
            thread_map = {}
            for email in emails:
                thread_id = email.thread_id or email.message_id
                if thread_id not in thread_map:
                    thread_map[thread_id] = email
                else:
                    # Keep the most recent email from each thread
                    if email.received_at > thread_map[thread_id].received_at:
                        thread_map[thread_id] = email

            # Get unique thread emails, sort by date, and apply pagination
            emails = sorted(thread_map.values(), key=lambda x: x.received_at, reverse=True)
            emails = emails[offset:offset + limit]
        else:
            # No threading, just use pagination
            emails = emails[offset:offset + limit]

        # Convert to response models
        import json
        return [
            EmailResponse(
                id=email.id,
                from_address=email.from_address,
                from_name=email.from_name,
                subject=email.subject,
                snippet=email.snippet,
                received_at=email.received_at.isoformat(),
                is_read=email.is_read,
                is_starred=email.is_starred,
                is_important=email.is_important,
                has_attachments=email.has_attachments,
                labels=(
                    email.labels if isinstance(email.labels, list)
                    else json.loads(email.labels) if isinstance(email.labels, str) and email.labels
                    else []
                )
            )
            for email in emails
        ]

    except Exception as e:
        # Return empty list on error - frontend will handle gracefully
        print(f"Error listing emails: {e}")
        return []
    finally:
        session.close()


@router.get("/{email_id}", response_model=EmailDetailResponse)
async def get_email_details(
    email_id: int,
    user_id: int = Query(..., description="User ID")
):
    """
    Get detailed email information including body.

    Example:
        GET /api/emails/123?user_id=1

    Returns:
        Full email details including body content
    """
    session = get_multi_store_session()

    try:
        email = session.query(Email).filter(
            Email.id == email_id,
            Email.user_id == user_id
        ).first()

        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        # Get account info
        account = session.query(UserEmailAccount).filter(
            UserEmailAccount.id == email.email_account_id
        ).first()

        import json

        return EmailDetailResponse(
            id=email.id,
            from_address=email.from_address,
            from_name=email.from_name,
            to_addresses=json.loads(email.to_addresses) if email.to_addresses else [],
            subject=email.subject,
            body_plain=email.body_plain,
            body_html=email.body_html,
            snippet=email.snippet,
            received_at=email.received_at.isoformat(),
            is_read=email.is_read,
            is_starred=email.is_starred,
            is_important=email.is_important,
            has_attachments=email.has_attachments,
            labels=(
                email.labels if isinstance(email.labels, list)
                else json.loads(email.labels) if isinstance(email.labels, str) and email.labels
                else []
            ),
            provider=account.provider if account else 'unknown',
            email_account_email=account.email_address if account else ''
        )

    finally:
        session.close()


@router.get("/stats/summary")
async def get_email_stats(
    user_id: int = Query(..., description="User ID"),
    group_threads: bool = Query(True, description="Count threads instead of individual emails")
):
    """
    Get email statistics for a user.

    Example:
        GET /api/emails/stats/summary?user_id=1

    Returns:
        Email counts and statistics.
        By default, counts unique conversation threads (like Gmail)
        instead of individual emails.
    """
    session = get_multi_store_session()

    try:
        all_emails = session.query(Email).filter(Email.user_id == user_id).all()

        # Group by thread if requested (Gmail-style)
        if group_threads:
            thread_map = {}
            for email in all_emails:
                thread_id = email.thread_id or email.message_id
                if thread_id not in thread_map:
                    thread_map[thread_id] = email
                else:
                    # Keep the most recent email from each thread
                    if email.received_at > thread_map[thread_id].received_at:
                        thread_map[thread_id] = email

            emails = list(thread_map.values())
        else:
            emails = all_emails

        # Count stats from grouped/ungrouped emails
        total = len(emails)
        unread = sum(1 for e in emails if not e.is_read)
        starred = sum(1 for e in emails if e.is_starred)
        important = sum(1 for e in emails if e.is_important)

        # Emails by account
        accounts = session.query(UserEmailAccount).filter(
            UserEmailAccount.user_id == user_id
        ).all()

        accounts_stats = []
        for account in accounts:
            account_emails = [e for e in all_emails if e.email_account_id == account.id]

            if group_threads:
                account_thread_map = {}
                for email in account_emails:
                    thread_id = email.thread_id or email.message_id
                    if thread_id not in account_thread_map:
                        account_thread_map[thread_id] = email
                    else:
                        if email.received_at > account_thread_map[thread_id].received_at:
                            account_thread_map[thread_id] = email
                account_emails = list(account_thread_map.values())

            account_total = len(account_emails)
            account_unread = sum(1 for e in account_emails if not e.is_read)

            accounts_stats.append({
                'account_id': account.id,
                'email_address': account.email_address,
                'provider': account.provider,
                'total_emails': account_total,
                'unread_emails': account_unread,
                'last_synced': account.last_synced.isoformat() if account.last_synced else None
            })

        return {
            'total_emails': total,
            'unread_emails': unread,
            'starred_emails': starred,
            'important_emails': important,
            'accounts': accounts_stats
        }

    except Exception as e:
        # Return empty stats on error - frontend will handle gracefully
        print(f"Error fetching email stats: {e}")
        return {
            'total_emails': 0,
            'unread_emails': 0,
            'starred_emails': 0,
            'important_emails': 0,
            'accounts': []
        }
    finally:
        session.close()


@router.post("/{email_id}/mark-read")
async def mark_email_read(
    email_id: int,
    user_id: int = Query(..., description="User ID"),
    is_read: bool = Query(True, description="Mark as read (true) or unread (false)")
):
    """
    Mark an email as read or unread.

    This will update both the local database AND sync with the parent email platform
    (Gmail, Outlook, or IMAP provider).

    Example:
        POST /api/emails/123/mark-read?user_id=1&is_read=true

    Returns:
        Success message with sync status
    """
    session = get_multi_store_session()

    try:
        email = session.query(Email).filter(
            Email.id == email_id,
            Email.user_id == user_id
        ).first()

        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        # Get the email account for syncing
        account = session.query(UserEmailAccount).filter(
            UserEmailAccount.id == email.email_account_id
        ).first()

        if not account:
            raise HTTPException(status_code=404, detail="Email account not found")

        # Update local database
        email.is_read = is_read
        session.commit()

        # Sync with parent platform
        executor = EmailActionExecutor()
        sync_result = await executor.execute_action(
            account=account,
            email=email,
            action='mark_read',
            is_read=is_read
        )

        return {
            'success': True,
            'email_id': email_id,
            'is_read': is_read,
            'synced_to_provider': sync_result.get('synced', False),
            'sync_error': sync_result.get('error')
        }

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/{email_id}/star")
async def star_email(
    email_id: int,
    user_id: int = Query(..., description="User ID"),
    is_starred: bool = Query(True, description="Star (true) or unstar (false)")
):
    """
    Star or unstar an email.

    This will update both the local database AND sync with the parent email platform
    (Gmail stars, Outlook flags, or IMAP flags).

    Example:
        POST /api/emails/123/star?user_id=1&is_starred=true

    Returns:
        Success message with sync status
    """
    session = get_multi_store_session()

    try:
        email = session.query(Email).filter(
            Email.id == email_id,
            Email.user_id == user_id
        ).first()

        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        # Get the email account for syncing
        account = session.query(UserEmailAccount).filter(
            UserEmailAccount.id == email.email_account_id
        ).first()

        if not account:
            raise HTTPException(status_code=404, detail="Email account not found")

        # Update local database
        email.is_starred = is_starred
        session.commit()

        # Sync with parent platform
        executor = EmailActionExecutor()
        sync_result = await executor.execute_action(
            account=account,
            email=email,
            action='star' if is_starred else 'unstar',
            is_starred=is_starred
        )

        return {
            'success': True,
            'email_id': email_id,
            'is_starred': is_starred,
            'synced_to_provider': sync_result.get('synced', False),
            'sync_error': sync_result.get('error')
        }

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete("/{email_id}")
async def delete_email(
    email_id: int,
    user_id: int = Query(..., description="User ID")
):
    """
    Delete an email.

    This will delete from both the local database AND the parent email platform
    (Gmail trash, Outlook delete, or IMAP delete).

    Example:
        DELETE /api/emails/123?user_id=1

    Returns:
        Success message with sync status
    """
    session = get_multi_store_session()

    try:
        email = session.query(Email).filter(
            Email.id == email_id,
            Email.user_id == user_id
        ).first()

        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        # Get the email account for syncing
        account = session.query(UserEmailAccount).filter(
            UserEmailAccount.id == email.email_account_id
        ).first()

        if not account:
            raise HTTPException(status_code=404, detail="Email account not found")

        # Sync deletion with parent platform BEFORE deleting from database
        executor = EmailActionExecutor()
        sync_result = await executor.execute_action(
            account=account,
            email=email,
            action='delete'
        )

        # Delete from local database
        session.delete(email)
        session.commit()

        return {
            'success': True,
            'email_id': email_id,
            'message': 'Email deleted from database and provider',
            'synced_to_provider': sync_result.get('synced', False),
            'sync_error': sync_result.get('error')
        }

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/{email_id}/archive")
async def archive_email(
    email_id: int,
    user_id: int = Query(..., description="User ID")
):
    """
    Archive an email.

    This will archive the email in both the local database AND the parent email platform
    (Gmail removes INBOX label, Outlook moves to Archive folder).

    Example:
        POST /api/emails/123/archive?user_id=1

    Returns:
        Success message with sync status
    """
    session = get_multi_store_session()

    try:
        email = session.query(Email).filter(
            Email.id == email_id,
            Email.user_id == user_id
        ).first()

        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        # Get the email account for syncing
        account = session.query(UserEmailAccount).filter(
            UserEmailAccount.id == email.email_account_id
        ).first()

        if not account:
            raise HTTPException(status_code=404, detail="Email account not found")

        # Sync archive action with parent platform
        executor = EmailActionExecutor()
        sync_result = await executor.execute_action(
            account=account,
            email=email,
            action='archive'
        )

        # Update local labels (remove INBOX if present)
        if email.labels:
            import json
            labels = json.loads(email.labels) if isinstance(email.labels, str) else email.labels
            if 'INBOX' in labels:
                labels.remove('INBOX')
                email.labels = json.dumps(labels)

        session.commit()

        return {
            'success': True,
            'email_id': email_id,
            'message': 'Email archived',
            'synced_to_provider': sync_result.get('synced', False),
            'sync_error': sync_result.get('error')
        }

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


class LabelRequest(BaseModel):
    """Request body for applying a label"""
    label_name: str


@router.post("/{email_id}/label")
async def apply_label_to_email(
    email_id: int,
    label_data: LabelRequest,
    user_id: int = Query(..., description="User ID")
):
    """
    Apply a label/category to an email.

    This will apply the label in both the local database AND the parent email platform
    (Gmail labels or Outlook categories).

    Example:
        POST /api/emails/123/label?user_id=1
        Body: {"label_name": "Important"}

    Returns:
        Success message with sync status
    """
    session = get_multi_store_session()

    try:
        email = session.query(Email).filter(
            Email.id == email_id,
            Email.user_id == user_id
        ).first()

        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        # Get the email account for syncing
        account = session.query(UserEmailAccount).filter(
            UserEmailAccount.id == email.email_account_id
        ).first()

        if not account:
            raise HTTPException(status_code=404, detail="Email account not found")

        # Sync label/category with parent platform
        executor = EmailActionExecutor()
        sync_result = await executor.execute_action(
            account=account,
            email=email,
            action='label',
            label_name=label_data.label_name
        )

        # Update local labels
        import json
        labels = json.loads(email.labels) if email.labels and isinstance(email.labels, str) else (email.labels or [])
        if label_data.label_name not in labels:
            labels.append(label_data.label_name)
            email.labels = json.dumps(labels)

        session.commit()

        return {
            'success': True,
            'email_id': email_id,
            'label': label_data.label_name,
            'message': f'Label "{label_data.label_name}" applied',
            'synced_to_provider': sync_result.get('synced', False),
            'sync_error': sync_result.get('error')
        }

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


class ReplyRequest(BaseModel):
    """Request body for replying to an email"""
    message: str


class ComposeRequest(BaseModel):
    """Request body for composing a new email"""
    to: str  # Comma-separated email addresses
    subject: str
    message: str
    cc: Optional[str] = None  # Comma-separated email addresses
    bcc: Optional[str] = None  # Comma-separated email addresses
    account_id: Optional[int] = None  # Which account to send from (optional, uses first account if not specified)


@router.post("/send")
async def send_composed_email(
    compose_data: ComposeRequest,
    user_id: int = Query(..., description="User ID")
):
    """
    Send a new composed email.

    Example:
        POST /api/emails/send?user_id=1
        Body: {
            "to": "recipient@example.com",
            "subject": "Hello",
            "message": "This is a test email",
            "cc": "cc@example.com",
            "bcc": "bcc@example.com",
            "account_id": 5
        }

    Returns:
        Success message
    """
    session = get_multi_store_session()

    try:
        # Parse email addresses
        to_addresses = [addr.strip() for addr in compose_data.to.split(',') if addr.strip()]
        cc_addresses = [addr.strip() for addr in compose_data.cc.split(',') if compose_data.cc and addr.strip()] if compose_data.cc else []
        bcc_addresses = [addr.strip() for addr in compose_data.bcc.split(',') if compose_data.bcc and addr.strip()] if compose_data.bcc else []

        if not to_addresses:
            raise HTTPException(status_code=400, detail="At least one recipient is required")

        # Get the account to send from
        if compose_data.account_id:
            account = session.query(UserEmailAccount).filter(
                UserEmailAccount.id == compose_data.account_id,
                UserEmailAccount.user_id == user_id,
                UserEmailAccount.is_active == True
            ).first()
        else:
            # Use first active account
            account = session.query(UserEmailAccount).filter(
                UserEmailAccount.user_id == user_id,
                UserEmailAccount.is_active == True
            ).first()

        if not account:
            raise HTTPException(status_code=404, detail="No active email account found")

        # Import email sending service
        from ospra_os.email_automation.email_sender import EmailSenderService

        # Send the email
        sender_service = EmailSenderService()
        result = await sender_service.send_compose(
            account=account,
            to_addresses=to_addresses,
            subject=compose_data.subject,
            body=compose_data.message,
            cc_addresses=cc_addresses if cc_addresses else None,
            bcc_addresses=bcc_addresses if bcc_addresses else None
        )

        if not result['success']:
            raise HTTPException(status_code=500, detail=result.get('error', 'Failed to send email'))

        return {
            'success': True,
            'message': 'Email sent successfully',
            'from': account.email_address,
            'to': to_addresses
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/{email_id}/reply")
async def reply_to_email(
    email_id: int,
    reply_data: ReplyRequest,
    user_id: int = Query(..., description="User ID")
):
    """
    Send a reply to an email.

    Example:
        POST /api/emails/123/reply?user_id=1
        Body: {"message": "Thank you for your email..."}

    Returns:
        Success message
    """
    session = get_multi_store_session()

    try:
        # Get the email
        email = session.query(Email).filter(
            Email.id == email_id,
            Email.user_id == user_id
        ).first()

        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        # Get the account
        account = session.query(UserEmailAccount).filter(
            UserEmailAccount.id == email.email_account_id
        ).first()

        if not account:
            raise HTTPException(status_code=404, detail="Email account not found")

        # Import email sending service
        from ospra_os.email_automation.email_sender import EmailSenderService

        # Send the reply
        sender_service = EmailSenderService()
        result = await sender_service.send_reply(
            account=account,
            original_email=email,
            reply_message=reply_data.message
        )

        if not result['success']:
            raise HTTPException(status_code=500, detail=result.get('error', 'Failed to send reply'))

        return {
            'success': True,
            'message': 'Reply sent successfully'
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
