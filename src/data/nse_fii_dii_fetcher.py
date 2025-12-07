"""
NSE India FII/DII Flow Data Fetcher

Scrapes institutional flow data from NSE India official website.
Provides daily FII/DII buying/selling activity for individual stocks and market-wide.
"""

import aiohttp
from bs4 import BeautifulSoup
import structlog
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import json

logger = structlog.get_logger(__name__)


class NSEFIIDIIFetcher:
    """
    Fetches FII/DII flow data from NSE India.

    Data Sources:
    1. Daily FII/DII Turnover (market-wide)
    2. Bulk Deals (stock-specific institutional activity)
    3. Participant-wise Trading Volumes
    """

    BASE_URL = "https://www.nseindia.com"

    # NSE endpoints
    FII_DII_ENDPOINT = f"{BASE_URL}/api/fiidiiTradeReact"
    BULK_DEALS_ENDPOINT = f"{BASE_URL}/api/snapshot-capital-market-largedeal"

    # Required headers to bypass NSE anti-scraping
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://www.nseindia.com/reports-indices-historical-equityMarket'
    }

    REQUEST_DELAY = 2.0  # seconds (NSE is strict on rate limiting)
    MAX_RETRIES = 3

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.cookies: Dict[str, str] = {}
        self.last_request_time = None

    async def _ensure_session(self):
        """Ensure aiohttp session exists with cookies."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=15)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers=self.HEADERS
            )
            # Get session cookies by visiting homepage
            await self._initialize_cookies()

    async def _initialize_cookies(self):
        """
        Initialize session cookies by visiting NSE homepage.
        NSE requires valid session cookies before API calls work.
        """
        try:
            async with self.session.get(self.BASE_URL) as response:
                if response.status == 200:
                    # Store cookies for subsequent requests
                    for cookie in response.cookies.values():
                        self.cookies[cookie.key] = cookie.value
                    logger.info("NSE session cookies initialized")
        except Exception as e:
            logger.error("Failed to initialize NSE cookies", error=str(e))

    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def _rate_limit(self):
        """Implement rate limiting between requests."""
        if self.last_request_time is not None:
            elapsed = asyncio.get_event_loop().time() - self.last_request_time
            if elapsed < self.REQUEST_DELAY:
                await asyncio.sleep(self.REQUEST_DELAY - elapsed)

        self.last_request_time = asyncio.get_event_loop().time()

    async def get_market_wide_flows(self, date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get market-wide FII/DII flows for a specific date.

        Args:
            date: Date in DD-MMM-YYYY format (e.g., '07-Dec-2024').
                  If None, fetches latest available data.

        Returns:
            Dictionary with FII/DII flow data:
            {
                'date': '07-Dec-2024',
                'fii_gross_purchase': 12345.67,  # Crores
                'fii_gross_sale': 10234.56,
                'fii_net': 2111.11,
                'dii_gross_purchase': 8765.43,
                'dii_gross_sale': 7654.32,
                'dii_net': 1111.11,
                'net_institutional_flow': 3222.22,
                'source': 'nse'
            }
        """
        await self._ensure_session()
        await self._rate_limit()

        try:
            # NSE FII/DII API endpoint
            async with self.session.get(
                self.FII_DII_ENDPOINT,
                cookies=self.cookies
            ) as response:
                if response.status == 200:
                    data = await response.json()

                    # Parse NSE response format
                    # Typical structure: array of objects with date, category, buyValue, sellValue
                    if not data:
                        return None

                    # Find latest date or specified date
                    target_date = date or self._get_latest_trading_date(data)

                    fii_data = next((item for item in data if 'FII' in item.get('category', '') and item.get('date') == target_date), None)
                    dii_data = next((item for item in data if 'DII' in item.get('category', '') and item.get('date') == target_date), None)

                    if not fii_data and not dii_data:
                        logger.warning("No FII/DII data found", date=target_date)
                        return None

                    # Parse values (NSE returns in crores)
                    result = {
                        'date': target_date,
                        'fii_gross_purchase': float(fii_data.get('buyValue', 0)) if fii_data else 0,
                        'fii_gross_sale': float(fii_data.get('sellValue', 0)) if fii_data else 0,
                        'fii_net': 0,
                        'dii_gross_purchase': float(dii_data.get('buyValue', 0)) if dii_data else 0,
                        'dii_gross_sale': float(dii_data.get('sellValue', 0)) if dii_data else 0,
                        'dii_net': 0,
                        'net_institutional_flow': 0,
                        'source': 'nse'
                    }

                    # Calculate net flows
                    result['fii_net'] = result['fii_gross_purchase'] - result['fii_gross_sale']
                    result['dii_net'] = result['dii_gross_purchase'] - result['dii_gross_sale']
                    result['net_institutional_flow'] = result['fii_net'] + result['dii_net']

                    logger.info("NSE FII/DII data fetched", date=target_date, fii_net=result['fii_net'])
                    return result

                elif response.status == 403:
                    logger.warning("NSE access forbidden - reinitializing cookies")
                    await self._initialize_cookies()
                    return None
                else:
                    logger.warning("NSE FII/DII fetch failed", status=response.status)
                    return None

        except Exception as e:
            logger.error("NSE FII/DII fetch error", error=str(e), exc_info=True)
            return None

    async def get_bulk_deals(self, ticker: str, days: int = 30) -> Optional[List[Dict[str, Any]]]:
        """
        Get bulk/block deals for a specific stock (institutional activity indicator).

        Bulk deals = Transactions > 0.5% of total equity
        Block deals = Large off-market transactions

        Args:
            ticker: Stock ticker (e.g., 'RELIANCE', 'TCS')
            days: Number of days to look back

        Returns:
            List of bulk/block deals with institutional buyer/seller info
        """
        await self._ensure_session()
        await self._rate_limit()

        # Remove .NS/.BO suffix for NSE lookup
        symbol = ticker.replace('.NS', '').replace('.BO', '')

        try:
            async with self.session.get(
                self.BULK_DEALS_ENDPOINT,
                cookies=self.cookies
            ) as response:
                if response.status == 200:
                    data = await response.json()

                    # Filter for target symbol
                    deals = [
                        deal for deal in data
                        if deal.get('symbol', '').upper() == symbol.upper()
                    ]

                    logger.info("NSE bulk deals fetched", ticker=ticker, count=len(deals))
                    return deals

                else:
                    logger.warning("NSE bulk deals fetch failed", status=response.status)
                    return None

        except Exception as e:
            logger.error("NSE bulk deals error", ticker=ticker, error=str(e))
            return None

    def _get_latest_trading_date(self, data: List[Dict]) -> str:
        """Extract latest trading date from NSE data."""
        if not data:
            return datetime.now().strftime('%d-%b-%Y')

        dates = [item.get('date') for item in data if item.get('date')]
        if dates:
            return max(dates, key=lambda d: datetime.strptime(d, '%d-%b-%Y'))

        return datetime.now().strftime('%d-%b-%Y')

    async def get_fii_dii_trend(self, days: int = 30) -> Dict[str, Any]:
        """
        Get FII/DII trend over the last N days.

        Useful for determining accumulation/distribution patterns.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with trend analysis:
            {
                'fii_net_flow_total': 12345.67,  # Crores (sum of last N days)
                'fii_trend': 'ACCUMULATION',  # or 'DISTRIBUTION' or 'NEUTRAL'
                'fii_positive_days': 18,  # Days with net buying
                'dii_net_flow_total': 8765.43,
                'dii_trend': 'ACCUMULATION',
                'dii_positive_days': 20,
                'days_analyzed': 30
            }
        """
        # Note: This would require historical API calls or cached data
        # Implementation depends on whether NSE provides historical endpoint
        # or if we need to maintain our own database

        logger.warning("FII/DII trend analysis requires historical data - implement caching/DB")
        return {
            'error': 'Historical trend analysis not yet implemented',
            'recommendation': 'Implement with database caching of daily flows'
        }

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Singleton instance
_nse_fii_dii_fetcher: Optional[NSEFIIDIIFetcher] = None


def get_nse_fii_dii_fetcher() -> NSEFIIDIIFetcher:
    """Get singleton NSEFIIDIIFetcher instance."""
    global _nse_fii_dii_fetcher
    if _nse_fii_dii_fetcher is None:
        _nse_fii_dii_fetcher = NSEFIIDIIFetcher()
    return _nse_fii_dii_fetcher
