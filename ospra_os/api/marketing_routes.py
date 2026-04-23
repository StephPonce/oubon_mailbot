"""
Marketing API Routes
====================

Marketing angle generation and A/B testing endpoints.

Author: OspraOS
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/marketing", tags=["Marketing"])


# ============================================================================
# REQUEST MODELS
# ============================================================================

class MarketingAngleRequest(BaseModel):
    """Request to generate a marketing angle."""
    product_name: str = Field(..., min_length=1, max_length=300)
    product_description: str = Field(..., min_length=1, max_length=2000)
    niche: str = Field(default="smart_home", max_length=100)
    user_brand_voice: str = Field(default="professional", max_length=100)
    user_target_audience: str = Field(default="general", max_length=200)
    avoid_angles: Optional[List[str]] = Field(default=None, max_length=20)


class MultipleAnglesRequest(BaseModel):
    """Request to generate multiple marketing angles."""
    product_name: str = Field(..., min_length=1, max_length=300)
    product_description: str = Field(..., min_length=1, max_length=2000)
    niche: str = Field(default="smart_home", max_length=100)
    num_angles: int = Field(default=3, ge=1, le=5)
    user_brand_voice: str = Field(default="professional", max_length=100)
    user_target_audience: str = Field(default="general", max_length=200)


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/generate-angle")
async def generate_marketing_angle(request: MarketingAngleRequest):
    """
    Generate unique marketing angle for a product.

    Creates AI-powered marketing positioning to differentiate users
    selling the same products. Each user gets a unique angle.

    Returns:
        Marketing angle with title, description, target audience,
        pain points, benefits, CTA, ad copy, and hashtags
    """
    try:
        from ospra_os.intelligence.marketing_angle_generator import MarketingAngleGenerator

        generator = MarketingAngleGenerator(ai_provider='claude')

        angle = await generator.generate_unique_angle(
            product_name=request.product_name,
            product_description=request.product_description,
            user_brand_voice=request.user_brand_voice,
            user_target_audience=request.user_target_audience,
            niche=request.niche,
            avoid_angles=request.avoid_angles or []
        )

        return {
            "success": True,
            "angle": angle
        }

    except Exception as e:
        logger.error(f"Marketing angle generation failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": "Marketing angle generation failed. Please try again."
        }


@router.post("/generate-multiple-angles")
async def generate_multiple_angles(request: MultipleAnglesRequest):
    """
    Generate multiple marketing angles for A/B testing.

    Creates several different marketing angles for the same product
    to test which resonates best with the audience.

    Returns:
        List of marketing angles for A/B testing
    """
    try:
        from ospra_os.intelligence.marketing_angle_generator import MarketingAngleGenerator

        num_angles = min(max(request.num_angles, 1), 5)
        generator = MarketingAngleGenerator(ai_provider='claude')

        angles = await generator.generate_multiple_angles(
            product_name=request.product_name,
            product_description=request.product_description,
            niche=request.niche,
            num_angles=num_angles,
            user_brand_voice=request.user_brand_voice,
            user_target_audience=request.user_target_audience
        )

        return {
            "success": True,
            "count": len(angles),
            "angles": angles,
            "recommendation": "Test each angle with a small audience to see which performs best"
        }

    except Exception as e:
        logger.error(f"Multiple angles generation failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": "Marketing angle generation failed. Please try again."
        }


@router.get("/available-angles")
async def get_available_angles(niche: str = "smart_home"):
    """
    Get list of available marketing angles for a niche.

    Returns all possible marketing angles that can be used
    for products in the specified niche.

    Returns:
        List of available angles and their descriptions
    """
    try:
        from ospra_os.intelligence.marketing_angle_generator import MarketingAngleGenerator

        generator = MarketingAngleGenerator(ai_provider='claude')
        angles = generator.get_available_angles(niche)

        angle_details = []
        for angle in angles:
            details = generator.get_angle_description(angle)
            angle_details.append(details)

        return {
            "success": True,
            "niche": niche,
            "count": len(angles),
            "angles": angle_details
        }

    except Exception as e:
        logger.error(f"Failed to get available angles: {e}", exc_info=True)
        return {
            "success": False,
            "error": "Failed to retrieve available angles. Please try again."
        }


logger.info("[SUCCESS] Marketing routes loaded")
