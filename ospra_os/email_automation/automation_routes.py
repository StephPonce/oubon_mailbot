"""
Email Automation Settings API Routes

Endpoints for managing automation rules, email templates, and custom labels.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from ospra_os.database import (
    EmailAutomationRule, EmailTemplate, EmailLabel,
    TriggerType, ActionType, get_multi_store_session
)

router = APIRouter(prefix="/api/email-automation", tags=["Email Automation"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class RuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    trigger_type: str  # 'keyword', 'sender', 'subject', 'label'
    trigger_value: str
    action_type: str   # 'label', 'reply', 'forward', 'delete', 'mark_read'
    action_value: str
    is_active: bool = True
    priority: int = 100


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_value: Optional[str] = None
    action_type: Optional[str] = None
    action_value: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None


class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    subject: str
    body: str
    variables: List[str] = []


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    variables: Optional[List[str]] = None


class LabelCreate(BaseModel):
    name: str
    color: str  # Hex color code


class LabelUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None


# ============================================================================
# AUTOMATION RULES ENDPOINTS
# ============================================================================

@router.get("/rules")
def get_automation_rules(
    user_id: int = Query(..., description="User ID"),
    session: Session = Depends(get_multi_store_session)
):
    """
    Get all automation rules for a user.

    GET /api/email-automation/rules?user_id=1
    """
    try:
        rules = session.query(EmailAutomationRule)\
            .filter(EmailAutomationRule.user_id == user_id)\
            .order_by(EmailAutomationRule.priority.asc())\
            .all()

        return {
            'success': True,
            'rules': [
                {
                    'id': rule.id,
                    'name': rule.name,
                    'description': rule.description,
                    'trigger_type': rule.trigger_type.value,
                    'trigger_value': rule.trigger_value,
                    'action_type': rule.action_type.value,
                    'action_value': rule.action_value,
                    'is_active': rule.is_active,
                    'priority': rule.priority,
                    'times_triggered': rule.times_triggered,
                    'last_triggered': rule.last_triggered.isoformat() if rule.last_triggered else None,
                    'created_at': rule.created_at.isoformat(),
                    'updated_at': rule.updated_at.isoformat()
                }
                for rule in rules
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch rules: {str(e)}")
    finally:
        session.close()


@router.post("/rules")
def create_automation_rule(
    rule_data: RuleCreate,
    user_id: int = Query(..., description="User ID"),
    session: Session = Depends(get_multi_store_session)
):
    """
    Create a new automation rule.

    POST /api/email-automation/rules?user_id=1
    Body: {"name": "VIP Auto-Label", "trigger_type": "sender", ...}
    """
    try:
        # Validate enum values
        try:
            trigger_type = TriggerType(rule_data.trigger_type)
            action_type = ActionType(rule_data.action_type)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid enum value: {str(e)}")

        # Create rule
        new_rule = EmailAutomationRule(
            user_id=user_id,
            name=rule_data.name,
            description=rule_data.description,
            trigger_type=trigger_type,
            trigger_value=rule_data.trigger_value,
            action_type=action_type,
            action_value=rule_data.action_value,
            is_active=rule_data.is_active,
            priority=rule_data.priority
        )

        session.add(new_rule)
        session.commit()
        session.refresh(new_rule)

        return {
            'success': True,
            'rule': {
                'id': new_rule.id,
                'name': new_rule.name,
                'trigger_type': new_rule.trigger_type.value,
                'action_type': new_rule.action_type.value,
                'is_active': new_rule.is_active,
                'priority': new_rule.priority
            }
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create rule: {str(e)}")
    finally:
        session.close()


@router.put("/rules/{rule_id}")
def update_automation_rule(
    rule_id: int,
    rule_data: RuleUpdate,
    user_id: int = Query(..., description="User ID"),
    session: Session = Depends(get_multi_store_session)
):
    """
    Update an existing automation rule.

    PUT /api/email-automation/rules/5?user_id=1
    Body: {"name": "Updated Rule Name", "priority": 50}
    """
    try:
        rule = session.query(EmailAutomationRule)\
            .filter(EmailAutomationRule.id == rule_id)\
            .filter(EmailAutomationRule.user_id == user_id)\
            .first()

        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")

        # Update fields
        if rule_data.name is not None:
            rule.name = rule_data.name
        if rule_data.description is not None:
            rule.description = rule_data.description
        if rule_data.trigger_type is not None:
            rule.trigger_type = TriggerType(rule_data.trigger_type)
        if rule_data.trigger_value is not None:
            rule.trigger_value = rule_data.trigger_value
        if rule_data.action_type is not None:
            rule.action_type = ActionType(rule_data.action_type)
        if rule_data.action_value is not None:
            rule.action_value = rule_data.action_value
        if rule_data.is_active is not None:
            rule.is_active = rule_data.is_active
        if rule_data.priority is not None:
            rule.priority = rule_data.priority

        rule.updated_at = datetime.utcnow()

        session.commit()

        return {
            'success': True,
            'rule_id': rule.id,
            'message': 'Rule updated successfully'
        }
    except ValueError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid enum value: {str(e)}")
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update rule: {str(e)}")
    finally:
        session.close()


@router.delete("/rules/{rule_id}")
def delete_automation_rule(
    rule_id: int,
    user_id: int = Query(..., description="User ID"),
    session: Session = Depends(get_multi_store_session)
):
    """
    Delete an automation rule.

    DELETE /api/email-automation/rules/5?user_id=1
    """
    try:
        rule = session.query(EmailAutomationRule)\
            .filter(EmailAutomationRule.id == rule_id)\
            .filter(EmailAutomationRule.user_id == user_id)\
            .first()

        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")

        session.delete(rule)
        session.commit()

        return {
            'success': True,
            'rule_id': rule_id,
            'message': 'Rule deleted successfully'
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete rule: {str(e)}")
    finally:
        session.close()


# ============================================================================
# EMAIL TEMPLATES ENDPOINTS
# ============================================================================

@router.get("/templates")
def get_email_templates(
    user_id: int = Query(..., description="User ID"),
    session: Session = Depends(get_multi_store_session)
):
    """
    Get all email templates for a user.

    GET /api/email-automation/templates?user_id=1
    """
    try:
        templates = session.query(EmailTemplate)\
            .filter(EmailTemplate.user_id == user_id)\
            .order_by(EmailTemplate.created_at.desc())\
            .all()

        return {
            'success': True,
            'templates': [
                {
                    'id': template.id,
                    'name': template.name,
                    'description': template.description,
                    'subject': template.subject,
                    'body': template.body,
                    'variables': template.variables,
                    'times_used': template.times_used,
                    'last_used': template.last_used.isoformat() if template.last_used else None,
                    'created_at': template.created_at.isoformat(),
                    'updated_at': template.updated_at.isoformat()
                }
                for template in templates
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch templates: {str(e)}")
    finally:
        session.close()


@router.post("/templates")
def create_email_template(
    template_data: TemplateCreate,
    user_id: int = Query(..., description="User ID"),
    session: Session = Depends(get_multi_store_session)
):
    """
    Create a new email template.

    POST /api/email-automation/templates?user_id=1
    Body: {"name": "Order Status", "subject": "...", "body": "...", "variables": ["order_id"]}
    """
    try:
        new_template = EmailTemplate(
            user_id=user_id,
            name=template_data.name,
            description=template_data.description,
            subject=template_data.subject,
            body=template_data.body,
            variables=template_data.variables
        )

        session.add(new_template)
        session.commit()
        session.refresh(new_template)

        return {
            'success': True,
            'template': {
                'id': new_template.id,
                'name': new_template.name,
                'subject': new_template.subject,
                'variables': new_template.variables
            }
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create template: {str(e)}")
    finally:
        session.close()


@router.put("/templates/{template_id}")
def update_email_template(
    template_id: int,
    template_data: TemplateUpdate,
    user_id: int = Query(..., description="User ID"),
    session: Session = Depends(get_multi_store_session)
):
    """
    Update an existing email template.

    PUT /api/email-automation/templates/5?user_id=1
    Body: {"subject": "Updated Subject", "body": "Updated body text"}
    """
    try:
        template = session.query(EmailTemplate)\
            .filter(EmailTemplate.id == template_id)\
            .filter(EmailTemplate.user_id == user_id)\
            .first()

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Update fields
        if template_data.name is not None:
            template.name = template_data.name
        if template_data.description is not None:
            template.description = template_data.description
        if template_data.subject is not None:
            template.subject = template_data.subject
        if template_data.body is not None:
            template.body = template_data.body
        if template_data.variables is not None:
            template.variables = template_data.variables

        template.updated_at = datetime.utcnow()

        session.commit()

        return {
            'success': True,
            'template_id': template.id,
            'message': 'Template updated successfully'
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update template: {str(e)}")
    finally:
        session.close()


@router.delete("/templates/{template_id}")
def delete_email_template(
    template_id: int,
    user_id: int = Query(..., description="User ID"),
    session: Session = Depends(get_multi_store_session)
):
    """
    Delete an email template.

    DELETE /api/email-automation/templates/5?user_id=1
    """
    try:
        template = session.query(EmailTemplate)\
            .filter(EmailTemplate.id == template_id)\
            .filter(EmailTemplate.user_id == user_id)\
            .first()

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        session.delete(template)
        session.commit()

        return {
            'success': True,
            'template_id': template_id,
            'message': 'Template deleted successfully'
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete template: {str(e)}")
    finally:
        session.close()


# ============================================================================
# CUSTOM LABELS ENDPOINTS
# ============================================================================

@router.get("/labels")
def get_email_labels(
    user_id: int = Query(..., description="User ID"),
    session: Session = Depends(get_multi_store_session)
):
    """
    Get all custom labels for a user.

    GET /api/email-automation/labels?user_id=1
    """
    try:
        labels = session.query(EmailLabel)\
            .filter(EmailLabel.user_id == user_id)\
            .order_by(EmailLabel.created_at.desc())\
            .all()

        return {
            'success': True,
            'labels': [
                {
                    'id': label.id,
                    'name': label.name,
                    'color': label.color,
                    'email_count': label.email_count,
                    'created_at': label.created_at.isoformat(),
                    'updated_at': label.updated_at.isoformat()
                }
                for label in labels
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch labels: {str(e)}")
    finally:
        session.close()


@router.post("/labels")
def create_email_label(
    label_data: LabelCreate,
    user_id: int = Query(..., description="User ID"),
    session: Session = Depends(get_multi_store_session)
):
    """
    Create a new custom label.

    POST /api/email-automation/labels?user_id=1
    Body: {"name": "VIP", "color": "#FF5733"}
    """
    try:
        # Check if label with this name already exists for user
        existing = session.query(EmailLabel)\
            .filter(EmailLabel.user_id == user_id)\
            .filter(EmailLabel.name == label_data.name)\
            .first()

        if existing:
            raise HTTPException(status_code=400, detail="Label with this name already exists")

        new_label = EmailLabel(
            user_id=user_id,
            name=label_data.name,
            color=label_data.color
        )

        session.add(new_label)
        session.commit()
        session.refresh(new_label)

        return {
            'success': True,
            'label': {
                'id': new_label.id,
                'name': new_label.name,
                'color': new_label.color
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create label: {str(e)}")
    finally:
        session.close()


@router.put("/labels/{label_id}")
def update_email_label(
    label_id: int,
    label_data: LabelUpdate,
    user_id: int = Query(..., description="User ID"),
    session: Session = Depends(get_multi_store_session)
):
    """
    Update an existing custom label.

    PUT /api/email-automation/labels/5?user_id=1
    Body: {"name": "Important", "color": "#FF0000"}
    """
    try:
        label = session.query(EmailLabel)\
            .filter(EmailLabel.id == label_id)\
            .filter(EmailLabel.user_id == user_id)\
            .first()

        if not label:
            raise HTTPException(status_code=404, detail="Label not found")

        # Check for duplicate name if changing name
        if label_data.name is not None and label_data.name != label.name:
            existing = session.query(EmailLabel)\
                .filter(EmailLabel.user_id == user_id)\
                .filter(EmailLabel.name == label_data.name)\
                .first()

            if existing:
                raise HTTPException(status_code=400, detail="Label with this name already exists")

        # Update fields
        if label_data.name is not None:
            label.name = label_data.name
        if label_data.color is not None:
            label.color = label_data.color

        label.updated_at = datetime.utcnow()

        session.commit()

        return {
            'success': True,
            'label_id': label.id,
            'message': 'Label updated successfully'
        }
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update label: {str(e)}")
    finally:
        session.close()


@router.delete("/labels/{label_id}")
def delete_email_label(
    label_id: int,
    user_id: int = Query(..., description="User ID"),
    session: Session = Depends(get_multi_store_session)
):
    """
    Delete a custom label.

    DELETE /api/email-automation/labels/5?user_id=1
    """
    try:
        label = session.query(EmailLabel)\
            .filter(EmailLabel.id == label_id)\
            .filter(EmailLabel.user_id == user_id)\
            .first()

        if not label:
            raise HTTPException(status_code=404, detail="Label not found")

        session.delete(label)
        session.commit()

        return {
            'success': True,
            'label_id': label_id,
            'message': 'Label deleted successfully'
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete label: {str(e)}")
    finally:
        session.close()


# ============================================================================
# AUTOMATION ENGINE ENDPOINTS
# ============================================================================

@router.post("/process")
async def process_automation_rules(
    user_id: int = Query(..., description="User ID"),
    limit: int = Query(50, ge=1, le=200, description="Max emails to process")
):
    """
    Manually trigger automation rule processing for a user's emails.

    This will process recent emails against all active automation rules
    and execute matching actions.

    Normally this would be triggered automatically after email sync,
    but this endpoint allows manual triggering for testing or on-demand processing.

    POST /api/email-automation/process?user_id=1&limit=50

    Returns:
        Processing statistics and results
    """
    try:
        from ospra_os.email_automation.automation_engine import AutomationEngine

        engine = AutomationEngine()
        result = await engine.process_batch(user_id=user_id, limit=limit)

        return {
            'success': True,
            **result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process automation: {str(e)}")
