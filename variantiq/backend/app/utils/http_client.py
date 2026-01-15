"""HTTP client utilities with retry logic and error handling."""

import asyncio
from typing import Any, Dict, Optional

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.logging import get_logger
from app.utils.rate_limiter import RateLimiter

logger = get_logger(__name__)


class HTTPClient:
    """
    HTTP client with retry logic, rate limiting, and error handling.

    Features:
    - Automatic retries with exponential backoff
    - Rate limiting
    - Timeout handling
    - Comprehensive error logging

    Example:
        ```python
        client = HTTPClient(
            rate_limiter=RateLimiter(calls_per_second=3),
            name="ClinVar"
        )

        async with client:
            data = await client.get("https://api.example.com/data")
        ```
    """

    def __init__(
        self,
        rate_limiter: Optional[RateLimiter] = None,
        timeout: int = 30,
        max_retries: int = 3,
        name: str = "HTTPClient",
        headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize HTTP client.

        Args:
            rate_limiter: Rate limiter for API calls
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
            name: Client name for logging
            headers: Default headers for requests
        """
        self.rate_limiter = rate_limiter
        self.timeout = timeout
        self.max_retries = max_retries
        self.name = name
        self.headers = headers or {}

        self.client: Optional[httpx.AsyncClient] = None

        # Statistics
        self.total_requests = 0
        self.total_errors = 0
        self.total_retries = 0

    async def __aenter__(self):
        """Context manager entry."""
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            headers=self.headers,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.client:
            await self.client.aclose()

    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Make GET request with retry logic.

        Args:
            url: Request URL
            params: Query parameters
            headers: Additional headers

        Returns:
            Response data (JSON)

        Raises:
            httpx.HTTPError: On request failure after retries
        """
        return await self._request("GET", url, params=params, headers=headers)

    async def post(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Make POST request with retry logic.

        Args:
            url: Request URL
            data: Form data
            json: JSON data
            headers: Additional headers

        Returns:
            Response data (JSON)

        Raises:
            httpx.HTTPError: On request failure after retries
        """
        return await self._request(
            "POST",
            url,
            data=data,
            json=json,
            headers=headers
        )

    async def _request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> Any:
        """
        Make HTTP request with retry logic and rate limiting.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional request arguments

        Returns:
            Response data

        Raises:
            httpx.HTTPError: On request failure after retries
        """
        if not self.client:
            raise RuntimeError(
                "HTTPClient must be used as context manager (async with)"
            )

        # Merge headers
        request_headers = {**self.headers, **kwargs.pop("headers", {})}

        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.RemoteProtocolError,
            )),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            stop=stop_after_attempt(self.max_retries),
            reraise=True,
        ):
            with attempt:
                # Apply rate limiting
                if self.rate_limiter:
                    await self.rate_limiter.acquire()

                self.total_requests += 1

                try:
                    logger.debug(f"{self.name}: {method} {url}")

                    response = await self.client.request(
                        method,
                        url,
                        headers=request_headers,
                        **kwargs
                    )

                    response.raise_for_status()

                    # Try to parse as JSON
                    try:
                        return response.json()
                    except Exception:
                        return response.text

                except httpx.HTTPStatusError as e:
                    self.total_errors += 1
                    logger.error(
                        f"{self.name}: HTTP {e.response.status_code} "
                        f"for {method} {url}: {e}"
                    )
                    raise

                except (
                    httpx.TimeoutException,
                    httpx.NetworkError,
                    httpx.RemoteProtocolError,
                ) as e:
                    self.total_retries += 1
                    logger.warning(
                        f"{self.name}: Request failed (attempt "
                        f"{attempt.retry_state.attempt_number}/{self.max_retries}): {e}"
                    )
                    raise

                except Exception as e:
                    self.total_errors += 1
                    logger.exception(f"{self.name}: Unexpected error: {e}")
                    raise

    def get_stats(self) -> Dict[str, int]:
        """
        Get client statistics.

        Returns:
            dict: Statistics including total requests, errors, retries
        """
        return {
            "name": self.name,
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "total_retries": self.total_retries,
            "success_rate": (
                (self.total_requests - self.total_errors) / self.total_requests
                if self.total_requests > 0
                else 0
            ),
        }
