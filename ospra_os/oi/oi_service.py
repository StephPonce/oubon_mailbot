"""
Oi Service - The Brain of Ospra Intelligence

USES AI FACTORY - defaults to Claude for reasoning/consistency
VALIDATES RESPONSES - catches hallucination attempts
ADDS DISCLAIMERS - makes data source clear to users

Author: OspraOS
Date: December 2024
"""

import os
import re
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from ospra_os.ai.factory import AIFactory
from ospra_os.oi.prompts import OI_SYSTEM_PROMPT, build_context_prompt
from ospra_os.oi.action_executor import ActionExecutor, ActionResult
from ospra_os.oi.response_validator import ResponseValidator, ValidationResult

logger = logging.getLogger(__name__)

# Import Intelligence Bridge for product recommendations and learning
try:
    from ospra_os.oi.intelligence_bridge import OiIntelligenceBridge, get_intelligence_bridge
    INTELLIGENCE_BRIDGE_AVAILABLE = True
except ImportError:
    INTELLIGENCE_BRIDGE_AVAILABLE = False
    logger.warning("Intelligence Bridge not available - Oi will have limited product intelligence")


@dataclass
class OiResponse:
    """Response from Oi assistant."""
    message: str
    actions_taken: List[ActionResult] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    context_used: Dict[str, Any] = field(default_factory=dict)
    tokens_used: int = 0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    data_disclaimer: Optional[str] = None  # Added: data source disclaimer
    validation_warnings: List[str] = field(default_factory=list)  # Added: validation issues


@dataclass
class ConversationMessage:
    """A single message in the conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class OiService:
    """
    Oi - The Brain of Ospra Intelligence
    
    Uses AI Factory (defaults to Claude for reasoning tasks).
    Validates responses to catch hallucinations.
    Adds disclaimers about data sources.
    """
    
    # Default to Claude - best for reasoning and instruction-following
    DEFAULT_PROVIDER = "claude"
    MAX_TOKENS = 2048
    MAX_CONVERSATION_HISTORY = 20
    
    def __init__(
        self,
        user_id: str,
        provider_name: Optional[str] = None,
        api_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize Oi for a specific user.
        
        Args:
            user_id: Unique user identifier
            provider_name: AI provider ("claude", "openai", "gemini") - defaults to Claude
            api_key: API key (defaults to env var based on provider)
            context: Initial context (stores, products, etc.)
        """
        self.user_id = user_id
        self.provider_name = provider_name or self.DEFAULT_PROVIDER
        
        # Get API key based on provider
        if not api_key:
            api_key = self._get_api_key_for_provider(self.provider_name)
        
        if not api_key:
            raise ValueError(f"API key required for {self.provider_name}")
        
        # Initialize AI provider via Factory
        try:
            self.ai_provider = AIFactory.get_provider(self.provider_name, api_key)
            logger.info(f"Oi initialized with {self.provider_name} provider")
        except Exception as e:
            logger.error(f"Failed to initialize AI provider: {e}")
            raise
        
        # Initialize components
        self.action_executor = ActionExecutor()
        self.response_validator = ResponseValidator()
        
        # Initialize Intelligence Bridge for product recommendations
        self.intelligence_bridge = None
        if INTELLIGENCE_BRIDGE_AVAILABLE:
            try:
                self.intelligence_bridge = get_intelligence_bridge(user_id)
                logger.info("[SUCCESS] Intelligence Bridge connected to Oi")
            except Exception as e:
                logger.warning(f"Could not initialize Intelligence Bridge: {e}")
        
        # Conversation state
        self.conversation_history: List[ConversationMessage] = []
        self.context = context or {}
        self.total_tokens = 0
        
        logger.info(f"Oi initialized for user {user_id} with {self.provider_name}")
    
    def _get_api_key_for_provider(self, provider: str) -> Optional[str]:
        """Get API key from environment based on provider."""
        key_map = {
            "claude": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "gemini": "GOOGLE_API_KEY",
            "groq": "GROQ_API_KEY",
            "llama": "GROQ_API_KEY",  # Llama uses Groq
            "xai": "XAI_API_KEY",
            "grok": "XAI_API_KEY",    # Grok is xAI
        }
        env_var = key_map.get(provider.lower())
        return os.getenv(env_var) if env_var else None
    
    async def chat(
        self,
        message: str,
        context_update: Optional[Dict[str, Any]] = None,
        execute_actions: bool = True
    ) -> OiResponse:
        """
        Send a message to Oi and get a validated response.
        
        Response is validated for hallucinations and includes
        appropriate disclaimers about data sources.
        """
        # Update context if provided
        if context_update:
            self.context.update(context_update)
        
        # Fetch intelligence context (product recommendations, learning insights)
        if self.intelligence_bridge:
            try:
                # Get user_id as int if possible for learning system
                user_id_int = None
                try:
                    user_id_int = int(self.user_id)
                except (ValueError, TypeError):
                    pass
                
                intelligence_context = await self.intelligence_bridge.get_intelligence_context(
                    user_id=user_id_int,
                    include_recommendations=True,
                    include_insights=True,
                    max_recommendations=5
                )
                self.context["intelligence_context"] = intelligence_context
                logger.debug(f"Intelligence context added: {len(intelligence_context.get('top_opportunities', []))} opportunities")
            except Exception as e:
                logger.warning(f"Could not fetch intelligence context: {e}")
        
        # Add user message to history
        self.conversation_history.append(
            ConversationMessage(role="user", content=message)
        )
        
        # Build system prompt with context (now includes intelligence)
        system_prompt = self._build_system_prompt()
        
        # Generate disclaimer based on what data is available
        data_disclaimer = self._generate_data_disclaimer()
        
        try:
            # Call AI provider
            response_text = await self.ai_provider.chat(
                message=message,
                context={"system_prompt": system_prompt, **self.context}
            )
            
            # VALIDATION: Check response for potential hallucinations
            validation = self.response_validator.validate(
                response=response_text,
                context=self.context
            )
            
            # If validation failed, modify or flag the response
            if not validation.is_valid:
                response_text = self._handle_validation_failure(
                    original_response=response_text,
                    validation=validation
                )
            
            # Add to history
            self.conversation_history.append(
                ConversationMessage(role="assistant", content=response_text)
            )
            
            # Trim history
            self._trim_history()
            
            # Process for actions
            actions_taken = []
            suggestions = []
            if execute_actions:
                actions_taken, suggestions = await self._process_response(response_text)
            
            return OiResponse(
                message=response_text,
                actions_taken=actions_taken,
                suggestions=suggestions,
                context_used=self._get_context_summary(),
                tokens_used=0,  # TODO: Track from provider
                data_disclaimer=data_disclaimer,
                validation_warnings=validation.warnings if not validation.is_valid else []
            )
            
        except Exception as e:
            import traceback
            logger.error(f"Oi chat error: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return OiResponse(
                message=(
                    "I encountered an issue processing your request. "
                    "Please try again or check if the backend is running."
                ),
                tokens_used=0,
                data_disclaimer=data_disclaimer
            )
    
    def _generate_data_disclaimer(self) -> str:
        """Generate disclaimer based on what data is actually connected."""
        status = self.context.get("connection_status", {})
        
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
        
        if status.get("has_email"):
            connected.append("email")
        else:
            not_connected.append("email")
        
        # Build disclaimer
        if not connected:
            return "[WARNING] No data sources connected. Responses are general guidance only."
        elif not_connected:
            return f"[STATS] Data from: {', '.join(connected)} | Not connected: {', '.join(not_connected)}"
        else:
            return "[SUCCESS] All data sources connected"
    
    def _handle_validation_failure(
        self,
        original_response: str,
        validation: ValidationResult
    ) -> str:
        """Handle a response that failed validation (potential hallucination)."""
        
        # Log the issue
        logger.warning(f"Response validation failed: {validation.warnings}")
        
        # Option 1: Prepend a warning
        warning_prefix = (
            "[WARNING] Note: Some information in my response may not be from your "
            "connected data sources. Please verify any specific numbers or claims.\n\n"
        )
        
        # Option 2: For severe hallucinations, replace entirely
        if validation.severity == "high":
            return (
                "I apologize, but I don't have reliable data to answer that question. "
                f"The following data sources are not connected: {', '.join(validation.missing_data)}. "
                "Would you like help connecting them?"
            )
        
        return warning_prefix + original_response
    
    def _build_system_prompt(self) -> str:
        """Build system prompt with context."""
        prompt = OI_SYSTEM_PROMPT
        
        if self.context:
            context_prompt = build_context_prompt(self.context)
            prompt += f"\n\n{context_prompt}"
        
        prompt += f"\n\nCurrent date/time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        
        return prompt
    
    def _trim_history(self) -> None:
        """Keep conversation history manageable."""
        if len(self.conversation_history) > self.MAX_CONVERSATION_HISTORY:
            self.conversation_history = self.conversation_history[-self.MAX_CONVERSATION_HISTORY:]
    
    async def _process_response(
        self,
        response: str
    ) -> Tuple[List[ActionResult], List[str]]:
        """Extract and execute actions from response."""
        actions_taken = []
        suggestions = []
        
        # Check for action markers: [ACTION:name:params]
        action_pattern = r'\[ACTION:(\w+):(\{[^}]+\})\]'
        for match in re.finditer(action_pattern, response):
            action_name = match.group(1)
            try:
                params = json.loads(match.group(2))
                result = await self.action_executor.execute(action_name, params, self.context)
                actions_taken.append(result)
            except Exception as e:
                logger.error(f"Action execution error: {e}")
        
        # Extract suggestions: [SUGGEST:text]
        suggest_pattern = r'\[SUGGEST:([^\]]+)\]'
        for match in re.finditer(suggest_pattern, response):
            suggestions.append(match.group(1))
        
        return actions_taken, suggestions
    
    def _get_context_summary(self) -> Dict[str, Any]:
        """Summarize what context was used."""
        status = self.context.get("connection_status", {})
        intelligence = self.context.get("intelligence_context", {})
        
        return {
            "stores_connected": status.get("has_stores", False),
            "metrics_available": status.get("has_metrics", False),
            "trending_available": status.get("has_trending", False),
            "email_connected": status.get("has_email", False),
            # Intelligence status
            "intelligence_available": intelligence.get("intelligence_available", False),
            "learning_available": intelligence.get("learning_available", False),
            "opportunities_count": len(intelligence.get("top_opportunities", [])),
        }
    
    def update_context(self, context: Dict[str, Any]) -> None:
        """Update Oi's context."""
        self.context.update(context)
    
    # ========================================================================
    # INTELLIGENCE BRIDGE METHODS
    # ========================================================================
    
    async def get_product_recommendations(
        self,
        niche: Optional[str] = None,
        limit: int = 10,
        min_score: float = 55.0
    ) -> List[Dict[str, Any]]:
        """
        Get product recommendations from Intelligence Bridge.
        
        Returns list of product recommendations with scores and reasoning.
        """
        if not self.intelligence_bridge:
            return []
        
        try:
            # Get user_id as int
            user_id_int = None
            try:
                user_id_int = int(self.user_id)
            except (ValueError, TypeError):
                pass
            
            recommendations = await self.intelligence_bridge.get_top_opportunities(
                niche=niche,
                limit=limit,
                min_score=min_score,
                user_id=user_id_int
            )
            
            return [
                {
                    "product_id": r.product_id,
                    "product_name": r.product_name,
                    "niche": r.niche,
                    "opportunity_score": r.opportunity_score,
                    "final_score": r.final_score,
                    "personal_adjustment": r.personal_adjustment,
                    "recommendation": r.recommendation,
                    "confidence": r.confidence,
                    "reasons": r.reasons,
                    "risks": r.risks,
                    "suggested_price": r.suggested_price,
                    "estimated_profit": r.estimated_profit,
                    "timing_advice": r.timing_advice,
                    "urgency": r.urgency
                }
                for r in recommendations
            ]
            
        except Exception as e:
            logger.error(f"Error getting product recommendations: {e}")
            return []
    
    async def analyze_product(self, product_name: str, product_data: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """
        Analyze a specific product using Intelligence Bridge.
        
        Returns detailed analysis with score and reasoning.
        """
        if not self.intelligence_bridge:
            return None
        
        try:
            user_id_int = None
            try:
                user_id_int = int(self.user_id)
            except (ValueError, TypeError):
                pass
            
            analysis = await self.intelligence_bridge.analyze_product(
                product_name=product_name,
                product_data=product_data,
                user_id=user_id_int
            )
            
            if analysis:
                return {
                    "product_name": analysis.product_name,
                    "opportunity_score": analysis.opportunity_score,
                    "final_score": analysis.final_score,
                    "recommendation": analysis.recommendation,
                    "confidence": analysis.confidence,
                    "reasons": analysis.reasons,
                    "risks": analysis.risks,
                    "suggested_price": analysis.suggested_price,
                    "estimated_profit": analysis.estimated_profit,
                    "timing_advice": analysis.timing_advice,
                    "urgency": analysis.urgency
                }
            return None
            
        except Exception as e:
            logger.error(f"Error analyzing product: {e}")
            return None
    
    async def record_sale_feedback(
        self,
        product_id: str,
        units_sold: int,
        revenue: float,
        predicted_score: float = 0,
        niche: str = "smart_home",
        price: float = 0
    ) -> Dict[str, Any]:
        """
        Record a sale for learning. This trains both Global Brain and Personal Layer.
        
        Call this when a recommended product sells to improve future recommendations.
        """
        if not self.intelligence_bridge:
            return {"success": False, "reason": "Intelligence Bridge not available"}
        
        try:
            user_id_int = None
            try:
                user_id_int = int(self.user_id)
            except (ValueError, TypeError):
                return {"success": False, "reason": "Invalid user ID for learning"}
            
            result = await self.intelligence_bridge.record_sale(
                product_id=product_id,
                user_id=user_id_int,
                units_sold=units_sold,
                revenue=revenue,
                predicted_score=predicted_score,
                niche=niche,
                price=price
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error recording sale feedback: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_learning_insights(self) -> Dict[str, Any]:
        """
        Get learning insights for this user.
        
        Returns global brain insights and personal layer (if available).
        """
        if not self.intelligence_bridge:
            return {"available": False, "reason": "Intelligence Bridge not available"}
        
        try:
            user_id_int = None
            try:
                user_id_int = int(self.user_id)
            except (ValueError, TypeError):
                pass
            
            insights = await self.intelligence_bridge.get_learning_insights(user_id_int)
            
            return {
                "available": True,
                "global_best_niches": insights.global_best_niches,
                "global_best_price_range": insights.global_best_price_range,
                "global_accuracy": insights.global_accuracy,
                "personal_available": insights.personal_available,
                "personal_best_niches": insights.personal_best_niches,
                "personal_optimal_price": insights.personal_optimal_price,
                "personal_peak_days": insights.personal_peak_days,
                "engagement_level": insights.engagement_level,
                "suggested_focus": insights.suggested_focus,
                "learning_tips": insights.learning_tips
            }
            
        except Exception as e:
            logger.error(f"Error getting learning insights: {e}")
            return {"available": False, "error": str(e)}
    
    def clear_history(self) -> None:
        """Clear conversation history."""
        self.conversation_history = []
    
    def get_conversation_summary(self) -> Dict[str, Any]:
        """Get conversation summary."""
        return {
            "message_count": len(self.conversation_history),
            "total_tokens": self.total_tokens,
            "context_keys": list(self.context.keys()),
            "provider": self.provider_name,
            "last_message": (
                self.conversation_history[-1].content[:100] 
                if self.conversation_history else None
            )
        }


class OiSessionManager:
    """Manages Oi sessions across users."""
    
    def __init__(self):
        self._sessions: Dict[str, OiService] = {}
    
    def get_or_create(
        self,
        user_id: str,
        provider_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> OiService:
        """Get existing or create new Oi session."""
        if user_id not in self._sessions:
            self._sessions[user_id] = OiService(
                user_id=user_id,
                provider_name=provider_name,
                context=context
            )
        elif context:
            self._sessions[user_id].update_context(context)
        
        return self._sessions[user_id]
    
    def end_session(self, user_id: str) -> None:
        """End a user's session."""
        if user_id in self._sessions:
            del self._sessions[user_id]
    
    def get_active_sessions(self) -> List[str]:
        """Get list of active user IDs."""
        return list(self._sessions.keys())


# Global session manager
oi_sessions = OiSessionManager()
