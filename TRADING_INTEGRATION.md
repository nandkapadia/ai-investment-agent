# Trading System Integration Strategy
## Fundamental Filter to Trading Repository

**Status**: Strategy Document
**Date**: 2025-12-07
**Purpose**: Define integration architecture for feeding AI agent signals into trading systems

---

## Executive Summary

This document analyzes 3 approaches to integrating the AI Investment Agent as a fundamental filter feeding into trading systems, evaluates trade-offs, and recommends an optimal architecture.

**Key Challenge**: Bridge the gap between slow-moving fundamental analysis (daily/weekly) and fast-execution trading systems (millisecond latency).

**Integration Points**:
1. Signal generation (fundamental filter)
2. Universe construction (watchlist/blocklist)
3. Position sizing (risk-adjusted allocation)
4. Monitoring (ongoing position validation)

---

## APPROACH 1: API-Based Signal Feed (Loose Coupling)

### Core Concept

AI agent runs independently, exposes REST/WebSocket API that trading system queries for fundamental signals.

### Architecture

```
┌─────────────────────────────────────┐
│   AI Investment Agent System        │
│                                     │
│  ┌──────────┐    ┌──────────────┐  │
│  │  Agents  │───▶│ Signal Cache │  │
│  └──────────┘    └──────────────┘  │
│                         │           │
│                  ┌──────▼───────┐   │
│                  │  FastAPI     │   │
│                  │  /signals    │   │
│                  └──────────────┘   │
└────────────┬────────────────────────┘
             │ HTTP/WebSocket
             │
┌────────────▼────────────────────────┐
│   Trading System                    │
│                                     │
│  ┌──────────────┐  ┌─────────────┐ │
│  │ Signal       │─▶│ Portfolio   │ │
│  │ Aggregator   │  │ Optimizer   │ │
│  └──────────────┘  └──────┬──────┘ │
│                           │         │
│                    ┌──────▼──────┐  │
│                    │  Execution  │  │
│                    │  Engine     │  │
│                    └─────────────┘  │
└─────────────────────────────────────┘
```

### Implementation

#### 1. Signal API Design

```python
# api/signals.py

from fastapi import FastAPI, WebSocket, Depends
from typing import List, Optional
from datetime import datetime, timedelta
import asyncio

app = FastAPI()

class SignalCache:
    """
    Cache for fundamental signals to avoid re-running expensive
    agent analysis on every query.
    """

    def __init__(self, ttl_hours: int = 24):
        self.cache = {}
        self.ttl = timedelta(hours=ttl_hours)

    async def get_signal(self, ticker: str) -> Optional[dict]:
        """Get cached signal if still valid."""
        if ticker in self.cache:
            signal, timestamp = self.cache[ticker]
            if datetime.now() - timestamp < self.ttl:
                return signal
        return None

    async def set_signal(self, ticker: str, signal: dict):
        """Cache signal with timestamp."""
        self.cache[ticker] = (signal, datetime.now())

signal_cache = SignalCache()

@app.get("/api/v1/signals/universe")
async def get_universe_signals(
    min_score: float = 6.0,
    max_results: int = 50,
    sectors: Optional[List[str]] = None
) -> dict:
    """
    Get fundamental signals for entire universe.

    Returns stocks passing fundamental filter with scores.
    Trading system uses this for universe construction.
    """
    # Get pre-computed signals from database
    signals = await db.get_latest_signals(
        min_score=min_score,
        sectors=sectors,
        limit=max_results
    )

    return {
        "timestamp": datetime.now().isoformat(),
        "signals": [
            {
                "ticker": s.ticker,
                "score": s.score,
                "recommendation": s.recommendation,
                "confidence": s.confidence,
                "fair_value": s.fair_value,
                "current_price": s.current_price,
                "upside": s.upside,
                "risk_level": s.risk_level,
                "last_updated": s.updated_at.isoformat()
            }
            for s in signals
        ],
        "metadata": {
            "total_universe": len(signals),
            "avg_score": sum(s.score for s in signals) / len(signals),
            "sectors_covered": list(set(s.sector for s in signals))
        }
    }

@app.get("/api/v1/signals/{ticker}")
async def get_ticker_signal(
    ticker: str,
    force_refresh: bool = False
) -> dict:
    """
    Get fundamental signal for specific ticker.

    Trading system queries this before entering position.
    """
    # Check cache
    if not force_refresh:
        cached = await signal_cache.get_signal(ticker)
        if cached:
            return {
                "ticker": ticker,
                "signal": cached,
                "source": "cache",
                "age_hours": (datetime.now() - cached['timestamp']).total_seconds() / 3600
            }

    # Run fresh analysis
    analysis = await agent_orchestrator.analyze(ticker, depth="standard")

    # Extract signal
    signal = {
        "ticker": ticker,
        "score": analysis.score,
        "recommendation": analysis.recommendation,
        "confidence": analysis.confidence,
        "fair_value": analysis.fair_value,
        "risk_factors": analysis.risk_factors,
        "timestamp": datetime.now().isoformat()
    }

    # Cache
    await signal_cache.set_signal(ticker, signal)

    return {
        "ticker": ticker,
        "signal": signal,
        "source": "fresh",
        "age_hours": 0
    }

@app.get("/api/v1/signals/watchlist")
async def get_watchlist_signals(
    tickers: List[str],
    background_refresh: bool = True
) -> dict:
    """
    Batch query for watchlist tickers.

    Trading system uses this for daily universe refresh.
    """
    results = []

    # Get cached signals
    for ticker in tickers:
        signal = await signal_cache.get_signal(ticker)
        if signal:
            results.append({
                "ticker": ticker,
                "signal": signal,
                "source": "cache"
            })
        else:
            results.append({
                "ticker": ticker,
                "signal": None,
                "source": "missing"
            })

    # Optionally trigger background refresh for missing
    if background_refresh:
        missing = [r['ticker'] for r in results if r['signal'] is None]
        if missing:
            asyncio.create_task(refresh_signals_background(missing))

    return {
        "timestamp": datetime.now().isoformat(),
        "signals": results,
        "summary": {
            "total_requested": len(tickers),
            "cached": sum(1 for r in results if r['source'] == 'cache'),
            "missing': sum(1 for r in results if r['source'] == 'missing'),
            "background_refresh_triggered": background_refresh and any(r['source'] == 'missing' for r in results)
        }
    }

@app.websocket("/ws/signals/stream")
async def signal_stream(websocket: WebSocket):
    """
    Real-time signal updates via WebSocket.

    Trading system can subscribe for live updates when
    fundamental signals change.
    """
    await websocket.accept()

    try:
        while True:
            # Wait for new signal
            signal = await signal_queue.get()

            # Send to subscriber
            await websocket.send_json({
                "type": "signal_update",
                "ticker": signal['ticker'],
                "signal": signal['data'],
                "timestamp": datetime.now().isoformat()
            })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")

@app.post("/api/v1/signals/validate")
async def validate_position(
    ticker: str,
    entry_price: float,
    current_price: float,
    days_held: int
) -> dict:
    """
    Validate existing position against current fundamentals.

    Trading system calls this to check if position should be held.
    """
    # Get latest analysis
    signal = await get_ticker_signal(ticker, force_refresh=True)

    # Calculate PnL
    pnl_pct = (current_price - entry_price) / entry_price

    # Compare to fair value
    fair_value = signal['signal']['fair_value']
    remaining_upside = (fair_value - current_price) / current_price

    # Recommendation logic
    if signal['signal']['recommendation'] == 'SELL':
        action = 'EXIT'
        reason = 'Fundamental downgrade to SELL'
    elif remaining_upside < 0.05:  # Less than 5% upside
        action = 'REDUCE'
        reason = 'Price near fair value, limited upside remaining'
    elif pnl_pct > 0.50:  # Up 50%+
        action = 'PARTIAL_EXIT'
        reason = 'Take profits after significant gain'
    else:
        action = 'HOLD'
        reason = 'Fundamentals intact, upside remaining'

    return {
        "ticker": ticker,
        "current_signal": signal['signal'],
        "position_metrics": {
            "entry_price": entry_price,
            "current_price": current_price,
            "pnl_pct": pnl_pct,
            "days_held": days_held
        },
        "action": action,
        "reason": reason,
        "target_price": fair_value,
        "remaining_upside": remaining_upside
    }
```

#### 2. Trading System Client

```python
# trading_system/fundamental_filter.py

import httpx
from typing import List, Dict
import asyncio

class FundamentalFilter:
    """
    Client for AI agent fundamental signals.

    Integrates with trading system's universe construction.
    """

    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.headers = {"Authorization": f"Bearer {api_key}"}
        self.client = httpx.AsyncClient(base_url=api_url, headers=self.headers)

    async def get_trading_universe(
        self,
        min_score: float = 6.5,
        max_positions: int = 30,
        sector_diversification: bool = True
    ) -> List[str]:
        """
        Get list of tickers passing fundamental filter.

        Returns:
            List of tickers suitable for trading
        """
        # Query signals API
        response = await self.client.get(
            "/api/v1/signals/universe",
            params={
                "min_score": min_score,
                "max_results": max_positions * 2  # Get 2x for diversification
            }
        )

        signals = response.json()['signals']

        # Apply sector diversification
        if sector_diversification:
            signals = self._diversify_by_sector(signals, max_positions)

        # Extract tickers
        tickers = [s['ticker'] for s in signals[:max_positions]]

        return tickers

    def _diversify_by_sector(self, signals: List[dict], max_positions: int) -> List[dict]:
        """
        Ensure no sector exceeds 30% of portfolio.
        """
        max_per_sector = int(max_positions * 0.30)
        sector_counts = {}
        diversified = []

        # Sort by score descending
        signals = sorted(signals, key=lambda x: x['score'], reverse=True)

        for signal in signals:
            sector = signal.get('sector', 'Unknown')

            if sector_counts.get(sector, 0) < max_per_sector:
                diversified.append(signal)
                sector_counts[sector] = sector_counts.get(sector, 0) + 1

            if len(diversified) >= max_positions:
                break

        return diversified

    async def validate_ticker(self, ticker: str) -> dict:
        """
        Check if ticker passes fundamental filter before entry.
        """
        response = await self.client.get(f"/api/v1/signals/{ticker}")
        signal = response.json()['signal']

        # Decision logic
        if signal['recommendation'] == 'BUY' and signal['score'] >= 6.0:
            return {
                "approved": True,
                "signal": signal,
                "notes": f"Score: {signal['score']}/10, Upside: {signal['upside']:.1%}"
            }
        else:
            return {
                "approved": False,
                "signal": signal,
                "notes": f"Does not pass filter (score: {signal['score']}, rec: {signal['recommendation']})"
            }

    async def get_position_sizing(self, ticker: str, portfolio_value: float) -> float:
        """
        Risk-adjusted position sizing based on fundamental conviction.

        Higher conviction (score, lower risk) = larger position
        """
        response = await self.client.get(f"/api/v1/signals/{ticker}")
        signal = response.json()['signal']

        # Base allocation
        base_allocation = 0.03  # 3% base

        # Adjust for score (6.0-10.0 scale)
        score_multiplier = (signal['score'] - 6.0) / 4.0  # 0 to 1
        score_adjustment = score_multiplier * 0.02  # Add up to 2%

        # Adjust for risk level
        risk_adjustments = {
            'LOW': 1.0,
            'MEDIUM': 0.7,
            'HIGH': 0.4
        }
        risk_multiplier = risk_adjustments.get(signal['risk_level'], 0.5)

        # Final allocation
        allocation_pct = (base_allocation + score_adjustment) * risk_multiplier

        # Clamp between 1% and 5%
        allocation_pct = max(0.01, min(0.05, allocation_pct))

        # Calculate position size
        position_size = portfolio_value * allocation_pct

        return position_size

    async def monitor_positions(self, positions: List[dict]) -> List[dict]:
        """
        Check all positions against current fundamentals.

        Returns list of recommended actions (hold/reduce/exit).
        """
        actions = []

        for position in positions:
            response = await self.client.post(
                "/api/v1/signals/validate",
                json={
                    "ticker": position['ticker'],
                    "entry_price": position['entry_price'],
                    "current_price": position['current_price'],
                    "days_held": position['days_held']
                }
            )

            validation = response.json()
            actions.append({
                "ticker": position['ticker'],
                "action": validation['action'],
                "reason": validation['reason'],
                "current_allocation": position['allocation'],
                "recommended_allocation": self._calculate_recommended_allocation(validation)
            })

        return actions
```

### Strengths

✅ **Loose Coupling**: Systems independent, can evolve separately
✅ **Language Agnostic**: Trading system can be any language (Python/C++/Java)
✅ **Scalability**: API can handle multiple consumers
✅ **Testing**: Easy to mock API for trading system tests
✅ **Caching**: Avoid expensive re-computation
✅ **Real-time**: WebSocket for live updates

### Weaknesses

❌ **Network Dependency**: Trading system needs network access
❌ **Latency**: HTTP roundtrips add delay (50-200ms)
❌ **Availability**: Trading system blocked if agent API down
❌ **Versioning**: API changes need coordination
❌ **State Sync**: Potential for stale data

---

## APPROACH 2: Shared Database (Data-Level Integration)

### Core Concept

AI agent writes signals to shared database, trading system reads directly. No API layer, tighter coupling at data level.

### Architecture

```
┌──────────────────────────────────────┐
│   AI Investment Agent System         │
│                                      │
│  ┌──────────┐                        │
│  │  Agents  │                        │
│  └────┬─────┘                        │
│       │                              │
│       ▼                              │
│  ┌──────────────────────────┐       │
│  │  Signal Writer           │       │
│  │  (Batch Job)             │       │
│  └────┬─────────────────────┘       │
└───────┼──────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────┐
│   Shared PostgreSQL Database           │
│                                        │
│  Tables:                               │
│  - fundamental_signals                 │
│  - agent_analysis_history              │
│  - factor_scores                       │
│  - risk_metrics                        │
└────────┬───────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│   Trading System                       │
│                                        │
│  ┌──────────────────────┐             │
│  │  Signal Reader       │             │
│  │  (Real-time Query)   │             │
│  └──────┬───────────────┘             │
│         ▼                              │
│  ┌──────────────────────┐             │
│  │  Trading Logic       │             │
│  └──────────────────────┘             │
└────────────────────────────────────────┘
```

### Implementation

#### 1. Database Schema

```sql
-- fundamental_signals table
CREATE TABLE fundamental_signals (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    score DECIMAL(4, 2) NOT NULL,  -- 0.00 to 10.00
    recommendation VARCHAR(10) NOT NULL,  -- BUY/HOLD/SELL
    confidence DECIMAL(3, 2),  -- 0.00 to 1.00
    fair_value DECIMAL(12, 2),
    current_price DECIMAL(12, 2),
    upside_pct DECIMAL(6, 2),
    risk_level VARCHAR(10),  -- LOW/MEDIUM/HIGH

    -- Key metrics for quick filtering
    pe_ratio DECIMAL(8, 2),
    pb_ratio DECIMAL(8, 2),
    roe_pct DECIMAL(5, 2),
    debt_equity DECIMAL(6, 2),
    revenue_growth_pct DECIMAL(6, 2),

    -- Ownership (Indian specific)
    promoter_holding_pct DECIMAL(5, 2),
    fii_holding_pct DECIMAL(5, 2),
    pledging_pct DECIMAL(5, 2),

    -- Metadata
    sector VARCHAR(50),
    market_cap BIGINT,
    analysis_date TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_score CHECK (score >= 0 AND score <= 10),
    CONSTRAINT valid_recommendation CHECK (recommendation IN ('BUY', 'HOLD', 'SELL')),
    CONSTRAINT unique_ticker_date UNIQUE (ticker, analysis_date)
);

-- Indexes for fast queries
CREATE INDEX idx_signals_ticker ON fundamental_signals(ticker);
CREATE INDEX idx_signals_date ON fundamental_signals(analysis_date DESC);
CREATE INDEX idx_signals_score ON fundamental_signals(score DESC);
CREATE INDEX idx_signals_recommendation ON fundamental_signals(recommendation);
CREATE INDEX idx_signals_sector ON fundamental_signals(sector);

-- Factor scores table
CREATE TABLE factor_scores (
    id SERIAL PRIMARY KEY,
    signal_id INTEGER REFERENCES fundamental_signals(id),
    factor_name VARCHAR(50) NOT NULL,
    factor_value DECIMAL(10, 4),
    factor_zscore DECIMAL(6, 3),
    factor_percentile DECIMAL(5, 2),

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_factor_scores_signal ON factor_scores(signal_id);
CREATE INDEX idx_factor_scores_name ON factor_scores(factor_name);

-- Agent reasoning (for audit trail)
CREATE TABLE agent_reasoning (
    id SERIAL PRIMARY KEY,
    signal_id INTEGER REFERENCES fundamental_signals(id),
    agent_name VARCHAR(50) NOT NULL,
    agent_conclusion VARCHAR(50),
    confidence DECIMAL(3, 2),
    reasoning_text TEXT,
    data_sources JSONB,
    processing_time_ms INTEGER,

    created_at TIMESTAMP DEFAULT NOW()
);
```

#### 2. Signal Writer (Agent Side)

```python
# agent_system/signal_writer.py

import asyncpg
from typing import List, Dict
from datetime import datetime

class SignalWriter:
    """
    Writes agent analysis results to shared database.
    """

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.pool = None

    async def initialize(self):
        """Create database connection pool."""
        self.pool = await asyncpg.create_pool(
            self.db_url,
            min_size=5,
            max_size=20
        )

    async def write_signal(self, analysis: dict):
        """
        Write analysis result as signal.
        """
        async with self.pool.acquire() as conn:
            # Insert signal
            signal_id = await conn.fetchval(
                """
                INSERT INTO fundamental_signals (
                    ticker, score, recommendation, confidence,
                    fair_value, current_price, upside_pct, risk_level,
                    pe_ratio, pb_ratio, roe_pct, debt_equity, revenue_growth_pct,
                    promoter_holding_pct, fii_holding_pct, pledging_pct,
                    sector, market_cap, analysis_date
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                    $14, $15, $16, $17, $18, $19
                )
                ON CONFLICT (ticker, analysis_date)
                DO UPDATE SET
                    score = EXCLUDED.score,
                    recommendation = EXCLUDED.recommendation,
                    confidence = EXCLUDED.confidence,
                    fair_value = EXCLUDED.fair_value,
                    updated_at = NOW()
                RETURNING id
                """,
                analysis['ticker'],
                analysis['score'],
                analysis['recommendation'],
                analysis['confidence'],
                analysis['fair_value'],
                analysis['current_price'],
                analysis['upside_pct'],
                analysis['risk_level'],
                analysis['fundamentals']['pe'],
                analysis['fundamentals']['pb'],
                analysis['fundamentals']['roe'],
                analysis['fundamentals']['debt_equity'],
                analysis['fundamentals']['revenue_growth'],
                analysis['ownership']['promoter'],
                analysis['ownership']['fii'],
                analysis['ownership']['pledging'],
                analysis['sector'],
                analysis['market_cap'],
                datetime.now()
            )

            # Write factor scores
            if analysis.get('factors'):
                await self._write_factors(conn, signal_id, analysis['factors'])

            # Write agent reasoning
            if analysis.get('agent_workflow'):
                await self._write_reasoning(conn, signal_id, analysis['agent_workflow'])

        return signal_id

    async def batch_write_signals(self, analyses: List[dict]):
        """
        Efficiently write multiple signals in batch.
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                for analysis in analyses:
                    await self.write_signal(analysis)

    async def _write_factors(self, conn, signal_id: int, factors: dict):
        """Write factor scores."""
        await conn.executemany(
            """
            INSERT INTO factor_scores (
                signal_id, factor_name, factor_value,
                factor_zscore, factor_percentile
            ) VALUES ($1, $2, $3, $4, $5)
            """,
            [
                (signal_id, name, data['value'], data['zscore'], data['percentile'])
                for name, data in factors.items()
            ]
        )
```

#### 3. Signal Reader (Trading System Side)

```python
# trading_system/signal_reader.py

import asyncpg
from typing import List, Optional
from datetime import datetime, timedelta

class SignalReader:
    """
    Reads fundamental signals from shared database.
    """

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.pool = None

    async def initialize(self):
        """Create read-only connection pool."""
        self.pool = await asyncpg.create_pool(
            self.db_url,
            min_size=10,
            max_size=50,
            command_timeout=5  # Fast timeout for trading
        )

    async def get_universe(
        self,
        min_score: float = 6.5,
        max_age_hours: int = 24,
        sectors: Optional[List[str]] = None
    ) -> List[dict]:
        """
        Get trading universe from fundamental signals.
        """
        query = """
            SELECT
                ticker,
                score,
                recommendation,
                confidence,
                fair_value,
                current_price,
                upside_pct,
                risk_level,
                sector,
                analysis_date
            FROM fundamental_signals
            WHERE score >= $1
                AND recommendation = 'BUY'
                AND analysis_date > NOW() - INTERVAL '%s hours'
        """

        params = [min_score]

        if sectors:
            query += " AND sector = ANY($2)"
            params.append(sectors)

        query += " ORDER BY score DESC, upside_pct DESC"

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query % max_age_hours, *params)

        return [dict(row) for row in rows]

    async def get_signal(self, ticker: str) -> Optional[dict]:
        """Get latest signal for ticker."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM fundamental_signals
                WHERE ticker = $1
                ORDER BY analysis_date DESC
                LIMIT 1
                """,
                ticker
            )

        return dict(row) if row else None

    async def get_signals_batch(self, tickers: List[str]) -> dict:
        """
        Get signals for multiple tickers efficiently.

        Returns dict mapping ticker to signal.
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (ticker)
                        *
                    FROM fundamental_signals
                    WHERE ticker = ANY($1)
                    ORDER BY ticker, analysis_date DESC
                )
                SELECT * FROM latest
                """,
                tickers
            )

        return {row['ticker']: dict(row) for row in rows}

    async def get_factor_scores(self, ticker: str) -> dict:
        """
        Get all factor scores for a ticker.

        Useful for custom factor analysis in trading system.
        """
        async with self.pool.acquire() as conn:
            # Get latest signal
            signal = await conn.fetchrow(
                """
                SELECT id FROM fundamental_signals
                WHERE ticker = $1
                ORDER BY analysis_date DESC
                LIMIT 1
                """,
                ticker
            )

            if not signal:
                return {}

            # Get factors for this signal
            rows = await conn.fetch(
                """
                SELECT
                    factor_name,
                    factor_value,
                    factor_zscore,
                    factor_percentile
                FROM factor_scores
                WHERE signal_id = $1
                """,
                signal['id']
            )

        return {
            row['factor_name']: {
                'value': row['factor_value'],
                'zscore': row['factor_zscore'],
                'percentile': row['factor_percentile']
            }
            for row in rows
        }
```

### Strengths

✅ **Performance**: Direct DB queries, no HTTP overhead
✅ **Reliability**: No API availability dependency
✅ **Flexibility**: Trading system can query any way it wants
✅ **Batch Operations**: Efficient bulk queries
✅ **History**: Full signal history in database
✅ **Atomic**: Database transactions ensure consistency

### Weaknesses

❌ **Tight Coupling**: Schema changes impact both systems
❌ **Database Load**: High-frequency queries can impact agent
❌ **Versioning**: Schema migrations need coordination
❌ **Security**: Both systems need DB credentials
❌ **No Business Logic**: Just data, trading system must interpret

---

## APPROACH 3: Message Queue (Event-Driven)

### Core Concept

AI agent publishes signal events to message queue (Kafka/RabbitMQ), trading system consumes events and maintains local signal cache.

### Architecture

```
┌─────────────────────────────────┐
│  AI Investment Agent System     │
│                                 │
│  ┌──────────┐                   │
│  │  Agents  │                   │
│  └────┬─────┘                   │
│       │                         │
│       ▼                         │
│  ┌──────────────────┐           │
│  │  Event Publisher │           │
│  └────┬─────────────┘           │
└───────┼─────────────────────────┘
        │
        ▼
┌────────────────────────────────────────┐
│   Apache Kafka / RabbitMQ              │
│                                        │
│   Topics:                              │
│   - fundamental.signals.new            │
│   - fundamental.signals.updated        │
│   - fundamental.alerts                 │
└────────┬───────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│   Trading System                       │
│                                        │
│  ┌──────────────────────┐             │
│  │  Event Consumer      │             │
│  └──────┬───────────────┘             │
│         ▼                              │
│  ┌──────────────────────┐             │
│  │  Local Signal Cache  │             │
│  │  (Redis/In-Memory)   │             │
│  └──────┬───────────────┘             │
│         ▼                              │
│  ┌──────────────────────┐             │
│  │  Trading Logic       │             │
│  └──────────────────────┘             │
└────────────────────────────────────────┘
```

### Implementation

#### 1. Event Schema

```json
{
  "event_type": "signal.new",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-12-07T10:30:00Z",
  "version": "1.0",

  "payload": {
    "ticker": "RELIANCE.NS",
    "score": 8.5,
    "recommendation": "BUY",
    "confidence": 0.85,

    "valuation": {
      "fair_value": 2850.00,
      "current_price": 2450.00,
      "upside_pct": 16.33
    },

    "fundamentals": {
      "pe": 22.5,
      "pb": 2.1,
      "roe": 15.8,
      "debt_equity": 0.45,
      "revenue_growth": 18.2
    },

    "risk": {
      "level": "MEDIUM",
      "factors": [
        "High valuation vs historical average",
        "Sector competition increasing"
      ]
    },

    "factors": {
      "quality_score": 8.2,
      "growth_score": 7.8,
      "value_score": 6.5
    },

    "metadata": {
      "analysis_depth": "deep",
      "agent_version": "3.1.0",
      "data_sources": ["FMP", "Trendlyne", "Moneycontrol"]
    }
  }
}
```

#### 2. Event Publisher (Agent Side)

```python
# agent_system/event_publisher.py

from confluent_kafka import Producer
import json
import uuid
from datetime import datetime

class SignalEventPublisher:
    """
    Publish signal events to Kafka.
    """

    def __init__(self, kafka_config: dict):
        self.producer = Producer(kafka_config)
        self.topic_signals = "fundamental.signals"
        self.topic_alerts = "fundamental.alerts"

    def publish_signal(self, analysis: dict, event_type: str = "signal.new"):
        """
        Publish signal event.

        Args:
            analysis: Agent analysis result
            event_type: signal.new or signal.updated
        """
        event = {
            "event_type": event_type,
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "version": "1.0",
            "payload": {
                "ticker": analysis['ticker'],
                "score": analysis['score'],
                "recommendation": analysis['recommendation'],
                "confidence": analysis['confidence'],
                "valuation": {
                    "fair_value": analysis['fair_value'],
                    "current_price": analysis['current_price'],
                    "upside_pct": analysis['upside']
                },
                "fundamentals": analysis['fundamentals'],
                "risk": {
                    "level": analysis['risk_level'],
                    "factors": analysis['risk_factors']
                },
                "factors": analysis.get('factor_scores', {}),
                "metadata": {
                    "analysis_depth": analysis.get('depth', 'standard'),
                    "agent_version": "3.1.0",
                    "data_sources": analysis.get('sources_used', [])
                }
            }
        }

        # Publish to Kafka
        self.producer.produce(
            topic=self.topic_signals,
            key=analysis['ticker'].encode('utf-8'),
            value=json.dumps(event).encode('utf-8'),
            callback=self._delivery_callback
        )

        self.producer.poll(0)  # Trigger delivery reports

    def publish_alert(self, ticker: str, alert_type: str, message: str):
        """
        Publish alert event (e.g., fundamental downgrade).
        """
        event = {
            "event_type": "alert",
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": {
                "ticker": ticker,
                "alert_type": alert_type,
                "message": message,
                "severity": self._get_severity(alert_type)
            }
        }

        self.producer.produce(
            topic=self.topic_alerts,
            key=ticker.encode('utf-8'),
            value=json.dumps(event).encode('utf-8')
        )

        self.producer.poll(0)

    def _delivery_callback(self, err, msg):
        """Kafka delivery callback."""
        if err:
            logger.error(f"Event delivery failed: {err}")
        else:
            logger.debug(f"Event delivered to {msg.topic()} [{msg.partition()}]")

    def flush(self):
        """Wait for all messages to be delivered."""
        self.producer.flush()
```

#### 3. Event Consumer (Trading System Side)

```python
# trading_system/signal_consumer.py

from confluent_kafka import Consumer, KafkaError
import json
import redis
from typing import Callable

class SignalEventConsumer:
    """
    Consume signal events and maintain local cache.
    """

    def __init__(self, kafka_config: dict, redis_url: str):
        self.consumer = Consumer(kafka_config)
        self.redis = redis.from_url(redis_url)

        # Subscribe to topics
        self.consumer.subscribe([
            'fundamental.signals',
            'fundamental.alerts'
        ])

        # Callbacks
        self.on_signal_callback = None
        self.on_alert_callback = None

    def on_signal(self, callback: Callable):
        """Register callback for signal events."""
        self.on_signal_callback = callback

    def on_alert(self, callback: Callable):
        """Register callback for alert events."""
        self.on_alert_callback = callback

    def start(self):
        """
        Start consuming events (blocking).

        Run this in background thread/process.
        """
        try:
            while True:
                msg = self.consumer.poll(timeout=1.0)

                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        logger.error(f"Consumer error: {msg.error()}")
                        break

                # Process event
                self._process_event(msg)

        except KeyboardInterrupt:
            pass
        finally:
            self.consumer.close()

    def _process_event(self, msg):
        """Process incoming event."""
        try:
            event = json.loads(msg.value().decode('utf-8'))

            if event['event_type'].startswith('signal.'):
                self._handle_signal_event(event)
            elif event['event_type'] == 'alert':
                self._handle_alert_event(event)

        except Exception as e:
            logger.error(f"Error processing event: {e}")

    def _handle_signal_event(self, event: dict):
        """
        Handle signal event.

        1. Update Redis cache
        2. Trigger callback for trading logic
        """
        payload = event['payload']
        ticker = payload['ticker']

        # Store in Redis with 24h TTL
        self.redis.setex(
            f"signal:{ticker}",
            86400,  # 24 hours
            json.dumps(payload)
        )

        # Update index (for fast universe queries)
        if payload['recommendation'] == 'BUY':
            self.redis.zadd(
                'signals:buy',
                {ticker: payload['score']}
            )
        else:
            self.redis.zrem('signals:buy', ticker)

        # Trigger callback
        if self.on_signal_callback:
            self.on_signal_callback(payload)

        logger.info(f"Signal updated for {ticker}: {payload['recommendation']} (score: {payload['score']})")

    def _handle_alert_event(self, event: dict):
        """Handle alert event."""
        payload = event['payload']

        # Trigger callback
        if self.on_alert_callback:
            self.on_alert_callback(payload)

        logger.warning(f"Alert for {payload['ticker']}: {payload['message']}")

    def get_signal(self, ticker: str) -> dict:
        """
        Get signal from local cache (fast).
        """
        data = self.redis.get(f"signal:{ticker}")
        return json.loads(data) if data else None

    def get_universe(self, min_score: float = 6.0) -> list:
        """
        Get tickers passing fundamental filter (fast).
        """
        # Query sorted set by score
        tickers = self.redis.zrangebyscore(
            'signals:buy',
            min_score,
            10.0,
            withscores=True
        )

        return [
            {
                'ticker': ticker.decode('utf-8'),
                'score': score
            }
            for ticker, score in tickers
        ]
```

### Strengths

✅ **Asynchronous**: Non-blocking, event-driven
✅ **Scalable**: Kafka handles millions of messages/sec
✅ **Decoupled**: Systems completely independent
✅ **Replay**: Can replay event history
✅ **Multiple Consumers**: Many systems can consume same events
✅ **Guaranteed Delivery**: Kafka ensures no message loss
✅ **Fast Queries**: Local cache (Redis) = microsecond latency

### Weaknesses

❌ **Complexity**: Kafka/RabbitMQ infrastructure needed
❌ **Eventual Consistency**: Slight delay between publish and consume
❌ **Operational Overhead**: Monitoring Kafka, managing topics
❌ **Debugging**: Event-driven harder to debug than request/response

---

## CRITICAL EVALUATION & RECOMMENDATION

### Comparison Matrix

| Criterion | API-Based | Shared Database | Message Queue |
|-----------|-----------|-----------------|---------------|
| **Latency** | ⭐⭐⭐ 50-200ms | ⭐⭐⭐⭐⭐ 1-10ms | ⭐⭐⭐⭐ 5-50ms |
| **Coupling** | ⭐⭐⭐⭐⭐ Loose | ⭐⭐ Tight | ⭐⭐⭐⭐⭐ Loose |
| **Complexity** | ⭐⭐⭐⭐ Simple | ⭐⭐⭐⭐⭐ Simple | ⭐⭐ Complex |
| **Scalability** | ⭐⭐⭐⭐ Good | ⭐⭐⭐ Moderate | ⭐⭐⭐⭐⭐ Excellent |
| **Reliability** | ⭐⭐⭐ Dependent on API | ⭐⭐⭐⭐ Database SLA | ⭐⭐⭐⭐⭐ Kafka guarantees |
| **Real-time** | ⭐⭐⭐⭐ WebSocket | ⭐⭐ Polling | ⭐⭐⭐⭐⭐ Events |
| **Debugging** | ⭐⭐⭐⭐⭐ Easy (logs) | ⭐⭐⭐⭐ SQL queries | ⭐⭐⭐ Event tracking |
| **Versioning** | ⭐⭐⭐⭐⭐ API versions | ⭐⭐ Schema changes | ⭐⭐⭐⭐ Event schemas |

### Use Case Fit

**Approach 1 (API)**: Best for
- Prototyping/MVP
- Trading system in different language
- Simple integration needs
- Limited technical resources

**Approach 2 (Database)**: Best for
- Python-only ecosystem
- Low latency critical
- Simple deployment
- Small team

**Approach 3 (Message Queue)**: Best for
- Enterprise-scale systems
- Multiple consumers (risk, compliance, reporting)
- Event sourcing architecture
- High reliability requirements

---

## RECOMMENDED STRATEGY: Hybrid Approach

### Implementation

**Phase 1 (MVP)**: API-Based
- Start with FastAPI signals endpoint
- Trading system queries before each trade
- Simple caching layer
- **Timeline**: 2-3 weeks
- **Cost**: $10k-15k

**Phase 2 (Production)**: Add Message Queue
- Introduce Kafka for real-time signals
- Trading system consumes events, maintains local cache
- Keep API for backward compatibility
- **Timeline**: 4-6 weeks
- **Cost**: $30k-40k

**Phase 3 (Scale)**: Optimize with Shared DB
- Add direct DB access for backtesting/analytics
- Event sourcing into database
- API remains for external consumers
- **Timeline**: 2-3 weeks
- **Cost**: $15k-20k

**Total Investment**: $55k-75k over 12-16 weeks

---

## INTEGRATION WORKFLOW

### Daily Universe Refresh

```python
# Run every morning before market open (9:00 AM IST)

async def daily_universe_refresh():
    """
    Refresh trading universe with latest fundamental signals.
    """
    # 1. Get latest signals from agent system
    universe = await fundamental_filter.get_trading_universe(
        min_score=6.5,
        max_positions=50,
        sector_diversification=True
    )

    # 2. Validate each ticker
    approved_tickers = []
    for ticker in universe:
        validation = await fundamental_filter.validate_ticker(ticker)
        if validation['approved']:
            approved_tickers.append(ticker)

    # 3. Update trading system universe
    await trading_system.set_universe(approved_tickers)

    # 4. Calculate position sizes
    allocations = {}
    portfolio_value = await portfolio.get_total_value()

    for ticker in approved_tickers:
        size = await fundamental_filter.get_position_sizing(ticker, portfolio_value)
        allocations[ticker] = size

    await trading_system.set_allocations(allocations)

    logger.info(f"Universe refreshed: {len(approved_tickers)} tickers approved")
```

### Pre-Trade Validation

```python
# Before entering position

async def validate_trade(ticker: str, signal_type: str) -> bool:
    """
    Validate trade against fundamental filter.

    Returns True if trade should proceed.
    """
    # Get latest fundamental signal
    signal = await fundamental_filter.get_signal(ticker)

    if not signal:
        logger.warning(f"No fundamental signal for {ticker}, blocking trade")
        return False

    # Check recommendation matches trade type
    if signal_type == 'BUY':
        if signal['recommendation'] != 'BUY':
            logger.warning(f"{ticker} not recommended for BUY (signal: {signal['recommendation']})")
            return False

        if signal['score'] < 6.0:
            logger.warning(f"{ticker} score too low ({signal['score']})")
            return False

    elif signal_type == 'SELL':
        # Always allow exits
        return True

    # Check signal age
    signal_age = datetime.now() - signal['analysis_date']
    if signal_age.total_seconds() > 86400:  # 24 hours
        logger.warning(f"{ticker} signal stale ({signal_age.total_seconds() / 3600:.1f} hours old)")
        return False

    logger.info(f"{ticker} passed fundamental filter (score: {signal['score']}, rec: {signal['recommendation']})")
    return True
```

### Position Monitoring

```python
# Run every hour during market hours

async def monitor_positions():
    """
    Check existing positions against current fundamentals.
    """
    positions = await portfolio.get_positions()

    actions = await fundamental_filter.monitor_positions(positions)

    for action in actions:
        if action['action'] == 'EXIT':
            # Fundamental downgrade, exit immediately
            await trading_system.close_position(
                ticker=action['ticker'],
                reason=action['reason'],
                urgency='high'
            )

        elif action['action'] == 'REDUCE':
            # Reduce position size
            current_allocation = action['current_allocation']
            target_allocation = action['recommended_allocation']

            if target_allocation < current_allocation:
                reduce_pct = 1 - (target_allocation / current_allocation)
                await trading_system.reduce_position(
                    ticker=action['ticker'],
                    reduce_pct=reduce_pct,
                    reason=action['reason']
                )

        elif action['action'] == 'PARTIAL_EXIT':
            # Take profits
            await trading_system.reduce_position(
                ticker=action['ticker'],
                reduce_pct=0.50,  # Sell half
                reason='Take profits (50%+ gain)'
            )
```

---

## CONCLUSION

### Key Recommendations

1. **Start Simple**: Begin with API-based integration (Phase 1)
2. **Validate**: Run in parallel with existing system for 3 months
3. **Measure**: Track performance improvement vs pure technical signals
4. **Evolve**: Add message queue when scaling to multiple consumers
5. **Monitor**: Continuous validation of signal quality and staleness

### Success Metrics

Track these KPIs to validate integration:

- **Signal Coverage**: % of trades with valid fundamental signals (target: >95%)
- **Signal Accuracy**: % of BUY signals with positive returns @ 3M/6M (target: >60%)
- **Avoid Rate**: % of prevented losses by blocking fundamentally weak stocks (measure drawdown avoided)
- **Alpha Generation**: Excess returns vs technical-only strategy (target: +2-3% annually)
- **Sharpe Improvement**: Risk-adjusted return improvement (target: +0.3-0.5)

### Risk Mitigation

- **Fallback**: Always have bypass mode if agent system unavailable
- **Staleness Detection**: Block trades if signals >24 hours old
- **Gradual Rollout**: Start with 10% of capital, scale after validation
- **Human Override**: Allow manual overrides with audit trail

---

**Document Version**: 1.0
**Author**: AI Investment Agent Development Team
**Review Date**: 2025-12-07
