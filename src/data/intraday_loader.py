"""
Intraday Data Loader for 1-minute OHLCV Parquet Files

Handles loading and caching of 1-minute bar data stored as parquet files.
Each ticker has its own parquet file with columns: datetime, open, high, low, close, volume
"""

import pandas as pd
import structlog
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta
from functools import lru_cache

logger = structlog.get_logger(__name__)


class IntradayDataLoader:
    """
    Efficient loader for 1-minute OHLCV parquet files.

    File structure expected:
    - One parquet file per ticker
    - Columns: datetime, open, high, low, close, volume
    - Cleaned for splits/bonus issues
    """

    def __init__(self, data_dir: str = None):
        """
        Initialize loader.

        Args:
            data_dir: Path to directory containing parquet files
                     Defaults to env var INTRADAY_DATA_DIR or ./data/intraday
        """
        import os

        if data_dir is None:
            data_dir = os.getenv('INTRADAY_DATA_DIR', './data/intraday')

        self.data_dir = Path(data_dir)

        if not self.data_dir.exists():
            logger.warning("intraday_data_dir_not_found",
                          path=str(self.data_dir),
                          msg="Intraday data not available - will use daily data only")

    def is_available(self) -> bool:
        """Check if intraday data directory exists."""
        return self.data_dir.exists()

    def has_data(self, ticker: str) -> bool:
        """Check if parquet file exists for ticker."""
        file_path = self._get_file_path(ticker)
        return file_path.exists()

    def load(
        self,
        ticker: str,
        lookback_days: int = 90,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Load 1-minute data for ticker.

        Args:
            ticker: Stock symbol (e.g., 'RELIANCE.NS', 'TCS.NS')
            lookback_days: Number of days to load (default 90)
            start_date: Explicit start date (overrides lookback_days)
            end_date: Explicit end date (default: today)

        Returns:
            DataFrame with datetime index and OHLCV columns

        Raises:
            FileNotFoundError: If parquet file doesn't exist
        """
        file_path = self._get_file_path(ticker)

        if not file_path.exists():
            raise FileNotFoundError(f"No intraday data for {ticker} at {file_path}")

        # Load parquet file
        logger.info("loading_intraday_data", ticker=ticker, file=str(file_path))

        try:
            df = pd.read_parquet(file_path)

            # Ensure datetime index
            if 'datetime' in df.columns:
                df.set_index('datetime', inplace=True)

            # Ensure index is datetime
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)

            # Filter by date range
            if start_date is None:
                if end_date is None:
                    end_date = datetime.now()
                start_date = end_date - timedelta(days=lookback_days)

            if end_date is None:
                end_date = datetime.now()

            df = df[(df.index >= start_date) & (df.index <= end_date)]

            logger.info("intraday_data_loaded",
                       ticker=ticker,
                       rows=len(df),
                       start=df.index.min(),
                       end=df.index.max())

            return df

        except Exception as e:
            logger.error("intraday_load_failed", ticker=ticker, error=str(e))
            raise

    def _get_file_path(self, ticker: str) -> Path:
        """
        Get parquet file path for ticker.

        Handles different ticker formats:
        - RELIANCE.NS -> RELIANCE.parquet
        - TCS.BO -> TCS.parquet
        - RELIANCE -> RELIANCE.parquet
        """
        # Strip exchange suffix
        ticker_clean = ticker.replace('.NS', '').replace('.BO', '')

        return self.data_dir / f"{ticker_clean}.parquet"

    def get_available_tickers(self) -> list:
        """Get list of all tickers with intraday data."""
        if not self.is_available():
            return []

        parquet_files = list(self.data_dir.glob('*.parquet'))
        tickers = [f.stem for f in parquet_files]

        return sorted(tickers)
