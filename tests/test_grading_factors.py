"""F7 — grading v2 factors.

The load-bearing test here is the last one: these factors are RECORDED but not
APPLIED by default. The spec forbids changing weights without a before/after
calibration comparison, and there is no calibration data yet — so recording
has to come first, and the default must stay off.
"""


from ospra_os.intelligence import fit_gate, grading_factors
from ospra_os.intelligence.grading_factors import compute, stamp


def _graded(title, **kw):
    """A product that has already been through F2, as it is in the pipeline."""
    p = {
        "clean_title": title,
        "aliexpress_rating": 4.8, "sales_count": 1200,
        "cost_price": 15.0, "suggested_price": 50.0,
        "image_count": 6, "image_url": "https://cdn.example.com/x_800x800.jpg",
        "oi_score": 8.0, "available_on": ["aliexpress"],
    }
    p.update(kw)
    return fit_gate.apply(p)


# ---------------------------------------------------------------------------
# D3 — app dependency
# ---------------------------------------------------------------------------

def test_app_dependency_reads_the_fit_gate_not_the_title_again():
    """Two parsers of the same title eventually disagree. The penalty reads
    F2's own control verdict so the gate and the grade cannot diverge."""
    hub = compute(_graded("Zigbee Smart Bulb warm white hub gateway dimmable"))
    assert hub["app_dependency_penalty"] == 1.0

    clean = compute(_graded("Warm White Desk Lamp USB-C dimmable with touch switch"))
    assert clean["app_dependency_penalty"] == 0.0


def test_wifi_with_physical_control_is_penalised_less_than_without():
    """A lamp that still works when the cloud is down is a smaller liability
    than one that does not. D3 is about support cost, not wifi as a sin."""
    with_switch = compute(_graded("WiFi Smart Lamp E27 warm white dimmable with remote"))
    without = compute(_graded("Tuya WiFi Smart Bulb E27 Alexa warm white dimmable"))
    assert with_switch["app_dependency_penalty"] < without["app_dependency_penalty"]


def test_unknown_control_yields_none_not_zero():
    """0.0 means 'verified no dependency'. Unknown must not claim that."""
    f = compute(_graded("Warm White Lamp 2700K"))
    assert f["app_dependency_penalty"] is None


# ---------------------------------------------------------------------------
# D4 — repeat purchase ("lighting's structural flaw")
# ---------------------------------------------------------------------------

def test_a_lamp_scores_low_on_repeat_purchase():
    """D4 exists because lighting is one-and-done and the grader must see it."""
    f = compute(_graded("Warm White Matte Table Lamp USB-C dimmable touch"))
    assert f["repeat_purchase_potential"] <= 0.2


def test_consumable_host_scores_high():
    """Diffuser/candle-warmer lamps unlock the oils/melts repeat SKU."""
    f = compute(_graded("Ceramic Candle Warmer Lamp warm white USB-C dimmable touch",
                        cost_price=8.0, suggested_price=30.0))
    assert f["repeat_purchase_potential"] >= 0.85


def test_bulbs_beat_lamps_because_they_burn_out():
    lamp = compute(_graded("Warm White Matte Table Lamp USB-C dimmable touch"))
    bulb = compute(_graded("E27 Warm White 2700K Dimmable Bulb with remote"))
    assert bulb["repeat_purchase_potential"] > lamp["repeat_purchase_potential"]


# ---------------------------------------------------------------------------
# brand_fit — the differentiator
# ---------------------------------------------------------------------------

def test_brand_fit_is_none_without_vision_never_a_default():
    """No competitor scores aesthetic fit, which is exactly why inventing a
    default value here would be self-defeating."""
    p = {"clean_title": "Warm White Lamp", "fit_check": {
        "finish": {"state": "unverified"}, "photos": {"state": "unverified"}}}
    assert compute(p)["brand_fit_score"] is None


def test_brand_fit_uses_an_explicit_vision_score_when_present():
    p = _graded("Warm White Matte Lamp USB-C dimmable touch")
    assert compute(p, vision={"brand_fit": 0.82})["brand_fit_score"] == 0.82


# ---------------------------------------------------------------------------
# supplier resilience
# ---------------------------------------------------------------------------

def test_single_source_products_score_zero_resilience():
    """One supplier delisting away from a dead SKU."""
    assert compute(_graded("Warm White Lamp", available_on=["aliexpress"]))[
        "supplier_resilience"] == 0.0


def test_multi_source_products_score_higher():
    two = compute(_graded("Warm White Lamp", available_on=["aliexpress", "cj"]))
    assert two["supplier_resilience"] == 0.5
    three = compute(_graded("Warm White Lamp",
                            available_on=["aliexpress", "cj", "amazon"]))
    assert three["supplier_resilience"] == 1.0


def test_unknown_sources_yield_none():
    p = {"clean_title": "Warm White Lamp", "fit_check": {}}
    assert compute(p)["supplier_resilience"] is None


# ---------------------------------------------------------------------------
# THE RULE: recorded, not applied
# ---------------------------------------------------------------------------

def test_v2_weights_are_off_by_default_and_the_score_is_untouched(monkeypatch):
    """Spec: 'Never change weights without a calibration-report comparison
    before/after.' There is no calibration data yet, so applying these today
    would change the engine with no way to tell if it improved — and would
    split the cohort at the moment the validation clock started."""
    monkeypatch.delenv("GRADING_V2_ENABLED", raising=False)
    p = stamp(_graded("Tuya WiFi Smart Bulb E27 Alexa warm white"))
    assert p["oi_score"] == 8.0, "v2 must not move the live score by default"
    assert p["grading_factors_v2"]["applied"] is False
    assert "oi_score_v1" not in p


def test_factors_are_recorded_even_while_unapplied():
    """You cannot produce the 'after' half of a calibration comparison until
    the factors are already being logged. Recording is the prerequisite."""
    p = stamp(_graded("Tuya WiFi Smart Bulb E27 Alexa warm white"))
    f = p["grading_factors_v2"]
    assert f["app_dependency_penalty"] is not None
    assert f["repeat_purchase_potential"] is not None
    assert f["weights_version"] == grading_factors.WEIGHTS_V2_VERSION


def test_enabling_v2_adjusts_the_score_and_preserves_v1(monkeypatch):
    monkeypatch.setenv("GRADING_V2_ENABLED", "true")
    p = stamp(_graded("Tuya WiFi Smart Bulb E27 Alexa warm white"))
    assert p["oi_score_v1"] == 8.0
    assert p["oi_score"] != 8.0
    assert p["grading_factors_v2"]["applied"] is True
    # app-dependency is a penalty, so a Tuya bulb must score DOWN.
    assert p["oi_score"] < 8.0


def test_none_factors_contribute_nothing_rather_than_zero(monkeypatch):
    """A None factor coerced to 0.0 would apply the full negative weight of a
    factor that was never measured — punishing a product for our ignorance."""
    monkeypatch.setenv("GRADING_V2_ENABLED", "true")
    factors = {"app_dependency_penalty": None, "repeat_purchase_potential": None,
               "brand_fit_score": None, "supplier_resilience": None}
    adjusted = grading_factors.apply_v2_weights({"oi_score": 8.0}, factors)
    assert adjusted == 8.0
    assert factors["adjustment"] == 0.0


def test_ledger_snapshot_carries_the_v2_factors(monkeypatch):
    """Recorded into factor_breakdown so a future calibration can correlate
    each factor against outcomes individually."""
    from ospra_os.intelligence.ledger import _factor_breakdown
    p = stamp(_graded("Warm White Matte Lamp USB-C dimmable touch"))
    fb = _factor_breakdown(p)
    assert fb["v2_factors"] is not None
    assert "repeat_purchase_potential" in fb["v2_factors"]


def test_weights_version_flips_to_v2_only_when_v2_is_live(monkeypatch):
    """If v2 grades were stamped 'v1', calibration would pool two different
    engines — the exact failure the version column prevents."""
    from ospra_os.intelligence import ledger
    monkeypatch.delenv("OSPRA_WEIGHTS_VERSION", raising=False)
    monkeypatch.delenv("GRADING_V2_ENABLED", raising=False)
    assert ledger.grade_versions()["weights_version"] == "v1"

    monkeypatch.setenv("GRADING_V2_ENABLED", "true")
    assert grading_factors.grading_v2_enabled() is True
    assert grading_factors.WEIGHTS_V2_VERSION == "v2"


def test_compute_never_raises_on_garbage():
    assert "repeat_purchase_potential" in compute({}) or "error" in compute({})
    assert compute({"fit_check": "not-a-dict"}).get("applied") is False
