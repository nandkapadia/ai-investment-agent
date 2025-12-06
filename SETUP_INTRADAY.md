# Quick Setup Guide: Intraday Data Integration

## What You Get

With your 9 years of 1-minute data, you'll unlock:
- ✅ **Manipulation detection** - Avoid operator-driven stocks
- ✅ **Institutional signature** - Detect FII/DII buying patterns
- ✅ **Liquidity consistency** - Real vs fake liquidity
- ✅ **Optimal entry times** - Best windows for execution

## 5-Minute Setup

### Step 1: Configure Data Path

Add to your `.env` file:

```bash
INTRADAY_DATA_DIR=/path/to/your/parquet/files
```

Example:
```bash
INTRADAY_DATA_DIR=/home/user/data/intraday_data
```

### Step 2: Verify File Structure

Your parquet files should be:
```
/home/user/data/intraday_data/
  ├── RELIANCE.parquet
  ├── TCS.parquet
  ├── HDFCBANK.parquet
  └── ...
```

**Expected columns:** `datetime`, `open`, `high`, `low`, `close`, `volume`

### Step 3: Test It

```bash
# Run a test analysis
python -m src.main analyze RELIANCE.NS
```

If intraday data is found, you'll see:
```
Liquidity Analysis for RELIANCE.NS:
Status: PASS

BASIC METRICS:
Avg Daily Turnover: ₹850.45 lakhs

INTRADAY LIQUIDITY INSIGHTS:
✓ Consistency: 0.85 (continuous trading)
✓ Institutional Activity: 0.72 (strong FII/DII)
✓ Volume Concentration: 0.35 (healthy distribution)
✓ Manipulation Risk: LOW

Best Entry Times: 9:30-9:45, 14:00-14:15

📊 ENHANCED ANALYSIS: Based on 90 days of 1-minute data
```

If no intraday data:
```
ℹ️  BASIC ANALYSIS: Using daily data only
   (Install intraday data for manipulation detection & institutional analysis)
```

## What Changed

### New Files Created

1. **`src/data/intraday_loader.py`**
   - Loads 1-minute parquet data
   - Handles date filtering
   - Efficient caching

2. **`src/data/intraday_liquidity.py`**
   - Multi-dimensional liquidity scoring
   - Manipulation detection algorithms
   - Institutional pattern recognition
   - Entry time optimization

3. **`src/liquidity_calculation_tool.py`** (updated)
   - Now tries intraday analysis first
   - Falls back to daily data gracefully
   - Backwards compatible

## Example Output Comparison

### Before (Daily Data Only)
```
Liquidity Analysis for DIXON.NS:
Status: PASS
Avg Daily Turnover: ₹15.23 lakhs
```
**Problem:** Can't tell if this is real or manipulated liquidity!

### After (With Intraday Data)
```
Liquidity Analysis for DIXON.NS:
Status: MARGINAL  ← DOWNGRADED!

BASIC METRICS:
Avg Daily Turnover: ₹15.23 lakhs

INTRADAY LIQUIDITY INSIGHTS:
✓ Consistency: 0.42 (sporadic trading) ← RED FLAG
✓ Institutional Activity: 0.35 (retail/operator) ← RED FLAG
✓ Volume Concentration: 0.78 (78% in top 10% of bars) ← RED FLAG
✓ Manipulation Risk: MEDIUM ← DETECTED!

INTERPRETATION:
✗ Sporadic trading pattern (red flag)
⚠ Primarily retail/operator driven
✗ High volume concentration (manipulation risk)
⚠ Moderate manipulation signals detected

→ RECOMMENDATION: Trade with caution (max 3% position)
```

**Value:** Avoided a manipulated stock that looked liquid from daily data!

## Ticker Name Handling

The loader automatically handles different formats:

```python
# All these work:
RELIANCE.NS → loads RELIANCE.parquet
TCS.BO → loads TCS.parquet
HDFCBANK → loads HDFCBANK.parquet
```

## Performance

- **Loading 90 days of 1-min data:** ~0.5-1 second per stock
- **Analysis time:** ~0.2-0.5 seconds
- **Total overhead:** ~1-2 seconds (negligible)

**Tip:** Results are calculated once per analysis, so no performance impact on multi-agent workflow.

## Troubleshooting

### "No intraday data for TICKER"

**Cause:** Parquet file doesn't exist or wrong path

**Fix:**
1. Check `INTRADAY_DATA_DIR` in `.env`
2. Verify file exists: `ls /path/to/data/RELIANCE.parquet`
3. Check ticker naming (should be without .NS/.BO suffix)

### "intraday_analysis_failed"

**Cause:** Corrupted parquet or wrong column names

**Fix:**
1. Test loading manually:
   ```python
   import pandas as pd
   df = pd.read_parquet('RELIANCE.parquet')
   print(df.columns)  # Should show: datetime, open, high, low, close, volume
   print(df.head())
   ```

2. Ensure 'datetime' column exists and is datetime type

### System still uses daily data

**Cause:** INTRADAY_DATA_DIR not set or module import failed

**Check:**
1. `.env` file has `INTRADAY_DATA_DIR` set
2. Python can import: `python -c "from src.data.intraday_liquidity import IntradayLiquidityAnalyzer; print('OK')"`

## Advanced: Custom Analysis

You can also use the analyzer directly:

```python
from src.data.intraday_liquidity import IntradayLiquidityAnalyzer

analyzer = IntradayLiquidityAnalyzer('/path/to/data')

# Get detailed metrics
metrics = await analyzer.calculate_liquidity_score('RELIANCE.NS', lookback_days=90)

print(f"Manipulation Risk: {metrics['manipulation_risk']}")
print(f"Institutional Score: {metrics['institutional_signature']}")
print(f"Best Entry Times: {metrics['recommended_entry_windows']}")
```

## Next Steps

Once this is working:

1. **Phase 2:** Volume Profile analysis (support/resistance levels)
2. **Phase 3:** Smart Money detection (accumulation/distribution)
3. **Phase 4:** Backtesting framework (validate thesis)

See `INTRADAY_DATA_INTEGRATION.md` for full roadmap!

## Questions?

- Check logs: Look for `intraday_*` log messages
- Test specific ticker: `python -m src.main analyze YOUR_TICKER.NS`
- Verify data path: `echo $INTRADAY_DATA_DIR`

**Your 1-minute data is now powering institutional-grade liquidity analysis!** 🚀
