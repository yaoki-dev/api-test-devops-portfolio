"""同期・非同期HTTPAPIクライアント

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
from structlog.typing import FilteringBoundLogger

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


def _validate_optional_int(value: int | None, name: str, min_value: int) -> None:
    """オプショナルな整数パラメータの最小値バリデーション。

    Args:
        value: 検証対象の値（Noneの場合はスキップ）
        name: パラメータ名（エラーメッセージ用）
        min_value: 最小許容値（含む）

    Raises:
        ValueError: valueがmin_valueより小さい場合
    """
    if value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}")


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
        e: httpx.RequestError または httpx.InvalidURL（またはそのサブクラス）

    Returns:
        APIClientErrorサブクラス（リトライ可能エラーの場合のみ。
        非リトライ時（TooManyRedirects / InvalidURL）は
        APIClientError 基底クラスを raise するため返らない）。

    Raises:
        APIClientError: 非リトライ可能エラー（TooManyRedirects, InvalidURL）

    Note:
        httpx例外の扱い:
        - RequestError サブクラス（リトライ可能）:
          TimeoutException (ConnectTimeout, ReadTimeout),
          NetworkError (ConnectError, ReadError, WriteError 等のサブクラスを含む)
          ※ ConnectError は NetworkError のサブクラスだが個別分岐で処理
        - RequestError サブクラス（非リトライ）:
          TooManyRedirects → 即座にraise
        - 独立例外（RequestError のサブクラスではない、非リトライ）:
          InvalidURL → 即座にraise

    """
    # Non-retryable errors - raise immediately (no point in retrying)
    if isinstance(e, httpx.TooManyRedirects | httpx.InvalidURL):
        raise APIClientError(f"Non-retryable request error: {e}") from e

    # Retryable errors: returnするため `raise ... from e` は使えず __cause__ を手動設定する。
    # PEP 3134: exc.__cause__ = e を設定すると __suppress_context__ が自動で True になり、
    # 呼び出し元が raise した際に `raise exc from e` と同じ例外チェーン表示になる。
    if isinstance(e, httpx.TimeoutException):
        timeout_exc = APITimeoutError(f"Request timeout: {e}")
        timeout_exc.__cause__ = e
        return timeout_exc
    if isinstance(e, httpx.ConnectError):
        connect_exc = APIConnectionError(f"Connection failed: {e}")
        connect_exc.__cause__ = e
        return connect_exc
    # NetworkError, etc. - retryable network issues
    network_exc = APIConnectionError(f"Network error: {e}")
    network_exc.__cause__ = e
    return network_exc


def _resolve_client_config(
    base_url: str | None,
    timeout: float | None,
    retry_count: int | None,
    retry_delay: float | None,
    headers: dict[str, str] | None,
) -> tuple[str, float, int, float, dict[str, str]]:
    """Sync/Async共通の設定解決ロジック。

    引数またはsettingsから設定値を解決し、バリデーションを実行する。
    HTTPクライアント初期化・ロガー初期化は呼び出し元の責務。

    Args:
        base_url: APIのベースURL（Noneの場合settings.api.base_urlを使用）
        timeout: タイムアウト秒数（Noneの場合settings.api.timeoutを使用）
        retry_count: リトライ回数（Noneの場合settings.api.retry_countを使用）
        retry_delay: リトライ間隔秒数（Noneの場合settings.api.retry_delayを使用）
        headers: 追加ヘッダー（デフォルトヘッダーにマージ）

    Returns:
        (base_url, timeout, retry_count, retry_delay, default_headers) のタプル

    Raises:
        ValueError: base_urlが空文字列またはスペースのみの文字列の場合

    """
    base_url = base_url if base_url is not None else settings.api.base_url
    if not base_url.strip():
        raise ValueError("base_url が空です。引数または API__BASE_URL 環境変数を確認してください。")
    timeout = timeout if timeout is not None else settings.api.timeout
    retry_count = retry_count if retry_count is not None else settings.api.retry_count
    retry_delay = retry_delay if retry_delay is not None else settings.api.retry_delay

    default_headers = {
        "User-Agent": settings.api.user_agent,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    # `if headers:` ではなく `is not None` を使用: 空辞書({})を渡した場合も
    # update()を実行する（no-opだが、Noneと空辞書の意味論を明確に区別するため）
    if headers is not None:
        default_headers.update(headers)

    return (
        base_url,
        timeout,
        retry_count,
        retry_delay,
        default_headers,
    )


def _classify_error(
    e: httpx.RequestError | httpx.InvalidURL,
    logger: FilteringBoundLogger,
    *,
    is_async: bool,
    method: str,
    endpoint: str,
) -> APIClientError:
    """Sync/Async共通のネットワークエラー分類・ログ出力。

    エラー種別に応じてERROR/WARNINGログを出力し、_map_request_error()を呼び出す。
    非リトライエラー(TooManyRedirects/InvalidURL)は_map_request_error()内で即座にraiseされる。

    Args:
        e: httpxのリクエストエラーまたはInvalidURL
        logger: structlogロガーインスタンス
        is_async: 非同期クライアントからの呼び出しかどうか
        method: HTTPメソッド名
        endpoint: APIエンドポイント

    Returns:
        APIClientErrorサブクラス（リトライ可能エラーの場合）。
        TooManyRedirects / InvalidURL の場合は _map_request_error() 内で
        raise されるため、呼び出し元には値が返らない。

    Raises:
        APIClientError: TooManyRedirects または InvalidURL の場合
            （logger.error でログ出力後、_map_request_error() を経由して raise される）。
            注: サブクラスではなく APIClientError 基底クラスが raise される。
            リトライ可能エラーは logger.warning でログ出力し、raise されない。

    Notes:
        ログの ``error`` フィールドは省略している。httpx 例外の文字列には
        ホスト名、プロキシ設定等の機密情報が含まれるため、``error_type``
        （例外クラス名）のみ記録してエラー分類に必須情報を確保する。

        cf. ``health_check_failed()`` では ``error=str(e)`` を記録しているが、
        その ``e`` は ``APIClientError``（独自例外）であり、httpx 生例外と
        異なりセキュリティリスクが低いため扱いが異なる。

    """
    if isinstance(e, httpx.TooManyRedirects | httpx.InvalidURL):
        # セキュリティ対策: httpx 例外の文字列には接続先 URL・ホスト名等の
        # 機密情報が含まれるため、error フィールドを省略し、error_type
        # （例外クラス名）のみを記録する。
        logger.error(
            "request_error_non_retryable",
            is_async=is_async,
            method=method,
            endpoint=endpoint,
            error_type=type(e).__name__,
        )
    else:
        # 同上: httpx 生例外のリスク対策として error フィールド省略。
        logger.warning(
            "request_error",
            is_async=is_async,
            method=method,
            endpoint=endpoint,
            error_type=type(e).__name__,
        )
    return _map_request_error(e)


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

        Raises:
            ValueError: base_urlが空文字列の場合

        """
        # 設定解決・バリデーション（Sync/Async共通ロジック）
        # NOTE: retry_count=0, retry_delay=0.0, timeout=0.0 は有効な設定値のため is not None で判定
        # timeout=0.0: 即座にタイムアウト（無効化は timeout=None）
        (
            self.base_url,
            self.timeout,
            self.retry_count,
            self.retry_delay,
            self.default_headers,
        ) = _resolve_client_config(base_url, timeout, retry_count, retry_delay, headers)

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
            APIClientError: 非リトライエラー（TooManyRedirects / InvalidURL）

        Note:
            TooManyRedirects/InvalidURL は _map_request_error() 内で即 raise されるため、
            APIRetryError ではなく APIClientError として呼び出し元に届く。
            呼び出し元は APIClientError で捕捉すること。

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
            except (httpx.RequestError, httpx.InvalidURL) as e:
                # 全ネットワーク層エラーをキャッチ（TimeoutException, ConnectError, etc.）
                # TooManyRedirects/InvalidURL は _classify_error → _map_request_error 内で即 raise
                last_exception = _classify_error(
                    e,
                    self.logger,
                    is_async=False,
                    method=method,
                    endpoint=endpoint,
                )
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
        _validate_optional_int(limit, "limit", 0)
        _validate_optional_int(user_id, "user_id", 1)

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
        _validate_optional_int(limit, "limit", 0)
        _validate_optional_int(user_id, "user_id", 1)

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
        _validate_optional_int(post_id, "post_id", 1)

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
        _validate_optional_int(user_id, "user_id", 1)

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
        _validate_optional_int(album_id, "album_id", 1)

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
        except KeyboardInterrupt, SystemExit, MemoryError:
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

        Raises:
            ValueError: base_urlが空文字列の場合

        """
        # 設定解決・バリデーション（Sync/Async共通ロジック）
        # NOTE: retry_count=0, retry_delay=0.0, timeout=0.0 は有効な設定値のため is not None で判定
        # timeout=0.0: 即座にタイムアウト（無効化は timeout=None）
        (
            self.base_url,
            self.timeout,
            self.retry_count,
            self.retry_delay,
            self.default_headers,
        ) = _resolve_client_config(base_url, timeout, retry_count, retry_delay, headers)

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
            self.logger.info("async_api_client_closed")

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
            APIClientError: 非リトライエラー（TooManyRedirects / InvalidURL）

        Note:
            TooManyRedirects/InvalidURL は _map_request_error() 内で即 raise されるため、
            APIRetryError ではなく APIClientError として呼び出し元に届く。
            呼び出し元は APIClientError で捕捉すること。

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
            except (httpx.RequestError, httpx.InvalidURL) as e:
                # 全ネットワーク層エラーをキャッチ（TimeoutException, ConnectError, etc.）
                # TooManyRedirects/InvalidURL は _classify_error → _map_request_error 内で即 raise
                last_exception = _classify_error(
                    e,
                    self.logger,
                    is_async=True,
                    method=method,
                    endpoint=endpoint,
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
        _validate_optional_int(limit, "limit", 0)
        _validate_optional_int(user_id, "user_id", 1)

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
        _validate_optional_int(limit, "limit", 0)
        _validate_optional_int(user_id, "user_id", 1)

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
        K8s SIGTERM等で複数タスクが同時キャンセルされた場合はerrorログを出力後、
        CancelledError等のfatal例外を再発生させる（graceful shutdown保護）。

        Args:
            users_data: 作成するユーザーデータのリスト（各要素はname/emailを含むdict）

        Returns:
            成功したユーザーデータのリスト（失敗した分は除外される）

        Raises:
            asyncio.CancelledError: 単一タスクがキャンセルされた場合（K8s graceful shutdown等）
            BaseExceptionGroup: 複数タスクが同時にfatal例外を発生させた場合（Python convention準拠）
            KeyboardInterrupt: Ctrl+C等の割り込みシグナルを受けた場合
            SystemExit: sys.exit()が呼ばれた場合
            MemoryError: メモリ不足が発生した場合
        """
        # 並行してユーザー作成（個別失敗許容）
        tasks = [self.create_user(user_data) for user_data in users_data]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # システム例外はgather後に再発生させる（graceful shutdown保護）
        # asyncio.CancelledError（Python 3.8+ は BaseException サブクラス）を吸収しない
        # 複数タスクが同時キャンセルされる場合（K8s SIGTERM等）に全件収集してログ出力
        fatal_exceptions = [
            r
            for r in results
            if isinstance(r, (KeyboardInterrupt, SystemExit, MemoryError, asyncio.CancelledError))
        ]
        if fatal_exceptions:
            if len(fatal_exceptions) > 1:
                # Python convention: 複数同時例外はBaseExceptionGroupで伝播（TaskGroup同パターン）
                # ログとraise件数の一貫性を保証（count=N → N件をBaseExceptionGroupで伝播）
                # NOTE: CancelledError/KeyboardInterrupt/SystemExitはBaseExceptionサブクラスのため
                #       ExceptionGroup（Exception限定）ではなくBaseExceptionGroupを使用
                self.logger.error(
                    "bulk_create_multiple_fatal_errors",
                    count=len(fatal_exceptions),
                    types=[type(e).__name__ for e in fatal_exceptions],
                )
                raise BaseExceptionGroup(
                    "bulk_create_users: multiple fatal errors occurred",
                    fatal_exceptions,
                )
            # 単一例外は直接raise（Python convention: asyncio.TaskGroupと同パターン）
            exc = fatal_exceptions[0]
            raise exc

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
        _validate_optional_int(post_id, "post_id", 1)

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
        _validate_optional_int(user_id, "user_id", 1)

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
        _validate_optional_int(album_id, "album_id", 1)

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
        except KeyboardInterrupt, SystemExit, MemoryError, asyncio.CancelledError:
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
                except KeyboardInterrupt, SystemExit, MemoryError, asyncio.CancelledError:
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

        except APIClientError as e:
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
