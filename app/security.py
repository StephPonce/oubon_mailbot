from __future__ import annotations

import base64
import hmac
from hashlib import sha256


def compute_signature(raw_body: bytes, secret: str) -> str:
    mac = hmac.new(secret.encode("utf-8"), raw_body, sha256)
    return base64.b64encode(mac.digest()).decode("utf-8")


def verify_signature(provided: str | None, raw_body: bytes, secret: str) -> bool:
    if not provided:
        return False
    expected = compute_signature(raw_body, secret)
    try:
        return hmac.compare_digest(provided.strip(), expected)
    except Exception:
        return False
