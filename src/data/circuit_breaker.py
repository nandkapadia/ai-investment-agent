"""
Circuit Breaker Pattern for External API Failures

Prevents cascading failures by failing fast when external services are down.
Implements OPEN/CLOSED/HALF_OPEN states per service to minimize wasted retries.
"""

import asyncio
from enum import Enum
from datetime import datetime, timedelta
from typing import Dict, Callable, Any, Optional
import structlog

logger = structlog.get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Failing, reject requests immediately
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker for external API calls.

    Prevents cascading failures by tracking failure rates per service
    and failing fast when a service is determined to be down.

    States:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: Service is failing, reject requests immediately (fail fast)
    - HALF_OPEN: After timeout, allow test requests to check recovery

    Usage:
        breaker = CircuitBreaker()
        result = await breaker.call('fmp', fetch_fmp_data, ticker)
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        half_open_max_calls: int = 3
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of consecutive failures before opening circuit
            timeout_seconds: How long to wait before transitioning from OPEN to HALF_OPEN
            half_open_max_calls: Max requests to allow in HALF_OPEN state before decision
        """
        self.failure_threshold = failure_threshold
        self.timeout = timedelta(seconds=timeout_seconds)
        self.half_open_max_calls = half_open_max_calls

        # State tracking per service
        self.failure_count: Dict[str, int] = {}
        self.success_count: Dict[str, int] = {}
        self.state: Dict[str, CircuitState] = {}
        self.last_failure_time: Dict[str, datetime] = {}
        self.half_open_call_count: Dict[str, int] = {}

    def get_state(self, source: str) -> CircuitState:
        """Get current state for a service."""
        return self.state.get(source, CircuitState.CLOSED)

    async def call(
        self,
        source: str,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            source: Service identifier (e.g., 'fmp', 'moneycontrol', 'yfinance')
            func: Async function to execute
            *args, **kwargs: Arguments to pass to func

        Returns:
            Result from func if successful

        Raises:
            CircuitBreakerOpenError: If circuit is OPEN (service is down)
            Exception: Original exception if func fails and circuit is CLOSED/HALF_OPEN
        """
        current_state = self.get_state(source)

        # If circuit is OPEN, check if timeout elapsed
        if current_state == CircuitState.OPEN:
            if self._should_attempt_reset(source):
                logger.info("circuit_breaker_transition", source=source,
                           from_state="OPEN", to_state="HALF_OPEN")
                self.state[source] = CircuitState.HALF_OPEN
                self.half_open_call_count[source] = 0
            else:
                # Still in timeout period, fail fast
                time_remaining = self._get_remaining_timeout(source)
                logger.warning("circuit_breaker_blocked", source=source,
                             state="OPEN", time_remaining_seconds=time_remaining)
                raise CircuitBreakerOpenError(
                    f"Circuit breaker OPEN for {source}. "
                    f"Retry in {time_remaining:.0f}s"
                )

        # CLOSED or HALF_OPEN - attempt the call
        try:
            result = await func(*args, **kwargs)

            # Success - handle state transitions
            self._record_success(source)
            return result

        except Exception as e:
            # Failure - record and potentially open circuit
            self._record_failure(source, e)
            raise

    def _should_attempt_reset(self, source: str) -> bool:
        """Check if enough time has passed to attempt reset from OPEN to HALF_OPEN."""
        if source not in self.last_failure_time:
            return True

        elapsed = datetime.now() - self.last_failure_time[source]
        return elapsed >= self.timeout

    def _get_remaining_timeout(self, source: str) -> float:
        """Get remaining timeout in seconds before circuit can transition to HALF_OPEN."""
        if source not in self.last_failure_time:
            return 0.0

        elapsed = datetime.now() - self.last_failure_time[source]
        remaining = self.timeout - elapsed
        return max(0.0, remaining.total_seconds())

    def _record_success(self, source: str):
        """Record successful call and update circuit state."""
        current_state = self.get_state(source)

        if current_state == CircuitState.HALF_OPEN:
            # Track successes in HALF_OPEN state
            self.half_open_call_count[source] = self.half_open_call_count.get(source, 0) + 1

            # If we've had enough successful test calls, close the circuit
            if self.half_open_call_count[source] >= self.half_open_max_calls:
                logger.info("circuit_breaker_transition", source=source,
                           from_state="HALF_OPEN", to_state="CLOSED",
                           test_successes=self.half_open_call_count[source])
                self.state[source] = CircuitState.CLOSED
                self.failure_count[source] = 0
                self.half_open_call_count[source] = 0
        else:
            # In CLOSED state, reset failure count on success
            self.failure_count[source] = 0

    def _record_failure(self, source: str, exception: Exception):
        """Record failed call and potentially open circuit."""
        self.failure_count[source] = self.failure_count.get(source, 0) + 1
        self.last_failure_time[source] = datetime.now()

        current_state = self.get_state(source)

        if current_state == CircuitState.HALF_OPEN:
            # Single failure in HALF_OPEN reopens the circuit immediately
            logger.error("circuit_breaker_transition", source=source,
                        from_state="HALF_OPEN", to_state="OPEN",
                        error=str(exception)[:200])
            self.state[source] = CircuitState.OPEN
            self.failure_count[source] = self.failure_threshold
            self.half_open_call_count[source] = 0

        elif self.failure_count[source] >= self.failure_threshold:
            # Threshold exceeded in CLOSED state - open circuit
            logger.error("circuit_breaker_opened", source=source,
                        failures=self.failure_count[source],
                        threshold=self.failure_threshold,
                        error=str(exception)[:200])
            self.state[source] = CircuitState.OPEN

    def reset(self, source: str):
        """Manually reset circuit breaker for a service (admin function)."""
        logger.info("circuit_breaker_manual_reset", source=source)
        self.failure_count[source] = 0
        self.success_count[source] = 0
        self.state[source] = CircuitState.CLOSED
        self.half_open_call_count[source] = 0

    def get_stats(self, source: str) -> Dict[str, Any]:
        """Get statistics for a service."""
        return {
            'state': self.get_state(source).value,
            'failure_count': self.failure_count.get(source, 0),
            'success_count': self.success_count.get(source, 0),
            'last_failure': self.last_failure_time.get(source),
            'time_until_half_open': self._get_remaining_timeout(source) if self.get_state(source) == CircuitState.OPEN else 0
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is OPEN and request is rejected."""
    pass


# Global circuit breaker instance
_circuit_breaker: Optional[CircuitBreaker] = None


def get_circuit_breaker() -> CircuitBreaker:
    """Get global circuit breaker instance."""
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker()
    return _circuit_breaker
