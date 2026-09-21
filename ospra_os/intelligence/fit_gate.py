"""
F2 — THE FIT GATE (implements spec `01-OUBON-PRODUCT-SPEC.md`).

A hard pass/fail coherence filter every candidate passes. Twelve unrelated
factories produce one brand only if something enforces the brand; this is that
something. Eight rules, G1-G8.

THREE STATES PER RULE, NOT TWO
------------------------------
The spec writes each rule as pass/fail. Real listings do not cooperate: a
supplier title that never mentions a charger is not evidence of a compliant
charger. Marking that "pass" manufactures confidence out of missing data —
the fabrication this codebase has spent a whole audit sweep removing.

So each rule returns PASS, FAIL, or UNVERIFIED:

    PASS        positive evidence the rule is satisfied
    FAIL        positive evidence it is violated  → product rejected
    UNVERIFIED  the listing does not say          → needs a human or vision

`fit_pass` is True when nothing FAILED, which keeps the boolean the F1 ledger
already stores meaningful. `fit_status` carries the nuance: "pass",
"needs_review" (no fails but unverified rules remain), or "fail". A gate that
silently upgraded unverified to pass would be worse than no gate, because it
would look rigorous.

WHY REJECTIONS ARE RETURNED, NOT DROPPED
----------------------------------------
Spec: "Fail = logged with reason (the gate's rejections are training data
too)." Every evaluation returns its reasons so F1 can snapshot them. What the
engine refused to sell is as informative as what it chose.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

PASS = "pass"
FAIL = "fail"
UNVERIFIED = "unverified"

# Scene/role vocabulary — MUST stay identical to the metafields in
# `04-OUBON-THEME-BUILD.md`. A role string that does not match the theme is a
# product that cannot be merchandised.
SCENES = (
    "studio-desk", "bedroom-sleep", "living-ambience",
    "garage-workshop", "car-roadside", "outdoor-garden",
)
ROLE_HERO = "hero"
ROLE_TASK = "task"
ROLE_AMBIENT = "ambient"
ROLE_ACCESSORY = "accessory"
ROLE_CONSUMABLE_HOST = "consumable-host"

# G7 thresholds (spec + D8).
MIN_GROSS_MARGIN = 0.60
# Retail prices are rounded to the cent, which lands products priced at
# exactly 2.5x cost on 0.59993 instead of 0.60. Thirteen live products failed
# on that in the first run against production — a rounding artifact deciding
# a business gate. 0.1pp absorbs cent-rounding; a genuine 59% still fails.
_MARGIN_TOLERANCE = 0.001
HERO_MIN_RETAIL = 50.0
ACCESSORY_MAX_RETAIL = 25.0

# G5 supplier floor.
MIN_RATING = 4.6
MIN_ORDERS = 500
MAX_SHIP_DAYS_US = 12
MIN_STORE_AGE_MONTHS = 6

# G6 photo floor.
MIN_IMAGE_PX = 800


def _text(product: Dict[str, Any]) -> str:
    """Everything the listing says about itself, lowercased.

    Titles are the only description most AliExpress rows carry, so the text
    rules read title + any description-ish fields rather than assuming a
    `description` exists.
    """
    parts = [
        product.get("clean_title"), product.get("title"),
        product.get("title_normalized"), product.get("description"),
        product.get("product_name"),
    ]
    return " ".join(str(p) for p in parts if p).lower()


def _any(text: str, *words: str) -> bool:
    """Word-boundary match so 'app' does not fire inside 'apple'."""
    return any(re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", text) for w in words)


def _num(v: Any) -> Optional[float]:
    try:
        return float(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# G1 — POWER. USB-C or standard wall plug. No proprietary, no primary-cell.
# ---------------------------------------------------------------------------

def _g1_power(text: str) -> Tuple[str, Dict[str, Any], Optional[str]]:
    usb_c = _any(text, "usb-c", "usb c", "type-c", "typec") or "type c" in text
    wall_plug = _any(text, "plug-in", "plug in", "mains", "ac adapter", "wall plug",
                     "e27", "e26", "b22", "gu10")
    proprietary = _any(text, "proprietary", "dock only", "docking charger")
    # Primary (non-rechargeable) cells: the listing names the cell and never
    # says rechargeable.
    primary_cell = (
        _any(text, "aa battery", "aaa battery", "aa batteries", "aaa batteries",
             "cr2032", "button cell", "coin cell")
        and not _any(text, "rechargeable", "recharge", "usb")
    )

    detail = {"usb_c": usb_c, "wall_plug": wall_plug, "proprietary": proprietary,
              "primary_cell_only": primary_cell}
    if proprietary:
        return FAIL, detail, "G1 proprietary charger"
    if primary_cell:
        return FAIL, detail, "G1 non-rechargeable battery only"
    if usb_c or wall_plug:
        return PASS, detail, None
    return UNVERIFIED, detail, None


# ---------------------------------------------------------------------------
# G2 — LIGHT QUALITY. Warm-capable (<=3000K) or CCT-adjustable. RGB only if
# warm white is first-class. Oubon is a LIGHTING brand: a product that is not
# a light cannot pass, however good it is.
# ---------------------------------------------------------------------------

# Bare "led" is NOT here on purpose. It matched "OnePlus TWS Bluetooth Headset
# LED Display" as a lighting product — an LED indicator is not a luminaire.
# LED only counts when attached to something that emits light for a room.
_LIGHT_WORDS = (
    "lamp", "light", "lighting", "bulb", "sconce", "lantern", "luminaire",
    "projector", "nightlight", "night light", "chandelier", "spotlight",
    "downlight", "candle warmer", "diffuser lamp", "ring light", "panel light",
    "led strip", "led bulb", "led lamp", "led light", "led panel",
)


def _is_lighting(text: str) -> bool:
    return _any(text, *_LIGHT_WORDS)


def _g2_light(text: str) -> Tuple[str, Dict[str, Any], Optional[str]]:
    if not _is_lighting(text):
        return FAIL, {"is_lighting": False}, "G2 not a lighting product"

    kelvin = [int(k) for k in re.findall(r"(\d{4})\s*k(?![a-z])", text)]
    warm_words = _any(text, "warm white", "warm-white", "warm light", "2700k",
                      "3000k", "amber", "sunset", "candlelight")
    adjustable = _any(text, "cct", "color temperature", "colour temperature",
                      "tunable", "dimmable", "3 color", "three color", "tri-color")
    rgb = _any(text, "rgb", "rgbw", "rgbic", "multicolor", "multicolour", "gaming")

    min_cct = min(kelvin) if kelvin else None
    detail = {"kelvin_found": kelvin, "min_cct": min_cct, "warm_capable": bool(warm_words),
              "cct_adjustable": adjustable, "rgb": rgb, "is_lighting": True}

    warm_capable = warm_words or (min_cct is not None and min_cct <= 3000)
    if rgb and not (warm_capable or adjustable):
        return FAIL, detail, "G2 RGB without first-class warm white"
    if warm_capable or adjustable:
        return PASS, detail, None
    return UNVERIFIED, detail, None


# ---------------------------------------------------------------------------
# G3 — FINISH. Matte black / white / wood only. Vision check (GPT-4V).
# ---------------------------------------------------------------------------

def _g3_finish(text: str, vision: Optional[Dict[str, Any]]) -> Tuple[str, Dict[str, Any], Optional[str]]:
    # Text vetoes catch the obvious cases for free, before spending on vision.
    banned = _any(text, "chrome", "gamer", "gaming", "rgb gaming", "glossy",
                  "mirror finish", "neon", "cyberpunk")
    detail: Dict[str, Any] = {"allowed": ["matte_black", "white", "wood"],
                              "text_veto": banned, "source": "text"}
    if banned:
        return FAIL, detail, "G3 finish outside palette (text veto)"

    if vision and vision.get("palette_match") is not None:
        detail["source"] = "gpt4v"
        detail["palette_match"] = vision["palette_match"]
        if vision["palette_match"]:
            return PASS, detail, None
        return FAIL, detail, "G3 finish outside palette (vision)"

    # No vision result: say so. Assuming a pass here is exactly how a gate
    # becomes decorative.
    return UNVERIFIED, detail, None


# ---------------------------------------------------------------------------
# G4 — CONTROL. Physical controls/remote must suffice. App optional, no hub.
# ---------------------------------------------------------------------------

def _g4_control(text: str) -> Tuple[str, Dict[str, Any], Optional[str]]:
    hub_required = _any(text, "hub", "gateway", "bridge required", "zigbee")
    app_required = _any(text, "app required", "app control only", "app-only",
                        "requires app", "must use app")
    wifi_mandatory = _any(text, "wifi", "wi-fi", "tuya", "alexa", "google home",
                          "smart life", "bluetooth app")
    physical = _any(text, "remote", "switch", "button", "touch", "knob", "dial",
                    "pull chain", "physical")

    detail = {"app_required": app_required, "hub_required": hub_required,
              "wifi_dependent": wifi_mandatory, "physical_control": physical}

    if hub_required:
        return FAIL, detail, "G4 hub required"
    if app_required:
        return FAIL, detail, "G4 app required"
    # D3: wifi-mandatory is firmware/support liability. Wifi WITH physical
    # control is fine — the app is then an enhancement, which is the rule.
    if wifi_mandatory and not physical:
        return FAIL, detail, "G4 wifi-dependent with no physical control"
    if physical:
        return PASS, detail, None
    return UNVERIFIED, detail, None


# ---------------------------------------------------------------------------
# G5 — SUPPLIER HEALTH. rating >= 4.6, orders >= 500, <= 12d US, store >= 6mo.
# ---------------------------------------------------------------------------

def _g5_supplier(product: Dict[str, Any]) -> Tuple[str, Dict[str, Any], Optional[str]]:
    # `aliexpress_rating` is the 1-5 star rating. `aliexpress_buyer_rating` is
    # NOT — live values are 67/70/73, a percentage-style score. Reading the
    # wrong one turns every supplier into a 5-star supplier.
    rating = _num(product.get("aliexpress_rating")) or _num(product.get("supplier_rating"))
    orders = _num(product.get("sales_count"))
    if orders is None:
        orders = _num((product.get("data_sources", {}).get("aliexpress") or {}).get("orders"))
    ship_days = _num(product.get("ds_delivery_time_days"))
    store_age = _num(product.get("store_age_months"))  # not currently collected

    detail = {"rating": rating, "orders": orders, "ship_days_us": ship_days,
              "store_age_months": store_age}
    reasons = []
    if rating is not None and rating < MIN_RATING:
        reasons.append(f"G5 rating {rating} < {MIN_RATING}")
    if orders is not None and orders < MIN_ORDERS:
        reasons.append(f"G5 orders {int(orders)} < {MIN_ORDERS}")
    if ship_days is not None and ship_days > MAX_SHIP_DAYS_US:
        reasons.append(f"G5 ship {int(ship_days)}d > {MAX_SHIP_DAYS_US}d")
    if store_age is not None and store_age < MIN_STORE_AGE_MONTHS:
        reasons.append(f"G5 store age {store_age}mo < {MIN_STORE_AGE_MONTHS}mo")
    if reasons:
        return FAIL, detail, "; ".join(reasons)

    # Rating AND orders are the two that are actually collected today. Ship
    # time lands on ~12% of rows and store age on none, so requiring all four
    # would mark every product unverified and make the gate useless.
    if rating is not None and orders is not None:
        detail["unchecked"] = [k for k, v in
                               (("ship_days_us", ship_days), ("store_age_months", store_age))
                               if v is None]
        return PASS, detail, None
    return UNVERIFIED, detail, None


# ---------------------------------------------------------------------------
# G6 — PHOTO QUALITY. >=800px, clean background, no watermark. Vision.
# ---------------------------------------------------------------------------

def _g6_photos(product: Dict[str, Any], vision: Optional[Dict[str, Any]]) -> Tuple[str, Dict[str, Any], Optional[str]]:
    image_count = _num(product.get("image_count")) or 0
    url = product.get("image_url") or ""
    # AliExpress CDN encodes size in the path (…_800x800.jpg). Free signal
    # when present; absent is not evidence of a small image.
    m = re.search(r"_(\d{3,4})x(\d{3,4})", str(url))
    px = min(int(m.group(1)), int(m.group(2))) if m else None

    detail: Dict[str, Any] = {"image_count": int(image_count), "min_px": px,
                              "source": "url" if px else "none"}
    if image_count < 1:
        return FAIL, detail, "G6 no images"
    if px is not None and px < MIN_IMAGE_PX:
        return FAIL, detail, f"G6 image {px}px < {MIN_IMAGE_PX}px"

    if vision and vision.get("clean_bg") is not None:
        detail["source"] = "gpt4v"
        detail.update({"clean_bg": vision.get("clean_bg"),
                       "watermark": vision.get("watermark")})
        if vision.get("watermark"):
            return FAIL, detail, "G6 watermark"
        if vision.get("clean_bg") is False:
            return FAIL, detail, "G6 background not clean"
        return PASS, detail, None

    if px is not None and px >= MIN_IMAGE_PX:
        # Resolution verified, background/watermark not. Honest partial.
        detail["unchecked"] = ["clean_bg", "watermark"]
        return UNVERIFIED, detail, None
    return UNVERIFIED, detail, None


# ---------------------------------------------------------------------------
# G7 — ECONOMICS. >= 60% GROSS margin. Hero >= $50. < $25 = accessory only.
# ---------------------------------------------------------------------------

def _g7_economics(product: Dict[str, Any]) -> Tuple[str, Dict[str, Any], Optional[str]]:
    cost = _num(product.get("cost_price")) or _num(product.get("supplier_cost"))
    retail = (_num(product.get("suggested_price")) or _num(product.get("msrp"))
              or _num(product.get("selling_price")))

    detail: Dict[str, Any] = {"landed_cost": cost, "target_retail": retail}
    if cost is None or retail is None or retail <= 0:
        return UNVERIFIED, detail, None

    # GROSS MARGIN = (retail - cost) / retail.
    #
    # NOT `profit_margin_pct`, which this pipeline populates with MARKUP:
    # cost 6.16 → retail 18.48 is stored as 200.0, but the gross margin is
    # 66.7%. Trusting that field would pass products at ~33% real margin and
    # the one-and-done category would lose money on order #1.
    gross_margin = (retail - cost) / retail
    detail["gross_margin"] = round(gross_margin, 4)
    detail["markup_pct_field"] = _num(product.get("profit_margin_pct"))

    role_eligible: List[str] = []
    if retail >= HERO_MIN_RETAIL:
        role_eligible = [ROLE_HERO, ROLE_TASK, ROLE_AMBIENT]
    elif retail < ACCESSORY_MAX_RETAIL:
        role_eligible = [ROLE_ACCESSORY]
    else:
        role_eligible = [ROLE_TASK, ROLE_AMBIENT]
    detail["role_eligible"] = role_eligible

    if gross_margin < MIN_GROSS_MARGIN - _MARGIN_TOLERANCE:
        return FAIL, detail, (
            f"G7 gross margin {gross_margin:.1%} < {MIN_GROSS_MARGIN:.0%}"
        )
    return PASS, detail, None


# ---------------------------------------------------------------------------
# G8 — SAFETY / OPS. No hardwiring, no restricted cells, no therapy claims.
# ---------------------------------------------------------------------------

def _g8_safety(text: str) -> Tuple[str, Dict[str, Any], Optional[str]]:
    hardwire = _any(text, "hardwire", "hardwired", "hard-wired", "junction box",
                    "mains wiring", "electrician")
    therapy = _any(text, "therapy", "therapeutic", "medical", "treats", "cures",
                   "heals", "pain relief", "red light therapy", "phototherapy")
    detail = {"hardwire_required": hardwire, "therapy_claims": therapy}
    if hardwire:
        return FAIL, detail, "G8 mains hardwiring required"
    if therapy:
        # Not a silent drop: the spec's priority zone WANTS light-therapy-
        # adjacent devices, with the claims stripped from inherited copy. This
        # flags copy we would inherit, not the product category.
        return FAIL, detail, "G8 therapy/medical claims in inherited copy"
    return PASS, detail, None


# ---------------------------------------------------------------------------
# Role + scene assignment
# ---------------------------------------------------------------------------

_SCENE_HINTS = {
    "studio-desk": ("desk", "monitor", "studio", "office", "reading", "task",
                    "sketch", "tracing", "laptop"),
    "bedroom-sleep": ("bedside", "bedroom", "sleep", "sunrise", "alarm",
                      "night light", "nightlight", "nursery"),
    "living-ambience": ("living room", "ambient", "ambience", "sunset",
                        "projector", "mood", "floor lamp", "table lamp"),
    "garage-workshop": ("garage", "workshop", "work light", "inspection",
                        "mechanic", "tool"),
    "car-roadside": ("car", "roadside", "trunk", "vehicle", "emergency",
                     "magnetic work"),
    "outdoor-garden": ("garden", "outdoor", "patio", "solar", "pathway",
                       "waterproof", "camping", "lantern"),
}

_CONSUMABLE_HOST_HINTS = ("diffuser", "candle warmer", "wax melt", "aroma",
                          "essential oil", "melt warmer")


def _assign_role(text: str, retail: Optional[float]) -> str:
    # consumable-host outranks price banding: these unlock the repeat-purchase
    # SKU (oils/melts), which the spec marks priority sourcing.
    if _any(text, *_CONSUMABLE_HOST_HINTS):
        return ROLE_CONSUMABLE_HOST
    if retail is None:
        return ROLE_TASK
    if retail >= HERO_MIN_RETAIL:
        return ROLE_HERO
    if retail < ACCESSORY_MAX_RETAIL:
        return ROLE_ACCESSORY
    return ROLE_TASK


def _assign_scenes(text: str) -> List[str]:
    hits = [s for s, words in _SCENE_HINTS.items() if _any(text, *words)]
    return hits


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fit_gate_enabled() -> bool:
    return os.getenv("FIT_GATE_ENABLED", "true").strip().lower() in {"1", "true", "yes"}


def evaluate(product: Dict[str, Any],
             vision: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run G1-G8. Returns the spec's `fit_check` + `result` shape.

    `vision` is an optional GPT-4V result ({palette_match, clean_bg,
    watermark}). Omitted → G3/G6 report UNVERIFIED rather than assuming.
    Never raises: a gate that crashes the pipeline is worse than one that
    abstains.
    """
    text = _text(product)

    checks: Dict[str, Tuple[str, Dict[str, Any], Optional[str]]] = {
        "power": _g1_power(text),
        "light": _g2_light(text),
        "finish": _g3_finish(text, vision),
        "control": _g4_control(text),
        "supplier": _g5_supplier(product),
        "photos": _g6_photos(product, vision),
        "economics": _g7_economics(product),
        "safety": _g8_safety(text),
    }

    fit_check = {name: {"state": state, **detail}
                 for name, (state, detail, _) in checks.items()}
    fail_reasons = [r for (state, _, r) in checks.values() if state == FAIL and r]
    unverified = [n for n, (state, _, _) in checks.items() if state == UNVERIFIED]

    retail = fit_check["economics"].get("target_retail")
    passed = not fail_reasons

    if fail_reasons:
        status = "fail"
    elif unverified:
        status = "needs_review"
    else:
        status = "pass"

    return {
        "fit_check": fit_check,
        "result": {
            "pass": passed,
            "status": status,
            "role_assignment": _assign_role(text, retail) if passed else None,
            "scene_candidates": _assign_scenes(text) if passed else [],
            "fail_reasons": fail_reasons,
            "unverified": unverified,
        },
    }


def apply(product: Dict[str, Any],
          vision: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Evaluate and stamp the result onto the product dict, in place.

    Writes `fit_pass` / `fit_reasons` — the two columns F1's `grade_snapshots`
    already carries — so every rejection is captured in the immutable ledger
    the moment it happens.
    """
    try:
        verdict = evaluate(product, vision)
    except Exception:  # a gate must never take the pipeline down with it
        product["fit_pass"] = None
        product["fit_reasons"] = ["fit_gate_error"]
        return product

    result = verdict["result"]
    product["fit_pass"] = result["pass"]
    product["fit_status"] = result["status"]
    product["fit_reasons"] = result["fail_reasons"] or None
    product["fit_check"] = verdict["fit_check"]
    product["fit_unverified"] = result["unverified"]
    product["role_assignment"] = result["role_assignment"]
    product["scene_candidates"] = result["scene_candidates"]
    return product
