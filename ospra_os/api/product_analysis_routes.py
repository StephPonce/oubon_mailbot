"""
Product Analysis & Caption Generation Routes
=============================================
AI-powered analysis and Shopify-ready caption generation.

Routes:
- POST /api/oi/analyze-product - Full AI analysis
- POST /api/oi/generate-caption - Generate Shopify caption
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
import os
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/oi", tags=["AI Analysis"])

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY') or os.getenv('CLAUDE_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')


# ============================================================================
# REQUEST MODELS
# ============================================================================

class ProductAnalysisRequest(BaseModel):
    product_id: str
    product_title: str
    product_data: Optional[Dict[str, Any]] = {}


class CaptionRequest(BaseModel):
    product_title: str
    product_niche: str = "general"
    price: float = 0
    tags: Optional[List[str]] = []


# ============================================================================
# ROUTES
# ============================================================================

@router.post("/analyze-product")
async def analyze_product(request: ProductAnalysisRequest):
    """
    Generate comprehensive AI analysis for a product.
    Uses Claude (Anthropic) or falls back to rule-based analysis.
    """
    product = request.product_data
    
    # Try Claude API
    if ANTHROPIC_API_KEY:
        try:
            analysis = await _analyze_with_claude(request.product_title, product)
            if analysis:
                return {"success": True, "analysis": analysis, "source": "claude"}
        except Exception as e:
            logger.warning(f"Claude analysis failed: {e}")
    
    # Fallback to rule-based analysis
    analysis = _generate_fallback_analysis(request.product_title, product)
    return {"success": True, "analysis": analysis, "source": "fallback"}


@router.post("/generate-caption")
async def generate_caption(request: CaptionRequest):
    """
    Generate Shopify-ready product caption.
    Professional, clean copy - NO emojis, NO hashtags.
    """
    # Try Claude API
    if ANTHROPIC_API_KEY:
        try:
            caption = await _generate_caption_with_claude(
                request.product_title,
                request.product_niche,
                request.price,
                request.tags
            )
            if caption:
                return {"success": True, "caption": caption, "source": "claude"}
        except Exception as e:
            logger.warning(f"Claude caption failed: {e}")
    
    # Fallback to template
    caption = _generate_template_caption(
        request.product_title,
        request.product_niche,
        request.price,
        request.tags
    )
    return {"success": True, "caption": caption, "source": "template"}


# ============================================================================
# CLAUDE API INTEGRATION
# ============================================================================

async def _analyze_with_claude(title: str, product: dict) -> Optional[dict]:
    """Generate analysis using Claude API"""
    
    prompt = f"""You are an e-commerce analyst for Oubon Shop, a premium smart home and lifestyle store.

Analyze this product for dropshipping potential:

Product: {title}
Niche: {product.get('niche', 'general')}
Supplier Cost: ${product.get('cost_price', 0):.2f}
Suggested Retail Price: ${product.get('suggested_price', 0):.2f}
Profit: ${product.get('profit', 0):.2f}
OI Score: {product.get('oi_score', product.get('score', 50))}/100
Demand Score: {product.get('demand_score', 50)}/100
Trend Score: {product.get('trend_score', 50)}/100
Sentiment Score: {product.get('sentiment_score', 50)}/100
Sales Count: {product.get('sales_count', 'Unknown')}
Rating: {product.get('rating', 'Unknown')}
Source: {product.get('source', 'Unknown')}

Data Sources Available: {list(product.get('data_sources', {}).keys())}

Provide a PROFESSIONAL analysis in this exact JSON format:
{{
    "summary": "Brief 2-sentence executive summary of product viability",
    "verdict": "BUY | CONSIDER | SKIP",
    "confidence": 85,
    "strengths": ["specific strength 1", "specific strength 2", "specific strength 3"],
    "risks": ["specific risk 1", "specific risk 2"],
    "target_audience": "Precise target demographic description",
    "marketing_angles": ["angle 1", "angle 2", "angle 3"],
    "ad_spend_recommendation": "Recommended daily ad budget and approach",
    "price_strategy": "Pricing recommendation with reasoning",
    "competition_assessment": "Assessment of competitive landscape",
    "seasonal_factors": "Any seasonal considerations"
}}

Be specific and data-driven. No generic advice. Only respond with valid JSON."""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            content = data["content"][0]["text"]
            import json
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            return json.loads(content.strip())
        else:
            logger.error(f"Claude API error: {response.status_code} - {response.text}")
            return None


async def _generate_caption_with_claude(title: str, niche: str, price: float, tags: list) -> Optional[str]:
    """
    Generate PROFESSIONAL Shopify product caption.
    
    Requirements:
    - NO emojis
    - NO hashtags
    - Clean, premium copywriting
    - Oubon Shop brand voice
    """
    
    prompt = f"""You are a professional copywriter for Oubon Shop, a premium smart home and lifestyle e-commerce store.

Write a Shopify product description for:

Product: {title}
Category: {niche.replace('_', ' ').title()}
Price: ${price:.2f}

STRICT REQUIREMENTS:
- NO emojis whatsoever
- NO hashtags
- NO exclamation marks in excess (max 1)
- Professional, clean, premium tone
- Oubon Shop brand voice: sophisticated, modern, trustworthy
- Focus on benefits, not features
- Create subtle urgency without being salesy
- 80-120 words maximum

STRUCTURE:
1. Opening hook (1 sentence)
2. Key benefits (2-3 short sentences)
3. Quality/trust statement (1 sentence)
4. Soft call-to-action (1 sentence)

Write ONLY the caption text. No explanations, no formatting instructions."""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 400,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=20.0
        )
        
        if response.status_code == 200:
            data = response.json()
            caption = data["content"][0]["text"].strip()
            # Double-check: remove any emojis or hashtags that slipped through
            import re
            caption = re.sub(r'[#⃣[HOT][NEW][PRICE][SUCCESS][SHIPPING][STAR][BELOW][CART][SPECIAL][TARGET][TOP][LOVE][PERFECT][SUCCESS][APPLAUSE][GIFT][PACKAGE]]', '', caption)
            caption = re.sub(r'#\w+', '', caption)
            caption = caption.strip()
            return caption
        else:
            logger.error(f"Claude caption error: {response.status_code}")
            return None


# ============================================================================
# FALLBACK GENERATORS (When API unavailable)
# ============================================================================

def _generate_fallback_analysis(title: str, product: dict) -> dict:
    """Generate rule-based analysis when API unavailable"""
    
    score = product.get('oi_score', product.get('score', 50))
    cost = product.get('cost_price', 0)
    sell = product.get('suggested_price', 0)
    profit = product.get('profit', sell - cost if sell and cost else 0)
    margin = ((sell - cost) / cost * 100) if cost > 0 else 0
    
    # Determine verdict
    if score >= 75:
        verdict = "BUY"
        confidence = 85
    elif score >= 55:
        verdict = "CONSIDER"
        confidence = 65
    else:
        verdict = "SKIP"
        confidence = 70
    
    # Generate strengths based on actual metrics
    strengths = []
    if score >= 70:
        strengths.append(f"High OI score ({score}/100) indicates strong market opportunity")
    if margin >= 100:
        strengths.append(f"Excellent profit margin of {margin:.0f}% supports aggressive ad spend")
    if product.get('sales_count', 0) > 100:
        strengths.append(f"Proven demand with {product.get('sales_count')} confirmed sales")
    if product.get('rating', 0) >= 4.5:
        strengths.append(f"Strong customer satisfaction ({product.get('rating')}/5 rating)")
    if product.get('trend_score', 0) >= 60:
        strengths.append(f"Trending momentum (trend score: {product.get('trend_score')})")
    if product.get('sentiment_score', 50) >= 65:
        strengths.append("Positive social sentiment across platforms")
    if len(strengths) < 2:
        strengths.append("Competitive entry price point")
    
    # Generate risks based on actual data
    risks = []
    if margin < 50:
        risks.append(f"Thin margin ({margin:.0f}%) limits advertising flexibility")
    if product.get('source') == 'aliexpress':
        risks.append("Extended shipping times (10-20 days) may impact customer satisfaction")
    if product.get('competition_score', 50) < 40:
        risks.append("High market saturation in this product category")
    if product.get('sentiment_score', 50) < 45:
        risks.append("Mixed social sentiment suggests quality concerns")
    if len(risks) < 1:
        risks.append("Market conditions subject to seasonal fluctuation")
    
    niche = product.get('niche', 'general').replace('_', ' ')
    
    return {
        "summary": f"{title} presents a {'strong' if score >= 70 else 'moderate' if score >= 50 else 'weak'} opportunity in the {niche} market. {'Recommended for testing with targeted ad campaigns.' if score >= 55 else 'Consider alternative products with better metrics.'}",
        "verdict": verdict,
        "confidence": confidence,
        "strengths": strengths[:4],
        "risks": risks[:3],
        "target_audience": f"Online consumers interested in {niche} products, primarily ages 25-45",
        "marketing_angles": [
            "Problem-solution focused content",
            "Social proof and user testimonials",
            "Comparison to higher-priced alternatives"
        ],
        "ad_spend_recommendation": f"Start with ${10 if score >= 70 else 5}/day, scale to ${50 if margin >= 100 else 25}/day if ROAS > 2.5",
        "price_strategy": f"${sell:.2f} optimal. Test ${sell * 1.1:.2f} for perceived premium value.",
        "competition_assessment": "Moderate competition. Differentiate through faster shipping or bundle offers.",
        "seasonal_factors": "Consistent year-round demand with potential Q4 spike"
    }


def _generate_template_caption(title: str, niche: str, price: float, tags: list) -> str:
    """
    Generate PROFESSIONAL template-based caption.
    NO emojis, NO hashtags.
    """
    
    clean_niche = niche.replace('_', ' ')
    
    # Different templates based on niche
    templates = {
        "smart_home": f"""Transform your living space with the {title}.

Designed for the modern home, this device seamlessly integrates into your daily routine while delivering exceptional performance. Experience the convenience of smart technology without the complexity.

Built to last with premium materials and backed by our satisfaction guarantee. Elevate your home today.""",

        "kitchen": f"""Elevate your culinary experience with the {title}.

This thoughtfully designed kitchen essential combines form and function, making meal preparation more efficient and enjoyable. Quality construction ensures years of reliable use.

Join thousands of home chefs who have upgraded their kitchen. Order now and experience the difference.""",

        "fitness": f"""Reach your fitness goals with the {title}.

Engineered for performance, this equipment helps you maximize every workout whether at home or on the go. Durable construction meets ergonomic design for comfort during even the most intense sessions.

Invest in your health today.""",

        "beauty": f"""Discover your best self with the {title}.

This professional-grade beauty tool brings salon results to your home. Gentle yet effective, it works with your natural beauty to enhance your daily routine.

Premium quality you can feel. Results you can see.""",

        "tech": f"""Stay ahead with the {title}.

Cutting-edge technology meets intuitive design in this must-have device. Whether for work or play, experience seamless performance that keeps up with your lifestyle.

Modern solutions for modern life. Upgrade today.""",
    }
    
    # Get template or use default
    caption = templates.get(niche)
    
    if not caption:
        caption = f"""Introducing the {title}.

Thoughtfully designed for everyday use, this {clean_niche} essential combines quality craftsmanship with practical functionality. Every detail has been considered to enhance your experience.

Premium quality at an exceptional value. Satisfaction guaranteed.

Add to your collection today."""
    
    return caption
