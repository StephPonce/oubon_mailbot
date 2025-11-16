"""
🔍 PRODUCT CHANGE ANALYZER
Uses Claude AI to analyze product changes and recommend actions
"""

import logging
from datetime import datetime
from typing import Dict, List
from ospra_os.intelligence.claude_analyzer_REALTIME import RealTimeClaudeAnalyzer

logger = logging.getLogger(__name__)


class ProductChangeAnalyzer:
    """Analyze product changes using Claude AI"""

    def __init__(self):
        self.claude = RealTimeClaudeAnalyzer()
        logger.info("✅ Product change analyzer initialized")

    def analyze_change(
        self,
        product_name: str,
        change_type: str,
        old_value: str,
        new_value: str,
        product_data: Dict
    ) -> Dict:
        """
        Let Claude analyze what a product change means

        Args:
            product_name: Name of the product
            change_type: Type of change (velocity, price, score)
            old_value: Previous value
            new_value: New value
            product_data: Full product data for context

        Returns:
            Analysis dict with cause, impact, action, urgency
        """

        prompt = f"""Analyze this dropshipping product change and provide actionable insights.

**Product:** {product_name}
**Change Type:** {change_type}
**Old Value:** {old_value}
**New Value:** {new_value}

**Current Product Data:**
- Price: ${product_data.get('price', 0)}
- Cost: ${product_data.get('cost', 0)}
- Velocity Score: {product_data.get('velocity_score', 0)}/100
- Orders: {product_data.get('orders', 0)}
- Rating: {product_data.get('rating', 0)}/5

**Questions to answer:**
1. What likely caused this change? (market trends, competition, seasonality, supplier changes)
2. Is this a positive or negative signal for dropshipping this product?
3. What specific action should the seller take NOW?
4. How urgent is this? (Low/Medium/High)

Be direct and actionable. Focus on profit impact and competitive advantage.

**Required format:**
CAUSE: [1-2 sentences explaining why this happened]
IMPACT: [Positive/Negative/Neutral - with brief reason]
ACTION: [Specific, actionable step the seller should take]
URGENCY: [Low/Medium/High]
EXPLANATION: [2-3 sentences on business impact]
"""

        try:
            # Use chat_response method from Claude analyzer
            response = self.claude.chat_response(prompt, context=product_data)

            # Parse response
            parsed = self._parse_analysis(response)

            return {
                "product_name": product_name,
                "change_type": change_type,
                "old_value": old_value,
                "new_value": new_value,
                "cause": parsed.get("cause", "Unknown"),
                "impact": parsed.get("impact", "Neutral"),
                "action": parsed.get("action", "Monitor situation"),
                "urgency": parsed.get("urgency", "Low"),
                "explanation": parsed.get("explanation", ""),
                "raw_analysis": response,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Change analysis failed: {e}")
            return self._get_fallback_analysis(
                product_name, change_type, old_value, new_value
            )

    def _parse_analysis(self, response: str) -> Dict:
        """Parse Claude's structured response"""
        parsed = {}

        lines = response.split('\n')
        for line in lines:
            line = line.strip()

            if line.startswith('CAUSE:'):
                parsed['cause'] = line.replace('CAUSE:', '').strip()
            elif line.startswith('IMPACT:'):
                parsed['impact'] = line.replace('IMPACT:', '').strip()
            elif line.startswith('ACTION:'):
                parsed['action'] = line.replace('ACTION:', '').strip()
            elif line.startswith('URGENCY:'):
                parsed['urgency'] = line.replace('URGENCY:', '').strip()
            elif line.startswith('EXPLANATION:'):
                parsed['explanation'] = line.replace('EXPLANATION:', '').strip()

        return parsed

    def _get_fallback_analysis(
        self,
        product_name: str,
        change_type: str,
        old_value: str,
        new_value: str
    ) -> Dict:
        """Simple rule-based analysis when Claude unavailable"""

        if change_type == "velocity":
            old_vel = int(old_value)
            new_vel = int(new_value)

            if new_vel > old_vel:
                return {
                    "product_name": product_name,
                    "change_type": change_type,
                    "old_value": old_value,
                    "new_value": new_value,
                    "cause": "Increased market demand or trending topic",
                    "impact": "Positive - Growing interest",
                    "action": "Increase ad spend and inventory",
                    "urgency": "High" if new_vel > 70 else "Medium",
                    "explanation": "Rising velocity indicates growing demand. Act quickly to capitalize on trend.",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "product_name": product_name,
                    "change_type": change_type,
                    "old_value": old_value,
                    "new_value": new_value,
                    "cause": "Declining trend or increased competition",
                    "impact": "Negative - Losing momentum",
                    "action": "Review competitors, consider price adjustment or pause ads",
                    "urgency": "Medium",
                    "explanation": "Declining velocity suggests weakening demand. Monitor closely.",
                    "timestamp": datetime.now().isoformat()
                }

        elif change_type == "price":
            return {
                "product_name": product_name,
                "change_type": change_type,
                "old_value": old_value,
                "new_value": new_value,
                "cause": "Supplier pricing change or market adjustment",
                "impact": "Neutral - Requires margin review",
                "action": "Recalculate profit margins and adjust retail price if needed",
                "urgency": "Medium",
                "explanation": "Price changes affect margins. Ensure 3x markup is maintained.",
                "timestamp": datetime.now().isoformat()
            }

        else:
            return {
                "product_name": product_name,
                "change_type": change_type,
                "old_value": old_value,
                "new_value": new_value,
                "cause": "Product data updated",
                "impact": "Neutral",
                "action": "Monitor for additional changes",
                "urgency": "Low",
                "explanation": "Change detected. Continue monitoring.",
                "timestamp": datetime.now().isoformat()
            }

    def batch_analyze_changes(self, changes: List[Dict]) -> List[Dict]:
        """
        Analyze multiple changes and prioritize

        Args:
            changes: List of change dicts with product_name, type, old, new, product_data

        Returns:
            List of analysis results, sorted by urgency
        """
        logger.info(f"Analyzing {len(changes)} product changes...")

        analyses = []

        for change in changes:
            try:
                analysis = self.analyze_change(
                    product_name=change['product_name'],
                    change_type=change['type'],
                    old_value=str(change['old']),
                    new_value=str(change['new']),
                    product_data=change.get('product_data', {})
                )
                analyses.append(analysis)

            except Exception as e:
                logger.error(f"Failed to analyze change for {change['product_name']}: {e}")
                continue

        # Sort by urgency
        urgency_order = {"High": 0, "Medium": 1, "Low": 2}
        analyses.sort(key=lambda x: urgency_order.get(x.get('urgency', 'Low'), 3))

        logger.info(f"✅ Analyzed {len(analyses)} changes")

        return analyses

    def format_analysis_report(self, analyses: List[Dict]) -> str:
        """Format analyses into readable report"""

        if not analyses:
            return "No changes to analyze."

        report = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 PRODUCT CHANGE ANALYSIS REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total Changes Analyzed: {len(analyses)}
Report Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

"""

        # Group by urgency
        high = [a for a in analyses if a.get('urgency') == 'High']
        medium = [a for a in analyses if a.get('urgency') == 'Medium']
        low = [a for a in analyses if a.get('urgency') == 'Low']

        if high:
            report += f"\n🔴 HIGH URGENCY ({len(high)}):\n"
            for analysis in high:
                report += f"\n  📦 {analysis['product_name']}\n"
                report += f"     Change: {analysis['change_type']} ({analysis['old_value']} → {analysis['new_value']})\n"
                report += f"     Impact: {analysis['impact']}\n"
                report += f"     Action: {analysis['action']}\n"
                report += f"     Cause: {analysis['cause']}\n"

        if medium:
            report += f"\n🟡 MEDIUM URGENCY ({len(medium)}):\n"
            for analysis in medium:
                report += f"\n  📦 {analysis['product_name']}\n"
                report += f"     Change: {analysis['change_type']} ({analysis['old_value']} → {analysis['new_value']})\n"
                report += f"     Action: {analysis['action']}\n"

        if low:
            report += f"\n🟢 LOW URGENCY ({len(low)}):\n"
            for analysis in low[:3]:  # Limit to 3
                report += f"  • {analysis['product_name']}: {analysis['action']}\n"
            if len(low) > 3:
                report += f"  ... and {len(low) - 3} more low priority items\n"

        report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

        return report


# Convenience function
def get_analyzer() -> ProductChangeAnalyzer:
    """Get or create analyzer instance"""
    if not hasattr(get_analyzer, '_instance'):
        get_analyzer._instance = ProductChangeAnalyzer()
    return get_analyzer._instance
