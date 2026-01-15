"""Rate limiting utilities for external API calls."""

import asyncio
import time
from collections import deque
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter for API calls.

    Ensures compliance with external API rate limits.

    Example:
        ```python
        limiter = RateLimiter(calls_per_second=3)

        async with limiter:
            # Make API call
            response = await client.get(url)
        ```
    """

    def __init__(
        self,
        calls_per_second: float,
        burst: Optional[int] = None,
        name: str = "RateLimiter"
    ):
        """
        Initialize rate limiter.

        Args:
            calls_per_second: Maximum calls per second
            burst: Maximum burst size (default: calls_per_second * 2)
            name: Limiter name for logging
        """
        self.calls_per_second = calls_per_second
        self.burst = burst or int(calls_per_second * 2)
        self.name = name

        # Token bucket
        self.tokens = float(self.burst)
        self.last_update = time.monotonic()
        self.lock = asyncio.Lock()

        # Statistics
        self.total_calls = 0
        self.total_wait_time = 0.0

        logger.info(
            f"Rate limiter '{name}' initialized: "
            f"{calls_per_second} calls/sec, burst={self.burst}"
        )

    async def acquire(self) -> None:
        """Acquire permission to make an API call."""
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_update

            # Refill tokens based on elapsed time
            self.tokens = min(
                self.burst,
                self.tokens + elapsed * self.calls_per_second
            )
            self.last_update = now

            # Wait if no tokens available
            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.calls_per_second
                logger.debug(
                    f"{self.name}: Rate limit reached, waiting {wait_time:.2f}s"
                )
                await asyncio.sleep(wait_time)

                self.tokens = 1
                self.last_update = time.monotonic()
                self.total_wait_time += wait_time

            # Consume token
            self.tokens -= 1
            self.total_calls += 1

    async def __aenter__(self):
        """Context manager entry."""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        pass

    def get_stats(self) -> dict:
        """
        Get rate limiter statistics.

        Returns:
            dict: Statistics including total calls and wait time
        """
        return {
            "name": self.name,
            "total_calls": self.total_calls,
            "total_wait_time": self.total_wait_time,
            "avg_wait_time": (
                self.total_wait_time / self.total_calls
                if self.total_calls > 0
                else 0
            ),
            "calls_per_second": self.calls_per_second,
            "current_tokens": self.tokens,
        }


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter for more precise control.

    Tracks actual timestamps of calls within a time window.
    """

    def __init__(
        self,
        max_calls: int,
        window_seconds: float,
        name: str = "SlidingWindowRateLimiter"
    ):
        """
        Initialize sliding window rate limiter.

        Args:
            max_calls: Maximum calls within window
            window_seconds: Time window in seconds
            name: Limiter name for logging
        """
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.name = name

        self.calls: deque = deque()
        self.lock = asyncio.Lock()

        logger.info(
            f"Sliding window rate limiter '{name}' initialized: "
            f"{max_calls} calls per {window_seconds}s"
        )

    async def acquire(self) -> None:
        """Acquire permission to make an API call."""
        async with self.lock:
            now = time.monotonic()

            # Remove calls outside window
            while self.calls and self.calls[0] < now - self.window_seconds:
                self.calls.popleft()

            # Check if we can make a call
            if len(self.calls) >= self.max_calls:
                # Wait until oldest call expires
                wait_time = self.calls[0] + self.window_seconds - now
                if wait_time > 0:
                    logger.debug(
                        f"{self.name}: Rate limit reached, "
                        f"waiting {wait_time:.2f}s"
                    )
                    await asyncio.sleep(wait_time)

                    # Remove expired calls
                    now = time.monotonic()
                    while self.calls and self.calls[0] < now - self.window_seconds:
                        self.calls.popleft()

            # Record call
            self.calls.append(time.monotonic())

    async def __aenter__(self):
        """Context manager entry."""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        pass
