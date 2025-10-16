"""Monitor consumer sentiment across social platforms."""

import logging
from typing import Any, List

try:
    from transformers import pipeline
except ImportError as exc:  # pragma: no cover - optional dependency
    raise ImportError(
        "SentimentBot requires transformers; install with `pip install transformers`."
    ) from exc

logger = logging.getLogger(__name__)

_sentiment_pipeline = pipeline("sentiment-analysis")


class SentimentBot:
    """Wrapper around a HuggingFace sentiment-analysis pipeline."""

    def analyze(self, text: str | List[str]) -> Any:
        """Return sentiment predictions for the supplied text."""
        logger.info("Analyzing sentiment for input type %s", type(text).__name__)
        return _sentiment_pipeline(text)
