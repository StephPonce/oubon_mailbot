from __future__ import annotations
from typing import List, Dict
from ospra_os.core.settings import get_settings


def get_reddit_hot_topics(subreddit: str = "Entrepreneur", limit: int = 10) -> List[Dict]:
    _ = (get_settings().REDDIT_CLIENT_ID, get_settings().REDDIT_SECRET)
    return [{"title": "placeholder_reddit", "upvotes": 0} for _ in range(limit)]
