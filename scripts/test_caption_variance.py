"""
Task #16: Unit test for template caption variance.

Old behaviour: 5 hard-coded niche templates produced identical copy for every
product in the same niche (only the title swapped in). That's a bad look on a
Shopify store where a customer might compare 3 products side by side.

This test builds 6 products in the same niche and asserts:
  1. All 6 captions are distinct strings.
  2. The same product title + price always produces the same caption
     (determinism — important for cache/idempotency).
  3. Captions contain NO emojis and NO hashtags.
  4. Captions reference the actual product title.
  5. Price-tier language varies with price ("$X", "mid-tier", "premium").
  6. Feature hints from the title (e.g. "wireless", "stainless") actually
     show up in the generated copy.
"""

from __future__ import annotations

import sys
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ospra_os.api.product_analysis_routes import _generate_template_caption


EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002700-\U000027BF"
    "\U0001F900-\U0001F9FF"
    "]"
)


def test_caption_variance():
    niche = "smart_home"

    products = [
        {"title": "Smart LED Strip Light", "price": 19.99, "tags": ["led", "rgb", "wifi"]},
        {"title": "Smart Home Hub", "price": 49.00, "tags": ["smart", "voice", "wifi"]},
        {"title": "Smart Plug WiFi",  "price": 12.50, "tags": ["wifi", "smart"]},
        {"title": "Smart Thermostat", "price": 129.00, "tags": ["smart", "wireless", "app"]},
        {"title": "Smart Button", "price": 8.99, "tags": ["wireless", "compact"]},
        {"title": "Smart Door Sensor", "price": 24.00, "tags": ["wireless", "battery", "sensor"]},
    ]

    captions = []
    for p in products:
        cap = _generate_template_caption(p["title"], niche, p["price"], p["tags"])
        captions.append(cap)
        print(f"\n--- {p['title']} (${p['price']:.2f}) ---")
        print(cap)

    # ASSERTION 1: all distinct
    unique = set(captions)
    assert len(unique) == len(captions), (
        f"Captions are not all unique: {len(captions) - len(unique)} duplicates"
    )

    # ASSERTION 2: deterministic
    for p in products:
        c1 = _generate_template_caption(p["title"], niche, p["price"], p["tags"])
        c2 = _generate_template_caption(p["title"], niche, p["price"], p["tags"])
        assert c1 == c2, f"Non-deterministic caption for {p['title']}"

    # ASSERTION 3: no emojis / no hashtags
    for p, c in zip(products, captions):
        assert not EMOJI_RE.search(c), f"Emoji leaked into caption for {p['title']}"
        assert "#" not in c, f"Hashtag found in caption for {p['title']}"

    # ASSERTION 4: title appears in caption
    for p, c in zip(products, captions):
        assert p["title"] in c, (
            f"Product title '{p['title']}' missing from its caption"
        )

    # ASSERTION 5: price-tier language varies
    # Low-price product should say something like "under $" or show its exact price;
    # high-price product should use premium language.
    low_cap = captions[4]   # Smart Button $8.99
    high_cap = captions[3]  # Smart Thermostat $129
    assert "under $" in low_cap.lower() or "$9" in low_cap, (
        f"Low-price product missing budget-tier language: {low_cap}"
    )
    assert "premium" in high_cap.lower() or "$129" in high_cap, (
        f"High-price product missing premium-tier language: {high_cap}"
    )

    # ASSERTION 6: feature hints surface where applicable
    # Strip light has "led" + "rgb" tags -> should mention lighting OR color
    strip_cap = captions[0].lower()
    assert any(kw in strip_cap for kw in ["lighting", "color", "ambient", "rgb"]), (
        f"LED/RGB product caption missing lighting cues: {captions[0]}"
    )

    # Thermostat has "wireless" tag -> should mention wireless
    thermo_cap = captions[3].lower()
    assert "wireless" in thermo_cap, (
        f"Wireless-tagged product missing wireless cue: {captions[3]}"
    )

    print(f"\n[PASS] Generated {len(captions)} distinct captions in niche '{niche}'.")
    return 0


if __name__ == "__main__":
    sys.exit(test_caption_variance())
