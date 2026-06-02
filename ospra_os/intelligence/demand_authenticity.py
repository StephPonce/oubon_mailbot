"""
Demand Authenticity / Divergence scoring.

Distinguishes ORGANIC, real demand from PAID / MANUFACTURED hype — the defense
against being gamed by bought likes & comments or "pump" products with no real
backing.

IMPORTANT distinction (do not conflate):
  * AUTHENTICITY (this module): is the demand REAL or MANUFACTURED? Catches
    bought engagement / paid pumps. A product with huge TikTok views but zero
    Google-search intent and no Amazon purchase signal is manufactured.
  * SATURATION (separate, existing scorer): is the market EMERGING or already
    OWNED by a big brand? That's the GOVEE problem — GOVEE's demand is real
    (authentic), it's just saturated. Saturation, not authenticity, demotes it.

Principle: no single signal is trustworthy, but signals differ in how EXPENSIVE
they are to fake. We weight hard-to-fake ORGANIC signals (Google Trends search
intent, Amazon verified-review / BSR velocity, real sales) against easy-to-fake
PROMOTED signals (ad volume, TikTok/IG likes & views, claimed order counts).
When promoted buzz is HIGH but organic demand is ABSENT, that's a DIVERGENCE →
likely manufactured → HEAVILY DEMOTED (not excluded — kept visible as a "hyped
but unproven" category, per product decision).

This module is PURE (no I/O) so ``compute_authenticity`` is deterministically
unit-testable. ``signals_from_product`` maps live product fields to the two
strengths (best-effort; LIVE-TUNE the normalizers against real data ranges).

The divergence signal gets MUCH stronger once time-series snapshots exist —
then ``organic_strength`` / ``promoted_strength`` become true VELOCITIES
(rate of change), which is what truly separates a flash pump from sustained
organic growth.

────────────────────────────────────────────────────────────────────────────
WIRING (for the live pipeline — gated, demote-only):

    from ospra_os.intelligence.demand_authenticity import (
        signals_from_product, compute_authenticity, AUTHENTICITY_ENABLED,
    )
    if AUTHENTICITY_ENABLED:
        org, promo, n_org = signals_from_product(product)
        auth = compute_authenticity(
            organic_strength=org, promoted_strength=promo, n_organic_sources=n_org
        )
        oi_score = oi_score * auth.multiplier           # demote-only (<= 1.0)
        product['authenticity_score'] = auth.score
        product['authenticity_label'] = auth.label      # corroborated/organic/unproven/manufactured
        product['authenticity_divergence'] = auth.divergence_flag
        product['authenticity_reasons'] = auth.reasons  # surface in UI ("why")
────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

# Master flag — default OFF so this is a safe A/B toggle, like winner-first.
AUTHENTICITY_ENABLED = os.getenv("DISCOVERY_AUTHENTICITY_ENABLED", "false").lower() == "true"

# Tunables (env-overridable; the discovery operator tunes these against live runs).
# Heavy demote per product decision: manufactured hype is demoted, NOT excluded.
DIVERGENCE_DEMOTE_MULTIPLIER = float(os.getenv("DISCOVERY_DIVERGENCE_DEMOTE", "0.4"))
PROMOTED_HIGH = float(os.getenv("DISCOVERY_PROMOTED_HIGH", "0.6"))  # "lots of paid/social buzz"
ORGANIC_LOW = float(os.getenv("DISCOVERY_ORGANIC_LOW", "0.25"))     # "little real demand"
# When promoted buzz is high but organic demand was NOT measured (we never
# gathered Google Trends / review data this run), the honest verdict is
# "unverified hype" — suspicious, but NOT confirmed fake. Moderate demote, not
# the heavy one. (This is what stopped real winners like GOVEE being nuked to
# zero when Google Trends came back empty: absence of measurement is not
# evidence of fakeness.)
UNVERIFIED_HYPE_MULTIPLIER = float(os.getenv("DISCOVERY_UNVERIFIED_HYPE_DEMOTE", "0.75"))
# Minimum organic sources that must be PRESENT before "manufactured" can fire.
MIN_ORGANIC_FOR_DIVERGENCE = int(os.getenv("DISCOVERY_MIN_ORGANIC_FOR_DIVERGENCE", "1"))


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


@dataclass
class AuthenticityResult:
    score: float            # 0..1 — organic substance minus unsupported hype
    multiplier: float       # demote-only factor for oi_score (always <= 1.0)
    divergence_flag: bool   # True = promoted buzz not backed by organic demand
    label: str              # 'corroborated' | 'organic' | 'unproven' | 'manufactured'
    reasons: List[str] = field(default_factory=list)


def compute_authenticity(
    *,
    organic_strength: float,
    promoted_strength: float,
    n_organic_sources: int = 0,
) -> AuthenticityResult:
    """
    Score how ORGANIC (vs manufactured) a product's demand is.

    Args:
        organic_strength: 0..1 aggregate of HARD-to-fake demand signals
            (Google Trends intent, Amazon review/BSR velocity, real sales).
        promoted_strength: 0..1 aggregate of EASY-to-fake / paid buzz
            (ad volume, TikTok/IG likes & views, claimed order counts).
        n_organic_sources: count of independent organic signals present
            (corroboration across independent hard signals raises confidence).

    Returns AuthenticityResult with a DEMOTE-ONLY multiplier (<= 1.0): real
    organic demand is never inflated here — the honest scorer already credits
    real signals; this layer only PUNISHES manufactured hype.
    """
    organic = _clamp01(organic_strength)
    promoted = _clamp01(promoted_strength)
    gap = promoted - organic  # positive = more hype than substance
    reasons: List[str] = []

    # Substance = organic demand minus HALF of the unsupported hype.
    score = _clamp01(organic - max(0.0, gap) * 0.5)

    promoted_high = promoted >= PROMOTED_HIGH
    organic_low = organic <= ORGANIC_LOW
    organic_measured = n_organic_sources >= MIN_ORGANIC_FOR_DIVERGENCE

    # CONFIRMED MANUFACTURED: we MEASURED organic demand, it's low, yet promoted
    # buzz is high. Heavy demote. organic_measured is REQUIRED so we never brand
    # a product "fake" merely because we failed to gather its organic data this
    # run — that false-positive nuked real winners (GOVEE) to zero. Absence of
    # measurement is not evidence of fakeness.
    if promoted_high and organic_low and organic_measured:
        multiplier = DIVERGENCE_DEMOTE_MULTIPLIER
        divergence = True
        label = "manufactured"
        reasons.append(
            f"Measured organic demand low ({organic:.2f}) across {n_organic_sources} "
            f"organic source(s) despite high promoted buzz ({promoted:.2f}) — likely "
            f"paid/manufactured. Heavily demoted (kept visible)."
        )
    elif promoted_high and organic_low:
        # Buzz, but organic demand UNMEASURED → suspicious, not confirmed fake.
        multiplier = UNVERIFIED_HYPE_MULTIPLIER
        divergence = False
        label = "unverified_hype"
        reasons.append(
            f"High promoted buzz ({promoted:.2f}) but organic demand not measured this "
            f"run (no Google Trends / review data) — UNVERIFIED, moderately demoted. "
            f"Gather organic signals to confirm real vs manufactured."
        )
    elif organic >= 0.5:
        divergence = False
        # Real demand present. Demote-only model caps the factor at 1.0.
        multiplier = 0.85 + 0.15 * score
        if n_organic_sources >= 2:
            label = "corroborated"
            reasons.append(
                f"Organic demand corroborated across {n_organic_sources} independent "
                f"hard-to-fake sources (strength {organic:.2f})."
            )
        else:
            label = "organic"
            reasons.append(f"Organic demand present (strength {organic:.2f}).")
        if gap > 0.25:
            reasons.append(
                f"Promoted buzz exceeds organic demand by {gap:.2f} — real demand, "
                f"but watch for added hype."
            )
    else:
        # Weak everything → unproven (NOT fake). Slight demote only; the honest
        # scorer already handles missing signals, so we don't double-punish hard.
        divergence = False
        multiplier = 0.85 + 0.15 * score
        label = "unproven"
        reasons.append(
            f"Weak signals (organic {organic:.2f}, promoted {promoted:.2f}) — "
            f"unproven, not yet validated."
        )
        if gap > 0.2:
            reasons.append(
                f"Promoted buzz exceeds organic demand by {gap:.2f} — early hype, treat with caution."
            )

    return AuthenticityResult(
        score=round(score, 3),
        multiplier=round(min(1.0, multiplier), 3),
        divergence_flag=divergence,
        label=label,
        reasons=reasons,
    )


def signals_from_product(product: Dict[str, Any]) -> Tuple[float, float, int]:
    """
    Best-effort adapter: map a discovery product dict to
    (organic_strength, promoted_strength, n_organic_sources).

    LIVE-TUNE the normalizers — the ranges below are reasonable defaults, not
    calibrated against your real data. This is point-in-time today; once
    time-series snapshots exist, feed VELOCITIES here instead of levels and the
    divergence signal becomes far stronger.
    """
    ds = product.get("data_sources", {}) or {}
    organic_parts: List[float] = []
    promoted_parts: List[float] = []

    # ── ORGANIC (hard to fake) ──────────────────────────────────────────────
    gt = ds.get("google_trends") or {}
    gt_interest = float(gt.get("interest") or product.get("google_trend_score") or 0)
    if gt_interest > 0:
        organic_parts.append(_clamp01(gt_interest / 100.0))

    amz = ds.get("amazon_reviews") or {}
    amz_reviews = float(amz.get("total_reviews") or product.get("amazon_review_count") or 0)
    if amz_reviews > 0:
        # log-saturated: ~50 reviews → 0.57, ~500 → 0.90, 1000+ → ~1.0
        organic_parts.append(_clamp01(math.log10(1 + amz_reviews) / 3.0))

    # AliExpress buyer signals — WEAKER organic (AE inflates orders & ratings, so
    # mid-fakeability), but for dropshipping items with no Western footprint they
    # are the only buyer-side evidence available. Down-weighted vs Google/Amazon
    # so they corroborate without masking a true demand vacuum.
    # NOTE: we deliberately do NOT use cj_supplier_quality / warehouse / image
    # count here — those are SUPPLY-side signals and say nothing about whether
    # customers WANT the product; treating them as demand would defeat the check.
    ali = ds.get("aliexpress") or {}
    ali_orders = float(ali.get("orders") or product.get("sales_count") or 0)
    if ali_orders > 0:
        # log-saturated and down-weighted: ~100k orders → ~0.7
        organic_parts.append(_clamp01(math.log10(1 + ali_orders) / 5.0) * 0.7)

    ae_sig = ds.get("aliexpress_signals") or {}
    ae_rating = float(ae_sig.get("rating_stars") or product.get("aliexpress_rating") or 0)
    if ae_rating >= 4.0:
        organic_parts.append(0.4)  # decent verified-buyer rating = weak positive

    # ── PROMOTED (easy to fake) ─────────────────────────────────────────────
    if product.get("winner_source") == "meta_ads" or product.get("meta_winner_match"):
        # Being a Meta-ad "winner" is a strong PROMOTED signal (someone is
        # paying to push it) — not by itself evidence of organic demand.
        promoted_parts.append(0.8)

    tk = ds.get("tiktok") or {}
    tk_views = float(tk.get("views") or 0)
    if tk_views > 0:
        # log-saturated: ~10M views → ~1.0
        promoted_parts.append(_clamp01(math.log10(1 + tk_views) / 7.0))

    organic_strength = sum(organic_parts) / len(organic_parts) if organic_parts else 0.0
    promoted_strength = sum(promoted_parts) / len(promoted_parts) if promoted_parts else 0.0
    return organic_strength, promoted_strength, len(organic_parts)
