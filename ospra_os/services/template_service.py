"""
Template Service - GROK RECOMMENDATION #12

Business logic for action template marketplace.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_, or_
from datetime import datetime, timedelta, timezone
import re
import json

from ospra_os.database.template_models import (
    ActionTemplate, TemplatePurchase, TemplateUsage, TemplateReview
)


class TemplateService:
    """Service for managing action templates"""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    # ==================== BROWSE TEMPLATES ====================

    def get_featured_templates(self, limit: int = 6) -> List[ActionTemplate]:
        """Get featured templates"""
        return self.db.query(ActionTemplate).filter(
            ActionTemplate.status == "published",
            ActionTemplate.is_featured == True
        ).order_by(ActionTemplate.featured_order).limit(limit).all()

    def browse_templates(
        self,
        category: Optional[str] = None,
        niche: Optional[str] = None,
        search: Optional[str] = None,
        free_only: bool = False,
        sort_by: str = "popular",
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """Browse available templates"""

        query = self.db.query(ActionTemplate).filter(
            ActionTemplate.status == "published"
        )

        # Filters
        if category:
            query = query.filter(ActionTemplate.category == category)

        if niche:
            # Check if niches array contains the niche
            query = query.filter(
                func.json_contains(ActionTemplate.niches, json.dumps([niche]))
            )

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    ActionTemplate.name.ilike(search_term),
                    ActionTemplate.description.ilike(search_term)
                )
            )

        if free_only:
            query = query.filter(ActionTemplate.is_free == True)

        # Sorting
        if sort_by == "popular":
            query = query.order_by(desc(ActionTemplate.uses_count))
        elif sort_by == "rating":
            query = query.order_by(desc(ActionTemplate.avg_rating))
        elif sort_by == "newest":
            query = query.order_by(desc(ActionTemplate.published_at))
        elif sort_by == "price_low":
            query = query.order_by(ActionTemplate.price)
        elif sort_by == "price_high":
            query = query.order_by(desc(ActionTemplate.price))

        # Pagination
        total = query.count()
        templates = query.offset((page - 1) * per_page).limit(per_page).all()

        return {
            "templates": [self._template_to_dict(t) for t in templates],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page
        }

    def get_template(self, template_id: int) -> Optional[Dict]:
        """Get template details"""
        template = self.db.query(ActionTemplate).filter(
            ActionTemplate.id == template_id
        ).first()

        if not template:
            return None

        # Check access
        has_access = self._user_has_access(template)

        return {
            **self._template_to_dict(template, full=True),
            "has_access": has_access,
            "actions": template.actions if has_access else None,
            "reviews": self._get_template_reviews(template_id)
        }

    def get_my_templates(self) -> List[Dict]:
        """Get templates created by user"""
        templates = self.db.query(ActionTemplate).filter(
            ActionTemplate.creator_id == self.user_id
        ).order_by(desc(ActionTemplate.updated_at)).all()

        return [self._template_to_dict(t, include_stats=True) for t in templates]

    def get_purchased_templates(self) -> List[Dict]:
        """Get templates purchased by user"""
        purchases = self.db.query(TemplatePurchase).filter(
            TemplatePurchase.user_id == self.user_id,
            TemplatePurchase.status == "completed"
        ).all()

        template_ids = [p.template_id for p in purchases]

        if not template_ids:
            return []

        templates = self.db.query(ActionTemplate).filter(
            ActionTemplate.id.in_(template_ids)
        ).all()

        return [self._template_to_dict(t) for t in templates]

    # ==================== CREATE/EDIT TEMPLATES ====================

    def create_template(
        self,
        name: str,
        description: str,
        category: str,
        actions: List[Dict],
        variables: List[Dict] = None,
        **kwargs
    ) -> ActionTemplate:
        """Create a new template"""

        # Generate slug
        slug = self._generate_slug(name)

        template = ActionTemplate(
            creator_id=self.user_id,
            name=name,
            slug=slug,
            description=description,
            short_description=kwargs.get("short_description", description[:200]),
            category=category,
            actions=actions,
            variables=variables or [],
            tags=kwargs.get("tags", []),
            niches=kwargs.get("niches", []),
            requirements=kwargs.get("requirements", {}),
            is_free=kwargs.get("is_free", True),
            price=kwargs.get("price", 0),
            status="draft"
        )

        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)

        return template

    def update_template(self, template_id: int, updates: Dict) -> ActionTemplate:
        """Update a template"""
        template = self.db.query(ActionTemplate).filter(
            ActionTemplate.id == template_id,
            ActionTemplate.creator_id == self.user_id
        ).first()

        if not template:
            raise ValueError("Template not found")

        # Can't edit published templates directly
        if template.status == "published" and "actions" in updates:
            raise ValueError("Create a new version to modify published templates")

        for key, value in updates.items():
            if hasattr(template, key) and key not in ["id", "creator_id", "created_at"]:
                setattr(template, key, value)

        if "name" in updates:
            template.slug = self._generate_slug(updates["name"])

        self.db.commit()
        self.db.refresh(template)

        return template

    def submit_for_review(self, template_id: int) -> ActionTemplate:
        """Submit template for review (to be published)"""
        template = self.db.query(ActionTemplate).filter(
            ActionTemplate.id == template_id,
            ActionTemplate.creator_id == self.user_id,
            ActionTemplate.status == "draft"
        ).first()

        if not template:
            raise ValueError("Template not found or not in draft status")

        # Validate template
        errors = self._validate_template(template)
        if errors:
            raise ValueError(f"Template validation failed: {', '.join(errors)}")

        template.status = "review"
        self.db.commit()

        return template

    def publish_template(self, template_id: int) -> ActionTemplate:
        """Publish a template (admin or auto-approve for free)"""
        template = self.db.query(ActionTemplate).filter(
            ActionTemplate.id == template_id
        ).first()

        if not template:
            raise ValueError("Template not found")

        template.status = "published"
        template.published_at = datetime.now(timezone.utc)
        self.db.commit()

        return template

    # ==================== USE TEMPLATES ====================

    def use_template(
        self,
        template_id: int,
        store_id: int,
        variables: Dict[str, Any]
    ) -> TemplateUsage:
        """Start using a template"""

        template = self.db.query(ActionTemplate).filter(
            ActionTemplate.id == template_id,
            ActionTemplate.status == "published"
        ).first()

        if not template:
            raise ValueError("Template not found")

        # Check access
        if not self._user_has_access(template):
            raise ValueError("You don't have access to this template")

        # Validate variables
        self._validate_variables(template.variables, variables)

        # Create usage record
        usage = TemplateUsage(
            user_id=self.user_id,
            template_id=template_id,
            store_id=store_id,
            variables_used=variables,
            actions_total=len(template.actions),
            status="active"
        )

        self.db.add(usage)

        # Increment uses count
        template.uses_count += 1

        self.db.commit()
        self.db.refresh(usage)

        return usage

    # ==================== PURCHASE TEMPLATES ====================

    def _verify_payment_with_processor(self, payment_token: str, expected_amount: float) -> str:
        """T31: verify a payment server-side with LemonSqueezy before granting.

        The old code trusted the client-supplied token without reading it and
        fabricated a transaction id — POSTing any string bought any paid
        template for free.

        ``payment_token`` must be a LemonSqueezy order id from the checkout
        redirect. We confirm with the processor that the order (1) exists,
        (2) is paid, (3) covers the template price, (4) belongs to the calling
        user's email, and (5) hasn't already been spent on another purchase.
        Fails CLOSED: no API key / processor unreachable → no grant.

        Returns the canonical transaction id to store.
        """
        import os
        import httpx

        api_key = os.getenv("LEMONSQUEEZY_API_KEY")
        if not api_key:
            raise ValueError("Payment verification is not configured")

        order_id = (payment_token or "").strip()
        if not order_id.isdigit():
            raise ValueError("Invalid payment token")

        try:
            response = httpx.get(
                f"https://api.lemonsqueezy.com/v1/orders/{order_id}",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/vnd.api+json",
                },
                timeout=15.0,
            )
        except Exception as e:
            raise ValueError(f"Payment verification unavailable: {e}")

        if response.status_code != 200:
            raise ValueError("Payment not found")

        attributes = (response.json().get("data") or {}).get("attributes") or {}

        if attributes.get("status") != "paid":
            raise ValueError("Payment is not completed")

        # LemonSqueezy totals are in cents.
        paid_cents = int(attributes.get("total") or 0)
        if paid_cents < int(round(expected_amount * 100)):
            raise ValueError("Payment amount does not match template price")

        # The order must belong to the calling user.
        from ospra_os.database import User

        user = self.db.query(User).filter(User.id == self.user_id).first()
        order_email = (attributes.get("user_email") or "").strip().lower()
        if user is not None and getattr(user, "email", None) and order_email:
            if order_email != user.email.strip().lower():
                raise ValueError("Payment belongs to a different account")

        transaction_id = f"ls_order_{order_id}"

        # One processor payment buys exactly one purchase.
        already_used = self.db.query(TemplatePurchase).filter(
            TemplatePurchase.transaction_id == transaction_id
        ).first()
        if already_used:
            raise ValueError("This payment was already used")

        return transaction_id

    def purchase_template(
        self,
        template_id: int,
        payment_token: str
    ) -> TemplatePurchase:
        """Purchase a paid template"""

        template = self.db.query(ActionTemplate).filter(
            ActionTemplate.id == template_id,
            ActionTemplate.status == "published"
        ).first()

        if not template:
            raise ValueError("Template not found")

        if template.is_free:
            raise ValueError("This template is free")

        # Check not already purchased
        existing = self.db.query(TemplatePurchase).filter(
            TemplatePurchase.user_id == self.user_id,
            TemplatePurchase.template_id == template_id,
            TemplatePurchase.status == "completed"
        ).first()

        if existing:
            raise ValueError("Already purchased")

        # T31: verify with the processor BEFORE granting anything.
        transaction_id = self._verify_payment_with_processor(payment_token, template.price)

        # Calculate split
        creator_amount = template.price * template.revenue_share
        platform_amount = template.price - creator_amount

        purchase = TemplatePurchase(
            user_id=self.user_id,
            template_id=template_id,
            price_paid=template.price,
            creator_amount=creator_amount,
            platform_amount=platform_amount,
            transaction_id=transaction_id,
            status="completed"
        )

        self.db.add(purchase)
        self.db.commit()
        self.db.refresh(purchase)

        return purchase

    # ==================== REVIEWS ====================

    def add_review(
        self,
        template_id: int,
        rating: int,
        title: str = None,
        content: str = None,
        revenue_reported: float = None
    ) -> TemplateReview:
        """Add a review for a template"""

        if not 1 <= rating <= 5:
            raise ValueError("Rating must be 1-5")

        # Check user has used this template
        usage = self.db.query(TemplateUsage).filter(
            TemplateUsage.user_id == self.user_id,
            TemplateUsage.template_id == template_id
        ).first()

        # Check for existing review
        existing = self.db.query(TemplateReview).filter(
            TemplateReview.user_id == self.user_id,
            TemplateReview.template_id == template_id
        ).first()

        if existing:
            raise ValueError("Already reviewed this template")

        review = TemplateReview(
            user_id=self.user_id,
            template_id=template_id,
            usage_id=usage.id if usage else None,
            rating=rating,
            title=title,
            content=content,
            revenue_reported=revenue_reported,
            is_verified=usage is not None
        )

        self.db.add(review)

        # Update template rating
        self._update_template_rating(template_id)

        self.db.commit()
        self.db.refresh(review)

        return review

    # ==================== HELPERS ====================

    def _user_has_access(self, template: ActionTemplate) -> bool:
        """Check if user has access to template"""

        # Creator always has access
        if template.creator_id == self.user_id:
            return True

        # Free templates are accessible
        if template.is_free:
            return True

        # Check purchase
        purchase = self.db.query(TemplatePurchase).filter(
            TemplatePurchase.user_id == self.user_id,
            TemplatePurchase.template_id == template.id,
            TemplatePurchase.status == "completed"
        ).first()

        return purchase is not None

    def _template_to_dict(
        self,
        template: ActionTemplate,
        full: bool = False,
        include_stats: bool = False
    ) -> Dict:
        """Convert template to dictionary"""

        data = {
            "id": template.id,
            "name": template.name,
            "slug": template.slug,
            "short_description": template.short_description,
            "category": template.category,
            "tags": template.tags or [],
            "niches": template.niches or [],
            "is_free": template.is_free,
            "price": template.price,
            "uses_count": template.uses_count,
            "avg_rating": template.avg_rating,
            "ratings_count": template.ratings_count,
            "is_featured": template.is_featured,
            "actions_count": len(template.actions) if template.actions else 0,
            "creator": {
                "id": template.creator_id,
                "name": "Creator"  # Would get from User relationship
            },
            "created_at": template.created_at.isoformat(),
        }

        if full:
            data.update({
                "description": template.description,
                "variables": template.variables or [],
                "requirements": template.requirements or {},
                "version": template.version,
                "changelog": template.changelog or [],
                "status": template.status,
            })

        if include_stats:
            data.update({
                "status": template.status,
                "success_rate": template.success_rate,
                "avg_revenue_generated": template.avg_revenue_generated,
                "total_earnings": self._get_template_earnings(template.id)
            })

        return data

    def _generate_slug(self, name: str) -> str:
        """Generate URL-friendly slug"""
        slug = re.sub(r'[^a-zA-Z0-9\s-]', '', name.lower())
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = re.sub(r'-+', '-', slug).strip('-')

        # Check uniqueness
        base_slug = slug
        counter = 1
        while self.db.query(ActionTemplate).filter(
            ActionTemplate.slug == slug
        ).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug

    def _validate_template(self, template: ActionTemplate) -> List[str]:
        """Validate template before publishing"""
        errors = []

        if not template.name or len(template.name) < 5:
            errors.append("Name must be at least 5 characters")

        if not template.description or len(template.description) < 50:
            errors.append("Description must be at least 50 characters")

        if not template.actions or len(template.actions) == 0:
            errors.append("Template must have at least one action")

        if not template.is_free and template.price < 5:
            errors.append("Paid templates must be at least $5")

        return errors

    def _validate_variables(self, required: List[Dict], provided: Dict):
        """Validate user-provided variables"""
        for var in required:
            if var["name"] not in provided:
                if "default" not in var:
                    raise ValueError(f"Missing required variable: {var['name']}")

    def _get_template_reviews(self, template_id: int) -> List[Dict]:
        """Get reviews for a template"""
        reviews = self.db.query(TemplateReview).filter(
            TemplateReview.template_id == template_id,
            TemplateReview.is_approved == True
        ).order_by(desc(TemplateReview.created_at)).limit(10).all()

        return [{
            "id": r.id,
            "rating": r.rating,
            "title": r.title,
            "content": r.content,
            "is_verified": r.is_verified,
            "revenue_reported": r.revenue_reported,
            "created_at": r.created_at.isoformat()
        } for r in reviews]

    def _update_template_rating(self, template_id: int):
        """Update template's average rating"""
        result = self.db.query(
            func.avg(TemplateReview.rating),
            func.count(TemplateReview.id)
        ).filter(
            TemplateReview.template_id == template_id
        ).first()

        template = self.db.query(ActionTemplate).filter(
            ActionTemplate.id == template_id
        ).first()

        if template and result:
            template.avg_rating = float(result[0]) if result[0] else 0
            template.ratings_count = result[1]

    def _get_template_earnings(self, template_id: int) -> float:
        """Get total earnings for a template"""
        result = self.db.query(
            func.sum(TemplatePurchase.creator_amount)
        ).filter(
            TemplatePurchase.template_id == template_id,
            TemplatePurchase.status == "completed"
        ).scalar()

        return float(result) if result else 0
