"""
White-Label API Routes - GROK RECOMMENDATION #19

Routes for managing white-label partners, branding, domains, and clients.

Endpoints:
- Admin: Create/activate partners (requires admin auth)
- Partner: Manage own branding/domains/clients (requires API key auth)
- Public: Get branding for current request
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, EmailStr, Field

# T4 (unlisted finding): this import path never existed — the module ALWAYS
# failed to import, so main.py's graceful degradation silently never mounted
# /api/whitelabel/*. That's also why the admin-key-placeholder was never
# exploitable in practice: the entire white-label feature was dead. Fixed so
# the router loads — now gated by the REAL admin dependency below.
from ospra_os.database import get_db
from ospra_os.whitelabel.service import WhiteLabelService
from ospra_os.whitelabel.middleware import get_whitelabel_branding

logger = logging.getLogger(__name__)


# ==================== PYDANTIC MODELS ====================

class PartnerCreate(BaseModel):
    """Create white-label partner request"""
    company_name: str = Field(..., min_length=1, max_length=255)
    contact_name: Optional[str] = Field(None, max_length=255)
    contact_email: EmailStr
    slug: str = Field(..., min_length=2, max_length=50, pattern="^[a-z0-9-]+$")
    plan: str = Field("starter", pattern="^(starter|growth|enterprise)$")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "company_name": "E-Commerce Pros Agency",
                "contact_name": "John Smith",
                "contact_email": "admin@ecompros.io",
                "slug": "ecompros",
                "plan": "growth",
            }
        }
    )


class PartnerResponse(BaseModel):
    """White-label partner response"""
    id: int
    company_name: str
    contact_name: Optional[str]
    contact_email: str
    slug: str
    api_key: str
    plan: str
    max_clients: int
    monthly_fee: float
    status: str
    activated_at: Optional[str]

    # v2: orm_mode was renamed to from_attributes
    model_config = ConfigDict(from_attributes=True)


class BrandingUpdate(BaseModel):
    """Update branding request"""
    brand_name: Optional[str] = Field(None, max_length=100)
    tagline: Optional[str] = Field(None, max_length=255)
    logo_url: Optional[str] = Field(None, max_length=500)
    logo_dark_url: Optional[str] = Field(None, max_length=500)
    favicon_url: Optional[str] = Field(None, max_length=500)
    logo_email_url: Optional[str] = Field(None, max_length=500)
    primary_color: Optional[str] = Field(None, pattern="^#[0-9a-fA-F]{6}$")
    secondary_color: Optional[str] = Field(None, pattern="^#[0-9a-fA-F]{6}$")
    accent_color: Optional[str] = Field(None, pattern="^#[0-9a-fA-F]{6}$")
    background_color: Optional[str] = Field(None, pattern="^#[0-9a-fA-F]{6}$")
    surface_color: Optional[str] = Field(None, pattern="^#[0-9a-fA-F]{6}$")
    text_color: Optional[str] = Field(None, pattern="^#[0-9a-fA-F]{6}$")
    text_muted_color: Optional[str] = Field(None, pattern="^#[0-9a-fA-F]{6}$")
    success_color: Optional[str] = Field(None, pattern="^#[0-9a-fA-F]{6}$")
    warning_color: Optional[str] = Field(None, pattern="^#[0-9a-fA-F]{6}$")
    error_color: Optional[str] = Field(None, pattern="^#[0-9a-fA-F]{6}$")
    font_family: Optional[str] = Field(None, max_length=100)
    heading_font: Optional[str] = Field(None, max_length=100)
    custom_css: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "brand_name": "E-Commerce Pros",
                "tagline": "Your E-Commerce Success Partner",
                "logo_url": "https://ecompros.io/logo.png",
                "primary_color": "#2563eb",
                "secondary_color": "#7c3aed",
                "accent_color": "#10b981",
                "font_family": "Poppins",
            }
        }
    )


class DomainConfigure(BaseModel):
    """Configure custom domain request"""
    domain: str = Field(..., min_length=4, max_length=255)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "domain": "app.ecompros.io",
            }
        }
    )


class ClientAdd(BaseModel):
    """Add client request"""
    user_id: int
    client_name: Optional[str] = Field(None, max_length=255)
    client_email: Optional[EmailStr] = None
    plan: str = Field("basic", max_length=50)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": 42,
                "client_name": "Bob's Store",
                "client_email": "bob@bobsstore.com",
                "plan": "premium",
            }
        }
    )


# ==================== DEPENDENCIES ====================

async def get_partner_from_api_key(
    x_whitelabel_api_key: str = Header(...),
    db: Session = Depends(get_db)
):
    """Authenticate partner via API key"""
    service = WhiteLabelService(db)
    partner = service.get_partner_by_api_key(x_whitelabel_api_key)

    if not partner:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )

    if partner.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Partner account is {partner.status}"
        )

    return partner


# T4: partner-admin endpoints used to gate on a literal
# `x-admin-key: admin-key-placeholder` header — anyone who read the source (it's
# in git) had full partner-admin access (create/activate/suspend partners).
# Delegate to the real DB-backed admin dependency (is_admin/is_superuser flag).
from ospra_os.auth.jwt_auth import (  # noqa: E402
    get_current_user,
    require_admin_user as require_admin,
)


# ==================== ROUTER ====================

def get_whitelabel_router() -> APIRouter:
    """Create and configure white-label router"""
    # SECURITY (2026-08): router-level auth. Admin routes already carried
    # require_admin, but the PARTNER surface did not — POST/DELETE
    # /partner/clients, /partner/domain, /partner/domain/verify and PUT
    # /partner/branding were all anonymously callable, i.e. anyone could create
    # or delete agency clients and rewrite partner branding.
    router = APIRouter(
        prefix="/api/whitelabel",
        tags=["white-label"],
        dependencies=[Depends(get_current_user)],
    )

    # ==================== ADMIN ENDPOINTS ====================

    @router.post("/partners", response_model=PartnerResponse, dependencies=[Depends(require_admin)])
    async def create_partner(
        partner: PartnerCreate,
        db: Session = Depends(get_db)
    ):
        """
        Create a new white-label partner (admin only).

        Returns partner details including generated API key.
        """
        try:
            service = WhiteLabelService(db)
            new_partner = service.create_partner(
                company_name=partner.company_name,
                contact_email=partner.contact_email,
                slug=partner.slug,
                plan=partner.plan,
                contact_name=partner.contact_name
            )

            return PartnerResponse(
                id=new_partner.id,
                company_name=new_partner.company_name,
                contact_name=new_partner.contact_name,
                contact_email=new_partner.contact_email,
                slug=new_partner.slug,
                api_key=new_partner.api_key,
                plan=new_partner.plan,
                max_clients=new_partner.max_clients,
                monthly_fee=new_partner.monthly_fee,
                status=new_partner.status,
                activated_at=new_partner.activated_at.isoformat() if new_partner.activated_at else None
            )

        except ValueError as e:
            logger.warning(f"Partner registration validation error: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid partner registration data.")

    @router.post("/partners/{partner_id}/activate", dependencies=[Depends(require_admin)])
    async def activate_partner(
        partner_id: int,
        db: Session = Depends(get_db)
    ):
        """Activate a white-label partner (admin only)"""
        try:
            service = WhiteLabelService(db)
            partner = service.activate_partner(partner_id)

            return {
                "success": True,
                "partner_id": partner.id,
                "status": partner.status,
                "activated_at": partner.activated_at.isoformat()
            }

        except ValueError as e:
            logger.warning(f"Partner activation error: {e}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found or cannot be activated.")

    @router.post("/partners/{partner_id}/suspend", dependencies=[Depends(require_admin)])
    async def suspend_partner(
        partner_id: int,
        reason: Optional[str] = None,
        db: Session = Depends(get_db)
    ):
        """Suspend a white-label partner (admin only)"""
        try:
            service = WhiteLabelService(db)
            partner = service.suspend_partner(partner_id, reason)

            return {
                "success": True,
                "partner_id": partner.id,
                "status": partner.status
            }

        except ValueError as e:
            logger.warning(f"Partner suspension error: {e}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found or cannot be suspended.")

    # ==================== PARTNER ENDPOINTS ====================

    @router.get("/partner/me")
    async def get_partner_info(
        partner = Depends(get_partner_from_api_key)
    ):
        """Get partner information"""
        return {
            "id": partner.id,
            "company_name": partner.company_name,
            "slug": partner.slug,
            "plan": partner.plan,
            "max_clients": partner.max_clients,
            "status": partner.status,
            "settings": partner.settings
        }

    @router.get("/partner/branding")
    async def get_partner_branding(
        partner = Depends(get_partner_from_api_key),
        db: Session = Depends(get_db)
    ):
        """Get partner branding configuration"""
        service = WhiteLabelService(db)
        branding = service.get_branding(partner.id)

        if not branding:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branding not found")

        return {
            "brand_name": branding.brand_name,
            "tagline": branding.tagline,
            "logo_url": branding.logo_url,
            "logo_dark_url": branding.logo_dark_url,
            "favicon_url": branding.favicon_url,
            "logo_email_url": branding.logo_email_url,
            "colors": {
                "primary": branding.primary_color,
                "secondary": branding.secondary_color,
                "accent": branding.accent_color,
                "background": branding.background_color,
                "surface": branding.surface_color,
                "text": branding.text_color,
                "textMuted": branding.text_muted_color,
                "success": branding.success_color,
                "warning": branding.warning_color,
                "error": branding.error_color
            },
            "fonts": {
                "family": branding.font_family,
                "heading": branding.heading_font
            },
            "custom_css": branding.custom_css,
            "ui_config": branding.ui_config
        }

    @router.put("/partner/branding")
    async def update_partner_branding(
        branding_update: BrandingUpdate,
        partner = Depends(get_partner_from_api_key),
        db: Session = Depends(get_db)
    ):
        """Update partner branding"""
        try:
            service = WhiteLabelService(db)

            # Filter out None values
            update_data = {k: v for k, v in branding_update.dict().items() if v is not None}

            branding = service.update_branding(partner.id, **update_data)

            return {
                "success": True,
                "message": "Branding updated successfully"
            }

        except ValueError as e:
            logger.warning(f"Branding update error: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid branding data.")

    @router.get("/partner/branding/css")
    async def get_partner_css(
        partner = Depends(get_partner_from_api_key),
        db: Session = Depends(get_db)
    ):
        """Get CSS variables for partner branding"""
        service = WhiteLabelService(db)
        css = service.generate_css_variables(partner.id)

        return {
            "css": css
        }

    @router.post("/partner/domain")
    async def configure_partner_domain(
        domain_config: DomainConfigure,
        partner = Depends(get_partner_from_api_key),
        db: Session = Depends(get_db)
    ):
        """Configure custom domain for partner"""
        try:
            service = WhiteLabelService(db)
            domain = service.configure_domain(partner.id, domain_config.domain)

            instructions = service.get_domain_instructions(partner.id)

            return {
                "success": True,
                "domain": domain.domain,
                "status": domain.status,
                "instructions": instructions
            }

        except ValueError as e:
            logger.warning(f"Domain configuration error: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid domain configuration.")

    @router.get("/partner/domain")
    async def get_partner_domain(
        partner = Depends(get_partner_from_api_key),
        db: Session = Depends(get_db)
    ):
        """Get domain configuration and instructions"""
        service = WhiteLabelService(db)
        instructions = service.get_domain_instructions(partner.id)

        if not instructions:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not configured")

        return instructions

    @router.post("/partner/domain/verify")
    async def verify_partner_domain(
        partner = Depends(get_partner_from_api_key),
        db: Session = Depends(get_db)
    ):
        """Verify domain DNS configuration"""
        try:
            service = WhiteLabelService(db)
            results = service.verify_domain(partner.id)

            # `verified` comes straight from the service now — it used to be
            # derived from two flags the service hardcoded to True.
            return {
                "success": True,
                "verified": bool(results.get("verified")),
                "details": results,
            }

        except ValueError as e:
            logger.warning(f"Domain verification error: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Domain verification failed.")

    @router.get("/partner/clients")
    async def get_partner_clients(
        active_only: bool = True,
        partner = Depends(get_partner_from_api_key),
        db: Session = Depends(get_db)
    ):
        """Get all clients for partner"""
        service = WhiteLabelService(db)
        clients = service.get_clients(partner.id, active_only=active_only)

        return {
            "total": len(clients),
            "max_clients": partner.max_clients,
            "clients": [
                {
                    "id": c.id,
                    "user_id": c.user_id,
                    "client_name": c.client_name,
                    "client_email": c.client_email,
                    "plan": c.plan,
                    "is_active": c.is_active,
                    "created_at": c.created_at.isoformat()
                }
                for c in clients
            ]
        }

    @router.post("/partner/clients")
    async def add_partner_client(
        client: ClientAdd,
        partner = Depends(get_partner_from_api_key),
        db: Session = Depends(get_db)
    ):
        """Add a client to partner"""
        try:
            service = WhiteLabelService(db)
            new_client = service.add_client(
                partner_id=partner.id,
                user_id=client.user_id,
                client_name=client.client_name,
                client_email=client.client_email,
                plan=client.plan
            )

            return {
                "success": True,
                "client": {
                    "id": new_client.id,
                    "user_id": new_client.user_id,
                    "client_name": new_client.client_name,
                    "client_email": new_client.client_email,
                    "plan": new_client.plan
                }
            }

        except ValueError as e:
            logger.warning(f"Client addition error: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to add client. Client limit may be exceeded.")

    @router.delete("/partner/clients/{user_id}")
    async def remove_partner_client(
        user_id: int,
        partner = Depends(get_partner_from_api_key),
        db: Session = Depends(get_db)
    ):
        """Remove a client from partner"""
        service = WhiteLabelService(db)
        success = service.remove_client(partner.id, user_id)

        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

        return {
            "success": True,
            "message": "Client removed successfully"
        }

    @router.get("/partner/analytics")
    async def get_partner_analytics(
        days: int = 30,
        partner = Depends(get_partner_from_api_key),
        db: Session = Depends(get_db)
    ):
        """Get analytics for partner"""
        service = WhiteLabelService(db)
        analytics = service.get_partner_analytics(partner.id, days=days)

        return analytics

    # ==================== PUBLIC ENDPOINTS ====================

    @router.get("/branding")
    async def get_current_branding(request: Request):
        """
        Get white-label branding for current request.
        Resolves based on domain, slug parameter, or user association.
        """
        branding = get_whitelabel_branding(request)

        if not branding:
            return {
                "whitelabel": False,
                "brand_name": "Ospra",
                "message": "Default branding"
            }

        return {
            "whitelabel": True,
            **branding
        }

    return router


# Export router getter
__all__ = ["get_whitelabel_router"]
