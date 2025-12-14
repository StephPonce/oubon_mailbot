#!/usr/bin/env python3
"""
Template Vault Schema Migration Script - GROK RECOMMENDATION #12

This script creates the template marketplace database tables:
- action_templates (reusable action sequences)
- template_purchases (purchase records)
- template_usages (tracking when templates are used)
- template_reviews (user reviews and ratings)

Usage:
    python migrate_templates.py

This will:
1. Backup the current database
2. Create the template tables
3. Add sample featured templates (optional)
"""

import os
import shutil
from datetime import datetime
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import Session

# Import database models
from ospra_os.database import (
    Base,
    get_engine,
)
from ospra_os.database.template_models import (
    ActionTemplate,
    TemplatePurchase,
    TemplateUsage,
    TemplateReview,
    TemplateStatus,
    TemplateCategory
)


def backup_database(db_path: str) -> str:
    """Create a backup of the database before migration."""
    if not os.path.exists(db_path):
        print(f"⚠️  Database not found at {db_path}")
        return ""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.backup_{timestamp}"

    shutil.copy2(db_path, backup_path)
    print(f"✅ Database backed up to: {backup_path}")
    return backup_path


def check_table_exists(engine, table_name: str) -> bool:
    """Check if a table exists in the database."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def create_sample_templates(engine):
    """Create sample featured templates for testing."""
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        # Check if templates already exist
        existing = session.query(ActionTemplate).count()
        if existing > 0:
            print("   ℹ️  Sample templates already exist, skipping...")
            return

        # Sample Template 1: Black Friday Strategy
        template1 = ActionTemplate(
            creator_id=1,  # Assuming user 1 exists
            name="Black Friday Mega Sale Strategy",
            slug="black-friday-mega-sale-strategy",
            description="A proven 3-day Black Friday strategy that generated $50K+ in revenue. "
                       "Includes dynamic pricing, email campaigns, and social media ads. "
                       "Perfect for stores with 20+ products targeting holiday shoppers.",
            short_description="Proven Black Friday strategy with dynamic pricing and multi-channel marketing",
            category=TemplateCategory.SEASONAL.value,
            tags=["black_friday", "high_volume", "multi_channel", "proven"],
            niches=["fashion", "electronics", "home_goods"],
            actions=[
                {
                    "order": 1,
                    "type": "adjust_price",
                    "name": "Early Bird Discount",
                    "description": "Start with 25% off to create urgency",
                    "config": {
                        "discount_percent": 25,
                        "apply_to": "all_products"
                    },
                    "delay_hours": 0,
                    "conditions": []
                },
                {
                    "order": 2,
                    "type": "send_email",
                    "name": "VIP Early Access",
                    "description": "Send to top customers 24h before public sale",
                    "config": {
                        "template": "vip_early_access",
                        "segment": "high_value_customers"
                    },
                    "delay_hours": 0,
                    "conditions": []
                },
                {
                    "order": 3,
                    "type": "launch_ad",
                    "name": "Facebook Flash Sale",
                    "description": "Run high-impact ad campaign",
                    "config": {
                        "platform": "facebook",
                        "budget_daily": 100,
                        "duration_days": 3
                    },
                    "delay_hours": 24,
                    "conditions": []
                }
            ],
            variables=[
                {
                    "name": "discount_percent",
                    "type": "number",
                    "default": 25,
                    "min": 10,
                    "max": 50,
                    "description": "Discount percentage to offer"
                },
                {
                    "name": "ad_budget_daily",
                    "type": "number",
                    "default": 100,
                    "min": 20,
                    "description": "Daily advertising budget in USD"
                }
            ],
            requirements={
                "min_products": 20,
                "integrations": ["shopify", "meta_ads", "email"],
                "subscription_tier": "flight"
            },
            status=TemplateStatus.PUBLISHED.value,
            is_free=False,
            price=49.99,
            revenue_share=0.7,
            uses_count=127,
            success_rate=0.85,
            avg_revenue_generated=32500,
            avg_rating=4.8,
            ratings_count=43,
            is_featured=True,
            featured_order=1,
            published_at=datetime.utcnow()
        )

        # Sample Template 2: Product Launch Sequence
        template2 = ActionTemplate(
            creator_id=1,
            name="Perfect Product Launch - 7 Day Sequence",
            slug="perfect-product-launch-7-day-sequence",
            description="Launch new products with maximum impact using this 7-day sequence. "
                       "Includes teaser campaigns, influencer outreach, launch day promotions, and post-launch follow-up. "
                       "Used successfully for 50+ product launches.",
            short_description="7-day product launch sequence with teasers, influencers, and promotions",
            category=TemplateCategory.LAUNCH.value,
            tags=["product_launch", "influencer", "email_sequence", "proven"],
            niches=["beauty", "fashion", "tech_gadgets"],
            actions=[
                {
                    "order": 1,
                    "type": "social_post",
                    "name": "Teaser Campaign Day 1",
                    "description": "Post mysterious product teasers",
                    "config": {
                        "platforms": ["instagram", "tiktok"],
                        "content_type": "teaser"
                    },
                    "delay_hours": 0,
                    "conditions": []
                },
                {
                    "order": 2,
                    "type": "send_email",
                    "name": "Insider Preview",
                    "description": "Give subscribers first look",
                    "config": {
                        "template": "product_preview",
                        "segment": "subscribers"
                    },
                    "delay_hours": 72,
                    "conditions": []
                },
                {
                    "order": 3,
                    "type": "launch_ad",
                    "name": "Launch Day Blitz",
                    "description": "Full advertising push on launch day",
                    "config": {
                        "platforms": ["facebook", "instagram", "google"],
                        "budget_daily": 200,
                        "duration_days": 3
                    },
                    "delay_hours": 168,
                    "conditions": []
                }
            ],
            variables=[
                {
                    "name": "launch_discount",
                    "type": "number",
                    "default": 15,
                    "min": 0,
                    "max": 30,
                    "description": "Launch day discount percentage"
                },
                {
                    "name": "teaser_days",
                    "type": "number",
                    "default": 7,
                    "min": 3,
                    "max": 14,
                    "description": "Days of teaser content before launch"
                }
            ],
            requirements={
                "min_products": 1,
                "integrations": ["shopify", "social_media", "email"],
                "subscription_tier": "nest"
            },
            status=TemplateStatus.PUBLISHED.value,
            is_free=True,
            price=0,
            uses_count=89,
            success_rate=0.78,
            avg_revenue_generated=15200,
            avg_rating=4.6,
            ratings_count=28,
            is_featured=True,
            featured_order=2,
            published_at=datetime.utcnow()
        )

        # Sample Template 3: Cart Recovery Campaign
        template3 = ActionTemplate(
            creator_id=1,
            name="Ultimate Cart Recovery Campaign",
            slug="ultimate-cart-recovery-campaign",
            description="Recover abandoned carts with this proven 3-email sequence. "
                       "Includes personalized reminders, urgency tactics, and discount escalation. "
                       "Average recovery rate: 18% (industry average is 8%).",
            short_description="3-email cart recovery sequence with 18% average recovery rate",
            category=TemplateCategory.RECOVERY.value,
            tags=["cart_recovery", "email_automation", "high_conversion"],
            niches=["all"],
            actions=[
                {
                    "order": 1,
                    "type": "send_email",
                    "name": "Gentle Reminder (1 hour)",
                    "description": "Friendly reminder about cart items",
                    "config": {
                        "template": "cart_reminder_1",
                        "delay_minutes": 60
                    },
                    "delay_hours": 1,
                    "conditions": []
                },
                {
                    "order": 2,
                    "type": "send_email",
                    "name": "Urgency + 5% Off (24 hours)",
                    "description": "Add urgency with limited-time discount",
                    "config": {
                        "template": "cart_reminder_2",
                        "discount_code": "COMEBACK5",
                        "discount_percent": 5
                    },
                    "delay_hours": 24,
                    "conditions": []
                },
                {
                    "order": 3,
                    "type": "send_email",
                    "name": "Last Chance + 10% Off (48 hours)",
                    "description": "Final attempt with better discount",
                    "config": {
                        "template": "cart_reminder_3",
                        "discount_code": "LASTCHANCE10",
                        "discount_percent": 10
                    },
                    "delay_hours": 48,
                    "conditions": []
                }
            ],
            variables=[
                {
                    "name": "first_discount",
                    "type": "number",
                    "default": 5,
                    "min": 0,
                    "max": 15,
                    "description": "First email discount %"
                },
                {
                    "name": "final_discount",
                    "type": "number",
                    "default": 10,
                    "min": 5,
                    "max": 25,
                    "description": "Final email discount %"
                }
            ],
            requirements={
                "min_products": 5,
                "integrations": ["shopify", "email"],
                "subscription_tier": "nest"
            },
            status=TemplateStatus.PUBLISHED.value,
            is_free=True,
            price=0,
            uses_count=203,
            success_rate=0.82,
            avg_revenue_generated=8900,
            avg_rating=4.7,
            ratings_count=67,
            is_featured=True,
            featured_order=3,
            published_at=datetime.utcnow()
        )

        session.add_all([template1, template2, template3])
        session.commit()

        print(f"   ✅ Created 3 sample featured templates")


def migrate_database():
    """Run the template vault migration."""
    print("🚀 Starting Template Vault Migration")
    print("=" * 60)

    # Get database engine
    engine = get_engine()
    db_url = str(engine.url)

    print(f"📊 Database: {db_url}")

    # Backup database if it's SQLite
    if db_url.startswith('sqlite'):
        db_path = db_url.replace('sqlite:///', '')
        backup_path = backup_database(db_path)
        if not backup_path:
            print("\n⚠️  No existing database found. Creating new database...")

    # Check existing schema
    print("\n🔍 Checking existing schema...")

    tables_to_create = []
    table_names = [
        'action_templates',
        'template_purchases',
        'template_usages',
        'template_reviews'
    ]

    for table_name in table_names:
        if not check_table_exists(engine, table_name):
            tables_to_create.append(table_name)

    if not tables_to_create:
        print("✅ All template tables already exist!")
    else:
        print(f"📝 Need to create {len(tables_to_create)} tables:")
        for table in tables_to_create:
            print(f"   - {table}")

        # Create tables
        print("\n🔨 Creating template tables...")
        # Import Base from template_models to ensure we're using the correct metadata
        from ospra_os.database.template_models import Base as TemplateBase
        TemplateBase.metadata.create_all(engine)
        print("   ✅ All template tables created successfully")

    # Create sample templates
    print("\n📦 Creating sample templates...")
    try:
        create_sample_templates(engine)
    except Exception as e:
        print(f"   ⚠️  Could not create sample templates: {e}")
        print("   ℹ️  This is normal if users table doesn't exist yet")

    print("\n" + "=" * 60)
    print("✅ Template Vault Migration completed successfully!")
    print("\nNew features available:")
    print("  • Template Marketplace - Browse and purchase action templates")
    print("  • Template Creation - Save successful strategies as reusable templates")
    print("  • Template Reviews - Rate and review templates")
    print("  • Revenue Sharing - Earn 70% revenue from template sales")
    print("\nAPI Endpoints:")
    print("  • GET /api/templates/featured - Featured templates")
    print("  • GET /api/templates/browse - Browse all templates")
    print("  • GET /api/templates/my-templates - My created templates")
    print("  • GET /api/templates/purchased - My purchased templates")
    print("  • POST /api/templates - Create new template")
    print("  • POST /api/templates/{id}/use - Apply template to store")
    print("  • POST /api/templates/{id}/purchase - Purchase template")
    print("  • POST /api/templates/{id}/review - Add review")
    print("\nFrontend:")
    print("  • Visit /templates to browse the marketplace")
    print("  • Visit /templates/create to create your own template")


if __name__ == "__main__":
    try:
        migrate_database()
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        print("\nIf you have a backup, you can restore it manually.")
        raise
