"""
Moneycontrol.com scraper for Indian stock analyst data.

Extracts:
- Analyst recommendations (Buy/Hold/Sell count)
- Price targets (min/max/average)
- Earnings estimates
- Quarterly analysis
"""

import aiohttp
from bs4 import BeautifulSoup
import structlog
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import re

logger = structlog.get_logger(__name__)


class MoneycontrolFetcher:
    """
    Scrapes analyst consensus data from Moneycontrol.com for Indian stocks.

    Features:
    - Analyst recommendations aggregation
    - Price target extraction
    - Earnings estimates
    - Rate limiting and retry logic
    """

    BASE_URL = "https://www.moneycontrol.com"
    SEARCH_URL = f"{BASE_URL}/india/stockpricequote"

    # Rate limiting: delay between requests
    REQUEST_DELAY = 1.0  # seconds

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0  # seconds

    def __init__(self):
        self.last_request_time = None
        self.session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        """Ensure aiohttp session exists."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=15)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
            )

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

    def _normalize_ticker(self, ticker: str) -> str:
        """
        Convert ticker format to Moneycontrol symbol.

        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS', 'TCS.BO')

        Returns:
            Normalized ticker without exchange suffix (e.g., 'RELIANCE', 'TCS')
        """
        # Remove .NS or .BO suffix
        if ticker.endswith('.NS') or ticker.endswith('.BO'):
            return ticker[:-3]
        return ticker

    async def _search_stock(self, ticker: str) -> Optional[str]:
        """
        Search for stock on Moneycontrol and get its URL.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Stock page URL if found, None otherwise
        """
        await self._ensure_session()
        await self._rate_limit()

        symbol = self._normalize_ticker(ticker)

        try:
            # Try direct search
            search_url = f"{self.BASE_URL}/stocksmarketsindia/"
            params = {'search': symbol, 'type': 'all'}

            async with self.session.get(search_url, params=params) as response:
                if response.status != 200:
                    logger.warning("moneycontrol_search_failed",
                                 ticker=ticker, status=response.status)
                    return None

                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')

                # Find stock link in search results
                # Moneycontrol uses specific patterns for stock links
                links = soup.find_all('a', href=re.compile(r'/india/stockpricequote/'))

                for link in links:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)

                    # Match ticker symbol in link text or href
                    if symbol.upper() in text.upper() or symbol.lower() in href.lower():
                        # Construct full URL
                        if href.startswith('http'):
                            return href
                        else:
                            return f"{self.BASE_URL}{href}"

                # Alternative: Try company financials page
                # Some stocks are found directly at /financials/ pages
                alt_url = f"{self.BASE_URL}/financials/{symbol.lower()}"
                async with self.session.head(alt_url) as head_response:
                    if head_response.status == 200:
                        return alt_url

                logger.info("moneycontrol_stock_not_found", ticker=ticker)
                return None

        except Exception as e:
            logger.error("moneycontrol_search_error", ticker=ticker, error=str(e))
            return None

    async def _fetch_with_retry(self, url: str) -> Optional[str]:
        """
        Fetch URL with retry logic.

        Args:
            url: URL to fetch

        Returns:
            HTML content if successful, None otherwise
        """
        await self._ensure_session()

        for attempt in range(self.MAX_RETRIES):
            try:
                await self._rate_limit()

                async with self.session.get(url) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 404:
                        logger.info("moneycontrol_page_not_found", url=url)
                        return None
                    elif response.status == 429:
                        # Rate limited
                        logger.warning("moneycontrol_rate_limited",
                                     attempt=attempt + 1, url=url)
                        await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                        continue
                    else:
                        logger.warning("moneycontrol_fetch_failed",
                                     status=response.status, url=url)

                        if attempt < self.MAX_RETRIES - 1:
                            await asyncio.sleep(self.RETRY_DELAY)

            except asyncio.TimeoutError:
                logger.warning("moneycontrol_timeout", attempt=attempt + 1, url=url)
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.RETRY_DELAY)

            except Exception as e:
                logger.error("moneycontrol_fetch_error",
                           attempt=attempt + 1, url=url, error=str(e))
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.RETRY_DELAY)

        return None

    def _parse_analyst_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Parse analyst recommendations from page HTML.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            Dictionary with analyst consensus data
        """
        data = {
            'buy_count': 0,
            'hold_count': 0,
            'sell_count': 0,
            'consensus': None,
            'price_target_min': None,
            'price_target_max': None,
            'price_target_avg': None,
            'analysts_count': 0,
            'last_updated': None,
            'source': 'moneycontrol'
        }

        try:
            # Look for analyst recommendation sections
            # Moneycontrol typically has sections like "Analyst Recommendations"
            analyst_section = soup.find(text=re.compile(r'Analyst.*Recommendation', re.I))

            if analyst_section:
                # Find parent container
                container = analyst_section.find_parent('div') or analyst_section.find_parent('section')

                if container:
                    # Look for Buy/Hold/Sell counts
                    # Pattern: "Buy: 15", "Hold: 3", "Sell: 1"
                    text = container.get_text()

                    buy_match = re.search(r'Buy[\s:]+(\d+)', text, re.I)
                    hold_match = re.search(r'Hold[\s:]+(\d+)', text, re.I)
                    sell_match = re.search(r'Sell[\s:]+(\d+)', text, re.I)

                    if buy_match:
                        data['buy_count'] = int(buy_match.group(1))
                    if hold_match:
                        data['hold_count'] = int(hold_match.group(1))
                    if sell_match:
                        data['sell_count'] = int(sell_match.group(1))

                    data['analysts_count'] = data['buy_count'] + data['hold_count'] + data['sell_count']

            # Look for price target data
            # Pattern: "Target: ₹2,800 - ₹3,200" or "Avg Target: ₹3,000"
            price_target_section = soup.find(text=re.compile(r'Price.*Target|Target.*Price', re.I))

            if price_target_section:
                container = price_target_section.find_parent('div') or price_target_section.find_parent('section')

                if container:
                    text = container.get_text()

                    # Look for ranges: ₹2,800 - ₹3,200
                    range_match = re.search(r'₹\s*([0-9,]+(?:\.\d+)?)\s*-\s*₹\s*([0-9,]+(?:\.\d+)?)', text)
                    if range_match:
                        min_price = float(range_match.group(1).replace(',', ''))
                        max_price = float(range_match.group(2).replace(',', ''))
                        data['price_target_min'] = min_price
                        data['price_target_max'] = max_price
                        data['price_target_avg'] = (min_price + max_price) / 2

                    # Look for average: Avg Target: ₹3,000
                    avg_match = re.search(r'(?:Avg|Average|Mean).*?₹\s*([0-9,]+(?:\.\d+)?)', text, re.I)
                    if avg_match:
                        data['price_target_avg'] = float(avg_match.group(1).replace(',', ''))

            # Determine consensus
            if data['analysts_count'] > 0:
                total = data['analysts_count']
                buy_pct = data['buy_count'] / total

                if buy_pct >= 0.6:
                    data['consensus'] = 'BUY'
                elif buy_pct >= 0.4:
                    data['consensus'] = 'HOLD'
                else:
                    data['consensus'] = 'SELL'

            # Try to find last updated date
            date_elem = soup.find(text=re.compile(r'(?:Updated|Last Updated|As of)', re.I))
            if date_elem:
                # Try to extract date
                date_text = date_elem.get_text() if hasattr(date_elem, 'get_text') else str(date_elem)
                date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', date_text)
                if date_match:
                    data['last_updated'] = date_match.group(1)

        except Exception as e:
            logger.error("moneycontrol_parse_error", error=str(e), exc_info=True)

        return data

    async def get_analyst_consensus(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get aggregated analyst recommendations for a stock.

        Args:
            ticker: Indian stock ticker (e.g., 'RELIANCE.NS', 'TCS.BO')

        Returns:
            Dictionary with analyst consensus data:
            {
                'buy_count': 15,
                'hold_count': 3,
                'sell_count': 1,
                'consensus': 'BUY',
                'price_target_min': 2800,
                'price_target_max': 3200,
                'price_target_avg': 3000,
                'analysts_count': 19,
                'last_updated': '06-12-2024',
                'source': 'moneycontrol'
            }

            Returns None if stock not found or no analyst data available.
        """
        logger.info("fetching_moneycontrol_data", ticker=ticker)

        try:
            # Step 1: Find stock URL
            stock_url = await self._search_stock(ticker)

            if not stock_url:
                logger.info("moneycontrol_stock_not_found", ticker=ticker)
                return None

            # Step 2: Fetch stock page
            html = await self._fetch_with_retry(stock_url)

            if not html:
                logger.warning("moneycontrol_fetch_failed", ticker=ticker)
                return None

            # Step 3: Parse analyst data
            soup = BeautifulSoup(html, 'html.parser')
            data = self._parse_analyst_data(soup)

            # Step 4: Validate data
            if data['analysts_count'] == 0:
                logger.info("moneycontrol_no_analyst_coverage", ticker=ticker)
                return None

            logger.info("moneycontrol_data_fetched",
                       ticker=ticker,
                       analysts=data['analysts_count'],
                       consensus=data['consensus'])

            return data

        except Exception as e:
            logger.error("moneycontrol_fetch_failed", ticker=ticker, error=str(e), exc_info=True)
            return None

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Singleton instance
_moneycontrol_fetcher: Optional[MoneycontrolFetcher] = None


def get_moneycontrol_fetcher() -> MoneycontrolFetcher:
    """Get singleton MoneycontrolFetcher instance."""
    global _moneycontrol_fetcher
    if _moneycontrol_fetcher is None:
        _moneycontrol_fetcher = MoneycontrolFetcher()
    return _moneycontrol_fetcher
