"""
Test Meta and TikTok Ads Platform Integration
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("="*70)
print("[TEST] TESTING AD PLATFORMS INTEGRATION")
print("="*70)
print()

# Test Meta Ads Platform
print("1⃣  Testing Meta (Facebook/Instagram) Ads Platform...")
print()

try:
    from ospra_os.advertising.meta import MetaAdsManager
    print("   [SUCCESS] MetaAdsManager imported successfully")
except ImportError as e:
    print(f"   [ERROR] Failed to import MetaAdsManager: {e}")
    meta_available = False
else:
    # Check credentials
    meta_credentials = {
        'META_APP_ID': os.getenv('OUBONSHOP_META_APP_ID') or os.getenv('META_APP_ID'),
        'META_APP_SECRET': os.getenv('OUBONSHOP_META_APP_SECRET') or os.getenv('META_APP_SECRET'),
        'META_ACCESS_TOKEN': os.getenv('OUBONSHOP_META_ACCESS_TOKEN') or os.getenv('META_ACCESS_TOKEN'),
        'META_AD_ACCOUNT_ID': os.getenv('OUBONSHOP_META_AD_ACCOUNT_ID') or os.getenv('META_AD_ACCOUNT_ID'),
        'META_PAGE_ID': os.getenv('OUBONSHOP_META_PAGE_ID') or os.getenv('META_PAGE_ID'),
    }

    print("   Checking credentials:")
    all_present = True
    for key, value in meta_credentials.items():
        status = "[SUCCESS]" if value else "[ERROR]"
        print(f"      {status} {key}: {'Set' if value else 'Not set'}")
        if not value:
            all_present = False

    if all_present:
        try:
            # Temporarily set env vars for testing
            for key, value in meta_credentials.items():
                os.environ[key] = value

            meta = MetaAdsManager()
            print("   [SUCCESS] MetaAdsManager initialized successfully")
            meta_available = True
        except Exception as e:
            print(f"   [ERROR] Failed to initialize MetaAdsManager: {e}")
            meta_available = False
    else:
        print("   [WARNING]  Meta Ads credentials not configured")
        meta_available = False

print()

# Test TikTok Ads Platform
print("2⃣  Testing TikTok Ads Platform...")
print()

try:
    from ospra_os.advertising.tiktok import TikTokAdsManager
    print("   [SUCCESS] TikTokAdsManager imported successfully")
except ImportError as e:
    print(f"   [ERROR] Failed to import TikTokAdsManager: {e}")
    tiktok_available = False
else:
    # Check credentials
    tiktok_credentials = {
        'TIKTOK_APP_ID': os.getenv('OUBONSHOP_TIKTOK_APP_ID') or os.getenv('TIKTOK_APP_ID'),
        'TIKTOK_SECRET': os.getenv('OUBONSHOP_TIKTOK_SECRET') or os.getenv('TIKTOK_SECRET'),
        'TIKTOK_ACCESS_TOKEN': os.getenv('OUBONSHOP_TIKTOK_ACCESS_TOKEN') or os.getenv('TIKTOK_ACCESS_TOKEN'),
        'TIKTOK_ADVERTISER_ID': os.getenv('OUBONSHOP_TIKTOK_ADVERTISER_ID') or os.getenv('TIKTOK_ADVERTISER_ID'),
    }

    print("   Checking credentials:")
    all_present = True
    for key, value in tiktok_credentials.items():
        status = "[SUCCESS]" if value else "[ERROR]"
        print(f"      {status} {key}: {'Set' if value else 'Not set'}")
        if not value:
            all_present = False

    if all_present:
        try:
            # Temporarily set env vars for testing
            for key, value in tiktok_credentials.items():
                os.environ[key] = value

            tiktok = TikTokAdsManager()
            print("   [SUCCESS] TikTokAdsManager initialized successfully")
            tiktok_available = True
        except Exception as e:
            print(f"   [ERROR] Failed to initialize TikTokAdsManager: {e}")
            tiktok_available = False
    else:
        print("   [WARNING]  TikTok Ads credentials not configured")
        tiktok_available = False

print()
print("="*70)
print("[SUCCESS] AD PLATFORMS TEST COMPLETE")
print("="*70)
print()

# Summary
print("Summary:")
print(f"  {'[SUCCESS]' if meta_available else '[WARNING] '} Meta (Facebook/Instagram) Ads: {'Available' if meta_available else 'Not configured'}")
print(f"  {'[SUCCESS]' if tiktok_available else '[WARNING] '} TikTok Ads: {'Available' if tiktok_available else 'Not configured'}")
print()

if not meta_available and not tiktok_available:
    print("Next Steps:")
    print("  1. Add credentials to .env file:")
    print()
    print("     # Meta Ads")
    print("     OUBONSHOP_META_APP_ID=your_app_id")
    print("     OUBONSHOP_META_APP_SECRET=your_app_secret")
    print("     OUBONSHOP_META_ACCESS_TOKEN=your_access_token")
    print("     OUBONSHOP_META_AD_ACCOUNT_ID=your_account_id")
    print("     OUBONSHOP_META_PAGE_ID=your_page_id")
    print()
    print("     # TikTok Ads")
    print("     OUBONSHOP_TIKTOK_APP_ID=your_app_id")
    print("     OUBONSHOP_TIKTOK_SECRET=your_secret")
    print("     OUBONSHOP_TIKTOK_ACCESS_TOKEN=your_access_token")
    print("     OUBONSHOP_TIKTOK_ADVERTISER_ID=your_advertiser_id")
    print()
    print("  2. Get Meta credentials from: https://business.facebook.com/settings/ad-accounts")
    print("  3. Get TikTok credentials from: https://ads.tiktok.com/marketing_api/apps")
    print()
elif meta_available and tiktok_available:
    print("[LAUNCH] Both ad platforms are ready to use!")
    print()
    print("You can now:")
    print("  • Create automated ad campaigns for products")
    print("  • Manage campaign budgets and targeting")
    print("  • Track ad performance metrics")
    print("  • Pause/activate campaigns programmatically")
    print()
else:
    platform_name = "Meta Ads" if meta_available else "TikTok Ads"
    other_platform = "TikTok Ads" if meta_available else "Meta Ads"
    print(f"[SUCCESS] {platform_name} is ready!")
    print(f"[WARNING]  Configure {other_platform} to enable multi-platform advertising")
    print()
