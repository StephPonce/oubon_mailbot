"""Top-level controller that coordinates all OubonOS agents."""

import asyncio
import logging
from typing import Any, Dict, List

import pandas as pd

from oubonos.ads_bot import AdBot
from oubonos.evaluator import Evaluator
from oubonos.market_bot import MarketBot
from oubonos.prophet_forecaster import ProphetPredictor

logger = logging.getLogger(__name__)


class StoreAgent:
    """Coordinator that wires together market, forecasting, and ads agents."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.market = MarketBot(config)
        self.ads = AdBot(config)
        self.forecaster = ProphetPredictor()
        self.eval = Evaluator()

    async def run_cycle(self) -> None:
        """Execute a single automation cycle across agents."""
        products = await self.market.find_trending_products()
        logger.info("Market bot returned %d products.", len(products))

        df = pd.DataFrame(products)
        forecasts = self.forecaster.predict_demand(df) if not df.empty else None
        if forecasts is not None:
            logger.info("Forecast DataFrame head:\n%s", forecasts.head())

        scored: List[Dict[str, Any]] = [self.eval.score(product) for product in products]
        logger.info("Generated %d product scores.", len(scored))

        await self.ads.launch_campaigns(products)
