"""GitHub API非同期クライアント

学習目標:
- GitHub REST API v3の実務的活用（Rate Limit管理、Conditional Requests）
- 非同期HTTP通信の最適化（ETag活用）
- API制約への対応戦略（認証なし60 req/h → 認証あり5000 req/h拡張可能設計）
"""

import asyncio
import hashlib
import itertools
import json
import re
from datetime import UTC, datetime
from types import TracebackType
from typing import Any, NoReturn, Self, cast
from urllib.parse import quote, urlencode

import httpx

from utils.api_client import ASYNC_FATAL_EXCEPTIONS, APIClientError, exponential_backoff_with_jitter
from utils.logger import get_logger

# =============================================================================
# 入力バリデーション（OWASP A03:2021 - Injection対策）
# =============================================================================

# GitHub username仕様: 1-39文字、英数字・ハイフン、先頭は英数字
GITHUB_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38}$")
# GitHub repository名仕様: 1-100文字、英数字・ドット・ハイフン・アンダースコア
GITHUB_REPO_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{1,100}$")
# ETag形式バリデーション（RFC 7232準拠: W/"..." または "..."）
_ETAG_PATTERN: re.Pattern[str] = re.compile(r'^(?:W/)?"[^"\r\n\\]*"$')


def validate_github_username(username: str) -> None:
    """GitHubユーザー名のバリデーション

    Args:
        username: GitHubユーザー名

    Raises:
        ValueError: バリデーション失敗

    Note:
        GitHub username仕様:
        - 1-39文字
        - 英数字、ハイフン（連続不可、先頭・末尾不可）
        - 先頭は英数字

    """
    if not username or not GITHUB_USERNAME_PATTERN.match(username):
        raise ValueError(f"Invalid GitHub username: '{username}'")


def validate_github_repo(repo: str) -> None:
    """GitHubリポジトリ名のバリデーション

    "." と ".." は予約名として拒否する。
    ".github" のようなドット始まりの名前はGitHub上で有効なため許可する。

    Args:
        repo: リポジトリ名

    Raises:
        ValueError: バリデーション失敗

    """
    if not repo or repo in {".", ".."} or not GITHUB_REPO_PATTERN.match(repo):
        raise ValueError(f"Invalid GitHub repository name: '{repo}'")


# =============================================================================
# Rate Limit定数（フォールバック値・閾値）
# =============================================================================
_RATE_LIMIT_FALLBACK_REMAINING = 999  # 監視パス: ヘッダー不正値時、残量十分とみなす
_RATE_LIMIT_WARNING_THRESHOLD = 10  # 残量10未満で警告ログ出力
_RATE_LIMIT_FORBIDDEN_FALLBACK = -1  # 403判定パス: 不正値時はRate Limit超過と判定しない
_RATE_LIMIT_RESET_FALLBACK = 0  # リセット時刻不明時のフォールバック
_MAX_403_ERROR_MESSAGE_CHARS = 200  # 403 JSON message の上限文字数: ログ肥大・漏洩防止
# HTTPStatusError body_preview の上限バイト数: ログ肥大・漏洩防止
_MAX_HTTP_ERROR_BODY_PREVIEW_BYTES = 200
# cache_invariant_violation logger.error 出力時のキーリスト上限件数 (PII漏洩防止)
_MAX_CACHE_INVARIANT_LOG_KEYS = 5


# =============================================================================
# 例外クラス
# =============================================================================


def _redact_body_preview(body_preview: str) -> str:
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
    """GitHub API基底例外（APIClientErrorを継承し統一的なエラーハンドリングを実現）"""


class _SanitizedJSONDecodeError(Exception):
    """レスポンスbodyを保持しない JSONDecodeError cause。"""

    def __init__(self, error_type: str, pos: int, lineno: int) -> None:
        self.error_type = error_type
        self.pos = pos
        self.lineno = lineno
        super().__init__(f"{error_type}: pos={pos}, lineno={lineno}")


class RateLimitError(GitHubAPIError):
    """Rate Limit超過エラー（403/429）"""

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
    """リソースが見つからない（404 Not Found）"""


class GitHubServerError(GitHubAPIError):
    """GitHub側のサーバーエラー（5xx）"""


# =============================================================================
# AsyncGitHubClient実装
# =============================================================================


class AsyncGitHubClient:
    """GitHub API非同期クライアント

    特徴:
    - Rate Limit自動対応（X-RateLimit-Remaining監視）
    - Conditional Requests対応（ETag活用）
    - リトライロジック（5xx・timeout・NetworkError・RemoteProtocolError、指数バックオフ+ジッター）
    - 例外チェーン（HTTPStatusError は URL+ステータスのみ保持した cause に再ラップ）

    使用例:
        >>> async with AsyncGitHubClient() as client:
        ...     user = await client.get_user("octocat")
        ...     print(user["name"])  # "The Octocat"
    """

    BASE_URL = "https://api.github.com"

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        user_agent: str = "AsyncGitHubClient/1.0",
        max_cache_entries: int = 256,
    ):
        """AsyncGitHubClientの初期化

        Args:
            timeout: リクエストタイムアウト（秒）
            max_retries: 最大試行回数
                （5xx・timeout・NetworkError・RemoteProtocolError の再試行回数、初回含む）。
                デフォルト設定(timeout=30, max_retries=3)での最悪ケース: 約96秒。
            user_agent: User-Agentヘッダー（GitHub要求事項）
            max_cache_entries: ETag/dataキャッシュの最大エントリ数（デフォルト256）

        """
        if max_cache_entries < 1:
            raise ValueError("max_cache_entries must be >= 1")
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent
        self.max_cache_entries = max_cache_entries
        self._client: httpx.AsyncClient | None = None
        self._etag_cache: dict[str, str] = {}  # cache_key (endpoint+sorted query) -> ETag
        # cache_key -> response data（304レスポンス時のキャッシュ返却用）
        self._data_cache: dict[str, dict[str, Any] | list[dict[str, Any]]] = {}
        self.logger = get_logger(__name__)

    async def _log_and_sleep_for_retry(
        self,
        *,
        event: str,
        error_context: str,
        error: httpx.TimeoutException | httpx.NetworkError | httpx.RemoteProtocolError,
        endpoint: str,
        method: str,
        attempt: int,
    ) -> None:
        """Retry 対象例外をログし、次の試行前に sleep する。

        最終試行（attempt == max_retries - 1）では sleep を行わず error ログを出力して返る。
        例外の raise は呼び出し元の責務。

        Args:
            event: structlog に渡すイベント名（例："request_timeout"）
            error_context: ログの error_context フィールド値（例："timeout"）
            error: キャッチした例外（TimeoutException、NetworkError、RemoteProtocolError）。
                   LocalProtocolError はクライアント側 protocol violation のため retry 対象外。
            endpoint: リクエスト先エンドポイント（ログ用）
            method: HTTP メソッド（ログ用）
            attempt: 現在の試行インデックス（0-based）
        """
        self.logger.warning(
            event,
            endpoint=endpoint,
            method=method,
            error_type=type(error).__qualname__,
            error_module=type(error).__module__,
            error_context=error_context,
        )
        if attempt < self.max_retries - 1:
            delay = exponential_backoff_with_jitter(attempt, base_delay=2.0)
            await asyncio.sleep(delay)
            return
        self.logger.error(
            "github_retry_failed",
            endpoint=endpoint,
            method=method,
            error_type=type(error).__qualname__,
            error_module=type(error).__module__,
            error_context=error_context,
            max_retries=self.max_retries,
            status_code=None,  # timeout/network error はステータスコードなし
        )

    async def __aenter__(self) -> Self:
        """非同期コンテキストマネージャーのエントリー"""
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=self.timeout,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": self.user_agent,
            },
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """非同期コンテキストマネージャーの終了処理。"""
        # AsyncGitHubClient は AsyncAPIClient の _close_async_client() ヘルパーを継承しないため、
        # __aexit__ に close ロジックをインラインで実装する。
        if self._client:
            try:
                await self._client.aclose()
            except (httpx.CloseError, OSError) as close_exc:  # fmt: skip
                # 既知のクローズ時例外 — warning のみ（body 例外 exc_val を上書きしない）。
                # error_type + error_module で third-party 例外の起点モジュールを識別可能にする。
                self.logger.warning(
                    "github_client_aclose_failed",
                    error_type=type(close_exc).__name__,
                    error_module=type(close_exc).__module__,
                )
            except RecursionError:
                # RecursionError も Exception 派生のため、再raise しないと下流の
                # except Exception に has_body_exception=True 時捕捉されサイレント隠蔽される
                # （api_client._close_async_client / sentry_init と同一方針）。
                # 致命的エラーとして必ず再raise（fail-fast）。
                raise
            except MemoryError:
                # MemoryError も Exception 派生のため、再raise しないと下流の
                # except Exception に捕捉されサイレント隠蔽される。
                # 致命的エラーとして必ず再raise（fail-fast）。
                raise
            except Exception as close_exc:  # noqa: BLE001
                # 予期しない例外（AttributeError, RuntimeError 等の実装バグ可能性）。
                # RecursionError / MemoryError は上の専用句で先取り済み（fail-fast）。
                has_body_exception = exc_type is not None
                self.logger.error(
                    "github_client_aclose_unexpected_error",
                    error_type=type(close_exc).__name__,
                    error_module=type(close_exc).__module__,
                    has_body_exception=has_body_exception,
                    action=(
                        "suppressed_due_to_body_exception" if has_body_exception else "re_raised"
                    ),
                    # PR#347 review SF-2: close_exc が body 例外を上書きしないため
                    # __context__ チェーンは切断される。代わりに body 例外の型名を
                    # 同一ログイベント内に記録し、close 失敗と body 例外の対応関係を
                    # 追跡可能にする (PII 非含: __qualname__ はクラス名のみ)。
                    body_exception_type=exc_type.__qualname__ if exc_type is not None else None,
                    exc_info=True,  # スタックトレースをログに残す
                )
                # body 例外がない場合のみ実装バグとして re-raise。
                # body 例外がある場合は本質的原因の上書きを防ぐため raise しない。
                # bare ``raise`` で active exception の traceback を完全保持
                # （``raise close_exc`` への回帰防止: 余分な frame を追加せず Python idiom）。
                if not has_body_exception:
                    raise
            else:
                # aclose() 成功時のみ closed ログを出す。logger.info を try 内に置くと
                # logger 自体の例外が aclose 失敗として誤検知されるため else 節に分離 (PR#347)。
                self.logger.info("async_github_client_closed")
                # ダブルクローズ防止: AsyncAPIClient._close_async_client と同一パターン。
                # aclose() 成功後に None をセットし、再 __aexit__ 時の if self._client ガードで
                # 空振りさせる（冪等性確保）。
                self._client = None

    async def get_user(self, username: str) -> dict[str, Any]:
        """ユーザー情報取得

        Args:
            username: GitHubユーザー名

        Returns:
            ユーザー情報（name, bio, public_repos等）

        Raises:
            ValueError: 無効なユーザー名
            NotFoundError: ユーザーが存在しない
            RateLimitError: 403 Rate Limit超過 または 429 Too Many Requests
            GitHubServerError: 5xxエラー（リトライ上限後）
            GitHubAPIError: タイムアウト・NetworkError・RemoteProtocolError
                            リトライ上限後の最終失敗、または不正なレスポンス型

        Example:
            >>> async with AsyncGitHubClient() as client:
            ...     user = await client.get_user("octocat")
            ...     print(user["name"])  # "The Octocat"

        """
        validate_github_username(username)
        result = await self._request("GET", f"/users/{username}")
        if not isinstance(result, dict):
            raise GitHubAPIError(f"Expected dict response, got {type(result).__name__}")
        return result

    async def get_repos(
        self,
        username: str,
        sort: str = "updated",
        per_page: int = 30,
    ) -> list[dict[str, Any]]:
        """ユーザーのリポジトリ一覧取得

        Args:
            username: GitHubユーザー名
            sort: ソート順（created, updated, pushed, full_name）
            per_page: 1ページあたりの件数（最大100）

        Returns:
            リポジトリ情報リスト

        Raises:
            ValueError: 無効なユーザー名
            RateLimitError: 403 Rate Limit超過 または 429 Too Many Requests
            NotFoundError: リソースが見つからない場合
            GitHubServerError: 5xxエラー（リトライ上限後）
            GitHubAPIError: タイムアウト・NetworkError・RemoteProtocolError
                            リトライ上限後の最終失敗、または不正なレスポンス型

        Example:
            >>> repos = await client.get_repos("octocat", sort="updated")
            >>> print(repos[0]["name"])  # 最新更新のリポジトリ

        """
        validate_github_username(username)
        if sort not in {"created", "updated", "pushed", "full_name"}:
            raise ValueError("sort must be one of: created, updated, pushed, full_name")
        if not 1 <= per_page <= 100:
            raise ValueError("per_page must be between 1 and 100")
        params: dict[str, str | int] = {"sort": sort, "per_page": per_page}
        result = await self._request("GET", f"/users/{username}/repos", params=params)
        if not isinstance(result, list):
            raise GitHubAPIError(f"Expected list response, got {type(result).__name__}")
        return result

    async def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        """リポジトリ詳細取得

        Args:
            owner: オーナー名
            repo: リポジトリ名

        Returns:
            リポジトリ詳細（stars, forks, open_issues等）

        Raises:
            ValueError: 無効なオーナー名またはリポジトリ名
            RateLimitError: 403 Rate Limit超過 または 429 Too Many Requests
            NotFoundError: リソースが見つからない場合
            GitHubServerError: 5xxエラー（リトライ上限後）
            GitHubAPIError: タイムアウト・NetworkError・RemoteProtocolError
                            リトライ上限後の最終失敗、または不正なレスポンス型

        Example:
            >>> repo = await client.get_repo("octocat", "Hello-World")
            >>> print(repo["stargazers_count"])  # スター数

        """
        validate_github_username(owner)
        validate_github_repo(repo)
        result = await self._request("GET", f"/repos/{owner}/{repo}")
        if not isinstance(result, dict):
            raise GitHubAPIError(f"Expected dict response, got {type(result).__name__}")
        return result

    def _parse_rate_limit_header(self, headers: httpx.Headers, name: str, default: int) -> int:
        """Rate Limitヘッダーを安全にパースする。

        Args:
            headers: HTTPレスポンスヘッダー
            name: ヘッダー名（例: "X-RateLimit-Remaining"）
            default: パース失敗時のフォールバック値

        Returns:
            パースされた整数値。ヘッダー未設定またはパース失敗時は default を返す。

        Note:
            ValueErrorをキャッチし、warningログを出力してフォールバック値を返す。
        """
        raw = headers.get(name)
        if raw is None:
            return default
        try:
            return int(raw)
        except ValueError:
            self.logger.warning(
                "invalid_rate_limit_header",
                header=name,
                value=repr(raw)[:100],
            )
            return default

    def _prepare_headers(self, cache_key: str) -> dict[str, str]:
        """ETagキャッシュが存在する場合に If-None-Match ヘッダーを含む dict を返す。

        Conditional Requests対応。
        """
        headers: dict[str, str] = {}
        if cache_key in self._etag_cache:
            headers["If-None-Match"] = self._etag_cache[cache_key]
        return headers

    def _check_rate_limit_warning(
        self,
        response_headers: httpx.Headers,
        remaining: int,
    ) -> int | None:
        """RateLimit残量が閾値未満の場合に警告ログを出力する。

        Args:
            response_headers: HTTPレスポンスヘッダー（X-RateLimit-Reset を参照）
            remaining: 残りAPIコール数

        Returns:
            remaining が閾値未満の場合は X-RateLimit-Reset のエポック秒（int）を返す。
            閾値以上の場合は None を返す。
            返却値は呼び出し元で Rate Limit エラー処理用 reset_time としても使用される。
        """
        if remaining < _RATE_LIMIT_WARNING_THRESHOLD:
            # 戻り値 >= 1: 有効な Unix タイムスタンプ（rate limit warning 発生時）
            reset_time = self._parse_rate_limit_header(
                response_headers, "X-RateLimit-Reset", _RATE_LIMIT_RESET_FALLBACK
            )
            # 異常に大きい reset_time では OverflowError/OSError が発生する場合がある。
            # RateLimitError.__init__（L127-130）と同じパターンで保護し、
            # 警告ログの継続出力を保証する。
            try:
                reset_str = datetime.fromtimestamp(reset_time, tz=UTC).isoformat()
            except (OverflowError, OSError):  # fmt: skip
                reset_str = f"unix:{reset_time}"
            self.logger.warning(
                "rate_limit_low",
                remaining=remaining,
                reset_time=reset_str,
            )
            return reset_time
        return None

    def _handle_304_response(self, cache_key: str) -> dict[str, Any] | list[dict[str, Any]]:
        """304 Not Modified: キャッシュデータを返却する。キャッシュミス時はエラー。"""
        if cache_key in self._data_cache:
            return self._data_cache[cache_key]
        # キャッシュミス時（理論上発生しない: ETagあり=キャッシュあり）
        # Fail-fast: キャッシュ不整合は実装バグの証拠
        # endpoint_only: クエリパラメータを除去してデバッグ可能性を確保しつつ機密パラメータを非露出
        endpoint_only = cache_key.split("?")[0]
        self.logger.error(
            "cache_miss_on_304",
            endpoint=endpoint_only,
            hint="ETag存在時のキャッシュミスは実装バグ",
            etag=self._etag_cache.get(cache_key),
        )
        raise GitHubAPIError(
            f"Cache inconsistency: 304 response without cached data for {endpoint_only}"
        )

    def _handle_403_response(
        self,
        response: httpx.Response,
        *,
        rate_remaining: int | None = None,
        reset_time: int | None = None,
    ) -> NoReturn:
        """403エラー処理: Rate Limit超過 vs その他の403を判別して raise する。"""
        # フォールバック -1 = 不正値時はRate Limit超過と判定せずGitHubAPIErrorへ
        if rate_remaining is None:
            rate_remaining = self._parse_rate_limit_header(
                response.headers, "X-RateLimit-Remaining", _RATE_LIMIT_FORBIDDEN_FALLBACK
            )
        if rate_remaining == 0:
            # Rate Limit超過確定
            if reset_time is None:
                reset_time = self._parse_rate_limit_header(
                    response.headers, "X-RateLimit-Reset", _RATE_LIMIT_RESET_FALLBACK
                )
            raise RateLimitError(reset_time) from None
        # その他の403エラー（IPブロック、アクセス権限不足等）
        error_message = ""
        try:
            parsed = response.json()
            if isinstance(parsed, dict):
                raw_message = parsed.get("message", "")
                if isinstance(raw_message, str):
                    error_message = raw_message[:_MAX_403_ERROR_MESSAGE_CHARS]
        except json.JSONDecodeError as parse_err:
            # JSONパース失敗は想定内（GitHub APIが非JSON形式で403を返す場合がある）
            # PII漏洩防止: parse_err.doc はレスポンスbody全体を保持するため、
            # ログのみ記録し active exception context の外で raise して __context__ を None に保つ。
            self.logger.warning(
                "failed_to_parse_403_message",
                error_type=type(parse_err).__qualname__,
                error_module=type(parse_err).__module__,
                error_pos=parse_err.pos,
                error_lineno=parse_err.lineno,
            )

        # JSONDecodeError.doc はレスポンスbody全体を保持する。
        # except 外で raise して __context__ を None に保つ（_parse_json_response と同方針）。
        # JSONDecodeError パス（error_message=""）も正常パスも同一の raise で処理。
        raise GitHubAPIError(
            f"Access forbidden: {error_message}" if error_message else "Access forbidden"
        ) from None

    async def _handle_5xx_response(
        self,
        response: httpx.Response,
        attempt: int,
        endpoint: str,
        method: str,
    ) -> None:
        """5xxエラーのリトライ制御。最終試行なら raise、継続なら return する。

        リトライ継続時は return し、呼び出し元が continue する。

        Raises:
            GitHubServerError: リトライ上限到達
        """
        if attempt < self.max_retries - 1:
            delay = exponential_backoff_with_jitter(attempt, base_delay=2.0)
            self.logger.warning(
                "retrying_server_error",
                attempt=attempt + 1,
                max_retries=self.max_retries,
                delay=delay,
                status_code=response.status_code,
                endpoint=endpoint,
                method=method,
            )
            await asyncio.sleep(delay)
            return
        self.logger.error(
            "github_retry_failed",
            endpoint=endpoint,
            method=method,
            error_type=f"HTTP_{response.status_code}",
            error_module="httpx",
            error_context=f"{method} {endpoint}",
            max_retries=self.max_retries,
            status_code=response.status_code,
        )
        raise GitHubServerError(
            f"Server error: {response.status_code} after {self.max_retries} attempts",
        ) from None

    def _parse_json_response(
        self,
        response: httpx.Response,
        endpoint: str,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """JSONレスポンスをパースする。破損JSON時はGitHubAPIErrorを発生。"""
        _sanitized_cause: _SanitizedJSONDecodeError | None = None
        try:
            return cast(
                "dict[str, Any] | list[dict[str, Any]]",
                response.json(),
            )
        except json.JSONDecodeError as e:
            self.logger.error(
                "json_decode_error",
                endpoint=endpoint,
                error_type=type(e).__qualname__,
                error_module=type(e).__module__,
                error_pos=e.pos,
                error_lineno=e.lineno,
            )
            # JSONDecodeError.doc はレスポンスbody全体を保持する。
            # doc を除外し、型情報と位置情報のみを保持する sanitized cause を作成。
            # except 内で raise すると __context__ に元例外が残存して露出するため、
            # active exception context の外で raise して __context__ を None に保つ。
            _sanitized_cause = _SanitizedJSONDecodeError(
                f"{type(e).__module__}.{type(e).__qualname__}",
                e.pos,
                e.lineno,
            )
        raise GitHubAPIError("Invalid JSON response") from _sanitized_cause

    def _handle_http_status_error(
        self,
        response: httpx.Response,
        endpoint: str,
        method: str,
    ) -> NoReturn:
        """HTTPエラーレスポンスを適切な例外に変換して raise する。

        404/429/403 は専用例外 (NotFoundError/RateLimitError/GitHubAPIError) に変換し、
        それ以外の 4xx/5xx は GitHubAPIError に変換する。

        通常フローでは 404/429/403/5xx は _request の main path で先行処理済みのため、
        本メソッドは主に httpx.HTTPStatusError defensive path (except 外) から呼ばれる。
        401/400/405 等の other 4xx はこのメソッドのみで処理される。

        設計上の制約: `from None` を使用し __cause__ を None に設定する。
        理由: 全 PII 回避パス（timeout/unexpected/NotFound/RateLimit/JSONDecode）と統一し、
        呼び出し元が __cause__ を参照する際の分岐を不要とするため。
        診断情報は構造化ログの endpoint フィールドで取得可能なため __cause__ への記録は不要。
        コーディング規約 Section 5「from e でチェーン維持」の意図的例外（PII漏洩防止優先）。

        response/endpoint/method を直接受け取る理由: 呼び出し元が except 外で呼ぶことで
        __context__ に PII含有オブジェクトが残存しないよう設計（PII漏洩防止）。
        """
        status_code = response.status_code

        # 404: NotFoundError に変換（通常パスと等価）
        if status_code == 404:
            raise NotFoundError(f"Resource not found: {endpoint}") from None

        # 429: RateLimitError に変換（通常パスと等価）
        if status_code == 429:
            reset_time = self._parse_rate_limit_header(
                response.headers, "X-RateLimit-Reset", _RATE_LIMIT_RESET_FALLBACK
            )
            raise RateLimitError(reset_time) from None

        # 403: Rate Limit超過 vs その他 403 を詳細分析して raise（通常パスと等価）
        if status_code == 403:
            remaining = self._parse_rate_limit_header(
                response.headers, "X-RateLimit-Remaining", _RATE_LIMIT_FORBIDDEN_FALLBACK
            )
            reset_time_403 = (
                self._parse_rate_limit_header(
                    response.headers, "X-RateLimit-Reset", _RATE_LIMIT_RESET_FALLBACK
                )
                if remaining == 0
                else None
            )
            self._handle_403_response(response, rate_remaining=remaining, reset_time=reset_time_403)
            raise AssertionError("unreachable: _handle_403_response is NoReturn")

        # ログレベル別出力先
        # warning(401) → LOG__LEVEL=ERROR未満の全設定でstdoutに出力（デフォルトINFO含む）
        # debug(404等) → LOG__LEVEL=DEBUGの場合のみstdoutに出力
        # いずれもSentry非送信: make_filtering_bound_logger によりDEBUG/WARNING は
        #   Sentry送信前にフィルタ済み（参照: utils/logger.py L160, _sentry_processor L52-54）
        body_preview_raw = response.content[:_MAX_HTTP_ERROR_BODY_PREVIEW_BYTES].decode(
            response.encoding or "utf-8",
            errors="replace",
        )
        # 401 (Unauthorized) は認証エラーのため warning、その他の想定内エラーは debug に抑制
        log_fn = self.logger.warning if status_code == 401 else self.logger.debug
        log_fn(
            "http_status_error",
            status_code=status_code,
            endpoint=endpoint,
            method=method,
            body_preview=_redact_body_preview(body_preview_raw),
        )
        raise GitHubAPIError(f"HTTP {status_code} error") from None

    def _update_etag_cache(
        self,
        cache_key: str,
        response: httpx.Response,
        result_json: dict[str, Any] | list[dict[str, Any]],
    ) -> None:
        """ETagとデータキャッシュを同時更新する。

        asyncio シングルスレッド環境のため競合は発生しない。

        挿入順序（挿入前退避方式）:
          1. 既存キーを both dict から削除して挿入順を更新する。
          2. _enforce_cache_limit(reserve=1) で挿入前に退避し、新規 1 件分の余地を確保する。
          3. data→ETag の順で保存する（挿入後も上限を超えない, PR#347 review #9）。

        例外発生時は「dataあり/ETagなし」の一時状態になりうるが、ETagなしなら次回は
        通常リクエスト（304非使用）となり安全に回復する。
        「ETagあり/dataなし」はETagが最後に書き込まれるため物理的に発生しない。
        """
        if "ETag" in response.headers:
            etag = response.headers["ETag"]
            # ETag形式バリデーション（RFC 7232準拠: W/"..." または "..."）
            if not _ETAG_PATTERN.match(etag):
                self.logger.warning(
                    "invalid_etag_format",
                    endpoint=cache_key.split("?")[0],
                    etag_prefix=etag[:20] if len(etag) > 20 else etag,
                )
                # 無効ETag受信時は既存キャッシュを破棄（次回リクエストで304再利用を防止）
                self._etag_cache.pop(cache_key, None)
                self._data_cache.pop(cache_key, None)
                return
            self._etag_cache.pop(cache_key, None)
            self._data_cache.pop(cache_key, None)
            # 挿入前に reserve=1 で退避し、挿入後もエントリ数が max_cache_entries を
            # 超えないようにする。挿入後 enforce では瞬間的に max+1 件になるため、
            # 新規エントリ 1 件分の余地を空けてから挿入する (PR#347 review #9)。
            self._enforce_cache_limit(reserve=1)
            self._data_cache[cache_key] = result_json
            self._etag_cache[cache_key] = etag
        else:
            if cache_key in self._etag_cache or cache_key in self._data_cache:
                self.logger.info("etag_removed", endpoint=cache_key.split("?")[0])
            self._etag_cache.pop(cache_key, None)
            self._data_cache.pop(cache_key, None)

    @staticmethod
    def _cache_key(endpoint: str, params: dict[str, str | int] | None = None) -> str:
        """エンドポイントとクエリパラメータからキャッシュキーを生成する。

        params が None または空の場合は endpoint をそのまま返す。
        params={} は httpx の仕様（空クエリ = クエリなし）に従い、
        params=None と同一のキャッシュキーを生成する。
        params がある場合は ``endpoint?key1=val1&key2=val2`` 形式で返す。
        URLエンコードには ``quote_via=quote`` を使用する（スペースは ``%20``）。
         パラメータはキーでソートされ決定論的なキーを生成する。

        Args:
            endpoint: APIエンドポイントパス（例: ``/users/octocat/repos``）。
            params: クエリパラメータ辞書（None可）

        Returns:
            キャッシュキー文字列

        """
        if not params:
            return endpoint
        try:
            sorted_params = sorted((k, str(v)) for k, v in params.items())
            return f"{endpoint}?{urlencode(sorted_params, quote_via=quote)}"
        except (TypeError, UnicodeEncodeError) as e:
            # PR#347 review #4-[8]: 通常パスの try/except 外で実行されるため、
            # 例外型のみ含む GitHubAPIError に変換して呼び出し元のリトライ/エラー
            # ハンドリング体系に統合。params 値は PII 含有可能性があるため
            # ``from None`` で例外チェーンを切断し、エラーメッセージに含めない。
            raise GitHubAPIError(
                f"cache_key build failed for endpoint={endpoint!r}: {type(e).__name__}"
            ) from None

    def _enforce_cache_limit(self, reserve: int = 0) -> None:
        """ETag/dataキャッシュを ``max_cache_entries - reserve`` 以下に保つ。

        Args:
            reserve: 直後に挿入する新規エントリ数の予約枠（デフォルト 0）。
                ``_update_etag_cache`` は挿入前に ``reserve=1`` で呼び出すことで、
                挿入後もエントリ数が ``max_cache_entries`` を超えない（瞬間的な
                max+1 を防止, PR#347 review #9）。``max_cache_entries >= 1``
                かつ ``reserve in (0, 1)`` のため退避目標は常に 0 以上。

        _update_etag_cache は _etag_cache と _data_cache を常にペアで書き込むため、
        _etag_cache のみを基準に古いエントリを削除すれば両キャッシュの整合性が保たれる。

        Invariant 違反検出時は logger.error + 両キャッシュ clear で safe-fallback する。
        ``assert`` 文は ``python -O`` モードで silent disable されるため production では使わない。

        Invariant 判定は ``dict.keys()`` の集合等価比較 (defense-in-depth)。
        ``len`` だけでは「同件数だがキー集合が異なる」状態 (例: 1 件抜けて 1 件余分) を
        検出できないため、set-equality でキー差異も検出する。

        Note: After clearing both caches (invariant violation), all subsequent requests will
        hit the API without cache, potentially causing rate limit spikes in the short term.
        """
        # O(1) fast path before O(n) set comparison:
        # サイズが異なれば invariant 違反確定
        # （同件数だがキー集合が異なる場合は下記 set-equality で検出）。
        invariant_violated = (
            len(self._etag_cache) != len(self._data_cache)
            or self._etag_cache.keys() != self._data_cache.keys()
        )
        if invariant_violated:
            # PII漏洩防止 (PR#347 review #3-2): キーパスは GitHub API endpoint
            # (例: /users/octocat, /repos/owner/name) を含み、SENSITIVE_KEYS の
            # redact 対象外。logger.error → Sentry 送信時のログ肥大・PII露出を
            # 抑えるため _MAX_CACHE_INVARIANT_LOG_KEYS 件に制限する。
            # query string は split("?")[0] で除去済み。
            etag_only_cache_keys = self._etag_cache.keys() - self._data_cache.keys()
            data_only_cache_keys = self._data_cache.keys() - self._etag_cache.keys()
            etag_only_count = len(etag_only_cache_keys)
            data_only_count = len(data_only_cache_keys)
            etag_only_keys = sorted(k.split("?")[0] for k in etag_only_cache_keys)[
                :_MAX_CACHE_INVARIANT_LOG_KEYS
            ]
            data_only_keys = sorted(k.split("?")[0] for k in data_only_cache_keys)[
                :_MAX_CACHE_INVARIANT_LOG_KEYS
            ]
            # 通常フローでは発生しない。発生した場合は実装バグの兆候として
            # Sentry に捕捉される logger.error を出力し、両キャッシュを clear して
            # 次回リクエストの fresh fetch に倒す（user request flow は維持）。
            self.logger.error(
                "cache_invariant_violation",
                etag_cache_size=len(self._etag_cache),
                data_cache_size=len(self._data_cache),
                etag_only_keys=etag_only_keys,
                data_only_keys=data_only_keys,
                etag_only_keys_truncated=etag_only_count > _MAX_CACHE_INVARIANT_LOG_KEYS,
                data_only_keys_truncated=data_only_count > _MAX_CACHE_INVARIANT_LOG_KEYS,
                action="cleared_both_caches",
            )
            self._etag_cache.clear()
            self._data_cache.clear()
            return  # clear() によりサイズ 0 → max_cache_entries 制限は達成済み（while ループ不要）
        excess = len(self._etag_cache) - (self.max_cache_entries - reserve)
        if excess > 0:
            # 削除件数を事前計算し islice でまとめて取得（毎反復 len() 再計算を回避, PR#347）。
            keys_to_evict = list(itertools.islice(self._etag_cache, excess))
            for key in keys_to_evict:
                self._etag_cache.pop(key, None)
                self._data_cache.pop(key, None)
            self.logger.info(
                "cache_entries_evicted",
                evicted_count=excess,
                current_size=len(self._etag_cache),
                max_size=self.max_cache_entries,
            )

    async def _request(  # noqa: C901 - HTTPプロトコル処理の最小必要分岐（4xxステータス, 5xxリトライ, タイムアウト, キャンセル等）のため許容 CC≈12
        self,
        method: str,
        endpoint: str,
        params: dict[str, str | int] | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """内部リクエストメソッド

        機能:
        - Rate Limit監視（X-RateLimit-Remaining < _RATE_LIMIT_WARNING_THRESHOLD で警告ログ）
        - Conditional Requests（ETag活用、304 Not Modified対応）
        - 5xx・timeout・NetworkError・RemoteProtocolError リトライ（指数バックオフ+ジッター）
        - 4xxエラー即失敗（NotFoundError, RateLimitError例外）
        - 例外情報の安全な保持（HTTPStatusError は URL+ステータスのみ保持した cause に再ラップ、response body 非露出）

        Args:
            method: HTTPメソッド（GET, POST等）
            endpoint: APIエンドポイント
            params: クエリパラメータ

        Returns:
            JSONレスポンス（dict or list[dict]）

        Raises:
            RuntimeError: クライアント未初期化（`async with` 未使用）
            NotFoundError: 404エラー
            RateLimitError: 403 Rate Limit超過 または 429 Too Many Requests
            GitHubServerError: 5xxエラー（リトライ上限後）
            GitHubAPIError: タイムアウト・NetworkError・RemoteProtocolError は再試行後の最終失敗、
                予期しないエラーは即失敗

        Note:
            max_retries は 5xx エラーと timeout / NetworkError / RemoteProtocolError の試行回数（初回含む合計）を制御する。
            unexpected エラーは再試行せず、1回目で GitHubAPIError へ変換する。
            X-RateLimit-Remaining ヘッダーが不正値の場合:
            - 監視パス: _RATE_LIMIT_FALLBACK_REMAINING（残量十分と見なし、rate_limit_low警告なし）
            - 403判定パス: _RATE_LIMIT_FORBIDDEN_FALLBACK（Rate Limit超過と判定せず、GitHubAPIError発生）
            いずれのパスでも不正値（ValueError）検出時は
            invalid_rate_limit_header warningを出力する。
            なお、ヘッダー自体が未設定（None）の場合は
            warningを出力せずフォールバック値を返す。
        """  # noqa: E501
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context.")

        cache_key = self._cache_key(endpoint, params)
        headers = self._prepare_headers(cache_key)

        for attempt in range(self.max_retries):
            retry_error_message: str | None = None
            unexpected_error_type: str | None = None
            http_status_response: httpx.Response | None = None
            try:
                response = await self._client.request(
                    method,
                    endpoint,
                    params=params,
                    headers=headers,
                )

                # Rate Limit監視
                remaining = self._parse_rate_limit_header(
                    response.headers, "X-RateLimit-Remaining", _RATE_LIMIT_FALLBACK_REMAINING
                )
                warning_reset_time = self._check_rate_limit_warning(response.headers, remaining)

                # ステータスコード処理
                if response.status_code == 304:
                    return self._handle_304_response(cache_key)

                if response.status_code == 404:
                    raise NotFoundError(f"Resource not found: {endpoint}") from None

                # 通常パス: raise_for_status()より前に429を検出してRateLimitErrorに変換
                if response.status_code == 429:
                    reset_time = (
                        warning_reset_time
                        if warning_reset_time is not None
                        else self._parse_rate_limit_header(
                            response.headers, "X-RateLimit-Reset", _RATE_LIMIT_RESET_FALLBACK
                        )
                    )
                    # PII漏洩防止: 例外チェーン経由の httpx URL/header 露出を抑制
                    # (defensive path との等価性維持: 403→RateLimitError 変換も from None)
                    raise RateLimitError(reset_time) from None

                if response.status_code == 403:
                    # 注: warning_reset_time は _check_rate_limit_warning が
                    # remaining < _RATE_LIMIT_WARNING_THRESHOLD (=10) のときのみ
                    # 非 None を返す (utils/github_client.py L75, L440-473)。
                    # 閾値変更時はこの reset_time が常に None になり _handle_403_response
                    # 側の Retry-After ヘッダー fallback パスに倒れる挙動になる。
                    # debug-only ログのため動作影響は限定的だが、依存関係を明示する。
                    self._handle_403_response(
                        response,
                        rate_remaining=remaining,
                        reset_time=warning_reset_time,
                    )
                elif response.status_code >= 500:
                    await self._handle_5xx_response(response, attempt, endpoint, method)
                    continue
                else:
                    response.raise_for_status()

                result_json = self._parse_json_response(response, endpoint)
                # PR#347 review #4-[9]: ETag cache 更新失敗を HTTP 層 unexpected_error
                # と分離。cache update 失敗はレスポンス返却を阻害してはならず (cache の
                # 副作用) かつ専用イベントで観測性を確保する。HTTP 層 unexpected_error
                # は retry/エラー判定の対象だが、本イベントは warning 止まり。
                try:
                    self._update_etag_cache(cache_key, response, result_json)
                except RecursionError:
                    # RecursionError も Exception 派生のため、再raise しないと下流の
                    # except Exception に捕捉されサイレント隠蔽される（sentry_init と同一方針）。
                    # 致命的エラーとして必ず再raise（fail-fast）。
                    raise
                except MemoryError:
                    # MemoryError は Exception 派生のため、再raise しないと下流の
                    # except Exception に捕捉されサイレント隠蔽される。
                    # 致命的エラーとして必ず再raise（fail-fast）。
                    raise
                except Exception as cache_exc:  # noqa: BLE001
                    self.logger.warning(
                        "etag_cache_update_failed",
                        endpoint=endpoint,
                        method=method,
                        error_type=type(cache_exc).__name__,
                        error_module=type(cache_exc).__module__,
                    )

                return result_json

            except GitHubAPIError:
                raise

            except httpx.HTTPStatusError as e:
                # except外raiseパターン: e.response（PII含有）が __context__ に残存するのを防止
                # e.response を退避してから except を抜け、except 外で処理・raise する
                http_status_response = e.response

            except httpx.TimeoutException as e:
                # PII漏洩防止: str(e)はURL/host:port等を含む可能性があるためログから除外
                # (unexpected_errorパスと同じ方針:
                #  error_type + error_module + error_context で診断情報を提供)
                retry_error_message = f"Request timeout: {type(e).__qualname__}"
                await self._log_and_sleep_for_retry(
                    event="request_timeout",
                    error_context="timeout",
                    error=e,
                    endpoint=endpoint,
                    method=method,
                    attempt=attempt,
                )
                if attempt < self.max_retries - 1:
                    continue

            except (httpx.NetworkError, httpx.RemoteProtocolError) as e:  # fmt: skip
                # PII漏洩防止: str(e)はURL/host:port等を含む可能性があるためログから除外
                retry_error_message = f"Network error: {type(e).__qualname__}"
                await self._log_and_sleep_for_retry(
                    event="request_network_error",
                    error_context="network",
                    error=e,
                    endpoint=endpoint,
                    method=method,
                    attempt=attempt,
                )
                if attempt < self.max_retries - 1:
                    continue

            except ASYNC_FATAL_EXCEPTIONS:
                # システム例外は再発生
                # - KeyboardInterrupt/SystemExit: graceful shutdown対応
                # - MemoryError: K8s OOMKilled等のリソース枯渇検知
                # - CancelledError: asyncioタスクキャンセル伝播
                raise

            except httpx.ResponseNotRead:
                # ResponseNotRead は response body 未読の httpx 正常系制御例外。
                # unexpected_error に包まず、そのまま伝播させる。
                raise

            except Exception as e:
                unexpected_error_type = type(e).__qualname__
                error_module = type(e).__module__
                self.logger.error(
                    "unexpected_error",
                    endpoint=endpoint,
                    method=method,
                    error_type=unexpected_error_type,
                    error_module=error_module,
                    error_context="unexpected",
                )
                # except外raiseパターン: 予期しない例外が__context__に残存するのを防止

            if http_status_response is not None:
                # PII漏洩防止: __context__ を None に保つため except 外で処理・raise
                # (httpx.HTTPStatusError.response は response body + request URL を保持するため)
                #
                # PR#347 review #4-[10]: 5xx のみ _handle_5xx_response でリトライ制御が必要なため
                # 個別分岐を維持。404/429/403/その他 は _handle_http_status_error に一本化。
                if http_status_response.status_code >= 500:
                    # 防御的パス: 5xxをhttpx.HTTPStatusErrorとして受信した場合、通常パスと同等に処理
                    await self._handle_5xx_response(http_status_response, attempt, endpoint, method)
                    continue
                self._handle_http_status_error(http_status_response, endpoint, method)

            if retry_error_message is not None:
                # PII漏洩防止 (__context__): active exception context の外で raise して
                # httpx.TimeoutException / httpx.NetworkError / httpx.RemoteProtocolError の
                # URL/host:port等を例外チェーンに残さない
                raise GitHubAPIError(retry_error_message) from None

            if unexpected_error_type is not None:
                # PII漏洩防止 (__cause__): catch-all例外はURL/host:port等のPIIを含む可能性があるため
                # 例外チェーンを切断し、診断情報は非PIIのログフィールドに限定する。
                raise GitHubAPIError(f"Unexpected error: {unexpected_error_type}") from None

        # リトライ上限到達フォールバック: max_retries 回連続で
        # retry_error_message / unexpected_error_type が None のまま for ループを
        # 抜けた場合に到達する。通常は最後の attempt で上記いずれかが populate
        # されて先行 raise されるが、例外捕捉と raise の境界条件 (例: continue 後の
        # ループ終了タイミング) で到達しうるため、型チェッカー対策と防御的 fallback
        # を兼ねて常時 raise を維持する。`from None` で PII を含む例外チェーンを切断。
        raise GitHubServerError(f"Failed after {self.max_retries} attempts") from None
