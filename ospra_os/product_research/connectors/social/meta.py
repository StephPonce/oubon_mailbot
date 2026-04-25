"""
Meta (Facebook/Instagram) connector — DEPRECATED placeholder.

The Meta Graph API is no longer viable for product-discovery sentiment:

  • Public Facebook post search (`/search?type=post`) was deprecated in
    2018 — the endpoint no longer exists.
  • Instagram Hashtag Search (``ig_hashtag_search``) requires a
    Business or Creator IG account linked to a Facebook Page that the
    caller owns, capped at 30 unique hashtags per 7 days per IG user.
    That doesn't fit a multi-tenant SaaS where tenants don't all run IG
    businesses and we'd need to query arbitrary product hashtags.

Phase J replaced this with an Apify path, see
``ospra_os/product_research/connectors/apify/instagram_hashtag.py``.

This shim is kept only so legacy import paths
(``from ...social.meta import MetaConnector``) don't break — it
intentionally exposes ``available=False`` so callers that still
reference it route to the Apify connector instead of silently no-op-ing.
"""

from typing import List, Optional

from ..base import BaseConnector, ProductCandidate


class MetaConnector(BaseConnector):
    """Deprecated: the Meta Graph API path is no longer wired. See
    ``InstagramHashtagApify`` (Phase J)."""

    @property
    def name(self) -> str:
        return "Meta (Facebook/Instagram) — deprecated"

    @property
    def source_id(self) -> str:
        return "meta"

    def is_available(self) -> bool:  # type: ignore[override]
        return False

    async def search(self, query: str, **kwargs) -> List[ProductCandidate]:
        return []

    async def get_trending(
        self, category: Optional[str] = None, limit: int = 10
    ) -> List[ProductCandidate]:
        return []

    async def get_hashtag_stats(self, hashtag: str) -> dict:
        return {}
