"""AI-powered competitive pricing and optimization."""

from openai import OpenAI
from ospra_os.core.settings import get_settings
from typing import Dict, List
import json


class PriceOptimizer:
    """Analyze competitor pricing and suggest optimal prices using AI."""

    def __init__(self):
        self.settings = get_settings()
        self.openai = OpenAI(api_key=self.settings.OPENAI_API_KEY)

    async def analyze_pricing(
        self,
        product_name: str,
        aliexpress_cost: float,
        niche: str,
        trend_score: float = 0
    ) -> Dict:
        """
        Analyze competitor pricing and suggest optimal price using AI.

        Args:
            product_name: Product name
            aliexpress_cost: Cost from AliExpress supplier
            niche: Product category
            trend_score: Google Trends score (0-100)

        Returns:
            {
                "suggested_price": 29.99,
                "profit_margin": 65.5,
                "profit_per_sale": 19.49,
                "compare_at_price": 49.99,
                "competitor_prices": [24.99, 29.99, 34.99],
                "reasoning": "AI explanation of pricing strategy",
                "pricing_strategy": "premium|competitive|value"
            }
        """

        print(f"💰 Analyzing pricing for: {product_name}")
        print(f"   Cost: ${aliexpress_cost}")

        # Try to find competitor prices (would integrate real scraping later)
        competitor_prices = await self._find_competitor_prices(product_name)

        if not competitor_prices:
            # No competitors found - use intelligent markup based on cost tier
            print("   ℹ️  No competitors found, using intelligent markup...")

            if aliexpress_cost < 5:
                markup = 4.0  # 300% profit margin for very cheap items
                compare_markup = 5.0
            elif aliexpress_cost < 10:
                markup = 3.5  # 250% profit margin
                compare_markup = 4.5
            elif aliexpress_cost < 20:
                markup = 3.0  # 200% profit margin
                compare_markup = 4.0
            elif aliexpress_cost < 50:
                markup = 2.5  # 150% profit margin
                compare_markup = 3.5
            else:
                markup = 2.0  # 100% profit margin for expensive items
                compare_markup = 3.0

            suggested_price = round(aliexpress_cost * markup, 2)
            compare_at_price = round(aliexpress_cost * compare_markup, 2)
            profit = suggested_price - aliexpress_cost
            margin = (profit / suggested_price) * 100

            return {
                "suggested_price": suggested_price,
                "profit_margin": round(margin, 1),
                "profit_per_sale": round(profit, 2),
                "compare_at_price": compare_at_price,
                "competitor_prices": [],
                "reasoning": f"Using {markup}x cost markup based on price tier (${aliexpress_cost}). This provides healthy {margin:.0f}% margins while staying competitive. Compare-at price creates perceived value.",
                "pricing_strategy": "value"
            }

        # Use AI to determine optimal price based on competitors
        avg_competitor = sum(competitor_prices) / len(competitor_prices)
        min_competitor = min(competitor_prices)
        max_competitor = max(competitor_prices)

        print(f"   📊 Competitors: ${min_competitor} - ${max_competitor} (avg: ${avg_competitor})")

        prompt = f"""
You are a pricing strategist for an e-commerce dropshipping store.

Product: {product_name}
Our Cost: ${aliexpress_cost}
Competitor Prices: ${min_competitor} - ${max_competitor} (avg: ${avg_competitor})
Category: {niche}
Trend Score: {trend_score}/100 (Higher = more demand)

Determine the optimal selling price that:
1. Maximizes profit margin (target 50-70%)
2. Stays competitive (within 15% of average competitor price)
3. Accounts for marketing costs (~$3-6 per sale for ads)
4. Considers perceived value and psychological pricing
5. Uses .99 or .95 endings (e.g., 29.99 not 30.00)

Also suggest a "compare at" price (the "was $XX.XX" strikethrough price) that:
- Is 30-50% higher than suggested price
- Creates urgency and perceived value
- Feels realistic (not absurdly high)

Provide response in JSON:
{{
    "suggested_price": float,
    "compare_at_price": float,
    "reasoning": "2-3 sentence explanation of pricing strategy",
    "pricing_strategy": "premium|competitive|value"
}}

Pricing Strategies:
- Premium: Top 25% of market (high quality perception, trending products)
- Competitive: Middle 50% (balanced value/quality)
- Value: Bottom 25% (price-conscious buyers)
"""

        try:
            response = self.openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert e-commerce pricing strategist specializing in dropshipping and profit optimization."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent pricing
                response_format={"type": "json_object"}
            )

            pricing_data = json.loads(response.choices[0].message.content)

            suggested_price = pricing_data["suggested_price"]
            compare_at_price = pricing_data.get("compare_at_price", suggested_price * 1.4)
            profit = suggested_price - aliexpress_cost
            margin = (profit / suggested_price) * 100

            print(f"   ✅ Price: ${suggested_price}")
            print(f"   📊 Margin: {margin:.1f}%")
            print(f"   💰 Profit: ${profit:.2f}/sale")

            return {
                "suggested_price": round(suggested_price, 2),
                "profit_margin": round(margin, 1),
                "profit_per_sale": round(profit, 2),
                "compare_at_price": round(compare_at_price, 2),
                "competitor_prices": competitor_prices,
                "reasoning": pricing_data["reasoning"],
                "pricing_strategy": pricing_data["pricing_strategy"]
            }

        except Exception as e:
            print(f"⚠️  AI pricing failed: {e}")
            # Fallback to simple competitive pricing
            suggested_price = round(avg_competitor * 0.95, 2)  # 5% below average
            compare_at_price = round(suggested_price * 1.4, 2)
            profit = suggested_price - aliexpress_cost
            margin = (profit / suggested_price) * 100

            return {
                "suggested_price": suggested_price,
                "profit_margin": round(margin, 1),
                "profit_per_sale": round(profit, 2),
                "compare_at_price": compare_at_price,
                "competitor_prices": competitor_prices,
                "reasoning": "Priced 5% below market average for competitive advantage. Compare-at price shows value.",
                "pricing_strategy": "competitive"
            }

    async def _find_competitor_prices(self, product_name: str) -> List[float]:
        """
        Try to find competitor prices.

        For now, returns empty list. Can be enhanced later with:
        - Google Shopping API
        - Amazon Product API
        - Web scraping (ScraperAPI, etc.)
        """
        # Future: Integrate with Google Shopping API or scraping service
        return []
