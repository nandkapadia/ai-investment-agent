# Indian Stock Market Support - Changes Summary

## Overview
This document summarizes the changes made to adapt the AI Investment Agent for the Indian stock market. The system has been calibrated to account for the characteristics of Indian equities, which differ significantly from US and other developed markets.

## Key Changes Made

### 1. Currency Conversion
**File:** `src/liquidity_calculation_tool.py`

**Status:** ✅ Already Configured
- INR exchange rate is already correctly set at 0.012 (approximately 1 USD = 84 INR)
- Both NSE (.NS) and BSE (.BO) exchanges are properly mapped to INR
- Currency conversion logic is working correctly

### 2. Liquidity Thresholds
**Files:** `src/liquidity_calculation_tool.py`, `src/prompts.py`

**Changes:**
- **Base threshold reduced from $500k to $150k** for Indian stocks (NSE/BSE)
  - Location: `liquidity_calculation_tool.py:141-146`
  - Rationale: Indian small/mid-cap stocks have lower trading volumes than US counterparts

- **Marginal liquidity threshold reduced from $100k-$250k to $75k-$150k**
  - Location: `prompts.py:1678-1681`
  - Stocks in this range: Max 3% position size

- **Hard fail threshold reduced from $100k to $75k**
  - Location: `prompts.py:1665`, `1679`, `1683`
  - Below this level: Mandatory SELL

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
   - Many viable companies trade <$200k daily

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

1. `src/liquidity_calculation_tool.py` - Lines 137-146
2. `src/prompts.py` - Multiple sections:
   - Financial Health Score (lines 805-823)
   - Bull Researcher criteria (lines 1077-1091, 1105-1111, 1127, 1148)
   - Hard Fail Criteria (lines 1659-1668)
   - Liquidity thresholds (lines 1678-1683)
   - Risk factors (line 1696)

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
- Various stocks with $100k-$200k daily turnover
- P/E ratios in 20-28 range
- D/E ratios 1.0-1.5

## Future Considerations

If expanding to other emerging markets, similar adjustments may be needed for:
- **Southeast Asia** (Thailand, Indonesia, Philippines): Similar liquidity/valuation profiles
- **Latin America** (Brazil, Mexico): Higher leverage and volatility
- **Other Asian markets** (Taiwan, Korea): Different characteristics, may need separate calibration

## Conclusion

The system is now calibrated for Indian market conditions while maintaining the core investment philosophy of finding quality, undiscovered value-to-growth opportunities. The adjusted thresholds reflect the realities of Indian corporate finance and market structure without compromising on investment quality standards.
