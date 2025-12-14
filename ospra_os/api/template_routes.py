"""
Template Vault API Routes - GROK RECOMMENDATION #12

FastAPI endpoints for action template marketplace.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ospra_os.database.connection import get_db
from ospra_os.services.template_service import TemplateService
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database.multi_store_models import User
from ospra_os.api.schemas import (
    TemplateResponse,
    TemplateBrowseResponse,
    TemplateSubmitResponse,
    TemplateUsageResponse,
    TemplatePurchaseResponse,
    TemplateReviewResponse,
    TemplateCategoriesResponse,
    TemplateStatsResponse,
)


router = APIRouter(prefix="/api/templates", tags=["templates"])


# ==================== REQUEST/RESPONSE MODELS ====================

class TemplateBase(BaseModel):
    name: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=50)
    short_description: Optional[str] = Field(None, max_length=500)
    category: str
    tags: List[str] = []
    niches: List[str] = []
    is_free: bool = True
    price: float = 0


class TemplateCreate(TemplateBase):
    actions: List[Dict[str, Any]]
    variables: List[Dict[str, Any]] = []
    requirements: Dict[str, Any] = {}


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = None
    tags: Optional[List[str]] = None
    niches: Optional[List[str]] = None
    is_free: Optional[bool] = None
    price: Optional[float] = None


class TemplateUseRequest(BaseModel):
    store_id: int
    variables: Dict[str, Any]


class TemplatePurchaseRequest(BaseModel):
    payment_token: str


class TemplateReviewRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    title: Optional[str] = None
    content: Optional[str] = None
    revenue_reported: Optional[float] = None


class TemplateFromActionsRequest(BaseModel):
    """Create template from existing action sequence"""
    name: str = Field(..., min_length=5)
    description: str = Field(..., min_length=50)
    category: str
    action_ids: List[int]  # Scheduled action IDs to convert
    is_free: bool = True
    price: float = 0
    tags: List[str] = []
    niches: List[str] = []


class BrowseTemplatesQuery(BaseModel):
    category: Optional[str] = None
    niche: Optional[str] = None
    search: Optional[str] = None
    free_only: bool = False
    sort_by: str = "popular"  # popular, rating, newest, price_low, price_high
    page: int = 1
    per_page: int = 20


# ==================== ENDPOINTS ====================

@router.get("/featured", response_model=List[TemplateResponse])
def get_featured_templates(
    limit: int = 6,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get featured templates for homepage"""
    service = TemplateService(db, user.id)
    templates = service.get_featured_templates(limit=limit)
    return [service._template_to_dict(t) for t in templates]


@router.get("/browse", response_model=TemplateBrowseResponse)
def browse_templates(
    category: Optional[str] = None,
    niche: Optional[str] = None,
    search: Optional[str] = None,
    free_only: bool = False,
    sort_by: str = "popular",
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Browse and search templates with filters

    Sort options:
    - popular: Most used templates
    - rating: Highest rated
    - newest: Recently published
    - price_low: Lowest price first
    - price_high: Highest price first
    """
    service = TemplateService(db, user.id)

    result = service.browse_templates(
        category=category,
        niche=niche,
        search=search,
        free_only=free_only,
        sort_by=sort_by,
        page=page,
        per_page=per_page
    )

    return result


@router.get("/my-templates", response_model=List[TemplateResponse])
def get_my_templates(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get templates created by current user"""
    service = TemplateService(db, user.id)
    return service.get_my_templates()


@router.get("/purchased", response_model=List[TemplateResponse])
def get_purchased_templates(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get templates purchased by current user"""
    service = TemplateService(db, user.id)
    return service.get_purchased_templates()


@router.get("/{template_id}")
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get template details

    Returns full template with actions if user has access.
    Also includes reviews and user's access status.
    """
    service = TemplateService(db, user.id)
    template = service.get_template(template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    return template


@router.post("", status_code=status.HTTP_201_CREATED)
def create_template(
    data: TemplateCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Create a new template

    Template will be in 'draft' status initially.
    Submit for review to make it available in marketplace.
    """
    service = TemplateService(db, user.id)

    try:
        template = service.create_template(
            name=data.name,
            description=data.description,
            category=data.category,
            actions=data.actions,
            variables=data.variables,
            short_description=data.short_description,
            tags=data.tags,
            niches=data.niches,
            requirements=data.requirements,
            is_free=data.is_free,
            price=data.price
        )

        return service._template_to_dict(template, full=True, include_stats=True)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/from-actions", status_code=status.HTTP_201_CREATED)
def create_template_from_actions(
    data: TemplateFromActionsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Create template from existing scheduled actions

    This converts a sequence of actions that worked well
    into a reusable template for other stores.
    """
    # TODO: Implement conversion from ScheduledAction to template format
    # For now, return placeholder
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Template creation from actions coming soon"
    )


@router.patch("/{template_id}")
def update_template(
    template_id: int,
    data: TemplateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Update a template

    Only draft templates can be fully edited.
    Published templates require creating a new version.
    """
    service = TemplateService(db, user.id)

    try:
        updates = data.dict(exclude_unset=True)
        template = service.update_template(template_id, updates)
        return service._template_to_dict(template, full=True, include_stats=True)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{template_id}/submit", response_model=TemplateSubmitResponse)
def submit_for_review(
    template_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Submit template for review

    Template will be validated and moved to 'review' status.
    Auto-approved if free, otherwise requires admin approval.
    """
    service = TemplateService(db, user.id)

    try:
        template = service.submit_for_review(template_id)

        # Auto-approve free templates
        if template.is_free:
            template = service.publish_template(template_id)

        return {
            "status": template.status,
            "message": "Template published" if template.status == "published" else "Submitted for review"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{template_id}/use", response_model=TemplateUsageResponse)
def use_template(
    template_id: int,
    data: TemplateUseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Apply template to a store

    Creates a TemplateUsage record and schedules the actions.
    Requires access to template (free, purchased, or creator).
    """
    service = TemplateService(db, user.id)

    try:
        usage = service.use_template(
            template_id=template_id,
            store_id=data.store_id,
            variables=data.variables
        )

        return {
            "usage_id": usage.id,
            "status": usage.status,
            "actions_total": usage.actions_total,
            "message": "Template applied successfully"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{template_id}/purchase", response_model=TemplatePurchaseResponse)
def purchase_template(
    template_id: int,
    data: TemplatePurchaseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Purchase a paid template

    Processes payment and grants access.
    Revenue is split 70% creator / 30% platform.
    """
    service = TemplateService(db, user.id)

    try:
        purchase = service.purchase_template(
            template_id=template_id,
            payment_token=data.payment_token
        )

        return {
            "purchase_id": purchase.id,
            "transaction_id": purchase.transaction_id,
            "amount_paid": purchase.price_paid,
            "message": "Purchase successful"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{template_id}/review", response_model=TemplateReviewResponse)
def add_review(
    template_id: int,
    data: TemplateReviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Add a review for a template

    Reviews are marked as 'verified' if user has used the template.
    Can include revenue results to help others evaluate ROI.
    """
    service = TemplateService(db, user.id)

    try:
        review = service.add_review(
            template_id=template_id,
            rating=data.rating,
            title=data.title,
            content=data.content,
            revenue_reported=data.revenue_reported
        )

        return {
            "review_id": review.id,
            "is_verified": review.is_verified,
            "message": "Review submitted successfully"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/categories/list", response_model=TemplateCategoriesResponse)
def list_categories(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get list of available template categories"""
    from ospra_os.database.template_models import TemplateCategory

    return {
        "categories": [
            {"value": cat.value, "label": cat.value.replace("_", " ").title()}
            for cat in TemplateCategory
        ]
    }


@router.get("/stats/overview", response_model=TemplateStatsResponse)
def get_marketplace_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get marketplace overview statistics"""
    from ospra_os.database.template_models import ActionTemplate
    from sqlalchemy import func

    stats = db.query(
        func.count(ActionTemplate.id).label("total_templates"),
        func.sum(ActionTemplate.uses_count).label("total_uses"),
        func.avg(ActionTemplate.avg_rating).label("avg_rating"),
        func.count(ActionTemplate.id).filter(ActionTemplate.is_featured == True).label("featured_count")
    ).filter(
        ActionTemplate.status == "published"
    ).first()

    return {
        "total_templates": stats.total_templates or 0,
        "total_uses": stats.total_uses or 0,
        "avg_rating": round(stats.avg_rating or 0, 2),
        "featured_count": stats.featured_count or 0
    }
