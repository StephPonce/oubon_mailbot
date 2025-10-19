from __future__ import annotations
from typing import List, Dict
from ospra_os.core.settings import get_settings


def get_tiktok_trending_hashtags(limit: int = 10) -> List[Dict]:
    _ = get_settings().TIKTOK_ACCESS_TOKEN
    return [{"hashtag": "#placeholder_tiktok", "score": 0.0} for _ in range(limit)]
