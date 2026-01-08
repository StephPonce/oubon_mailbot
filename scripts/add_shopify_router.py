#!/usr/bin/env python3
"""
Update main.py to include Shopify Store Management router

Run from project root:
    python scripts/add_shopify_router.py
"""

import re
from pathlib import Path

def main():
    main_py = Path(__file__).parent.parent / "ospra_os" / "main.py"
    
    if not main_py.exists():
        print(f"[ERROR] Could not find {main_py}")
        return
    
    content = main_py.read_text()
    
    # Check if already added
    if "_HAS_SHOPIFY_STORES" in content:
        print("[SUCCESS] Shopify Store Management router already added")
        return
    
    # Add the import after shopify_deployment_router
    import_block = '''# Shopify Deployment router (AI-Enhanced Shopify Integration)
try:
    from ospra_os.integrations.shopify.routes import router as shopify_deployment_router  # type: ignore
    _HAS_SHOPIFY_DEPLOYMENT = True
    print("[SUCCESS] Shopify Deployment router loaded successfully (AI-powered)")
except Exception as e:
    print(f"[WARNING]  Shopify Deployment router not loaded: {e}")
    shopify_deployment_router = None
    _HAS_SHOPIFY_DEPLOYMENT = False

# Meta Ads router'''

    new_import_block = '''# Shopify Deployment router (AI-Enhanced Shopify Integration)
try:
    from ospra_os.integrations.shopify.routes import router as shopify_deployment_router  # type: ignore
    _HAS_SHOPIFY_DEPLOYMENT = True
    print("[SUCCESS] Shopify Deployment router loaded successfully (AI-powered)")
except Exception as e:
    print(f"[WARNING]  Shopify Deployment router not loaded: {e}")
    shopify_deployment_router = None
    _HAS_SHOPIFY_DEPLOYMENT = False

# Shopify Store Management router (OAuth, store data, real-time sync)
try:
    from ospra_os.api.shopify_routes import router as shopify_store_router  # type: ignore
    _HAS_SHOPIFY_STORES = True
    print("[SUCCESS] Shopify Store Management router loaded successfully")
except Exception as e:
    print(f"[WARNING]  Shopify Store Management router not loaded: {e}")
    shopify_store_router = None
    _HAS_SHOPIFY_STORES = False

# Meta Ads router'''
    
    content = content.replace(import_block, new_import_block)
    
    # Add the router inclusion after shopify_deployment_router inclusion
    include_block = '''if _HAS_SHOPIFY_DEPLOYMENT and shopify_deployment_router:
    app.include_router(shopify_deployment_router)  # exposes /api/shopify/* (AI-powered deployment)

# Meta Ads Router'''
    
    new_include_block = '''if _HAS_SHOPIFY_DEPLOYMENT and shopify_deployment_router:
    app.include_router(shopify_deployment_router)  # exposes /api/shopify/* (AI-powered deployment)

if _HAS_SHOPIFY_STORES and shopify_store_router:
    app.include_router(shopify_store_router)  # exposes /api/shopify/* (Store management & OAuth)

# Meta Ads Router'''
    
    content = content.replace(include_block, new_include_block)
    
    # Write back
    main_py.write_text(content)
    print("[SUCCESS] Successfully added Shopify Store Management router to main.py")
    print("   Import: ospra_os.api.shopify_routes")
    print("   Endpoints: /api/shopify/stores, /api/shopify/oauth/*, etc.")

if __name__ == "__main__":
    main()
