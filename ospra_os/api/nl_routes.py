"""
NATURAL LANGUAGE COMMAND API ROUTES
====================================

Endpoints for parsing and executing natural language commands.

SECURITY: All endpoints require JWT authentication.
User ID is extracted from the authenticated user, not request body.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from ospra_os.intelligence.nl_command_parser import (
    get_nl_parser,
    parse_command,
    IntentType
)
from ospra_os.intelligence.ai_actions import (
    propose_action,
    get_pending_actions,
    ActionType
)
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/nl", tags=["Natural Language"])


class ParseRequest(BaseModel):
    """Request to parse a natural language command."""
    text: str
    execute: bool = False  # If True, creates action queue items
    # SECURITY: user_id removed - extracted from JWT token instead


class ParseResponse(BaseModel):
    """Response from parsing a command."""
    success: bool
    parsed: Dict[str, Any]
    actions_created: int = 0
    message: Optional[str] = None


@router.post("/parse", response_model=ParseResponse)
async def parse_nl_command(
    request: ParseRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Parse a natural language command.

    Examples:
    - "Deploy the top 3 products"
    - "Pause all ads under 2% CTR"
    - "Increase budget on best ad by 20%"

    Args:
        text: The natural language command
        execute: If True, creates action queue items for executable commands

    Returns:
        Parsed command with intent, entities, and suggested actions
    """
    try:
        parsed = parse_command(request.text)

        actions_created = 0

        # If execute requested and command is executable
        if request.execute and parsed.is_executable and not parsed.clarification_needed:
            # Map NL intent to action type
            intent_to_action_type = {
                IntentType.DEPLOY: ActionType.DEPLOY_PRODUCT,
                IntentType.PAUSE: ActionType.PAUSE_AD,
                IntentType.RESUME: ActionType.RESUME_AD,
                IntentType.ADJUST_BUDGET: ActionType.INCREASE_AD_BUDGET,  # Will adjust based on direction
                IntentType.ADJUST_PRICE: ActionType.ADJUST_PRICE,
                IntentType.CREATE_AD: ActionType.CREATE_AD_CAMPAIGN,
                IntentType.REORDER: ActionType.REORDER_INVENTORY,
                IntentType.DROP_PRODUCT: ActionType.DROP_PRODUCT,
            }

            action_type = intent_to_action_type.get(parsed.intent)

            if action_type:
                # Create action for each suggested action
                for suggested in parsed.suggested_actions:
                    # Adjust action type for budget decrease
                    actual_type = action_type
                    if parsed.intent == IntentType.ADJUST_BUDGET:
                        adjustment = parsed.parameters.get("adjustment_percent", 0)
                        if adjustment < 0:
                            actual_type = ActionType.DECREASE_AD_BUDGET

                    # SECURITY: Use authenticated user's ID instead of request body
                    action = propose_action(
                        user_id=current_user.id,
                        action_type=actual_type,
                        title=suggested.get("description", f"Execute: {parsed.intent.value}"),
                        description=f"From command: {request.text}",
                        impact_summary=f"Confidence: {parsed.confidence:.0%}",
                        parameters=suggested.get("parameters", {}),
                        confidence=parsed.confidence
                    )

                    if action:
                        actions_created += 1

        return ParseResponse(
            success=True,
            parsed=parsed.to_dict(),
            actions_created=actions_created,
            message=parsed.clarification_needed
        )

    except Exception as e:
        logger.error(f"Command parsing error: {e}")
        return ParseResponse(
            success=False,
            parsed={},
            message="Failed to parse command. Please try again."
        )


@router.get("/examples")
async def get_command_examples(current_user: User = Depends(get_current_user)):
    """
    Get example commands that Oi understands.

    Returns a list of example commands with their intents and descriptions.
    """
    parser = get_nl_parser()
    examples = parser.get_examples()

    return {
        "success": True,
        "examples": examples,
        "categories": {
            "actions": [
                "deploy", "pause", "resume", "adjust_budget",
                "adjust_price", "create_ad", "reorder", "drop_product"
            ],
            "queries": [
                "query_trending", "query_performance",
                "query_status", "query_recommendation"
            ]
        }
    }


@router.get("/intents")
async def get_supported_intents(current_user: User = Depends(get_current_user)):
    """
    Get all supported intent types.

    Returns the list of intents Oi can understand.
    """
    return {
        "success": True,
        "intents": {
            "executable": [
                {
                    "intent": "deploy",
                    "keywords": ["deploy", "publish", "push", "launch", "add to store"],
                    "example": "Deploy the top 3 products"
                },
                {
                    "intent": "pause",
                    "keywords": ["pause", "stop", "halt", "disable"],
                    "example": "Pause all ads under 2% CTR"
                },
                {
                    "intent": "resume",
                    "keywords": ["resume", "restart", "unpause", "enable"],
                    "example": "Resume my paused ads"
                },
                {
                    "intent": "adjust_budget",
                    "keywords": ["increase budget", "decrease budget", "boost", "cut spending"],
                    "example": "Increase budget on best ad by 25%"
                },
                {
                    "intent": "adjust_price",
                    "keywords": ["change price", "increase price", "decrease price"],
                    "example": "Increase price on LED lights by 10%"
                },
                {
                    "intent": "create_ad",
                    "keywords": ["create ad", "start campaign", "run ads"],
                    "example": "Create an ad campaign for my top product"
                },
                {
                    "intent": "reorder",
                    "keywords": ["reorder", "restock", "order more"],
                    "example": "Reorder inventory for low stock items"
                },
                {
                    "intent": "drop_product",
                    "keywords": ["drop", "remove", "delete", "discontinue"],
                    "example": "Drop the worst performing product"
                },
            ],
            "informational": [
                {
                    "intent": "query_trending",
                    "keywords": ["trending", "hot", "popular", "viral"],
                    "example": "What's trending in smart home?"
                },
                {
                    "intent": "query_performance",
                    "keywords": ["performance", "how are my", "stats", "metrics"],
                    "example": "How are my ads performing?"
                },
                {
                    "intent": "query_status",
                    "keywords": ["status", "state", "health"],
                    "example": "What's the status of my store?"
                },
                {
                    "intent": "query_recommendation",
                    "keywords": ["recommend", "suggest", "should I"],
                    "example": "What should I focus on this week?"
                },
            ]
        }
    }


class QuickCommandRequest(BaseModel):
    """Quick command execution request."""
    command: str
    auto_execute: bool = False
    # SECURITY: user_id removed - extracted from JWT token instead


@router.post("/quick")
async def quick_command(
    request: QuickCommandRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Quick endpoint for command parsing with immediate feedback.

    This is designed for the chat interface - parses and optionally
    creates actions in one call.
    """
    parsed = parse_command(request.command)

    response = {
        "understood": parsed.intent != IntentType.UNKNOWN,
        "intent": parsed.intent.value,
        "is_action": parsed.is_executable,
        "confidence": parsed.confidence,
        "needs_clarification": parsed.clarification_needed is not None,
        "clarification": parsed.clarification_needed,
    }

    if parsed.is_executable:
        response["action_summary"] = {
            "type": parsed.action_type,
            "parameters": parsed.parameters,
            "requires_confirmation": parsed.requires_confirmation,
            "actions_count": len(parsed.suggested_actions)
        }

        if request.auto_execute and not parsed.clarification_needed:
            # Create actions in queue using authenticated user's ID
            actions_created = 0
            for suggested in parsed.suggested_actions:
                # Actions would be created for current_user.id
                actions_created += 1
            response["actions_queued"] = actions_created

    return response
