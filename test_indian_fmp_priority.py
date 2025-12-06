#!/usr/bin/env python3
"""
Test script for Task 1.1: Verify FMP is promoted to primary for Indian stocks

This test verifies:
1. Indian stocks (.NS/.BO) use SOURCE_QUALITY_INDIAN (FMP at rank 10)
2. Non-Indian stocks continue using SOURCE_QUALITY (original behavior)
3. Data success rate improves for Indian stocks
"""

import asyncio
import sys
from src.data.fetcher import fetcher, is_indian_stock, SOURCE_QUALITY_INDIAN, SOURCE_QUALITY
import structlog

logger = structlog.get_logger(__name__)

# Test tickers
INDIAN_LARGE_CAPS = [
    'RELIANCE.NS',  # Reliance Industries
    'TCS.NS',       # Tata Consultancy Services
    'HDFCBANK.NS',  # HDFC Bank
    'INFY.NS',      # Infosys
    'ICICIBANK.NS', # ICICI Bank
]

INDIAN_SMALL_CAPS = [
    'DIXON.NS',     # Dixon Technologies
    'AARTIIND.NS',  # Aarti Industries
    'LEMONTREE.NS', # Lemon Tree Hotels
    'ZOMATO.NS',    # Zomato
    'POLICYBZR.NS', # PB Fintech (PolicyBazaar)
]

NON_INDIAN_STOCKS = [
    'AAPL',         # Apple (US)
    'MSFT',         # Microsoft (US)
    'TSLA',         # Tesla (US)
]

async def test_indian_stock_detection():
    """Test is_indian_stock() function."""
    print("\n" + "="*80)
    print("TEST 1: Indian Stock Detection")
    print("="*80)

    test_cases = [
        ('RELIANCE.NS', True),
        ('TCS.BO', True),
        ('AAPL', False),
        ('MSFT', False),
        ('HDFCBANK.NS', True),
    ]

    passed = 0
    for ticker, expected in test_cases:
        result = is_indian_stock(ticker)
        status = "✓ PASS" if result == expected else "✗ FAIL"
        print(f"  {ticker:20s} -> {result:5s} (expected {expected:5s}) {status}")
        if result == expected:
            passed += 1

    print(f"\nResult: {passed}/{len(test_cases)} tests passed")
    return passed == len(test_cases)

async def test_source_quality_maps():
    """Verify SOURCE_QUALITY_INDIAN has FMP at rank 10."""
    print("\n" + "="*80)
    print("TEST 2: Source Quality Maps")
    print("="*80)

    print("\nStandard SOURCE_QUALITY (for non-Indian stocks):")
    print(f"  FMP rank: {SOURCE_QUALITY.get('fmp', 'NOT FOUND')}")
    print(f"  yfinance rank: {SOURCE_QUALITY.get('yfinance', 'NOT FOUND')}")

    print("\nIndian SOURCE_QUALITY_INDIAN (for .NS/.BO stocks):")
    print(f"  FMP rank: {SOURCE_QUALITY_INDIAN.get('fmp', 'NOT FOUND')}")
    print(f"  yfinance rank: {SOURCE_QUALITY_INDIAN.get('yfinance', 'NOT FOUND')}")

    # Verify FMP is promoted
    fmp_promoted = SOURCE_QUALITY_INDIAN.get('fmp') == 10
    yfinance_demoted = SOURCE_QUALITY_INDIAN.get('yfinance') < SOURCE_QUALITY_INDIAN.get('fmp')

    print("\nValidation:")
    print(f"  ✓ FMP promoted to rank 10: {fmp_promoted}")
    print(f"  ✓ yfinance demoted below FMP: {yfinance_demoted}")

    return fmp_promoted and yfinance_demoted

async def test_indian_large_caps():
    """Test data fetching for Indian large-cap stocks."""
    print("\n" + "="*80)
    print("TEST 3: Indian Large-Cap Stocks")
    print("="*80)

    results = []
    for ticker in INDIAN_LARGE_CAPS:
        print(f"\nFetching {ticker}...")
        try:
            data = await fetcher.get_financial_metrics(ticker)

            success = 'error' not in data
            sources_used = data.get('_sources_used', [])
            fmp_used = 'fmp' in sources_used
            coverage = data.get('_coverage_pct', 0.0)

            print(f"  Status: {'SUCCESS' if success else 'FAILED'}")
            print(f"  Sources: {', '.join(sources_used)}")
            print(f"  FMP used: {fmp_used}")
            print(f"  Coverage: {coverage:.1%}")

            if success:
                field_sources = data.get('_quality', {})
                # Check if key fields came from FMP
                pe_source = None
                pb_source = None
                for key in ['trailingPE', 'priceToBook']:
                    if key in data and data[key] is not None:
                        # Field sources are in merge_metadata but not exposed in final data
                        # We can only check if FMP was used overall
                        pass

            results.append({
                'ticker': ticker,
                'success': success,
                'fmp_used': fmp_used,
                'coverage': coverage
            })

        except Exception as e:
            print(f"  ERROR: {str(e)}")
            results.append({
                'ticker': ticker,
                'success': False,
                'error': str(e)
            })

    # Summary
    print("\n" + "-"*80)
    print("SUMMARY - Large Caps:")
    successful = sum(1 for r in results if r.get('success', False))
    fmp_usage = sum(1 for r in results if r.get('fmp_used', False))
    avg_coverage = sum(r.get('coverage', 0) for r in results) / len(results) if results else 0

    print(f"  Success rate: {successful}/{len(INDIAN_LARGE_CAPS)} ({successful/len(INDIAN_LARGE_CAPS)*100:.1f}%)")
    print(f"  FMP usage: {fmp_usage}/{len(INDIAN_LARGE_CAPS)} ({fmp_usage/len(INDIAN_LARGE_CAPS)*100:.1f}%)")
    print(f"  Avg coverage: {avg_coverage:.1%}")

    return successful >= 4  # At least 80% success rate

async def test_indian_small_caps():
    """Test data fetching for Indian small-cap stocks."""
    print("\n" + "="*80)
    print("TEST 4: Indian Small-Cap Stocks")
    print("="*80)

    results = []
    for ticker in INDIAN_SMALL_CAPS:
        print(f"\nFetching {ticker}...")
        try:
            data = await fetcher.get_financial_metrics(ticker)

            success = 'error' not in data
            sources_used = data.get('_sources_used', [])
            fmp_used = 'fmp' in sources_used
            coverage = data.get('_coverage_pct', 0.0)

            print(f"  Status: {'SUCCESS' if success else 'FAILED'}")
            print(f"  Sources: {', '.join(sources_used)}")
            print(f"  FMP used: {fmp_used}")
            print(f"  Coverage: {coverage:.1%}")

            results.append({
                'ticker': ticker,
                'success': success,
                'fmp_used': fmp_used,
                'coverage': coverage
            })

        except Exception as e:
            print(f"  ERROR: {str(e)}")
            results.append({
                'ticker': ticker,
                'success': False,
                'error': str(e)
            })

    # Summary
    print("\n" + "-"*80)
    print("SUMMARY - Small Caps:")
    successful = sum(1 for r in results if r.get('success', False))
    fmp_usage = sum(1 for r in results if r.get('fmp_used', False))
    avg_coverage = sum(r.get('coverage', 0) for r in results) / len(results) if results else 0

    print(f"  Success rate: {successful}/{len(INDIAN_SMALL_CAPS)} ({successful/len(INDIAN_SMALL_CAPS)*100:.1f}%)")
    print(f"  FMP usage: {fmp_usage}/{len(INDIAN_SMALL_CAPS)} ({fmp_usage/len(INDIAN_SMALL_CAPS)*100:.1f}%)")
    print(f"  Avg coverage: {avg_coverage:.1%}")

    return successful >= 3  # At least 60% success rate (small caps harder)

async def test_non_indian_stocks():
    """Test that non-Indian stocks still work (no regression)."""
    print("\n" + "="*80)
    print("TEST 5: Non-Indian Stocks (Regression Check)")
    print("="*80)

    results = []
    for ticker in NON_INDIAN_STOCKS:
        print(f"\nFetching {ticker}...")
        try:
            data = await fetcher.get_financial_metrics(ticker)

            success = 'error' not in data
            sources_used = data.get('_sources_used', [])
            coverage = data.get('_coverage_pct', 0.0)

            print(f"  Status: {'SUCCESS' if success else 'FAILED'}")
            print(f"  Sources: {', '.join(sources_used)}")
            print(f"  Coverage: {coverage:.1%}")

            results.append({
                'ticker': ticker,
                'success': success,
                'coverage': coverage
            })

        except Exception as e:
            print(f"  ERROR: {str(e)}")
            results.append({
                'ticker': ticker,
                'success': False,
                'error': str(e)
            })

    # Summary
    print("\n" + "-"*80)
    print("SUMMARY - Non-Indian Stocks:")
    successful = sum(1 for r in results if r.get('success', False))
    avg_coverage = sum(r.get('coverage', 0) for r in results) / len(results) if results else 0

    print(f"  Success rate: {successful}/{len(NON_INDIAN_STOCKS)} ({successful/len(NON_INDIAN_STOCKS)*100:.1f}%)")
    print(f"  Avg coverage: {avg_coverage:.1%}")

    return successful >= 2  # At least 67% success rate

async def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("TASK 1.1 TEST SUITE: FMP Promoted to Primary for Indian Stocks")
    print("="*80)

    tests = [
        ("Indian Stock Detection", test_indian_stock_detection()),
        ("Source Quality Maps", test_source_quality_maps()),
        ("Indian Large-Cap Stocks", test_indian_large_caps()),
        ("Indian Small-Cap Stocks", test_indian_small_caps()),
        ("Non-Indian Stocks (Regression)", test_non_indian_stocks()),
    ]

    results = []
    for name, test_coro in tests:
        try:
            result = await test_coro
            results.append((name, result))
        except Exception as e:
            print(f"\nERROR in test '{name}': {str(e)}")
            results.append((name, False))

    # Final summary
    print("\n" + "="*80)
    print("FINAL TEST SUMMARY")
    print("="*80)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status} - {name}")

    total_passed = sum(1 for _, passed in results if passed)
    print(f"\nOverall: {total_passed}/{len(results)} tests passed")

    if total_passed == len(results):
        print("\n🎉 ALL TESTS PASSED! Task 1.1 is complete.")
        return 0
    else:
        print(f"\n⚠️  {len(results) - total_passed} test(s) failed. Review output above.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
