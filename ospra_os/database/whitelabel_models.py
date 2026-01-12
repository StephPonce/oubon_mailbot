"""
White-Label SaaS Models - GROK RECOMMENDATION #19

Allows agencies to rebrand Ospra as their own platform.
They pay wholesale, charge their clients retail.

Tables:
- whitelabel_partners - Agency/reseller accounts
- whitelabel_branding - Custom branding (logos, colors, fonts)
- whitelabel_domains - Custom domain configuration
- whitelabel_email_settings - Custom email configuration
- whitelabel_clients - Client management
- whitelabel_analytics - Partner analytics
"""

from sqlalchemy import Column, Integer, String, Float, Text, JSON, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship
from datetime import datetime

from ospra_os.database import Base


class WhiteLabelPartner(Base):
    """
    Agency/reseller who white-labels the platform.
    They pay wholesale, sell retail to their clients.
    """
    __tablename__ = "whitelabel_partners"

    id = Column(Integer, primary_key=True, index=True)

    # Partner info
    company_name = Column(String(255), nullable=False)
    contact_name = Column(String(255), nullable=True)
    contact_email = Column(String(255), nullable=False, unique=True)

    # Account
    slug = Column(String(50), unique=True, nullable=False, index=True)  # Used in URLs
    api_key = Column(String(100), unique=True, nullable=False)

    # Subscription
    plan = Column(String(50), default="starter")  # starter, growth, enterprise
    max_clients = Column(Integer, default=10)
    monthly_fee = Column(Float, default=299.0)
    per_client_fee = Column(Float, default=0)  # Optional per-client pricing

    # Status
    status = Column(String(20), default="pending")  # pending, active, suspended, cancelled
    activated_at = Column(DateTime, nullable=True)

    # Billing
    stripe_customer_id = Column(String(100), nullable=True)
    lemonsqueezy_customer_id = Column(String(100), nullable=True)
    billing_email = Column(String(255), nullable=True)

    # Settings
    settings = Column(JSON, default=dict)
    # {
    #   "support_email": "support@agency.com",
    #   "support_url": "https://agency.com/support",
    #   "onboarding_flow": "custom",
    #   "allowed_features": ["products", "ads", "email"],
    #   "hidden_features": ["federated_learning"]
    # }

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    branding = relationship("WhiteLabelBranding", back_populates="partner", uselist=False)
    domain = relationship("WhiteLabelDomain", back_populates="partner", uselist=False)
    clients = relationship("WhiteLabelClient", back_populates="partner")
    email_settings = relationship("WhiteLabelEmailSettings", back_populates="partner", uselist=False)


class WhiteLabelBranding(Base):
    """Custom branding for a white-label partner"""
    __tablename__ = "whitelabel_branding"

    id = Column(Integer, primary_key=True, index=True)
    partner_id = Column(Integer, ForeignKey("whitelabel_partners.id"), nullable=False, unique=True)

    # Brand identity
    brand_name = Column(String(100), nullable=False)  # Display name
    tagline = Column(String(255), nullable=True)

    # Logos
    logo_url = Column(String(500), nullable=True)  # Main logo
    logo_dark_url = Column(String(500), nullable=True)  # For dark mode
    favicon_url = Column(String(500), nullable=True)
    logo_email_url = Column(String(500), nullable=True)  # For emails

    # Colors (hex codes)
    primary_color = Column(String(7), default="#6366f1")  # Indigo
    secondary_color = Column(String(7), default="#8b5cf6")  # Purple
    accent_color = Column(String(7), default="#06b6d4")  # Cyan
    background_color = Column(String(7), default="#0f172a")  # Slate 900
    surface_color = Column(String(7), default="#1e293b")  # Slate 800
    text_color = Column(String(7), default="#f8fafc")  # Slate 50
    text_muted_color = Column(String(7), default="#94a3b8")  # Slate 400
    success_color = Column(String(7), default="#22c55e")
    warning_color = Column(String(7), default="#f59e0b")
    error_color = Column(String(7), default="#ef4444")

    # Typography
    font_family = Column(String(100), default="Inter")
    heading_font = Column(String(100), nullable=True)  # Optional different heading font

    # Custom CSS (advanced)
    custom_css = Column(Text, nullable=True)

    # UI customization
    ui_config = Column(JSON, default=dict)
    # {
    #   "show_powered_by": true,
    #   "sidebar_style": "expanded",
    #   "card_style": "glassmorphism",
    #   "animation_level": "full"
    # }

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    partner = relationship("WhiteLabelPartner", back_populates="branding")


class WhiteLabelDomain(Base):
    """Custom domain configuration"""
    __tablename__ = "whitelabel_domains"

    id = Column(Integer, primary_key=True, index=True)
    partner_id = Column(Integer, ForeignKey("whitelabel_partners.id"), nullable=False, unique=True)

    # Domain
    domain = Column(String(255), unique=True, nullable=False)  # app.theiragency.com

    # SSL
    ssl_status = Column(String(20), default="pending")  # pending, provisioning, active, failed
    ssl_provisioned_at = Column(DateTime, nullable=True)
    ssl_expires_at = Column(DateTime, nullable=True)

    # DNS verification
    dns_verified = Column(Boolean, default=False)
    dns_verification_token = Column(String(100), nullable=True)
    dns_verified_at = Column(DateTime, nullable=True)

    # CNAME target
    cname_target = Column(String(255), default="custom.ospra.io")

    # Status
    status = Column(String(20), default="pending")  # pending, verifying, active, failed

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    partner = relationship("WhiteLabelPartner", back_populates="domain")


class WhiteLabelEmailSettings(Base):
    """Custom email settings for white-label"""
    __tablename__ = "whitelabel_email_settings"

    id = Column(Integer, primary_key=True, index=True)
    partner_id = Column(Integer, ForeignKey("whitelabel_partners.id"), nullable=False, unique=True)

    # From address
    from_name = Column(String(100), nullable=False)
    from_email = Column(String(255), nullable=False)
    reply_to = Column(String(255), nullable=True)

    # SMTP settings (if using custom)
    use_custom_smtp = Column(Boolean, default=False)
    smtp_host = Column(String(255), nullable=True)
    smtp_port = Column(Integer, nullable=True)
    smtp_username = Column(String(255), nullable=True)
    smtp_password = Column(String(255), nullable=True)  # Encrypted
    smtp_use_tls = Column(Boolean, default=True)

    # Email templates
    email_footer = Column(Text, nullable=True)
    email_signature = Column(Text, nullable=True)

    # Verified
    domain_verified = Column(Boolean, default=False)
    dkim_configured = Column(Boolean, default=False)
    spf_configured = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    partner = relationship("WhiteLabelPartner", back_populates="email_settings")


class WhiteLabelClient(Base):
    """
    Client of a white-label partner.
    Links a user account to a white-label partner.
    """
    __tablename__ = "whitelabel_clients"

    id = Column(Integer, primary_key=True, index=True)
    partner_id = Column(Integer, ForeignKey("whitelabel_partners.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)

    # Client info (from partner's perspective)
    client_name = Column(String(255), nullable=True)
    client_email = Column(String(255), nullable=True)

    # Subscription (managed by partner)
    plan = Column(String(50), default="basic")
    is_active = Column(Boolean, default=True)

    # Partner's internal tracking
    partner_client_id = Column(String(100), nullable=True)  # Their CRM ID
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    partner = relationship("WhiteLabelPartner", back_populates="clients")
    user = relationship("User", foreign_keys=[user_id])


class WhiteLabelAnalytics(Base):
    """Aggregated analytics for white-label partner dashboard"""
    __tablename__ = "whitelabel_analytics"

    id = Column(Integer, primary_key=True, index=True)
    partner_id = Column(Integer, ForeignKey("whitelabel_partners.id"), nullable=False)

    # Date
    date = Column(DateTime, nullable=False)

    # Client metrics
    total_clients = Column(Integer, default=0)
    active_clients = Column(Integer, default=0)
    new_clients = Column(Integer, default=0)
    churned_clients = Column(Integer, default=0)

    # Usage metrics (aggregated across all clients)
    total_products = Column(Integer, default=0)
    total_orders = Column(Integer, default=0)
    total_revenue = Column(Float, default=0)
    total_actions_executed = Column(Integer, default=0)

    # API usage
    api_calls = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)


# Indexes
Index('idx_wl_partner_slug', WhiteLabelPartner.slug)
Index('idx_wl_partner_api_key', WhiteLabelPartner.api_key)
Index('idx_wl_client_partner', WhiteLabelClient.partner_id)
Index('idx_wl_client_user', WhiteLabelClient.user_id)
Index('idx_wl_domain', WhiteLabelDomain.domain)
