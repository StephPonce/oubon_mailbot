"""
Social media platform connectors.

HISTORY:
- twitter.py (empty stub) deleted and meta.py sunset in #57 — Meta's organic
  Graph API is dead; Meta signal now comes from the Ad Library actor in the
  main discovery pipeline.
- reddit.py and xai_twitter.py REMOVED 2026-08 (owner decision; X was already
  retired by D15). Reddit never actually worked: the connector reported
  is_available() unconditionally, hit Reddit's unauthenticated JSON endpoint
  which returns 403, and swallowed non-200 into an empty list — silent zeros
  that looked like a live source. Do not re-add either without an
  authenticated client and a test proving it returns real data.

ACTIVE CONNECTORS:
- AmazonReviewsConnector (via Apify) — primary sentiment signal
- YouTubeConnector — free tier, evidence only (not yet in the numeric composite)
"""
