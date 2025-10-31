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

__all__ = [
    'ClaudeBusinessAdvisor',
    'get_daily_briefing',
    'get_weekly_report',
    'chat_with_claude'
]
