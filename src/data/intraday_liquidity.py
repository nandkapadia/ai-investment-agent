"""
Enhanced Liquidity Analysis using 1-minute Intraday Data

Provides institutional-grade liquidity assessment for Indian stocks:
- Manipulation detection (volume concentration, end-of-day ramps)
- Liquidity consistency (sporadic vs continuous trading)
- Institutional signature detection (FII/DII patterns)
- Optimal entry time recommendations
"""

import pandas as pd
import numpy as np
import structlog
from typing import Dict, List, Optional
from datetime import datetime

from src.data.intraday_loader import IntradayDataLoader

logger = structlog.get_logger(__name__)


class IntradayLiquidityAnalyzer:
    """
    Multi-dimensional liquidity analysis using 1-minute data.

    Detects:
    - Manipulated stocks (volume concentration, end-of-day ramps)
    - Institutional vs retail trading patterns
    - Best times to enter/exit
    - Real vs artificial liquidity
    """

    def __init__(self, data_dir: str = None):
        """Initialize analyzer with data loader."""
        self.loader = IntradayDataLoader(data_dir)

    def is_available(self) -> bool:
        """Check if intraday data is available."""
        return self.loader.is_available()

    async def calculate_liquidity_score(
        self,
        ticker: str,
        lookback_days: int = 90
    ) -> Dict:
        """
        Calculate comprehensive liquidity metrics.

        Args:
            ticker: Stock symbol
            lookback_days: Days of history to analyze

        Returns:
            {
                'avg_daily_turnover_inr': float,
                'liquidity_consistency': float (0-1),
                'volume_concentration': float (0-1),
                'institutional_signature': float (0-1),
                'manipulation_risk': str (LOW/MEDIUM/HIGH),
                'recommended_entry_windows': list,
                'final_status': str (PASS/MARGINAL/FAIL),
                'details': str
            }
        """

        # Check if data exists
        if not self.loader.has_data(ticker):
            logger.warning("no_intraday_data", ticker=ticker)
            return None

        # Load data
        try:
            df = self.loader.load(ticker, lookback_days=lookback_days)
        except Exception as e:
            logger.error("intraday_load_failed", ticker=ticker, error=str(e))
            return None

        if df.empty:
            logger.warning("empty_intraday_data", ticker=ticker)
            return None

        # Calculate metrics
        avg_turnover_inr = self._calc_avg_turnover(df)
        consistency = self._calc_consistency(df)
        concentration = self._calc_volume_concentration(df)
        institutional = self._detect_institutional_pattern(df)
        manipulation = self._detect_manipulation(df)
        entry_windows = self._find_best_entry_times(df)

        # Enhanced decision
        final_status = self._enhanced_decision(
            avg_turnover_inr, consistency, concentration, manipulation
        )

        metrics = {
            'avg_daily_turnover_inr': avg_turnover_inr,
            'liquidity_consistency': consistency,
            'volume_concentration': concentration,
            'institutional_signature': institutional,
            'manipulation_risk': manipulation,
            'recommended_entry_windows': entry_windows,
            'final_status': final_status,
            'details': self._format_details(
                avg_turnover_inr, consistency, concentration,
                institutional, manipulation, entry_windows, final_status
            )
        }

        logger.info("intraday_liquidity_calculated", ticker=ticker, metrics=metrics)

        return metrics

    def _calc_avg_turnover(self, df: pd.DataFrame) -> float:
        """Calculate average daily turnover in INR."""
        # Group by date
        daily = df.groupby(df.index.date).agg({
            'close': 'last',
            'volume': 'sum'
        })

        # Daily turnover = volume * closing price
        daily['turnover'] = daily['volume'] * daily['close']

        return daily['turnover'].mean()

    def _calc_consistency(self, df: pd.DataFrame) -> float:
        """
        Liquidity consistency score (0-1).

        High score = trading throughout day
        Low score = sporadic, concentrated trading (red flag)
        """
        # % of 1-min bars with volume > 0
        active_bars_pct = (df['volume'] > 0).sum() / len(df)

        # Volume distribution across hours (Gini coefficient)
        hourly_vol = df.groupby(df.index.hour)['volume'].sum()
        gini = self._gini_coefficient(hourly_vol.values)

        # Combined score: activity spread × even distribution
        consistency = (active_bars_pct * 0.6) + ((1 - gini) * 0.4)

        return round(consistency, 2)

    def _calc_volume_concentration(self, df: pd.DataFrame) -> float:
        """
        Volume concentration index (0-1).

        Measures: What % of volume comes from top 10% of bars?
        High concentration = manipulation risk
        """
        if df['volume'].sum() == 0:
            return 1.0

        # Sort by volume
        df_sorted = df.sort_values('volume', ascending=False)

        # Top 10% of bars
        top_10_pct = int(len(df) * 0.1)
        top_volume = df_sorted.head(top_10_pct)['volume'].sum()
        total_volume = df['volume'].sum()

        concentration = top_volume / total_volume if total_volume > 0 else 1.0

        return round(concentration, 2)

    def _detect_institutional_pattern(self, df: pd.DataFrame) -> float:
        """
        Institutional activity signature (0-1).

        Indian institutional patterns:
        - FII: Active 9:15-10:00 AM (opening auction + first hour)
        - DII: Active throughout, peak 2:30-3:15 PM
        - Retail: Peak 11:00-1:00 PM, 3:00-3:30 PM

        Returns:
        - 0.7-1.0: Strong institutional
        - 0.4-0.7: Mixed
        - 0.0-0.4: Retail/operator driven
        """
        # Volume by hour
        hourly_profile = df.groupby(df.index.hour)['volume'].sum()

        if hourly_profile.sum() == 0:
            return 0.5

        # Normalize
        hourly_profile = hourly_profile / hourly_profile.sum()

        # Institutional hours: 9-10 AM (open), 2-3 PM (late afternoon)
        institutional_hours = [9, 10, 14, 15]
        # Retail hours: 11 AM - 1 PM (lunch break trading)
        retail_hours = [11, 12, 13]

        inst_volume = hourly_profile[hourly_profile.index.isin(institutional_hours)].sum()
        retail_volume = hourly_profile[hourly_profile.index.isin(retail_hours)].sum()

        if inst_volume + retail_volume > 0:
            score = inst_volume / (inst_volume + retail_volume)
        else:
            score = 0.5

        return round(score, 2)

    def _detect_manipulation(self, df: pd.DataFrame) -> str:
        """
        Manipulation risk detection.

        Red flags:
        1. Extreme volume spikes (>10x avg)
        2. End-of-day ramps (last 5 mins = >20% daily volume)
        3. Repeated patterns (circular trading)

        Returns: 'LOW' | 'MEDIUM' | 'HIGH'
        """
        risk_score = 0

        # Flag 1: Volume spikes
        avg_bar_volume = df['volume'].mean()
        max_bar_volume = df['volume'].max()

        if avg_bar_volume > 0:
            if max_bar_volume > 10 * avg_bar_volume:
                risk_score += 2  # Severe
            elif max_bar_volume > 5 * avg_bar_volume:
                risk_score += 1  # Moderate

        # Flag 2: End-of-day manipulation
        daily_groups = df.groupby(df.index.date)

        eod_manipulation_count = 0
        for date, day_df in daily_groups:
            if len(day_df) < 5:
                continue

            # Last 5 minutes volume
            eod_volume = day_df.tail(5)['volume'].sum()
            daily_volume = day_df['volume'].sum()

            if daily_volume > 0 and (eod_volume / daily_volume) > 0.2:
                eod_manipulation_count += 1

        # If >30% of days show end-of-day concentration
        if len(daily_groups) > 0:
            eod_ratio = eod_manipulation_count / len(daily_groups)
            if eod_ratio > 0.3:
                risk_score += 2
            elif eod_ratio > 0.15:
                risk_score += 1

        # Flag 3: Price manipulation (too few unique prices)
        unique_prices = df['close'].nunique()
        total_bars = len(df)

        if total_bars > 0:
            price_diversity = unique_prices / total_bars
            if price_diversity < 0.01:  # Same price in >99% of bars
                risk_score += 1

        # Classification
        if risk_score >= 4:
            return 'HIGH'
        elif risk_score >= 2:
            return 'MEDIUM'
        else:
            return 'LOW'

    def _find_best_entry_times(self, df: pd.DataFrame) -> List[str]:
        """
        Identify best times to enter/exit.

        Criteria:
        - High volume (good liquidity)
        - Low volatility (safer entry)
        - Avoiding manipulation windows

        Returns: List of time windows (e.g., ["9:30-9:45", "14:00-14:15"])
        """
        # Calculate volatility and volume by 15-min buckets
        df = df.copy()
        df['hour'] = df.index.hour
        df['minute_bucket'] = df.index.minute // 15  # 0, 15, 30, 45

        time_analysis = df.groupby(['hour', 'minute_bucket']).agg({
            'high': 'max',
            'low': 'min',
            'volume': 'sum',
            'close': 'mean'
        })

        if len(time_analysis) == 0:
            return []

        # Calculate range (volatility proxy)
        time_analysis['range_pct'] = (
            (time_analysis['high'] - time_analysis['low']) / time_analysis['close'] * 100
        )

        # Score: high volume + low volatility = good entry
        # Normalize to 0-1 scale
        vol_normalized = (time_analysis['volume'] - time_analysis['volume'].min()) / \
                        (time_analysis['volume'].max() - time_analysis['volume'].min() + 1)

        range_normalized = 1 - ((time_analysis['range_pct'] - time_analysis['range_pct'].min()) / \
                               (time_analysis['range_pct'].max() - time_analysis['range_pct'].min() + 1))

        time_analysis['score'] = vol_normalized * 0.6 + range_normalized * 0.4

        # Top 3 time windows
        top_windows = time_analysis.nlargest(3, 'score')

        windows = []
        for (hour, bucket), row in top_windows.iterrows():
            start_min = bucket * 15
            end_min = start_min + 15
            windows.append(f"{hour:02d}:{start_min:02d}-{hour:02d}:{end_min:02d}")

        return windows

    def _enhanced_decision(
        self,
        turnover: float,
        consistency: float,
        concentration: float,
        manipulation: str
    ) -> str:
        """
        Enhanced liquidity decision using intraday insights.

        Args:
            turnover: Average daily turnover (INR)
            consistency: Liquidity consistency (0-1)
            concentration: Volume concentration (0-1)
            manipulation: Risk level (LOW/MEDIUM/HIGH)

        Returns:
            'PASS' | 'MARGINAL' | 'FAIL'
        """
        # Base decision from turnover (traditional thresholds)
        if turnover >= 12_00_000:
            base = 'PASS'
        elif turnover >= 6_00_000:
            base = 'MARGINAL'
        else:
            base = 'FAIL'

        # Adjust based on intraday analysis
        if base == 'PASS':
            # Downgrade if manipulation detected
            if manipulation == 'HIGH':
                return 'FAIL'
            elif manipulation == 'MEDIUM' or consistency < 0.5 or concentration > 0.7:
                return 'MARGINAL'
            return 'PASS'

        elif base == 'MARGINAL':
            # Upgrade if very consistent and no manipulation
            if consistency > 0.75 and manipulation == 'LOW' and concentration < 0.5:
                return 'PASS'
            # Downgrade if manipulated
            elif manipulation == 'HIGH':
                return 'FAIL'
            return 'MARGINAL'

        else:  # FAIL
            # No upgrades for very low liquidity
            return 'FAIL'

    def _format_details(
        self,
        turnover: float,
        consistency: float,
        concentration: float,
        institutional: float,
        manipulation: str,
        entry_windows: List[str],
        final_status: str
    ) -> str:
        """Format detailed analysis text."""

        turnover_lakhs = turnover / 1_00_000

        return f"""INTRADAY LIQUIDITY INSIGHTS:
✓ Consistency: {consistency:.2f} (0=sporadic, 1=continuous)
✓ Institutional Activity: {institutional:.2f} (0=retail, 1=institutional)
✓ Volume Concentration: {concentration:.2f} (lower is better)
✓ Manipulation Risk: {manipulation}

Best Entry Times: {', '.join(entry_windows) if entry_windows else 'N/A'}

INTERPRETATION:
{self._interpret_metrics(consistency, concentration, institutional, manipulation, final_status)}"""

    def _interpret_metrics(
        self,
        consistency: float,
        concentration: float,
        institutional: float,
        manipulation: str,
        final_status: str
    ) -> str:
        """Generate human-readable interpretation."""

        interpretations = []

        # Consistency
        if consistency > 0.7:
            interpretations.append("✓ Trades consistently throughout day (healthy)")
        elif consistency > 0.5:
            interpretations.append("⚠ Moderate trading consistency")
        else:
            interpretations.append("✗ Sporadic trading pattern (red flag)")

        # Institutional
        if institutional > 0.7:
            interpretations.append("✓ Strong institutional signature (FII/DII active)")
        elif institutional > 0.5:
            interpretations.append("⚠ Mixed institutional/retail activity")
        else:
            interpretations.append("⚠ Primarily retail/operator driven")

        # Concentration
        if concentration < 0.4:
            interpretations.append("✓ Volume well distributed (healthy)")
        elif concentration < 0.6:
            interpretations.append("⚠ Moderate volume concentration")
        else:
            interpretations.append("✗ High volume concentration (manipulation risk)")

        # Manipulation
        if manipulation == 'HIGH':
            interpretations.append("✗ HIGH manipulation risk - avoid this stock")
        elif manipulation == 'MEDIUM':
            interpretations.append("⚠ Moderate manipulation signals detected")
        else:
            interpretations.append("✓ Low manipulation risk")

        # Final verdict
        if final_status == 'FAIL':
            interpretations.append("\n→ RECOMMENDATION: Do not trade (insufficient/manipulated liquidity)")
        elif final_status == 'MARGINAL':
            interpretations.append("\n→ RECOMMENDATION: Trade with caution (max 3% position)")
        else:
            interpretations.append("\n→ RECOMMENDATION: Good liquidity for trading")

        return '\n'.join(interpretations)

    @staticmethod
    def _gini_coefficient(x: np.ndarray) -> float:
        """Calculate Gini coefficient (0 = equality, 1 = inequality)."""
        if len(x) == 0 or x.sum() == 0:
            return 0.0

        sorted_x = np.sort(x)
        n = len(x)
        cumsum = 0

        for i, xi in enumerate(sorted_x):
            cumsum += (n - i) * xi

        return (n + 1 - 2 * cumsum / x.sum()) / n
