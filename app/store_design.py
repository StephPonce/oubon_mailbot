"""
Utilities for automating Shopify storefront adjustments.

Requires the `shopify` Python SDK (`pip install ShopifyAPI` or `pip install shopify-python-api`).
"""
from typing import Optional

try:
    import shopify
except ImportError:  # pragma: no cover - library optional at runtime
    shopify = None  # type: ignore

from app.settings import Settings, get_settings


def _ensure_shopify_sdk() -> None:
    if shopify is None:
        raise RuntimeError(
            "The `shopify` package is not installed. Run `pip install shopify-python-api` before calling update_theme."
        )


def _activate_session(settings: Settings) -> Optional["shopify.Session"]:
    shopify.ShopifyResource.set_site(f"https://{settings.SHOPIFY_STORE}/admin/api/{settings.SHOPIFY_API_VERSION}")
    shopify.Session.setup(api_key=settings.SHOPIFY_API_KEY, secret=settings.SHOPIFY_API_SECRET)
    session = shopify.Session(
        shop_url=settings.SHOPIFY_STORE,
        version=settings.SHOPIFY_API_VERSION,
        token=settings.SHOPIFY_API_TOKEN,
    )
    shopify.ShopifyResource.activate_session(session)
    return session


def update_theme(logo_url: str, email_template: str) -> None:
    """
    Update the active theme logo and default email template.
    """
    _ensure_shopify_sdk()

    settings = get_settings()
    if not all([settings.SHOPIFY_STORE, settings.SHOPIFY_API_TOKEN]):
        raise ValueError("Missing Shopify store or access token in environment.")
    if not all([settings.SHOPIFY_API_KEY, settings.SHOPIFY_API_SECRET]):
        raise ValueError("Missing Shopify API key/secret; update .env before running.")

    session = None
    try:
        session = _activate_session(settings)

        asset_payload = {
            "key": "assets/logo.png",
            "attachment": None,
            "src": logo_url,
        }
        shopify.Asset.create({"asset": asset_payload})

        try:
            email_template_resource = shopify.EmailTemplate.find_first()
        except AttributeError:
            email_template_resource = None

        if email_template_resource:
            email_template_resource.update({"body_html": email_template})
        else:
            print("shopify.EmailTemplate not available in current SDK version; skipping email template update.")

        print("Theme update submitted; verify changes inside Shopify admin.")
    finally:
        if session:
            shopify.ShopifyResource.clear_session()
