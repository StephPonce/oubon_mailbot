from typing import List, Optional

# Keyword groups for classification
KEYWORDS_IMPORTANT = [
    "refund", "return", "chargeback", "angry", "complaint",
    "wrong item", "broken", "cancel", "late", "delayed"
]

KEYWORDS_VIP = [
    "press", "investor", "wholesale", "bulk order", "partnership",
    "collaboration", "media", "sponsorship"
]

KEYWORDS_ORDER = [
    "order",
    "package",
    "delivery",
    "tracking",
    "shipment",
    "arrived",
    "missing",
    "unreceived",
    "not received",
    "where is",
    "hasn't arrived",
    "hasnt arrived",
]


# Simple message classifier
def classify_message(subject: str, body: str) -> List[str]:
    text = f"{subject} {body}".lower()
    tags = []

    if any(k in text for k in KEYWORDS_VIP):
        tags.append("VIP")
    elif any(k in text for k in KEYWORDS_ORDER):
        tags.append("Orders")
    elif any(k in text for k in KEYWORDS_IMPORTANT):
        tags.append("Important")
    else:
        tags.append("Routine")

    return tags


# Map tags to auto-reply behavior and templates
def get_rule_for_tags(tags: List[str]) -> Optional[dict]:
    # Priority order: VIP > Orders > Important > Routine
    if "VIP" in tags:
        return {
            "apply_label": "VIP",
            "auto_reply": True,
            "auto_reply_template": "vip_welcome"
        }
    if "Orders" in tags:
        return {
            "apply_label": "Orders",
            "auto_reply": True,
            "auto_reply_template": "order_missing"
        }
    if "Important" in tags:
        return {
            "apply_label": "Admin",
            "auto_reply": True,
            "auto_reply_template": "support_default"
        }
    return {
        "apply_label": "Routine",
        "auto_reply": False,
    }
