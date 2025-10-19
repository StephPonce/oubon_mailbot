from __future__ import annotations
from typing import List, Dict


def get_google_trends(keywords: list[str]) -> List[Dict]:
    return [{"keyword": k, "trend": 0.0} for k in keywords]
