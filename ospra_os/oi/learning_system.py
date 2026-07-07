"""
Oi Learning System - Self-Improvement Through Interaction

Tracks user interactions, learns from feedback, and improves recommendations.
This is the foundation for Oi becoming smarter over time.

Author: OspraOS
Date: December 2024
"""

import logging
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import os

logger = logging.getLogger(__name__)


@dataclass
class UserInteraction:
    """A single user interaction."""
    timestamp: str
    type: str  # product_view, product_deploy, search, filter, oi_query, feedback, action
    data: Dict[str, Any]
    user_id: str = "default"


@dataclass 
class ConversationFeedback:
    """Feedback on an Oi response."""
    message_id: str
    helpful: bool
    comment: Optional[str]
    context: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class LearnedPattern:
    """A pattern Oi has learned."""
    pattern_type: str  # query_response, product_preference, niche_interest, workflow
    pattern_data: Dict[str, Any]
    confidence: float  # 0.0 - 1.0
    occurrences: int
    last_seen: str
    first_seen: str


class OiLearningSystem:
    """
    Oi's self-learning system.
    
    Learns from:
    1. User interactions (what they click, view, deploy)
    2. Search patterns (what they search for)
    3. Feedback (thumbs up/down on responses)
    4. Conversation history (what questions lead to actions)
    5. Product preferences (what scores/niches they prefer)
    
    Uses learned patterns to:
    1. Personalize responses
    2. Improve recommendations
    3. Predict user needs
    4. Auto-suggest actions
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """Initialize the learning system."""
        self.storage_path = storage_path or os.path.join(
            os.path.dirname(__file__), 
            "learning_data"
        )
        os.makedirs(self.storage_path, exist_ok=True)
        
        # In-memory stores (loaded from disk)
        self._interactions: Dict[str, List[UserInteraction]] = defaultdict(list)
        self._feedback: Dict[str, List[ConversationFeedback]] = defaultdict(list)
        self._patterns: Dict[str, List[LearnedPattern]] = defaultdict(list)
        self._user_profiles: Dict[str, Dict[str, Any]] = {}
        
        # Load existing data
        self._load_data()
        
        logger.info("Oi Learning System initialized")
    
    # ========================================================================
    # DATA RECORDING
    # ========================================================================
    
    def record_interaction(self, interaction: UserInteraction) -> None:
        """Record a user interaction for learning."""
        self._interactions[interaction.user_id].append(interaction)
        
        # Keep last 1000 interactions per user
        if len(self._interactions[interaction.user_id]) > 1000:
            self._interactions[interaction.user_id] = \
                self._interactions[interaction.user_id][-1000:]
        
        # Update user profile based on interaction
        self._update_user_profile(interaction)
        
        # Detect patterns
        self._detect_patterns(interaction)

        # T98: persist learned state after each interaction. Previously
        # save_data() had ZERO callers, so every profile/pattern update lived
        # only in memory and vanished on restart — the "self-improvement"
        # premise never survived a deploy. save_data() is failure-safe (it logs
        # and never raises), so this cannot break the interaction path.
        self.save_data()

        logger.debug(f"Recorded interaction: {interaction.type} for user {interaction.user_id}")
    
    def record_feedback(self, feedback: ConversationFeedback, user_id: str = "default") -> None:
        """Record feedback on an Oi response."""
        self._feedback[user_id].append(feedback)
        
        # Learn from feedback
        self._learn_from_feedback(feedback, user_id)

        # T98: persist feedback-driven profile changes (see record_interaction).
        self.save_data()

        logger.info(f"Recorded feedback: {'helpful' if feedback.helpful else 'not helpful'}")
    
    def record_oi_query(
        self,
        query: str,
        response: str,
        context: Dict[str, Any],
        user_id: str = "default"
    ) -> str:
        """Record an Oi conversation exchange. Returns message_id for feedback."""
        message_id = f"msg_{datetime.now(timezone.utc).timestamp()}"
        
        interaction = UserInteraction(
            timestamp=datetime.now(timezone.utc).isoformat(),
            type="oi_query",
            data={
                "message_id": message_id,
                "query": query,
                "response_preview": response[:200],
                "context_summary": self._summarize_context(context),
            },
            user_id=user_id
        )
        
        self.record_interaction(interaction)
        return message_id
    
    # ========================================================================
    # PATTERN DETECTION
    # ========================================================================
    
    def _detect_patterns(self, interaction: UserInteraction) -> None:
        """Detect patterns from interactions."""
        user_id = interaction.user_id
        
        # Product view patterns
        if interaction.type == "product_view":
            self._update_product_preferences(interaction)
        
        # Search patterns
        elif interaction.type == "search":
            self._update_search_patterns(interaction)
        
        # Filter patterns
        elif interaction.type == "filter":
            self._update_filter_preferences(interaction)
        
        # Workflow patterns (sequences of actions)
        self._detect_workflow_patterns(user_id)
    
    def _update_product_preferences(self, interaction: UserInteraction) -> None:
        """Learn product preferences from views."""
        user_id = interaction.user_id
        data = interaction.data
        
        # Track niche interests
        if niche := data.get("niche"):
            profile = self._get_user_profile(user_id)
            niche_counts = profile.setdefault("niche_interests", {})
            niche_counts[niche] = niche_counts.get(niche, 0) + 1
            self._user_profiles[user_id] = profile
        
        # Track price range preferences
        if price := data.get("price"):
            profile = self._get_user_profile(user_id)
            prices = profile.setdefault("viewed_prices", [])
            prices.append(price)
            # Keep last 100
            profile["viewed_prices"] = prices[-100:]
            self._user_profiles[user_id] = profile
    
    def _update_search_patterns(self, interaction: UserInteraction) -> None:
        """Learn from search queries."""
        user_id = interaction.user_id
        query = interaction.data.get("query", "")
        
        if not query:
            return
        
        profile = self._get_user_profile(user_id)
        searches = profile.setdefault("search_history", [])
        searches.append({
            "query": query,
            "timestamp": interaction.timestamp
        })
        # Keep last 100
        profile["search_history"] = searches[-100:]
        
        # Extract keywords
        keywords = profile.setdefault("search_keywords", {})
        for word in query.lower().split():
            if len(word) > 2:  # Skip short words
                keywords[word] = keywords.get(word, 0) + 1
        
        self._user_profiles[user_id] = profile
    
    def _update_filter_preferences(self, interaction: UserInteraction) -> None:
        """Learn filter preferences."""
        user_id = interaction.user_id
        filters = interaction.data
        
        profile = self._get_user_profile(user_id)
        filter_history = profile.setdefault("filter_preferences", {})
        
        for key, value in filters.items():
            if key not in filter_history:
                filter_history[key] = []
            filter_history[key].append({
                "value": value,
                "timestamp": interaction.timestamp
            })
            # Keep last 20 per filter
            filter_history[key] = filter_history[key][-20:]
        
        self._user_profiles[user_id] = profile
    
    def _detect_workflow_patterns(self, user_id: str) -> None:
        """Detect workflow patterns (sequences of actions)."""
        interactions = self._interactions.get(user_id, [])
        
        if len(interactions) < 3:
            return
        
        # Look at last 10 interactions for sequences
        recent = interactions[-10:]
        
        # Detect common sequences
        for i in range(len(recent) - 2):
            seq = [recent[i].type, recent[i+1].type, recent[i+2].type]
            seq_str = "->".join(seq)
            
            patterns = self._patterns[user_id]
            
            # Find or create pattern
            existing = next(
                (p for p in patterns if p.pattern_type == "workflow" and p.pattern_data.get("sequence") == seq_str),
                None
            )
            
            if existing:
                existing.occurrences += 1
                existing.last_seen = datetime.now(timezone.utc).isoformat()
                existing.confidence = min(1.0, existing.occurrences / 10)
            else:
                patterns.append(LearnedPattern(
                    pattern_type="workflow",
                    pattern_data={"sequence": seq_str},
                    confidence=0.1,
                    occurrences=1,
                    last_seen=datetime.now(timezone.utc).isoformat(),
                    first_seen=datetime.now(timezone.utc).isoformat()
                ))
    
    # ========================================================================
    # LEARNING FROM FEEDBACK
    # ========================================================================
    
    def _learn_from_feedback(self, feedback: ConversationFeedback, user_id: str) -> None:
        """Learn from user feedback on responses."""
        context = feedback.context
        
        if feedback.helpful:
            # Positive feedback - reinforce patterns
            if current_page := context.get("currentPage"):
                profile = self._get_user_profile(user_id)
                good_contexts = profile.setdefault("helpful_contexts", [])
                good_contexts.append({
                    "page": current_page,
                    "timestamp": feedback.timestamp
                })
                profile["helpful_contexts"] = good_contexts[-50:]
                self._user_profiles[user_id] = profile
        else:
            # Negative feedback - note what didn't work
            profile = self._get_user_profile(user_id)
            bad_responses = profile.setdefault("unhelpful_responses", [])
            bad_responses.append({
                "context": self._summarize_context(context),
                "comment": feedback.comment,
                "timestamp": feedback.timestamp
            })
            profile["unhelpful_responses"] = bad_responses[-50:]
            self._user_profiles[user_id] = profile
    
    # ========================================================================
    # INSIGHTS & RECOMMENDATIONS
    # ========================================================================
    
    def get_user_insights(self, user_id: str = "default") -> Dict[str, Any]:
        """Get insights about a user for personalizing Oi responses."""
        profile = self._get_user_profile(user_id)
        patterns = self._patterns.get(user_id, [])
        
        # Calculate top niches
        niche_interests = profile.get("niche_interests", {})
        top_niches = sorted(niche_interests.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Calculate average price interest
        viewed_prices = profile.get("viewed_prices", [])
        avg_price = sum(viewed_prices) / len(viewed_prices) if viewed_prices else None
        
        # Get top search keywords
        search_keywords = profile.get("search_keywords", {})
        top_keywords = sorted(search_keywords.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Get confident workflow patterns
        confident_workflows = [
            p for p in patterns 
            if p.pattern_type == "workflow" and p.confidence > 0.5
        ]
        
        return {
            "top_niches": [{"niche": n, "count": c} for n, c in top_niches],
            "avg_price_interest": avg_price,
            "price_range": {
                "min": min(viewed_prices) if viewed_prices else None,
                "max": max(viewed_prices) if viewed_prices else None,
            },
            "top_search_keywords": [{"keyword": k, "count": c} for k, c in top_keywords],
            "recent_searches": [s["query"] for s in profile.get("search_history", [])[-5:]],
            "workflow_patterns": [
                {"sequence": p.pattern_data.get("sequence"), "confidence": p.confidence}
                for p in confident_workflows[:5]
            ],
            "interactions_count": len(self._interactions.get(user_id, [])),
            "feedback_ratio": self._calculate_feedback_ratio(user_id),
        }
    
    def get_personalized_recommendations(
        self,
        user_id: str = "default",
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Get personalized recommendations based on learned patterns."""
        insights = self.get_user_insights(user_id)
        recommendations = []
        
        # Recommend based on top niches
        if top_niches := insights.get("top_niches"):
            top_niche = top_niches[0]["niche"] if top_niches else None
            if top_niche:
                recommendations.append({
                    "type": "niche_focus",
                    "message": f"Based on your browsing, you seem interested in {top_niche} products.",
                    "confidence": 0.8,
                    "action": f"Show more {top_niche} products",
                })
        
        # Price range recommendation
        if price_range := insights.get("price_range"):
            if price_range["min"] and price_range["max"]:
                recommendations.append({
                    "type": "price_filter",
                    "message": f"You typically look at products priced ${price_range['min']:.2f} - ${price_range['max']:.2f}.",
                    "confidence": 0.7,
                    "action": "Apply price filter",
                })
        
        # Search-based recommendation
        if recent_searches := insights.get("recent_searches"):
            recommendations.append({
                "type": "continue_search",
                "message": f"Continue exploring: {', '.join(recent_searches[:3])}",
                "confidence": 0.6,
            })
        
        return recommendations
    
    def get_context_enhancement(
        self,
        current_context: Dict[str, Any],
        user_id: str = "default"
    ) -> Dict[str, Any]:
        """
        Enhance the current dashboard context with learned insights.
        This is sent to Oi to make responses more personalized.
        """
        insights = self.get_user_insights(user_id)
        
        return {
            "user_preferences": {
                "top_niches": insights.get("top_niches", []),
                "price_interest": insights.get("avg_price_interest"),
                "search_keywords": insights.get("top_search_keywords", []),
            },
            "behavioral_patterns": {
                "recent_searches": insights.get("recent_searches", []),
                "workflow_patterns": insights.get("workflow_patterns", []),
            },
            "engagement_level": self._calculate_engagement_level(user_id),
            "personalization_enabled": True,
        }
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get or create user profile."""
        if user_id not in self._user_profiles:
            self._user_profiles[user_id] = {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_active": datetime.now(timezone.utc).isoformat(),
            }
        else:
            self._user_profiles[user_id]["last_active"] = datetime.now(timezone.utc).isoformat()
        return self._user_profiles[user_id]
    
    def _update_user_profile(self, interaction: UserInteraction) -> None:
        """Update user profile timestamps."""
        profile = self._get_user_profile(interaction.user_id)
        profile["last_active"] = interaction.timestamp
        self._user_profiles[interaction.user_id] = profile
    
    def _summarize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Create a summary of dashboard context for storage."""
        return {
            "page": context.get("currentPage"),
            "view": context.get("currentView"),
            "has_product": context.get("selectedProduct") is not None,
            "has_store": context.get("selectedStore") is not None,
            "visible_products_count": len(context.get("visibleProducts", [])),
            "has_metrics": context.get("storeMetrics") is not None,
        }
    
    def _calculate_feedback_ratio(self, user_id: str) -> Dict[str, Any]:
        """Calculate helpful/unhelpful feedback ratio."""
        feedback_list = self._feedback.get(user_id, [])
        if not feedback_list:
            return {"helpful": 0, "unhelpful": 0, "ratio": None}
        
        helpful = sum(1 for f in feedback_list if f.helpful)
        unhelpful = len(feedback_list) - helpful
        
        return {
            "helpful": helpful,
            "unhelpful": unhelpful,
            "ratio": helpful / len(feedback_list) if feedback_list else None,
        }
    
    def _calculate_engagement_level(self, user_id: str) -> str:
        """Calculate user engagement level."""
        interactions = self._interactions.get(user_id, [])
        
        if len(interactions) < 10:
            return "new"
        elif len(interactions) < 50:
            return "learning"
        elif len(interactions) < 200:
            return "engaged"
        else:
            return "power_user"
    
    # ========================================================================
    # PERSISTENCE
    # ========================================================================
    
    def _load_data(self) -> None:
        """Load learning data from disk."""
        try:
            profiles_path = os.path.join(self.storage_path, "user_profiles.json")
            if os.path.exists(profiles_path):
                with open(profiles_path, "r") as f:
                    self._user_profiles = json.load(f)
                logger.info(f"Loaded {len(self._user_profiles)} user profiles")
        except Exception as e:
            logger.warning(f"Failed to load learning data: {e}")
    
    def save_data(self) -> None:
        """Save learning data to disk."""
        try:
            profiles_path = os.path.join(self.storage_path, "user_profiles.json")
            with open(profiles_path, "w") as f:
                json.dump(self._user_profiles, f, indent=2)
            logger.debug(f"Saved {len(self._user_profiles)} user profiles")  # T98: debug — called per-interaction now
        except Exception as e:
            logger.error(f"Failed to save learning data: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get learning system statistics."""
        total_interactions = sum(len(i) for i in self._interactions.values())
        total_feedback = sum(len(f) for f in self._feedback.values())
        
        return {
            "total_users": len(self._user_profiles),
            "total_interactions": total_interactions,
            "total_feedback": total_feedback,
            "patterns_detected": sum(len(p) for p in self._patterns.values()),
        }


# Global learning system instance
_learning_system: Optional[OiLearningSystem] = None


def get_learning_system() -> OiLearningSystem:
    """Get or create the global learning system."""
    global _learning_system
    if _learning_system is None:
        _learning_system = OiLearningSystem()
    return _learning_system
