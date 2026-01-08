#!/usr/bin/env python3
"""Test AI-powered product description generation"""

import os
import sys

# Test product data
test_product = {
    "id": "test_001",
    "name": "Smart WiFi Security Camera 1080P with Night Vision",
    "price": 39.99,
    "cost": 15.00,
    "profit_margin": 62.5,
    "estimated_profit": 24.99,
    "category": "Electronics",
    "niche": "smart_home",
    "rating": 4.8,
    "orders": 15234,
    "velocity_score": 87
}

def test_ai_generator():
    """Test the AI description generator"""
    print("")
    print("[AI] TESTING AI DESCRIPTION GENERATOR")
    print("")
    print()

    # Check if ANTHROPIC_API_KEY is set
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY not found in environment")
        print("   Set it with: export ANTHROPIC_API_KEY='your-key-here'")
        return False

    print(f"[SUCCESS] ANTHROPIC_API_KEY found: {api_key[:20]}...")
    print()

    try:
        from ospra_os.intelligence.product_description_generator import ProductDescriptionGenerator
        print("[SUCCESS] ProductDescriptionGenerator imported successfully")
        print()

        # Initialize generator
        generator = ProductDescriptionGenerator()
        print("[SUCCESS] Generator initialized")
        print()

        # Generate description
        print(f"[NOTE] Generating AI description for: {test_product['name']}")
        print()

        result = generator.generate_shopify_description(test_product)

        print("")
        print("[SUCCESS] AI DESCRIPTION GENERATED SUCCESSFULLY!")
        print("")
        print()

        print(" SEO-OPTIMIZED TITLE:")
        print(f"   {result['title']}")
        print()

        print("[NOTE] HTML DESCRIPTION:")
        print(result['description'])
        print()

        print("[NEW] KEY FEATURES:")
        for i, feature in enumerate(result['bullet_points'], 1):
            print(f"   {i}. {feature}")
        print()

        print(" SEO KEYWORDS:")
        print(f"   {', '.join(result['seo_keywords'])}")
        print()

        return True

    except ImportError as e:
        print(f"[ERROR] Import failed: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_shopify_integration():
    """Test Shopify client with AI descriptions"""
    print()
    print("")
    print("[CART] TESTING SHOPIFY CLIENT INTEGRATION")
    print("")
    print()

    try:
        from ospra_os.integrations.shopify_client import ShopifyClient

        client = ShopifyClient()

        if hasattr(client, 'description_generator') and client.description_generator:
            print("[SUCCESS] ShopifyClient has AI description generator")
            print(f"   Type: {type(client.description_generator)}")
            print()

            # Test description generation through Shopify client
            print("[NOTE] Generating description via Shopify client...")
            description = client._generate_description(test_product)

            print("[SUCCESS] Description generated successfully!")
            print()
            print("PREVIEW:")
            print(description[:500] + "..." if len(description) > 500 else description)
            print()

            return True
        else:
            print("[ERROR] ShopifyClient does NOT have AI description generator")
            print("   This means the integration failed")
            return False

    except Exception as e:
        print(f"[ERROR] Shopify integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print()
    success1 = test_ai_generator()
    success2 = test_shopify_integration()

    print()
    print("")
    print("[STATS] TEST SUMMARY")
    print("")
    print(f"   AI Generator Test: {'[SUCCESS] PASSED' if success1 else '[ERROR] FAILED'}")
    print(f"   Shopify Integration: {'[SUCCESS] PASSED' if success2 else '[ERROR] FAILED'}")
    print()

    if success1 and success2:
        print("[LAUNCH] ALL TESTS PASSED! AI descriptions are ready to use.")
        sys.exit(0)
    else:
        print("[WARNING]  Some tests failed. Check the errors above.")
        sys.exit(1)
