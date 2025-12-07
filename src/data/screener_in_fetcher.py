"""
Screener.in scraper for Indian stock financial data and conference call transcripts.

Extracts:
- 10-year financial history
- Quarterly conference call transcripts
- Peer comparison data
- Management quality metrics
"""

import aiohttp
from bs4 import BeautifulSoup
import structlog
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import re

logger = structlog.get_logger(__name__)


class ScreenerInFetcher:
    """
    Scrapes financial data and concall transcripts from Screener.in.

    Features:
    - 10-year financial history
    - Conference call transcripts
    - Quarterly results analysis
    - Peer comparison
    """

    BASE_URL = "https://www.screener.in"

    # Rate limiting
    REQUEST_DELAY = 1.5  # seconds (be respectful to Screener.in)

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0  # seconds

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
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
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
        Convert ticker to Screener.in format.

        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS')

        Returns:
            Company name for Screener.in (e.g., 'RELIANCE')
        """
        # Remove .NS or .BO suffix
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
                        logger.info("screener_in_page_not_found", url=url)
                        return None
                    elif response.status == 429:
                        logger.warning("screener_in_rate_limited",
                                     attempt=attempt + 1, url=url)
                        await asyncio.sleep(self.RETRY_DELAY * (attempt + 1) * 2)  # Longer delay
                        continue
                    else:
                        logger.warning("screener_in_fetch_failed",
                                     status=response.status, url=url)
                        if attempt < self.MAX_RETRIES - 1:
                            await asyncio.sleep(self.RETRY_DELAY)

            except asyncio.TimeoutError:
                logger.warning("screener_in_timeout", attempt=attempt + 1, url=url)
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.RETRY_DELAY)

            except Exception as e:
                logger.error("screener_in_fetch_error",
                           attempt=attempt + 1, url=url, error=str(e))
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.RETRY_DELAY)

        return None

    def _parse_financial_history(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Parse 10-year financial history from company page.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            Dictionary with financial metrics over time
        """
        data = {
            'revenue_history': [],
            'profit_history': [],
            'roe_history': [],
            'debt_to_equity_history': [],
            'years': [],
            'source': 'screener.in'
        }

        try:
            # Screener.in has financial tables with class "data-table"
            tables = soup.find_all('table', class_='data-table')

            for table in tables:
                # Get table headers (years)
                headers = table.find_all('th')
                years = []
                for th in headers[1:]:  # Skip first header (metric name)
                    year_text = th.get_text(strip=True)
                    if year_text and (year_text.startswith('20') or year_text.startswith('FY')):
                        years.append(year_text)

                if not years:
                    continue

                # Parse rows
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if not cells:
                        continue

                    metric_name = cells[0].get_text(strip=True).lower()
                    values = [cell.get_text(strip=True) for cell in cells[1:]]

                    # Parse revenue
                    if 'sales' in metric_name or 'revenue' in metric_name:
                        data['revenue_history'] = self._parse_number_list(values)

                    # Parse profit
                    elif 'net profit' in metric_name or 'profit after tax' in metric_name:
                        data['profit_history'] = self._parse_number_list(values)

                    # Parse ROE
                    elif 'roe' in metric_name or 'return on equity' in metric_name:
                        data['roe_history'] = self._parse_percentage_list(values)

                    # Parse debt/equity
                    elif 'debt' in metric_name and 'equity' in metric_name:
                        data['debt_to_equity_history'] = self._parse_number_list(values)

                if years and not data['years']:
                    data['years'] = years

        except Exception as e:
            logger.error("screener_in_parse_financials_error", error=str(e))

        return data

    def _parse_number_list(self, values: List[str]) -> List[float]:
        """Parse list of number strings (handles Indian numbering: Cr, Lakhs)."""
        result = []
        for val in values:
            try:
                # Remove commas
                val = val.replace(',', '')

                # Handle Indian units: Cr (Crores = 10M), L (Lakhs = 100K)
                multiplier = 1
                if 'Cr' in val or 'cr' in val:
                    multiplier = 10_000_000  # 1 Crore = 10 million
                    val = val.replace('Cr', '').replace('cr', '').strip()
                elif 'L' in val or 'Lakhs' in val.lower():
                    multiplier = 100_000  # 1 Lakh = 100 thousand
                    val = val.replace('L', '').replace('Lakhs', '').replace('lakhs', '').strip()

                # Parse number
                num = float(val) * multiplier
                result.append(num)
            except:
                result.append(None)

        return result

    def _parse_percentage_list(self, values: List[str]) -> List[float]:
        """Parse list of percentage strings."""
        result = []
        for val in values:
            try:
                val = val.replace('%', '').replace(',', '').strip()
                result.append(float(val))
            except:
                result.append(None)

        return result

    def _parse_concall_transcript(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """
        Parse conference call transcript from quarterly results page.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            Dictionary with concall data or None if not found
        """
        data = {
            'quarter': None,
            'date': None,
            'transcript': None,
            'participants': [],
            'key_points': [],
            'management_guidance': {},
            'source': 'screener.in'
        }

        try:
            # Look for concall/transcript sections
            # Screener.in shows transcripts in quarterly results section
            concall_section = soup.find(text=re.compile(r'Conference.*Call|Concall|Transcript', re.I))

            if not concall_section:
                logger.info("screener_in_no_concall_found")
                return None

            # Find parent container
            container = concall_section.find_parent('div') or concall_section.find_parent('section')

            if container:
                # Extract transcript text
                transcript_text = container.get_text(separator='\n', strip=True)

                # Try to identify quarter
                quarter_match = re.search(r'(Q[1-4])\s*(FY|20)\s*(\d{2,4})', transcript_text, re.I)
                if quarter_match:
                    data['quarter'] = quarter_match.group(0)

                # Try to find date
                date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', transcript_text)
                if date_match:
                    data['date'] = date_match.group(1)

                # Extract participants (CEO, CFO, etc.)
                # Look for common patterns
                participants = re.findall(r'((?:Mr\.|Ms\.|Dr\.)\s+[\w\s]+(?:CEO|CFO|MD|Director))', transcript_text)
                data['participants'] = list(set(participants))[:10]  # Limit to 10

                # Extract key financial guidance numbers
                # Pattern: "expect revenue growth of 15-20%"
                guidance_patterns = [
                    (r'revenue.*?growth.*?(\d+(?:\.\d+)?)\s*-?\s*(\d+(?:\.\d+)?)?%', 'revenue_growth'),
                    (r'margin.*?(\d+(?:\.\d+)?)\s*-?\s*(\d+(?:\.\d+)?)?%', 'margin'),
                    (r'capex.*?₹?\s*([0-9,]+)\s*(Cr|cr|crore)', 'capex'),
                ]

                for pattern, key in guidance_patterns:
                    matches = re.findall(pattern, transcript_text, re.I)
                    if matches:
                        data['management_guidance'][key] = str(matches[0])

                # Store full transcript (limit size)
                data['transcript'] = transcript_text[:10000]  # First 10K chars

                # Extract bullet points for key points
                # Look for lists or numbered points
                key_points = re.findall(r'(?:^|\n)\s*[-•*]\s*(.+?)(?:\n|$)', transcript_text)
                if key_points:
                    data['key_points'] = key_points[:10]  # Top 10 points

        except Exception as e:
            logger.error("screener_in_parse_concall_error", error=str(e))
            return None

        return data if data['transcript'] else None

    async def get_financial_history(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get 10-year financial history for a stock.

        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS')

        Returns:
            Dictionary with financial metrics over time:
            {
                'revenue_history': [1000, 1200, 1500, ...],
                'profit_history': [200, 250, 300, ...],
                'roe_history': [15.5, 16.2, 17.1, ...],
                'debt_to_equity_history': [0.5, 0.45, 0.4, ...],
                'years': ['FY2015', 'FY2016', ...],
                'source': 'screener.in'
            }
        """
        logger.info("fetching_screener_in_financials", ticker=ticker)

        try:
            symbol = self._normalize_ticker(ticker)

            # Screener.in URL pattern
            url = f"{self.BASE_URL}/company/{symbol}/consolidated/"

            html = await self._fetch_with_retry(url)

            if not html:
                logger.warning("screener_in_fetch_failed", ticker=ticker)
                return None

            soup = BeautifulSoup(html, 'html.parser')
            data = self._parse_financial_history(soup)

            if not data['years']:
                logger.info("screener_in_no_financial_data", ticker=ticker)
                return None

            logger.info("screener_in_financials_fetched",
                       ticker=ticker, years=len(data['years']))

            return data

        except Exception as e:
            logger.error("screener_in_fetch_failed", ticker=ticker, error=str(e), exc_info=True)
            return None

    async def get_latest_concall(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get latest conference call transcript.

        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS')

        Returns:
            Dictionary with concall data:
            {
                'quarter': 'Q2FY25',
                'date': '15-11-2024',
                'transcript': 'Full text...',
                'participants': ['Mr. Mukesh Ambani, CMD', ...],
                'key_points': ['Strong revenue growth', ...],
                'management_guidance': {
                    'revenue_growth': '15-20%',
                    'margin': '25%',
                    ...
                },
                'source': 'screener.in'
            }
        """
        logger.info("fetching_screener_in_concall", ticker=ticker)

        try:
            symbol = self._normalize_ticker(ticker)

            # Try main company page first
            url = f"{self.BASE_URL}/company/{symbol}/consolidated/"

            html = await self._fetch_with_retry(url)

            if not html:
                return None

            soup = BeautifulSoup(html, 'html.parser')
            concall_data = self._parse_concall_transcript(soup)

            if concall_data:
                logger.info("screener_in_concall_fetched",
                           ticker=ticker, quarter=concall_data.get('quarter'))
            else:
                logger.info("screener_in_no_concall", ticker=ticker)

            return concall_data

        except Exception as e:
            logger.error("screener_in_concall_fetch_failed", ticker=ticker, error=str(e), exc_info=True)
            return None

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Singleton instance
_screener_in_fetcher: Optional[ScreenerInFetcher] = None


def get_screener_in_fetcher() -> ScreenerInFetcher:
    """Get singleton ScreenerInFetcher instance."""
    global _screener_in_fetcher
    if _screener_in_fetcher is None:
        _screener_in_fetcher = ScreenerInFetcher()
    return _screener_in_fetcher
