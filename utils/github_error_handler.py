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
import re
from datetime import UTC, datetime
from typing import Any, NoReturn, cast

import httpx
from structlog.typing import FilteringBoundLogger

from utils.exceptions import APIClientError
from utils.github_rate_limit import (
    _RATE_LIMIT_FORBIDDEN_FALLBACK,
    _RATE_LIMIT_RESET_FALLBACK,
    SECONDARY_RATE_LIMIT_FALLBACK_RETRY_AFTER,
    _parse_rate_limit_header,
)
from utils.retry import exponential_backoff_with_jitter

_MAX_403_ERROR_MESSAGE_CHARS = 200
_MAX_HTTP_ERROR_BODY_PREVIEW_BYTES = 200

# secondary rate limit は primary と違い remaining が 0 にならず Retry-After も
# 付かないことがあるため、ヘッダーだけでは通常の 403/429 と区別できない。
# body の message 文言が唯一の判定材料であり、公式SDK octokit/plugin-throttling.js も
# 同一の正規表現で判定している。文言変更で検出漏れしうる既知の脆さだが代替手段がない。
_SECONDARY_RATE_LIMIT_PATTERN = re.compile(r"\bsecondary rate\b", re.IGNORECASE)


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
    """GitHub primary or secondary rate limit was exceeded.

    Args:
        reset_time: primary quota がリセットされる unix 時刻。GitHub が X-RateLimit-Reset
            を返さなかった場合は 0（= 不明）。
        retry_after: Retry-After ヘッダーの秒数。primary / secondary を問わず保持する。
            secondary で Retry-After 欠損時は既定60秒。None のときは reset_time まで待つが、
            reset_time == 0 なら待機時間を算出できないため、呼び出し側が既定値を決める。

    GitHub docs は「Retry-After の秒数が経過するまで再試行しない」と「remaining == 0 なら
    reset 時刻まで再試行しない」を独立した条件として課すため、再試行可能時刻は
    max(now + retry_after, reset_time) とする。本リポジトリに自動リトライの消費者は
    ないが（4xx 即失敗契約）、導入する場合は上記の遅い方まで待機すること。
    どの条件で retry_after が定まるかは _rate_limit_retry_after を参照。
    """

    def __init__(self, reset_time: int, *, retry_after: int | None = None) -> None:
        self.reset_time = reset_time
        self.retry_after = retry_after
        if reset_time > 0:
            try:
                reset_str = datetime.fromtimestamp(reset_time, tz=UTC).isoformat()
            except (OverflowError, OSError):  # fmt: skip
                reset_str = f"unix:{reset_time}"
        else:
            reset_str = "unknown"
        message = f"Rate limit exceeded. Reset at {reset_str}"
        if retry_after is not None:
            message = f"{message}. Retry after {retry_after}s"
        super().__init__(message)


class NotFoundError(GitHubAPIError):
    """The requested GitHub resource was not found."""


class GitHubServerError(GitHubAPIError):
    """GitHub returned a server-side failure."""


def _extract_error_message(
    response: httpx.Response,
    *,
    logger: FilteringBoundLogger,
) -> str:
    """Return the JSON body's `message` field, or "" when absent or unparsable.

    呼び出し側は本関数を1レスポンスにつき1回だけ呼ぶこと。body は都度パースされ、
    失敗時に warning を出すため、複数回呼ぶとログが重複する。

    空 body は「パース失敗」ではなく「message なし」として warning なしで "" を返す。
    429 は body を持たないことが常態であり、警告を出すとノイズになるため。この結果、
    従来 warning が出ていた空 body の 403 では出なくなるが、送出される例外は変わらない。
    """
    if not response.content:
        return ""
    try:
        parsed = response.json()
    except json.JSONDecodeError as parse_err:
        logger.warning(
            "failed_to_parse_error_message",
            # 本関数は 403 と 429 の両経路から呼ばれるため、status_code がないと
            # ログだけではどちらのレスポンスで失敗したか切り分けられない。
            status_code=response.status_code,
            error_type=type(parse_err).__qualname__,
            error_module=type(parse_err).__module__,
            error_pos=parse_err.pos,
            error_lineno=parse_err.lineno,
        )
        return ""
    if not isinstance(parsed, dict):
        return ""
    raw_message = parsed.get("message", "")
    if not isinstance(raw_message, str):
        return ""
    return raw_message[:_MAX_403_ERROR_MESSAGE_CHARS]


def _parse_retry_after(headers: httpx.Headers) -> int | None:
    """Return the Retry-After seconds, or None when absent, unparsable, or non-positive.

    RFC 9110 は Retry-After に HTTP-date も許すが GitHub は秒数で返す。秒数として
    読めない値や非正の値はヘッダー不在として扱う（誤った待機時間を返すより安全側）。
    """
    raw = headers.get("Retry-After")
    if raw is None:
        return None
    try:
        seconds = int(raw)
    except ValueError:
        return None
    return seconds if seconds > 0 else None


def _rate_limit_retry_after(response: httpx.Response, error_message: str) -> int | None:
    """Return the wait seconds for a rate-limited response, or None to wait for the reset time.

    GitHub docs は「Retry-After の秒数が経過するまで再試行しない」と「remaining == 0 なら
    reset まで再試行しない」を独立した条件として課すため、Retry-After は primary /
    secondary を問わず常に保持する（再試行可能時刻の合成規則は RateLimitError を参照）。
    Retry-After 欠損時は、secondary なら docs の「最低1分」に倒し、それ以外は None を
    返して reset まで待たせる。

    `error_message` は JSON body の message フィールドに限定する。生 body を対象にすると
    プロキシが返す HTML エラー等が文言を含むだけで誤検出されうる。呼び出し側は
    remaining == 0（primary 枯渇）のとき body を読まず "" を渡す規約なので、
    secondary の 60 秒フォールバックが primary 枯渇時に誤って適用されることはない。
    """
    seconds = _parse_retry_after(response.headers)
    if seconds is not None:
        return seconds
    if _SECONDARY_RATE_LIMIT_PATTERN.search(error_message):
        return SECONDARY_RATE_LIMIT_FALLBACK_RETRY_AFTER
    return None


def _resolve_rate_limit_retry_after(
    response: httpx.Response,
    *,
    logger: FilteringBoundLogger,
    rate_remaining: int | None = None,
) -> int | None:
    """Return the retry_after seconds for a 429 response, or None to wait for the reset time.

    remaining == 0 は primary 枯渇として扱い body を読まない（403 側と同じ判定規則）。
    403 ハンドラは抽出した message を forbidden ログにも使うため抽出と判定を分けて呼ぶが、
    429 の2経路は retry_after しか要らないため本関数を使う（message の二重パースを避ける）。

    Args:
        rate_remaining: 呼び出し側が X-RateLimit-Remaining をパース済みならその値。None なら
            本関数がパースする。ヘッダー不正時に _parse_rate_limit_header が warning を出すため、
            既にパース済みの値を渡さないと1レスポンスにつき warning が重複する。
            fallback 値は呼び出し側と異なりうるが、0 以外である点は共通なので判定は変わらない。
    """
    if rate_remaining is None:
        rate_remaining = _parse_rate_limit_header(
            response.headers,
            "X-RateLimit-Remaining",
            # 定数名は 403 由来だが、値 -1 の意味は「remaining ヘッダーが読めない」であり
            # 429 でも同じ。0 以外なら primary 枯渇と誤判定しないため既定として正しい。
            _RATE_LIMIT_FORBIDDEN_FALLBACK,
            logger=logger,
        )
    error_message = "" if rate_remaining == 0 else _extract_error_message(response, logger=logger)
    return _rate_limit_retry_after(response, error_message)


def _handle_403_response(
    response: httpx.Response,
    *,
    logger: FilteringBoundLogger,
    rate_remaining: int | None = None,
    reset_time: int | None = None,
) -> NoReturn:
    """Distinguish a rate-limit response from other 403 failures and raise.

    403 は primary 超過 / secondary rate limit / 通常の Forbidden の3通りで返る。
    primary は remaining == 0 で判別できるが、secondary は remaining != 0 のまま返り
    Retry-After も付かないことがあるため、body の message 文言でしか判別できない。
    """
    if rate_remaining is None:
        rate_remaining = _parse_rate_limit_header(
            response.headers,
            "X-RateLimit-Remaining",
            _RATE_LIMIT_FORBIDDEN_FALLBACK,
            logger=logger,
        )

    # primary は remaining だけで判別でき body を読む必要がない。読まないことで、
    # primary 経路に parse 失敗 warning を増やさない従来挙動も維持される。
    error_message = "" if rate_remaining == 0 else _extract_error_message(response, logger=logger)
    # rate limit 判定は remaining と message 文言のみで行う。Retry-After の有無を判定に
    # 使うと、WAF 等が Retry-After を付けた通常の Forbidden を RateLimitError に誤分類する。
    is_secondary = _SECONDARY_RATE_LIMIT_PATTERN.search(error_message) is not None

    if rate_remaining == 0 or is_secondary:
        retry_after = _rate_limit_retry_after(response, error_message)
        if reset_time is None:
            reset_time = _parse_rate_limit_header(
                response.headers,
                "X-RateLimit-Reset",
                _RATE_LIMIT_RESET_FALLBACK,
                logger=logger,
            )
        raise RateLimitError(reset_time, retry_after=retry_after) from None

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
        # 429 は primary / secondary の両方で返る。Retry-After は両者で保持し、
        # 再試行可能時刻は max(now + retry_after, reset_time)（RateLimitError 参照）。
        retry_after = _resolve_rate_limit_retry_after(response, logger=logger)
        raise RateLimitError(reset_time, retry_after=retry_after) from None
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
