"""
Email Automation Engine

This module processes incoming emails against user-defined automation rules
and executes actions automatically.
"""

import re
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from ospra_os.database.multi_store_models import (
    Email,
    EmailAutomationRule,
    EmailTemplate,
    UserEmailAccount,
    TriggerType,
    ActionType,
    get_multi_store_session
)
from ospra_os.email_automation.email_action_executor import EmailActionExecutor
from ospra_os.email_automation.email_sender import EmailSenderService


class AutomationEngine:
    """
    Automation engine that processes emails against rules and executes actions.
    """

    def __init__(self):
        self.action_executor = EmailActionExecutor()
        self.email_sender = EmailSenderService()


    async def process_email(self, email: Email, session: Session) -> Dict:
        """
        Process a single email against all active automation rules.

        Args:
            email: The email to process
            session: Database session

        Returns:
            Dict with processing results
        """
        # Get all active rules for this user, ordered by priority
        rules = session.query(EmailAutomationRule).filter(
            EmailAutomationRule.user_id == email.user_id,
            EmailAutomationRule.is_active == True
        ).order_by(EmailAutomationRule.priority.asc()).all()

        if not rules:
            return {
                'success': True,
                'rules_matched': 0,
                'actions_executed': 0,
                'message': 'No active rules to process'
            }

        matched_rules = []
        actions_executed = []

        # Check each rule for matches
        for rule in rules:
            if self._does_rule_match(email, rule):
                matched_rules.append(rule)

                # Execute the action
                action_result = await self._execute_rule_action(email, rule, session)

                if action_result['success']:
                    actions_executed.append({
                        'rule_id': rule.id,
                        'rule_name': rule.name,
                        'action': rule.action_type.value,
                        'result': action_result
                    })

                    # Update rule statistics
                    rule.times_triggered += 1
                    rule.last_triggered = datetime.utcnow()
                    session.commit()

        return {
            'success': True,
            'rules_matched': len(matched_rules),
            'actions_executed': len(actions_executed),
            'actions': actions_executed
        }


    def _does_rule_match(self, email: Email, rule: EmailAutomationRule) -> bool:
        """
        Check if an email matches a rule's trigger conditions.

        Args:
            email: The email to check
            rule: The automation rule

        Returns:
            True if the rule matches, False otherwise
        """
        trigger_value = rule.trigger_value.lower()

        if rule.trigger_type == TriggerType.KEYWORD:
            # Search for keyword in subject or body
            subject = (email.subject or '').lower()
            body = (email.body_plain or '').lower()

            # Support regex or simple contains
            if trigger_value.startswith('regex:'):
                pattern = trigger_value[6:]  # Remove 'regex:' prefix
                try:
                    return bool(re.search(pattern, subject, re.IGNORECASE) or
                               re.search(pattern, body, re.IGNORECASE))
                except re.error:
                    # Invalid regex, fall back to simple contains
                    return trigger_value[6:] in subject or trigger_value[6:] in body
            else:
                return trigger_value in subject or trigger_value in body

        elif rule.trigger_type == TriggerType.SENDER:
            # Check if sender email matches
            from_address = (email.from_address or '').lower()

            # Support wildcards like "@domain.com" or exact match
            if trigger_value.startswith('@'):
                # Match any email from this domain
                return from_address.endswith(trigger_value)
            else:
                # Exact match or contains
                return trigger_value in from_address

        elif rule.trigger_type == TriggerType.SUBJECT:
            # Check if subject matches
            subject = (email.subject or '').lower()

            # Support regex or simple contains
            if trigger_value.startswith('regex:'):
                pattern = trigger_value[6:]
                try:
                    return bool(re.search(pattern, subject, re.IGNORECASE))
                except re.error:
                    return trigger_value[6:] in subject
            else:
                return trigger_value in subject

        elif rule.trigger_type == TriggerType.LABEL:
            # Check if email has this label
            import json
            email_labels = []
            if email.labels:
                if isinstance(email.labels, str):
                    email_labels = json.loads(email.labels)
                else:
                    email_labels = email.labels

            return trigger_value.lower() in [label.lower() for label in email_labels]

        return False


    async def _execute_rule_action(
        self,
        email: Email,
        rule: EmailAutomationRule,
        session: Session
    ) -> Dict:
        """
        Execute the action specified by a rule.

        Args:
            email: The email to act on
            rule: The automation rule
            session: Database session

        Returns:
            Dict with action execution results
        """
        action_value = rule.action_value

        try:
            # Get the email account
            account = session.query(UserEmailAccount).filter(
                UserEmailAccount.id == email.email_account_id
            ).first()

            if not account:
                return {
                    'success': False,
                    'error': 'Email account not found'
                }

            if rule.action_type == ActionType.LABEL:
                # Apply label to email
                result = await self.action_executor.execute_action(
                    account=account,
                    email=email,
                    action='label',
                    label_name=action_value
                )

                # Update local database
                import json
                labels = json.loads(email.labels) if email.labels and isinstance(email.labels, str) else (email.labels or [])
                if action_value not in labels:
                    labels.append(action_value)
                    email.labels = json.dumps(labels)
                    session.commit()

                return result

            elif rule.action_type == ActionType.REPLY:
                # Send auto-reply using template
                template_id = None
                try:
                    template_id = int(action_value)
                except ValueError:
                    # action_value is raw message, not template ID
                    pass

                if template_id:
                    # Get template
                    from ospra_os.database import EmailTemplate
                    template = session.query(EmailTemplate).filter(
                        EmailTemplate.id == template_id,
                        EmailTemplate.user_id == email.user_id
                    ).first()

                    if not template:
                        return {
                            'success': False,
                            'error': f'Template {template_id} not found'
                        }

                    # Render template (basic variable substitution)
                    message = self._render_template(template.body, email)
                    subject = self._render_template(template.subject, email)

                    # Update template usage stats
                    template.times_used += 1
                    template.last_used = datetime.utcnow()
                    session.commit()
                else:
                    # Use action_value as message directly
                    message = action_value
                    subject = f"Re: {email.subject or ''}"

                # Send reply
                result = await self.email_sender.send_reply(
                    account=account,
                    original_email=email,
                    reply_message=message
                )

                return result

            elif rule.action_type == ActionType.FORWARD:
                # Forward email to specified address(es)
                forward_addresses = [addr.strip() for addr in action_value.split(',')]

                # TODO: Implement forwarding logic
                # For now, return success but note it's not implemented
                return {
                    'success': True,
                    'message': 'Forward action queued (not yet implemented)',
                    'forward_to': forward_addresses
                }

            elif rule.action_type == ActionType.DELETE:
                # Delete email
                result = await self.action_executor.execute_action(
                    account=account,
                    email=email,
                    action='delete'
                )

                # Delete from local database
                session.delete(email)
                session.commit()

                return result

            elif rule.action_type == ActionType.MARK_READ:
                # Mark as read
                is_read = action_value.lower() in ['true', '1', 'yes', 'read']

                result = await self.action_executor.execute_action(
                    account=account,
                    email=email,
                    action='mark_read',
                    is_read=is_read
                )

                # Update local database
                email.is_read = is_read
                session.commit()

                return result

            elif rule.action_type == ActionType.AI_REPLY:
                # Use AI to generate contextual response
                from ospra_os.email_automation.ai_responder import EmailAutomationAI
                
                ai = EmailAutomationAI()
                ai_result = await ai.process_email(
                    email_id=str(email.id),
                    from_address=email.from_address or '',
                    from_name=email.from_name or '',
                    subject=email.subject or '',
                    body=email.body_plain or '',
                    received_at=email.received_at or datetime.utcnow()
                )
                
                if ai_result.get('should_respond'):
                    # Send the AI-generated response
                    send_result = await self.email_sender.send_reply(
                        account=account,
                        original_email=email,
                        reply_message=ai_result['response_text']
                    )
                    
                    return {
                        'success': send_result.get('success', False),
                        'ai_category': ai_result.get('category'),
                        'ai_urgency': ai_result.get('urgency'),
                        'response_type': ai_result.get('response_type'),
                        'order_detected': ai_result.get('order_number')
                    }
                else:
                    return {
                        'success': True,
                        'message': f"Email auto-ignored: {ai_result.get('reason', 'no response needed')}"
                    }

            else:
                return {
                    'success': False,
                    'error': f'Unknown action type: {rule.action_type}'
                }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


    def _render_template(self, template_text: str, email: Email) -> str:
        """
        Render a template by replacing variables with email data.

        Supported variables:
            {{from_name}} - Sender's name
            {{from_address}} - Sender's email
            {{subject}} - Email subject
            {{date}} - Received date

        Args:
            template_text: The template text with {{variables}}
            email: The email object

        Returns:
            Rendered text with variables replaced
        """
        rendered = template_text

        # Replace common variables
        rendered = rendered.replace('{{from_name}}', email.from_name or email.from_address or 'there')
        rendered = rendered.replace('{{from_address}}', email.from_address or '')
        rendered = rendered.replace('{{subject}}', email.subject or '')
        rendered = rendered.replace('{{date}}', email.received_at.strftime('%B %d, %Y') if email.received_at else '')

        return rendered


    async def process_batch(self, user_id: int, limit: int = 50) -> Dict:
        """
        Process a batch of recent unprocessed emails for a user.

        This can be called periodically or triggered after email sync.

        Args:
            user_id: The user ID
            limit: Maximum number of emails to process

        Returns:
            Dict with batch processing results
        """
        session = get_multi_store_session()

        try:
            # Get recent emails that haven't been processed
            # (For simplicity, we'll process all recent emails each time)
            emails = session.query(Email).filter(
                Email.user_id == user_id
            ).order_by(Email.received_at.desc()).limit(limit).all()

            total_rules_matched = 0
            total_actions_executed = 0
            processed_emails = []

            for email in emails:
                result = await self.process_email(email, session)

                if result['rules_matched'] > 0:
                    processed_emails.append({
                        'email_id': email.id,
                        'subject': email.subject,
                        **result
                    })

                    total_rules_matched += result['rules_matched']
                    total_actions_executed += result['actions_executed']

            return {
                'success': True,
                'emails_processed': len(emails),
                'emails_with_matches': len(processed_emails),
                'total_rules_matched': total_rules_matched,
                'total_actions_executed': total_actions_executed,
                'details': processed_emails
            }

        finally:
            session.close()
