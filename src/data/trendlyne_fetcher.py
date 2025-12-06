"""
Trendlyne.com scraper for Indian stock analysis.

Extracts:
- Ownership patterns (Promoter, FII, DII, Public)
- Peer comparison metrics
- Quality and health scores
- Brokerage price targets
- Corporate governance indicators
"""

import aiohttp
from bs4 import BeautifulSoup
import structlog
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import re
import json

logger = structlog.get_logger(__name__)


class TrendlyneFetcher:
    """
    Scrapes comprehensive analysis data from Trendlyne.com for Indian stocks.

    Features:
    - Ownership breakdown (Promoter/FII/DII/Public)
    - Peer comparison
    - Quality/Health scores
    - Price target consensus
    - Corporate governance metrics
    """

    BASE_URL = "https://trendlyne.com"

    # Rate limiting
    REQUEST_DELAY = 2.0  # seconds (Trendlyne is stricter)

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 3.0  # seconds

    def __init__(self):
        self.last_request_time = None
        self.session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        """Ensure aiohttp session exists."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=20)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                }
            )

    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def _rate_limit(self):
        """Implement rate limiting."""
        if self.last_request_time is not None:
            elapsed = asyncio.get_event_loop().time() - self.last_request_time
            if elapsed < self.REQUEST_DELAY:
                await asyncio.sleep(self.REQUEST_DELAY - elapsed)

        self.last_request_time = asyncio.get_event_loop().time()

    def _normalize_ticker(self, ticker: str) -> str:
        """
        Convert ticker to Trendlyne format.

        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS')

        Returns:
            Normalized ticker (e.g., 'RELIANCE')
        """
        if ticker.endswith('.NS') or ticker.endswith('.BO'):
            return ticker[:-3]
        return ticker

    async def _fetch_with_retry(self, url: str) -> Optional[str]:
        """Fetch URL with retry logic."""
        await self._ensure_session()

        for attempt in range(self.MAX_RETRIES):
            try:
                await self._rate_limit()

                async with self.session.get(url) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 404:
                        logger.info("trendlyne_page_not_found", url=url)
                        return None
                    elif response.status == 429:
                        logger.warning("trendlyne_rate_limited",
                                     attempt=attempt + 1, url=url)
                        await asyncio.sleep(self.RETRY_DELAY * (attempt + 1) * 2)
                        continue
                    else:
                        logger.warning("trendlyne_fetch_failed",
                                     status=response.status, url=url)
                        if attempt < self.MAX_RETRIES - 1:
                            await asyncio.sleep(self.RETRY_DELAY)

            except asyncio.TimeoutError:
                logger.warning("trendlyne_timeout", attempt=attempt + 1, url=url)
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.RETRY_DELAY)

            except Exception as e:
                logger.error("trendlyne_fetch_error",
                           attempt=attempt + 1, url=url, error=str(e))
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.RETRY_DELAY)

        return None

    def _parse_ownership_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Parse ownership breakdown from Trendlyne page.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            Dictionary with ownership data
        """
        data = {
            'promoter_holding': None,
            'fii_holding': None,
            'dii_holding': None,
            'public_holding': None,
            'pledged_percentage': None,
            'source': 'trendlyne'
        }

        try:
            # Look for ownership section
            # Trendlyne typically has sections with "Shareholding Pattern"
            ownership_section = soup.find(text=re.compile(r'Shareholding.*Pattern|Ownership', re.I))

            if ownership_section:
                container = ownership_section.find_parent('div', class_=re.compile(r'shareholding|ownership'))

                if not container:
                    # Try finding table
                    container = ownership_section.find_parent('table')

                if container:
                    text = container.get_text()

                    # Parse percentages
                    # Pattern: "Promoters: 50.5%" or "Promoter Holding 50.5%"
                    promoter_match = re.search(r'Promoter[s]?.*?(\d+(?:\.\d+)?)\s*%', text, re.I)
                    if promoter_match:
                        data['promoter_holding'] = float(promoter_match.group(1))

                    # FII/FPI holdings
                    fii_match = re.search(r'(?:FII|FPI|Foreign.*Institution).*?(\d+(?:\.\d+)?)\s*%', text, re.I)
                    if fii_match:
                        data['fii_holding'] = float(fii_match.group(1))

                    # DII holdings
                    dii_match = re.search(r'(?:DII|Domestic.*Institution).*?(\d+(?:\.\d+)?)\s*%', text, re.I)
                    if dii_match:
                        data['dii_holding'] = float(dii_match.group(1))

                    # Public holding
                    public_match = re.search(r'Public.*?(\d+(?:\.\d+)?)\s*%', text, re.I)
                    if public_match:
                        data['public_holding'] = float(public_match.group(1))

                    # Pledged shares
                    pledge_match = re.search(r'Pledged.*?(\d+(?:\.\d+)?)\s*%', text, re.I)
                    if pledge_match:
                        data['pledged_percentage'] = float(pledge_match.group(1))

        except Exception as e:
            logger.error("trendlyne_parse_ownership_error", error=str(e))

        return data

    def _parse_quality_scores(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Parse Trendlyne's quality and health scores.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            Dictionary with quality metrics
        """
        data = {
            'trendlyne_rating': None,
            'financial_health': None,
            'valuation_rating': None,
            'growth_rating': None,
            'momentum_rating': None,
            'source': 'trendlyne'
        }

        try:
            # Trendlyne has proprietary ratings (1-10 scale typically)
            # Look for rating sections
            rating_section = soup.find(text=re.compile(r'Rating|Score|Health', re.I))

            if rating_section:
                container = rating_section.find_parent('div') or rating_section.find_parent('section')

                if container:
                    text = container.get_text()

                    # Overall rating
                    overall_match = re.search(r'(?:Overall|Trendlyne).*?Rating.*?(\d+(?:\.\d+)?)', text, re.I)
                    if overall_match:
                        data['trendlyne_rating'] = float(overall_match.group(1))

                    # Financial health
                    health_match = re.search(r'(?:Financial|Health).*?(\d+(?:\.\d+)?)', text, re.I)
                    if health_match:
                        data['financial_health'] = float(health_match.group(1))

                    # Valuation
                    valuation_match = re.search(r'Valuation.*?(\d+(?:\.\d+)?)', text, re.I)
                    if valuation_match:
                        data['valuation_rating'] = float(valuation_match.group(1))

                    # Growth
                    growth_match = re.search(r'Growth.*?(\d+(?:\.\d+)?)', text, re.I)
                    if growth_match:
                        data['growth_rating'] = float(growth_match.group(1))

        except Exception as e:
            logger.error("trendlyne_parse_quality_error", error=str(e))

        return data

    def _parse_price_targets(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Parse brokerage price targets from Trendlyne.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            Dictionary with price target data
        """
        data = {
            'consensus_target': None,
            'high_target': None,
            'low_target': None,
            'num_brokerages': None,
            'upside_percentage': None,
            'source': 'trendlyne'
        }

        try:
            # Look for price target section
            target_section = soup.find(text=re.compile(r'Price.*Target|Target.*Price|Analyst.*Target', re.I))

            if target_section:
                container = target_section.find_parent('div') or target_section.find_parent('section')

                if container:
                    text = container.get_text()

                    # Consensus target
                    consensus_match = re.search(r'(?:Consensus|Average|Mean).*?₹?\s*([0-9,]+(?:\.\d+)?)', text, re.I)
                    if consensus_match:
                        data['consensus_target'] = float(consensus_match.group(1).replace(',', ''))

                    # High/Low range
                    range_match = re.search(r'₹?\s*([0-9,]+(?:\.\d+)?)\s*-\s*₹?\s*([0-9,]+(?:\.\d+)?)', text)
                    if range_match:
                        low_val = float(range_match.group(1).replace(',', ''))
                        high_val = float(range_match.group(2).replace(',', ''))
                        data['low_target'] = min(low_val, high_val)
                        data['high_target'] = max(low_val, high_val)

                    # Number of brokerages
                    brokerage_match = re.search(r'(\d+)\s*(?:brokerage|analyst|firm)', text, re.I)
                    if brokerage_match:
                        data['num_brokerages'] = int(brokerage_match.group(1))

                    # Upside
                    upside_match = re.search(r'(?:upside|potential).*?(\d+(?:\.\d+)?)\s*%', text, re.I)
                    if upside_match:
                        data['upside_percentage'] = float(upside_match.group(1))

        except Exception as e:
            logger.error("trendlyne_parse_targets_error", error=str(e))

        return data

    def _parse_peer_comparison(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Parse peer comparison data.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            Dictionary with peer comparison metrics
        """
        data = {
            'peers': [],
            'sector_pe_avg': None,
            'sector_pb_avg': None,
            'industry_rank': None,
            'source': 'trendlyne'
        }

        try:
            # Look for peer comparison table
            peer_section = soup.find(text=re.compile(r'Peer|Comparison|Competitor', re.I))

            if peer_section:
                # Find table with peer data
                table = peer_section.find_parent('table')

                if table:
                    rows = table.find_all('tr')
                    for row in rows[1:6]:  # Get top 5 peers
                        cells = row.find_all('td')
                        if cells and len(cells) >= 2:
                            peer_name = cells[0].get_text(strip=True)
                            if peer_name:
                                data['peers'].append(peer_name)

                # Extract sector averages
                container = peer_section.find_parent('div')
                if container:
                    text = container.get_text()

                    # Sector P/E
                    sector_pe_match = re.search(r'(?:Sector|Industry).*?P/?E.*?(\d+(?:\.\d+)?)', text, re.I)
                    if sector_pe_match:
                        data['sector_pe_avg'] = float(sector_pe_match.group(1))

                    # Sector P/B
                    sector_pb_match = re.search(r'(?:Sector|Industry).*?P/?B.*?(\d+(?:\.\d+)?)', text, re.I)
                    if sector_pb_match:
                        data['sector_pb_avg'] = float(sector_pb_match.group(1))

        except Exception as e:
            logger.error("trendlyne_parse_peers_error", error=str(e))

        return data

    async def get_ownership_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get ownership breakdown for a stock.

        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS')

        Returns:
            Dictionary with ownership data:
            {
                'promoter_holding': 50.5,
                'fii_holding': 25.3,
                'dii_holding': 15.2,
                'public_holding': 9.0,
                'pledged_percentage': 0.0,
                'source': 'trendlyne'
            }
        """
        logger.info("fetching_trendlyne_ownership", ticker=ticker)

        try:
            symbol = self._normalize_ticker(ticker)

            # Trendlyne URL pattern: /equity/{symbol}/shareholding
            url = f"{self.BASE_URL}/equity/{symbol}/shareholding/"

            html = await self._fetch_with_retry(url)

            if not html:
                # Try alternative URL pattern
                url = f"{self.BASE_URL}/equity/{symbol}/"
                html = await self._fetch_with_retry(url)

            if not html:
                logger.warning("trendlyne_fetch_failed", ticker=ticker)
                return None

            soup = BeautifulSoup(html, 'html.parser')
            ownership = self._parse_ownership_data(soup)

            if ownership['promoter_holding'] is None:
                logger.info("trendlyne_no_ownership_data", ticker=ticker)
                return None

            logger.info("trendlyne_ownership_fetched",
                       ticker=ticker,
                       promoter=ownership['promoter_holding'])

            return ownership

        except Exception as e:
            logger.error("trendlyne_ownership_fetch_failed", ticker=ticker, error=str(e), exc_info=True)
            return None

    async def get_quality_metrics(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get Trendlyne quality and health scores.

        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS')

        Returns:
            Dictionary with quality metrics
        """
        logger.info("fetching_trendlyne_quality", ticker=ticker)

        try:
            symbol = self._normalize_ticker(ticker)
            url = f"{self.BASE_URL}/equity/{symbol}/"

            html = await self._fetch_with_retry(url)

            if not html:
                return None

            soup = BeautifulSoup(html, 'html.parser')
            quality = self._parse_quality_scores(soup)

            logger.info("trendlyne_quality_fetched",
                       ticker=ticker,
                       rating=quality.get('trendlyne_rating'))

            return quality

        except Exception as e:
            logger.error("trendlyne_quality_fetch_failed", ticker=ticker, error=str(e), exc_info=True)
            return None

    async def get_comprehensive_analysis(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive Trendlyne analysis including ownership, quality, and targets.

        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS')

        Returns:
            Comprehensive dictionary with all available data
        """
        logger.info("fetching_trendlyne_comprehensive", ticker=ticker)

        try:
            symbol = self._normalize_ticker(ticker)
            url = f"{self.BASE_URL}/equity/{symbol}/"

            html = await self._fetch_with_retry(url)

            if not html:
                return None

            soup = BeautifulSoup(html, 'html.parser')

            # Parse all sections
            data = {
                'ticker': ticker,
                'symbol': symbol,
                **self._parse_ownership_data(soup),
                **self._parse_quality_scores(soup),
                **self._parse_price_targets(soup),
                **self._parse_peer_comparison(soup),
            }

            # Remove duplicate 'source' keys
            data['source'] = 'trendlyne'

            logger.info("trendlyne_comprehensive_fetched", ticker=ticker)

            return data

        except Exception as e:
            logger.error("trendlyne_comprehensive_fetch_failed", ticker=ticker, error=str(e), exc_info=True)
            return None

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Singleton instance
_trendlyne_fetcher: Optional[TrendlyneFetcher] = None


def get_trendlyne_fetcher() -> TrendlyneFetcher:
    """Get singleton TrendlyneFetcher instance."""
    global _trendlyne_fetcher
    if _trendlyne_fetcher is None:
        _trendlyne_fetcher = TrendlyneFetcher()
    return _trendlyne_fetcher
