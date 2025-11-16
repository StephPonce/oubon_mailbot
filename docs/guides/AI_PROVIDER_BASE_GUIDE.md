# AI Provider Base Class - Complete Guide

**Module:** `ospra_os.ai.providers.base`
**Status:** Production Ready
**Date:** November 14, 2025

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Abstract Base Class](#abstract-base-class)
4. [Abstract Methods](#abstract-methods)
5. [Concrete Methods](#concrete-methods)
6. [Error Handling](#error-handling)
7. [Usage Examples](#usage-examples)
8. [Creating a New Provider](#creating-a-new-provider)
9. [Best Practices](#best-practices)

---

## Overview

The `AIProvider` abstract base class defines a consistent interface for all AI providers in the OspraOS system. This abstraction allows seamless switching between providers (Claude, OpenAI, Gemini, Grok) without changing application code.

### Key Benefits

- ✅ **Consistent Interface**: All providers implement the same methods
- ✅ **Easy Provider Switching**: Change providers with configuration only
- ✅ **Type Safety**: Full TypeScript-style type hints
- ✅ **Cost Tracking**: Built-in token usage and cost monitoring
- ✅ **Error Handling**: Standardized exception hierarchy
- ✅ **Extensibility**: Easy to add new providers

---

## Architecture

```
AIProvider (Abstract Base Class)
├── ClaudeProvider (Implementation)
├── OpenAIProvider (Implementation)
├── GeminiProvider (Implementation)
└── GrokProvider (Implementation - Coming Soon)
```

### Design Pattern

This uses the **Abstract Factory Pattern** combined with **Strategy Pattern**:

- **Abstract Factory**: `AIProvider` defines the interface
- **Strategy Pattern**: Different implementations can be swapped at runtime

---

## Abstract Base Class

### Class Definition

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

class AIProvider(ABC):
    """Abstract base class for all AI providers"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.provider_name = "base"
        self.model_name = "unknown"
        self.cost_per_1k = 0.0
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `api_key` | str | API key for the provider |
| `provider_name` | str | Provider identifier (claude, openai, gemini) |
| `model_name` | str | Specific model (claude-sonnet-4, gpt-4, etc.) |
| `cost_per_1k` | float | Cost per 1,000 tokens in USD |
| `_total_tokens_used` | int | Total tokens used (internal tracking) |
| `_total_cost` | float | Total cost incurred (internal tracking) |
| `_request_count` | int | Number of API requests (internal tracking) |

---

## Abstract Methods

All providers **must** implement these methods.

### 1. analyze_product()

**Purpose:** Analyze a product and return AI-powered intelligence about its market potential.

**Signature:**
```python
async def analyze_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
```

**Input:**
```python
product_data = {
    "name": "Smart LED Strip Lights",
    "niche": "smart_home",
    "trend_score": 85.5,
    "supplier_cost": 12.50,  # Optional
    "description": "RGB LED strips...",  # Optional
    "features": ["WiFi", "16M colors"],  # Optional
    "images": ["url1", "url2"]  # Optional
}
```

**Output:**
```python
{
    "score": 8.5,  # Overall score (0-10)
    "explanation": "This product has strong market demand...",
    "recommendations": [
        "Focus on smart home automation angle",
        "Bundle with voice assistant compatibility",
        "Target tech-savvy homeowners"
    ],
    "risks": [
        "Competitive market with established brands",
        "Requires app development for full features"
    ],
    "target_audience": "Tech enthusiasts aged 25-45...",
    "pricing_suggestion": 29.99,
    "confidence": 0.85,  # Confidence level (0-1)
    "market_insights": "Smart home market growing 25% YoY...",
    "competitive_advantage": "Unique voice control integration"
}
```

**Example Implementation:**
```python
class ClaudeProvider(AIProvider):
    async def analyze_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        # Validate input
        self.validate_product_data(product_data)

        # Build prompt
        prompt = f"""Analyze this product for e-commerce potential:
        Name: {product_data['name']}
        Niche: {product_data['niche']}
        Trend Score: {product_data.get('trend_score', 'N/A')}

        Provide a comprehensive analysis..."""

        # Call Claude API
        response = await self._call_api(prompt)

        # Parse and return
        return self._parse_analysis(response)
```

---

### 2. generate_description()

**Purpose:** Generate SEO-optimized product descriptions and marketing copy.

**Signature:**
```python
async def generate_description(self, product: Dict[str, Any]) -> Dict[str, Any]:
```

**Input:**
```python
product = {
    "name": "Wireless Earbuds Pro",
    "niche": "electronics",
    "features": [
        "Active Noise Cancellation",
        "30-hour battery life",
        "IPX7 waterproof"
    ],
    "target_market": "US",
    "specifications": {
        "driver_size": "10mm",
        "bluetooth": "5.2"
    },
    "benefits": [
        "Crystal clear audio",
        "All-day comfort"
    ]
}
```

**Output:**
```python
{
    "title": "Wireless Earbuds Pro - 30Hr Battery ANC IPX7 Waterproof",
    "description": """
        <h2>Experience Premium Sound</h2>
        <p>Immerse yourself in crystal-clear audio with our Wireless Earbuds Pro...</p>
        <h3>Key Features</h3>
        <ul>
            <li>Active Noise Cancellation blocks up to 95% of ambient noise</li>
            <li>30-hour battery life keeps you listening all day</li>
        </ul>
    """,
    "bullet_points": [
        "🎵 Premium 10mm drivers deliver rich, balanced sound",
        "🔇 Active Noise Cancellation for immersive listening",
        "🔋 30-hour total battery life with charging case",
        "💧 IPX7 waterproof rating for workouts and rain",
        "⚡ Bluetooth 5.2 for stable, lag-free connection"
    ],
    "meta_description": "Premium wireless earbuds with ANC, 30hr battery, IPX7 waterproof. Perfect sound quality for music lovers. Free shipping!",
    "tags": [
        "wireless earbuds",
        "ANC headphones",
        "bluetooth earbuds",
        "waterproof earbuds",
        "long battery earbuds"
    ],
    "headline": "Your Music, Your Way - Premium Sound On The Go",
    "call_to_action": "Order Now - Free 2-Day Shipping!"
}
```

---

### 3. chat()

**Purpose:** Conversational AI assistant for dashboard interactions.

**Signature:**
```python
async def chat(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
```

**Input:**
```python
message = "What products should I add to my smart home store?"

context = {
    "current_products": [
        {"name": "Smart Bulbs", "revenue": 1250.50},
        {"name": "Smart Plugs", "revenue": 890.30}
    ],
    "store_metrics": {
        "niche": "smart_home",
        "total_revenue": 2140.80,
        "conversion_rate": 2.3
    },
    "recent_activity": [
        "Added Smart Bulbs 2 days ago",
        "Revenue up 15% this week"
    ],
    "user_preferences": {
        "budget": "medium",
        "risk_tolerance": "moderate"
    }
}
```

**Output:**
```python
"""Based on your smart home store's performance, I recommend adding these products:

1. **Smart Door Locks** ($45-65 price range)
   - Complements your current product line
   - High profit margins (60%+)
   - Growing 35% annually

2. **Motion Sensors** ($20-30 price range)
   - Natural upsell with smart bulbs
   - Low competition
   - Easy to market

3. **Smart Thermostats** ($80-120 price range)
   - Premium product for higher AOV
   - Strong customer demand
   - Great reviews

Your store is performing well with smart bulbs. These additions will increase your average order value and appeal to customers already interested in home automation.

Would you like me to analyze any of these products in detail?"""
```

---

### 4. optimize_pricing()

**Purpose:** Suggest optimal pricing strategy for maximum profitability.

**Signature:**
```python
async def optimize_pricing(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
```

**Input:**
```python
product_data = {
    "name": "Premium Yoga Mat",
    "supplier_cost": 8.50,
    "competitor_prices": [19.99, 24.99, 29.99, 34.99],
    "niche": "fitness",
    "target_market": "US",
    "desired_margin": 65.0  # Optional: desired profit margin %
}
```

**Output:**
```python
{
    "suggested_price": 22.99,
    "compare_at_price": 29.99,  # "Was" price for discount perception
    "profit_margin": 63.0,  # Actual margin percentage
    "strategy": "competitive",  # competitive/premium/value
    "reasoning": """
        Based on analysis of 4 competitors, I recommend $22.99:

        - Undercuts 75% of competitors
        - Maintains healthy 63% margin
        - Creates value perception vs $29.99 "compare at"
        - Sweet spot for fitness product pricing

        This competitive pricing will drive volume while
        maintaining strong profitability.
    """,
    "price_range": {
        "min": 19.99,  # Minimum viable price
        "max": 34.99,  # Maximum market will bear
        "optimal": 22.99
    },
    "market_position": "mid-range competitive"
}
```

---

### 5. test_connection()

**Purpose:** Verify API credentials are valid.

**Signature:**
```python
async def test_connection(self) -> bool:
```

**Usage:**
```python
provider = ClaudeProvider(api_key="sk-ant-...")

try:
    is_valid = await provider.test_connection()
    if is_valid:
        print("✅ API key is valid")
    else:
        print("❌ API key is invalid")
except APIKeyError as e:
    print(f"Error: {e}")
```

**Returns:**
- `True`: API key is valid and connection works
- `False`: API key is invalid or connection failed

**Raises:**
- `APIKeyError`: If API key format is invalid

---

## Concrete Methods

These methods are already implemented in the base class.

### 1. get_model_info()

Get information about the current provider and model.

```python
info = provider.get_model_info()
print(info)
```

**Output:**
```python
{
    "provider": "claude",
    "model": "claude-sonnet-4",
    "cost_per_1k_tokens": 0.003,
    "total_tokens_used": 15420,
    "total_cost": 0.0463,
    "request_count": 12
}
```

---

### 2. calculate_cost()

Calculate cost for a given number of tokens.

```python
cost = provider.calculate_cost(5000)
print(f"Cost for 5K tokens: ${cost}")  # $0.015
```

---

### 3. track_usage()

Track token usage after API calls.

```python
# After making an API call
tokens_used = 1250
provider.track_usage(tokens_used)

# Check updated stats
info = provider.get_model_info()
print(f"Total tokens: {info['total_tokens_used']}")
print(f"Total cost: ${info['total_cost']}")
```

---

### 4. reset_usage()

Reset usage statistics.

```python
provider.reset_usage()
info = provider.get_model_info()
print(info['total_tokens_used'])  # 0
```

---

### 5. validate_product_data()

Validate product data before processing.

```python
try:
    provider.validate_product_data({
        "name": "Test Product",
        "niche": "electronics"
    })
    print("✅ Data is valid")
except ValueError as e:
    print(f"❌ Validation error: {e}")
```

---

## Error Handling

### Exception Hierarchy

```
AIProviderError (Base)
├── APIKeyError
├── RateLimitError
└── InvalidResponseError
```

### Error Classes

#### AIProviderError
Base exception for all AI provider errors.

```python
class AIProviderError(Exception):
    """Base exception for AI provider errors"""
    pass
```

#### APIKeyError
Raised when API key is invalid or missing.

```python
try:
    provider = ClaudeProvider(api_key="")
except APIKeyError as e:
    print(f"API Key Error: {e}")
```

#### RateLimitError
Raised when API rate limit is exceeded.

```python
try:
    result = await provider.analyze_product(product_data)
except RateLimitError:
    print("Rate limit exceeded. Please wait and retry.")
    await asyncio.sleep(60)  # Wait 1 minute
```

#### InvalidResponseError
Raised when API returns invalid or unexpected data.

```python
try:
    description = await provider.generate_description(product)
except InvalidResponseError as e:
    print(f"Invalid response: {e}")
    # Fallback to template-based description
```

---

## Usage Examples

### Example 1: Using a Provider

```python
from ospra_os.ai.providers import ClaudeProvider

async def analyze_my_product():
    # Initialize provider
    provider = ClaudeProvider(api_key="sk-ant-...")

    # Test connection
    if not await provider.test_connection():
        print("Failed to connect")
        return

    # Analyze product
    result = await provider.analyze_product({
        "name": "Smart Watch Pro",
        "niche": "electronics",
        "trend_score": 92.5,
        "supplier_cost": 35.00
    })

    print(f"Score: {result['score']}/10")
    print(f"Explanation: {result['explanation']}")
    print(f"Recommendations: {result['recommendations']}")

    # Check usage
    info = provider.get_model_info()
    print(f"Cost: ${info['total_cost']}")

# Run
await analyze_my_product()
```

---

### Example 2: Provider Factory

```python
from typing import Type
from ospra_os.ai.providers import AIProvider, ClaudeProvider, OpenAIProvider

class ProviderFactory:
    """Factory for creating AI providers"""

    _providers: Dict[str, Type[AIProvider]] = {
        "claude": ClaudeProvider,
        "openai": OpenAIProvider,
        "gemini": GeminiProvider
    }

    @classmethod
    def create(cls, provider_name: str, api_key: str) -> AIProvider:
        """Create provider instance"""
        provider_class = cls._providers.get(provider_name.lower())

        if not provider_class:
            raise ValueError(f"Unknown provider: {provider_name}")

        return provider_class(api_key=api_key)

# Usage
provider = ProviderFactory.create("claude", "sk-ant-...")
result = await provider.analyze_product(product_data)
```

---

### Example 3: Switching Providers

```python
from ospra_os.core.settings import settings

async def get_ai_provider() -> AIProvider:
    """Get AI provider based on user settings"""

    # Get user preference from database or settings
    preferred_provider = settings.ai_provider  # "claude"
    custom_key = settings.custom_ai_key

    if preferred_provider == "claude":
        api_key = custom_key or settings.claude_api_key
        return ClaudeProvider(api_key=api_key)

    elif preferred_provider == "openai":
        api_key = custom_key or settings.openai_api_key
        return OpenAIProvider(api_key=api_key)

    elif preferred_provider == "gemini":
        api_key = custom_key or settings.gemini_api_key
        return GeminiProvider(api_key=api_key)

    else:
        # Default to Claude
        return ClaudeProvider(api_key=settings.claude_api_key)

# Usage
provider = await get_ai_provider()
result = await provider.analyze_product(product_data)
```

---

## Creating a New Provider

### Step-by-Step Guide

#### 1. Create Provider File

Create `/ospra_os/ai/providers/my_provider.py`:

```python
from ospra_os.ai.providers.base import AIProvider, InvalidResponseError
from typing import Dict, Any, Optional
import httpx

class MyProvider(AIProvider):
    """Custom AI Provider implementation"""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.provider_name = "myprovider"
        self.model_name = "my-model-v1"
        self.cost_per_1k = 0.002
        self.api_url = "https://api.myprovider.com/v1"

    async def analyze_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Implement product analysis"""
        self.validate_product_data(product_data)

        # Build API request
        payload = {
            "model": self.model_name,
            "prompt": self._build_analysis_prompt(product_data)
        }

        # Call API
        response = await self._call_api("/analyze", payload)

        # Track usage
        self.track_usage(response.get("tokens_used", 0))

        # Return parsed result
        return self._parse_analysis_response(response)

    async def generate_description(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Implement description generation"""
        # Similar implementation
        pass

    async def chat(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Implement chat interface"""
        # Similar implementation
        pass

    async def optimize_pricing(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Implement pricing optimization"""
        # Similar implementation
        pass

    async def test_connection(self) -> bool:
        """Test API connection"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/health",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                return response.status_code == 200
        except Exception:
            return False

    # Helper methods
    async def _call_api(self, endpoint: str, payload: dict) -> dict:
        """Make API call"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}{endpoint}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
```

#### 2. Register Provider

Add to `/ospra_os/ai/providers/__init__.py`:

```python
from ospra_os.ai.providers.my_provider import MyProvider

__all__ = [
    # ... existing exports
    "MyProvider"
]
```

#### 3. Update Factory

```python
# In ProviderFactory
_providers = {
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "myprovider": MyProvider  # Add new provider
}
```

---

## Best Practices

### 1. Always Validate Input

```python
async def analyze_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
    # ✅ Good: Validate before processing
    self.validate_product_data(product_data)

    # Process data...
```

### 2. Track Usage

```python
async def chat(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
    response = await self._call_api(message)

    # ✅ Good: Track token usage
    self.track_usage(response.get("usage", {}).get("total_tokens", 0))

    return response["content"]
```

### 3. Handle Errors Gracefully

```python
async def generate_description(self, product: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return await self._generate(product)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            # ✅ Good: Specific error for rate limits
            raise RateLimitError("API rate limit exceeded")
        else:
            raise InvalidResponseError(f"API error: {e}")
```

### 4. Use Type Hints

```python
# ✅ Good: Clear type hints
async def analyze_product(
    self,
    product_data: Dict[str, Any]
) -> Dict[str, Any]:
    pass

# ❌ Bad: No type hints
async def analyze_product(self, product_data):
    pass
```

### 5. Log Important Events

```python
import logging

logger = logging.getLogger(__name__)

async def test_connection(self) -> bool:
    try:
        result = await self._test()
        # ✅ Good: Log success
        logger.info(f"{self.provider_name} connection successful")
        return result
    except Exception as e:
        # ✅ Good: Log errors
        logger.error(f"{self.provider_name} connection failed: {e}")
        return False
```

---

## Summary

The `AIProvider` abstract base class provides:

✅ **Consistent Interface** - All providers implement the same methods
✅ **Type Safety** - Full type hints for IDE support
✅ **Cost Tracking** - Built-in token and cost monitoring
✅ **Error Handling** - Standardized exception hierarchy
✅ **Easy Extension** - Simple to add new providers
✅ **Best Practices** - Logging, validation, error handling built-in

**Next Steps:**
1. Implement ClaudeProvider (use Anthropic SDK)
2. Implement OpenAIProvider (use OpenAI SDK)
3. Implement GeminiProvider (use Google SDK)
4. Create provider factory and settings integration
5. Add provider switching to AISettings frontend

---

**Built with Python 3.12+ and AsyncIO**
**Part of OspraOS Multi-Store E-commerce System**
**November 2025**

🎉 **AI Provider abstraction layer complete!**
