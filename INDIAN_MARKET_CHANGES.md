# Indian Stock Market Support - Changes Summary

## Overview
This document summarizes the changes made to adapt the AI Investment Agent for the Indian stock market. The system has been completely re-calibrated to work natively in INR (Indian Rupees) without USD conversion, eliminating FX volatility risk and making the system more intuitive for Indian market users.

## Key Changes Made

### 1. Currency - Native INR Implementation (No USD Conversion)
**File:** `src/liquidity_calculation_tool.py`

**Major Change:** ✅ Eliminated USD Conversion
- System now works **directly in INR** for all Indian stocks (NSE/BSE)
- **No more FX conversion** - eliminates INR/USD volatility risk
- Prices from yfinance are already in INR for Indian stocks - we use them directly
- Much simpler, more accurate, and more intuitive for Indian market users

**Why this matters:**
- INR/USD can fluctuate 5-10% annually - this was adding unnecessary noise
- Thresholds in lakhs/crores are natural for Indian investors
- Simpler code = fewer errors

### 2. Liquidity Thresholds (Native INR)
**Files:** `src/liquidity_calculation_tool.py`, `src/prompts.py`

**Changes - Now in INR:**
- **Base threshold: ₹12 lakhs daily turnover** (PASS)
  - Location: `liquidity_calculation_tool.py:119`
  - Previous: $150k (which varied with FX rates)
  - Current: Fixed ₹12,00,000 daily

- **Marginal liquidity: ₹6-12 lakhs daily** (max 3% position)
  - Location: `liquidity_calculation_tool.py:120`, `prompts.py:1680`
  - Previous: $75k-$150k (varied with FX)
  - Current: Fixed ₹6-12 lakhs range

- **Hard fail: <₹6 lakhs daily** (Mandatory SELL)
  - Location: `prompts.py:1665`, `1679`, `1683`
  - Previous: <$75k (varied with FX)
  - Current: Fixed <₹6,00,000 threshold

**Output Format:**
- Displays turnover in both lakhs and full INR amount
- Example: "₹8.45 lakhs (₹8,45,000)"
- Clear PASS/MARGINAL/FAIL status with explanation

### 3. Valuation Multiples
**File:** `src/prompts.py`

**Changes:**

#### P/E Ratio Thresholds
- **Standard threshold increased from ≤18 to ≤22**
  - Locations: Lines 820, 1081, 1088, 1105, 1127
  - Rationale: Indian stocks typically trade at higher P/E ratios (market average 20-25 vs US 15-18)

- **Marginal P/E range changed from 18-25 to 22-28**
  - Location: Lines 1081, 1106, 1696
  - With PEG ≤1.2-1.3, this range is acceptable

- **Hard fail threshold increased from P/E > 25 to P/E > 30**
  - Locations: Lines 1111, 1148, 1668
  - OR **(P/E > 22 AND PEG > 1.3)** for Indian market

#### P/B Ratio
- **Increased from ≤1.4 to ≤1.8**
  - Location: Line 822
  - Rationale: Indian companies often have higher book value multiples

#### P/S Ratio
- **Increased from ≤1.0 to ≤1.2**
  - Location: Line 822
  - Allows for slightly higher revenue multiples common in Indian market

#### EV/EBITDA
- **Increased from <10 to <12**
  - Location: Line 821
  - Reflects higher valuation multiples in Indian market

### 4. Leverage Thresholds
**File:** `src/prompts.py`

**Changes:**

#### Debt-to-Equity (D/E) Ratio
- **Standard threshold increased from <0.8 to <1.2**
  - Location: Line 806
  - Rationale: Indian companies typically operate with higher leverage than US counterparts
  - Corporate India average D/E is around 1.0-1.5

- **Marginal range added: D/E 1.2-1.5** (scores 0.5 points if improving)
  - Location: Line 806

- **Sector exceptions increased from <2.0 to <2.5** for:
  - Utilities, REITs, Shipping, Banks
  - Location: Line 807

#### Net Debt/EBITDA
- **Increased from <2 to <3**
  - Location: Line 808
  - Reflects higher leverage norms in Indian corporate sector

### 5. Turnaround Exception Criteria
**File:** `src/prompts.py`

**Changes:**
- **P/E threshold for turnaround exception increased from <12 to <15**
  - Location: Line 1664
  - Allows more flexibility for identifying turnaround opportunities in Indian market

- **Financial Health exception P/B threshold adjusted from <0.6 to <0.7**
  - Location: Line 1661
  - Slightly relaxed for Indian market conditions

### 6. Market-Specific Notes Added
**File:** `src/prompts.py`

Added clarifying notes throughout:
- "Calibrated for Indian market" labels on key thresholds
- "Indian market threshold" annotations
- "Indian companies typically have higher leverage than US counterparts"
- "Indian stocks typically trade at higher multiples than US stocks"
- Reference to local news sources (Economic Times, Moneycontrol)

## Rationale: Why Indian Markets Are Different

### Market Characteristics
1. **Higher Valuation Multiples**: Indian stocks trade at premium multiples due to:
   - Higher expected growth rates
   - Demographic dividend and expanding middle class
   - Limited large-cap investment options
   - Strong domestic institutional buying

2. **Higher Leverage**: Indian companies operate with more debt because:
   - Banking system is well-developed
   - Cost of equity is higher
   - Tax advantages of debt financing
   - Historical acceptance of higher D/E ratios

3. **Lower Liquidity**: Especially for small/mid-caps:
   - Smaller free float (promoter holdings often 50-70%)
   - Less institutional participation in small caps
   - Lower retail trading volumes compared to US
   - Many viable companies trade ₹10-15 lakhs daily (vs $500k+ for US small caps)

4. **Different Analyst Coverage**:
   - Heavy focus on large caps by international analysts
   - Rich mid/small cap opportunities with minimal coverage
   - Local language research often more valuable

## What Remains Unchanged

These parameters were kept the same as they represent universal quality metrics:

- **ROE threshold**: >15% (Indian companies often achieve this or higher)
- **ROA threshold**: >7%
- **Operating Margin**: >12% (sector-dependent, reasonable for India)
- **Current Ratio**: >1.2
- **FCF Yield**: >4%
- **Growth rates**: Revenue >10%, EPS >12% (if anything, Indian companies often exceed these)
- **US Revenue exposure thresholds**: <25% PASS, >35% FAIL (applies to export-focused companies)
- **Analyst coverage**: <15 analysts (appropriate for "undiscovered" stocks)

## Files Modified

1. **`src/liquidity_calculation_tool.py`** - Complete rewrite for INR-native operation
   - Lines 81-151: Removed USD conversion, works directly in INR
   - Lines 115-120: INR thresholds (₹12L, ₹6L)
   - Lines 138-144: Output format in lakhs and full INR

2. **`src/prompts.py`** - Updated all thresholds to INR:
   - Line 1082: Bull researcher liquidity criteria (₹12L/₹6L)
   - Lines 1665, 1679, 1683: Hard fail and marginal thresholds in INR
   - Financial Health Score (lines 805-823): Valuation and leverage thresholds
   - Risk factors (line 1696): Marginal valuation criteria

## Testing Recommendations

To validate these changes, test with representative Indian stocks:

### Large Caps (should easily pass)
- Reliance Industries (RELIANCE.NS)
- TCS (TCS.NS)
- HDFC Bank (HDFCBANK.NS)
- Infosys (INFY.NS)

### Mid Caps (should pass with adjusted thresholds)
- Dixon Technologies
- Polycab India
- Avenue Supermarts (DMart)

### Small Caps (test liquidity and valuation thresholds)
- Various stocks with ₹8-15 lakhs daily turnover
- P/E ratios in 20-28 range
- D/E ratios 1.0-1.5

## Future Considerations

If expanding to other emerging markets, similar adjustments may be needed for:
- **Southeast Asia** (Thailand, Indonesia, Philippines): Similar liquidity/valuation profiles
- **Latin America** (Brazil, Mexico): Higher leverage and volatility
- **Other Asian markets** (Taiwan, Korea): Different characteristics, may need separate calibration

## Summary of Benefits

### 1. **No FX Volatility Risk**
- INR/USD rate can swing ±5-10% annually
- Old system: $150k threshold = ₹12.6L @ 84 or ₹13.8L @ 92 (10% difference!)
- New system: Fixed ₹12L threshold regardless of FX movements

### 2. **More Intuitive for Indian Users**
- Think in lakhs/crores naturally
- No mental conversion needed
- Aligns with how brokers and financial media report data

### 3. **Simpler, More Reliable Code**
- Removed entire FX conversion layer
- Fewer moving parts = fewer errors
- Direct calculation from market data

### 4. **Market-Appropriate Thresholds**
- Valuation multiples calibrated for higher Indian market P/E, P/B
- Leverage thresholds reflect Indian corporate norms (higher D/E acceptable)
- Liquidity thresholds match Indian small/mid-cap trading reality

## Conclusion

The system is now **fully optimized for Indian markets only**, working natively in INR without any USD conversion. This eliminates FX volatility, simplifies the codebase, and makes the system more intuitive for Indian market users. All thresholds have been calibrated to reflect Indian market characteristics while maintaining the core investment philosophy of finding quality, undiscovered value-to-growth opportunities.
