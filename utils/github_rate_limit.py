"""GitHub REST API rate-limit helpers."""

import asyncio
from datetime import UTC, datetime

import httpx
from structlog.typing import FilteringBoundLogger

from utils.retry import exponential_backoff_with_jitter

_RATE_LIMIT_FALLBACK_REMAINING = 999
RATE_LIMIT_WARNING_THRESHOLD = 10
_RATE_LIMIT_FORBIDDEN_FALLBACK = -1
_RATE_LIMIT_RESET_FALLBACK = 0


def _parse_rate_limit_header(
    headers: httpx.Headers,
    name: str,
    default: int,
    *,
    logger: FilteringBoundLogger,
) -> int:
    """Parse an integer rate-limit header, falling back on missing or invalid values."""
    raw = headers.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("invalid_rate_limit_header", header=name, value=repr(raw)[:100])
        return default


def _check_rate_limit_warning(
    response_headers: httpx.Headers,
    remaining: int,
    *,
    logger: FilteringBoundLogger,
) -> int | None:
    """Log and return the reset time when the remaining quota is below the threshold."""
    if remaining >= RATE_LIMIT_WARNING_THRESHOLD:
        return None

    reset_time = _parse_rate_limit_header(
        response_headers,
        "X-RateLimit-Reset",
        _RATE_LIMIT_RESET_FALLBACK,
        logger=logger,
    )
    try:
        reset_str = datetime.fromtimestamp(reset_time, tz=UTC).isoformat()
    except (OverflowError, OSError):  # fmt: skip
        reset_str = f"unix:{reset_time}"
    logger.warning("rate_limit_low", remaining=remaining, reset_time=reset_str)
    return reset_time


async def _log_and_sleep_for_retry(
    *,
    event: str,
    error_context: str,
    error: httpx.TimeoutException | httpx.NetworkError | httpx.RemoteProtocolError,
    endpoint: str,
    method: str,
    attempt: int,
    max_retries: int,
    logger: FilteringBoundLogger,
) -> None:
    """Log a retryable failure and sleep unless the final attempt has failed."""
    logger.warning(
        event,
        endpoint=endpoint,
        method=method,
        error_type=type(error).__qualname__,
        error_module=type(error).__module__,
        error_context=error_context,
    )
    if attempt < max_retries - 1:
        delay = exponential_backoff_with_jitter(attempt, base_delay=2.0)
        await asyncio.sleep(delay)
        return
    logger.error(
        "github_retry_failed",
        endpoint=endpoint,
        method=method,
        error_type=type(error).__qualname__,
        error_module=type(error).__module__,
        error_context=error_context,
        max_retries=max_retries,
        status_code=None,
    )
