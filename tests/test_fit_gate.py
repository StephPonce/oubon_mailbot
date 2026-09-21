"""F2 — the fit gate (implements spec 01, the Oubon coherence filter).

The gate's job is to REJECT. Most tests here assert a rejection and the reason
attached to it, because a gate that quietly passes things is worse than no gate
— it looks like diligence.
"""

import pytest

from ospra_os.intelligence import fit_gate
from ospra_os.intelligence.fit_gate import FAIL, PASS, UNVERIFIED, apply, evaluate


def _p(title, **kw):
    """A product that passes everything unless a test breaks one rule."""
    base = {
        "clean_title": title,
        "aliexpress_rating": 4.8,
        "sales_count": 1200,
        "cost_price": 15.00,
        "suggested_price": 50.00,   # 70% gross margin
        "image_count": 6,
        "image_url": "https://cdn.example.com/x_800x800.jpg",
    }
    base.update(kw)
    return base


def _state(product, rule, vision=None):
    return evaluate(product, vision)["fit_check"][rule]["state"]


def _reasons(product, vision=None):
    return evaluate(product, vision)["result"]["fail_reasons"]


# ---------------------------------------------------------------------------
# The two field traps — these cost real money if wrong
# ---------------------------------------------------------------------------

def test_g7_uses_gross_margin_not_the_markup_field(_unused=None):
    """`profit_margin_pct` holds MARKUP. cost 6.16 → retail 18.48 is stored as
    200.0, but gross margin is 66.7%. A product at 200% markup / 66% margin
    passes; one at 50% markup / 33% margin must not, however healthy the
    stored field looks."""
    good = _p("Warm White Table Lamp USB-C dimmable",
              cost_price=6.16, suggested_price=18.48, profit_margin_pct=200.0)
    assert _state(good, "economics") == PASS
    assert evaluate(good)["fit_check"]["economics"]["gross_margin"] == pytest.approx(0.6667, abs=0.001)

    bad = _p("Warm White Table Lamp USB-C dimmable",
             cost_price=10.00, suggested_price=15.00, profit_margin_pct=50.0)
    assert _state(bad, "economics") == FAIL
    assert any("gross margin" in r for r in _reasons(bad))


def test_g5_reads_the_star_rating_not_the_buyer_rating_score():
    """`aliexpress_buyer_rating` is a 0-100 style score (live values 67/70/73),
    NOT stars. Reading it as a rating makes every supplier pass a 4.6 floor."""
    p = _p("Warm White Table Lamp USB-C dimmable",
           aliexpress_rating=4.1, aliexpress_buyer_rating=73)
    assert _state(p, "supplier") == FAIL
    assert any("rating 4.1" in r for r in _reasons(p))


def test_g7_cent_rounding_does_not_decide_the_gate():
    """Retail rounded to the cent lands 2.5x-cost products on 0.59993. Thirteen
    live products failed on that. A rounding artifact must not reject a
    product priced exactly to spec — but a genuine 59% still must."""
    borderline = _p("Warm White Lamp USB-C dimmable",
                    cost_price=11.85, suggested_price=29.62)  # 0.59993
    assert _state(borderline, "economics") == PASS

    genuinely_low = _p("Warm White Lamp USB-C dimmable",
                       cost_price=12.30, suggested_price=29.62)  # ~0.585
    assert _state(genuinely_low, "economics") == FAIL


# ---------------------------------------------------------------------------
# UNVERIFIED is never silently upgraded to PASS
# ---------------------------------------------------------------------------

def test_silence_about_power_is_unverified_not_pass():
    """A title that never mentions a charger is not evidence of a compliant
    one. This is the fabrication the whole audit sweep removed."""
    assert _state(_p("Warm White Desk Lamp dimmable"), "power") == UNVERIFIED


def test_finish_without_vision_is_unverified():
    """G3 needs GPT-4V. Assuming a pass is how a gate becomes decorative."""
    p = _p("Warm White Desk Lamp USB-C dimmable")
    assert _state(p, "finish") == UNVERIFIED
    assert _state(p, "finish", vision={"palette_match": True}) == PASS
    assert _state(p, "finish", vision={"palette_match": False}) == FAIL


def test_needs_review_status_when_nothing_fails_but_gaps_remain():
    """No fails + unverified rules = needs_review, not pass. fit_pass stays
    True so the F1 boolean keeps meaning "nothing was violated"."""
    r = evaluate(_p("Warm White Desk Lamp USB-C dimmable"))["result"]
    assert r["pass"] is True
    assert r["status"] == "needs_review"
    assert r["unverified"]


def test_full_pass_when_vision_confirms_and_nothing_is_missing():
    p = _p("Warm White Matte Desk Lamp USB-C dimmable with touch switch")
    r = evaluate(p, vision={"palette_match": True, "clean_bg": True,
                            "watermark": False})["result"]
    assert r["status"] == "pass", r
    assert r["pass"] is True
    assert r["fail_reasons"] == []


# ---------------------------------------------------------------------------
# The individual rules
# ---------------------------------------------------------------------------

def test_g1_rejects_proprietary_and_primary_cells():
    assert "G1 proprietary charger" in _reasons(
        _p("Desk Lamp warm white proprietary charger dock"))
    assert any("non-rechargeable" in r for r in _reasons(
        _p("Warm White Puck Light with AAA batteries")))


def test_g2_rejects_non_lighting_products_outright():
    """Oubon is a lighting brand. A great kitchen gadget is still not a light."""
    assert "G2 not a lighting product" in _reasons(_p("Silicone Ice Cube Mold With Lid"))


def test_g2_an_led_indicator_is_not_a_luminaire():
    """Bare 'led' matched a Bluetooth headset with an LED display as lighting."""
    assert "G2 not a lighting product" in _reasons(
        _p("OnePlus TWS Wireless Bluetooth Headset LED Display"))


def test_g2_rejects_rgb_without_first_class_warm_white():
    assert "G2 RGB without first-class warm white" in _reasons(
        _p("RGB Gaming Light Bar E27 multicolor"))
    # RGB is fine when warm white is genuinely offered.
    assert _state(_p("RGBCW Smart Bulb E27 warm white 2700K dimmable touch"),
                  "light") == PASS


def test_g4_kills_the_wifi_dependency_d3_targets():
    """Tuya-style bulbs with no physical control are precisely the
    firmware/support liability D3 exists to refuse."""
    assert "G4 wifi-dependent with no physical control" in _reasons(
        _p("Tuya WiFi Smart Bulb E27 Alexa warm white dimmable"))
    assert "G4 hub required" in _reasons(
        _p("Zigbee Smart LED Bulb warm white hub gateway dimmable"))
    # WiFi WITH a physical control is allowed — the app is an enhancement.
    assert _state(_p("WiFi Smart Lamp E27 warm white dimmable with remote"),
                  "control") == PASS


def test_g8_rejects_hardwiring_and_inherited_therapy_claims():
    assert "G8 mains hardwiring required" in _reasons(
        _p("Warm White Ceiling Light hardwired junction box"))
    assert any("therapy" in r for r in _reasons(
        _p("Red Light Therapy Lamp warm 660nm pain relief")))


def test_g6_rejects_images_below_the_floor():
    small = _p("Warm White Lamp USB-C dimmable",
               image_url="https://cdn.example.com/x_300x300.jpg")
    assert any("300px" in r for r in _reasons(small))
    assert "G6 no images" in _reasons(_p("Warm White Lamp USB-C", image_count=0))


# ---------------------------------------------------------------------------
# Role + scene assignment
# ---------------------------------------------------------------------------

def test_role_bands_follow_retail_price():
    v = lambda **k: evaluate(_p("Warm White Matte Lamp USB-C dimmable touch", **k),
                             vision={"palette_match": True, "clean_bg": True,
                                     "watermark": False})["result"]
    assert v(cost_price=20, suggested_price=80)["role_assignment"] == "hero"
    assert v(cost_price=4, suggested_price=20)["role_assignment"] == "accessory"
    assert v(cost_price=10, suggested_price=35)["role_assignment"] == "task"


def test_consumable_host_outranks_price_band():
    """Diffuser/candle-warmer lamps unlock the repeat-purchase SKU, so the spec
    marks them priority sourcing regardless of where their price lands."""
    r = evaluate(_p("Ceramic Candle Warmer Lamp warm white USB-C dimmable touch",
                    cost_price=4, suggested_price=20),
                 vision={"palette_match": True, "clean_bg": True,
                         "watermark": False})["result"]
    assert r["role_assignment"] == "consumable-host"


def test_scene_candidates_come_from_the_spec_vocabulary():
    r = evaluate(_p("Warm White Matte Bedside Sunrise Alarm Lamp USB-C dimmable touch"),
                 vision={"palette_match": True, "clean_bg": True,
                         "watermark": False})["result"]
    assert "bedroom-sleep" in r["scene_candidates"]
    assert set(r["scene_candidates"]) <= set(fit_gate.SCENES)


# ---------------------------------------------------------------------------
# Integration contract with F1
# ---------------------------------------------------------------------------

def test_apply_stamps_the_fields_the_ledger_snapshots():
    p = apply(_p("Silicone Ice Cube Mold With Lid"))
    assert p["fit_pass"] is False
    assert p["fit_reasons"] == ["G2 not a lighting product"]
    assert p["fit_status"] == "fail"


def test_apply_never_raises_on_a_malformed_product():
    """A gate that takes the discovery pipeline down is worse than no gate.
    Discovery is priority #1."""
    p = apply({"clean_title": None, "cost_price": "not-a-number",
               "sales_count": {}, "image_count": []})
    assert "fit_pass" in p


def test_rejections_carry_reasons_because_they_are_training_data():
    """Spec: 'the gate's rejections are training data too'. A rejection with no
    reason teaches nothing."""
    for bad in ("Silicone Ice Cube Mold With Lid",
                "Tuya WiFi Smart Bulb E27 Alexa warm white",
                "RGB Gaming Light Bar multicolor"):
        reasons = _reasons(_p(bad))
        assert reasons and all(r.startswith("G") for r in reasons), bad


def test_filter_flag_is_applied_after_the_ledger_write_not_before():
    """ORDERING GUARD.

    In catalog_warm the fit gate stamps products, the F1 ledger snapshots ALL
    of them, and only then may FIT_GATE_FILTER drop the rejects. Filtering
    first would erase exactly the rejection record the gate exists to create —
    the gate would destroy its own training data and still report success.
    """
    import pathlib

    src = pathlib.Path("ospra_os/tasks/catalog_warm.py").read_text()
    gate_at = src.index("fit_gate.apply(p)")
    ledger_at = src.index("ledger.record_run(")
    filter_at = src.index("FIT_GATE_FILTER")
    # The flag is named twice (here and in the comment); take the LAST use,
    # which is the actual filtering branch.
    filter_at = src.rindex("FIT_GATE_FILTER")

    assert gate_at < ledger_at, "fit gate must stamp before the ledger writes"
    assert ledger_at < filter_at, (
        "FIT_GATE_FILTER must be applied AFTER record_run — filtering first "
        "means rejected products are never snapshotted"
    )
