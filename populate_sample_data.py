"""
POPULATE SAMPLE DATA FOR AI TESTING

Creates realistic sample data across all data sources so we can test
the AI's ability to access and analyze unified context.
"""

from datetime import datetime, timedelta
import random
from ospra_os.database.multi_store_models import (
    SessionLocal, User, Store, Product, ProductStatus, AdCampaign,
    Platform
)

print("=" * 80)
print("POPULATING SAMPLE DATA FOR AI TESTING")
print("=" * 80)
print()

db = SessionLocal()

# Clear existing data
print("1. Clearing existing data (if tables exist)...")
try:
    db.query(AdCampaign).delete()
    print("   Cleared AdCampaigns")
except Exception as e:
    print(f"   Skipping AdCampaigns: {str(e)[:50]}")

try:
    db.query(Product).delete()
    print("   Cleared Products")
except Exception as e:
    print(f"   Skipping Products: {str(e)[:50]}")

try:
    db.query(Store).delete()
    print("   Cleared Stores")
except Exception as e:
    print(f"   Skipping Stores: {str(e)[:50]}")

try:
    db.query(User).delete()
    print("   Cleared Users")
except Exception as e:
    print(f"   Skipping Users: {str(e)[:50]}")

db.commit()
print("✅ Cleared")
print()

# Create sample user
print("2. Creating sample user...")
user = User(
    id=1,
    email="demo@ospraos.com",
    username="demo_user",
    full_name="Demo User",
    subscription_tier="pro",
    created_at=datetime.utcnow() - timedelta(days=90)
)
db.add(user)
db.commit()
print(f"✅ User created: {user.email}")
print()

# Create sample stores
print("3. Creating sample stores...")
stores_data = [
    {
        "name": "FitGear Pro",
        "shopify_store_url": "fitgear-pro.myshopify.com",
        "niche": "fitness",
        "platform": Platform.SHOPIFY,
        "total_revenue": 15420.50,
        "total_orders": 342,
    },
    {
        "name": "Smart Home Hub",
        "shopify_store_url": "smart-home-hub.myshopify.com",
        "niche": "smart_home",
        "platform": Platform.SHOPIFY,
        "total_revenue": 28340.25,
        "total_orders": 521,
    }
]

stores = []
for store_data in stores_data:
    store = Store(
        user_id=user.id,
        **store_data,
        created_at=datetime.utcnow() - timedelta(days=60)
    )
    db.add(store)
    stores.append(store)

db.commit()
print(f"✅ {len(stores)} stores created")
print()

# Create sample products
print("4. Creating sample products...")
products_data = [
    # FitGear Pro products
    {
        "store_id": stores[0].id,
        "title": "Resistance Bands Set - Premium Quality",
        "price": 29.99,
        "supplier_cost": 8.50,
        "total_sales": 145,
        "status": ProductStatus.ACTIVE,
        "discovery_score": 8.2,
        "trend_score": 85,
        "velocity_score": 7.5,
    },
    {
        "store_id": stores[0].id,
        "title": "Yoga Mat Extra Thick Non-Slip",
        "price": 39.99,
        "supplier_cost": 12.00,
        "total_sales": 89,
        "status": ProductStatus.ACTIVE,
        "discovery_score": 7.8,
        "trend_score": 78,
        "velocity_score": 6.9,
    },
    {
        "store_id": stores[0].id,
        "title": "Foam Roller for Muscle Recovery",
        "price": 24.99,
        "supplier_cost": 7.20,
        "total_sales": 8,
        "status": ProductStatus.ACTIVE,
        "discovery_score": 6.1,
        "trend_score": 62,
        "velocity_score": 4.2,
    },
    # Smart Home Hub products
    {
        "store_id": stores[1].id,
        "title": "Smart LED Light Bulbs (4-Pack)",
        "price": 49.99,
        "supplier_cost": 15.00,
        "total_sales": 234,
        "status": ProductStatus.ACTIVE,
        "discovery_score": 9.1,
        "trend_score": 92,
        "velocity_score": 8.7,
    },
    {
        "store_id": stores[1].id,
        "title": "WiFi Smart Plug with Energy Monitoring",
        "price": 19.99,
        "supplier_cost": 6.50,
        "total_sales": 178,
        "status": ProductStatus.ACTIVE,
        "discovery_score": 8.5,
        "trend_score": 88,
        "velocity_score": 8.1,
    },
    {
        "store_id": stores[1].id,
        "title": "Smart Door/Window Sensor",
        "price": 15.99,
        "supplier_cost": 5.20,
        "total_sales": 12,
        "status": ProductStatus.ACTIVE,
        "discovery_score": 5.8,
        "trend_score": 58,
        "velocity_score": 3.9,
    },
]

products = []
for i, prod_data in enumerate(products_data, 1):
    # Calculate profit margin
    price = prod_data["price"]
    cost = prod_data["supplier_cost"]
    margin = ((price - cost) / price) * 100

    product = Product(
        id=i,
        product_name=f"PROD-{i:03d}",
        profit_margin=margin,
        discovered_at=datetime.utcnow() - timedelta(days=random.randint(30, 60)),
        deployed_at=datetime.utcnow() - timedelta(days=random.randint(15, 45)),
        **prod_data
    )
    db.add(product)
    products.append(product)

db.commit()
print(f"✅ {len(products)} products created")
print()

# Create sample ad campaigns
print("5. Creating sample ad campaigns...")
campaigns_data = [
    {
        "product_id": products[0].id,
        "store_id": stores[0].id,
        "platform": Platform.META,
        "campaign_name": "Resistance Bands - US Fitness Enthusiasts",
        "daily_budget": 50.00,
        "budget_spent": 420.50,
        "impressions": 125000,
        "clicks": 3250,
        "conversions": 89,
        "revenue": 2666.11,
        "status": "ACTIVE",
        "roas": 6.34,
    },
    {
        "product_id": products[3].id,
        "store_id": stores[1].id,
        "platform": Platform.META,
        "campaign_name": "Smart LED Bulbs - Home Automation",
        "daily_budget": 75.00,
        "budget_spent": 1250.00,
        "impressions": 285000,
        "clicks": 7200,
        "conversions": 156,
        "revenue": 7798.44,
        "status": "ACTIVE",
        "roas": 6.24,
    },
    {
        "product_id": products[2].id,
        "store_id": stores[0].id,
        "platform": Platform.META,
        "campaign_name": "Foam Roller - Recovery Athletes",
        "daily_budget": 25.00,
        "budget_spent": 175.00,
        "impressions": 42000,
        "clicks": 650,
        "conversions": 4,
        "revenue": 99.96,
        "status": "ACTIVE",
        "roas": 0.57,  # Low ROAS - should trigger correlation
    },
]

campaigns = []
for i, camp_data in enumerate(campaigns_data, 1):
    campaign = AdCampaign(
        id=i,
        user_id=user.id,
        campaign_id=f"CAMP-{i:05d}",
        created_at=datetime.utcnow() - timedelta(days=random.randint(10, 30)),
        activated_at=datetime.utcnow() - timedelta(days=random.randint(5, 25)),
        **camp_data
    )
    # Calculate CTR and CPC
    campaign.ctr = (camp_data["clicks"] / camp_data["impressions"]) * 100 if camp_data["impressions"] > 0 else 0
    campaign.cpc = camp_data["budget_spent"] / camp_data["clicks"] if camp_data["clicks"] > 0 else 0

    db.add(campaign)
    campaigns.append(campaign)

db.commit()
print(f"✅ {len(campaigns)} ad campaigns created")
print()

# Summary
print("=" * 80)
print("SAMPLE DATA POPULATED SUCCESSFULLY")
print("=" * 80)
print()
print(f"Users: {db.query(User).count()}")
print(f"Stores: {db.query(Store).count()}")
print(f"Products: {db.query(Product).count()}")
print(f"Ad Campaigns: {db.query(AdCampaign).count()}")
print()
print("Data includes:")
print("  ✅ High-performing products (Smart LED Bulbs, Resistance Bands)")
print("  ✅ Underperforming products (Foam Roller, Door Sensor)")
print("  ✅ Successful ad campaigns (ROAS >6x)")
print("  ✅ Failing ad campaign (ROAS 0.57x) - should trigger AI alert")
print()
print("Ready to test AI context awareness with real data!")
print()

db.close()
