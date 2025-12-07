# Implementation Task Breakdown - Indian Market Enhancements

## Overview
This document breaks down the IMPROVEMENT_RECOMMENDATIONS.md into discrete, actionable tasks with detailed implementation specifications.

---

## PHASE 1: QUICK WINS (Week 1-2)

### Task 1.1: Promote FMP to Primary for Indian Stocks
**Priority:** CRITICAL
**Estimated Time:** 2-3 days
**Dependencies:** None

**Objective:** Make FMP the primary data source for Indian stocks instead of yfinance

**Files to Modify:**
1. `src/data/fetcher.py`

**Detailed Steps:**

#### Step 1.1.1: Add Indian Stock Detection
```python
def is_indian_stock(ticker: str) -> bool:
    """Detect if ticker is from Indian exchanges."""
    return ticker.endswith('.NS') or ticker.endswith('.BO')
```

#### Step 1.1.2: Create Indian-Specific Source Priority
```python
SOURCE_QUALITY_INDIAN = {
    'fmp': 10,                      # PRIMARY for Indian stocks
    'eodhd': 9,                     # Backup
    'yfinance_statements': 8,
    'yfinance': 7,                  # Demoted (scraping unreliable)
    'yahooquery': 6,
    'tavily_extraction': 4,
}
```

#### Step 1.1.3: Modify Fetcher to Use Different Priority for Indian Stocks
```python
async def get_company_data(self, ticker: str):
    if is_indian_stock(ticker):
        # Use Indian-specific source priority
        source_quality = SOURCE_QUALITY_INDIAN
    else:
        # Use default priority
        source_quality = SOURCE_QUALITY

    # Apply priority in merging logic
    ...
```

**Testing:**
- Test with 10 Indian stocks (5 large-cap, 5 small-cap)
- Compare data quality: FMP vs yfinance
- Measure success rate improvement
- Verify no regression for non-Indian stocks

**Success Criteria:**
- [ ] FMP is fetched first for .NS/.BO tickers
- [ ] Data success rate >90% for Indian stocks
- [ ] No regression for other markets
- [ ] Response time <5 seconds

---

### Task 1.2: Add Moneycontrol Scraper
**Priority:** HIGH
**Estimated Time:** 2 days
**Dependencies:** None

**Objective:** Scrape analyst consensus and price targets from Moneycontrol.com

**New File:** `src/data/moneycontrol_fetcher.py`

**Detailed Implementation:**

#### Step 1.2.1: Create Moneycontrol Fetcher Class
```python
import aiohttp
from bs4 import BeautifulSoup
import structlog

logger = structlog.get_logger(__name__)

class MoneycontrolFetcher:
    """
    Scrapes analyst data from Moneycontrol.com for Indian stocks.

    Extracts:
    - Analyst recommendations (Buy/Hold/Sell count)
    - Price target (min/max/average)
    - Earnings estimates
    - Quarterly analysis
    """

    BASE_URL = "https://www.moneycontrol.com"

    async def get_analyst_consensus(self, ticker: str) -> dict:
        """
        Get aggregated analyst recommendations.

        Args:
            ticker: Indian stock ticker (e.g., 'RELIANCE.NS')

        Returns:
            {
                'buy_count': 15,
                'hold_count': 3,
                'sell_count': 1,
                'consensus': 'BUY',
                'price_target_min': 2800,
                'price_target_max': 3200,
                'price_target_avg': 3000,
                'analysts_count': 19,
                'last_updated': '2024-12-06'
            }
        """
        pass
```

#### Step 1.2.2: Implement URL Construction
Moneycontrol URLs follow pattern:
- `https://www.moneycontrol.com/india/stockpricequote/[sector]/[company]/[code]`
- Need to map ticker to Moneycontrol code

Solution: Create ticker mapping or search by company name

#### Step 1.2.3: Parse Analyst Page
Key elements to scrape:
- Analyst recommendations table
- Price target section
- Earnings estimates
- Latest reports links

#### Step 1.2.4: Handle Edge Cases
- Stock not found: Return None
- No analyst coverage: Return empty dict
- Network errors: Retry with backoff
- Rate limiting: Add delays between requests

**Testing:**
- Test with 20 stocks (large, mid, small cap)
- Verify data accuracy against manual check
- Test error handling (invalid ticker, network failure)
- Performance: <3 seconds per stock

**Success Criteria:**
- [ ] Successfully scrapes 95%+ of NSE stocks
- [ ] Data matches manual verification
- [ ] Proper error handling
- [ ] Integration with existing toolkit

---

### Task 1.3: Add Screener.in Fetcher
**Priority:** HIGH
**Estimated Time:** 2 days
**Dependencies:** None

**Objective:** Scrape financial data and concall transcripts from Screener.in

**New File:** `src/data/screener_in_fetcher.py`

**Detailed Implementation:**

#### Step 1.3.1: Create Screener.in Fetcher Class
```python
class ScreenerInFetcher:
    """
    Scrapes data from Screener.in for Indian stocks.

    Extracts:
    - 10-year financial history
    - Quarterly concall transcripts
    - Peer comparison
    - Management quality metrics
    """

    BASE_URL = "https://www.screener.in"

    async def get_financial_history(self, ticker: str) -> dict:
        """Get 10-year financial history."""
        pass

    async def get_latest_concall(self, ticker: str) -> dict:
        """
        Get latest conference call transcript.

        Returns:
            {
                'quarter': 'Q2FY25',
                'date': '2024-11-15',
                'transcript': 'Full text...',
                'participants': ['CEO', 'CFO', ...],
                'key_points': [...],
                'management_guidance': {...}
            }
        """
        pass
```

#### Step 1.3.2: URL Pattern
Screener.in URLs:
- `https://www.screener.in/company/{company_name}/consolidated/`
- Need to map ticker to company name
- Example: RELIANCE.NS -> "RELIANCE"

#### Step 1.3.3: Extract Conference Call Transcripts
- Navigate to "Quarterly Results" section
- Find latest concall link
- Extract full transcript text
- Parse into structured format

#### Step 1.3.4: Extract Financial Tables
- Revenue, profit, margins (10 years)
- Quarterly trends
- Peer comparison data

**Testing:**
- Test with 15 stocks
- Verify concall extraction works
- Check financial data accuracy
- Test with stocks that have no concalls

**Success Criteria:**
- [ ] Successfully extracts concalls for 80%+ of stocks
- [ ] Financial data matches company reports
- [ ] Handles missing data gracefully
- [ ] <5 seconds per fetch

---

### Task 1.4: Integrate Scrapers with Toolkit
**Priority:** HIGH
**Estimated Time:** 1 day
**Dependencies:** Tasks 1.2, 1.3

**Objective:** Add new data sources as tools available to agents

**Files to Modify:**
1. `src/toolkit.py` or create `src/indian_toolkit.py`

**Detailed Implementation:**

#### Step 1.4.1: Create New Tools
```python
@tool
async def get_indian_analyst_consensus(ticker: str) -> str:
    """
    Get analyst recommendations from Indian sources.

    Aggregates data from:
    - Moneycontrol analyst consensus
    - Screener.in data

    Returns formatted report for agents.
    """
    mc_fetcher = MoneycontrolFetcher()
    consensus = await mc_fetcher.get_analyst_consensus(ticker)

    if not consensus:
        return f"No analyst coverage found for {ticker}"

    return f"""Indian Analyst Consensus for {ticker}:

Recommendations:
- Buy: {consensus['buy_count']}
- Hold: {consensus['hold_count']}
- Sell: {consensus['sell_count']}
- Consensus: {consensus['consensus']}

Price Targets:
- Average: ₹{consensus['price_target_avg']:,.0f}
- Range: ₹{consensus['price_target_min']:,.0f} - ₹{consensus['price_target_max']:,.0f}

Total Analysts: {consensus['analysts_count']}
Last Updated: {consensus['last_updated']}
"""

@tool
async def get_latest_concall_summary(ticker: str) -> str:
    """
    Get summary of latest conference call.

    Uses LLM to summarize key points from Screener.in transcript.
    """
    screener = ScreenerInFetcher()
    concall = await screener.get_latest_concall(ticker)

    if not concall:
        return f"No conference call transcript found for {ticker}"

    # Use Gemini Flash to summarize
    summary = await summarize_concall(concall['transcript'])

    return f"""Latest Conference Call - {ticker}:

Quarter: {concall['quarter']}
Date: {concall['date']}

Key Highlights:
{summary['key_points']}

Management Guidance:
{summary['forward_guidance']}

Risk Factors Mentioned:
{summary['risks']}
"""
```

#### Step 1.4.2: Add to Agent Toolkit
Modify agent configurations to include new tools:
- Fundamentals Analyst: Gets analyst consensus
- News Analyst: Gets concall summaries
- Bull/Bear Researchers: Can cite analyst views

**Testing:**
- Test each tool independently
- Test in full agent workflow
- Verify LLM can use tools correctly
- Check output formatting

**Success Criteria:**
- [ ] Tools callable from agents
- [ ] Formatted output is readable
- [ ] Integrates with existing workflow
- [ ] No performance degradation

---

## PHASE 2: ENHANCED FMP INTEGRATION (Week 2-3)

### Task 2.1: Add Indian-Specific FMP Endpoints
**Priority:** HIGH
**Estimated Time:** 2 days
**Dependencies:** Task 1.1

**Objective:** Fetch Indian market-specific data from FMP

**File to Modify:** `src/data/fmp_fetcher.py`

**Detailed Implementation:**

#### Step 2.1.1: Add Ownership Data Endpoint
```python
async def get_ownership_data(self, ticker: str) -> dict:
    """
    Get ownership structure for Indian stocks.

    Critical for India:
    - Promoter holding %
    - FII/DII holdings
    - Pledged shares %

    Returns:
        {
            'promoter_holding': 47.5,  # %
            'fii_holding': 18.2,        # %
            'dii_holding': 15.8,        # %
            'public_holding': 18.5,     # %
            'pledged_shares': 0.0,      # %
            'last_updated': '2024-12-01'
        }
    """
    endpoint = f'/v4/institutional-ownership/symbol-ownership'
    params = {'symbol': ticker}
    data = await self._get(endpoint, params)

    # Parse and structure data
    return parse_ownership(data)
```

#### Step 2.1.2: Add Peer Comparison
```python
async def get_indian_peers(self, ticker: str) -> dict:
    """
    Get peer companies in Indian market.

    Returns stocks in same sector with comparison metrics.
    """
    endpoint = f'/v4/stock_peers'
    params = {'symbol': ticker}
    return await self._get(endpoint, params)
```

#### Step 2.1.3: Add Bulk Deal Detection
```python
async def get_bulk_deals(self, ticker: str, days: int = 30) -> list:
    """
    Get recent bulk/block deals.

    Large transactions often precede price moves in Indian market.
    """
    # FMP might not have this - may need NSE API
    pass
```

**Testing:**
- Test ownership data for 20 stocks
- Verify promoter holding accuracy
- Test peer comparison
- Handle missing data

**Success Criteria:**
- [ ] Ownership data for 90%+ of stocks
- [ ] Data accuracy verified against exchange filings
- [ ] Peer comparison works
- [ ] <2 seconds per fetch

---

### Task 2.2: Create Indian Market Metrics Analyzer
**Priority:** MEDIUM
**Estimated Time:** 1 day
**Dependencies:** Task 2.1

**Objective:** Analyze Indian market-specific red flags

**New File:** `src/data/indian_market_analyzer.py`

**Implementation:**

```python
class IndianMarketAnalyzer:
    """
    Analyzes Indian market-specific risk factors.

    Checks:
    - Promoter pledging (>50% = red flag)
    - Related party transactions
    - Corporate governance issues
    - Promoter holding changes
    """

    async def analyze_ownership_risk(self, ownership: dict) -> dict:
        """
        Assess risk from ownership structure.

        Red flags:
        - Promoter holding <25% (loss of control risk)
        - Promoter pledging >30% (financial stress)
        - Declining promoter holding (dilution)
        - High concentration in single FII

        Returns:
            {
                'risk_level': 'LOW' | 'MEDIUM' | 'HIGH',
                'concerns': [...],
                'positive_signals': [...],
                'recommendation': 'PASS' | 'MARGINAL' | 'FAIL'
            }
        """
        concerns = []
        positives = []

        # Check promoter holding
        if ownership['promoter_holding'] < 25:
            concerns.append("Low promoter holding (<25%) - control risk")
        elif ownership['promoter_holding'] > 70:
            positives.append("Strong promoter commitment (>70%)")

        # Check pledging
        if ownership['pledged_shares'] > 50:
            concerns.append("HIGH RISK: >50% promoter shares pledged")
        elif ownership['pledged_shares'] > 30:
            concerns.append("Moderate pledging (30-50%) - monitor")
        elif ownership['pledged_shares'] == 0:
            positives.append("Zero promoter pledging (healthy)")

        # Determine risk level
        if len(concerns) >= 3 or 'HIGH RISK' in str(concerns):
            risk_level = 'HIGH'
            recommendation = 'FAIL'
        elif len(concerns) >= 1:
            risk_level = 'MEDIUM'
            recommendation = 'MARGINAL'
        else:
            risk_level = 'LOW'
            recommendation = 'PASS'

        return {
            'risk_level': risk_level,
            'concerns': concerns,
            'positive_signals': positives,
            'recommendation': recommendation
        }
```

**Testing:**
- Test with stocks with high pledging
- Test with low promoter holdings
- Verify risk classification
- Test edge cases

**Success Criteria:**
- [ ] Correctly identifies high-risk ownership
- [ ] Provides actionable recommendations
- [ ] Integrates with fundamentals analyst
- [ ] Clear output format

---

## PHASE 3: NSE/BSE DIRECT DATA (Week 3)

### Task 3.1: Create NSE API Fetcher
**Priority:** MEDIUM
**Estimated Time:** 2 days
**Dependencies:** None

**Objective:** Access NSE public APIs for FII/DII and bulk deal data

**New File:** `src/data/nse_fetcher.py`

**Implementation:**

#### Step 3.1.1: NSE Headers and Session Management
```python
class NSEFetcher:
    """
    Direct NSE API access for Indian market data.

    NOTE: NSE requires proper headers to avoid blocking.
    """

    BASE_URL = "https://www.nseindia.com/api"

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 ...',
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
    }

    async def __aenter__(self):
        # Create session with cookies
        self.session = aiohttp.ClientSession(headers=self.HEADERS)
        # NSE requires visiting homepage first to set cookies
        await self.session.get("https://www.nseindia.com")
        return self

    async def __aexit__(self, *args):
        await self.session.close()
```

#### Step 3.1.2: FII/DII Data
```python
async def get_fii_dii_data(self, date: str = None) -> dict:
    """
    Get FII/DII buying/selling for date.

    Returns:
        {
            'date': '2024-12-06',
            'fii_net': 1250.5,  # Crores (positive = buying)
            'dii_net': -450.2,   # Crores (negative = selling)
            'fii_gross_buy': 5000,
            'fii_gross_sell': 3749.5,
            'dii_gross_buy': 3000,
            'dii_gross_sell': 3450.2
        }
    """
    endpoint = f"{self.BASE_URL}/fiidiiTrading"
    if date:
        endpoint += f"?date={date}"

    async with self.session.get(endpoint) as resp:
        data = await resp.json()
        return self._parse_fii_dii(data)
```

#### Step 3.1.3: Bulk/Block Deals
```python
async def get_bulk_deals(self, date: str = None) -> list:
    """
    Get bulk/block deals for date.

    Bulk deal = transaction >0.5% of equity
    Block deal = transaction >INR 10 crores

    Returns:
        [
            {
                'symbol': 'RELIANCE',
                'client_name': 'XYZ Investment',
                'deal_type': 'BUY',
                'quantity': 1000000,
                'price': 2500,
                'value_crores': 250
            },
            ...
        ]
    """
    endpoint = f"{self.BASE_URL}/block-deal"
    if date:
        endpoint += f"?date={date}"

    data = await self.session.get(endpoint)
    return self._parse_bulk_deals(await data.json())
```

**Testing:**
- Test FII/DII data fetch
- Test bulk deals for specific date
- Handle NSE anti-bot measures
- Test rate limiting

**Success Criteria:**
- [ ] Successfully fetches FII/DII data
- [ ] Bulk deals data accurate
- [ ] Handles NSE blocking gracefully
- [ ] Proper error handling

---

### Task 3.2: Add FII/DII Analysis Tool
**Priority:** MEDIUM
**Estimated Time:** 1 day
**Dependencies:** Task 3.1

**Objective:** Create tool to analyze FII/DII flow for stock

**File:** `src/toolkit.py` or `src/indian_toolkit.py`

**Implementation:**

```python
@tool
async def analyze_fii_dii_flow(ticker: str, days: int = 30) -> str:
    """
    Analyze FII/DII institutional flow for stock.

    Leading indicator for Indian stocks:
    - Consistent FII buying = bullish
    - Heavy DII selling = bearish
    - Divergence = interesting signal

    Args:
        ticker: Stock symbol
        days: Lookback period

    Returns formatted analysis
    """
    nse = NSEFetcher()

    # Get historical FII/DII data
    flow_data = await nse.get_historical_flow(ticker, days=days)

    # Calculate trends
    fii_trend = calculate_trend(flow_data['fii'])
    dii_trend = calculate_trend(flow_data['dii'])

    # Detect patterns
    if fii_trend > 0 and dii_trend > 0:
        signal = "STRONG BUY - Both FII and DII accumulating"
    elif fii_trend > 0 and dii_trend < 0:
        signal = "MIXED - FII buying, DII selling (monitor)"
    elif fii_trend < 0 and dii_trend < 0:
        signal = "BEARISH - Both FII and DII selling"
    else:
        signal = "NEUTRAL"

    return f"""FII/DII Flow Analysis - {ticker}:

Last {days} Days:
- FII Net: ₹{sum(flow_data['fii']):.1f} Cr ({fii_trend_desc})
- DII Net: ₹{sum(flow_data['dii']):.1f} Cr ({dii_trend_desc})

Signal: {signal}

Recent Activity:
{format_recent_activity(flow_data)}
"""
```

**Testing:**
- Test with stocks with heavy FII buying
- Test with stocks with FII selling
- Verify signal accuracy
- Test edge cases

**Success Criteria:**
- [ ] Accurate flow analysis
- [ ] Clear buy/sell signals
- [ ] Integrates with research agents
- [ ] <5 seconds execution

---

## PHASE 4: CONFERENCE CALL ANALYSIS (Week 4)

### Task 4.1: Create Concall Summarizer
**Priority:** MEDIUM
**Estimated Time:** 2 days
**Dependencies:** Task 1.3

**Objective:** Use LLM to extract key insights from concall transcripts

**New File:** `src/data/concall_analyzer.py`

**Implementation:**

```python
class ConcallAnalyzer:
    """
    Analyzes conference call transcripts using LLM.

    Extracts:
    - Forward guidance
    - Capacity expansion plans
    - Management sentiment
    - Q&A red flags
    - Growth catalysts
    """

    def __init__(self, llm):
        self.llm = llm
        self.prompt = self._create_prompt()

    async def analyze_transcript(self, transcript: str, ticker: str, quarter: str) -> dict:
        """
        Analyze concall transcript.

        Returns:
            {
                'summary': '...',
                'forward_guidance': {
                    'revenue_guidance': '15-20% growth',
                    'margin_guidance': 'Expect 100bps improvement',
                    'capex_plans': 'INR 500 cr for expansion'
                },
                'catalysts': [...],
                'risks': [...],
                'management_tone': 'CONFIDENT' | 'CAUTIOUS' | 'DEFENSIVE',
                'key_quotes': [...]
            }
        """
        # Use Gemini Flash 1.5 (1M token context, cheap)
        result = await self.llm.ainvoke(
            self.prompt.format(
                transcript=transcript,
                ticker=ticker,
                quarter=quarter
            )
        )

        return self._parse_llm_output(result)

    def _create_prompt(self) -> str:
        return """You are analyzing an Indian company's quarterly earnings conference call.

TRANSCRIPT:
{transcript}

EXTRACT THE FOLLOWING:

1. FORWARD GUIDANCE:
   - Revenue growth expectations
   - Margin guidance
   - Capex plans
   - Volume/production targets

2. GROWTH CATALYSTS:
   - New products/services launching
   - Market expansion plans
   - Capacity additions
   - Strategic initiatives

3. RISK FACTORS:
   - Challenges mentioned by management
   - Tough questions from analysts
   - Margin pressures
   - Competitive threats

4. MANAGEMENT TONE:
   - Overall sentiment (CONFIDENT/CAUTIOUS/DEFENSIVE)
   - Quality of answers (TRANSPARENT/EVASIVE)

5. KEY QUOTES:
   - Most important statements by management

OUTPUT AS JSON:
{json_structure}
"""
```

**Testing:**
- Test with 10 real concall transcripts
- Verify extraction accuracy
- Test with different company sizes
- Measure LLM cost per analysis

**Success Criteria:**
- [ ] Accurate extraction of guidance
- [ ] Identifies key catalysts
- [ ] Reasonable LLM costs (<$0.10 per concall)
- [ ] <30 seconds per transcript

---

### Task 4.2: Integrate Concall Analysis
**Priority:** MEDIUM
**Estimated Time:** 1 day
**Dependencies:** Task 4.1

**Objective:** Make concall insights available to agents

**File:** `src/toolkit.py`

**Implementation:**

```python
@tool
async def get_management_guidance(ticker: str) -> str:
    """
    Get latest management guidance from conference call.

    Provides forward-looking insights not in databases.
    """
    # Get transcript from Screener.in
    screener = ScreenerInFetcher()
    concall = await screener.get_latest_concall(ticker)

    if not concall:
        return f"No recent conference call found for {ticker}"

    # Analyze with LLM
    analyzer = ConcallAnalyzer(llm=gemini_flash)
    analysis = await analyzer.analyze_transcript(
        concall['transcript'],
        ticker,
        concall['quarter']
    )

    return f"""Management Guidance - {ticker} ({concall['quarter']}):

FORWARD GUIDANCE:
- Revenue: {analysis['forward_guidance']['revenue_guidance']}
- Margins: {analysis['forward_guidance']['margin_guidance']}
- Capex: {analysis['forward_guidance']['capex_plans']}

GROWTH CATALYSTS:
{format_list(analysis['catalysts'])}

RISKS MENTIONED:
{format_list(analysis['risks'])}

MANAGEMENT TONE: {analysis['management_tone']}

KEY QUOTE:
"{analysis['key_quotes'][0]}"

Date: {concall['date']}
"""
```

**Testing:**
- Test tool invocation
- Verify agent can use insights
- Check output quality
- Test error handling

**Success Criteria:**
- [ ] Tool callable by agents
- [ ] Insights are actionable
- [ ] Proper error handling
- [ ] Reasonable response time

---

## PHASE 5: TESTING & INTEGRATION (Week 5)

### Task 5.1: End-to-End Testing
**Priority:** CRITICAL
**Estimated Time:** 2 days
**Dependencies:** All previous tasks

**Objective:** Test complete flow with all enhancements

**Test Cases:**

#### Test Case 1: Large Cap with Full Coverage
- Stock: RELIANCE.NS
- Expected: All data sources work
- Verify: FMP, Moneycontrol, Screener, NSE all return data

#### Test Case 2: Mid Cap with Partial Coverage
- Stock: DIXON.NS
- Expected: Some sources work, graceful degradation
- Verify: System still provides analysis

#### Test Case 3: Small Cap with Minimal Coverage
- Stock: [Pick small cap]
- Expected: Limited data, system handles it
- Verify: Doesn't fail, uses available data

#### Test Case 4: Full Analysis Workflow
- Run complete analysis on 5 stocks
- Measure: Time, data quality, agent decisions
- Compare: Before vs after enhancements

**Performance Metrics:**
- Data fetch time: Should be <30 seconds
- Success rate: Should be >90%
- Agent decision quality: Manual review

**Success Criteria:**
- [ ] All test cases pass
- [ ] Performance meets targets
- [ ] No critical bugs
- [ ] Documentation updated

---

### Task 5.2: Documentation
**Priority:** HIGH
**Estimated Time:** 1 day
**Dependencies:** Task 5.1

**Objective:** Document all new features and usage

**Files to Create/Update:**

1. **INDIAN_DATA_SOURCES.md**
   - Overview of all Indian data sources
   - How to configure each source
   - Data available from each
   - Troubleshooting guide

2. **API_USAGE.md**
   - How to use new tools
   - Example queries
   - Expected outputs
   - Rate limits and costs

3. **Update README.md**
   - Add Indian market features
   - Update setup instructions
   - Add examples

**Success Criteria:**
- [ ] Complete documentation
- [ ] Examples work
- [ ] User can set up from docs alone
- [ ] Troubleshooting guide comprehensive

---

## Summary Timeline

| Week | Tasks | Deliverables |
|------|-------|--------------|
| **1** | 1.1, 1.2, 1.3 | FMP primary, Moneycontrol, Screener.in |
| **2** | 1.4, 2.1, 2.2 | Integration, Indian FMP endpoints |
| **3** | 3.1, 3.2 | NSE API, FII/DII analysis |
| **4** | 4.1, 4.2 | Concall analysis |
| **5** | 5.1, 5.2 | Testing, Documentation |

**Total Estimated Time:** 4-5 weeks

---

## Priority Order for Implementation

If time is limited, implement in this order:

1. **Task 1.1** - FMP Primary (biggest immediate impact)
2. **Task 1.2** - Moneycontrol (analyst consensus)
3. **Task 1.4** - Integration (make #1 and #2 usable)
4. **Task 1.3** - Screener.in (concalls are valuable)
5. **Task 2.1** - Indian FMP endpoints (ownership data)
6. **Task 3.1** - NSE FII/DII (leading indicator)
7. **Task 4.1** - Concall analysis (forward guidance)
8. **Task 5.1** - Testing
9. **Task 5.2** - Documentation

This ensures you get value quickly while building toward the complete solution.
