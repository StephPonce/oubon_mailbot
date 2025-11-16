# Multi-Store Database Initialization & Migration Guide

Complete guide for initializing the multi-store database and migrating your existing Oubon Shop store.

---

## 🚀 Quick Start

### Option 1: Using Wrapper Script (Easiest)

```bash
cd /path/to/oubon_mailbot

# Initialize database
./multi-store --init

# Migrate Oubon Shop
./multi-store --migrate

# Check status
./multi-store --status
```

### Option 2: Direct Python Script

```bash
cd /path/to/oubon_mailbot

# Initialize database
PYTHONPATH=. uv run python ospra_os/database/init_multi_store.py --init

# Migrate Oubon Shop
PYTHONPATH=. uv run python ospra_os/database/init_multi_store.py --migrate

# Check status
PYTHONPATH=. uv run python ospra_os/database/init_multi_store.py --status
```

---

## 📋 Commands

### `--init` - Initialize Database

Creates all multi-store database tables.

**Usage:**
```bash
./multi-store --init
```

**What it does:**
- Creates 6 core tables:
  - `users` - Multi-tenant user accounts
  - `stores` - Platform-agnostic stores
  - `products` - Product catalog
  - `product_deployments` - Cross-platform tracking
  - `ai_usage` - AI cost tracking
  - `user_settings` - User preferences

**Output:**
```
======================================================================
  DATABASE INITIALIZATION
======================================================================

ℹ️  Database: sqlite:///./oubon_store.db
ℹ️  Existing tables: 0

Creating multi-store tables...
✅ Multi-store database initialized!

📊 Total tables: 6

🆕 New tables created (6):
   • ai_usage
   • product_deployments
   • products
   • stores
   • user_settings
   • users

✨ Multi-store tables (6/6):
   ✅ users
   ✅ stores
   ✅ products
   ✅ product_deployments
   ✅ ai_usage
   ✅ user_settings
```

**Safe to run multiple times:** Won't overwrite existing tables.

---

### `--migrate` - Migrate Existing Store

Migrates your existing Oubon Shop Shopify store to the multi-store system.

**Usage:**
```bash
./multi-store --migrate
```

**With auto-confirmation:**
```bash
./multi-store --migrate --yes
```

**Requirements:**
Environment variables must be set in `.env`:

```env
# Required Shopify credentials
OUBONSHOP_SHOPIFY_STORE_DOMAIN=your-store.myshopify.com
OUBONSHOP_SHOPIFY_ADMIN_TOKEN=shpat_...
OUBONSHOP_SHOPIFY_API_VERSION=2025-01
```

**What it does:**
1. Auto-initializes database if not already done
2. Creates default user: `steph@oubonshop.com`
3. Creates Oubon Shop store with your Shopify credentials
4. Sets up default user settings
5. Ranks store as #1

**Migration Plan (shown before execution):**
```
1️⃣  Create Default User:
   Email: steph@oubonshop.com
   Name: Stephen Ponce
   Tier: PRO
   AI Provider: Claude
   Monthly AI Budget: $200
   Product Limit: 1000

2️⃣  Create Oubon Shop Store:
   Name: Oubon Shop
   Platform: Shopify
   Store URL: rxxj7d-1i.myshopify.com
   API Version: 2025-01
   Token: shpat_bcfcdbf00...
   Niche: smart_home
   Currency: USD
```

**Confirmation prompt:**
```
Proceed with migration? (yes/no):
```

**On success:**
```
======================================================================
  MIGRATION COMPLETE
======================================================================

📊 Migration Summary:

User:
   • Email: steph@oubonshop.com
   • Tier: pro
   • Total Stores: 1
   • Created: 2025-11-14 09:02:07

Store:
   • Name: Oubon Shop
   • Platform: shopify
   • URL: rxxj7d-1i.myshopify.com
   • Rank: #1
   • Active: Yes
   • Created: 2025-11-14 09:02:07

======================================================================
✅ Oubon Shop successfully migrated to multi-store system!

Next steps:
   • Test API: curl http://localhost:8001/api/portfolio/overview
   • View docs: http://localhost:8001/docs
   • Add more stores: POST /api/portfolio/stores/add
```

**Safety features:**
- ✅ Won't overwrite existing users
- ✅ Won't duplicate stores
- ✅ Requires confirmation (unless `--yes`)
- ✅ Shows what will be created before running

---

### `--status` - Show Database Status

Shows current state of the multi-store database.

**Usage:**
```bash
./multi-store --status
```

**Output:**
```
======================================================================
  MULTI-STORE DATABASE STATUS
======================================================================

ℹ️  Database: sqlite:///./oubon_store.db

📊 Total tables: 10

✨ Multi-store tables:
   ✅ users
   ✅ stores
   ✅ products
   ✅ product_deployments
   ✅ ai_usage
   ✅ user_settings

----------------------------------------------------------------------

📈 Database Statistics:

   Users: 1
   Stores: 1
   Products: 0
   Deployments: 0

👥 Users:

   • steph@oubonshop.com
     Name: Stephen Ponce
     Tier: pro
     Stores: 1
     Products: 0
     Created: 2025-11-14 09:02:07

🏪 Stores:

   🟢 Oubon Shop
     Platform: shopify
     URL: rxxj7d-1i.myshopify.com
     Rank: #1
     Niche: smart_home
     Products: 0
     Revenue: $0.00

======================================================================
✅ Database is operational!

💡 Access API: http://localhost:8001/api/portfolio/overview
```

**Use cases:**
- Verify migration completed successfully
- Check user and store counts
- View current store rankings
- Debug database issues

---

## 🔧 Advanced Options

### Custom Database URL

Use a different database location:

```bash
./multi-store --init --db sqlite:///./custom_store.db
./multi-store --migrate --db sqlite:///./custom_store.db --yes
```

### Auto-Confirm Migration

Skip the confirmation prompt:

```bash
./multi-store --migrate --yes
```

---

## 📊 Complete Workflow

### First-Time Setup

**Step 1: Set Environment Variables**

Edit `.env` file:
```env
# Multi-Store Database
OUBONSHOP_database_url=sqlite:///./oubon_store.db

# Shopify Credentials
OUBONSHOP_SHOPIFY_STORE_DOMAIN=your-store.myshopify.com
OUBONSHOP_SHOPIFY_ADMIN_TOKEN=shpat_your_token_here
OUBONSHOP_SHOPIFY_API_VERSION=2025-01
```

**Step 2: Run Migration**

```bash
cd /path/to/oubon_mailbot

# One command does it all
./multi-store --migrate --yes
```

This will:
- ✅ Initialize database tables
- ✅ Create your user account
- ✅ Migrate Oubon Shop store
- ✅ Set up default settings

**Step 3: Verify**

```bash
# Check database status
./multi-store --status

# Test API
curl http://localhost:8001/api/portfolio/overview | python3 -m json.tool
```

**Step 4: Start Backend**

```bash
uv run uvicorn ospra_os.main:app --reload --host 127.0.0.1 --port 8001
```

**Step 5: View API Docs**

Visit: http://localhost:8001/docs

---

## 🔄 Re-running Migration

### Safe to Re-run

The migration is **idempotent** - safe to run multiple times:

```bash
./multi-store --migrate --yes
```

**Behavior:**
- Existing user: Skips creation, uses existing
- Existing store: Skips creation, shows warning
- New stores: Creates normally

**Output when re-running:**
```
⚠️  User already exists: steph@oubonshop.com
⚠️  Store already exists: Oubon Shop
```

---

## 🚨 Troubleshooting

### Error: "Missing Shopify credentials"

**Problem:**
```
❌ Missing Shopify credentials in environment!
ℹ️  Required environment variables:
   • OUBONSHOP_SHOPIFY_STORE_DOMAIN
   • OUBONSHOP_SHOPIFY_ADMIN_TOKEN
```

**Solution:**
Add credentials to `.env`:
```env
OUBONSHOP_SHOPIFY_STORE_DOMAIN=your-store.myshopify.com
OUBONSHOP_SHOPIFY_ADMIN_TOKEN=shpat_...
```

### Error: "No module named 'ospra_os'"

**Problem:**
```
ModuleNotFoundError: No module named 'ospra_os'
```

**Solution:**
Use the wrapper script or set PYTHONPATH:
```bash
# Option 1: Use wrapper
./multi-store --status

# Option 2: Set PYTHONPATH
PYTHONPATH=. uv run python ospra_os/database/init_multi_store.py --status
```

### Database Not Initialized

**Problem:**
```
❌ Database not initialized! Run: python init_multi_store.py --init
```

**Solution:**
```bash
./multi-store --init
```

Or just run migrate (auto-initializes):
```bash
./multi-store --migrate --yes
```

---

## 📈 What Happens After Migration

### Database State

**User Created:**
- Email: steph@oubonshop.com
- Tier: PRO ($200/month AI budget)
- Product Limit: 1000 products
- AI Provider: Claude

**Store Created:**
- Name: Oubon Shop
- Platform: Shopify
- Rank: #1
- Status: Active
- Niche: smart_home
- Currency: USD

**Settings Created:**
- Auto-deploy: OFF (safe default)
- Auto-generate content: ON
- Email notifications: ON
- Notify on new products: ON

### API Endpoints Ready

All portfolio endpoints are now functional:

```bash
# Portfolio overview
curl http://localhost:8001/api/portfolio/overview

# Store rankings
curl http://localhost:8001/api/portfolio/rankings

# Store details
curl http://localhost:8001/api/portfolio/stores/1

# Add another store
curl -X POST http://localhost:8001/api/portfolio/stores/add \
  -H "Content-Type: application/json" \
  -d '{...}'
```

---

## 🎯 Next Steps After Migration

### 1. Test API Access

```bash
# View portfolio
curl http://localhost:8001/api/portfolio/overview | python3 -m json.tool

# View store rankings
curl http://localhost:8001/api/portfolio/rankings | python3 -m json.tool
```

### 2. Add More Stores

Use the API to add Amazon, WooCommerce, etc.:

```bash
curl -X POST http://localhost:8001/api/portfolio/stores/add \
  -H "Content-Type: application/json" \
  -d '{
    "store_name": "Amazon Storefront",
    "store_url": "amazon.com/sp?seller=ABC",
    "platform": "amazon",
    "credentials": {
      "seller_id": "ABC123",
      "mws_token": "amzn.mws...",
      "marketplace_id": "ATVPDKIKX0DER"
    },
    "niche": "electronics"
  }'
```

### 3. Import Existing Products

(Coming soon - product import functionality)

### 4. Build Frontend Dashboard

Use the API endpoints to create a UI for managing your portfolio.

---

## 📚 Related Documentation

- **Database Models:** `/ospra_os/database/README.md`
- **API Reference:** `/ospra_os/dashboard/MULTI_STORE_API.md`
- **System Overview:** `/MULTI_STORE_SYSTEM_COMPLETE.md`

---

## ✅ Migration Checklist

- [ ] Add Shopify credentials to `.env`
- [ ] Run `./multi-store --migrate --yes`
- [ ] Verify with `./multi-store --status`
- [ ] Test API: `curl http://localhost:8001/api/portfolio/overview`
- [ ] Visit API docs: http://localhost:8001/docs
- [ ] Add additional stores via API (optional)

---

**Built with FastAPI + SQLAlchemy + Pydantic**
**Part of OspraOS - Ospra LLC**
