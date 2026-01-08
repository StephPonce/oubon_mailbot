"""
AI Cost Tracker for Usage Monitoring and Analytics

This module provides comprehensive tracking of AI usage and costs
across the OspraOS platform with database integration.

Author: OspraOS
Date: November 2025
"""

from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from functools import wraps
import logging

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from ospra_os.database.multi_store_models import (
    AIUsage,
    AIProvider as AIProviderEnum,
    TaskType,
    get_multi_store_session
)

logger = logging.getLogger(__name__)


class AICostTracker:
    """
    Track and analyze AI usage and costs for users.

    This class provides comprehensive tracking of AI API usage,
    cost analytics, budget alerts, and optimization recommendations.

    Usage:
        >>> tracker = AICostTracker()
        >>> tracker.track_usage(
        ...     user_id=1,
        ...     provider="claude",
        ...     model="claude-sonnet-4",
        ...     task_type="product_analysis",
        ...     tokens_used=1500,
        ...     estimated_cost=0.0045
        ... )
    """

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize cost tracker.

        Args:
            database_url: Optional custom database URL
        """
        self.database_url = database_url or "sqlite:///./multi_store.db"

    def _get_session(self) -> Session:
        """Get database session"""
        return get_multi_store_session(self.database_url)

    def track_usage(
        self,
        user_id: int,
        provider: str,
        model: str,
        task_type: str,
        tokens_used: int,
        estimated_cost: float,
        store_id: Optional[int] = None,
        product_id: Optional[int] = None
    ) -> AIUsage:
        """
        Track AI usage to database.

        Args:
            user_id: User ID
            provider: AI provider name ("claude", "openai", "gemini")
            model: Model name
            task_type: Type of task performed
            tokens_used: Number of tokens consumed
            estimated_cost: Estimated cost in USD
            store_id: Optional store ID
            product_id: Optional product ID

        Returns:
            AIUsage record

        Example:
            >>> usage = tracker.track_usage(
            ...     user_id=1,
            ...     provider="gemini",
            ...     model="gemini-1.5-flash",
            ...     task_type="product_analysis",
            ...     tokens_used=1500,
            ...     estimated_cost=0.000375
            ... )
        """
        session = self._get_session()

        try:
            # Convert provider string to enum
            provider_enum = AIProviderEnum(provider.lower())

            # Convert task_type string to enum
            task_type_enum = TaskType(task_type.lower())

            # Create usage record
            usage = AIUsage(
                user_id=user_id,
                provider=provider_enum,
                model=model,
                task_type=task_type_enum,
                tokens_used=tokens_used,
                estimated_cost=estimated_cost,
                store_id=store_id,
                product_id=product_id,
                created_at=datetime.utcnow()
            )

            session.add(usage)
            session.commit()
            session.refresh(usage)

            logger.info(
                f"Tracked AI usage: user={user_id}, provider={provider}, "
                f"tokens={tokens_used}, cost=${estimated_cost:.6f}"
            )

            return usage

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to track AI usage: {e}")
            raise

        finally:
            session.close()

    def get_user_costs(
        self,
        user_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get total costs for a user over specified period.

        Args:
            user_id: User ID
            days: Number of days to look back (default 30)

        Returns:
            Dictionary with cost breakdown

        Example:
            >>> costs = tracker.get_user_costs(user_id=1, days=30)
            >>> print(f"Total: ${costs['total_cost']:.2f}")
            >>> print(f"By provider: {costs['by_provider']}")
        """
        session = self._get_session()

        try:
            # Calculate date threshold
            since_date = datetime.utcnow() - timedelta(days=days)

            # Get all usage for user in period
            usage_records = session.query(AIUsage).filter(
                and_(
                    AIUsage.user_id == user_id,
                    AIUsage.created_at >= since_date
                )
            ).all()

            # Calculate totals
            total_cost = sum(r.estimated_cost for r in usage_records)
            total_tokens = sum(r.tokens_used for r in usage_records)

            # Group by provider
            by_provider = {}
            for provider in AIProviderEnum:
                provider_records = [r for r in usage_records if r.provider == provider]
                if provider_records:
                    by_provider[provider.value] = {
                        "cost": sum(r.estimated_cost for r in provider_records),
                        "tokens": sum(r.tokens_used for r in provider_records),
                        "requests": len(provider_records)
                    }

            # Group by task type
            by_task_type = {}
            for task_type in TaskType:
                task_records = [r for r in usage_records if r.task_type == task_type]
                if task_records:
                    by_task_type[task_type.value] = {
                        "cost": sum(r.estimated_cost for r in task_records),
                        "tokens": sum(r.tokens_used for r in task_records),
                        "requests": len(task_records)
                    }

            return {
                "total_cost": round(total_cost, 4),
                "total_tokens": total_tokens,
                "total_requests": len(usage_records),
                "period_days": days,
                "by_provider": by_provider,
                "by_task_type": by_task_type,
                "avg_cost_per_request": round(total_cost / len(usage_records), 4) if usage_records else 0,
                "avg_tokens_per_request": round(total_tokens / len(usage_records), 0) if usage_records else 0
            }

        finally:
            session.close()

    def get_usage_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Get comprehensive usage statistics for a user.

        Args:
            user_id: User ID

        Returns:
            Dictionary with usage statistics

        Example:
            >>> stats = tracker.get_usage_stats(user_id=1)
            >>> print(f"Most used: {stats['most_used_provider']}")
            >>> print(f"Total spent: ${stats['lifetime_cost']:.2f}")
        """
        session = self._get_session()

        try:
            # Get all usage for user
            all_usage = session.query(AIUsage).filter(
                AIUsage.user_id == user_id
            ).all()

            if not all_usage:
                return {
                    "lifetime_cost": 0,
                    "lifetime_tokens": 0,
                    "total_requests": 0,
                    "most_used_provider": None,
                    "most_common_task": None
                }

            # Calculate lifetime totals
            lifetime_cost = sum(r.estimated_cost for r in all_usage)
            lifetime_tokens = sum(r.tokens_used for r in all_usage)

            # Find most used provider
            provider_counts = {}
            for provider in AIProviderEnum:
                count = len([r for r in all_usage if r.provider == provider])
                if count > 0:
                    provider_counts[provider.value] = count

            most_used_provider = max(provider_counts.items(), key=lambda x: x[1])[0] if provider_counts else None

            # Find most common task type
            task_counts = {}
            for task_type in TaskType:
                count = len([r for r in all_usage if r.task_type == task_type])
                if count > 0:
                    task_counts[task_type.value] = count

            most_common_task = max(task_counts.items(), key=lambda x: x[1])[0] if task_counts else None

            # Recent activity (last 7 days)
            recent_date = datetime.utcnow() - timedelta(days=7)
            recent_usage = [r for r in all_usage if r.created_at >= recent_date]

            return {
                "lifetime_cost": round(lifetime_cost, 2),
                "lifetime_tokens": lifetime_tokens,
                "total_requests": len(all_usage),
                "most_used_provider": most_used_provider,
                "most_common_task": most_common_task,
                "avg_cost_per_request": round(lifetime_cost / len(all_usage), 4),
                "avg_tokens_per_request": round(lifetime_tokens / len(all_usage), 0),
                "recent_activity": {
                    "last_7_days_cost": round(sum(r.estimated_cost for r in recent_usage), 2),
                    "last_7_days_requests": len(recent_usage)
                }
            }

        finally:
            session.close()

    def check_budget_alert(
        self,
        user_id: int,
        monthly_budget: float,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Check if user is approaching or exceeding budget.

        Args:
            user_id: User ID
            monthly_budget: Monthly budget in USD
            days: Period to check (default 30)

        Returns:
            Alert dictionary with status and recommendations

        Example:
            >>> alert = tracker.check_budget_alert(
            ...     user_id=1,
            ...     monthly_budget=50.00
            ... )
            >>> if alert['exceeded']:
            ...     print(alert['message'])
        """
        costs = self.get_user_costs(user_id, days)
        total_cost = costs['total_cost']

        percentage_used = (total_cost / monthly_budget * 100) if monthly_budget > 0 else 0

        alert = {
            "total_cost": total_cost,
            "monthly_budget": monthly_budget,
            "percentage_used": round(percentage_used, 1),
            "exceeded": total_cost > monthly_budget,
            "warning": percentage_used > 80,
            "status": "ok"
        }

        if total_cost > monthly_budget:
            alert["status"] = "exceeded"
            alert["message"] = (
                f"[WARNING] Budget exceeded! You've spent ${total_cost:.2f} "
                f"of your ${monthly_budget:.2f} budget "
                f"({percentage_used:.0f}%)."
            )
            alert["recommendation"] = self._get_cost_optimization_recommendation(user_id, costs)

        elif percentage_used > 80:
            alert["status"] = "warning"
            alert["message"] = (
                f"[WARNING] Budget warning: You've used {percentage_used:.0f}% "
                f"of your ${monthly_budget:.2f} monthly budget."
            )
            alert["recommendation"] = "Consider switching to a cheaper provider to stay within budget."

        else:
            alert["status"] = "ok"
            alert["message"] = (
                f"[SUCCESS] Budget on track: ${total_cost:.2f} used "
                f"of ${monthly_budget:.2f} ({percentage_used:.0f}%)."
            )

        return alert

    def get_provider_comparison(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Compare actual costs across providers for a user.

        Args:
            user_id: User ID
            days: Period to analyze

        Returns:
            Provider comparison with recommendations

        Example:
            >>> comparison = tracker.get_provider_comparison(user_id=1)
            >>> print(comparison['cheapest_provider'])
            >>> print(comparison['potential_savings'])
        """
        costs = self.get_user_costs(user_id, days)

        if not costs['by_provider']:
            return {
                "providers_used": [],
                "cheapest_provider": None,
                "most_expensive_provider": None,
                "potential_savings": 0
            }

        # Sort providers by cost
        providers_by_cost = sorted(
            costs['by_provider'].items(),
            key=lambda x: x[1]['cost']
        )

        cheapest = providers_by_cost[0]
        most_expensive = providers_by_cost[-1]

        # Calculate potential savings if user switched to cheapest
        total_tokens = costs['total_tokens']
        current_cost = costs['total_cost']

        # Estimate cost if all requests used cheapest provider
        # (Simplified - assumes average token usage)
        cheapest_provider_name = cheapest[0]
        cost_per_token = {
            "gemini": 0.00025 / 1000,
            "claude": 0.003 / 1000,
            "openai": 0.015 / 1000
        }

        estimated_cheapest_cost = total_tokens * cost_per_token.get(cheapest_provider_name, 0)
        potential_savings = max(0, current_cost - estimated_cheapest_cost)

        return {
            "providers_used": [p[0] for p in providers_by_cost],
            "cheapest_provider": cheapest_provider_name,
            "most_expensive_provider": most_expensive[0],
            "cost_breakdown": costs['by_provider'],
            "potential_savings": round(potential_savings, 2),
            "recommendation": (
                f"[TIP] Switch to {cheapest_provider_name} to save up to "
                f"${potential_savings:.2f}/month ({days} day period)."
            ) if potential_savings > 1.0 else "You're already using cost-effective providers!"
        }

    def _get_cost_optimization_recommendation(
        self,
        user_id: int,
        costs: Dict[str, Any]
    ) -> str:
        """Generate cost optimization recommendation"""

        # Check which providers are being used
        providers = costs.get('by_provider', {})

        if not providers:
            return "Start using Gemini for the most cost-effective AI provider."

        # If using expensive providers, recommend switching
        if 'openai' in providers:
            return (
                "[TIP] Switch from OpenAI to Gemini to reduce costs by 60x. "
                "Gemini provides excellent quality at a fraction of the cost."
            )

        if 'claude' in providers and 'gemini' not in providers:
            return (
                "[TIP] Switch from Claude to Gemini for high-volume tasks. "
                "Gemini is 12x cheaper while maintaining excellent quality. "
                "Reserve Claude for critical analysis only."
            )

        if 'gemini' in providers:
            return (
                "[SUCCESS] You're already using Gemini, the most cost-effective provider. "
                "Consider reducing usage frequency or optimizing prompts to reduce token usage."
            )

        return "Consider using cheaper AI providers to reduce costs."


# ============================================================================
# DECORATOR FOR AUTO-TRACKING
# ============================================================================

def track_ai_call(
    task_type: str,
    tracker: Optional[AICostTracker] = None
):
    """
    Decorator to automatically track AI API calls.

    Args:
        task_type: Type of task being performed
        tracker: Optional AICostTracker instance (creates new if None)

    Usage:
        @track_ai_call(task_type="product_analysis")
        async def analyze_product(user_id: int, product_data: dict):
            provider = get_ai_provider("gemini", api_key="...")
            result = await provider.analyze_product(product_data)
            return result

    Note: The decorated function must return a dict with 'provider' and
    'tokens_used' keys for tracking to work properly.
    """
    if tracker is None:
        tracker = AICostTracker()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Call the original function
            result = await func(*args, **kwargs)

            # Extract tracking information from result
            if isinstance(result, dict) and '_tracking' in result:
                tracking = result.pop('_tracking')

                try:
                    tracker.track_usage(
                        user_id=tracking.get('user_id'),
                        provider=tracking.get('provider'),
                        model=tracking.get('model'),
                        task_type=task_type,
                        tokens_used=tracking.get('tokens_used', 0),
                        estimated_cost=tracking.get('estimated_cost', 0.0),
                        store_id=tracking.get('store_id'),
                        product_id=tracking.get('product_id')
                    )
                except Exception as e:
                    logger.warning(f"Failed to track AI usage: {e}")

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Call the original function
            result = func(*args, **kwargs)

            # Extract tracking information from result
            if isinstance(result, dict) and '_tracking' in result:
                tracking = result.pop('_tracking')

                try:
                    tracker.track_usage(
                        user_id=tracking.get('user_id'),
                        provider=tracking.get('provider'),
                        model=tracking.get('model'),
                        task_type=task_type,
                        tokens_used=tracking.get('tokens_used', 0),
                        estimated_cost=tracking.get('estimated_cost', 0.0),
                        store_id=tracking.get('store_id'),
                        product_id=tracking.get('product_id')
                    )
                except Exception as e:
                    logger.warning(f"Failed to track AI usage: {e}")

            return result

        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def get_cost_tracker(database_url: Optional[str] = None) -> AICostTracker:
    """
    Get a cost tracker instance.

    Args:
        database_url: Optional custom database URL

    Returns:
        AICostTracker instance

    Example:
        >>> tracker = get_cost_tracker()
        >>> costs = tracker.get_user_costs(user_id=1)
    """
    return AICostTracker(database_url)
