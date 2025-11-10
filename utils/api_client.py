"""
基本的な同期HTTPAPIクライアント

学習目標:
- HTTPクライアントの設計パターン
- エラーハンドリング戦略
- リトライロジックの実装
- 設定管理との統合
"""

import logging
import random
import time
from typing import Any

import httpx

from config.settings import settings


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
    # ±30%のジッター追加
    jitter = delay * jitter_percent
    delay = delay + random.uniform(-jitter, jitter)
    # 最小値保証
    return max(0.1, delay)


# =============================================================================
# 例外クラス
# =============================================================================


class APIClientError(Exception):
    """APIクライアント基底例外"""

    pass


class APIConnectionError(APIClientError):
    """API接続エラー"""

    pass


class APITimeoutError(APIClientError):
    """APIタイムアウトエラー"""

    pass


class APIHTTPError(APIClientError):
    """HTTPステータスエラー"""

    def __init__(self, message: str, status_code: int, response: httpx.Response | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class APIRetryError(APIClientError):
    """リトライ上限エラー"""

    pass


# =============================================================================
# 基本HTTPクライアント
# =============================================================================


class BaseAPIClient:
    """
    基本的な同期HTTPクライアント

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
        """
        Args:
            base_url: APIのベースURL（設定から自動取得可能）
            timeout: リクエストタイムアウト（秒）
            retry_count: リトライ回数
            retry_delay: リトライ間隔（秒）
            headers: 追加HTTPヘッダー
        """
        # 設定から値を取得（引数で上書き可能）
        self.base_url = base_url or settings.api.base_url
        self.timeout = timeout or settings.api.timeout
        self.retry_count = retry_count or settings.api.retry_count
        self.retry_delay = retry_delay or settings.api.retry_delay

        # デフォルトヘッダーの設定
        self.default_headers = {
            "User-Agent": settings.api.user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if headers:
            self.default_headers.update(headers)

        # ロガーの初期化
        self.logger = logging.getLogger(__name__)

        # HTTPクライアントの初期化
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self.default_headers,
            limits=httpx.Limits(max_connections=settings.api.max_connections),
        )

        self.logger.info(f"APIClient initialized: base_url={self.base_url}")

    def __enter__(self):
        """コンテキストマネージャーのエントリー"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャーの終了処理"""
        self.close()

    def close(self):
        """クライアントのクローズ"""
        if self._client:
            self._client.close()
            self.logger.info("APIClient closed")

    def _make_request_with_retry(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """
        リトライ機能付きHTTPリクエスト実行

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
        last_exception = None

        for attempt in range(self.retry_count + 1):
            try:
                # ログ出力
                if attempt > 0:
                    self.logger.warning(
                        f"Retrying request: attempt {attempt + 1}/{self.retry_count + 1} "
                        f"for {method} {endpoint}"
                    )
                else:
                    self.logger.debug(f"Making request: {method} {endpoint}")

                # HTTPリクエスト実行
                response = self._client.request(method, endpoint, **kwargs)

                # HTTPステータスコードチェック
                try:
                    response.raise_for_status()
                    self.logger.debug(
                        f"Request successful: {method} {endpoint} -> {response.status_code}"
                    )
                    return response

                except httpx.HTTPStatusError as e:
                    # 4xxエラーはリトライしない（クライアントエラー）
                    if 400 <= e.response.status_code < 500:
                        self.logger.error(
                            f"Client error: {e.response.status_code} for {method} {endpoint}"
                        )
                        raise APIHTTPError(
                            f"HTTP {e.response.status_code} Client Error",
                            e.response.status_code,
                            e.response,
                        ) from e

                    # 5xxエラーはリトライ対象
                    self.logger.warning(
                        f"Server error: {e.response.status_code} for {method} {endpoint}"
                    )
                    last_exception = APIHTTPError(
                        f"HTTP {e.response.status_code} Server Error",
                        e.response.status_code,
                        e.response,
                    )

            except httpx.TimeoutException as e:
                self.logger.warning(f"Timeout error for {method} {endpoint}: {e}")
                last_exception = APITimeoutError(f"Request timeout: {e}")

            except httpx.ConnectError as e:
                self.logger.warning(f"Connection error for {method} {endpoint}: {e}")
                last_exception = APIConnectionError(f"Connection failed: {e}")

            except Exception as e:
                self.logger.error(f"Unexpected error for {method} {endpoint}: {e}")
                last_exception = APIClientError(f"Unexpected error: {e}")

            # 最後の試行でなければ指数バックオフ + 30%ジッターで待機
            if attempt < self.retry_count:
                delay = exponential_backoff_with_jitter(
                    attempt=attempt, base_delay=self.retry_delay, jitter_percent=0.3
                )
                self.logger.debug(
                    f"Waiting {delay:.2f} seconds before retry "
                    f"(attempt {attempt + 1}, exponential backoff with 30% jitter)..."
                )
                time.sleep(delay)

        # すべてのリトライが失敗
        self.logger.error(f"All retry attempts failed for {method} {endpoint}")
        raise APIRetryError(
            f"Request failed after {self.retry_count + 1} attempts"
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
            "POST", endpoint, json=json, data=data, headers=headers
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
            "PATCH", endpoint, json=json, data=data, headers=headers
        )


# =============================================================================
# JSONPlaceholder API 専用クライアント
# =============================================================================


class JSONPlaceholderClient(BaseAPIClient):
    """
    JSONPlaceholder API専用クライアント

    学習目標:
    - 特化型クライアントの設計
    - APIスキーマとの統合
    - 便利メソッドの実装
    """

    # def __init__(self, **kwargs):
    #     # JSONPlaceholder APIのデフォルト設定
    #     if "base_url" not in kwargs:
    #         kwargs["base_url"] = "https://jsonplaceholder.typicode.com"

    #     super().__init__(**kwargs)

    # Posts API
    def get_posts(self, limit: int | None = None) -> list[dict[str, Any]]:
        """投稿一覧の取得"""
        params = {}
        if limit:
            params["_limit"] = limit

        response = self.get("/posts", params=params)
        return response.json()

    def get_post(self, post_id: int) -> dict[str, Any]:
        """特定投稿の取得"""
        response = self.get(f"/posts/{post_id}")
        return response.json()

    def create_post(self, title: str, body: str, user_id: int) -> dict[str, Any]:
        """新規投稿の作成"""
        data = {"title": title, "body": body, "userId": user_id}
        response = self.post("/posts", json=data)
        return response.json()

    # Users API
    def get_users(self) -> list[dict[str, Any]]:
        """ユーザー一覧の取得"""
        response = self.get("/users")
        return response.json()

    def get_user(self, user_id: int) -> dict[str, Any]:
        """特定ユーザーの取得"""
        response = self.get(f"/users/{user_id}")
        return response.json()

    # Todos API
    def get_todos(
        self,
        user_id: int | None = None,
        completed: bool | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """TODO一覧の取得"""
        params = {}
        if user_id:
            params["userId"] = user_id
        if completed is not None:
            params["completed"] = completed
        if limit:
            params["_limit"] = limit

        response = self.get("/todos", params=params)
        return response.json()

    def get_todo(self, todo_id: int) -> dict[str, Any]:
        """特定TODOの取得"""
        response = self.get(f"/todos/{todo_id}")
        return response.json()

    def create_todo(self, title: str, user_id: int, completed: bool = False) -> dict[str, Any]:
        """新規TODOの作成"""
        data = {"title": title, "userId": user_id, "completed": completed}
        response = self.post("/todos", json=data)
        return response.json()

    def update_todo(self, todo_id: int, **kwargs) -> dict[str, Any]:
        """TODOの更新"""
        response = self.patch(f"/todos/{todo_id}", json=kwargs)
        return response.json()

    # Comments API
    def get_comments(self, post_id: int | None = None) -> list[dict[str, Any]]:
        """コメント一覧の取得"""
        if post_id:
            response = self.get(f"/posts/{post_id}/comments")
        else:
            response = self.get("/comments")
        return response.json()

    # Albums & Photos API
    def get_albums(self, user_id: int | None = None) -> list[dict[str, Any]]:
        """アルバム一覧の取得"""
        params = {}
        if user_id:
            params["userId"] = user_id

        response = self.get("/albums", params=params)
        return response.json()

    def get_photos(self, album_id: int | None = None) -> list[dict[str, Any]]:
        """写真一覧の取得"""
        if album_id:
            response = self.get(f"/albums/{album_id}/photos")
        else:
            response = self.get("/photos")
        return response.json()


# =============================================================================
# 非同期APIクライアント
# =============================================================================


class AsyncAPIClient:
    """
    非同期HTTPクライアント

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
        """
        Args:
            base_url: APIのベースURL（設定から自動取得可能）
            timeout: リクエストタイムアウト（秒）
            retry_count: リトライ回数
            retry_delay: リトライ間隔（秒）
            headers: 追加HTTPヘッダー
        """
        # 設定から値を取得（引数で上書き可能）
        self.base_url = base_url or settings.api.base_url
        self.timeout = timeout or settings.api.timeout
        self.retry_count = retry_count or settings.api.retry_count
        self.retry_delay = retry_delay or settings.api.retry_delay

        # デフォルトヘッダーの設定
        self.default_headers = {
            "User-Agent": settings.api.user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if headers:
            self.default_headers.update(headers)

        # ロガーの初期化
        self.logger = logging.getLogger(__name__)

        # HTTPクライアントの初期化（非同期）
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self.default_headers,
            limits=httpx.Limits(max_connections=settings.api.max_connections),
        )

        self.logger.info(f"AsyncAPIClient initialized: base_url={self.base_url}")

    async def __aenter__(self):
        """非同期コンテキストマネージャーのエントリー"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同期コンテキストマネージャーの終了処理"""
        await self.aclose()

    async def aclose(self):
        """クライアントのクローズ"""
        if self._client:
            await self._client.aclose()
            self.logger.info("AsyncAPIClient closed")

    async def _make_request_with_retry(
        self, method: str, endpoint: str, **kwargs
    ) -> httpx.Response:
        """
        リトライ機能付き非同期HTTPリクエスト実行

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
        import asyncio

        last_exception = None

        for attempt in range(self.retry_count + 1):
            try:
                # ログ出力
                if attempt > 0:
                    self.logger.warning(
                        f"Retrying async request: attempt {attempt + 1}/{self.retry_count + 1} "
                        f"for {method} {endpoint}"
                    )
                else:
                    self.logger.debug(f"Making async request: {method} {endpoint}")

                # 非同期HTTPリクエスト実行
                response = await self._client.request(method, endpoint, **kwargs)

                # HTTPステータスコードチェック
                try:
                    response.raise_for_status()
                    self.logger.debug(
                        f"Async request successful: {method} {endpoint} -> {response.status_code}"
                    )
                    return response

                except httpx.HTTPStatusError as e:
                    # 4xxエラーはリトライしない（クライアントエラー）
                    if 400 <= e.response.status_code < 500:
                        self.logger.error(
                            f"Client error: {e.response.status_code} for {method} {endpoint}"
                        )
                        raise APIHTTPError(
                            f"HTTP {e.response.status_code} Client Error",
                            e.response.status_code,
                            e.response,
                        ) from e

                    # 5xxエラーはリトライ対象
                    self.logger.warning(
                        f"Server error: {e.response.status_code} for {method} {endpoint}"
                    )
                    last_exception = APIHTTPError(
                        f"HTTP {e.response.status_code} Server Error",
                        e.response.status_code,
                        e.response,
                    )

            except httpx.TimeoutException as e:
                self.logger.warning(f"Async timeout error for {method} {endpoint}: {e}")
                last_exception = APITimeoutError(f"Request timeout: {e}")

            except httpx.ConnectError as e:
                self.logger.warning(f"Async connection error for {method} {endpoint}: {e}")
                last_exception = APIConnectionError(f"Connection failed: {e}")

            except Exception as e:
                self.logger.error(f"Unexpected async error for {method} {endpoint}: {e}")
                last_exception = APIClientError(f"Unexpected error: {e}")

            # 最後の試行でなければ指数バックオフ + 30%ジッターで待機
            if attempt < self.retry_count:
                delay = exponential_backoff_with_jitter(
                    attempt=attempt, base_delay=self.retry_delay, jitter_percent=0.3
                )
                self.logger.debug(
                    f"Waiting {delay:.2f} seconds before async retry "
                    f"(attempt {attempt + 1}, exponential backoff with 30% jitter)..."
                )
                await asyncio.sleep(delay)

        # すべてのリトライが失敗
        self.logger.error(f"All async retry attempts failed for {method} {endpoint}")
        raise APIRetryError(
            f"Async request failed after {self.retry_count + 1} attempts"
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
            "POST", endpoint, json=json, data=data, headers=headers
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
            "PUT", endpoint, json=json, data=data, headers=headers
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
            "PATCH", endpoint, json=json, data=data, headers=headers
        )


class AsyncJSONPlaceholderClient(AsyncAPIClient):
    """
    JSONPlaceholder API専用非同期クライアント

    学習目標:
    - 非同期API操作の実践
    - 並行処理による効率化
    - async/awaitパターンの理解
    """

    # def __init__(self, **kwargs):
    #     # JSONPlaceholder APIのデフォルト設定
    #     if "base_url" not in kwargs:
    #         kwargs["base_url"] = "https://jsonplaceholder.typicode.com"

    #     super().__init__(**kwargs)

    # Posts API
    async def get_posts(self, limit: int | None = None) -> list[dict[str, Any]]:
        """投稿一覧の非同期取得"""
        params = {}
        if limit:
            params["_limit"] = limit

        response = await self.get("/posts", params=params)
        return response.json()

    async def get_post(self, post_id: int) -> dict[str, Any]:
        """特定投稿の非同期取得"""
        response = await self.get(f"/posts/{post_id}")
        return response.json()

    async def create_post(self, title: str, body: str, user_id: int) -> dict[str, Any]:
        """新規投稿の非同期作成"""
        data = {"title": title, "body": body, "userId": user_id}
        response = await self.post("/posts", json=data)
        return response.json()

    async def update_post(self, post_id: int, title: str, body: str) -> dict[str, Any]:
        """投稿更新の非同期実行"""
        data = {"title": title, "body": body}
        response = await self.put(f"/posts/{post_id}", json=data)
        return response.json()

    async def delete_post(self, post_id: int) -> None:
        """投稿削除の非同期実行"""
        await self.delete(f"/posts/{post_id}")

    # Users API
    async def get_users(self) -> list[dict[str, Any]]:
        """ユーザー一覧の非同期取得"""
        response = await self.get("/users")
        return response.json()

    async def get_user(self, user_id: int) -> dict[str, Any]:
        """特定ユーザーの非同期取得"""
        response = await self.get(f"/users/{user_id}")
        return response.json()

    # Todos API
    async def get_todos(
        self,
        user_id: int | None = None,
        completed: bool | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """TODO一覧の非同期取得"""
        params = {}
        if user_id:
            params["userId"] = user_id
        if completed is not None:
            params["completed"] = completed
        if limit:
            params["_limit"] = limit

        response = await self.get("/todos", params=params)
        return response.json()

    async def get_todo(self, todo_id: int) -> dict[str, Any]:
        """特定TODOの非同期取得"""
        response = await self.get(f"/todos/{todo_id}")
        return response.json()

    async def create_todo(
        self, title: str, user_id: int, completed: bool = False
    ) -> dict[str, Any]:
        """新規TODOの非同期作成"""
        data = {"title": title, "userId": user_id, "completed": completed}
        response = await self.post("/todos", json=data)
        return response.json()

    async def update_todo(self, todo_id: int, **kwargs) -> dict[str, Any]:
        """TODOの非同期更新"""
        response = await self.patch(f"/todos/{todo_id}", json=kwargs)
        return response.json()

    # Users API 追加メソッド
    async def create_user(self, user_data: dict[str, Any]) -> dict[str, Any]:
        """新規ユーザーの非同期作成"""
        response = await self.post("/users", json=user_data)
        return response.json()

    async def bulk_create_users(self, users_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """複数ユーザーの非同期一括作成"""
        import asyncio

        # 並行してユーザー作成
        tasks = [self.create_user(user_data) for user_data in users_data]
        results = await asyncio.gather(*tasks)
        return results

    # Comments API
    async def get_comments(self, post_id: int | None = None) -> list[dict[str, Any]]:
        """コメント一覧の非同期取得"""
        if post_id:
            response = await self.get(f"/posts/{post_id}/comments")
        else:
            response = await self.get("/comments")
        return response.json()

    # Albums & Photos API
    async def get_albums(self, user_id: int | None = None) -> list[dict[str, Any]]:
        """アルバム一覧の非同期取得"""
        params = {}
        if user_id:
            params["userId"] = user_id

        response = await self.get("/albums", params=params)
        return response.json()

    async def get_photos(self, album_id: int | None = None) -> list[dict[str, Any]]:
        """写真一覧の非同期取得"""
        if album_id:
            response = await self.get(f"/albums/{album_id}/photos")
        else:
            response = await self.get("/photos")
        return response.json()

    # 並行処理の例
    async def get_user_data(self, user_id: int) -> dict[str, Any]:
        """ユーザーに関連するデータを並行取得"""
        import asyncio

        # 並行してユーザー情報、投稿、TODO、アルバムを取得
        user_task = self.get_user(user_id)
        posts_task = self.get_posts()
        todos_task = self.get_todos(user_id=user_id)
        albums_task = self.get_albums(user_id=user_id)

        # 全ての結果を待機
        user, posts, todos, albums = await asyncio.gather(
            user_task, posts_task, todos_task, albums_task
        )

        return {
            "user": user,
            "posts": [p for p in posts if p["userId"] == user_id],
            "todos": todos,
            "albums": albums,
        }


# =============================================================================
# 便利な関数
# =============================================================================


def create_client() -> JSONPlaceholderClient:
    """設定に基づいたクライアントインスタンスの作成"""
    return JSONPlaceholderClient()


# =============================================================================
# デモ実行（モジュール直接実行時）
# =============================================================================


def main():
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
    # ログ設定
    logging.basicConfig(
        level=settings.get_log_level(),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

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
