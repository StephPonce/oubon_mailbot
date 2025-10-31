#!/usr/bin/env python3
"""
Shopify Setup Validation Script
================================

Validates your Shopify store is ready for launch.

Checks:
- Shopify API connection
- Products (count, images, descriptions, pricing)
- Collections (count, descriptions)
- Theme customization
- Store settings (warnings for manual tasks)

Usage:
    python validate_setup.py
"""

import os
import sys
import requests
import logging
from typing import Dict, List, Tuple
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from shopify_automation.config import (
    ShopifyConfig,
    ValidationConfig,
    LogConfig,
    UIConfig,
    get_shopify_headers
)


# ============================================
# LOGGING SETUP
# ============================================

logging.basicConfig(
    level=logging.INFO,
    format=LogConfig.LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LogConfig.VALIDATE_SETUP_LOG)
    ]
)

logger = logging.getLogger(__name__)


# ============================================
# SHOPIFY VALIDATOR
# ============================================

class ShopifyValidator:
    """Validates Shopify store setup"""

    def __init__(self):
        self.base_url = ShopifyConfig.BASE_URL
        self.headers = get_shopify_headers()
        self.errors = []
        self.warnings = []
        self.successes = []

    def validate_all(self) -> bool:
        """Run all validation checks"""
        print("\n" + "="*60)
        print("🔍 SHOPIFY STORE VALIDATION")
        print("="*60 + "\n")

        # Run checks
        self.check_api_connection()
        self.check_products()
        self.check_collections()
        self.check_manual_tasks()

        # Print results
        self.print_results()

        return len(self.errors) == 0

    def check_api_connection(self):
        """Validate Shopify API connection"""
        print(UIConfig.info("Checking Shopify API connection..."))

        try:
            response = requests.get(
                f"{self.base_url}/shop.json",
                headers=self.headers,
                timeout=10
            )

            response.raise_for_status()
            shop_data = response.json()

            shop_name = shop_data['shop']['name']
            shop_domain = shop_data['shop']['domain']

            self.successes.append(f"Connected to Shopify: {shop_name} ({shop_domain})")
            print(UIConfig.success(f"✓ Connected to {shop_name}"))

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                self.errors.append("Shopify API authentication failed. Check your SHOPIFY_ADMIN_ACCESS_TOKEN.")
            else:
                self.errors.append(f"Shopify API error: {e.response.status_code}")
            print(UIConfig.error("✗ API connection failed"))

        except Exception as e:
            self.errors.append(f"Failed to connect to Shopify: {str(e)}")
            print(UIConfig.error("✗ Connection error"))

    def check_products(self):
        """Validate products setup"""
        print(UIConfig.info("Checking products..."))

        try:
            response = requests.get(
                f"{self.base_url}/products/count.json",
                headers=self.headers,
                timeout=10
            )

            response.raise_for_status()
            count = response.json()['count']

            if count >= ValidationConfig.MIN_PRODUCTS_REQUIRED:
                self.successes.append(f"Products: {count} products created")
                print(UIConfig.success(f"✓ {count} products found"))
            elif count > 0:
                self.warnings.append(f"Only {count} products. Recommended: {ValidationConfig.MIN_PRODUCTS_REQUIRED}+")
                print(UIConfig.warning(f"⚠  Only {count} products (recommended: {ValidationConfig.MIN_PRODUCTS_REQUIRED}+)"))
            else:
                self.errors.append("No products found. Run setup_products.py first.")
                print(UIConfig.error("✗ No products found"))
                return

            # Check product details
            response = requests.get(
                f"{self.base_url}/products.json?limit=10",
                headers=self.headers,
                timeout=10
            )

            response.raise_for_status()
            products = response.json()['products']

            # Validate product quality
            issues = self._validate_product_quality(products)

            if not issues:
                self.successes.append("All products have images and descriptions")
                print(UIConfig.success("✓ Products are properly configured"))
            else:
                for issue in issues:
                    self.warnings.append(issue)
                    print(UIConfig.warning(f"⚠  {issue}"))

        except Exception as e:
            self.errors.append(f"Failed to check products: {str(e)}")
            print(UIConfig.error("✗ Product check failed"))

    def _validate_product_quality(self, products: List[Dict]) -> List[str]:
        """Validate individual product quality"""
        issues = []

        for product in products:
            product_title = product['title']

            # Check for images
            if ValidationConfig.REQUIRE_PRODUCT_IMAGES:
                if not product.get('images'):
                    issues.append(f"Product '{product_title}' has no images")

            # Check for description
            if ValidationConfig.REQUIRE_PRODUCT_DESCRIPTIONS:
                if not product.get('body_html') or len(product['body_html']) < 100:
                    issues.append(f"Product '{product_title}' has no/short description")

            # Check for pricing
            if ValidationConfig.REQUIRE_PRODUCT_PRICES:
                variants = product.get('variants', [])
                if not variants or not variants[0].get('price'):
                    issues.append(f"Product '{product_title}' has no price set")

        # Limit to first 5 issues
        return issues[:5]

    def check_collections(self):
        """Validate collections setup"""
        print(UIConfig.info("Checking collections..."))

        try:
            # Check smart collections
            response = requests.get(
                f"{self.base_url}/smart_collections/count.json",
                headers=self.headers,
                timeout=10
            )

            response.raise_for_status()
            smart_count = response.json()['count']

            # Check custom collections
            response = requests.get(
                f"{self.base_url}/custom_collections/count.json",
                headers=self.headers,
                timeout=10
            )

            response.raise_for_status()
            custom_count = response.json()['count']

            total_collections = smart_count + custom_count

            if total_collections >= ValidationConfig.MIN_COLLECTIONS_REQUIRED:
                self.successes.append(f"Collections: {total_collections} collections created ({smart_count} smart, {custom_count} custom)")
                print(UIConfig.success(f"✓ {total_collections} collections found"))
            elif total_collections > 0:
                self.warnings.append(f"Only {total_collections} collections. Recommended: {ValidationConfig.MIN_COLLECTIONS_REQUIRED}+")
                print(UIConfig.warning(f"⚠  Only {total_collections} collections (recommended: {ValidationConfig.MIN_COLLECTIONS_REQUIRED}+)"))
            else:
                self.errors.append("No collections found. Run create_collections.py first.")
                print(UIConfig.error("✗ No collections found"))

        except Exception as e:
            self.errors.append(f"Failed to check collections: {str(e)}")
            print(UIConfig.error("✗ Collection check failed"))

    def check_manual_tasks(self):
        """Check manual configuration tasks"""
        print(UIConfig.info("Checking manual tasks..."))

        for task in ValidationConfig.MANUAL_TASKS:
            self.warnings.append(f"Manual task: {task}")

        print(UIConfig.warning(f"⚠  {len(ValidationConfig.MANUAL_TASKS)} manual tasks remaining"))

    def print_results(self):
        """Print validation summary"""
        print("\n" + "="*60)
        print("📊 VALIDATION RESULTS")
        print("="*60 + "\n")

        # Successes
        if self.successes:
            print(UIConfig.success(f"✅ PASSED CHECKS ({len(self.successes)}):"))
            for success in self.successes:
                print(f"   ✓ {success}")
            print()

        # Errors
        if self.errors:
            print(UIConfig.error(f"❌ CRITICAL ISSUES ({len(self.errors)}):"))
            for error in self.errors:
                print(f"   ✗ {error}")
            print()

        # Warnings
        if self.warnings:
            print(UIConfig.warning(f"⚠️  WARNINGS ({len(self.warnings)}):"))
            for warning in self.warnings[:10]:  # Limit to 10 warnings
                print(f"   • {warning}")
            if len(self.warnings) > 10:
                print(f"   ... and {len(self.warnings) - 10} more")
            print()

        # Summary
        print("="*60)
        if not self.errors:
            print(UIConfig.success("🎉 STORE IS READY FOR LAUNCH!"))
            print()
            print("Next steps:")
            print("  1. Complete manual tasks listed above")
            print("  2. Test checkout process with test card")
            print("  3. Remove password protection")
            print("  4. Announce your launch!")
        else:
            print(UIConfig.error("❌ STORE NOT READY - Fix errors above"))
            print()
            print("Action items:")
            print("  1. Fix all critical issues")
            print("  2. Run validation again")
            print("  3. Review warnings")
        print("="*60 + "\n")


# ============================================
# MANUAL TASKS CHECKLIST
# ============================================

def print_manual_checklist():
    """Print manual tasks checklist"""
    print("\n" + "="*60)
    print("📋 MANUAL TASKS CHECKLIST")
    print("="*60 + "\n")

    print("Complete these tasks in Shopify Admin:\n")

    print("🎨 THEME & DESIGN (30 min)")
    print("  ☐ Upload logo")
    print("  ☐ Upload hero banner image (1920x1080px)")
    print("  ☐ Upload collection images")
    print("  ☐ Customize homepage sections")
    print("  ☐ Set announcement bar text")
    print()

    print("💳 PAYMENT & CHECKOUT (15 min)")
    print("  ☐ Activate payment gateway (Shopify Payments)")
    print("  ☐ Add bank account for payouts")
    print("  ☐ Test with test credit card")
    print("  ☐ Configure tax settings")
    print()

    print("📦 SHIPPING (10 min)")
    print("  ☐ Set up shipping rates")
    print("  ☐ Configure shipping zones")
    print("  ☐ Set processing time (2-5 days)")
    print()

    print("📄 LEGAL (10 min)")
    print("  ☐ Publish Privacy Policy")
    print("  ☐ Publish Refund Policy")
    print("  ☐ Publish Terms of Service")
    print("  ☐ Publish Shipping Policy")
    print()

    print("🔌 APPS (20 min)")
    print("  ☐ Install Judge.me (product reviews)")
    print("  ☐ Install trust badge app")
    print("  ☐ Install OptiMonk (email popup)")
    print("  ☐ Install TinyIMG (image optimization)")
    print()

    print("✅ PRE-LAUNCH (30 min)")
    print("  ☐ Test order flow end-to-end")
    print("  ☐ Test on mobile devices")
    print("  ☐ Check PageSpeed score")
    print("  ☐ Proofread all content")
    print("  ☐ Verify all links work")
    print()

    print("🚀 LAUNCH (15 min)")
    print("  ☐ Remove password protection")
    print("  ☐ Submit sitemap to Google")
    print("  ☐ Announce on social media")
    print("  ☐ Send launch email")
    print()

    print("="*60)
    print("Total estimated time: 2-3 hours")
    print("="*60 + "\n")


# ============================================
# MAIN
# ============================================

def main():
    """Run validation"""

    # Validate configuration first
    try:
        ShopifyConfig.validate()
    except ValueError as e:
        print(UIConfig.error(f"Configuration error: {e}"))
        print("\nMake sure you have set:")
        print("  - SHOPIFY_STORE_DOMAIN")
        print("  - SHOPIFY_ADMIN_ACCESS_TOKEN")
        sys.exit(1)

    # Run validation
    validator = ShopifyValidator()
    success = validator.validate_all()

    # Print manual checklist
    print_manual_checklist()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
