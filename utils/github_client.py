"""GitHub Async APIクライアント"""

import re
from types import TracebackType
from typing import Any, NoReturn, Self

import httpx

from utils.exceptions import ASYNC_FATAL_EXCEPTIONS
from utils.github_error_handler import (
    GitHubAPIError,
    GitHubServerError,
    NotFoundError,
    RateLimitError,
)
from utils.github_error_handler import (
    _handle_5xx_response as handle_5xx_response,
)
from utils.github_error_handler import (
    _handle_403_response as handle_403_response,
)
from utils.github_error_handler import (
    _handle_http_status_error as handle_http_status_error,
)
from utils.github_error_handler import (
    _parse_json_response as parse_json_response,
)
from utils.github_etag_cache import GitHubETagCache
from utils.github_rate_limit import (
    _RATE_LIMIT_FALLBACK_REMAINING,
    _RATE_LIMIT_RESET_FALLBACK,
)
from utils.github_rate_limit import (
    _check_rate_limit_warning as check_rate_limit_warning,
)
from utils.github_rate_limit import (
    _log_and_sleep_for_retry as log_and_sleep_for_retry,
)
from utils.github_rate_limit import (
    _parse_rate_limit_header as parse_rate_limit_header,
)
from utils.http_helpers import log_error_with_stderr_fallback
from utils.logger import get_logger

# =============================================================================
# 入力バリデーション（OWASP A03:2021 - Injection対策）
# =============================================================================

# GitHub username仕様: 1-39文字、英数字・ハイフン、先頭は英数字
GITHUB_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38}$")
# GitHub repository名仕様: 1-100文字、英数字・ドット・ハイフン・アンダースコア
GITHUB_REPO_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{1,100}$")


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
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent
        self._client: httpx.AsyncClient | None = None
        self.logger = get_logger(__name__)
        # ETag/data キャッシュは GitHubETagCache が排他所有する（facade は保持と委譲のみ）。
        # max_cache_entries の下限バリデーション（1 未満で ValueError）も cache 側で実施する。
        self._cache = GitHubETagCache(max_cache_entries, logger=self.logger)

    @property
    def max_cache_entries(self) -> int:
        """ETag/dataキャッシュの最大エントリ数（GitHubETagCache に委譲）。"""
        return self._cache.max_cache_entries

    @property
    def _etag_cache(self) -> dict[str, str]:
        """ETagキャッシュ実体への読み取り用参照（書込は GitHubETagCache に一元化）。

        既存テストの白箱アクセス互換のための暫定アクセサ（GW4 mirror テスト移行後に削除予定）。
        """
        return self._cache._etag_cache

    @property
    def _data_cache(self) -> dict[str, dict[str, Any] | list[dict[str, Any]]]:
        """データキャッシュ実体への読み取り用参照（書込は GitHubETagCache に一元化）。

        既存テストの白箱アクセス互換のための暫定アクセサ（GW4 mirror テスト移行後に削除予定）。
        """
        return self._cache._data_cache

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
        """Delegate retry logging and delay handling to the rate-limit module."""
        await log_and_sleep_for_retry(
            event=event,
            error_context=error_context,
            error=error,
            endpoint=endpoint,
            method=method,
            attempt=attempt,
            max_retries=self.max_retries,
            logger=self.logger,
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

    async def _close_async_client(
        self,
        body_exc_type: type[BaseException] | None,
        *,
        suppress_unexpected: bool = False,
    ) -> None:
        """``__aexit__`` と ``aclose()`` で共有する close 処理.

        AsyncAPIClient._close_async_client() と対称の集約ヘルパー。AsyncGitHubClient は
        AsyncAPIClient のヘルパーを継承しない（別クラス階層）ため自前で定義し、
        ``__aexit__`` / ``aclose()`` 間の close ロジック重複を解消する（DRY, PR#347）。

        Args:
            body_exc_type: ``__aexit__`` 経路では body 内で発生した例外型（無しなら ``None``）。
                ``aclose()`` 直接呼び出し経路では常に ``None``。予期しない close 例外捕捉時、
                ``has_body_exception = body_exc_type is not None`` を判定材料とし、body 例外の
                上書き防止のため ``None`` の場合のみ実装バグとして bare ``raise`` で再送出する。
            suppress_unexpected: ``True`` の場合、予期しない close 例外を error ログのみ記録して
                握りつぶす（re-raise しない）。``aclose()`` で ``True`` を渡し finally ブロック等
                での安全な呼び出しを保証する。``__aexit__`` 経路では ``False``（デフォルト）のまま
                ``has_body_exception`` ロジックによる従来の re-raise 判定を維持する。
        """
        if self._client is None:
            return
        try:
            await self._client.aclose()
        except (httpx.CloseError, OSError) as close_exc:
            # 既知のクローズ時例外 — warning のみ（body 例外を上書きしない）。
            # error_type + error_module で third-party 例外の起点モジュールを識別可能にする。
            self._client = None
            self.logger.warning(
                "async_github_client_aclose_failed",
                error_type=type(close_exc).__name__,
                error_module=type(close_exc).__module__,
            )
        except ASYNC_FATAL_EXCEPTIONS:
            # システム致命例外（MemoryError/RecursionError/KeyboardInterrupt/SystemExit/
            # asyncio.CancelledError）は再raise して fail-fast を維持する。MemoryError/
            # RecursionError は Exception 派生のため、明示捕捉しないと下流の except Exception に
            # （has_body_exception=True 時）捕捉されサイレント隠蔽される。KeyboardInterrupt/
            # SystemExit/CancelledError は BaseException 直系で except Exception の境界外（素通り）
            # だが、_client=None 設定の一貫性のため本句で先取りする。
            # NOTE: 本クラスは _request パス（utils.exceptions の ASYNC_FATAL_EXCEPTIONS 方針）と
            # 同一の定数を close 経路でも使用する。一方 AsyncAPIClient._close_async_client は
            # close 文脈で (MemoryError, RecursionError) のみを使う別方針（CancelledError 等は
            # BaseException 直系として素通りさせる設計）であり、両クラスの close ヘルパーは
            # この点で対称ではない（PR#347 Q-4）。
            # 他の close 経路（CloseError/OSError 句・else 節）と対称に _client=None を設定し、
            # 再呼び出し時のダブル aclose を防ぐ（PR#347 CQ-1）。
            self._client = None
            raise
        except Exception as close_exc:  # noqa: BLE001
            # 予期しない例外（AttributeError, RuntimeError 等の実装バグ可能性）。
            # RecursionError / MemoryError は上の ASYNC_FATAL_EXCEPTIONS 句で
            # 先取り済み（fail-fast）。
            # logger.error 記録 + 失敗時 stderr フォールバック。ロガー自体の例外が close_exc /
            # body 例外を隠蔽するのを防ぐ（PR#347 B-3）。utils.http_helpers と共通の module-level
            # ヘルパーで stderr フォールバックの重複を解消する（PR#347 Q-8 DRY）。
            if suppress_unexpected:
                # aclose() 直接呼び出し経路: finally ブロック等での安全な呼び出しを保証するため、
                # 伝播中の例外を上書きしないよう常に抑制し error ログで本番監視対象にする
                # （PR#347 SF-3）。suppress_unexpected=True は has_body_exception より優先評価。
                # suppress 経路でも状態一貫性のため _client=None を設定し、aclose 失敗後の
                # 壊れたクライアント再利用を防止する（成功時 else 節と同一方針）。
                self._client = None
                log_error_with_stderr_fallback(
                    self.logger,
                    "github_client",
                    "aclose",
                    close_exc,
                    "async_github_client_aclose_unexpected_error",
                    error_type=type(close_exc).__name__,
                    error_module=type(close_exc).__module__,
                    action="suppressed_standalone_aclose",
                    exc_info=True,  # スタックトレースをログに残す
                )
            else:
                # __aexit__ 経路（context manager）: 従来の has_body_exception ロジックを維持。
                # SF-2: close_exc は body 例外を上書きしないため __context__ チェーンは切断される。
                # 代わりに body 例外の型名（body_exception_type）を同一ログイベント内に記録し、
                # close 失敗と body 例外の対応関係を追跡可能にする（PII 非含: __qualname__ は
                # クラス名のみ）。本経路は _client=None を設定しない（従来 __aexit__ 挙動を保持）。
                has_body_exception = body_exc_type is not None
                log_error_with_stderr_fallback(
                    self.logger,
                    "github_client",
                    "aclose",
                    close_exc,
                    "async_github_client_aclose_unexpected_error",
                    error_type=type(close_exc).__name__,
                    error_module=type(close_exc).__module__,
                    has_body_exception=has_body_exception,
                    action=(
                        "suppressed_due_to_body_exception" if has_body_exception else "re_raised"
                    ),
                    body_exception_type=(
                        body_exc_type.__qualname__ if body_exc_type is not None else None
                    ),
                    exc_info=True,  # スタックトレースをログに残す
                )
                # body 例外がない場合のみ実装バグとして re-raise。body 例外がある場合は本質的
                # 原因の上書きを防ぐため raise しない。bare ``raise`` で active exception の
                # traceback を完全保持（``raise close_exc`` への回帰防止: 余分な frame 不追加）。
                if not has_body_exception:
                    raise
        else:
            # ダブルクローズ防止: logger.info より先に None をセットする。logger.info が例外を
            # 投げても _client=None が確定済みのため再呼び出し時のガードで空振りし aclose 二重
            # 実行を防ぐ（AsyncAPIClient._close_async_client と同一順序, PR#347 B-2）。
            self._client = None
            self.logger.info("async_github_client_closed")

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """非同期コンテキストマネージャーの終了処理。"""
        # close ロジックは _close_async_client() ヘルパーに集約（AsyncAPIClient と対称）。
        # body 例外型を渡し、has_body_exception ロジックで close 例外の re-raise を判定する。
        await self._close_async_client(exc_type)

    async def aclose(self) -> None:
        """明示的な非同期クローズ（``async with`` を使わない finally 解放経路用）.

        ``AsyncAPIClient.aclose()`` と対称。``__aexit__`` と同一の close ロジックを
        ``_close_async_client()`` ヘルパーに集約済み。body 例外コンテキストを持たないため
        ``body_exc_type=None`` を渡し、予期しない close 例外は ``suppress_unexpected=True`` で
        握りつぶす（finally ブロック内で他例外を上書きしないため）。全経路で ``_client=None``
        を設定し、再呼び出し時のダブル aclose を防ぐ。
        """
        await self._close_async_client(None, suppress_unexpected=True)

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
                            パラメータシリアライズ失敗（リトライなし）

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
                            パラメータシリアライズ失敗（リトライなし）

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

    def _parse_rate_limit_header(
        self,
        headers: httpx.Headers,
        name: str,
        default: int,
    ) -> int:
        """Delegate rate-limit header parsing to the rate-limit module."""
        return parse_rate_limit_header(headers, name, default, logger=self.logger)

    def _prepare_headers(self, cache_key: str) -> dict[str, str]:
        """Delegate If-None-Match header construction to the ETag cache."""
        return self._cache._prepare_headers(cache_key)

    def _check_rate_limit_warning(
        self,
        response_headers: httpx.Headers,
        remaining: int,
    ) -> int | None:
        """Delegate low-quota detection to the rate-limit module."""
        return check_rate_limit_warning(response_headers, remaining, logger=self.logger)

    def _handle_304_response(self, cache_key: str) -> dict[str, Any] | list[dict[str, Any]]:
        """Delegate 304 cached-data retrieval to the ETag cache."""
        return self._cache._handle_304_response(cache_key)

    def _handle_403_response(
        self,
        response: httpx.Response,
        *,
        rate_remaining: int | None = None,
        reset_time: int | None = None,
    ) -> NoReturn:
        """Delegate 403 classification to the error-handler module."""
        handle_403_response(
            response,
            logger=self.logger,
            rate_remaining=rate_remaining,
            reset_time=reset_time,
        )

    async def _handle_5xx_response(
        self,
        response: httpx.Response,
        attempt: int,
        endpoint: str,
        method: str,
    ) -> None:
        """Delegate 5xx retry handling to the error-handler module."""
        await handle_5xx_response(
            response,
            attempt,
            endpoint,
            method,
            max_retries=self.max_retries,
            logger=self.logger,
        )

    def _parse_json_response(
        self,
        response: httpx.Response,
        endpoint: str,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Delegate PII-safe JSON parsing to the error-handler module."""
        return parse_json_response(response, endpoint, logger=self.logger)

    def _handle_http_status_error(
        self,
        response: httpx.Response,
        endpoint: str,
        method: str,
    ) -> NoReturn:
        """Delegate HTTP status classification to the error-handler module."""
        handle_http_status_error(response, endpoint, method, logger=self.logger)

    def _update_etag_cache(
        self,
        cache_key: str,
        response: httpx.Response,
        result_json: dict[str, Any] | list[dict[str, Any]],
    ) -> None:
        """Delegate ETag/data cache updates to the ETag cache."""
        self._cache._update_etag_cache(cache_key, response, result_json)

    @staticmethod
    def _cache_key(endpoint: str, params: dict[str, str | int] | None = None) -> str:
        """Delegate cache-key construction to the ETag cache."""
        return GitHubETagCache._cache_key(endpoint, params)

    def _enforce_cache_limit(self, reserve: int = 0) -> None:
        """Delegate cache size enforcement to the ETag cache."""
        self._cache._enforce_cache_limit(reserve)

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
        if self._client is None:
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
                    # remaining < RATE_LIMIT_WARNING_THRESHOLD (=10) のときのみ
                    # 非 None を返す (utils/github_rate_limit.py)。
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
                # は retry/エラー判定の対象だが、本イベントは error ログで監視対象にする。
                try:
                    self._update_etag_cache(cache_key, response, result_json)
                except (MemoryError, RecursionError):  # fmt: skip
                    # MemoryError / RecursionError も Exception 派生のため、再raise しないと
                    # 下流の except Exception に捕捉されサイレント隠蔽される（sentry_init と
                    # 同一方針）。致命的エラーとして必ず再raise（fail-fast, PR#347 #1）。
                    raise
                except Exception as cache_exc:  # noqa: BLE001
                    # logger.error 記録 + 失敗時 stderr フォールバック（PR#347 Q-12）。
                    # cache 更新失敗はレスポンス返却を阻害しないが、ロガー自体の失敗で
                    # 観測性が完全に失われるのを防ぐ。utils.http_helpers と共通の DRY ヘルパー使用。
                    log_error_with_stderr_fallback(
                        self.logger,
                        "github_client",
                        "etag_cache_update",
                        cache_exc,
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
