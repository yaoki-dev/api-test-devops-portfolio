"""GitHub REST API error handling helpers.

設計上の制約: 本モジュールの例外は `from None` で raise し __cause__ を None に設定する。
コーディング規約 Section 5「from e でチェーン維持」の意図的例外であり、理由は PII 漏洩防止。
__cause__ / __context__ に httpx オブジェクト（URL・ヘッダー・body を保持）が残ると、
Sentry や traceback 経由でトークン・private repository 名が漏れうる。
診断情報は構造化ログの endpoint / status_code フィールドで取得可能なため、__cause__ は不要。

同じ理由で、各ハンドラは except 節の外から呼ばれ、response/endpoint/method を引数で受け取る
（except 節内で raise すると __context__ に PII 含有オブジェクトが暗黙で残るため）。
"""

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from typing import Any, NoReturn, cast

import httpx
from structlog.typing import FilteringBoundLogger

from utils.exceptions import APIClientError
from utils.github_rate_limit import (
    _RATE_LIMIT_FORBIDDEN_FALLBACK,
    _RATE_LIMIT_RESET_FALLBACK,
    _parse_rate_limit_header,
)
from utils.retry import exponential_backoff_with_jitter

_MAX_403_ERROR_MESSAGE_CHARS = 200
_MAX_HTTP_ERROR_BODY_PREVIEW_BYTES = 200


def redact_body_preview(body_preview: str) -> str:
    """HTTP error response body preview をリダクション

    エラー応答がトークン、API キー、private repository 名を含む場合に
    stdout/debug logs へ機密情報が漏れるのを防止する。
    内容を完全にマスクし、ハッシュベースの指紋を保持して debug に利用。

    Args:
        body_preview: デコード済みの response body
            （先頭 _MAX_HTTP_ERROR_BODY_PREVIEW_BYTES バイトで切り詰め済み）

    Returns:
        リダクション済み文字列 (形式: "[redacted:SHA256_16chars]")
    """
    body_hash = hashlib.sha256(body_preview.encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"[redacted:{body_hash}]"


class GitHubAPIError(APIClientError):
    """Base exception for GitHub REST API failures."""


class SanitizedJSONDecodeError(Exception):
    """JSON decoding cause that never retains the response body."""

    def __init__(self, error_type: str, msg: str, pos: int, lineno: int, colno: int) -> None:
        self.error_type = error_type
        self.msg = msg
        self.pos = pos
        self.lineno = lineno
        self.colno = colno
        super().__init__(f"{error_type}: {msg} pos={pos}, lineno={lineno}, colno={colno}")

    def __reduce__(
        self,
    ) -> tuple[type[SanitizedJSONDecodeError], tuple[str, str, int, int, int]]:
        # pytest-xdist の worker→controller 例外転送や Sentry SDK のシリアライズで
        # pickle される。非標準 __init__ シグネチャ（5 引数）は Exception 既定の
        # __reduce__（args=単一メッセージ文字列で復元）では TypeError になるため、
        # 全フィールドを渡す __reduce__ を明示する（PR#347 Q-2）。
        return (self.__class__, (self.error_type, self.msg, self.pos, self.lineno, self.colno))


class RateLimitError(GitHubAPIError):
    """GitHub primary or secondary rate limit was exceeded."""

    def __init__(self, reset_time: int) -> None:
        self.reset_time = reset_time
        if reset_time > 0:
            try:
                reset_str = datetime.fromtimestamp(reset_time, tz=UTC).isoformat()
            except (OverflowError, OSError):  # fmt: skip
                reset_str = f"unix:{reset_time}"
        else:
            reset_str = "unknown"
        super().__init__(f"Rate limit exceeded. Reset at {reset_str}")


class NotFoundError(GitHubAPIError):
    """The requested GitHub resource was not found."""


class GitHubServerError(GitHubAPIError):
    """GitHub returned a server-side failure."""


def _handle_403_response(
    response: httpx.Response,
    *,
    logger: FilteringBoundLogger,
    rate_remaining: int | None = None,
    reset_time: int | None = None,
) -> NoReturn:
    """Distinguish a rate-limit response from other 403 failures and raise."""
    if rate_remaining is None:
        rate_remaining = _parse_rate_limit_header(
            response.headers,
            "X-RateLimit-Remaining",
            _RATE_LIMIT_FORBIDDEN_FALLBACK,
            logger=logger,
        )
    if rate_remaining == 0:
        if reset_time is None:
            reset_time = _parse_rate_limit_header(
                response.headers,
                "X-RateLimit-Reset",
                _RATE_LIMIT_RESET_FALLBACK,
                logger=logger,
            )
        raise RateLimitError(reset_time) from None

    error_message = ""
    try:
        parsed = response.json()
        if isinstance(parsed, dict):
            raw_message = parsed.get("message", "")
            if isinstance(raw_message, str):
                error_message = raw_message[:_MAX_403_ERROR_MESSAGE_CHARS]
    except json.JSONDecodeError as parse_err:
        logger.warning(
            "failed_to_parse_403_message",
            error_type=type(parse_err).__qualname__,
            error_module=type(parse_err).__module__,
            error_pos=parse_err.pos,
            error_lineno=parse_err.lineno,
        )

    if error_message:
        logger.warning(
            "github_403_forbidden",
            message_preview=redact_body_preview(error_message),
        )

    raise GitHubAPIError("Access forbidden") from None


async def _handle_5xx_response(
    response: httpx.Response,
    attempt: int,
    endpoint: str,
    method: str,
    *,
    max_retries: int,
    logger: FilteringBoundLogger,
) -> None:
    """Sleep before retrying a 5xx response, or raise after the final attempt."""
    if attempt < max_retries - 1:
        delay = exponential_backoff_with_jitter(attempt, base_delay=2.0)
        logger.warning(
            "retrying_server_error",
            attempt=attempt + 1,
            max_retries=max_retries,
            delay=delay,
            status_code=response.status_code,
            endpoint=endpoint,
            method=method,
        )
        await asyncio.sleep(delay)
        return
    logger.error(
        "github_retry_failed",
        endpoint=endpoint,
        method=method,
        error_type=f"HTTP_{response.status_code}",
        error_module="httpx",
        error_context=f"{method} {endpoint}",
        max_retries=max_retries,
        status_code=response.status_code,
    )
    raise GitHubServerError(
        f"Server error: {response.status_code} after {max_retries} attempts"
    ) from None


def _parse_json_response(
    response: httpx.Response,
    endpoint: str,
    *,
    logger: FilteringBoundLogger,
) -> dict[str, Any] | list[dict[str, Any]]:
    """Parse JSON while replacing a body-retaining decode error with a safe cause."""
    sanitized_cause: SanitizedJSONDecodeError | None = None
    try:
        return cast("dict[str, Any] | list[dict[str, Any]]", response.json())
    except json.JSONDecodeError as error:
        logger.error(
            "json_decode_error",
            endpoint=endpoint,
            error_type=type(error).__qualname__,
            error_module=type(error).__module__,
            error_pos=error.pos,
            error_lineno=error.lineno,
        )
        sanitized_cause = SanitizedJSONDecodeError(
            f"{type(error).__module__}.{type(error).__qualname__}",
            error.msg,
            error.pos,
            error.lineno,
            error.colno,
        )
    raise GitHubAPIError("Invalid JSON response") from sanitized_cause


def _handle_http_status_error(
    response: httpx.Response,
    endpoint: str,
    method: str,
    *,
    logger: FilteringBoundLogger,
) -> NoReturn:
    """Map an HTTP error response to the GitHub exception hierarchy.

    通常フローでは 404/429/403/5xx は _request の main path で先行処理済みのため、
    本関数は主に httpx.HTTPStatusError の defensive path から呼ばれる。
    401/400/405 等の other 4xx はこの関数のみで処理される。
    `from None` と引数受け取りの設計理由はモジュール docstring を参照。
    """
    status_code = response.status_code
    if status_code == 404:
        raise NotFoundError(f"Resource not found: {endpoint}") from None
    if status_code == 429:
        reset_time = _parse_rate_limit_header(
            response.headers,
            "X-RateLimit-Reset",
            _RATE_LIMIT_RESET_FALLBACK,
            logger=logger,
        )
        raise RateLimitError(reset_time) from None
    if status_code == 403:
        remaining = _parse_rate_limit_header(
            response.headers,
            "X-RateLimit-Remaining",
            _RATE_LIMIT_FORBIDDEN_FALLBACK,
            logger=logger,
        )
        reset_time_403 = (
            _parse_rate_limit_header(
                response.headers,
                "X-RateLimit-Reset",
                _RATE_LIMIT_RESET_FALLBACK,
                logger=logger,
            )
            if remaining == 0
            else None
        )
        _handle_403_response(
            response,
            logger=logger,
            rate_remaining=remaining,
            reset_time=reset_time_403,
        )

    body_preview_raw = response.content[:_MAX_HTTP_ERROR_BODY_PREVIEW_BYTES].decode(
        response.encoding or "utf-8",
        errors="replace",
    )
    log_fn = logger.warning if status_code == 401 else logger.debug
    log_fn(
        "http_status_error",
        status_code=status_code,
        endpoint=endpoint,
        method=method,
        body_preview=redact_body_preview(body_preview_raw),
    )
    raise GitHubAPIError(f"HTTP {status_code} error") from None
