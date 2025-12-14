"""
White-Label Service - GROK RECOMMENDATION #19

Service for managing white-label partners, branding, domains, and clients.
"""

import secrets
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from ospra_os.database.whitelabel_models import (
    WhiteLabelPartner, WhiteLabelBranding, WhiteLabelDomain,
    WhiteLabelEmailSettings, WhiteLabelClient, WhiteLabelAnalytics
)

logger = logging.getLogger(__name__)


class WhiteLabelService:
    """Service for managing white-label partners and branding"""

    def __init__(self, db: Session):
        self.db = db

    # ==================== PARTNER MANAGEMENT ====================

    def create_partner(
        self,
        company_name: str,
        contact_email: str,
        slug: str,
        plan: str = "starter",
        contact_name: str = None
    ) -> WhiteLabelPartner:
        """Create a new white-label partner"""

        # Validate slug
        existing = self.db.query(WhiteLabelPartner).filter(
            WhiteLabelPartner.slug == slug
        ).first()
        if existing:
            raise ValueError(f"Slug '{slug}' already exists")

        # Generate API key
        api_key = f"wl_{secrets.token_urlsafe(32)}"

        # Plan limits
        plan_limits = {
            "starter": {"max_clients": 10, "monthly_fee": 299},
            "growth": {"max_clients": 50, "monthly_fee": 799},
            "enterprise": {"max_clients": 500, "monthly_fee": 1999}
        }
        limits = plan_limits.get(plan, plan_limits["starter"])

        partner = WhiteLabelPartner(
            company_name=company_name,
            contact_name=contact_name,
            contact_email=contact_email,
            slug=slug,
            api_key=api_key,
            plan=plan,
            max_clients=limits["max_clients"],
            monthly_fee=limits["monthly_fee"],
            status="pending"
        )

        self.db.add(partner)
        self.db.commit()
        self.db.refresh(partner)

        # Create default branding
        branding = WhiteLabelBranding(
            partner_id=partner.id,
            brand_name=company_name
        )
        self.db.add(branding)

        # Create default email settings
        email_settings = WhiteLabelEmailSettings(
            partner_id=partner.id,
            from_name=company_name,
            from_email=contact_email
        )
        self.db.add(email_settings)

        self.db.commit()

        logger.info(f"Created white-label partner: {company_name} ({slug})")

        return partner

    def get_partner(self, partner_id: int) -> Optional[WhiteLabelPartner]:
        """Get partner by ID"""
        return self.db.query(WhiteLabelPartner).filter(
            WhiteLabelPartner.id == partner_id
        ).first()

    def get_partner_by_slug(self, slug: str) -> Optional[WhiteLabelPartner]:
        """Get partner by slug"""
        return self.db.query(WhiteLabelPartner).filter(
            WhiteLabelPartner.slug == slug
        ).first()

    def get_partner_by_domain(self, domain: str) -> Optional[WhiteLabelPartner]:
        """Get partner by custom domain"""
        wl_domain = self.db.query(WhiteLabelDomain).filter(
            WhiteLabelDomain.domain == domain,
            WhiteLabelDomain.status == "active"
        ).first()

        if wl_domain:
            return wl_domain.partner
        return None

    def get_partner_by_api_key(self, api_key: str) -> Optional[WhiteLabelPartner]:
        """Get partner by API key"""
        return self.db.query(WhiteLabelPartner).filter(
            WhiteLabelPartner.api_key == api_key
        ).first()

    def activate_partner(self, partner_id: int) -> WhiteLabelPartner:
        """Activate a partner account"""
        partner = self.get_partner(partner_id)
        if not partner:
            raise ValueError("Partner not found")

        partner.status = "active"
        partner.activated_at = datetime.utcnow()
        self.db.commit()

        logger.info(f"Activated partner: {partner.company_name}")

        return partner

    def suspend_partner(self, partner_id: int, reason: str = None) -> WhiteLabelPartner:
        """Suspend a partner account"""
        partner = self.get_partner(partner_id)
        if not partner:
            raise ValueError("Partner not found")

        partner.status = "suspended"
        if reason:
            if partner.settings is None:
                partner.settings = {}
            partner.settings["suspension_reason"] = reason

        self.db.commit()

        return partner

    # ==================== BRANDING ====================

    def update_branding(
        self,
        partner_id: int,
        **kwargs
    ) -> WhiteLabelBranding:
        """Update partner branding"""

        branding = self.db.query(WhiteLabelBranding).filter(
            WhiteLabelBranding.partner_id == partner_id
        ).first()

        if not branding:
            raise ValueError("Branding not found")

        # Update provided fields
        for key, value in kwargs.items():
            if value is not None and hasattr(branding, key):
                setattr(branding, key, value)

        self.db.commit()
        self.db.refresh(branding)

        logger.info(f"Updated branding for partner {partner_id}")

        return branding

    def get_branding(self, partner_id: int) -> Optional[WhiteLabelBranding]:
        """Get partner branding"""
        return self.db.query(WhiteLabelBranding).filter(
            WhiteLabelBranding.partner_id == partner_id
        ).first()

    def generate_css_variables(self, partner_id: int) -> str:
        """Generate CSS variables for a partner's branding"""

        branding = self.get_branding(partner_id)
        if not branding:
            return ""

        css = f"""
:root {{
    --wl-primary: {branding.primary_color};
    --wl-secondary: {branding.secondary_color};
    --wl-accent: {branding.accent_color};
    --wl-background: {branding.background_color};
    --wl-surface: {branding.surface_color};
    --wl-text: {branding.text_color};
    --wl-text-muted: {branding.text_muted_color};
    --wl-success: {branding.success_color};
    --wl-warning: {branding.warning_color};
    --wl-error: {branding.error_color};
    --wl-font-family: '{branding.font_family}', system-ui, sans-serif;
    --wl-heading-font: '{branding.heading_font or branding.font_family}', system-ui, sans-serif;
}}
"""

        if branding.custom_css:
            css += f"\n/* Custom CSS */\n{branding.custom_css}"

        return css

    # ==================== CUSTOM DOMAIN ====================

    def configure_domain(
        self,
        partner_id: int,
        domain: str
    ) -> WhiteLabelDomain:
        """Configure custom domain for partner"""

        # Check if domain already exists
        existing = self.db.query(WhiteLabelDomain).filter(
            WhiteLabelDomain.domain == domain
        ).first()
        if existing and existing.partner_id != partner_id:
            raise ValueError("Domain already registered to another partner")

        # Get or create domain record
        wl_domain = self.db.query(WhiteLabelDomain).filter(
            WhiteLabelDomain.partner_id == partner_id
        ).first()

        if wl_domain:
            wl_domain.domain = domain
            wl_domain.dns_verified = False
            wl_domain.status = "pending"
        else:
            wl_domain = WhiteLabelDomain(
                partner_id=partner_id,
                domain=domain,
                dns_verification_token=secrets.token_urlsafe(16)
            )
            self.db.add(wl_domain)

        self.db.commit()
        self.db.refresh(wl_domain)

        logger.info(f"Configured domain {domain} for partner {partner_id}")

        return wl_domain

    def get_domain_instructions(self, partner_id: int) -> Dict:
        """Get DNS configuration instructions"""

        wl_domain = self.db.query(WhiteLabelDomain).filter(
            WhiteLabelDomain.partner_id == partner_id
        ).first()

        if not wl_domain:
            return None

        return {
            "domain": wl_domain.domain,
            "status": wl_domain.status,
            "instructions": {
                "step_1": {
                    "type": "CNAME",
                    "name": wl_domain.domain,
                    "value": wl_domain.cname_target,
                    "description": f"Point {wl_domain.domain} to our servers"
                },
                "step_2": {
                    "type": "TXT",
                    "name": f"_ospra-verify.{wl_domain.domain}",
                    "value": wl_domain.dns_verification_token,
                    "description": "Verify domain ownership"
                }
            },
            "dns_verified": wl_domain.dns_verified,
            "ssl_status": wl_domain.ssl_status
        }

    def verify_domain(self, partner_id: int) -> Dict:
        """Verify domain DNS configuration (mock verification for now)"""

        wl_domain = self.db.query(WhiteLabelDomain).filter(
            WhiteLabelDomain.partner_id == partner_id
        ).first()

        if not wl_domain:
            raise ValueError("Domain not configured")

        # In production, this would use dnspython to check DNS records
        # For now, simulate verification
        results = {
            "cname_verified": True,  # Mock
            "txt_verified": True  # Mock
        }

        # Update status
        if results["cname_verified"] and results["txt_verified"]:
            wl_domain.dns_verified = True
            wl_domain.dns_verified_at = datetime.utcnow()
            wl_domain.status = "active"
            wl_domain.ssl_status = "active"  # Mock SSL provisioning
            wl_domain.ssl_provisioned_at = datetime.utcnow()

        self.db.commit()

        logger.info(f"Verified domain for partner {partner_id}")

        return results

    # ==================== CLIENT MANAGEMENT ====================

    def add_client(
        self,
        partner_id: int,
        user_id: int,
        client_name: str = None,
        client_email: str = None,
        plan: str = "basic"
    ) -> WhiteLabelClient:
        """Add a client to a white-label partner"""

        partner = self.get_partner(partner_id)
        if not partner:
            raise ValueError("Partner not found")

        # Check client limit
        current_clients = self.db.query(WhiteLabelClient).filter(
            WhiteLabelClient.partner_id == partner_id,
            WhiteLabelClient.is_active == True
        ).count()

        if current_clients >= partner.max_clients:
            raise ValueError(f"Client limit reached ({partner.max_clients})")

        # Check if user already has a white-label association
        existing = self.db.query(WhiteLabelClient).filter(
            WhiteLabelClient.user_id == user_id
        ).first()
        if existing:
            raise ValueError("User already associated with a white-label partner")

        client = WhiteLabelClient(
            partner_id=partner_id,
            user_id=user_id,
            client_name=client_name,
            client_email=client_email,
            plan=plan
        )

        self.db.add(client)
        self.db.commit()
        self.db.refresh(client)

        logger.info(f"Added client {user_id} to partner {partner_id}")

        return client

    def get_clients(
        self,
        partner_id: int,
        active_only: bool = True
    ) -> List[WhiteLabelClient]:
        """Get all clients for a partner"""

        query = self.db.query(WhiteLabelClient).filter(
            WhiteLabelClient.partner_id == partner_id
        )

        if active_only:
            query = query.filter(WhiteLabelClient.is_active == True)

        return query.all()

    def get_client_for_user(self, user_id: int) -> Optional[WhiteLabelClient]:
        """Get white-label client record for a user"""
        return self.db.query(WhiteLabelClient).filter(
            WhiteLabelClient.user_id == user_id
        ).first()

    def remove_client(self, partner_id: int, user_id: int) -> bool:
        """Remove a client from a partner"""

        client = self.db.query(WhiteLabelClient).filter(
            WhiteLabelClient.partner_id == partner_id,
            WhiteLabelClient.user_id == user_id
        ).first()

        if client:
            client.is_active = False
            self.db.commit()
            return True

        return False

    # ==================== BRANDING RESOLUTION ====================

    def resolve_branding_for_request(
        self,
        domain: str = None,
        slug: str = None,
        user_id: int = None
    ) -> Optional[Dict]:
        """
        Resolve branding based on request context.
        Priority: domain > user's partner > slug > default
        """

        partner = None

        # Try domain first
        if domain and domain not in ["localhost", "ospra.io", "app.ospra.io", "127.0.0.1"]:
            partner = self.get_partner_by_domain(domain)

        # Try user's partner association
        if not partner and user_id:
            client = self.get_client_for_user(user_id)
            if client:
                partner = client.partner

        # Try slug
        if not partner and slug:
            partner = self.get_partner_by_slug(slug)

        # Return branding if found
        if partner and partner.status == "active":
            branding = self.get_branding(partner.id)
            if branding:
                return {
                    "partner_id": partner.id,
                    "partner_slug": partner.slug,
                    "brand_name": branding.brand_name,
                    "tagline": branding.tagline,
                    "logo_url": branding.logo_url,
                    "logo_dark_url": branding.logo_dark_url,
                    "favicon_url": branding.favicon_url,
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
                    "ui_config": branding.ui_config,
                    "custom_css": branding.custom_css,
                    "settings": partner.settings
                }

        # Return default Ospra branding
        return None

    # ==================== ANALYTICS ====================

    def get_partner_analytics(
        self,
        partner_id: int,
        days: int = 30
    ) -> Dict:
        """Get analytics for a partner"""

        clients = self.get_clients(partner_id, active_only=False)
        active_clients = [c for c in clients if c.is_active]

        return {
            "partner_id": partner_id,
            "period_days": days,
            "clients": {
                "total": len(clients),
                "active": len(active_clients),
                "inactive": len(clients) - len(active_clients)
            },
            "usage": {
                "total_products": 0,
                "total_orders": 0,
                "total_revenue": 0,
                "total_actions": 0
            }
        }
