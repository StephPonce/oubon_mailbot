"""
F7 — GRADING v2 FACTORS.

Four factors the v1 multiplier chain cannot see, each traceable to a decision:

    app_dependency_penalty   D3 — app/hub/wifi dependence is a support cost
    repeat_purchase_potential D4 — lighting's structural flaw is one-and-done
    brand_fit_score          F2 vision — nobody else scores aesthetic fit
    supplier_resilience      how many healthy sources actually carry this

COMPUTED AND RECORDED, NOT YET APPLIED
--------------------------------------
The spec attaches a hard rule to this feature:

    "Never change weights without a calibration-report comparison
     before/after."

There is no calibration data yet. F1 started logging days ago, and the file-03
launch gate wants four weeks. Folding these factors into `oi_score` today would
change the engine with no way to tell whether it got better, and it would split
the calibration cohort at the exact moment the validation clock started.

But you cannot produce an "after" until the factors are being recorded. So the
only order that satisfies both halves of the rule is: record first, weight
later. Every factor lands in the snapshot's `factor_breakdown` immediately;
`apply_v2_weights` stays behind `GRADING_V2_ENABLED` (default off) and bumps
`weights_version` to v2 when switched on, so pre- and post-change grades never
pool into one correlation.

NONE MEANS UNKNOWN
------------------
`brand_fit_score` is None without a vision result, never 0.0. A zero would be
read as "ugly" by any downstream weighting; None is read as "not assessed".
The distinction is the same one `source_manifest` and `spearman()` make.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

# Weights are DATA, not scattered constants, so a change is one reviewable
# diff and `weights_version` can describe it honestly.
WEIGHTS_V2: Dict[str, float] = {
    "app_dependency_penalty": -0.15,
    "repeat_purchase_potential": 0.10,
    "brand_fit_score": 0.10,
    "supplier_resilience": 0.05,
}
WEIGHTS_V2_VERSION = "v2"

# D4: lighting is structurally one-and-done. These priors exist so the grader
# SEES that flaw instead of treating a lamp like a consumable.
_REPEAT_PRIORS = (
    # (keywords, prior 0-1, why)
    (("diffuser", "candle warmer", "wax melt", "essential oil", "aroma"),
     0.90, "hosts a consumable — oils/melts are the repeat SKU"),
    (("bulb", "e27", "e26", "e14", "gu10", "b22"),
     0.55, "bulbs burn out and get bought in multiples"),
    (("strip", "string light", "fairy light", "tape light"),
     0.45, "extended and replaced in sections"),
    (("filter", "refill", "cartridge", "battery pack"),
     0.85, "explicitly consumable"),
)
_REPEAT_DEFAULT = 0.15  # a lamp is bought once. That is the D4 point.


def grading_v2_enabled() -> bool:
    return os.getenv("GRADING_V2_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def _app_dependency_penalty(fit_check: Dict[str, Any]) -> Optional[float]:
    """D3. 0.0 = no dependency, 1.0 = fully app/hub-bound.

    Reads F2's control check rather than re-parsing the title, so the gate and
    the grade can never disagree about the same product.
    """
    control = fit_check.get("control") or {}
    if control.get("state") == "unverified":
        return None

    if control.get("hub_required"):
        return 1.0
    if control.get("app_required"):
        return 0.9
    if control.get("wifi_dependent"):
        # WiFi WITH a physical control is a real but smaller liability: the
        # product still works when the cloud does not.
        return 0.35 if control.get("physical_control") else 0.75
    if control.get("physical_control"):
        return 0.0
    return None


def _repeat_purchase_potential(text: str, role: Optional[str]) -> float:
    """D4. Category priors plus the consumable-host bonus."""
    if role == "consumable-host":
        return 0.90
    low = text.lower()
    for words, prior, _why in _REPEAT_PRIORS:
        if any(w in low for w in words):
            return prior
    return _REPEAT_DEFAULT


def _brand_fit_score(fit_check: Dict[str, Any],
                     vision: Optional[Dict[str, Any]]) -> Optional[float]:
    """F2's aesthetic verdict, 0-1. None when vision did not run.

    This is the differentiator — no competitor scores whether a product looks
    like it belongs in your store — which is exactly why faking it with a
    default would be self-defeating.
    """
    if vision and vision.get("brand_fit") is not None:
        try:
            return max(0.0, min(1.0, float(vision["brand_fit"])))
        except (TypeError, ValueError):
            return None

    finish = fit_check.get("finish") or {}
    photos = fit_check.get("photos") or {}
    if finish.get("state") == "unverified" and photos.get("state") == "unverified":
        return None

    # Derive a coarse score from what the gate did establish.
    score = 0.0
    seen = 0
    if finish.get("state") in ("pass", "fail"):
        score += 1.0 if finish["state"] == "pass" else 0.0
        seen += 1
    if photos.get("state") in ("pass", "fail"):
        score += 1.0 if photos["state"] == "pass" else 0.0
        seen += 1
    return round(score / seen, 3) if seen else None


def _supplier_resilience(product: Dict[str, Any]) -> Optional[float]:
    """How many healthy sources actually carry this product, normalised 0-1.

    A single-source winner is one supplier delisting away from a dead SKU.
    F4 will make this a real health count across sources; until then it counts
    the suppliers discovery actually found, which today is usually one.
    """
    available = product.get("available_on")
    if isinstance(available, (list, tuple)) and available:
        n = len({str(a).lower() for a in available})
    elif product.get("cross_referenced"):
        n = 2
    else:
        return None
    # 1 source → 0.0, 2 → 0.5, 3+ → 1.0. Being carried twice is the whole
    # difference between resilient and fragile; beyond three it stops mattering.
    return round(min((n - 1) / 2.0, 1.0), 3)


def compute(product: Dict[str, Any],
            vision: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The four v2 factors for one product. Never raises."""
    try:
        fit_check = product.get("fit_check") or {}
        text = " ".join(str(product.get(k) or "") for k in
                        ("clean_title", "title", "title_normalized"))
        return {
            "app_dependency_penalty": _app_dependency_penalty(fit_check),
            "repeat_purchase_potential": _repeat_purchase_potential(
                text, product.get("role_assignment")),
            "brand_fit_score": _brand_fit_score(fit_check, vision),
            "supplier_resilience": _supplier_resilience(product),
            "weights_version": WEIGHTS_V2_VERSION,
            "applied": False,
        }
    except Exception:
        return {"error": "grading_factors_failed", "applied": False}


def apply_v2_weights(product: Dict[str, Any],
                     factors: Dict[str, Any]) -> Optional[float]:
    """Fold the v2 factors into oi_score. OFF unless GRADING_V2_ENABLED.

    Returns the adjusted score, or None when v2 is off or the base score is
    missing. A None factor contributes NOTHING — it is not coerced to zero,
    because "not assessed" must never read as "assessed and bad".
    """
    if not grading_v2_enabled():
        return None
    base = product.get("oi_score")
    if base is None:
        return None
    try:
        base = float(base)
    except (TypeError, ValueError):
        return None

    adjustment = 0.0
    for name, weight in WEIGHTS_V2.items():
        value = factors.get(name)
        if value is None:
            continue
        adjustment += weight * float(value)

    adjusted = round(base * (1.0 + adjustment), 2)
    factors["applied"] = True
    factors["adjustment"] = round(adjustment, 4)
    factors["base_score"] = base
    return adjusted


def stamp(product: Dict[str, Any],
          vision: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compute, record on the product, and apply weights if enabled."""
    factors = compute(product, vision)
    product["grading_factors_v2"] = factors
    adjusted = apply_v2_weights(product, factors)
    if adjusted is not None:
        product["oi_score_v1"] = product.get("oi_score")
        product["oi_score"] = adjusted
    return product
