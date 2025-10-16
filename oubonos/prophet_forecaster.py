"""Demand forecasting engine using Prophet."""

import logging
from typing import Optional

import pandas as pd
from prophet import Prophet

logger = logging.getLogger(__name__)


class ProphetPredictor:
    """Thin wrapper around Facebook Prophet for demand forecasts."""

    def predict_demand(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Fit a Prophet model on the provided DataFrame and return the forecast."""
        if df.empty:
            logger.warning("Received empty DataFrame; skipping Prophet forecast.")
            return None
        model = Prophet()
        model.fit(df)
        forecast = model.predict(df)
        logger.info("Forecast generated with %d rows", len(forecast))
        return forecast
