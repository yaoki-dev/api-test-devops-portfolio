"""GitHub API非同期クライアント

学習目標:
- GitHub REST API v3の実務的活用（Rate Limit管理、Conditional Requests）
- 非同期HTTP通信の最適化（ETag活用）
- API制約への対応戦略（認証なし60 req/h → 認証あり5000 req/h拡張可能設計）
"""

import asyncio
import json
import re
from datetime import UTC, datetime
from typing import Any, NoReturn, Self, cast

import httpx

from utils.api_client import APIClientError, exponential_backoff_with_jitter
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
_MAX_ERROR_RESPONSE_TEXT = 200  # エラーメッセージ: ログ肥大・センシティブデータ漏洩防止の上限文字数


# =============================================================================
# 例外クラス
# =============================================================================


class GitHubAPIError(APIClientError):
    """GitHub API基底例外（APIClientErrorを継承し統一的なエラーハンドリングを実現）"""


class RateLimitError(GitHubAPIError):
    """Rate Limit超過エラー（403 Forbidden）"""

    def __init__(self, reset_time: int):
        self.reset_time = reset_time
        super().__init__(f"Rate limit exceeded. Reset at {reset_time}")


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
    - リトライロジック（5xxエラーのみ、指数バックオフ+ジッター）
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
    ):
        """AsyncGitHubClientの初期化

        Args:
            timeout: リクエストタイムアウト（秒）
            max_retries: 最大試行回数（5xxエラーのみ、初回含む）
            user_agent: User-Agentヘッダー（GitHub要求事項）

        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent
        self._client: httpx.AsyncClient | None = None
        self._etag_cache: dict[str, str] = {}  # URL -> ETag
        # URL -> response data（304レスポンス時のキャッシュ返却用）
        self._data_cache: dict[str, dict[str, Any] | list[dict[str, Any]]] = {}
        self.logger = get_logger(__name__)

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

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """非同期コンテキストマネージャーの終了処理"""
        if self._client:
            await self._client.aclose()
            self.logger.info("AsyncGitHubClient closed")

    async def get_user(self, username: str) -> dict[str, Any]:
        """ユーザー情報取得

        Args:
            username: GitHubユーザー名

        Returns:
            ユーザー情報（name, bio, public_repos等）

        Raises:
            ValueError: 無効なユーザー名
            NotFoundError: ユーザーが存在しない
            RateLimitError: Rate Limit超過

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

        Example:
            >>> repos = await client.get_repos("octocat", sort="updated")
            >>> print(repos[0]["name"])  # 最新更新のリポジトリ

        """
        validate_github_username(username)
        params = {"sort": sort, "per_page": per_page}
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

    def _prepare_headers(self, endpoint: str) -> dict[str, str]:
        """ETagキャッシュが存在する場合に If-None-Match ヘッダーを含む dict を返す。

        Conditional Requests対応。
        """
        headers: dict[str, str] = {}
        if endpoint in self._etag_cache:
            headers["If-None-Match"] = self._etag_cache[endpoint]
        return headers

    def _check_rate_limit_warning(
        self,
        response_headers: httpx.Headers,
        remaining: int,
    ) -> None:
        """RateLimit残量が閾値未満の場合に警告ログを出力する。"""
        if remaining < _RATE_LIMIT_WARNING_THRESHOLD:
            reset_time = self._parse_rate_limit_header(
                response_headers, "X-RateLimit-Reset", _RATE_LIMIT_RESET_FALLBACK
            )
            reset_dt = datetime.fromtimestamp(reset_time, tz=UTC)
            self.logger.warning(
                "rate_limit_low",
                remaining=remaining,
                reset_time=reset_dt.isoformat(),
            )

    def _handle_304_response(self, endpoint: str) -> dict[str, Any] | list[dict[str, Any]]:
        """304 Not Modified: キャッシュデータを返却する。キャッシュミス時はエラー。"""
        if endpoint in self._data_cache:
            return self._data_cache[endpoint]
        # キャッシュミス時（理論上発生しない: ETagあり=キャッシュあり）
        # Fail-fast: キャッシュ不整合は実装バグの証拠
        self.logger.error(
            "cache_miss_on_304",
            endpoint=endpoint,
            hint="ETag存在時のキャッシュミスは実装バグ",
            etag=self._etag_cache.get(endpoint),
        )
        raise GitHubAPIError(
            f"Cache inconsistency: 304 response without cached data for {endpoint}"
        )

    def _handle_403_response(self, response: httpx.Response) -> NoReturn:
        """403エラー処理: Rate Limit超過 vs その他の403を判別して raise する。"""
        # フォールバック -1 = 不正値時はRate Limit超過と判定せずGitHubAPIErrorへ
        rate_remaining = self._parse_rate_limit_header(
            response.headers, "X-RateLimit-Remaining", _RATE_LIMIT_FORBIDDEN_FALLBACK
        )
        if rate_remaining == 0:
            # Rate Limit超過確定
            reset_time = self._parse_rate_limit_header(
                response.headers, "X-RateLimit-Reset", _RATE_LIMIT_RESET_FALLBACK
            )
            raise RateLimitError(reset_time)
        # その他の403エラー（IPブロック、アクセス権限不足等）
        error_message = "Access forbidden"
        try:
            parsed = response.json()
            if isinstance(parsed, dict):
                raw_message = parsed.get("message", error_message)
                if isinstance(raw_message, str):
                    error_message = raw_message[:_MAX_ERROR_RESPONSE_TEXT]
        except json.JSONDecodeError as parse_err:
            # JSONパース失敗は想定内（非JSON応答の可能性）— 削除禁止 (CONTEXT.md specifics)
            self.logger.warning("failed_to_parse_403_message", error=str(parse_err))
        raise GitHubAPIError(f"Access forbidden: {error_message}")

    async def _handle_5xx_response(
        self,
        response: httpx.Response,
        attempt: int,
    ) -> None:
        """5xxエラーのリトライ制御。最終試行なら raise、継続なら return（None）。

        - Returns: None — リトライ継続
        - Raises: GitHubServerError — リトライ上限到達
        """
        if attempt < self.max_retries - 1:
            delay = exponential_backoff_with_jitter(attempt, base_delay=2.0)
            self.logger.warning(
                "retrying_server_error",
                attempt=attempt + 1,
                max_retries=self.max_retries,
                delay=delay,
                status_code=response.status_code,
            )
            await asyncio.sleep(delay)
            return  # 呼び出し元で continue
        raise GitHubServerError(
            f"Server error: {response.status_code} after {self.max_retries} attempts",
        )

    def _parse_json_response(
        self,
        response: httpx.Response,
        endpoint: str,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """JSONレスポンスをパースする。破損JSON時はGitHubAPIErrorを発生。"""
        try:
            return cast(
                "dict[str, Any] | list[dict[str, Any]]",
                response.json(),
            )
        except json.JSONDecodeError as e:
            self.logger.error("json_decode_error", endpoint=endpoint, error=str(e))
            raise GitHubAPIError(f"Invalid JSON response: {e}") from e

    def _handle_http_status_error(
        self,
        e: httpx.HTTPStatusError,
    ) -> NoReturn:
        """4xxエラーを GitHubAPIError に変換して raise する。

        通常フローでは 5xx は _handle_5xx_response() で先に処理済みのため 4xx のみが渡る。
        httpx.HTTPStatusError として直接 5xx が発生した場合も、呼び出し元の except ブロックが
        先に status_code >= 500 を判定して _handle_5xx_response() へ分岐させるため、
        このメソッドへの 5xx 到達は想定しない。

        設計上の制約: `_cause` は `from e`（元の httpx.HTTPStatusError）ではなく
        新規生成した Exception を使用する。理由: `from e` にすると
        httpx.HTTPStatusError インスタンス（response body を含む可能性）が
        __cause__ に残り、Sentry 等の APM ツール経由でセンシティブデータが
        漏洩するリスクがある。コーディング規約 Section 5
        「from e でチェーン維持」の例外として意図的に採用。
        """
        _cause = Exception(
            f"httpx.HTTPStatusError: HTTP {e.response.status_code} {e.request.url.path}"
        )
        self.logger.warning(
            "http_status_error",
            status_code=e.response.status_code,
            endpoint=e.request.url.path,
            method=e.request.method,
            body_preview=e.response.text[:_MAX_ERROR_RESPONSE_TEXT],
        )
        raise GitHubAPIError(f"HTTP {e.response.status_code} error") from _cause

    def _update_etag_cache(
        self,
        endpoint: str,
        response: httpx.Response,
        result_json: dict[str, Any] | list[dict[str, Any]],
    ) -> None:
        """ETagとデータキャッシュを同時更新する。

        asyncio シングルスレッド環境で競合なく両キャッシュを更新する。
        （データベーストランザクション的なアトミック操作ではない）
        """
        if "ETag" in response.headers:
            self._etag_cache[endpoint] = response.headers["ETag"]
            self._data_cache[endpoint] = result_json

    async def _request(  # noqa: C901 - HTTPプロトコル処理の最小必要分岐（4xxステータス, 5xxリトライ, タイムアウト, キャンセル等）のため許容 CC≈12
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """内部リクエストメソッド

        機能:
        - Rate Limit監視（X-RateLimit-Remaining < _RATE_LIMIT_WARNING_THRESHOLD で警告ログ）
        - Conditional Requests（ETag活用、304 Not Modified対応）
        - 5xxエラーリトライ（指数バックオフ+ジッター）
        - 4xxエラー即失敗（NotFoundError, RateLimitError例外）
        - 例外情報の安全な保持（HTTPStatusError は URL+ステータスのみ保持した cause に再ラップ、response body 非露出）

        Args:
            method: HTTPメソッド（GET, POST等）
            endpoint: APIエンドポイント
            params: クエリパラメータ

        Returns:
            JSONレスポンス（dict or list[dict]）

        Raises:
            NotFoundError: 404エラー
            RateLimitError: 403 Rate Limit超過
            GitHubServerError: 5xxエラー（リトライ上限後）
            GitHubAPIError: タイムアウト等の予期しないエラー

        Note:
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

        headers = self._prepare_headers(endpoint)

        for attempt in range(self.max_retries):
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
                self._check_rate_limit_warning(response.headers, remaining)

                # ステータスコード処理
                if response.status_code == 304:
                    return self._handle_304_response(endpoint)

                if response.status_code == 404:
                    raise NotFoundError(f"Resource not found: {endpoint}")

                if response.status_code == 403:
                    self._handle_403_response(response)

                if response.status_code >= 500:
                    await self._handle_5xx_response(response, attempt)
                    continue  # _handle_5xx_response がraiseしない場合（非最終試行）はリトライ継続

                response.raise_for_status()

                result_json = self._parse_json_response(response, endpoint)
                self._update_etag_cache(endpoint, response, result_json)

                return result_json

            except GitHubAPIError:
                raise

            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500:
                    # 防御的パス: 5xxをhttpx.HTTPStatusErrorとして受信した場合、通常パスと同等に処理
                    await self._handle_5xx_response(e.response, attempt)
                    continue  # _handle_5xx_response がraiseしない場合（非最終試行）はリトライ継続
                self._handle_http_status_error(e)

            except httpx.TimeoutException as e:
                self.logger.warning("request_timeout", endpoint=endpoint, method=method)
                raise GitHubAPIError(f"Request timeout: {e}") from e

            except KeyboardInterrupt, SystemExit, MemoryError, asyncio.CancelledError:
                # システム例外は再発生
                # - KeyboardInterrupt/SystemExit: graceful shutdown対応
                # - MemoryError: K8s OOMKilled等のリソース枯渇検知
                # - CancelledError: asyncioタスクキャンセル伝播
                raise

            except Exception as e:
                self.logger.error(
                    "unexpected_error",
                    endpoint=endpoint,
                    method=method,
                    error=str(e),
                )
                raise GitHubAPIError(f"Unexpected error: {e}") from e

        # リトライ上限到達（ここに到達することはないはずだが、型チェッカー対策）
        raise GitHubServerError(f"Failed after {self.max_retries} attempts")


# =============================================================================
# 学習ポイント:
#
# 1. GitHub API v3の実務的活用:
#    - Rate Limit管理: X-RateLimit-Remaining監視、警告ログ出力
#    - Conditional Requests: ETag活用で304 Not Modified時Rate Limit消費なし
#    - 認証拡張性: Personal Access Tokenで60 req/h → 5000 req/h拡張可能
#
# 2. 非同期HTTP通信の最適化:
#    - async/awaitパターンによる非ブロッキングI/O
#    - ETagキャッシュによるネットワーク帯域削減
#    - 指数バックオフ+ジッターによる過負荷防止
#
# 3. エラーハンドリング戦略:
#    - 階層的な例外設計（GitHubAPIError基底 + 4派生例外）
#    - HTTPステータスコード別処理（4xx即失敗、5xxリトライ）
#    - 例外チェーン（HTTPStatusError は URL+ステータスのみ cause に再ラップ）
#
# 4. ロギング・監視:
#    - structlog構造化ロギング（JSON形式、フィールド検索可能）
#    - Rate Limit警告（残リクエスト数が _RATE_LIMIT_WARNING_THRESHOLD 未満で通知）
#    - リトライログ（試行回数、遅延時間、ステータスコード記録）
# =============================================================================
