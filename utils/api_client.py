"""基本的な同期HTTPAPIクライアント

学習目標:
- HTTPクライアントの設計パターン
- エラーハンドリング戦略
- リトライロジックの実装
- 設定管理との統合
"""

import asyncio
import json
import random
import time
from types import TracebackType
from typing import Any, Self

import httpx

from config.settings import settings
from utils.logger import get_logger


def exponential_backoff_with_jitter(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter_percent: float = 0.3,
) -> float:
    """指数バックオフ + 30%ジッター計算

    Args:
        attempt: 現在のリトライ回数（0始まり）
        base_delay: 基本遅延時間（秒）
        max_delay: 最大遅延時間（秒）
        jitter_percent: ジッター率（デフォルト30%）

    Returns:
        計算された遅延時間（秒、最小0.1秒）

    """
    # 指数バックオフ計算
    delay = min(base_delay * (2**attempt), max_delay)
    # ±30%のジッター追加（リトライ間隔用、暗号用途ではない）
    jitter = delay * jitter_percent
    delay = delay + random.uniform(-jitter, jitter)  # noqa: S311
    # 最小値保証
    return max(0.1, delay)


# =============================================================================
# 例外クラス
# =============================================================================


class APIClientError(Exception):
    """APIクライアント基底例外"""


class APIConnectionError(APIClientError):
    """API接続エラー"""


class APITimeoutError(APIClientError):
    """APIタイムアウトエラー"""


class APIHTTPError(APIClientError):
    """HTTPステータスエラー"""

    def __init__(self, message: str, status_code: int, response: httpx.Response | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class APIRetryError(APIClientError):
    """リトライ上限エラー"""


class APIJSONDecodeError(APIClientError):
    """JSONパースエラー"""

    def __init__(self, message: str, response: httpx.Response | None = None):
        super().__init__(message)
        self.response = response


def _safe_parse_json(response: httpx.Response) -> Any:
    """レスポンスJSONを安全にパース

    Args:
        response: HTTPレスポンスオブジェクト

    Returns:
        パースされたJSONデータ

    Raises:
        APIJSONDecodeError: JSONパース失敗時

    """
    try:
        return response.json()
    except json.JSONDecodeError as e:
        raise APIJSONDecodeError(
            f"Failed to parse JSON response: {e}",
            response=response,
        ) from e


def _map_request_error(e: httpx.RequestError | httpx.InvalidURL) -> APIClientError:
    """httpxネットワーク例外をカスタム例外にマッピング

    Args:
        e: httpx.RequestError または そのサブクラス

    Returns:
        適切なAPIClientErrorサブクラス

    Raises:
        APIClientError: 非リトライ可能エラー（TooManyRedirects, InvalidURL）

    Note:
        httpx.RequestError階層:
        - TimeoutException (ConnectTimeout, ReadTimeout) → リトライ可能
        - ConnectError → リトライ可能
        - NetworkError → リトライ可能
        - TooManyRedirects, InvalidURL → 非リトライ（即座にraise）

    """
    # Non-retryable errors - raise immediately (no point in retrying)
    if isinstance(e, httpx.TooManyRedirects | httpx.InvalidURL):
        raise APIClientError(f"Non-retryable request error: {e}") from e

    # Retryable errors
    if isinstance(e, httpx.TimeoutException):
        return APITimeoutError(f"Request timeout: {e}")
    if isinstance(e, httpx.ConnectError):
        return APIConnectionError(f"Connection failed: {e}")
    # NetworkError, etc. - retryable network issues
    return APIConnectionError(f"Network error: {e}")


# =============================================================================
# 基本HTTPクライアント
# =============================================================================


class SyncAPIClient:
    """基本的な同期HTTPクライアント

    学習目標:
    - クライアント設計の基本パターン
    - 設定との統合方法
    - エラーハンドリングの実装
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        retry_count: int | None = None,
        retry_delay: float | None = None,
        headers: dict[str, str] | None = None,
    ):
        """Args:
        base_url: APIのベースURL（設定から自動取得可能）
        timeout: リクエストタイムアウト（秒）
        retry_count: リトライ回数
        retry_delay: リトライ間隔（秒）
        headers: 追加HTTPヘッダー

        """
        # 設定から値を取得（引数で上書き可能）
        # NOTE: retry_count=0, retry_delay=0.0 は有効な設定値のため is not None で判定
        self.base_url = base_url or settings.api.base_url
        self.timeout = timeout or settings.api.timeout
        self.retry_count = retry_count if retry_count is not None else settings.api.retry_count
        self.retry_delay = retry_delay if retry_delay is not None else settings.api.retry_delay

        # デフォルトヘッダーの設定
        self.default_headers = {
            "User-Agent": settings.api.user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if headers:
            self.default_headers.update(headers)

        # ロガーの初期化（structlog統合）
        self.logger = get_logger(__name__)

        # HTTPクライアントの初期化
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self.default_headers,
            limits=httpx.Limits(max_connections=settings.api.max_connections),
        )

        self.logger.info("api_client_initialized", base_url=self.base_url)

    def __enter__(self) -> Self:
        """コンテキストマネージャーのエントリー"""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """コンテキストマネージャーの終了処理"""
        self.close()

    def close(self) -> None:
        """クライアントのクローズ"""
        if self._client:
            self._client.close()
            self.logger.info("api_client_closed")

    def _make_request_with_retry(self, method: str, endpoint: str, **kwargs: Any) -> httpx.Response:
        """リトライ機能付きHTTPリクエスト実行

        Args:
            method: HTTPメソッド
            endpoint: APIエンドポイント
            **kwargs: httpxに渡す追加パラメータ

        Returns:
            httpx.Response: APIレスポンス

        Raises:
            APIConnectionError: 接続エラー
            APITimeoutError: タイムアウトエラー
            APIHTTPError: HTTPステータスエラー
            APIRetryError: リトライ上限エラー

        """
        last_exception: APIClientError | None = None

        for attempt in range(self.retry_count + 1):
            # HTTPリクエスト実行（ネットワーク層）
            try:
                # structlogでログ出力（DRY原則: 重複ログ削除）
                if attempt > 0:
                    self.logger.warning(
                        "request_retry",
                        attempt=attempt + 1,
                        max_attempts=self.retry_count + 1,
                        method=method,
                        endpoint=endpoint,
                    )
                else:
                    self.logger.debug("request_start", method=method, endpoint=endpoint)

                # HTTPリクエスト実行
                response = self._client.request(method, endpoint, **kwargs)
            except httpx.RequestError as e:
                # 全ネットワーク層エラーをキャッチ（TimeoutException, ConnectError, etc.）
                last_exception = _map_request_error(e)
                self.logger.warning("Request error", method=method, endpoint=endpoint, error=str(e))
            else:
                # ネットワーク成功時のみHTTPステータス処理
                try:
                    response.raise_for_status()
                    self.logger.debug(
                        "request_success",
                        method=method,
                        endpoint=endpoint,
                        status_code=response.status_code,
                    )
                    return response
                except httpx.HTTPStatusError as e:
                    # 4xxエラーはリトライしない（クライアントエラー）
                    if e.response.is_client_error:
                        self.logger.error(
                            "client_error",
                            status_code=e.response.status_code,
                            method=method,
                            endpoint=endpoint,
                        )
                        raise APIHTTPError(
                            f"HTTP {e.response.status_code} Client Error",
                            e.response.status_code,
                            e.response,
                        ) from e

                    # 5xxエラーはリトライ対象
                    self.logger.warning(
                        "server_error",
                        status_code=e.response.status_code,
                        method=method,
                        endpoint=endpoint,
                    )
                    last_exception = APIHTTPError(
                        f"HTTP {e.response.status_code} Server Error",
                        e.response.status_code,
                        e.response,
                    )

            # 最後の試行でなければ指数バックオフ + 30%ジッターで待機
            if attempt < self.retry_count:
                delay = exponential_backoff_with_jitter(
                    attempt=attempt,
                    base_delay=self.retry_delay,
                    jitter_percent=0.3,
                )
                self.logger.debug(
                    "retry_backoff",
                    delay_seconds=round(delay, 2),
                    attempt=attempt + 1,
                    strategy="exponential_backoff_with_jitter",
                )
                time.sleep(delay)

        # すべてのリトライが失敗
        self.logger.error("all_retries_failed", method=method, endpoint=endpoint)
        raise APIRetryError(
            f"Request failed after {self.retry_count + 1} attempts",
        ) from last_exception

    def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """GETリクエスト実行"""
        return self._make_request_with_retry("GET", endpoint, params=params, headers=headers)

    def post(
        self,
        endpoint: str,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """POSTリクエスト実行"""
        return self._make_request_with_retry(
            "POST",
            endpoint,
            json=json,
            data=data,
            headers=headers,
        )

    def put(
        self,
        endpoint: str,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """PUTリクエスト実行"""
        return self._make_request_with_retry("PUT", endpoint, json=json, data=data, headers=headers)

    def delete(self, endpoint: str, headers: dict[str, str] | None = None) -> httpx.Response:
        """DELETEリクエスト実行"""
        return self._make_request_with_retry("DELETE", endpoint, headers=headers)

    def patch(
        self,
        endpoint: str,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """PATCHリクエスト実行"""
        return self._make_request_with_retry(
            "PATCH",
            endpoint,
            json=json,
            data=data,
            headers=headers,
        )


# =============================================================================
# JSONPlaceholder API 専用クライアント
# =============================================================================


class SyncJSONPlaceholderClient(SyncAPIClient):
    """JSONPlaceholder API専用クライアント

    学習目標:
    - 特化型クライアントの設計
    - APIスキーマとの統合
    - 便利メソッドの実装
    """

    # Posts API
    def get_posts(
        self, limit: int | None = None, user_id: int | None = None
    ) -> list[dict[str, Any]]:
        """投稿一覧の取得

        Args:
            limit: 取得件数上限（0以上）
            user_id: ユーザーIDでフィルタリング（API側フィルタ、1以上）

        Raises:
            ValueError: limit < 0 または user_id < 1 の場合
        """
        if limit is not None and limit < 0:
            raise ValueError("limit must be >= 0")
        if user_id is not None and user_id < 1:
            raise ValueError("user_id must be >= 1")

        params = {}
        if limit is not None:
            params["_limit"] = limit
        if user_id is not None:
            params["userId"] = user_id

        response = self.get("/posts", params=params)
        return _safe_parse_json(response)

    def get_post(self, post_id: int) -> dict[str, Any]:
        """特定投稿の取得"""
        response = self.get(f"/posts/{post_id}")
        return _safe_parse_json(response)

    def create_post(self, title: str, body: str, user_id: int) -> dict[str, Any]:
        """新規投稿の作成"""
        data = {"title": title, "body": body, "userId": user_id}
        response = self.post("/posts", json=data)
        return _safe_parse_json(response)

    # Users API
    def get_users(self) -> list[dict[str, Any]]:
        """ユーザー一覧の取得"""
        response = self.get("/users")
        return _safe_parse_json(response)

    def get_user(self, user_id: int) -> dict[str, Any]:
        """特定ユーザーの取得"""
        response = self.get(f"/users/{user_id}")
        return _safe_parse_json(response)

    # Todos API
    def get_todos(
        self,
        user_id: int | None = None,
        completed: bool | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """TODO一覧の取得

        Args:
            user_id: ユーザーIDでフィルタリング（API側フィルタ、1以上）
            completed: 完了状態でフィルタリング
            limit: 取得件数上限（0以上）

        Raises:
            ValueError: limit < 0 または user_id < 1 の場合
        """
        if limit is not None and limit < 0:
            raise ValueError("limit must be >= 0")
        if user_id is not None and user_id < 1:
            raise ValueError("user_id must be >= 1")

        params = {}
        if user_id is not None:
            params["userId"] = user_id
        if completed is not None:
            params["completed"] = completed
        if limit is not None:
            params["_limit"] = limit

        response = self.get("/todos", params=params)
        return _safe_parse_json(response)

    def get_todo(self, todo_id: int) -> dict[str, Any]:
        """特定TODOの取得"""
        response = self.get(f"/todos/{todo_id}")
        return _safe_parse_json(response)

    def create_todo(self, title: str, user_id: int, completed: bool = False) -> dict[str, Any]:
        """新規TODOの作成"""
        data = {"title": title, "userId": user_id, "completed": completed}
        response = self.post("/todos", json=data)
        return _safe_parse_json(response)

    def update_todo(self, todo_id: int, **kwargs: Any) -> dict[str, Any]:
        """TODOの更新"""
        response = self.patch(f"/todos/{todo_id}", json=kwargs)
        return _safe_parse_json(response)

    # Comments API
    def get_comments(self, post_id: int | None = None) -> list[dict[str, Any]]:
        """コメント一覧の取得

        Args:
            post_id: 投稿IDでフィルタリング（1以上）

        Raises:
            ValueError: post_id < 1 の場合
        """
        if post_id is not None and post_id < 1:
            raise ValueError("post_id must be >= 1")

        if post_id is not None:
            response = self.get(f"/posts/{post_id}/comments")
        else:
            response = self.get("/comments")
        return _safe_parse_json(response)

    # Albums & Photos API
    def get_albums(self, user_id: int | None = None) -> list[dict[str, Any]]:
        """アルバム一覧の取得

        Args:
            user_id: ユーザーIDでフィルタリング（API側フィルタ、1以上）

        Raises:
            ValueError: user_id < 1 の場合
        """
        if user_id is not None and user_id < 1:
            raise ValueError("user_id must be >= 1")

        params = {}
        if user_id is not None:
            params["userId"] = user_id

        response = self.get("/albums", params=params)
        return _safe_parse_json(response)

    def get_photos(self, album_id: int | None = None) -> list[dict[str, Any]]:
        """写真一覧の取得

        Args:
            album_id: アルバムIDでフィルタリング（1以上）

        Raises:
            ValueError: album_id < 1 の場合
        """
        if album_id is not None and album_id < 1:
            raise ValueError("album_id must be >= 1")

        if album_id is not None:
            response = self.get(f"/albums/{album_id}/photos")
        else:
            response = self.get("/photos")
        return _safe_parse_json(response)

    # ヘルスチェック（DevOps/K8s readiness対応）
    def health_check(self) -> bool:
        """API接続の健全性チェック（同期版）

        Docker/Kubernetes readiness probeとして使用可能。
        軽量なリクエスト（/users?_limit=1）でAPI到達性を確認。

        Returns:
            bool: API到達可能ならTrue、エラー時はFalse

        Note:
            Async版と同一インターフェースで統一。
            CLI、スクリプト、レガシーシステム統合時に使用。

        Example:
            >>> with SyncJSONPlaceholderClient() as client:
            ...     if client.health_check():
            ...         print("API is healthy")

        """
        try:
            response = self.get("/users", params={"_limit": 1})
            return response.status_code == 200
        except (KeyboardInterrupt, SystemExit, MemoryError):
            # システム例外は再発生（K8s OOMKilled検知、graceful shutdown対応）
            raise
        except APIClientError as e:
            # 予期されるAPI例外のみキャッチ
            self.logger.warning(
                "health_check_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return False


# =============================================================================
# 非同期APIクライアント
# =============================================================================


class AsyncAPIClient:
    """非同期HTTPクライアント

    学習目標:
    - 非同期プログラミングパターン
    - httpx.AsyncClientの活用
    - async/awaitによる並行処理
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        retry_count: int | None = None,
        retry_delay: float | None = None,
        headers: dict[str, str] | None = None,
    ):
        """Args:
        base_url: APIのベースURL（設定から自動取得可能）
        timeout: リクエストタイムアウト（秒）
        retry_count: リトライ回数
        retry_delay: リトライ間隔（秒）
        headers: 追加HTTPヘッダー

        """
        # 設定から値を取得（引数で上書き可能）
        # NOTE: retry_count=0, retry_delay=0.0 は有効な設定値のため is not None で判定
        self.base_url = base_url or settings.api.base_url
        self.timeout = timeout or settings.api.timeout
        self.retry_count = retry_count if retry_count is not None else settings.api.retry_count
        self.retry_delay = retry_delay if retry_delay is not None else settings.api.retry_delay

        # デフォルトヘッダーの設定
        self.default_headers = {
            "User-Agent": settings.api.user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if headers:
            self.default_headers.update(headers)

        # ロガーの初期化（structlog統合）
        self.logger = get_logger(__name__)

        # HTTPクライアントの初期化（非同期）
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self.default_headers,
            limits=httpx.Limits(max_connections=settings.api.max_connections),
        )

        self.logger.info("async_api_client_initialized", base_url=self.base_url)

    async def __aenter__(self) -> Self:
        """非同期コンテキストマネージャーのエントリー"""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """非同期コンテキストマネージャーの終了処理"""
        await self.aclose()

    async def aclose(self) -> None:
        """クライアントのクローズ"""
        if self._client:
            await self._client.aclose()
            self.logger.info("AsyncAPIClient closed")

    async def _make_request_with_retry(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """リトライ機能付き非同期HTTPリクエスト実行

        Args:
            method: HTTPメソッド
            endpoint: APIエンドポイント
            **kwargs: httpxに渡す追加パラメータ

        Returns:
            httpx.Response: APIレスポンス

        Raises:
            APIConnectionError: 接続エラー
            APITimeoutError: タイムアウトエラー
            APIHTTPError: HTTPステータスエラー
            APIRetryError: リトライ上限エラー

        """
        last_exception: APIClientError | None = None

        for attempt in range(self.retry_count + 1):
            # 非同期HTTPリクエスト実行（ネットワーク層）
            try:
                # structlogでログ出力（DRY原則: 重複ログ削除）
                if attempt > 0:
                    self.logger.warning(
                        "async_request_retry",
                        attempt=attempt + 1,
                        max_attempts=self.retry_count + 1,
                        method=method,
                        endpoint=endpoint,
                    )
                else:
                    self.logger.debug("async_request_start", method=method, endpoint=endpoint)

                # 非同期HTTPリクエスト実行
                response = await self._client.request(method, endpoint, **kwargs)
            except httpx.RequestError as e:
                # 全ネットワーク層エラーをキャッチ（TimeoutException, ConnectError, etc.）
                last_exception = _map_request_error(e)
                self.logger.warning(
                    "Async request error",
                    method=method,
                    endpoint=endpoint,
                    error=str(e),
                )
            else:
                # ネットワーク成功時のみHTTPステータス処理
                try:
                    response.raise_for_status()
                    self.logger.debug(
                        "async_request_success",
                        method=method,
                        endpoint=endpoint,
                        status_code=response.status_code,
                    )
                    return response
                except httpx.HTTPStatusError as e:
                    # 4xxエラーはリトライしない（クライアントエラー）
                    if e.response.is_client_error:
                        self.logger.error(
                            "client_error",
                            status_code=e.response.status_code,
                            method=method,
                            endpoint=endpoint,
                        )
                        raise APIHTTPError(
                            f"HTTP {e.response.status_code} Client Error",
                            e.response.status_code,
                            e.response,
                        ) from e

                    # 5xxエラーはリトライ対象
                    self.logger.warning(
                        "server_error",
                        status_code=e.response.status_code,
                        method=method,
                        endpoint=endpoint,
                    )
                    last_exception = APIHTTPError(
                        f"HTTP {e.response.status_code} Server Error",
                        e.response.status_code,
                        e.response,
                    )

            # 最後の試行でなければ指数バックオフ + 30%ジッターで待機
            if attempt < self.retry_count:
                delay = exponential_backoff_with_jitter(
                    attempt=attempt,
                    base_delay=self.retry_delay,
                    jitter_percent=0.3,
                )
                self.logger.debug(
                    "async_retry_backoff",
                    delay_seconds=round(delay, 2),
                    attempt=attempt + 1,
                    strategy="exponential_backoff_with_jitter",
                )
                await asyncio.sleep(delay)

        # すべてのリトライが失敗
        self.logger.error("async_all_retries_failed", method=method, endpoint=endpoint)
        raise APIRetryError(
            f"Async request failed after {self.retry_count + 1} attempts",
        ) from last_exception

    async def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """非同期GETリクエスト実行"""
        return await self._make_request_with_retry("GET", endpoint, params=params, headers=headers)

    async def post(
        self,
        endpoint: str,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """非同期POSTリクエスト実行"""
        return await self._make_request_with_retry(
            "POST",
            endpoint,
            json=json,
            data=data,
            headers=headers,
        )

    async def put(
        self,
        endpoint: str,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """非同期PUTリクエスト実行"""
        return await self._make_request_with_retry(
            "PUT",
            endpoint,
            json=json,
            data=data,
            headers=headers,
        )

    async def delete(self, endpoint: str, headers: dict[str, str] | None = None) -> httpx.Response:
        """非同期DELETEリクエスト実行"""
        return await self._make_request_with_retry("DELETE", endpoint, headers=headers)

    async def patch(
        self,
        endpoint: str,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """非同期PATCHリクエスト実行"""
        return await self._make_request_with_retry(
            "PATCH",
            endpoint,
            json=json,
            data=data,
            headers=headers,
        )


class AsyncJSONPlaceholderClient(AsyncAPIClient):
    """JSONPlaceholder API専用非同期クライアント

    学習目標:
    - 非同期API操作の実践
    - 並行処理による効率化
    - async/awaitパターンの理解
    """

    # Posts API
    async def get_posts(
        self, limit: int | None = None, user_id: int | None = None
    ) -> list[dict[str, Any]]:
        """投稿一覧の非同期取得

        Args:
            limit: 取得件数上限（0以上）
            user_id: ユーザーIDでフィルタリング（API側フィルタ、1以上）

        Raises:
            ValueError: limit < 0 または user_id < 1 の場合
        """
        if limit is not None and limit < 0:
            raise ValueError("limit must be >= 0")
        if user_id is not None and user_id < 1:
            raise ValueError("user_id must be >= 1")

        params = {}
        if limit is not None:
            params["_limit"] = limit
        if user_id is not None:
            params["userId"] = user_id

        response = await self.get("/posts", params=params)
        return _safe_parse_json(response)

    async def get_post(self, post_id: int) -> dict[str, Any]:
        """特定投稿の非同期取得"""
        response = await self.get(f"/posts/{post_id}")
        return _safe_parse_json(response)

    async def create_post(self, title: str, body: str, user_id: int) -> dict[str, Any]:
        """新規投稿の非同期作成"""
        data = {"title": title, "body": body, "userId": user_id}
        response = await self.post("/posts", json=data)
        return _safe_parse_json(response)

    async def update_post(self, post_id: int, title: str, body: str) -> dict[str, Any]:
        """投稿更新の非同期実行"""
        data = {"title": title, "body": body}
        response = await self.put(f"/posts/{post_id}", json=data)
        return _safe_parse_json(response)

    async def delete_post(self, post_id: int) -> None:
        """投稿削除の非同期実行"""
        await self.delete(f"/posts/{post_id}")

    # Users API
    async def get_users(self) -> list[dict[str, Any]]:
        """ユーザー一覧の非同期取得"""
        response = await self.get("/users")
        return _safe_parse_json(response)

    async def get_user(self, user_id: int) -> dict[str, Any]:
        """特定ユーザーの非同期取得"""
        response = await self.get(f"/users/{user_id}")
        return _safe_parse_json(response)

    # Todos API
    async def get_todos(
        self,
        user_id: int | None = None,
        completed: bool | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """TODO一覧の非同期取得

        Args:
            user_id: ユーザーIDでフィルタリング（API側フィルタ、1以上）
            completed: 完了状態でフィルタリング
            limit: 取得件数上限（0以上）

        Raises:
            ValueError: limit < 0 または user_id < 1 の場合
        """
        if limit is not None and limit < 0:
            raise ValueError("limit must be >= 0")
        if user_id is not None and user_id < 1:
            raise ValueError("user_id must be >= 1")

        params = {}
        if user_id is not None:
            params["userId"] = user_id
        if completed is not None:
            params["completed"] = completed
        if limit is not None:
            params["_limit"] = limit

        response = await self.get("/todos", params=params)
        return _safe_parse_json(response)

    async def get_todo(self, todo_id: int) -> dict[str, Any]:
        """特定TODOの非同期取得"""
        response = await self.get(f"/todos/{todo_id}")
        return _safe_parse_json(response)

    async def create_todo(
        self,
        title: str,
        user_id: int,
        completed: bool = False,
    ) -> dict[str, Any]:
        """新規TODOの非同期作成"""
        data = {"title": title, "userId": user_id, "completed": completed}
        response = await self.post("/todos", json=data)
        return _safe_parse_json(response)

    async def update_todo(self, todo_id: int, **kwargs: Any) -> dict[str, Any]:
        """TODOの非同期更新"""
        response = await self.patch(f"/todos/{todo_id}", json=kwargs)
        return _safe_parse_json(response)

    # Users API 追加メソッド
    async def create_user(self, user_data: dict[str, Any]) -> dict[str, Any]:
        """新規ユーザーの非同期作成"""
        response = await self.post("/users", json=user_data)
        return _safe_parse_json(response)

    async def bulk_create_users(self, users_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """複数ユーザーの非同期一括作成

        個別失敗を許容し、成功したユーザーのみ返却。
        失敗時はwarningログを出力（最初の5件まで詳細表示）。
        """
        # 並行してユーザー作成（個別失敗許容）
        tasks = [self.create_user(user_data) for user_data in users_data]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 成功・失敗を分離（型安全なフィルタリング）
        successful: list[dict[str, Any]] = [r for r in results if isinstance(r, dict)]
        failed: list[BaseException] = [r for r in results if isinstance(r, BaseException)]

        # 失敗時はログ出力（A1: デバッグ改善）
        if failed:
            # 失敗したユーザーデータのコンテキストを収集（リトライ可能性向上）
            # Note: user_dataにはPII含まれる可能性あり。Sentryスクラブで保護済み。
            failed_details = []
            for i, result in enumerate(results):
                if isinstance(result, BaseException):
                    # PIIリスク軽減: nameとemailのみ抽出（password等は除外）
                    user_data_safe = None
                    if i < len(users_data):
                        raw = users_data[i]
                        user_data_safe = {
                            "name": raw.get("name"),
                            "email": raw.get("email"),
                        }
                    failed_details.append(
                        {
                            "index": i,
                            "user_data": user_data_safe,
                            "error": str(result),
                            "error_type": type(result).__name__,
                        }
                    )
            self.logger.warning(
                "bulk_create_partial_failure",
                failed_count=len(failed),
                success_count=len(successful),
                failed_details=failed_details[:5],  # 最初の5件の詳細
            )

        return successful

    # Comments API
    async def get_comments(self, post_id: int | None = None) -> list[dict[str, Any]]:
        """コメント一覧の非同期取得

        Args:
            post_id: 投稿IDでフィルタリング（1以上）

        Raises:
            ValueError: post_id < 1 の場合
        """
        if post_id is not None and post_id < 1:
            raise ValueError("post_id must be >= 1")

        if post_id is not None:
            response = await self.get(f"/posts/{post_id}/comments")
        else:
            response = await self.get("/comments")
        return _safe_parse_json(response)

    # Albums & Photos API
    async def get_albums(self, user_id: int | None = None) -> list[dict[str, Any]]:
        """アルバム一覧の非同期取得

        Args:
            user_id: ユーザーIDでフィルタリング（API側フィルタ、1以上）

        Raises:
            ValueError: user_id < 1 の場合
        """
        if user_id is not None and user_id < 1:
            raise ValueError("user_id must be >= 1")

        params = {}
        if user_id is not None:
            params["userId"] = user_id

        response = await self.get("/albums", params=params)
        return _safe_parse_json(response)

    async def get_photos(self, album_id: int | None = None) -> list[dict[str, Any]]:
        """写真一覧の非同期取得

        Args:
            album_id: アルバムIDでフィルタリング（1以上）

        Raises:
            ValueError: album_id < 1 の場合
        """
        if album_id is not None and album_id < 1:
            raise ValueError("album_id must be >= 1")

        if album_id is not None:
            response = await self.get(f"/albums/{album_id}/photos")
        else:
            response = await self.get("/photos")
        return _safe_parse_json(response)

    # 並行処理の例
    async def get_user_data(self, user_id: int) -> dict[str, Any]:
        """ユーザーに関連するデータを並行取得"""
        # 並行してユーザー情報、投稿、TODO、アルバムを取得
        user_task = self.get_user(user_id)
        posts_task = self.get_posts(user_id=user_id)
        todos_task = self.get_todos(user_id=user_id)
        albums_task = self.get_albums(user_id=user_id)

        # 全ての結果を待機
        user, posts, todos, albums = await asyncio.gather(
            user_task,
            posts_task,
            todos_task,
            albums_task,
        )

        return {
            "user": user,
            "posts": posts,
            "todos": todos,
            "albums": albums,
        }

    # ヘルスチェック（DevOps/K8s readiness対応）
    async def health_check(self) -> bool:
        """API接続の健全性チェック

        Docker/Kubernetes readiness probeとして使用可能。
        軽量なリクエスト（/users?_limit=1）でAPI到達性を確認。

        Returns:
            bool: API到達可能ならTrue、エラー時はFalse

        学習ポイント:
        - Readiness Probe: コンテナがトラフィックを受け入れ可能か確認
        - Liveness Probe: コンテナが正常に動作しているか確認
        - 軽量クエリ（_limit=1）でサーバー負荷を最小化

        Example:
            >>> async with AsyncJSONPlaceholderClient() as client:
            ...     if await client.health_check():
            ...         print("API is healthy")

        """
        try:
            response = await self.get("/users", params={"_limit": 1})
            return response.status_code == 200
        except (KeyboardInterrupt, SystemExit, MemoryError, asyncio.CancelledError):
            # システム例外・タスクキャンセルは再発生（K8s対応、graceful shutdown）
            raise
        except APIClientError as e:
            # 予期されるAPI例外のみキャッチ
            self.logger.warning(
                "health_check_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return False

    # 複数ユーザー取得（Semaphore制御）
    async def get_multiple_users(
        self,
        user_ids: list[int],
        max_concurrent: int = 5,
    ) -> list[dict[str, Any]]:
        """複数ユーザーを並行取得（Semaphore制御付き）

        asyncio.Semaphoreを使用してRate Limit対策。
        GitHub APIなど制限のあるAPIでも安全に並行リクエスト可能。

        Args:
            user_ids: 取得対象のユーザーIDリスト
            max_concurrent: 同時実行数の上限（デフォルト5）

        Returns:
            list[dict]: 取得成功したユーザー情報リスト
                       （取得失敗したIDはスキップ、warningログ出力）

        学習ポイント:
        - asyncio.Semaphore: 同時実行数を制限するロック機構
        - Rate Limit対策: 外部APIへの過剰リクエスト防止
        - Graceful degradation: 一部失敗しても残りの結果を返す

        Example:
            >>> async with AsyncJSONPlaceholderClient() as client:
            ...     users = await client.get_multiple_users([1, 2, 3], max_concurrent=2)
            ...     print(f"Fetched {len(users)} users")

        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def fetch_with_semaphore(user_id: int) -> dict[str, Any] | None:
            """Semaphore制御付きでユーザー取得"""
            async with semaphore:
                try:
                    return await self.get_user(user_id)
                except (KeyboardInterrupt, SystemExit, MemoryError, asyncio.CancelledError):
                    # システム例外・タスクキャンセルは再発生（並行処理全体を停止）
                    raise
                except APIClientError as e:
                    # 予期されるAPI例外のみキャッチ（graceful degradation）
                    self.logger.warning(
                        "get_user_failed",
                        user_id=user_id,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    return None

        # 並行実行（return_exceptions不要：内部でtry-catch済み）
        results = await asyncio.gather(*[fetch_with_semaphore(uid) for uid in user_ids])

        # None除外（失敗分）
        return [r for r in results if r is not None]


# =============================================================================
# 便利な関数
# =============================================================================


def create_client() -> SyncJSONPlaceholderClient:
    """設定に基づいたクライアントインスタンスの作成"""
    return SyncJSONPlaceholderClient()


# =============================================================================
# デモ実行（モジュール直接実行時）
# =============================================================================


def main() -> None:
    """デモ実行"""
    print("=== JSONPlaceholder API Client Demo ===")

    with create_client() as client:
        try:
            # 投稿一覧の取得
            print("\n1. 投稿一覧取得（5件）:")
            posts = client.get_posts(limit=5)
            for post in posts:
                print(f"  - Post {post['id']}: {post['title'][:50]}...")

            # 特定ユーザーの取得
            print("\n2. ユーザー情報取得（ID: 1）:")
            user = client.get_user(1)
            print(f"  - Name: {user['name']}")
            print(f"  - Email: {user['email']}")
            print(f"  - Company: {user['company']['name']}")

            # TODOの取得
            print("\n3. TODO取得（完了済み、3件）:")
            todos = client.get_todos(completed=True, limit=3)
            for todo in todos:
                status = "✓" if todo["completed"] else "✗"
                print(f"  {status} User {todo['userId']}: {todo['title']}")

            # 新規投稿の作成（テスト用）
            print("\n4. 新規投稿作成テスト:")
            new_post = client.create_post(
                title="Test Post from API Client",
                body="This is a test post created by our API client.",
                user_id=1,
            )
            print(f"  - Created post ID: {new_post.get('id', 'N/A')}")
            print(f"  - Title: {new_post.get('title', 'N/A')}")

        except Exception as e:
            print(f"エラーが発生しました: {e}")
            if settings.debug:
                import traceback

                traceback.print_exc()

    print("\n=== Demo completed ===")


if __name__ == "__main__":
    # structlogはget_logger()初回呼び出し時に自動設定されるため、手動設定不要
    main()


# =============================================================================
# 学習ポイント:
#
# 1. クライアント設計パターン:
#    - ベースクライアントと特化クライアントの分離
#    - 設定との統合
#    - コンテキストマネージャー対応
#
# 2. エラーハンドリング戦略:
#    - 階層的な例外クラス設計
#    - HTTPステータスコード別の処理
#    - 詳細なログ出力
#
# 3. リトライロジック:
#    - 指数バックオフの実装可能性
#    - エラー種別による制御
#    - 設定可能なパラメータ
#
# 4. 実用性:
#    - APIスキーマとの対応
#    - 便利メソッドの提供
#    - デバッグ支援機能
#
# 5. 拡張性:
#    - 認証機能の追加可能性
#    - カスタムヘッダー対応
#    - 非同期版への拡張基盤
# =============================================================================
