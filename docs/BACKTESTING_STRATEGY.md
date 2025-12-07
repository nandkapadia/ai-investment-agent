# Backtesting Strategy for AI Investment Agent
## Comprehensive Analysis & Implementation Plan

**Status**: Strategy Document
**Date**: 2025-12-07
**Purpose**: Define rigorous backtesting methodology before production deployment

---

## Executive Summary

This document analyzes backtesting strategies for an LLM-based investment agent operating on Indian stocks. We explore 3 distinct approaches, evaluate their strengths/weaknesses, and synthesize an optimal strategy combining the best elements.

**Key Challenge**: LLM-based agents are non-deterministic and computationally expensive, making traditional backtesting approaches insufficient.

---

## PART 1: BACKTESTING APPROACHES

### Approach 1: Event-Driven Historical Replay (Traditional)

**Core Concept**: Replay historical market events chronologically, having agents make decisions with information available only at that point in time.

#### Implementation Design

```python
class HistoricalReplayBacktester:
    """
    Traditional event-driven backtesting with point-in-time data.
    """

    def __init__(self, start_date, end_date, universe, initial_capital):
        self.start_date = start_date
        self.end_date = end_date
        self.universe = universe  # List of tickers
        self.capital = initial_capital
        self.positions = {}
        self.trade_log = []

        # Historical data cache
        self.price_data = {}
        self.fundamental_data = {}
        self.news_archive = {}

    async def run_backtest(self):
        """Execute backtest day by day."""
        current_date = self.start_date

        while current_date <= self.end_date:
            # Get universe of stocks for this date
            active_universe = self._get_active_universe(current_date)

            # For each stock, gather point-in-time data
            for ticker in active_universe:
                pit_data = self._get_point_in_time_data(ticker, current_date)

                # Run agent analysis
                agent_decision = await self.agent.analyze(
                    ticker=ticker,
                    data=pit_data,
                    date=current_date
                )

                # Execute trades based on decision
                if agent_decision.action == 'BUY':
                    self._execute_trade(ticker, 'BUY', current_date)
                elif agent_decision.action == 'SELL':
                    self._execute_trade(ticker, 'SELL', current_date)

            # Move to next trading day
            current_date = self._next_trading_day(current_date)

        return self._calculate_performance()

    def _get_point_in_time_data(self, ticker, as_of_date):
        """
        Critical: Only return data that would have been available
        on as_of_date to avoid look-ahead bias.
        """
        return {
            'price': self.price_data[ticker].loc[:as_of_date],
            'fundamentals': self._get_latest_fundamentals(ticker, as_of_date),
            'news': self.news_archive[ticker].loc[:as_of_date],
            'analyst_ratings': self._get_analyst_data(ticker, as_of_date),
        }
```

#### Data Requirements

1. **Price Data**: Daily OHLCV for all stocks (9 years available ✓)
2. **Fundamental Data**: Quarterly financials with announcement dates
3. **News Archive**: Historical news with timestamps
4. **Analyst Data**: Historical recommendations with dates
5. **Corporate Actions**: Splits, bonuses, dividends with ex-dates

#### Strengths

✅ **Realistic simulation**: Mirrors actual trading conditions
✅ **No look-ahead bias**: Strict point-in-time data discipline
✅ **Transaction costs**: Can model slippage, commissions accurately
✅ **Position tracking**: Portfolio management like production
✅ **Risk metrics**: Calculate Sharpe, max drawdown, etc.

#### Weaknesses

❌ **Extremely slow**: LLM inference for every stock × every day = weeks
❌ **Non-deterministic**: Different runs produce different results
❌ **Data availability**: Historical fundamentals/news hard to obtain
❌ **Survivorship bias**: Need full universe including delisted stocks
❌ **Computational cost**: $1000+ in API costs for comprehensive backtest

#### Cost Analysis

- Universe: 500 Indian stocks
- Period: 3 years (750 trading days)
- Agent calls: 500 stocks × 750 days = 375,000 analyses
- LLM cost: ~$0.10 per analysis (multi-agent) = **$37,500**
- Runtime: ~5 seconds per analysis = **52 days continuous**

**Verdict**: Cost-prohibitive for frequent iteration

---

### Approach 2: Factor-Based Proxy Testing (Hybrid)

**Core Concept**: Extract the agent's decision logic into quantifiable factors, then backtest those factors traditionally. Validate factor extraction with LLM spot-checks.

#### Implementation Design

```python
class FactorProxyBacktester:
    """
    Extract agent reasoning into tradable factors, test factors
    at scale, validate with LLM sampling.
    """

    def __init__(self):
        self.factors = {}
        self.factor_weights = {}

    def extract_factors_from_agent(self, sample_size=100):
        """
        Run agent on sample of stocks, extract decision factors.

        Example: Agent consistently flags stocks with:
        - ROIC > 15% and expanding
        - D/E < 1.0 and declining
        - Revenue CAGR > 20%
        - Promoter holding > 50%
        - Low pledging
        """
        factor_analysis = []

        for ticker in self.sample_stocks[:sample_size]:
            # Get agent decision
            decision = await self.agent.analyze(ticker)

            # Extract numerical factors from reasoning
            factors = self._parse_agent_reasoning(decision.explanation)

            factor_analysis.append({
                'ticker': ticker,
                'decision': decision.action,
                'factors': factors,
                'confidence': decision.confidence
            })

        # Use ML to identify which factors matter most
        self.factors = self._identify_key_factors(factor_analysis)

        return self.factors

    def backtest_factors(self, start_date, end_date):
        """
        Traditional factor backtest - very fast.
        """
        # Calculate factor scores for all stocks daily
        factor_scores = self._calculate_factor_scores_vectorized()

        # Long stocks with high scores, short stocks with low scores
        returns = self._simulate_factor_portfolio(factor_scores)

        return self._calculate_performance(returns)

    def validate_with_llm_sampling(self, validation_size=50):
        """
        Periodically validate factor-based decisions match agent.
        """
        disagreements = []

        for ticker, date in self.random_samples[:validation_size]:
            # Factor-based decision
            factor_decision = self._factor_based_decision(ticker, date)

            # Agent decision
            agent_decision = await self.agent.analyze(ticker, date)

            if factor_decision != agent_decision.action:
                disagreements.append({
                    'ticker': ticker,
                    'date': date,
                    'factor_said': factor_decision,
                    'agent_said': agent_decision.action,
                    'agent_reasoning': agent_decision.explanation
                })

        # Update factors if disagreement > threshold
        if len(disagreements) / validation_size > 0.15:
            self._refine_factors(disagreements)

        return disagreements
```

#### Key Factors to Extract

Based on agent prompts and Indian market characteristics:

**Quality Factors:**
1. ROIC trend (expanding vs contracting)
2. ROE consistency (>15% for 3+ years)
3. FCF yield improving
4. Promoter holding >50%, stable/increasing

**Valuation Factors:**
5. P/E relative to sector median
6. PEG ratio <1.2
7. P/B vs ROE relationship
8. EV/EBITDA vs growth rate

**Leverage Factors:**
9. D/E trend (declining preferred)
10. Interest coverage improving
11. Pledging <10% (critical for India)

**Growth Factors:**
12. Revenue CAGR 3-year
13. Earnings growth consistency
14. Market share gains (vs peers)

**Sentiment Factors:**
15. Analyst upgrades (Moneycontrol)
16. FII/DII accumulation (Trendlyne)
17. Management guidance positive (concalls)

#### Strengths

✅ **Fast**: Vectorized computation, backtest in hours
✅ **Cheap**: One-time LLM cost for factor extraction
✅ **Reproducible**: Deterministic factor calculations
✅ **Iterative**: Rapid testing of variations
✅ **Explainable**: Clear factor contributions

#### Weaknesses

❌ **Reductionist**: May miss nuanced agent reasoning
❌ **Context loss**: Factors don't capture full picture
❌ **Validation needed**: Must check factors match agent
❌ **Factor drift**: Agent reasoning may evolve over time
❌ **Regime changes**: Factors valid in one period may not transfer

#### Cost Analysis

- Initial extraction: 100 stocks × $0.10 = **$10**
- Factor backtest: Negligible (pandas operations)
- Validation sampling: 50 stocks quarterly × 4 quarters = **$20/year**
- **Total**: ~$30 vs $37,500 (Approach 1)

**Verdict**: 1,250x cheaper, enables rapid iteration

---

### Approach 3: Monte Carlo Simulation with Agent Confidence

**Core Concept**: Run agent on smaller sample, model decision distribution, use Monte Carlo to simulate outcomes under uncertainty.

#### Implementation Design

```python
class MonteCarloAgentBacktester:
    """
    Model agent decision distribution, simulate outcomes
    via Monte Carlo.
    """

    def __init__(self):
        self.decision_model = None
        self.confidence_calibration = None

    def build_decision_model(self, sample_size=200):
        """
        Sample agent decisions, build probabilistic model.
        """
        samples = []

        for ticker, date in self.random_sample[:sample_size]:
            decision = await self.agent.analyze(ticker, date)

            samples.append({
                'features': self._extract_features(ticker, date),
                'decision': decision.action,
                'confidence': decision.confidence,
                'actual_return': self._get_future_return(ticker, date)
            })

        # Build conditional probability model
        # P(BUY | features) and calibrate confidence scores
        self.decision_model = self._train_decision_model(samples)
        self.confidence_calibration = self._calibrate_confidence(samples)

        return self.decision_model

    def monte_carlo_backtest(self, n_simulations=10000):
        """
        Simulate backtest outcomes under decision uncertainty.
        """
        results = []

        for sim in range(n_simulations):
            portfolio_return = 0

            for ticker, date in self.test_universe:
                features = self._extract_features(ticker, date)

                # Sample from decision distribution
                decision_prob = self.decision_model.predict_proba(features)
                decision = np.random.choice(['BUY', 'HOLD', 'SELL'],
                                           p=decision_prob)

                # Get actual return
                actual_return = self._get_future_return(ticker, date)

                if decision == 'BUY':
                    portfolio_return += actual_return
                elif decision == 'SELL':
                    portfolio_return -= actual_return

            results.append(portfolio_return)

        # Analyze distribution
        return {
            'mean': np.mean(results),
            'median': np.median(results),
            'std': np.std(results),
            'var_95': np.percentile(results, 5),  # Value at Risk
            'cvar_95': np.mean([r for r in results if r < np.percentile(results, 5)]),
            'probability_positive': sum(r > 0 for r in results) / len(results)
        }

    def confidence_calibration_analysis(self):
        """
        Critical: Check if agent confidence scores are well-calibrated.

        If agent says 90% confident, should be right 90% of time.
        """
        calibration_bins = np.linspace(0, 1, 11)
        actual_accuracy = []

        for bin_start, bin_end in zip(calibration_bins[:-1], calibration_bins[1:]):
            # Get decisions in this confidence range
            decisions_in_bin = [
                d for d in self.validation_data
                if bin_start <= d['confidence'] < bin_end
            ]

            if decisions_in_bin:
                # Calculate actual accuracy
                correct = sum(d['correct'] for d in decisions_in_bin)
                actual_accuracy.append(correct / len(decisions_in_bin))
            else:
                actual_accuracy.append(None)

        return {
            'expected_confidence': calibration_bins[1:],
            'actual_accuracy': actual_accuracy,
            'calibration_error': self._calculate_calibration_error()
        }
```

#### Strengths

✅ **Risk quantification**: Full distribution of outcomes
✅ **Uncertainty modeling**: Captures agent non-determinism
✅ **Moderate cost**: Sample-based, not exhaustive
✅ **Confidence calibration**: Validates agent self-assessment
✅ **Stress testing**: Can simulate extreme scenarios

#### Weaknesses

❌ **Model assumptions**: Decision model may be wrong
❌ **Sample dependency**: Quality depends on sample representativeness
❌ **Feature engineering**: Need good features for model
❌ **Validation complexity**: Hard to validate simulations
❌ **Cold start**: Needs initial agent samples

#### Cost Analysis

- Model building: 200 stocks × $0.10 = **$20**
- Monte Carlo: Negligible (uses model, not agent)
- Quarterly revalidation: 50 stocks × 4 = **$20/year**
- **Total**: ~$40 first year, $20/year ongoing

**Verdict**: Good middle ground for risk analysis

---

## PART 2: CRITICAL EVALUATION & SYNTHESIS

### Comparison Matrix

| Criterion | Historical Replay | Factor Proxy | Monte Carlo |
|-----------|------------------|--------------|-------------|
| **Cost** | ❌ Very High ($37k) | ✅ Very Low ($30) | ✅ Low ($40) |
| **Speed** | ❌ Very Slow (52d) | ✅ Very Fast (hours) | ✅ Fast (1-2d) |
| **Realism** | ✅ Highest | ⚠️ Medium | ⚠️ Medium |
| **Reproducibility** | ❌ Low (non-deterministic) | ✅ High | ⚠️ Medium |
| **Risk Metrics** | ✅ Complete | ✅ Complete | ✅ Complete + Distribution |
| **Iteration Speed** | ❌ Weeks | ✅ Hours | ⚠️ Days |
| **Agent Fidelity** | ✅ Perfect | ⚠️ Approximate | ⚠️ Approximate |
| **Data Requirements** | ❌ Very High | ✅ Moderate | ✅ Moderate |

### Key Insights

1. **Pure LLM backtesting is impractical** at scale due to cost and speed
2. **Factor extraction is essential** for rapid iteration
3. **Hybrid approaches** combine strengths of multiple methods
4. **Agent validation** must be built into any proxy method

---

## RECOMMENDED STRATEGY: Three-Tier Hybrid Approach

### Tier 1: Factor-Based Rapid Iteration (Weekly)

**Purpose**: Fast experimentation and strategy development

```python
# Weekly factor backtests
factor_bt = FactorProxyBacktester()
factor_bt.extract_factors_from_agent(sample_size=100)
results = factor_bt.backtest_factors(start='2021-01-01', end='2024-12-01')

# Analyze factor performance
factor_performance = factor_bt.analyze_factor_contributions()
```

**Frequency**: Weekly or after any prompt changes
**Cost**: ~$10-20 per run
**Time**: 2-4 hours

### Tier 2: Monte Carlo Risk Analysis (Monthly)

**Purpose**: Understand outcome distributions and risk

```python
# Monthly Monte Carlo analysis
mc_bt = MonteCarloAgentBacktester()
mc_bt.build_decision_model(sample_size=200)
distribution = mc_bt.monte_carlo_backtest(n_simulations=10000)

# Risk analysis
print(f"Expected return: {distribution['mean']:.2%}")
print(f"95% VaR: {distribution['var_95']:.2%}")
print(f"Probability of positive return: {distribution['probability_positive']:.1%}")
```

**Frequency**: Monthly
**Cost**: ~$20-40 per run
**Time**: 1-2 days

### Tier 3: Full Agent Replay (Quarterly)

**Purpose**: Comprehensive validation on critical periods

```python
# Quarterly comprehensive validation
replay_bt = HistoricalReplayBacktester(
    start_date='2024-07-01',
    end_date='2024-09-30',
    universe=top_200_stocks  # Reduced universe
)
results = await replay_bt.run_backtest()

# Compare to factor-based results
validation = compare_results(replay_bt.results, factor_bt.results)
```

**Frequency**: Quarterly
**Scope**: Reduced universe (top 200 stocks) × 1 quarter
**Cost**: ~$2,000 per quarter
**Time**: 3-5 days

### Validation Framework

```python
class BacktestValidator:
    """
    Continuous validation that factor/MC backtests match agent.
    """

    def validate_decision_agreement(self, sample_size=50):
        """Check factor decisions match agent decisions."""
        disagreements = []

        for ticker, date in random.sample(self.test_cases, sample_size):
            factor_decision = self.factor_bt.decide(ticker, date)
            agent_decision = await self.agent.analyze(ticker, date)

            if factor_decision != agent_decision.action:
                disagreements.append({
                    'ticker': ticker,
                    'date': date,
                    'factor': factor_decision,
                    'agent': agent_decision.action,
                    'explanation': agent_decision.explanation
                })

        disagreement_rate = len(disagreements) / sample_size

        if disagreement_rate > 0.20:  # 20% threshold
            print("⚠️  WARNING: High disagreement between factors and agent!")
            print("Consider re-extracting factors or investigating drift.")

        return disagreements

    def validate_performance_correlation(self):
        """Check factor backtest returns correlate with agent returns."""
        # Get overlapping period where we have both
        factor_returns = self.factor_bt.get_returns()
        agent_returns = self.agent_bt.get_returns()

        correlation = np.corrcoef(factor_returns, agent_returns)[0, 1]

        if correlation < 0.85:
            print(f"⚠️  WARNING: Low correlation ({correlation:.2f}) between methods!")

        return correlation
```

### Implementation Timeline

**Week 1-2: Infrastructure**
- Set up historical data pipeline
- Build factor extraction framework
- Implement basic backtest engine

**Week 3-4: Factor Development**
- Extract initial factors from agent
- Build factor calculation engine
- Run first factor backtests

**Week 5-6: Monte Carlo**
- Build decision distribution model
- Implement MC simulation
- Calibrate confidence scores

**Week 7-8: Validation**
- Run Tier 3 validation on recent quarter
- Compare all three methods
- Refine factors based on findings

**Week 9+: Production**
- Weekly Tier 1 runs
- Monthly Tier 2 runs
- Quarterly Tier 3 validation

---

## PART 3: FUNDAMENTAL ALPHA FACTORS RESEARCH

### Methodology for Factor Discovery

Using the reasoning protocol to identify fundamental factors that predict future returns in Indian markets.

---

### Factor Category 1: Quality & Profitability

#### Path A: ROIC-Based Factors

**Hypothesis**: Companies with high and expanding ROIC outperform

**Factor Definitions:**

1. **ROIC Expansion Velocity**
   ```python
   roic_expansion = (ROIC_current - ROIC_3y_ago) / 3
   # Measures: Rate of ROIC improvement
   # Prediction: Higher velocity → higher returns
   ```

2. **ROIC Consistency**
   ```python
   roic_consistency = 1 - (std(ROIC_5y) / mean(ROIC_5y))
   # Measures: Stability of returns on capital
   # Prediction: More consistent → lower risk, steadier returns
   ```

3. **ROIC vs WACC Spread**
   ```python
   value_creation = ROIC - WACC
   # Measures: Economic profit creation
   # Prediction: Wider spread → value creation → higher returns
   ```

**Academic Support:**
- Fama-French (2006): Profitability factor significant
- Novy-Marx (2013): Gross profitability predicts returns
- Indian evidence: Mohanram (2005) G-Score includes ROIC

#### Path B: Cash Flow Quality

**Hypothesis**: FCF generation and quality superior to earnings

**Factor Definitions:**

4. **FCF/Earnings Quality**
   ```python
   fcf_quality = FCF / Net_Income
   # Measures: Cash backing of earnings
   # Prediction: Higher ratio → higher quality → outperformance
   ```

5. **FCF Yield Expansion**
   ```python
   fcf_yield_delta = (FCF/EV)_current - (FCF/EV)_1y_ago
   # Measures: Improving cash generation relative to valuation
   # Prediction: Positive delta → undervalued → mean reversion
   ```

6. **Working Capital Discipline**
   ```python
   wc_efficiency = Delta(Revenue) / Delta(Working_Capital)
   # Measures: Revenue growth without WC bloat
   # Prediction: Higher efficiency → quality growth
   ```

#### Path C: ROE Decomposition (DuPont)

**Hypothesis**: Source of ROE matters (margin vs turnover vs leverage)

**Factor Definitions:**

7. **Margin-Driven ROE**
   ```python
   margin_contribution = Delta(Net_Margin) * Asset_Turnover * Leverage
   # Measures: ROE change from margin expansion
   # Prediction: Margin expansion more sustainable than leverage
   ```

8. **Asset Efficiency Improvement**
   ```python
   efficiency_improvement = Delta(Asset_Turnover) * Margin * Leverage
   # Measures: Better asset utilization
   # Prediction: Efficiency gains → competitive advantage
   ```

**Evaluation:**

| Factor | Data Availability | Signal Strength | Turnover | Best Approach |
|--------|------------------|-----------------|----------|---------------|
| ROIC Expansion | ✅ Good | ⭐⭐⭐⭐ | Low | **A - Primary** |
| FCF Quality | ⚠️ Moderate | ⭐⭐⭐⭐ | Medium | **B - Secondary** |
| ROE Decomp | ✅ Good | ⭐⭐⭐ | Low | **C - Tertiary** |

**Synthesis**: Use ROIC Expansion as primary quality signal, validate with FCF Quality

---

### Factor Category 2: Growth & Momentum

#### Path A: Revenue Quality & Persistence

**Factor Definitions:**

9. **Revenue CAGR 3Y**
   ```python
   revenue_cagr = (Revenue_current / Revenue_3y_ago) ** (1/3) - 1
   # Prediction: >20% CAGR → sustained growth → outperformance
   ```

10. **Revenue Visibility (Recurring)**
    ```python
    revenue_visibility = Recurring_Revenue / Total_Revenue
    # For SaaS, subscriptions
    # Prediction: Higher visibility → lower risk → valuation premium
    ```

11. **Market Share Gains**
    ```python
    market_share_delta = (Company_Revenue_Growth - Sector_Revenue_Growth)
    # Measures: Gaining share vs losing
    # Prediction: Share gains → competitive strength
    ```

#### Path B: Earnings Momentum

**Factor Definitions:**

12. **Earnings Surprise Momentum**
    ```python
    surprise_momentum = (Actual_EPS - Consensus_EPS) / Consensus_EPS
    # Measures: Beating estimates
    # Prediction: Positive surprises → analyst upgrades → price momentum
    ```

13. **Earnings Revision Breadth**
    ```python
    revision_breadth = (Upgrades - Downgrades) / Total_Analysts
    # Measures: Analyst sentiment shift
    # Prediction: Positive breadth → price follows
    ```

14. **Forward Guidance Strength**
    ```python
    guidance_strength = Management_Guide / Consensus_Estimate - 1
    # From concall transcripts
    # Prediction: Management optimism → future beats
    ```

#### Path C: Growth Acceleration

**Factor Definitions:**

15. **Growth Inflection**
    ```python
    inflection = (Revenue_Growth_Q1 - Revenue_Growth_Q5) > 0
    # Measures: Turning point from deceleration to acceleration
    # Prediction: Inflection points mispriced → opportunity
    ```

**Evaluation:**

- **Path A**: Better for India (less analyst coverage, market share data available)
- **Path B**: Requires extensive analyst data (Moneycontrol/Trendlyne help)
- **Path C**: High signal but noisy, needs smoothing

**Synthesis**: Combine Path A (Revenue CAGR) with Path C (Inflection detection)

---

### Factor Category 3: Valuation

#### Path A: Relative Valuation (Peer-Adjusted)

**Factor Definitions:**

16. **P/E vs Sector Median**
    ```python
    pe_zscore = (Company_PE - Sector_Median_PE) / Sector_Std_PE
    # Measures: Relative cheapness
    # Prediction: Negative z-score → undervalued → mean reversion
    ```

17. **PEG Ratio Adjusted**
    ```python
    peg_adjusted = PE / (Earnings_Growth_3Y * 100)
    # Traditional PEG but with 3Y growth
    # Prediction: PEG < 1.0 → cheap growth
    ```

18. **EV/EBITDA vs ROE Relationship**
    ```python
    valuation_quality = EV_EBITDA / ROE
    # Measures: Paying reasonable price for quality
    # Prediction: Lower ratio → quality at reasonable price
    ```

#### Path B: Absolute Valuation (Intrinsic)

**Factor Definitions:**

19. **FCF Yield**
    ```python
    fcf_yield = FCF / Enterprise_Value
    # Measures: Cash return on enterprise value
    # Prediction: >8% yield in India → attractive
    ```

20. **Earnings Yield vs Bond Yield Spread**
    ```python
    equity_risk_premium = Earnings_Yield - Indian_10Y_Yield
    # Measures: Equity attractiveness vs bonds
    # Prediction: Wider spread → equities attractive
    ```

**Evaluation:**

- **Path A**: More robust (peer comparison controls for sector effects)
- **Path B**: Simpler but needs macro timing

**Synthesis**: Use Path A for stock selection, Path B for market timing

---

### Factor Category 4: Indian Market Specific

#### Path A: Ownership Structure Factors

**Factor Definitions:**

21. **Promoter Holding Stability**
    ```python
    promoter_stability = 1 - abs(Promoter_Holding_Now - Promoter_Holding_1Y_Ago)
    # Measures: Promoter confidence
    # Prediction: Stable/increasing → positive signal
    ```

22. **FII Accumulation**
    ```python
    fii_accumulation = (FII_Holding_Now - FII_Holding_2Q_Ago) / 2
    # From Trendlyne
    # Prediction: FII accumulation → price support
    ```

23. **Pledging Risk**
    ```python
    pledging_risk = Pledged_Shares_Pct / Promoter_Holding_Pct
    # Critical for India
    # Prediction: >50% pledging → RED FLAG → avoid
    ```

#### Path B: Corporate Governance

**Factor Definitions:**

24. **Independent Director Ratio**
    ```python
    board_independence = Independent_Directors / Total_Directors
    # Measures: Governance quality
    # Prediction: Higher ratio → better governance → lower risk
    ```

25. **Related Party Transaction Intensity**
    ```python
    rpt_intensity = Related_Party_Transactions / Total_Revenue
    # Measures: Potential tunneling
    # Prediction: Lower ratio → cleaner governance
    ```

**Evaluation:**

- **Path A**: High signal in India (promoter/FII data available via Trendlyne)
- **Path B**: Important but data harder to obtain systematically

**Synthesis**: Focus on Path A (ownership) as primary Indian alpha source

---

### Factor Category 5: Sentiment & Information

#### Path A: Analyst Sentiment

**Factor Definitions:**

26. **Recommendation Upgrade Momentum**
    ```python
    upgrade_momentum = (Upgrades_3M - Downgrades_3M) / Total_Coverage
    # From Moneycontrol
    # Prediction: Net upgrades → positive sentiment → price follows
    ```

27. **Price Target Implied Upside**
    ```python
    target_upside = (Consensus_Target - Current_Price) / Current_Price
    # From Trendlyne
    # Prediction: >20% upside → potential catalyst
    ```

#### Path B: News & Events

**Factor Definitions:**

28. **Management Tone (Concalls)**
    ```python
    # Extract from Screener.in concall transcripts
    management_tone = LLM_sentiment_analysis(concall_transcript)
    # Prediction: Positive tone → future outperformance
    ```

29. **Capex Announcement Signal**
    ```python
    capex_signal = Announced_Capex / Current_Revenue
    # From news/concalls
    # Prediction: Large capex → growth confidence
    ```

**Evaluation:**

- **Path A**: Reliable data (Moneycontrol, Trendlyne)
- **Path B**: Innovative but requires NLP pipeline

**Synthesis**: Start with Path A, layer in Path B as sophistication grows

---

## FINAL FACTOR RANKING & PORTFOLIO

### Top 15 Factors for Indian Markets

**Tier 1: Core Quality (40% weight)**
1. ROIC Expansion Velocity ⭐⭐⭐⭐⭐
2. FCF/Earnings Quality ⭐⭐⭐⭐⭐
3. ROIC Consistency ⭐⭐⭐⭐

**Tier 2: Growth (25% weight)**
4. Revenue CAGR 3Y ⭐⭐⭐⭐⭐
5. Market Share Gains ⭐⭐⭐⭐
6. Growth Inflection ⭐⭐⭐⭐

**Tier 3: Valuation (15% weight)**
7. P/E vs Sector Median ⭐⭐⭐⭐
8. PEG Ratio <1.2 ⭐⭐⭐⭐

**Tier 4: Indian Specific (15% weight)**
9. Pledging Risk (inverse) ⭐⭐⭐⭐⭐
10. FII Accumulation ⭐⭐⭐⭐
11. Promoter Stability ⭐⭐⭐⭐

**Tier 5: Sentiment (5% weight)**
12. Analyst Upgrade Momentum ⭐⭐⭐
13. Price Target Upside >15% ⭐⭐⭐

### Factor Combination Strategy

```python
def calculate_composite_score(ticker, date):
    """
    Weighted composite of all factors.
    """
    scores = {}

    # Tier 1: Quality (40%)
    scores['quality'] = (
        0.15 * z_score(roic_expansion(ticker, date)) +
        0.15 * z_score(fcf_quality(ticker, date)) +
        0.10 * z_score(roic_consistency(ticker, date))
    )

    # Tier 2: Growth (25%)
    scores['growth'] = (
        0.10 * z_score(revenue_cagr(ticker, date)) +
        0.08 * z_score(market_share_gains(ticker, date)) +
        0.07 * binary(growth_inflection(ticker, date))
    )

    # Tier 3: Valuation (15%)
    scores['valuation'] = (
        0.08 * z_score(-1 * pe_vs_sector(ticker, date)) +  # Negative: lower is better
        0.07 * binary(peg_ratio(ticker, date) < 1.2)
    )

    # Tier 4: Indian Specific (15%)
    scores['indian'] = (
        0.06 * z_score(-1 * pledging_risk(ticker, date)) +  # Negative: lower is better
        0.05 * z_score(fii_accumulation(ticker, date)) +
        0.04 * z_score(promoter_stability(ticker, date))
    )

    # Tier 5: Sentiment (5%)
    scores['sentiment'] = (
        0.03 * z_score(analyst_upgrade_momentum(ticker, date)) +
        0.02 * binary(price_target_upside(ticker, date) > 0.15)
    )

    # Composite score (sum to 100%)
    composite = sum(scores.values())

    return composite, scores

def portfolio_construction(universe, date, top_n=30):
    """
    Build portfolio from factor scores.
    """
    # Calculate scores for all stocks
    stock_scores = [
        (ticker, calculate_composite_score(ticker, date)[0])
        for ticker in universe
    ]

    # Rank and select top N
    stock_scores.sort(key=lambda x: x[1], reverse=True)
    portfolio = stock_scores[:top_n]

    # Equal weight or score-weighted
    return portfolio
```

---

## TESTING FRAMEWORK

### Walk-Forward Backtesting

```python
class WalkForwardBacktester:
    """
    Industry-standard walk-forward optimization to avoid overfitting.
    """

    def __init__(self, lookback_months=12, test_months=3):
        self.lookback = lookback_months
        self.test = test_months

    def run_walkforward(self, start_date, end_date):
        """
        1. Train factors on 12M data
        2. Test on next 3M
        3. Roll forward, repeat
        """
        results = []
        current = start_date

        while current + timedelta(days=self.lookback*30) < end_date:
            # Training period
            train_start = current
            train_end = current + timedelta(days=self.lookback*30)

            # Optimize factor weights on training period
            optimal_weights = self._optimize_factors(train_start, train_end)

            # Testing period
            test_start = train_end + timedelta(days=1)
            test_end = test_start + timedelta(days=self.test*30)

            # Test with optimized weights
            test_return = self._test_strategy(test_start, test_end, optimal_weights)

            results.append({
                'train_period': (train_start, train_end),
                'test_period': (test_start, test_end),
                'weights': optimal_weights,
                'return': test_return
            })

            # Roll forward
            current = test_end

        return results
```

### Performance Metrics

```python
def calculate_performance_metrics(returns, benchmark_returns):
    """
    Comprehensive performance analysis.
    """
    return {
        # Returns
        'total_return': (1 + returns).prod() - 1,
        'cagr': ((1 + returns).prod() ** (252 / len(returns))) - 1,
        'annualized_return': returns.mean() * 252,

        # Risk
        'volatility': returns.std() * np.sqrt(252),
        'max_drawdown': (returns.cumsum().cummax() - returns.cumsum()).max(),
        'downside_deviation': returns[returns < 0].std() * np.sqrt(252),

        # Risk-Adjusted
        'sharpe_ratio': (returns.mean() * 252) / (returns.std() * np.sqrt(252)),
        'sortino_ratio': (returns.mean() * 252) / (returns[returns < 0].std() * np.sqrt(252)),
        'calmar_ratio': (returns.mean() * 252) / max_drawdown,

        # Relative
        'alpha': calculate_alpha(returns, benchmark_returns),
        'beta': calculate_beta(returns, benchmark_returns),
        'information_ratio': (returns - benchmark_returns).mean() / (returns - benchmark_returns).std(),
        'tracking_error': (returns - benchmark_returns).std() * np.sqrt(252),

        # Distribution
        'skewness': returns.skew(),
        'kurtosis': returns.kurtosis(),
        'var_95': returns.quantile(0.05),
        'cvar_95': returns[returns < returns.quantile(0.05)].mean(),
    }
```

---

## CONCLUSION & RECOMMENDATIONS

### Recommended Backtesting Implementation

**Phase 1 (Month 1-2): Foundation**
- Implement Tier 1 Factor-based backtesting
- Extract top 15 factors from agent reasoning
- Run initial 3-year backtest

**Phase 2 (Month 2-3): Validation**
- Implement Monte Carlo simulation (Tier 2)
- Run confidence calibration analysis
- Compare factor vs MC results

**Phase 3 (Month 3-4): Comprehensive Testing**
- Run Tier 3 agent replay on recent quarter
- Validate factor extraction accuracy
- Refine factors based on disagreements

**Phase 4 (Month 4+): Production**
- Weekly factor backtests
- Monthly MC risk analysis
- Quarterly full agent validation
- Continuous factor refinement

### Success Criteria

Before production deployment, require:

1. **Factor Validation**: >85% agreement between factors and agent
2. **Performance**: Sharpe ratio >1.5 in walk-forward tests
3. **Consistency**: Positive returns in >70% of rolling 12M periods
4. **Risk**: Max drawdown <25%
5. **Robustness**: Strategy works across market regimes (bull/bear/sideways)

### Cost Budget

- **Development**: $500-1,000 (factor extraction, initial tests)
- **Ongoing Monthly**: $50-100 (validation sampling)
- **Quarterly Deep Dive**: $2,000 (comprehensive replay)
- **Annual Total**: ~$9,000

**ROI**: If strategy generates >1% additional alpha, ROI on $10M AUM = $100k vs $9k cost = **11x ROI**

---

## APPENDIX: Implementation Code Templates

See separate files:
- `backtesting/factor_extractor.py`
- `backtesting/monte_carlo_sim.py`
- `backtesting/walkforward_optimizer.py`
- `backtesting/performance_analytics.py`

---

**Document Version**: 1.0
**Author**: AI Investment Agent Development Team
**Review Date**: 2025-12-07
**Next Review**: After Phase 1 completion
