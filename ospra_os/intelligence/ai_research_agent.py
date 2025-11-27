import logging
import os
import asyncio
from typing import Dict, List, Optional
import anthropic
from datetime import datetime

logger = logging.getLogger(__name__)

class AIResearchAgent:
    """
    Level 2 AI Learning - Claude actually researches and thinks

    Uses Claude API to:
    - Analyze why products fail/succeed
    - Research competitors
    - Generate hypotheses
    - Provide actionable recommendations
    """

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not set - AI research disabled")
            self.enabled = False
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)
            self.enabled = True

    async def analyze_product_failure(
        self,
        product: Dict,
        performance_data: Dict,
        competitor_data: Optional[List[Dict]] = None,
        market_trends: Optional[Dict] = None
    ) -> Dict:
        """
        Deep AI analysis of why a product failed

        Args:
            product: Product details (name, price, category, etc)
            performance_data: Views, clicks, sales, conversion rate
            competitor_data: Data about competing products
            market_trends: Google Trends, seasonal data

        Returns:
            {
                'hypothesis': 'Why the product failed',
                'recommendations': ['Action 1', 'Action 2', 'Action 3'],
                'predicted_improvement': 'Expected outcome',
                'confidence': 0-100,
                'research_summary': 'What AI discovered'
            }
        """

        if not self.enabled:
            return self._fallback_analysis(product, performance_data)

        try:
            # Build comprehensive research prompt
            prompt = self._build_research_prompt(
                product,
                performance_data,
                competitor_data,
                market_trends
            )

            logger.info(f"🔬 AI analyzing product failure: {product['name']}")

            # Call Claude for deep analysis
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2000,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Parse Claude's response
            analysis_text = message.content[0].text

            # Extract structured data from response
            analysis = self._parse_analysis(analysis_text)
            analysis['raw_analysis'] = analysis_text
            analysis['analyzed_at'] = datetime.now().isoformat()

            logger.info(f"✅ AI analysis complete - confidence: {analysis['confidence']}%")

            return analysis

        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return self._fallback_analysis(product, performance_data)

    async def analyze_product_success(
        self,
        product: Dict,
        performance_data: Dict
    ) -> Dict:
        """
        Analyze why a product succeeded to replicate success
        """

        if not self.enabled:
            return {'success_factors': ['High conversion rate'], 'confidence': 50}

        try:
            prompt = f"""Analyze why this product is succeeding in e-commerce:

Product: {product['name']}
Price: ${product['price']}
Category: {product.get('category', 'Unknown')}
Rating: {product.get('rating', 0)}/5
Orders: {product.get('orders', 0):,}

Performance:
- Views: {performance_data.get('views', 0):,}
- Sales: {performance_data.get('sales', 0)}
- Conversion Rate: {performance_data.get('conversion_rate', 0):.2f}%

Identify:
1. What makes this product successful?
2. What characteristics should we replicate?
3. What similar products should we test?

Be specific and actionable."""

            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )

            analysis_text = message.content[0].text

            return {
                'success_factors': self._extract_success_factors(analysis_text),
                'replicate_strategy': self._extract_strategy(analysis_text),
                'similar_products': self._extract_similar_products(analysis_text),
                'raw_analysis': analysis_text,
                'confidence': 85
            }

        except Exception as e:
            logger.error(f"Success analysis failed: {e}")
            return {'success_factors': ['High conversion'], 'confidence': 50}

    async def research_competitors(
        self,
        product_name: str,
        category: str,
        max_competitors: int = 5
    ) -> List[Dict]:
        """
        Research competitor products using AI + web search

        Returns list of competing products with:
        - Name
        - Price range
        - Key features
        - Rating
        - Why they're selling better
        """

        if not self.enabled:
            return []

        try:
            prompt = f"""Research competitor products for dropshipping:

Product Type: {product_name}
Category: {category}

Based on your knowledge of e-commerce and product trends:
1. List 5 similar products that sell well
2. Typical price range for this category
3. Key features customers look for
4. Common reasons products in this category fail

Format as a structured analysis."""

            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )

            analysis = message.content[0].text

            # Parse competitor data from Claude's response
            competitors = self._parse_competitors(analysis)

            logger.info(f"🔍 Found {len(competitors)} competitor insights")

            return competitors

        except Exception as e:
            logger.error(f"Competitor research failed: {e}")
            return []

    async def generate_improvement_plan(
        self,
        product: Dict,
        analysis: Dict
    ) -> Dict:
        """
        Generate specific action plan to improve product performance
        """

        if not self.enabled:
            return {'actions': ['Lower price', 'Improve images'], 'priority': 'medium'}

        try:
            prompt = f"""Create an action plan to improve this underperforming product:

Product: {product['name']}
Current Price: ${product['price']}
Current Conversion: {analysis.get('conversion_rate', 0):.2f}%

Analysis Summary:
{analysis.get('hypothesis', 'Performance below expectations')}

Create a specific, step-by-step action plan:
1. Immediate actions (do this week)
2. Testing strategy (what to A/B test)
3. Expected outcomes (realistic predictions)
4. Success metrics (how to measure improvement)

Be tactical and specific."""

            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )

            plan_text = message.content[0].text

            return {
                'immediate_actions': self._extract_actions(plan_text, 'immediate'),
                'testing_strategy': self._extract_actions(plan_text, 'testing'),
                'expected_outcomes': self._extract_outcomes(plan_text),
                'success_metrics': self._extract_metrics(plan_text),
                'full_plan': plan_text
            }

        except Exception as e:
            logger.error(f"Improvement plan failed: {e}")
            return {'actions': ['Review pricing', 'Test new images'], 'priority': 'medium'}

    # Helper methods

    def _build_research_prompt(
        self,
        product: Dict,
        performance: Dict,
        competitors: Optional[List[Dict]],
        trends: Optional[Dict]
    ) -> str:
        """Build comprehensive research prompt for Claude"""

        prompt = f"""You are an e-commerce expert analyzing why a product failed. Use data analysis and market research to provide actionable insights.

PRODUCT DETAILS:
Name: {product['name']}
Price: ${product['price']}
Cost: ${product.get('cost', 0)}
Category: {product.get('category', 'Unknown')}
Rating: {product.get('rating', 0)}/5
Total Orders (from supplier): {product.get('orders', 0):,}

PERFORMANCE DATA:
Views: {performance.get('views', 0):,}
Clicks: {performance.get('clicks', 0)}
Sales: {performance.get('sales', 0)}
Conversion Rate: {performance.get('conversion_rate', 0):.2f}%

CONTEXT:
- This product has been live for {performance.get('days_live', 14)} days
- Industry average conversion: 2-3%
- This product's conversion: {performance.get('conversion_rate', 0):.2f}%
"""

        if competitors:
            prompt += f"\n\nCOMPETITOR DATA:\n"
            for i, comp in enumerate(competitors[:3], 1):
                prompt += f"{i}. {comp.get('name', 'Unknown')} - ${comp.get('price', 0)} - {comp.get('rating', 0)}★\n"

        if trends:
            prompt += f"\n\nMARKET TRENDS:\n"
            prompt += f"Category interest: {trends.get('velocity_score', 'Unknown')}/100\n"
            prompt += f"Trend direction: {trends.get('trend_direction', 'Unknown')}\n"

        prompt += """

ANALYZE AND PROVIDE:

1. HYPOTHESIS (2-3 sentences)
Why did this product fail? Be specific about the root causes.

2. RECOMMENDATIONS (3 specific actions)
What should be done to fix this? Include:
- Pricing adjustments (if needed)
- Product sourcing changes (if needed)
- Marketing/positioning changes (if needed)

3. PREDICTED IMPROVEMENT
If recommendations are followed, what's the expected new conversion rate?

4. CONFIDENCE (0-100)
How confident are you in this analysis?

Be direct, data-driven, and actionable. No fluff."""

        return prompt

    def _parse_analysis(self, text: str) -> Dict:
        """Extract structured data from Claude's response"""

        analysis = {
            'hypothesis': '',
            'recommendations': [],
            'predicted_improvement': '',
            'confidence': 70
        }

        # Simple parsing - look for sections
        lines = text.split('\n')
        current_section = None

        for line in lines:
            line = line.strip()

            if 'HYPOTHESIS' in line.upper() or 'WHY' in line.upper():
                current_section = 'hypothesis'
                continue
            elif 'RECOMMENDATION' in line.upper():
                current_section = 'recommendations'
                continue
            elif 'PREDICTED' in line.upper() or 'IMPROVEMENT' in line.upper():
                current_section = 'predicted'
                continue
            elif 'CONFIDENCE' in line.upper():
                current_section = 'confidence'
                continue

            if current_section == 'hypothesis' and line:
                analysis['hypothesis'] += line + ' '
            elif current_section == 'recommendations' and line and (line.startswith('-') or line.startswith('•') or line[0].isdigit()):
                clean_line = line.lstrip('-•0123456789. ')
                if clean_line:
                    analysis['recommendations'].append(clean_line)
            elif current_section == 'predicted' and line:
                analysis['predicted_improvement'] += line + ' '
            elif current_section == 'confidence' and line:
                # Extract number
                import re
                numbers = re.findall(r'\d+', line)
                if numbers:
                    analysis['confidence'] = int(numbers[0])

        return analysis

    def _extract_success_factors(self, text: str) -> List[str]:
        """Extract success factors from analysis"""
        factors = []
        lines = text.split('\n')
        in_factors = False

        for line in lines:
            if 'success' in line.lower() or 'factor' in line.lower():
                in_factors = True
                continue
            if in_factors and (line.startswith('-') or line.startswith('•') or line[0].isdigit()):
                clean = line.lstrip('-•0123456789. ').strip()
                if clean:
                    factors.append(clean)

        return factors[:5] if factors else ['High conversion rate', 'Good product-market fit']

    def _extract_strategy(self, text: str) -> str:
        """Extract replication strategy"""
        # Look for strategy section
        if 'replicate' in text.lower() or 'strategy' in text.lower():
            lines = text.split('\n')
            strategy_lines = []
            capture = False

            for line in lines:
                if 'replicate' in line.lower() or 'strategy' in line.lower():
                    capture = True
                    continue
                if capture and line.strip():
                    strategy_lines.append(line.strip())
                    if len(strategy_lines) >= 3:
                        break

            return ' '.join(strategy_lines)

        return "Find similar products with comparable features and pricing"

    def _extract_similar_products(self, text: str) -> List[str]:
        """Extract similar product suggestions"""
        products = []
        lines = text.split('\n')

        for line in lines:
            if 'similar' in line.lower() and any(char.isdigit() or line.startswith('-') for char in line):
                clean = line.lstrip('-•0123456789. ').strip()
                if clean and len(clean) > 10:
                    products.append(clean)

        return products[:5] if products else ['Similar items in same category']

    def _parse_competitors(self, text: str) -> List[Dict]:
        """Parse competitor data from Claude's response"""
        competitors = []

        # Simple parsing - this would be more sophisticated in production
        lines = text.split('\n')
        for line in lines:
            if any(indicator in line.lower() for indicator in ['price', '$', 'sells', 'popular']):
                if line.strip():
                    competitors.append({
                        'description': line.strip(),
                        'insights': 'Extracted from market analysis'
                    })

        return competitors[:5]

    def _extract_actions(self, text: str, action_type: str) -> List[str]:
        """Extract specific action items"""
        actions = []
        lines = text.split('\n')
        capture = False

        for line in lines:
            if action_type.lower() in line.lower():
                capture = True
                continue
            if capture and (line.startswith('-') or line.startswith('•') or line[0].isdigit()):
                clean = line.lstrip('-•0123456789. ').strip()
                if clean:
                    actions.append(clean)
                if len(actions) >= 5:
                    break

        return actions if actions else [f'{action_type.title()} actions needed']

    def _extract_outcomes(self, text: str) -> str:
        """Extract expected outcomes"""
        if 'outcome' in text.lower() or 'expect' in text.lower():
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if 'outcome' in line.lower() or 'expect' in line.lower():
                    # Get next few lines
                    outcome_lines = lines[i+1:i+4]
                    return ' '.join(l.strip() for l in outcome_lines if l.strip())

        return "Improved conversion rate and sales volume expected"

    def _extract_metrics(self, text: str) -> List[str]:
        """Extract success metrics"""
        metrics = []
        lines = text.split('\n')

        for line in lines:
            if 'metric' in line.lower() and (line.startswith('-') or line.startswith('•')):
                clean = line.lstrip('-•0123456789. ').strip()
                if clean:
                    metrics.append(clean)

        return metrics if metrics else ['Conversion rate', 'Sales volume', 'Customer reviews']

    def _fallback_analysis(self, product: Dict, performance: Dict) -> Dict:
        """Fallback analysis when AI is not available"""

        conv_rate = performance.get('conversion_rate', 0)

        if conv_rate < 1.0:
            hypothesis = f"Low conversion ({conv_rate:.2f}%) suggests pricing or product-market fit issues"
            recommendations = [
                f"Test lower price point (current: ${product['price']})",
                "Improve product images and description",
                "Research competitor offerings"
            ]
        else:
            hypothesis = "Performance below expectations despite adequate traffic"
            recommendations = [
                "Analyze customer feedback",
                "Compare with successful similar products",
                "Test different marketing angles"
            ]

        return {
            'hypothesis': hypothesis,
            'recommendations': recommendations,
            'predicted_improvement': "2-3% conversion with optimizations",
            'confidence': 50,
            'research_summary': "Basic statistical analysis (AI research not available)"
        }
