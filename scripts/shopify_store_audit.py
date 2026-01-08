#!/usr/bin/env python3
"""
Shopify Store Audit Script
Performs comprehensive audit of Oubon Shop and generates action plan
"""

import os
import json
import requests
from typing import Dict, List, Optional
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ShopifyAuditor:
    """Comprehensive Shopify store auditor"""

    def __init__(self):
        self.store_url = os.getenv("SHOPIFY_STORE_URL") or os.getenv("SHOPIFY_STORE")
        self.access_token = os.getenv("SHOPIFY_ACCESS_TOKEN") or os.getenv("SHOPIFY_API_TOKEN")
        self.api_version = os.getenv("SHOPIFY_API_VERSION", "2025-01")

        if not self.store_url or not self.access_token:
            raise ValueError("Shopify credentials not found in .env file")

        self.base_url = f"https://{self.store_url}/admin/api/{self.api_version}"
        self.headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json"
        }

        self.audit_results = {
            "timestamp": datetime.now().isoformat(),
            "store": self.store_url,
            "overall_score": 0,
            "critical_issues": [],
            "warnings": [],
            "suggestions": [],
            "products": {},
            "pages": {},
            "navigation": {},
            "policies": {},
            "seo": {},
            "theme": {}
        }

    def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Make authenticated request to Shopify API"""
        url = f"{self.base_url}/{endpoint}.json"

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)

            if response.status_code == 200:
                return response.json()
            else:
                print(f"[WARNING]  API Error ({endpoint}): {response.status_code} - {response.text[:200]}")
                return None

        except Exception as e:
            print(f"[ERROR] Request failed ({endpoint}): {e}")
            return None

    def audit_products(self):
        """Audit all products for common issues"""
        print("\n[PACKAGE] Auditing Products...")

        products = self._make_request("products", {"limit": 250})

        if not products or "products" not in products:
            self.audit_results["critical_issues"].append({
                "area": "Products",
                "issue": "Could not fetch products from store",
                "severity": "CRITICAL"
            })
            return

        products_list = products["products"]
        total_products = len(products_list)

        print(f"   Found {total_products} products")

        issues = {
            "no_images": [],
            "poor_description": [],
            "no_seo_title": [],
            "no_seo_description": [],
            "no_variants": [],
            "no_price": [],
            "not_published": []
        }

        for product in products_list:
            product_id = product["id"]
            product_title = product["title"]

            # Check images
            if not product.get("images") or len(product["images"]) == 0:
                issues["no_images"].append(product_title)

            # Check description
            description = product.get("body_html", "")
            if not description or len(description) < 100:
                issues["poor_description"].append(product_title)

            # Check SEO
            if not product.get("metafields_global_title_tag"):
                issues["no_seo_title"].append(product_title)

            if not product.get("metafields_global_description_tag"):
                issues["no_seo_description"].append(product_title)

            # Check variants
            if not product.get("variants") or len(product["variants"]) == 0:
                issues["no_variants"].append(product_title)

            # Check price
            if product.get("variants"):
                variant = product["variants"][0]
                if not variant.get("price") or float(variant.get("price", 0)) == 0:
                    issues["no_price"].append(product_title)

            # Check published status
            if product.get("status") != "active":
                issues["not_published"].append(product_title)

        # Store results
        self.audit_results["products"] = {
            "total_count": total_products,
            "issues": issues,
            "score": self._calculate_product_score(total_products, issues)
        }

        # Add to critical/warnings
        if issues["no_images"]:
            self.audit_results["critical_issues"].append({
                "area": "Products",
                "issue": f"{len(issues['no_images'])} products missing images",
                "severity": "HIGH",
                "products": issues["no_images"][:5]  # First 5
            })

        if issues["poor_description"]:
            self.audit_results["warnings"].append({
                "area": "Products",
                "issue": f"{len(issues['poor_description'])} products have poor descriptions",
                "severity": "MEDIUM",
                "products": issues["poor_description"][:5]
            })

        print(f"   [SUCCESS] Product audit complete")

    def audit_pages(self):
        """Audit store pages"""
        print("\n[FILE] Auditing Pages...")

        pages = self._make_request("pages", {"limit": 250})

        if not pages or "pages" not in pages:
            self.audit_results["critical_issues"].append({
                "area": "Pages",
                "issue": "Could not fetch pages",
                "severity": "CRITICAL"
            })
            return

        pages_list = pages["pages"]
        page_handles = [page.get("handle", "") for page in pages_list]

        required_pages = {
            "about-us": "About Us",
            "about": "About Us",
            "contact": "Contact",
            "contact-us": "Contact Us",
            "faq": "FAQ",
            "frequently-asked-questions": "FAQ",
            "shipping": "Shipping Information",
            "shipping-information": "Shipping Information",
            "returns": "Returns & Exchanges",
            "returns-and-exchanges": "Returns & Exchanges"
        }

        missing_pages = []
        found_pages = set()

        for handle, name in required_pages.items():
            if handle in page_handles:
                found_pages.add(name)
            else:
                if name not in found_pages:  # Don't add duplicates
                    missing_pages.append(name)

        self.audit_results["pages"] = {
            "total_count": len(pages_list),
            "existing_pages": [p["title"] for p in pages_list],
            "missing_pages": list(set(missing_pages)),
            "score": 100 - (len(missing_pages) * 15)  # Deduct 15 points per missing page
        }

        if missing_pages:
            self.audit_results["critical_issues"].append({
                "area": "Pages",
                "issue": f"Missing {len(missing_pages)} essential pages",
                "severity": "HIGH",
                "missing": missing_pages
            })

        print(f"   Found {len(pages_list)} pages, {len(missing_pages)} missing")

    def audit_policies(self):
        """Audit legal policies"""
        print("\n Auditing Policies...")

        shop_info = self._make_request("shop")

        if not shop_info or "shop" not in shop_info:
            self.audit_results["warnings"].append({
                "area": "Policies",
                "issue": "Could not fetch shop information",
                "severity": "MEDIUM"
            })
            return

        shop = shop_info["shop"]

        policies = {
            "privacy_policy": shop.get("privacy_policy"),
            "refund_policy": shop.get("refund_policy"),
            "terms_of_service": shop.get("terms_of_service"),
            "shipping_policy": shop.get("shipping_policy")
        }

        missing_policies = [name.replace("_", " ").title() for name, content in policies.items() if not content]

        self.audit_results["policies"] = {
            "existing": [name.replace("_", " ").title() for name, content in policies.items() if content],
            "missing": missing_policies,
            "score": 100 - (len(missing_policies) * 20)
        }

        if missing_policies:
            self.audit_results["critical_issues"].append({
                "area": "Policies",
                "issue": f"Missing {len(missing_policies)} legal policies",
                "severity": "CRITICAL",
                "missing": missing_policies
            })

        print(f"   {len(policies) - len(missing_policies)}/4 policies configured")

    def audit_navigation(self):
        """Audit navigation menus"""
        print("\n Auditing Navigation...")

        # Note: Shopify API doesn't provide direct menu access
        # This is a placeholder for manual checking

        self.audit_results["navigation"] = {
            "note": "Navigation menus must be checked manually in Shopify Admin",
            "checklist": [
                "Main menu exists with Home, Shop, About, Contact",
                "Footer menu exists with Customer Service, Legal, Company sections",
                "All links are working (no 404s)"
            ]
        }

        self.audit_results["suggestions"].append({
            "area": "Navigation",
            "suggestion": "Manually verify navigation menus in Shopify Admin > Online Store > Navigation"
        })

    def audit_seo(self):
        """Audit SEO settings"""
        print("\n[SEARCH] Auditing SEO...")

        shop_info = self._make_request("shop")

        if not shop_info or "shop" not in shop_info:
            return

        shop = shop_info["shop"]

        seo_issues = []

        # Check store name
        if not shop.get("name") or len(shop.get("name", "")) < 3:
            seo_issues.append("Store name too short or missing")

        # Check domain
        if not shop.get("domain"):
            seo_issues.append("Custom domain not configured")

        self.audit_results["seo"] = {
            "store_name": shop.get("name"),
            "domain": shop.get("domain"),
            "primary_domain": shop.get("myshopify_domain"),
            "issues": seo_issues,
            "score": 100 - (len(seo_issues) * 25)
        }

        if seo_issues:
            self.audit_results["warnings"].append({
                "area": "SEO",
                "issue": "SEO configuration needs attention",
                "details": seo_issues
            })

    def audit_theme(self):
        """Audit theme configuration"""
        print("\n Auditing Theme...")

        themes = self._make_request("themes")

        if not themes or "themes" not in themes:
            return

        active_theme = None
        for theme in themes["themes"]:
            if theme.get("role") == "main":
                active_theme = theme
                break

        self.audit_results["theme"] = {
            "active_theme": active_theme.get("name") if active_theme else "Unknown",
            "theme_id": active_theme.get("id") if active_theme else None,
            "note": "Theme customization must be checked manually in Shopify Admin"
        }

    def _calculate_product_score(self, total: int, issues: Dict) -> int:
        """Calculate product quality score"""
        if total == 0:
            return 0

        deductions = 0
        deductions += len(issues["no_images"]) * 10
        deductions += len(issues["poor_description"]) * 5
        deductions += len(issues["no_seo_title"]) * 3
        deductions += len(issues["no_price"]) * 15

        max_score = total * 10
        score = max(0, max_score - deductions)

        return int((score / max_score) * 100) if max_score > 0 else 0

    def calculate_overall_score(self):
        """Calculate overall store health score"""
        scores = []

        if "score" in self.audit_results["products"]:
            scores.append(self.audit_results["products"]["score"])

        if "score" in self.audit_results["pages"]:
            scores.append(self.audit_results["pages"]["score"])

        if "score" in self.audit_results["policies"]:
            scores.append(self.audit_results["policies"]["score"])

        if "score" in self.audit_results["seo"]:
            scores.append(self.audit_results["seo"]["score"])

        self.audit_results["overall_score"] = int(sum(scores) / len(scores)) if scores else 0

    def run_full_audit(self):
        """Run complete store audit"""
        print("=" * 60)
        print("[SEARCH] OUBON SHOP - COMPREHENSIVE STORE AUDIT")
        print("=" * 60)
        print(f"Store: {self.store_url}")
        print(f"API Version: {self.api_version}")
        print("=" * 60)

        self.audit_products()
        self.audit_pages()
        self.audit_policies()
        self.audit_navigation()
        self.audit_seo()
        self.audit_theme()

        self.calculate_overall_score()

        print("\n" + "=" * 60)
        print(f"[SUCCESS] AUDIT COMPLETE")
        print(f"Overall Store Health: {self.audit_results['overall_score']}/100")
        print(f"Critical Issues: {len(self.audit_results['critical_issues'])}")
        print(f"Warnings: {len(self.audit_results['warnings'])}")
        print("=" * 60)

        return self.audit_results

    def save_report(self, filename: str = "shopify_audit_report.json"):
        """Save audit report to JSON file"""
        with open(filename, 'w') as f:
            json.dump(self.audit_results, f, indent=2)

        print(f"\n[FILE] Report saved to: {filename}")

    def print_summary(self):
        """Print executive summary"""
        print("\n" + "=" * 60)
        print("[STATS] EXECUTIVE SUMMARY")
        print("=" * 60)

        print(f"\n Overall Store Health: {self.audit_results['overall_score']}/100")

        if self.audit_results['overall_score'] >= 80:
            print("   [SUCCESS] EXCELLENT - Store is well-optimized")
        elif self.audit_results['overall_score'] >= 60:
            print("   [WARNING]  GOOD - Some improvements needed")
        elif self.audit_results['overall_score'] >= 40:
            print("   [WARNING]  FAIR - Significant improvements needed")
        else:
            print("   [ERROR] POOR - Critical issues need immediate attention")

        print(f"\n Critical Issues: {len(self.audit_results['critical_issues'])}")
        for issue in self.audit_results['critical_issues'][:3]:
            print(f"   • {issue['area']}: {issue['issue']}")

        print(f"\n[WARNING]  Warnings: {len(self.audit_results['warnings'])}")
        for warning in self.audit_results['warnings'][:3]:
            print(f"   • {warning['area']}: {warning['issue']}")

        print("\n[PACKAGE] Products:")
        print(f"   Total: {self.audit_results['products'].get('total_count', 0)}")
        print(f"   Score: {self.audit_results['products'].get('score', 0)}/100")

        print("\n[FILE] Pages:")
        print(f"   Existing: {self.audit_results['pages'].get('total_count', 0)}")
        missing = self.audit_results['pages'].get('missing_pages', [])
        if missing:
            print(f"   Missing: {', '.join(missing)}")

        print("\n Policies:")
        existing_policies = self.audit_results['policies'].get('existing', [])
        missing_policies = self.audit_results['policies'].get('missing', [])
        print(f"   Configured: {', '.join(existing_policies) if existing_policies else 'None'}")
        if missing_policies:
            print(f"   Missing: {', '.join(missing_policies)}")

        print("\n" + "=" * 60)
        print("[NOTE] NEXT STEPS:")
        print("=" * 60)
        print("1. Review full report: shopify_audit_report.json")
        print("2. Check manual editing checklist: docs/SHOPIFY_SEO_CHECKLIST.md")
        print("3. Login to Shopify Admin: https://{}/admin".format(self.store_url))
        print("4. Start with CRITICAL issues first")
        print("=" * 60)


def main():
    """Main entry point"""
    try:
        auditor = ShopifyAuditor()
        results = auditor.run_full_audit()
        auditor.save_report()
        auditor.print_summary()

    except Exception as e:
        print(f"\n[ERROR] Audit failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
