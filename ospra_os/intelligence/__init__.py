"""
Ospra OS Intelligence Module

Claude AI business advisor integration
"""

from .claude_advisor import (
    ClaudeBusinessAdvisor,
    get_daily_briefing,
    get_weekly_report,
    chat_with_claude
)

try:
    from .opportunity_scorer import (
        OpportunityScorer,
        get_opportunity_scorer,
        score_opportunity,
        find_opportunities,
        OpportunityTier,
        OpportunityScore
    )
    _HAS_OPPORTUNITY_SCORER = True
except ImportError:
    _HAS_OPPORTUNITY_SCORER = False

__all__ = [
    'ClaudeBusinessAdvisor',
    'get_daily_briefing',
    'get_weekly_report',
    'chat_with_claude',
    # Opportunity Scorer
    'OpportunityScorer',
    'get_opportunity_scorer',
    'score_opportunity',
    'find_opportunities',
    'OpportunityTier',
    'OpportunityScore'
]
