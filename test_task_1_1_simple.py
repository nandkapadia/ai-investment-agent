#!/usr/bin/env python3
"""
Simple verification test for Task 1.1 changes
Tests the code modifications without running full integration tests
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

print("="*80)
print("Task 1.1 Simple Verification Test")
print("="*80)

# Test 1: Check imports
print("\n[Test 1] Checking imports...")
try:
    from src.data.fetcher import (
        is_indian_stock,
        SOURCE_QUALITY,
        SOURCE_QUALITY_INDIAN
    )
    print("  ✓ All required exports available")
except ImportError as e:
    print(f"  ✗ FAIL: Import error - {e}")
    sys.exit(1)

# Test 2: Check is_indian_stock function
print("\n[Test 2] Testing is_indian_stock() function...")
test_cases = [
    ('RELIANCE.NS', True, 'NSE ticker'),
    ('TCS.BO', True, 'BSE ticker'),
    ('AAPL', False, 'US ticker'),
    ('MSFT', False, 'US ticker'),
    ('TSLA.US', False, 'Explicit US suffix'),
]

all_passed = True
for ticker, expected, description in test_cases:
    result = is_indian_stock(ticker)
    passed = result == expected
    status = "✓" if passed else "✗"
    print(f"  {status} {ticker:15s} -> {str(result):5s} (expected {str(expected):5s}) - {description}")
    if not passed:
        all_passed = False

if not all_passed:
    print("  ✗ FAIL: Some test cases failed")
    sys.exit(1)

# Test 3: Check SOURCE_QUALITY_INDIAN structure
print("\n[Test 3] Verifying SOURCE_QUALITY_INDIAN...")
required_keys = ['fmp', 'fmp_info', 'yfinance', 'yfinance_info', 'eodhd',
                 'yfinance_statements', 'calculated_from_statements',
                 'yahooquery', 'tavily_extraction']

for key in required_keys:
    if key not in SOURCE_QUALITY_INDIAN:
        print(f"  ✗ FAIL: Missing key '{key}' in SOURCE_QUALITY_INDIAN")
        sys.exit(1)

print("  ✓ All required keys present")

# Test 4: Verify FMP is promoted to rank 10
print("\n[Test 4] Verifying FMP promotion...")
fmp_rank = SOURCE_QUALITY_INDIAN.get('fmp')
fmp_info_rank = SOURCE_QUALITY_INDIAN.get('fmp_info')

if fmp_rank != 10:
    print(f"  ✗ FAIL: FMP rank is {fmp_rank}, expected 10")
    sys.exit(1)
print(f"  ✓ FMP rank is 10 (promoted)")

if fmp_info_rank != 10:
    print(f"  ✗ FAIL: FMP info rank is {fmp_info_rank}, expected 10")
    sys.exit(1)
print(f"  ✓ FMP info rank is 10 (promoted)")

# Test 5: Verify yfinance is demoted
print("\n[Test 5] Verifying yfinance demotion...")
yf_rank = SOURCE_QUALITY_INDIAN.get('yfinance')
if yf_rank >= fmp_rank:
    print(f"  ✗ FAIL: yfinance rank ({yf_rank}) should be less than FMP ({fmp_rank})")
    sys.exit(1)
print(f"  ✓ yfinance rank ({yf_rank}) < FMP rank ({fmp_rank})")

# Test 6: Compare with standard SOURCE_QUALITY
print("\n[Test 6] Comparing with standard SOURCE_QUALITY...")
standard_fmp = SOURCE_QUALITY.get('fmp')
indian_fmp = SOURCE_QUALITY_INDIAN.get('fmp')

print(f"  Standard SOURCE_QUALITY FMP rank: {standard_fmp}")
print(f"  Indian SOURCE_QUALITY_INDIAN FMP rank: {indian_fmp}")

if indian_fmp <= standard_fmp:
    print(f"  ✗ FAIL: Indian FMP rank ({indian_fmp}) should be higher than standard ({standard_fmp})")
    sys.exit(1)
print(f"  ✓ Indian FMP rank is promoted from {standard_fmp} to {indian_fmp}")

# Test 7: Check method signature updates
print("\n[Test 7] Verifying method signatures...")
try:
    from src.data.fetcher import SmartMarketDataFetcher
    import inspect

    # Check _smart_merge_with_quality has source_quality parameter
    merge_sig = inspect.signature(SmartMarketDataFetcher._smart_merge_with_quality)
    if 'source_quality' not in merge_sig.parameters:
        print("  ✗ FAIL: _smart_merge_with_quality missing 'source_quality' parameter")
        sys.exit(1)
    print("  ✓ _smart_merge_with_quality has 'source_quality' parameter")

    # Check _merge_gap_fill_data has source_quality parameter
    gap_fill_sig = inspect.signature(SmartMarketDataFetcher._merge_gap_fill_data)
    if 'source_quality' not in gap_fill_sig.parameters:
        print("  ✗ FAIL: _merge_gap_fill_data missing 'source_quality' parameter")
        sys.exit(1)
    print("  ✓ _merge_gap_fill_data has 'source_quality' parameter")

except Exception as e:
    print(f"  ✗ FAIL: Error checking method signatures - {e}")
    sys.exit(1)

# Test 8: Display full quality maps
print("\n[Test 8] Full Quality Map Comparison:")
print("\n  Standard SOURCE_QUALITY:")
for source, rank in sorted(SOURCE_QUALITY.items(), key=lambda x: -x[1]):
    print(f"    {source:30s} -> {rank}")

print("\n  Indian SOURCE_QUALITY_INDIAN:")
for source, rank in sorted(SOURCE_QUALITY_INDIAN.items(), key=lambda x: -x[1]):
    marker = " ⭐" if source in ['fmp', 'fmp_info'] else ""
    print(f"    {source:30s} -> {rank}{marker}")

# All tests passed
print("\n" + "="*80)
print("✅ ALL TESTS PASSED!")
print("="*80)
print("\nSummary of Changes:")
print("  1. ✓ is_indian_stock() function added")
print("  2. ✓ SOURCE_QUALITY_INDIAN created with FMP at rank 10")
print("  3. ✓ yfinance demoted in Indian quality map")
print("  4. ✓ Method signatures updated to accept source_quality parameter")
print("\nTask 1.1 implementation is COMPLETE and ready for integration testing.")
print("="*80)

sys.exit(0)
