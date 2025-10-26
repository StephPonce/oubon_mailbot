"""Email processor that integrates smart reply system with Gmail."""
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.smart_reply import SmartReplySystem
from app.gmail_client import GmailClient
from ospra_os.core.settings import Settings  # Use ospra_os settings for Render compatibility
from app.models import EmailFollowup, get_followup_session
from app.analytics import Analytics
import base64
import re
import time


class EmailProcessor:
    """Process emails with smart auto-replies."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.gmail_client = GmailClient(settings)
        self.smart_reply = SmartReplySystem(settings)
        self.analytics = Analytics(settings.database_url)

    def process_inbox(
        self,
        auto_reply: bool = True,
        max_messages: int = 25,
        rules: Dict[str, Any] = None,
        templates: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Process inbox with smart auto-replies.

        Args:
            auto_reply: Whether to send automatic replies
            max_messages: Maximum messages to process
            rules: Classification rules
            templates: Email templates

        Returns:
            {
                "processed": int,
                "labeled": int,
                "replied": int,
                "details": list,
            }
        """
        svc = self.gmail_client.service()

        # Query for relevant messages
        query = (
            'in:inbox (is:unread OR "order" OR "package" OR "delivery" OR "tracking" '
            'OR "shipment" OR "refund" OR "return" OR "damaged" OR "broken")'
        )

        result = svc.users().messages().list(
            userId="me",
            q=query,
            maxResults=max_messages
        ).execute()

        messages = result.get("messages", [])
        if not messages:
            return {
                "processed": 0,
                "labeled": 0,
                "replied": 0,
                "details": [],
            }

        # Get Gmail labels
        labels_response = svc.users().labels().list(userId="me").execute()
        existing_labels = {l["name"]: l["id"] for l in labels_response.get("labels", [])}

        processed = 0
        labeled = 0
        replied = 0
        details = []

        for msg in messages:
            try:
                detail = self._process_single_message(
                    svc,
                    msg["id"],
                    rules,
                    templates,
                    existing_labels,
                    auto_reply,
                )
                if detail:
                    details.append(detail)
                    processed += 1
                    if detail.get("labeled"):
                        labeled += 1
                    if detail.get("replied"):
                        replied += 1
            except Exception as e:
                print(f"Error processing message {msg['id']}: {e}")
                details.append({
                    "message_id": msg["id"],
                    "error": str(e),
                })

        return {
            "processed": processed,
            "labeled": labeled,
            "replied": replied,
            "details": details,
        }

    def _process_single_message(
        self,
        svc,
        message_id: str,
        rules: Dict[str, Any],
        templates: Dict[str, Any],
        existing_labels: Dict[str, str],
        auto_reply: bool,
    ) -> Optional[Dict[str, Any]]:
        """Process a single email message."""
        # Get full message
        full_msg = svc.users().messages().get(
            userId="me",
            id=message_id,
            format="full"
        ).execute()

        # Extract headers
        headers = {
            h["name"].lower(): h["value"]
            for h in full_msg.get("payload", {}).get("headers", [])
        }

        subject = headers.get("subject", "")
        from_header = headers.get("from", "")
        body = self._extract_body(full_msg)

        # Extract sender info
        from_email = self._extract_email(from_header)
        from_name = self._extract_name(from_header)

        # Classify message
        matched_rule = self._match_rule(subject, body, rules)

        if not matched_rule:
            return {
                "message_id": message_id,
                "subject": subject,
                "from": from_email,
                "matched_rule": None,
                "labeled": False,
                "replied": False,
            }

        # Apply label
        label_name = matched_rule.get("apply_label", "")
        label_id = self._ensure_label(svc, label_name, existing_labels)

        if label_id:
            svc.users().messages().modify(
                userId="me",
                id=message_id,
                body={"addLabelIds": [label_id]}
            ).execute()
            labeled = True
        else:
            labeled = False

        # Check for duplicate reply prevention
        # Don't reply twice UNLESS first reply was a quiet hours template
        auto_replied_label = self.settings.LABEL_AUTO_REPLIED
        auto_replied_label_id = existing_labels.get(auto_replied_label)

        already_replied = auto_replied_label_id and auto_replied_label_id in full_msg.get("labelIds", [])

        can_reply = True
        if already_replied:
            # Check if we need a follow-up (previous reply was template during quiet hours)
            session = get_followup_session(self.settings.database_url)
            followup = session.query(EmailFollowup).filter_by(
                message_id=message_id,
                needs_followup=True,
                followup_sent=False
            ).first()
            session.close()

            # Only allow reply if this is a follow-up to a quiet hours template
            can_reply = followup is not None

            if not can_reply:
                print(f"⏭️  Skipping reply to {message_id} - already replied (not a follow-up)")

        # Generate and send reply if enabled
        replied = False
        reply_metadata = {}

        if auto_reply and matched_rule.get("auto_reply") and can_reply:
            reply = self.smart_reply.generate_reply(
                subject=subject,
                body=body,
                from_email=from_email,
                from_name=from_name,
                rule=matched_rule,
                templates=templates,
            )

            if reply:
                try:
                    self.gmail_client.send_simple_email(
                        to=from_email,
                        subject=reply["subject"],
                        body=reply["body"],
                    )
                    replied = True
                    reply_metadata = reply.get("metadata", {})

                    # Add "Auto Replied" label
                    auto_replied_label_id = self._ensure_label(svc, self.settings.LABEL_AUTO_REPLIED, existing_labels)
                    if auto_replied_label_id:
                        svc.users().messages().modify(
                            userId="me",
                            id=message_id,
                            body={"addLabelIds": [auto_replied_label_id]}
                        ).execute()

                    # Track analytics
                    response_mode = "ai" if reply_metadata.get("used_ai") else "template"
                    self.analytics.track_email(
                        message_id=message_id,
                        customer_email=from_email,
                        subject=subject,
                        label=label_name,
                        response_mode=response_mode,
                        ai_provider=reply_metadata.get("ai_provider"),
                        processing_time_ms=reply_metadata.get("processing_time_ms", 0),
                        tokens_used=reply_metadata.get("tokens_used", 0),
                        estimated_cost=reply_metadata.get("estimated_cost", 0.0),
                        auto_reply_sent=True,
                        auto_refund_processed=reply_metadata.get("auto_refund_processed", False),
                        shopify_lookup=reply_metadata.get("shopify_lookup", False),
                        followup_needed=(reply_metadata.get("response_mode") == "template"),
                        success=True,
                    )

                    # If this was a template response during quiet hours, save for follow-up
                    if reply_metadata.get("response_mode") == "template":
                        self._save_for_followup(
                            message_id=message_id,
                            from_email=from_email,
                            from_name=from_name,
                            subject=subject,
                            body=body,
                            label=label_name,
                        )

                except Exception as e:
                    print(f"Error sending reply: {e}")
                    # Track failed email
                    self.analytics.track_email(
                        message_id=message_id,
                        customer_email=from_email,
                        subject=subject,
                        label=label_name,
                        response_mode="template",
                        success=False,
                        error_message=str(e),
                    )

        return {
            "message_id": message_id,
            "subject": subject,
            "from": from_email,
            "from_name": from_name,
            "matched_rule": label_name,
            "labeled": labeled,
            "replied": replied,
            "reply_metadata": reply_metadata,
        }

    def _extract_body(self, message: Dict[str, Any]) -> str:
        """Extract text from email body."""
        payload = message.get("payload", {})
        parts = payload.get("parts", [])

        if not parts:
            # Simple message with no parts
            body_data = payload.get("body", {}).get("data", "")
            if body_data:
                return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")
            return message.get("snippet", "")

        # Multi-part message
        chunks = []
        for part in parts:
            if part.get("mimeType") == "text/plain":
                body_data = part.get("body", {}).get("data")
                if body_data:
                    chunks.append(
                        base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")
                    )

        return "\n".join(chunks) if chunks else message.get("snippet", "")

    def _extract_email(self, from_header: str) -> str:
        """Extract email address from From header."""
        match = re.search(r"<([^>]+)>", from_header)
        if match:
            return match.group(1)
        return from_header.strip()

    def _extract_name(self, from_header: str) -> str:
        """Extract name from From header."""
        match = re.match(r'^\s*"?(?P<name>[^"<]+?)"?\s*<', from_header)
        if match:
            name = match.group("name").strip()
            if name:
                return name
        return ""

    def _match_rule(
        self,
        subject: str,
        body: str,
        rules: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Match email against classification rules."""
        if not rules:
            return None

        text = f"{subject}\n{body}".lower()

        for rule in rules.get("rules", []):
            keywords = rule.get("if_any", [])
            for keyword in keywords:
                if keyword.lower() in text:
                    return rule

        return None

    def _ensure_label(
        self,
        svc,
        label_name: str,
        existing_labels: Dict[str, str]
    ) -> Optional[str]:
        """Ensure Gmail label exists, create if needed."""
        if not label_name:
            return None

        if label_name in existing_labels:
            return existing_labels[label_name]

        # Create new label
        try:
            created = svc.users().labels().create(
                userId="me",
                body={
                    "name": label_name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                }
            ).execute()

            label_id = created["id"]
            existing_labels[label_name] = label_id
            return label_id
        except Exception as e:
            print(f"Error creating label {label_name}: {e}")
            return None

    def _save_for_followup(
        self,
        message_id: str,
        from_email: str,
        from_name: str,
        subject: str,
        body: str,
        label: str,
    ):
        """Save email to database for AI follow-up during operating hours."""
        try:
            session = get_followup_session(self.settings.database_url)

            # Check if already exists
            existing = session.query(EmailFollowup).filter_by(
                gmail_message_id=message_id
            ).first()

            if existing:
                # Update existing record
                existing.needs_followup = True
                existing.template_sent_at = datetime.utcnow()
            else:
                # Create new record
                followup = EmailFollowup(
                    gmail_message_id=message_id,
                    customer_email=from_email,
                    customer_name=from_name,
                    subject=subject,
                    body=body,
                    label=label,
                    needs_followup=True,
                    followup_sent=False,
                    received_at=datetime.utcnow(),
                    template_sent_at=datetime.utcnow(),
                )
                session.add(followup)

            session.commit()
            session.close()

            print(f"📝 Saved for follow-up: {from_email} - {subject}")

        except Exception as e:
            print(f"❌ Error saving for follow-up: {e}")
            import traceback
            traceback.print_exc()
