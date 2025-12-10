"""
AI Rationale Generator for Product Recommendations
Generates transparent explanations for why Ospra recommends products
"""

def generate_product_rationale(product: dict) -> dict:
    """
    Generate explanation for why this product was recommended

    Args:
        product: Product dict with scores and metrics

    Returns:
        Dict with rationale, confidence, and factors
    """

    score = product.get('score', product.get('ai_score', product.get('velocity_score', 0)))
    velocity = product.get('velocity_score', score)
    margin = product.get('profit_margin', 0)
    trend_score = product.get('trend_score', 0)
    orders = product.get('orders', product.get('sales_volume', 0))
    rating = product.get('rating', 0)

    factors = []
    rationale_parts = []
    confidence_boost = 0

    # Analyze velocity/demand
    if velocity > 80:
        factors.append({"label": "Exceptional demand velocity", "value": 15, "icon": "trend"})
        rationale_parts.append("selling rapidly across platforms")
        confidence_boost += 15
    elif velocity > 60:
        factors.append({"label": "Strong demand", "value": 10, "icon": "trend"})
        rationale_parts.append("consistent sales momentum")
        confidence_boost += 10
    elif velocity > 40:
        factors.append({"label": "Moderate demand", "value": 5, "icon": "trend"})
        rationale_parts.append("steady demand growth")
        confidence_boost += 5

    # Analyze profit margin
    if margin > 50:
        factors.append({"label": "Excellent profit margins", "value": 20, "icon": "success"})
        rationale_parts.append(f"exceptional {margin:.0f}% profit margin")
        confidence_boost += 20
    elif margin > 30:
        factors.append({"label": "Healthy margins", "value": 12, "icon": "success"})
        rationale_parts.append(f"solid {margin:.0f}% margin")
        confidence_boost += 12
    elif margin > 15:
        factors.append({"label": "Moderate margins", "value": 5, "icon": "success"})
        rationale_parts.append(f"{margin:.0f}% margin")
        confidence_boost += 5
    else:
        factors.append({"label": "Low margins", "value": -10, "icon": "warning"})
        rationale_parts.append("but watch margins closely")
        confidence_boost -= 10

    # Analyze social proof (orders/rating)
    if orders > 1000:
        factors.append({"label": "High sales volume", "value": 12, "icon": "success"})
        rationale_parts.append(f"{orders:,}+ proven sales")
        confidence_boost += 12
    elif orders > 500:
        factors.append({"label": "Good sales history", "value": 8, "icon": "success"})
        rationale_parts.append(f"{orders} sales")
        confidence_boost += 8

    if rating >= 4.5:
        factors.append({"label": "Excellent reviews", "value": 10, "icon": "success"})
        rationale_parts.append(f"{rating:.1f}★ customer satisfaction")
        confidence_boost += 10
    elif rating >= 4.0:
        factors.append({"label": "Good reviews", "value": 5, "icon": "success"})
        rationale_parts.append(f"{rating:.1f}★ rating")
        confidence_boost += 5
    elif rating < 3.5 and rating > 0:
        factors.append({"label": "Low reviews", "value": -15, "icon": "warning"})
        rationale_parts.append("but customer reviews need attention")
        confidence_boost -= 15

    # Analyze trending momentum
    if trend_score > 80:
        factors.append({"label": "Viral trending", "value": 15, "icon": "trend"})
        rationale_parts.append("trending virally on social media")
        confidence_boost += 15
    elif trend_score > 60:
        factors.append({"label": "Rising trend", "value": 8, "icon": "trend"})
        rationale_parts.append("gaining social momentum")
        confidence_boost += 8

    # Analyze competition/saturation
    saturation = product.get('saturation_score', product.get('competition_score', 50))
    if saturation < 30:
        factors.append({"label": "Low competition", "value": 12, "icon": "success"})
        rationale_parts.append("low market saturation")
        confidence_boost += 12
    elif saturation > 70:
        factors.append({"label": "High competition", "value": -8, "icon": "warning"})
        rationale_parts.append("but watch for market saturation")
        confidence_boost -= 8

    # Build rationale string
    if rationale_parts:
        rationale = f"This product shows {', '.join(rationale_parts[:3])}. "
    else:
        rationale = "This product meets baseline criteria for dropshipping. "

    # Add niche context if available
    niche = product.get('niche', '')
    if niche:
        rationale += f"Strong performer in the {niche} niche. "

    # Calculate confidence (base score + boosts, capped at 95%)
    base_confidence = min(score, 70)  # Use AI score as base
    confidence = min(95, max(35, base_confidence + confidence_boost))

    # Add confidence-based recommendation
    if confidence >= 80:
        rationale += "Strong buy signal based on multi-source validation. Recommended for immediate deployment."
    elif confidence >= 65:
        rationale += "Moderate confidence - good potential with manageable risk. Consider testing with small inventory."
    elif confidence >= 50:
        rationale += "Lower confidence - recommend manual review and market research before deploying."
    else:
        rationale += "Below recommended threshold - consider higher-scoring alternatives."

    return {
        "rationale": rationale,
        "confidence": int(confidence),
        "factors": factors[:5]  # Limit to top 5 factors for clarity
    }


def generate_niche_rationale(niche_data: dict) -> dict:
    """Generate rationale for niche recommendations"""

    demand = niche_data.get('demand_score', 0)
    saturation = niche_data.get('saturation', 50)
    trend = niche_data.get('trend_direction', 'stable')

    factors = []
    parts = []

    if demand > 70:
        factors.append({"label": "High market demand", "value": 15, "icon": "trend"})
        parts.append("strong buyer interest")

    if saturation < 40:
        factors.append({"label": "Low competition", "value": 12, "icon": "success"})
        parts.append("underserved market opportunity")
    elif saturation > 70:
        factors.append({"label": "Saturated market", "value": -10, "icon": "warning"})
        parts.append("but competition is high")

    if trend == 'rising':
        factors.append({"label": "Growing trend", "value": 10, "icon": "trend"})
        parts.append("upward momentum")

    rationale = f"This niche shows {', '.join(parts)}. " if parts else "Baseline niche opportunity. "

    confidence = min(90, demand + (100 - saturation) / 2)

    return {
        "rationale": rationale,
        "confidence": int(confidence),
        "factors": factors
    }
