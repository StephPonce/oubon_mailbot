# Multi-Store Database Models

Complete multi-tenant, multi-platform e-commerce database system with AI provider abstraction.

## 🏗️ Architecture

### Database Models

1. **User** - Multi-tenant user accounts
2. **Store** - Platform-agnostic stores (Shopify, Amazon, WooCommerce)
3. **Product** - Discovered/managed products
4. **ProductDeployment** - Track deployments across stores
5. **AIUsage** - AI cost tracking per user
6. **UserSettings** - User preferences and automation

### Supported Platforms

- ✅ Shopify
- ✅ Amazon
- ✅ WooCommerce
- ✅ Etsy
- ✅ eBay

### AI Providers

- ✅ Claude (Anthropic)
- ✅ OpenAI (GPT-4)
- ✅ Google Gemini
- ✅ Custom providers

## 🚀 Quick Start

### Initialize Database

```python
from ospra_os.database import init_multi_store_db

# Create all tables
engine = init_multi_store_db("sqlite:///./oubon_store.db")
```

### Create User and Store

```python
from ospra_os.database import (
    get_multi_store_session,
    User, Store, Product,
    SubscriptionTier, Platform, ProductStatus
)

# Get session
session = get_multi_store_session()

# Create user
user = User(
    email="john@example.com",
    name="John Doe",
    subscription_tier=SubscriptionTier.PRO,
    ai_preference=AIProvider.CLAUDE
)
session.add(user)
session.commit()

# Create Shopify store
shopify_store = Store(
    user_id=user.id,
    store_name="My Shopify Store",
    store_url="my-store.myshopify.com",
    platform=Platform.SHOPIFY,
    credentials={
        "shop_url": "my-store.myshopify.com",
        "access_token": "shpat_...",
        "api_version": "2025-01"
    },
    niche="smart_home",
    currency="USD"
)
session.add(shopify_store)
session.commit()
```

### Add Products

```python
# Create product
product = Product(
    store_id=shopify_store.id,
    product_name="Smart LED Light Bulb",
    product_sku="LED-RGB-001",
    source_platform="aliexpress",
    source_url="https://aliexpress.com/item/...",
    supplier_cost=5.99,
    selling_price=29.99,
    profit_margin=80.0,
    discovery_score=8.5,
    trend_score=75.0,
    status=ProductStatus.DISCOVERED,
    ai_title="Smart WiFi LED Bulb - 16M Colors",
    ai_description="Transform your home with...",
    ai_tags=["smart-home", "led", "wifi", "rgb"]
)
session.add(product)
session.commit()
```

### Deploy Product to Store

```python
from ospra_os.database import ProductDeployment, DeploymentStatus

deployment = ProductDeployment(
    product_id=product.id,
    store_id=shopify_store.id,
    platform_product_id="shopify_12345",
    platform_url="https://my-store.myshopify.com/products/smart-led-bulb",
    deployment_status=DeploymentStatus.SUCCESS,
    generated_title="Smart LED Bulb - RGB WiFi Enabled",
    generated_description="<p>AI-generated description...</p>",
    platform_price=29.99,
    platform_compare_price=49.99
)
session.add(deployment)
session.commit()
```

### Track AI Usage

```python
from ospra_os.database import AIUsage, AIProvider, TaskType

ai_usage = AIUsage(
    user_id=user.id,
    provider=AIProvider.CLAUDE,
    model="claude-sonnet-4",
    task_type=TaskType.CONTENT_GENERATION,
    tokens_used=1500,
    estimated_cost=0.0225,  # $0.0225
    product_id=product.id
)
session.add(ai_usage)
session.commit()
```

## 📊 Query Examples

### Get User's Stores

```python
user_stores = session.query(Store)\
    .filter(Store.user_id == user.id)\
    .filter(Store.is_active == True)\
    .all()

for store in user_stores:
    print(f"{store.store_name} ({store.platform})")
```

### Get Store Performance

```python
from ospra_os.database import get_store_performance

performance = get_store_performance(session, store_id=1)
print(f"Revenue: ${performance['total_revenue']}")
print(f"Conversion: {performance['conversion_rate']}%")
```

### Get User's Monthly AI Cost

```python
from ospra_os.database import get_user_monthly_ai_usage

monthly_cost = get_user_monthly_ai_usage(session, user_id=1)
print(f"AI cost this month: ${monthly_cost:.2f}")
```

### Find High-Performing Products

```python
top_products = session.query(Product)\
    .filter(Product.store_id == store.id)\
    .filter(Product.discovery_score >= 8.0)\
    .filter(Product.status == ProductStatus.ACTIVE)\
    .order_by(Product.total_revenue.desc())\
    .limit(10)\
    .all()
```

## 🔄 Migration from Single-Store

If you have an existing single-store setup, use the migration helper:

```python
from ospra_os.database import migrate_existing_store

user, store = migrate_existing_store(
    database_url="sqlite:///./oubon_store.db",
    user_email="existing@user.com",
    user_name="Existing User",
    shopify_credentials={
        "shop_url": "existing-store.myshopify.com",
        "access_token": "shpat_existing_token",
        "api_version": "2025-01"
    },
    store_name="Existing Shopify Store"
)

print(f"✅ Migrated! User ID: {user.id}, Store ID: {store.id}")
```

## 🔐 Security Notes

### Encrypted Fields

The following fields should be encrypted at rest:
- `User.custom_ai_keys` - User's custom AI API keys
- `Store.credentials` - Platform-specific credentials

**Recommended:** Use `sqlalchemy_utils.EncryptedType` or application-level encryption.

Example with encryption:
```python
from sqlalchemy_utils import EncryptedType
from sqlalchemy_utils.types.encrypted.encrypted_type import AesEngine

# In your model:
credentials = Column(
    EncryptedType(JSON, os.environ['DB_SECRET_KEY'], AesEngine, 'pkcs5'),
    nullable=False
)
```

## 📈 Subscription Tiers

| Tier | Monthly AI Budget | Product Limit | Features |
|------|------------------|---------------|----------|
| FREE | $10 | 50 | Basic discovery |
| STARTER | $50 | 200 | + Auto-deploy |
| PRO | $200 | 1000 | + Multi-store |
| ENTERPRISE | Unlimited | Unlimited | + Priority support |

## 🎯 Product Lifecycle

```
DISCOVERED → QUEUED → DEPLOYING → DEPLOYED → ACTIVE
                                      ↓
                                   PAUSED
                                      ↓
                                DISCONTINUED
```

## 🔧 Database Maintenance

### Backup

```bash
# SQLite backup
sqlite3 oubon_store.db ".backup oubon_store_backup.db"

# PostgreSQL backup
pg_dump oubon_db > oubon_backup.sql
```

### Optimize

```python
# Vacuum SQLite database
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text("VACUUM"))
```

### Index Performance

The following indexes are created automatically:
- User email (unique)
- Store user_id + platform
- Product store_id + status
- Product discovery_score
- Deployment product_id + store_id
- AIUsage user_id + created_at

## 🐛 Troubleshooting

### Import Error

```python
# If you get import errors, ensure the package is installed:
cd /path/to/oubon_mailbot
pip install -e .
```

### Database Locked (SQLite)

```python
# Use WAL mode for better concurrency:
engine = create_engine(
    "sqlite:///./oubon_store.db?check_same_thread=False",
    connect_args={"timeout": 30}
)

with engine.connect() as conn:
    conn.execute(text("PRAGMA journal_mode=WAL"))
```

## 📚 Examples

See `/tests/test_multi_store.py` for comprehensive examples.

## 🤝 Contributing

When adding new models or fields:
1. Update the model in `multi_store_models.py`
2. Add to `__init__.py` exports
3. Create migration script
4. Update this README

## 📄 License

Part of OspraOS - Ospra LLC
