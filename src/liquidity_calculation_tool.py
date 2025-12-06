from typing import Annotated, Optional
import pandas as pd
import structlog
from langchain_core.tools import tool
from src.ticker_utils import normalize_ticker
from src.data.fetcher import fetcher as market_data_fetcher

logger = structlog.get_logger(__name__)

# COMPREHENSIVE GLOBAL CURRENCY MAP
# format: suffix -> (currency_code, fx_rate_to_usd)
# Rates approximate as of late 2024/early 2025
EXCHANGE_INFO = {
    # --- Americas ---
    'US': ('USD', 1.0),
    'TO': ('CAD', 0.71),  # Toronto
    'V':  ('CAD', 0.71),  # TSX Venture
    'CN': ('CAD', 0.71),  # Canadian National
    'MX': ('MXN', 0.05),  # Mexico
    'SA': ('BRL', 0.17),  # Brazil (Sao Paulo)
    'BA': ('ARS', 0.001), # Buenos Aires (Highly volatile)
    'SN': ('CLP', 0.001), # Santiago

    # --- Europe (Eurozone) ---
    'DE': ('EUR', 1.05),  # Xetra (Germany)
    'F':  ('EUR', 1.05),  # Frankfurt
    'PA': ('EUR', 1.05),  # Paris
    'AS': ('EUR', 1.05),  # Amsterdam
    'BR': ('EUR', 1.05),  # Brussels
    'MC': ('EUR', 1.05),  # Madrid
    'MI': ('EUR', 1.05),  # Milan
    'LS': ('EUR', 1.05),  # Lisbon
    'VI': ('EUR', 1.05),  # Vienna
    'IR': ('EUR', 1.05),  # Dublin
    'HE': ('EUR', 1.05),  # Helsinki
    'AT': ('EUR', 1.05),  # Athens

    # --- Europe (Non-Euro) ---
    'L':  ('GBP', 1.27),  # London (Pence logic handled in code)
    'SW': ('CHF', 1.13),  # Switzerland
    'S':  ('CHF', 1.13),  # Switzerland
    'ST': ('SEK', 0.09),  # Stockholm
    'OL': ('NOK', 0.09),  # Oslo
    'CO': ('DKK', 0.14),  # Copenhagen
    'IC': ('ISK', 0.007), # Iceland
    'WA': ('PLN', 0.24),  # Warsaw
    'PR': ('CZK', 0.04),  # Prague
    'BD': ('HUF', 0.0026),# Budapest
    'IS': ('TRY', 0.028), # Istanbul
    'ME': ('RUB', 0.01),  # Moscow (Approx/Restricted)

    # --- Asia Pacific ---
    'T':  ('JPY', 0.0067), # Tokyo
    'HK': ('HKD', 0.129),  # Hong Kong
    'SS': ('CNY', 0.138),  # Shanghai
    'SZ': ('CNY', 0.138),  # Shenzhen
    'TW': ('TWD', 0.031),  # Taiwan
    'TWO':('TWD', 0.031),  # Taiwan OTC
    'KS': ('KRW', 0.00072), # Korea KOSPI
    'KQ': ('KRW', 0.00072), # Korea KOSDAQ
    'SI': ('SGD', 0.74),   # Singapore
    'KL': ('MYR', 0.23),   # Kuala Lumpur
    'BK': ('THB', 0.029),  # Bangkok
    'JK': ('IDR', 0.000063), # Jakarta
    'VN': ('VND', 0.000039), # Vietnam
    'PS': ('PHP', 0.017),  # Philippines
    'BO': ('INR', 0.012),  # Bombay
    'NS': ('INR', 0.012),  # NSE India
    'AX': ('AUD', 0.65),   # Australia
    'NZ': ('NZD', 0.58),   # New Zealand

    # --- Middle East & Africa ---
    'TA': ('ILS', 0.27),   # Tel Aviv
    'SR': ('SAR', 0.27),   # Saudi Arabia
    'QA': ('QAR', 0.27),   # Qatar
    'AE': ('AED', 0.27),   # UAE
    'JO': ('ZAR', 0.055),  # Johannesburg
    'EG': ('EGP', 0.02),   # Egypt
}

@tool
async def calculate_liquidity_metrics(ticker: Annotated[Optional[str], "Stock ticker symbol"] = None) -> str:
    """
    Calculate liquidity metrics using the robust MarketDataFetcher.
    Checks 3-month average volume and turnover.
    Handles global currency conversion automatically.
    """
    if not ticker:
        return "Error: No ticker symbol provided."

    normalized_symbol = normalize_ticker(ticker)
    
    try:
        # Use the robust fetcher for history
        hist = await market_data_fetcher.get_historical_prices(normalized_symbol, period="3mo")
        
        if hist.empty:
            logger.warning("no_history_found", ticker=ticker)
            return f"""Liquidity Analysis for {ticker}:
Status: FAIL - Insufficient Data
Avg Daily Volume (3mo): N/A
Avg Daily Turnover (USD): N/A
"""

        # Calculate metrics
        avg_volume = hist['Volume'].mean()
        avg_close = hist['Close'].mean()
        
        # Calculate local turnover
        # NOTE: For UK stocks (.L), prices are in Pence, so we must divide by 100 
        # to get Pounds before converting to USD.
        if normalized_symbol.endswith('.L'):
            avg_turnover_local = avg_volume * (avg_close / 100.0)
            logger.info("pence_adjustment_applied", ticker=ticker)
        else:
            avg_turnover_local = avg_volume * avg_close
        
        # Determine FX Rate based on suffix
        suffix = 'US' # Default
        if '.' in normalized_symbol:
            suffix = normalized_symbol.split('.')[-1].upper()
            
        # Special handling: If no dot, but not US exchange (rare edge case for clean tickers)
        # We assume US for clean tickers (e.g. AAPL) which aligns with 'US' default.
        
        if suffix in EXCHANGE_INFO:
            currency, fx_rate = EXCHANGE_INFO[suffix]
            logger.info("using_static_fx_rate", ticker=ticker, suffix=suffix, currency=currency, rate=fx_rate)
        else:
            # Fallback for unknown suffixes (assume 1.0 but flag it)
            currency = "Unknown (Assumed USD)"
            fx_rate = 1.0
            logger.warning("unknown_currency_suffix", ticker=ticker, suffix=suffix, default="1.0")

        avg_turnover_usd = avg_turnover_local * fx_rate

        # Threshold adjusted for Indian market conditions
        # Indian small/mid caps have lower liquidity than US counterparts
        # $150k is more appropriate for emerging markets like India
        # while $500k was calibrated for US/developed markets
        if suffix in ['NS', 'BO']:  # Indian exchanges (NSE, BSE)
            threshold_usd = 150_000  # $150k for Indian stocks
            threshold_label = "$150,000 USD daily (Indian market threshold)"
        else:
            threshold_usd = 500_000  # $500k for other markets
            threshold_label = "$500,000 USD daily"

        status = "PASS" if avg_turnover_usd > threshold_usd else "FAIL"

        return f"""Liquidity Analysis for {ticker}:
Status: {status}
Avg Daily Volume (3mo): {int(avg_volume):,}
Avg Daily Turnover (USD): ${int(avg_turnover_usd):,}
Details: {currency} turnover converted at FX rate {fx_rate}
Threshold: {threshold_label}
"""

    except Exception as e:
        logger.error("liquidity_calculation_failed", ticker=ticker, error=str(e), exc_info=True)
        return f"""Liquidity Analysis for {ticker}:
Status: ERROR
Error: {str(e)}
"""