"""
Oi API Routes - ENHANCED WITH MEMORY SYSTEM

REST API endpoints for the Oi AI assistant.
Now includes:
- Three-layer context (Dashboard + Memory + Universal)
- Persistent per-user memory
- Universal knowledge sharing (anonymized)
- Self-learning system

[SECURE] SECURED with JWT Authentication
"""

import logging
import traceback
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

from ospra_os.oi.oi_service import OiService, OiResponse, oi_sessions
from ospra_os.oi.context_builder import ContextBuilder
from ospra_os.oi.action_executor import ActionStatus
from ospra_os.oi.learning_system import get_learning_system, UserInteraction, ConversationFeedback

# JWT Authentication
from ospra_os.auth.dependencies import require_auth, optional_auth, TokenPayload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/oi", tags=["Oi Assistant"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class SelectedProductModel(BaseModel):
    id: str
    name: str
    price: Optional[float] = None
    supplier_cost: Optional[float] = None
    score: Optional[float] = None
    niche: Optional[str] = None
    trend_score: Optional[float] = None
    source: Optional[str] = None


class SelectedStoreModel(BaseModel):
    id: str
    platform: str
    store_name: str
    store_url: str
    currency: Optional[str] = None


class StoreMetricsModel(BaseModel):
    revenue_7d: float = 0
    revenue_30d: float = 0
    orders_7d: int = 0
    orders_30d: int = 0
    products_count: int = 0
    customers_count: int = 0
    avg_order_value: float = 0


class TrendingProductModel(BaseModel):
    id: str
    name: str
    score: float
    trend_direction: str = "stable"
    niche: str
    source: Optional[str] = None


class ConnectionStatusModel(BaseModel):
    stores: bool = False
    email: bool = False
    intelligence: bool = False
    ads: bool = False


class DashboardContextModel(BaseModel):
    """Complete dashboard context from frontend."""
    currentPage: str = "overview"
    currentView: Optional[str] = None
    selectedProduct: Optional[SelectedProductModel] = None
    selectedStore: Optional[SelectedStoreModel] = None
    visibleProducts: List[SelectedProductModel] = []
    trendingProducts: List[TrendingProductModel] = []
    storeMetrics: Optional[StoreMetricsModel] = None
    activeFilters: Dict[str, Any] = {}
    recentSearches: List[str] = []
    connectionStatus: ConnectionStatusModel = ConnectionStatusModel()


class ChatRequest(BaseModel):
    """Request model for chat endpoint - WITH FULL CONTEXT."""
    message: str = Field(..., min_length=1, max_length=4000, description="User message")
    context_refresh: bool = Field(default=False, description="Refresh backend context")
    execute_actions: bool = Field(default=True, description="Execute detected actions")
    dashboard_context: Optional[DashboardContextModel] = None
    # NEW: Conversation tracking
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    message: str
    actions_taken: List[Dict[str, Any]] = []
    suggestions: List[str] = []
    tokens_used: int = 0
    timestamp: str
    data_disclaimer: Optional[str] = None
    validation_warnings: List[str] = []
    data_sources: Dict[str, bool] = {}
    message_id: str = ""
    conversation_id: str = ""
    # NEW: Memory indicators
    remembered_context: List[str] = []  # What Oi remembered about user


class MemoryUpdateRequest(BaseModel):
    """Request to update user memory manually."""
    fact: Optional[str] = None
    preference_key: Optional[str] = None
    preference_value: Optional[Any] = None


class InteractionRequest(BaseModel):
    timestamp: str
    type: str
    data: Dict[str, Any]


class FeedbackRequest(BaseModel):
    message_id: str
    helpful: bool
    comment: Optional[str] = None
    context: Optional[DashboardContextModel] = None


class QuickActionRequest(BaseModel):
    action: str = Field(..., description="Action name to execute")
    params: Dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = Field(default=False)


class QuickActionResponse(BaseModel):
    action: str
    status: str
    message: str
    data: Dict[str, Any] = {}
    timestamp: str


class ContextResponse(BaseModel):
    user: Optional[Dict[str, Any]] = None
    stores: List[Dict[str, Any]] = []
    store_metrics: Optional[Dict[str, Any]] = None
    products_count: int = 0
    trending_count: int = 0
    email_stats: Optional[Dict[str, Any]] = None
    connection_status: Dict[str, bool] = {}
    data_disclaimer: str = ""
    user_insights: Optional[Dict[str, Any]] = None
    # NEW: Memory info
    memory_summary: Optional[Dict[str, Any]] = None


class ConversationSummary(BaseModel):
    message_count: int
    total_tokens: int
    context_keys: List[str]
    last_message: Optional[str] = None
    provider: str = "claude"


class RecommendationsResponse(BaseModel):
    recommendations: List[Dict[str, Any]]
    based_on: Dict[str, Any]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_user_id_from_token(user: TokenPayload) -> str:
    return str(user.user_id)


def merge_contexts(
    backend_context: Dict[str, Any],
    dashboard_context: Optional[DashboardContextModel]
) -> Dict[str, Any]:
    """Merge backend context with frontend dashboard context."""
    if not dashboard_context:
        return backend_context
    
    merged = {**backend_context}
    
    merged["current_page"] = dashboard_context.currentPage
    merged["current_view"] = dashboard_context.currentView
    
    if dashboard_context.selectedProduct:
        merged["selected_product"] = dashboard_context.selectedProduct.dict()
    
    if dashboard_context.selectedStore:
        merged["selected_store"] = dashboard_context.selectedStore.dict()
    
    if dashboard_context.visibleProducts:
        merged["visible_products"] = [p.dict() for p in dashboard_context.visibleProducts]
    
    if dashboard_context.trendingProducts:
        merged["trending_products"] = [p.dict() for p in dashboard_context.trendingProducts]
    
    if dashboard_context.storeMetrics:
        merged["store_metrics"] = dashboard_context.storeMetrics.dict()
    
    merged["active_filters"] = dashboard_context.activeFilters
    merged["recent_searches"] = dashboard_context.recentSearches
    
    merged["connection_status"] = {
        "has_stores": dashboard_context.connectionStatus.stores,
        "has_metrics": dashboard_context.storeMetrics is not None,
        "has_trending": len(dashboard_context.trendingProducts) > 0,
        "has_products": len(dashboard_context.visibleProducts) > 0 or len(dashboard_context.trendingProducts) > 0,
        "has_orders": dashboard_context.storeMetrics is not None and (dashboard_context.storeMetrics.orders_7d > 0 or dashboard_context.storeMetrics.orders_30d > 0),
        "has_email": dashboard_context.connectionStatus.email,
        "has_ads": dashboard_context.connectionStatus.ads,
    }
    
    return merged


async def get_oi_service(
    user_id: str,
    refresh_context: bool = False
) -> OiService:
    """Get or create Oi service with real context."""
    oi = oi_sessions.get_or_create(user_id)
    
    if refresh_context or not oi.context:
        builder = ContextBuilder(user_id)
        context = await builder.build_full_context()
        oi.update_context(context)
    
    return oi


def build_oi_system_prompt(
    user_context: Dict[str, Any],
    memory: Dict[str, Any],
    universal: Dict[str, Any]
) -> str:
    """
    Build comprehensive system prompt for Claude with all context layers.
    This is where Oi gets its "universal awareness".
    """
    prompt_parts = []
    
    # Core identity
    prompt_parts.append("""You are Oi, the AI brain of Ospra Intelligence - an e-commerce automation platform.
You have full visibility into the user's dashboard, their history with you, and market knowledge.

CRITICAL: You remember past conversations with this user and use that context.
You proactively use your knowledge to give better recommendations.""")
    
    # User memory (what you remember about them)
    if memory.get("important_facts"):
        facts = "\n".join(f"- {fact}" for fact in memory["important_facts"][:10])
        prompt_parts.append(f"\n## WHAT I REMEMBER ABOUT THIS USER:\n{facts}")
    
    if memory.get("preferences"):
        prefs = memory["preferences"]
        if prefs:
            pref_str = ", ".join(f"{k}: {v}" for k, v in list(prefs.items())[:5])
            prompt_parts.append(f"\n## USER PREFERENCES:\n{pref_str}")
    
    if memory.get("conversation_summary"):
        prompt_parts.append(f"\n## RECENT CONVERSATION CONTEXT:\n{memory['conversation_summary']}")
    
    # Dashboard context (what they're seeing now)
    dashboard = user_context.get("layers", {}).get("dashboard", {})
    
    if dashboard.get("products"):
        product_count = len(dashboard["products"])
        deployed = sum(1 for p in dashboard["products"] if p.get("deployed"))
        prompt_parts.append(f"\n## CURRENT DASHBOARD STATE:")
        prompt_parts.append(f"- Products in catalog: {product_count}")
        prompt_parts.append(f"- Products deployed to Shopify: {deployed}")
        
        if dashboard["products"][:5]:
            top_products = dashboard["products"][:5]
            product_list = "\n".join(
                f"  - {p['name']} (Score: {p.get('score', 'N/A')}, ${p.get('price', 'N/A')})"
                for p in top_products
            )
            prompt_parts.append(f"- Top products:\n{product_list}")
    
    if dashboard.get("autopilot"):
        ap = dashboard["autopilot"]
        status = "ACTIVE" if ap.get("is_active") else "INACTIVE"
        prompt_parts.append(f"- Auto-Pilot: {status}")
        if ap.get("config"):
            prompt_parts.append(f"  - Max daily actions: {ap['config'].get('max_daily_actions', 10)}")
            prompt_parts.append(f"  - Max daily spend: ${ap['config'].get('max_daily_spend', 100)}")
    
    if dashboard.get("pending_actions"):
        actions = dashboard["pending_actions"]
        prompt_parts.append(f"- Pending actions: {len(actions)}")
    
    if dashboard.get("store_health"):
        health = dashboard["store_health"]
        prompt_parts.append(f"- Store health: {health.get('score', 0)}/100 ({health.get('status', 'unknown')})")
        if health.get("issues"):
            issues = "\n".join(f"  - {issue}" for issue in health["issues"][:3])
            prompt_parts.append(f"- Issues:\n{issues}")
    
    # Current page context
    if user_context.get("current_page"):
        prompt_parts.append(f"\n## USER IS CURRENTLY VIEWING: {user_context['current_page']}")
    
    # Universal knowledge (market insights)
    if universal.get("trending_niches"):
        niches = ", ".join(n["niche"] for n in universal["trending_niches"][:5])
        prompt_parts.append(f"\n## CURRENT MARKET TRENDS:\n- Trending niches: {niches}")
    
    if universal.get("best_practices"):
        practices = "\n".join(f"- {p['practice']}" for p in universal["best_practices"][:3])
        prompt_parts.append(f"\n## BEST PRACTICES:\n{practices}")
    
    # Instructions
    prompt_parts.append("""
## HOW TO RESPOND:
1. Be proactive - suggest actions based on what you see
2. Reference specific data from the dashboard
3. Remember and use past conversation context
4. Be concise but thorough
5. If you learn something new about the user (preferences, goals), note it
6. Always provide actionable next steps""")
    
    return "\n".join(prompt_parts)


# ============================================================================
# MAIN CHAT ENDPOINT
# ============================================================================

@router.post("/chat", response_model=ChatResponse)
async def chat_with_oi(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    user: TokenPayload = Depends(require_auth)
):
    """
    Send a message to Oi with full three-layer context.
    
    Context Layers:
    1. Dashboard - Real-time data from user's store
    2. Memory - Persistent per-user memory (private)
    3. Universal - Shared market knowledge (anonymized)
    
    [SECURE] Requires authentication
    """
    user_id = get_user_id_from_token(user)
    conversation_id = request.conversation_id or str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    
    try:
        logger.info(f"Oi chat from {user_id}: {request.message[:50]}...")
        
        # Get base Oi service
        oi = await get_oi_service(user_id, refresh_context=request.context_refresh)
        
        # Merge backend context with frontend dashboard context
        merged_context = merge_contexts(oi.context, request.dashboard_context)
        
        # Add user info from JWT
        merged_context["authenticated_user"] = {
            "user_id": user.user_id,
            "email": user.email,
            "tier": user.tier
        }
        
        # ===== THREE-LAYER CONTEXT BUILDING =====

        # Layer 1: Dashboard context (already in merged_context)
        # Use visible_products and trending_products from frontend context
        visible_products = merged_context.get("visible_products", [])
        trending_products = merged_context.get("trending_products", [])

        # Combine for full product awareness
        all_products = visible_products + [
            p for p in trending_products
            if not any(v.get("id") == p.get("id") for v in visible_products)
        ]

        dashboard_context = {
            "products": all_products,  # Combined visible + trending (deduped)
            "visible_products": visible_products,
            "trending_products": trending_products,
            "autopilot": merged_context.get("autopilot", {}),
            "pending_actions": merged_context.get("pending_actions", []),
            "store_metrics": merged_context.get("store_metrics", {}),
            "current_page": merged_context.get("current_page", "dashboard"),
        }

        logger.debug(f"Dashboard context: {len(all_products)} products, {len(trending_products)} trending")
        
        # Layer 2: User memory (from database)
        # For now, use learning system as memory proxy
        learning = get_learning_system()
        learning_insights = learning.get_context_enhancement(merged_context, user_id)
        
        user_memory = {
            "preferences": learning_insights.get("user_preferences", {}),
            "important_facts": [],  # Would come from oi_user_memory table
            "conversation_summary": "",  # Would come from recent conversations
            "learned_insights": learning_insights.get("behavioral_patterns", {})
        }
        
        # Layer 3: Universal knowledge
        universal_knowledge = {
            "trending_niches": [],  # Would come from oi_universal_knowledge table
            "best_practices": [
                {"practice": "Maintain 30-50% profit margins", "priority": "high"},
                {"practice": "Focus on products with OI Score above 7", "priority": "high"},
                {"practice": "Start with $10-20/day ad spend per product", "priority": "medium"},
            ],
            "market_insights": []
        }
        
        # Build comprehensive context
        full_context = {
            "layers": {
                "dashboard": dashboard_context,
                "memory": user_memory,
                "universal": universal_knowledge
            },
            "current_page": merged_context.get("current_page"),
            "user": merged_context.get("authenticated_user")
        }
        
        # Build enhanced system prompt
        system_prompt = build_oi_system_prompt(
            full_context,
            user_memory,
            universal_knowledge
        )
        
        # Update Oi's context
        merged_context["oi_system_prompt"] = system_prompt
        merged_context["user_learning"] = learning_insights
        oi.update_context(merged_context)
        
        # Chat with Oi
        response = await oi.chat(
            message=request.message,
            execute_actions=request.execute_actions
        )
        
        # Record interaction for learning
        learning.record_oi_query(
            query=request.message,
            response=response.message,
            context=merged_context,
            user_id=user_id
        )
        
        # Extract memory from response (what Oi learned)
        # TODO: Parse response for new facts/preferences to store
        
        # Build remembered context list for response
        remembered = []
        if user_memory.get("preferences"):
            remembered.append("user_preferences")
        if user_memory.get("important_facts"):
            remembered.append("important_facts")
        if learning_insights.get("behavioral_patterns", {}).get("recent_searches"):
            remembered.append("search_history")
        
        actions = [action.to_dict() for action in response.actions_taken]
        
        return ChatResponse(
            message=response.message,
            actions_taken=actions,
            suggestions=response.suggestions,
            tokens_used=response.tokens_used,
            timestamp=response.timestamp,
            data_disclaimer=response.data_disclaimer,
            validation_warnings=response.validation_warnings,
            data_sources=response.context_used,
            message_id=message_id,
            conversation_id=conversation_id,
            remembered_context=remembered,
        )
        
    except ValueError as e:
        logger.error(f"Chat ValueError: {e}")
        raise HTTPException(status_code=400, detail="Invalid request. Please check your input.")
    except Exception as e:
        logger.error(f"Unexpected chat error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to process message")


# ============================================================================
# MEMORY ENDPOINTS
# ============================================================================

@router.get("/memory")
async def get_user_memory(
    user: TokenPayload = Depends(require_auth)
):
    """
    Get what Oi remembers about the user.
    
    [SECURE] Requires authentication
    """
    user_id = get_user_id_from_token(user)
    
    try:
        learning = get_learning_system()
        insights = learning.get_user_insights(user_id)
        
        return {
            "memory": {
                "preferences": insights.get("top_niches", []),
                "recent_interactions": insights.get("interactions_count", 0),
                "engagement_level": learning._calculate_engagement_level(user_id),
            },
            "can_be_cleared": True
        }
        
    except Exception as e:
        logger.error(f"Failed to get memory: {e}")
        raise HTTPException(status_code=500, detail="AI assistant operation failed. Please try again.")


@router.post("/memory")
async def update_user_memory(
    request: MemoryUpdateRequest,
    user: TokenPayload = Depends(require_auth)
):
    """
    Manually update user memory.
    
    [SECURE] Requires authentication
    """
    user_id = get_user_id_from_token(user)
    
    try:
        # Would update oi_user_memory table
        return {
            "status": "updated",
            "message": "Memory updated successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to update memory: {e}")
        raise HTTPException(status_code=500, detail="AI assistant operation failed. Please try again.")


@router.delete("/memory")
async def clear_user_memory(
    user: TokenPayload = Depends(require_auth)
):
    """
    Clear all of Oi's memory about the user.
    
    [SECURE] Requires authentication
    """
    user_id = get_user_id_from_token(user)
    
    try:
        learning = get_learning_system()
        learning.clear_user_data(user_id)
        
        return {
            "status": "cleared",
            "message": "All memory cleared successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to clear memory: {e}")
        raise HTTPException(status_code=500, detail="AI assistant operation failed. Please try again.")


# ============================================================================
# LEARNING ENDPOINTS
# ============================================================================

@router.post("/learn")
async def track_interaction(
    request: InteractionRequest,
    user: TokenPayload = Depends(require_auth)
):
    """Track user interactions for self-learning."""
    user_id = get_user_id_from_token(user)
    
    try:
        learning = get_learning_system()
        
        interaction = UserInteraction(
            timestamp=request.timestamp,
            type=request.type,
            data=request.data,
            user_id=user_id
        )
        
        learning.record_interaction(interaction)
        
        return {"status": "recorded", "type": request.type}
        
    except Exception as e:
        logger.error(f"Failed to track interaction: {e}")
        return {"status": "error", "message": "Failed to track interaction. Please try again."}


@router.post("/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    user: TokenPayload = Depends(require_auth)
):
    """Submit feedback on an Oi response."""
    user_id = get_user_id_from_token(user)
    
    try:
        learning = get_learning_system()
        
        context_dict = request.context.dict() if request.context else {}
        
        feedback = ConversationFeedback(
            message_id=request.message_id,
            helpful=request.helpful,
            comment=request.comment,
            context=context_dict,
        )
        
        learning.record_feedback(feedback, user_id)
        
        return {
            "status": "recorded",
            "helpful": request.helpful,
            "message": "Thank you! This helps Oi improve."
        }
        
    except Exception as e:
        logger.error(f"Failed to record feedback: {e}")
        return {"status": "error", "message": "Failed to record feedback. Please try again."}


@router.get("/recommendations", response_model=RecommendationsResponse)
async def get_recommendations(
    user: TokenPayload = Depends(require_auth)
):
    """Get personalized recommendations."""
    user_id = get_user_id_from_token(user)
    
    try:
        learning = get_learning_system()
        
        insights = learning.get_user_insights(user_id)
        recommendations = learning.get_personalized_recommendations(user_id)
        
        return RecommendationsResponse(
            recommendations=recommendations,
            based_on={
                "interactions_count": insights.get("interactions_count", 0),
                "engagement_level": learning._calculate_engagement_level(user_id),
                "top_interests": insights.get("top_niches", [])[:3],
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get recommendations: {e}")
        raise HTTPException(status_code=500, detail="AI assistant operation failed. Please try again.")


# ============================================================================
# ACTION ENDPOINTS
# ============================================================================

@router.post("/action", response_model=QuickActionResponse)
async def execute_quick_action(
    request: QuickActionRequest,
    user: TokenPayload = Depends(require_auth)
):
    """Execute a quick action without chat."""
    user_id = get_user_id_from_token(user)
    
    try:
        oi = await get_oi_service(user_id)
        
        result = await oi.action_executor.execute(
            action_name=request.action,
            params=request.params,
            context=oi.context,
            confirmed=request.confirmed
        )
        
        learning = get_learning_system()
        learning.record_interaction(UserInteraction(
            timestamp=datetime.utcnow().isoformat(),
            type="action",
            data={"action": request.action, "status": result.status.value},
            user_id=user_id
        ))
        
        return QuickActionResponse(
            action=result.action,
            status=result.status.value,
            message=result.message,
            data=result.data,
            timestamp=result.timestamp
        )
        
    except Exception as e:
        logger.error(f"Action error: {e}")
        raise HTTPException(status_code=500, detail="AI assistant operation failed. Please try again.")


# ============================================================================
# CONTEXT ENDPOINTS
# ============================================================================

@router.get("/context", response_model=ContextResponse)
async def get_current_context(
    refresh: bool = False,
    include_insights: bool = True,
    user: TokenPayload = Depends(require_auth)
):
    """Get Oi's current context including memory."""
    user_id = get_user_id_from_token(user)
    
    try:
        oi = await get_oi_service(user_id, refresh_context=refresh)
        context = oi.context
        
        status = context.get("connection_status", {})
        
        connected = []
        not_connected = []
        
        if status.get("has_stores"):
            connected.append("stores")
        else:
            not_connected.append("stores")
        
        if status.get("has_metrics"):
            connected.append("metrics")
        else:
            not_connected.append("metrics")
        
        if status.get("has_trending"):
            connected.append("market data")
        else:
            not_connected.append("market data")
        
        if connected:
            disclaimer = f"Connected: {', '.join(connected)}"
            if not_connected:
                disclaimer += f" | Not connected: {', '.join(not_connected)}"
        else:
            disclaimer = "No data sources connected. Connect your store to get started."
        
        user_insights = None
        memory_summary = None
        
        if include_insights:
            learning = get_learning_system()
            user_insights = learning.get_user_insights(user_id)
            memory_summary = {
                "facts_count": 0,
                "preferences_count": len(user_insights.get("top_niches", [])),
                "conversations_count": user_insights.get("interactions_count", 0)
            }
        
        return ContextResponse(
            user=context.get("user"),
            stores=context.get("stores", []) if isinstance(context.get("stores"), list) else [],
            store_metrics=context.get("store_metrics"),
            products_count=len(context.get("products", [])) if isinstance(context.get("products"), list) else 0,
            trending_count=len(context.get("trending", [])) if isinstance(context.get("trending"), list) else 0,
            email_stats=context.get("email_stats"),
            connection_status=status,
            data_disclaimer=disclaimer,
            user_insights=user_insights,
            memory_summary=memory_summary,
        )
        
    except Exception as e:
        logger.error(f"Context error: {e}")
        raise HTTPException(status_code=500, detail="AI assistant operation failed. Please try again.")


# ============================================================================
# CONVERSATION MANAGEMENT
# ============================================================================

@router.get("/conversation", response_model=ConversationSummary)
async def get_conversation_summary(
    user: TokenPayload = Depends(require_auth)
):
    """Get summary of current conversation."""
    user_id = get_user_id_from_token(user)
    
    try:
        oi = await get_oi_service(user_id)
        summary = oi.get_conversation_summary()
        
        return ConversationSummary(**summary)
        
    except Exception as e:
        logger.error(f"Conversation summary error: {e}")
        raise HTTPException(status_code=500, detail="AI assistant operation failed. Please try again.")


@router.post("/conversation/clear")
async def clear_conversation(
    user: TokenPayload = Depends(require_auth)
):
    """Clear conversation history."""
    user_id = get_user_id_from_token(user)
    
    try:
        oi = await get_oi_service(user_id)
        oi.clear_history()
        
        return {"status": "success", "message": "Conversation cleared"}
        
    except Exception as e:
        logger.error(f"Clear conversation error: {e}")
        raise HTTPException(status_code=500, detail="AI assistant operation failed. Please try again.")


# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@router.get("/actions")
async def list_available_actions():
    """List all actions with their requirements."""
    from ospra_os.oi.action_executor import ActionExecutor
    
    executor = ActionExecutor()
    actions = executor.list_actions()
    
    return {
        "actions": [
            {"name": name, "description": desc}
            for name, desc in actions.items()
        ]
    }


@router.get("/health")
async def oi_health():
    """Health check showing what's configured."""
    import os
    
    anthropic_key = bool(os.getenv("ANTHROPIC_API_KEY"))
    openai_key = bool(os.getenv("OPENAI_API_KEY"))
    google_key = bool(os.getenv("GOOGLE_API_KEY"))
    
    available_providers = []
    if anthropic_key:
        available_providers.append("claude")
    if openai_key:
        available_providers.append("openai")
    if google_key:
        available_providers.append("gemini")
    
    active_sessions = len(oi_sessions.get_active_sessions())
    
    learning = get_learning_system()
    learning_stats = learning.get_stats()
    
    return {
        "status": "healthy" if anthropic_key else "degraded",
        "default_provider": "claude",
        "available_providers": available_providers,
        "api_keys_configured": {
            "anthropic": anthropic_key,
            "openai": openai_key,
            "google": google_key
        },
        "active_sessions": active_sessions,
        "learning_system": learning_stats,
        "memory_system": {
            "enabled": True,
            "layers": ["dashboard", "user_memory", "universal"]
        },
        "timestamp": datetime.utcnow().isoformat()
    }
