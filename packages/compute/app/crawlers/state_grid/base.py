from __future__ import annotations

import random
import time
from typing import Any

import httpx

from app.config import settings


class StateGridError(Exception):
    """Base exception for State Grid client errors."""


class StateGridHttpError(StateGridError):
    """Raised when a State Grid HTTP request fails."""

    def __init__(self, message: str, response: httpx.Response | None = None) -> None:
        super().__init__(message)
        self.response = response


class StateGridClientBase:
    """Shared HTTP client with retry support for State Grid APIs."""

    def __init__(
        self,
        base_url: str = settings.state_grid_base_url,
        timeout: float = settings.state_grid_api_timeout,
        max_retries: int = settings.state_grid_max_retries,
        retry_backoff_base: float = settings.state_grid_retry_backoff_base,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_base = retry_backoff_base
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/146.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": settings.state_grid_origin,
            "Referer": settings.state_grid_referer,
        }
        if settings.state_grid_cookie:
            headers["Cookie"] = settings.state_grid_cookie
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=headers,
        )

    def _sleep_before_retry(self, attempt: int) -> None:
        delay = self.retry_backoff_base * (2 ** attempt) + random.uniform(0, 1)
        time.sleep(delay)

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        last_error: Exception | None = None
        response: httpx.Response | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.request(method, path, **kwargs)
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise StateGridHttpError(
                        f"State Grid request timed out after {self.max_retries + 1} attempts"
                    ) from exc
                self._sleep_before_retry(attempt)
                continue
            except httpx.HTTPError as exc:
                raise StateGridHttpError(f"State Grid request failed: {exc}") from exc

            status_code = response.status_code
            if status_code < 400:
                return response

            if status_code == 429 or 500 <= status_code <= 599:
                if attempt >= self.max_retries:
                    raise StateGridHttpError(
                        f"State Grid request failed with status {status_code}",
                        response=response,
                    )
                self._sleep_before_retry(attempt)
                continue

            raise StateGridHttpError(
                f"State Grid request failed with status {status_code}",
                response=response,
            )

        raise StateGridHttpError(
            f"State Grid request failed: {last_error}",
            response=response,
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "StateGridClientBase":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
