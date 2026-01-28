"""
AI Chat Routes

Provides unified AI chat endpoints:
- POST /api/ai/chat
- POST /api/claude/chat

Both route to the Claude AI chat response system with learning context.

SECURITY: All endpoints require JWT authentication.
User ID is extracted from the authenticated user, not request body.
"""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, List, Any

from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI Chat"])

# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None
    dashboard_context: Optional[Dict[str, Any]] = None  # Alternative name
    # SECURITY: user_id removed - extracted from JWT token instead
    conversation_history: Optional[List[Dict[str, str]]] = None


class ChatResponse(BaseModel):
    response: str
    timestamp: str
    sources: List[str] = []


# ============================================
# CHAT ENDPOINTS
# ============================================

@router.post("/ai/chat", response_model=ChatResponse)
async def ai_chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    """
    AI Chat endpoint using Claude

    POST /api/ai/chat

    Request body:
        {
            "message": "What products should I sell?",
            "context": {...},  # Optional business context
            "conversation_history": [...]  # Optional previous messages
        }

    Returns:
        {
            "response": "Claude's response",
            "timestamp": "2024-12-09T...",
            "sources": []
        }
    """
    try:
        # Import here to avoid circular dependencies
        from ospra_os.intelligence.trend_analyzer import TrendAnalyzer
        from ospra_os.learning.context_builder import build_claude_context

        # Initialize analyzer
        analyzer = TrendAnalyzer()

        if not analyzer.claude_client:
            raise HTTPException(
                status_code=503,
                detail="Claude AI is not available. Please check ANTHROPIC_API_KEY is set."
            )

        # SECURITY: Use authenticated user's ID instead of request body
        user_id = current_user.id

        # Build learning context (provides unlimited historical knowledge)
        learning_context = None
        try:
            learning_context = build_claude_context(
                user_id=user_id,
                user_query=request.message
            )
        except Exception as e:
            logger.warning(f"Failed to build learning context: {e}")
            # Continue without learning context

        # Merge contexts (prefer dashboard_context over context for backward compatibility)
        context_data = request.dashboard_context or request.context or {}

        # Get response from Claude with learning context
        response = analyzer.chat_response(
            message=request.message,
            context=context_data,
            user_id=user_id
        )

        return ChatResponse(
            response=response,
            timestamp=datetime.now().isoformat(),
            sources=[]  # Could add source tracking later
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to process chat request. Please try again."
        )


@router.post("/claude/chat", response_model=ChatResponse)
async def claude_chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Claude Chat endpoint (alias for /api/ai/chat)

    POST /api/claude/chat

    This endpoint exists for backward compatibility with frontend code
    that calls /api/claude/chat. It routes to the same logic as /api/ai/chat.
    """
    return await ai_chat(request, current_user)
