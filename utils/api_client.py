"""同期・非同期HTTPAPIクライアント"""

import asyncio
from typing import Any, Final, TypedDict

from config.settings import settings
from models.responses import Album, Comment, Photo, Post, Todo, User
from utils.exceptions import (
    ASYNC_FATAL_EXCEPTIONS,
)
from utils.exceptions import (
    APIClientError as APIClientError,
)
from utils.exceptions import (
    APIConnectionError as APIConnectionError,
)
from utils.exceptions import (
    APIHTTPError as APIHTTPError,
)
from utils.exceptions import (
    APIJSONDecodeError as APIJSONDecodeError,
)
from utils.exceptions import (
    APIRetryError as APIRetryError,
)
from utils.exceptions import (
    APITimeoutError as APITimeoutError,
)
from utils.http_helpers import (
    classify_error,
    log_error_with_stderr_fallback,
    map_request_error,
    resolve_client_config,
    validate_optional_int,
)
from utils.jsonplaceholder_base_async import AsyncAPIClient
from utils.jsonplaceholder_base_sync import SyncAPIClient
from utils.response_parsing import (
    parse_response_model,
    parse_response_model_list,
    safe_parse_json,
)
from utils.retry import exponential_backoff_with_jitter as exponential_backoff_with_jitter

SYNC_FATAL_EXCEPTIONS: tuple[type[BaseException], ...] = (
    KeyboardInterrupt,
    SystemExit,
    MemoryError,
    RecursionError,
)

# Backward-compatible aliases retained until W3 import cutover.
_validate_optional_int = validate_optional_int
_safe_parse_json = safe_parse_json
_parse_response_model = parse_response_model
_parse_response_model_list = parse_response_model_list
_map_request_error = map_request_error
_resolve_client_config = resolve_client_config
_classify_error = classify_error
_log_error_with_stderr_fallback = log_error_with_stderr_fallback


# =============================================================================
# JSONPlaceholder API 専用クライアント
# =============================================================================


class SyncJSONPlaceholderClient(SyncAPIClient):
    """JSONPlaceholder API専用クライアント"""

    # Posts API
    def get_posts(self, limit: int | None = None, user_id: int | None = None) -> list[Post]:
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
        return _parse_response_model_list(response, Post)

    def get_post(self, post_id: int) -> Post:
        """特定投稿の取得"""
        response = self.get(f"/posts/{post_id}")
        return _parse_response_model(response, Post)

    def create_post(self, title: str, body: str, user_id: int) -> Post:
        """新規投稿の作成"""
        data = {"title": title, "body": body, "userId": user_id}
        response = self.post("/posts", json=data)
        return _parse_response_model(response, Post)

    # Users API
    def get_users(self) -> list[User]:
        """ユーザー一覧の取得"""
        response = self.get("/users")
        return _parse_response_model_list(response, User)

    def get_user(self, user_id: int) -> User:
        """特定ユーザーの取得"""
        response = self.get(f"/users/{user_id}")
        return _parse_response_model(response, User)

    # Todos API
    def get_todos(
        self,
        user_id: int | None = None,
        completed: bool | None = None,
        limit: int | None = None,
    ) -> list[Todo]:
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
        return _parse_response_model_list(response, Todo)

    def get_todo(self, todo_id: int) -> Todo:
        """特定TODOの取得"""
        response = self.get(f"/todos/{todo_id}")
        return _parse_response_model(response, Todo)

    def create_todo(self, title: str, user_id: int, completed: bool = False) -> Todo:
        """新規TODOの作成"""
        data = {"title": title, "userId": user_id, "completed": completed}
        response = self.post("/todos", json=data)
        return _parse_response_model(response, Todo)

    def update_todo(self, todo_id: int, **kwargs: Any) -> dict[str, Any]:
        """TODOの更新

        Note:
            ``**kwargs`` による部分更新（PATCH）のため、レスポンスは可変な
            部分オブジェクトになりうる。検証モデル（Todo）に固定せず生のdictを
            返すのは意図的な設計（必須フィールド欠落で ``extra="forbid"`` の
            検証が失敗するのを避けるため）。
        """
        response = self.patch(f"/todos/{todo_id}", json=kwargs)
        return _safe_parse_json(response)

    # Comments API
    def get_comments(self, post_id: int | None = None) -> list[Comment]:
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
        return _parse_response_model_list(response, Comment)

    # Albums & Photos API
    def get_albums(self, user_id: int | None = None) -> list[Album]:
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
        return _parse_response_model_list(response, Album)

    def get_photos(self, album_id: int | None = None) -> list[Photo]:
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
        return _parse_response_model_list(response, Photo)

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
            同期版はasyncioタスクキャンセル文脈を持たないため、
            Async版と異なりCancelledErrorの再発生処理は不要。
            ログ出力（``health_check_failed`` イベント）では ``error`` フィールドを省略し、
            ``error_type`` のみ記録する（``_classify_error()`` は経由せず
            直接 ``logger.warning`` を呼び出す）。

        Example:
            >>> with SyncJSONPlaceholderClient() as client:
            ...     if client.health_check():
            ...         print("API is healthy")

        """
        try:
            response = self.get("/users", params={"_limit": 1})
            return response.status_code == 200
        except SYNC_FATAL_EXCEPTIONS:
            # システム例外は再発生（K8s OOMKilled検知、graceful shutdown対応）
            raise
        except APIClientError as e:
            # 予期されるAPI例外のみキャッチ
            self.logger.warning(
                "health_check_failed",
                error_type=type(e).__name__,
                endpoint="/users",  # health_check は常に固定エンドポイント（非機密）
            )
            return False


# =============================================================================
# JSONPlaceholder Async APIクライアント
# =============================================================================

# 一括作成の部分失敗ログで記録する詳細の上限件数
_MAX_LOGGED_FAILURE_DETAILS: Final[int] = 5


class UserDataDict(TypedDict):
    """get_user_data() の戻り値型

    asyncio.gather で並行取得した4リソースを集約。
    TypedDict により mypy の型チェックを通過させつつ、
    ランタイムオーバーヘッドゼロで dict 互換性を維持。
    """

    user: User
    posts: list[Post]
    todos: list[Todo]
    albums: list[Album]


class AsyncJSONPlaceholderClient(AsyncAPIClient):
    """JSONPlaceholder API専用非同期クライアント"""

    # Posts API
    async def get_posts(self, limit: int | None = None, user_id: int | None = None) -> list[Post]:
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
        return _parse_response_model_list(response, Post)

    async def get_post(self, post_id: int) -> Post:
        """特定投稿の非同期取得"""
        response = await self.get(f"/posts/{post_id}")
        return _parse_response_model(response, Post)

    async def create_post(self, title: str, body: str, user_id: int) -> Post:
        """新規投稿の非同期作成"""
        data = {"title": title, "body": body, "userId": user_id}
        response = await self.post("/posts", json=data)
        return _parse_response_model(response, Post)

    async def update_post(self, post_id: int, title: str, body: str) -> dict[str, Any]:
        """投稿更新の非同期実行

        Note:
            本メソッドは ``title`` と ``body`` のみ送信し ``userId`` を含めない。
            JSONPlaceholder の PUT は送信フィールド ＋ ``id`` のみをエコーするため
            （実測: ``PUT /posts/1`` で ``{"title", "body", "id"}`` を返却、
            ``userId`` は欠落）、必須フィールド ``user_id`` ＋ ``extra="forbid"`` を
            持つ Post モデルでは検証が失敗する。``update_todo`` (PATCH) と同様、
            部分的なレスポンスを検証モデルに固定せず生のdictで返すのは意図的な設計。
        """
        data = {"title": title, "body": body}
        response = await self.put(f"/posts/{post_id}", json=data)
        return _safe_parse_json(response)

    async def delete_post(self, post_id: int) -> None:
        """投稿削除の非同期実行"""
        await self.delete(f"/posts/{post_id}")

    # Users API
    async def get_users(self) -> list[User]:
        """ユーザー一覧の非同期取得"""
        response = await self.get("/users")
        return _parse_response_model_list(response, User)

    async def get_user(self, user_id: int) -> User:
        """特定ユーザーの非同期取得"""
        response = await self.get(f"/users/{user_id}")
        return _parse_response_model(response, User)

    # Todos API
    async def get_todos(
        self,
        user_id: int | None = None,
        completed: bool | None = None,
        limit: int | None = None,
    ) -> list[Todo]:
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
        return _parse_response_model_list(response, Todo)

    async def get_todo(self, todo_id: int) -> Todo:
        """特定TODOの非同期取得"""
        response = await self.get(f"/todos/{todo_id}")
        return _parse_response_model(response, Todo)

    async def create_todo(
        self,
        title: str,
        user_id: int,
        completed: bool = False,
    ) -> Todo:
        """新規TODOの非同期作成"""
        data = {"title": title, "userId": user_id, "completed": completed}
        response = await self.post("/todos", json=data)
        return _parse_response_model(response, Todo)

    async def update_todo(self, todo_id: int, **kwargs: Any) -> dict[str, Any]:
        """TODOの非同期更新

        Note:
            ``**kwargs`` による部分更新（PATCH）のため、レスポンスは可変な
            部分オブジェクトになりうる。検証モデル（Todo）に固定せず生のdictを
            返すのは意図的な設計（必須フィールド欠落で ``extra="forbid"`` の
            検証が失敗するのを避けるため）。
        """
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
        失敗時はwarningログを出力（詳細は _MAX_LOGGED_FAILURE_DETAILS 件まで記録）。
        K8s SIGTERM等で複数タスクが同時キャンセルされた場合はerrorログを出力後、
        CancelledError等のfatal例外を再発生させる（graceful shutdown保護）。

        Args:
            users_data: 作成するユーザーデータのリスト（各要素はname/emailを含むdict）

        Returns:
            成功したユーザーデータのリスト（失敗した分は除外される）。
            部分失敗時は入力件数より短いリストを返す。

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
        fatal_exceptions = [r for r in results if isinstance(r, ASYNC_FATAL_EXCEPTIONS)]
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
            failed_details = []
            for i, result in enumerate(results):
                if isinstance(result, BaseException):
                    failed_details.append(
                        {
                            "index": i,
                            "error_type": type(result).__name__,
                            # 422 vs 503 を区別
                            **(
                                {"status_code": result.status_code}
                                if isinstance(result, APIHTTPError)
                                else {}
                            ),
                        }
                    )
            # PII除去設計: ログには index/error_type/status_code のみ記録。
            # index はリクエスト配列内の元位置を示す（失敗行の特定・照合用）。
            self.logger.warning(
                "bulk_create_partial_failure",
                failed_count=len(failed),
                success_count=len(successful),
                failed_details=failed_details[:_MAX_LOGGED_FAILURE_DETAILS],
                details_truncated=len(failed_details) > _MAX_LOGGED_FAILURE_DETAILS,
            )

        return successful

    # Comments API
    async def get_comments(self, post_id: int | None = None) -> list[Comment]:
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
        return _parse_response_model_list(response, Comment)

    # Albums & Photos API
    async def get_albums(self, user_id: int | None = None) -> list[Album]:
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
        return _parse_response_model_list(response, Album)

    async def get_photos(self, album_id: int | None = None) -> list[Photo]:
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
        return _parse_response_model_list(response, Photo)

    # 並行処理の例
    async def get_user_data(self, user_id: int) -> UserDataDict:
        """ユーザーに関連するデータを並行取得"""
        # 並行してユーザー情報、投稿、TODO、アルバムを取得
        user_task = self.get_user(user_id)
        posts_task = self.get_posts(user_id=user_id)
        todos_task = self.get_todos(user_id=user_id)
        albums_task = self.get_albums(user_id=user_id)

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

    async def health_check(self) -> bool:
        """API接続の健全性チェック

        Docker/Kubernetes readiness probeとして使用可能。
        軽量なリクエスト（/users?_limit=1）でAPI到達性を確認。

        Returns:
            bool: API到達可能ならTrue、エラー時はFalse

        Note:
            ログ出力（``health_check_failed`` イベント）では ``error`` フィールドを省略し、
            ``error_type`` のみ記録する（``_classify_error()`` は経由せず
            直接 ``logger.warning`` を呼び出す）。

        Example:
            >>> async with AsyncJSONPlaceholderClient() as client:
            ...     if await client.health_check():
            ...         print("API is healthy")

        """
        try:
            response = await self.get("/users", params={"_limit": 1})
            return response.status_code == 200
        except ASYNC_FATAL_EXCEPTIONS:
            # システム例外・タスクキャンセルは再発生（K8s対応、graceful shutdown）
            raise
        except APIClientError as e:
            # 予期されるAPI例外のみキャッチ
            self.logger.warning(
                "health_check_failed",
                error_type=type(e).__name__,
                endpoint="/users",  # health_check は常に固定エンドポイント（非機密）
            )
            return False

    # 複数ユーザー取得（Semaphore制御）
    async def get_multiple_users(
        self,
        user_ids: list[int],
        max_concurrent: int = 5,
    ) -> list[User]:
        """複数ユーザーを並行取得（Semaphore制御付き）

        asyncio.Semaphoreを使用してRate Limit対策。
        GitHub APIなど制限のあるAPIでも安全に並行リクエスト可能。

        Args:
            user_ids: 取得対象のユーザーIDリスト
            max_concurrent: 同時実行数の上限（デフォルト5）

        Returns:
            list[User]: 取得成功したユーザー情報リスト
                       （取得失敗したIDはスキップ、warningログ出力）

        Example:
            >>> async with AsyncJSONPlaceholderClient() as client:
            ...     users = await client.get_multiple_users([1, 2, 3], max_concurrent=2)
            ...     print(f"Fetched {len(users)} users")

        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def fetch_with_semaphore(user_id: int) -> User | None:
            """Semaphore制御付きでユーザー取得"""
            async with semaphore:
                try:
                    return await self.get_user(user_id)
                except ASYNC_FATAL_EXCEPTIONS:
                    # システム例外・タスクキャンセルは再発生（並行処理全体を停止）
                    raise
                except APIClientError as e:
                    # 予期されるAPI例外のみキャッチ（graceful degradation）
                    self.logger.warning(
                        "get_user_failed",
                        user_id=user_id,
                        error_type=type(e).__name__,
                    )
                    return None

        # 並行実行（return_exceptions不要：内部でtry-catch済み）
        results = await asyncio.gather(*[fetch_with_semaphore(uid) for uid in user_ids])

        # None除外（失敗分）
        successful = [r for r in results if r is not None]
        failed_count = len(user_ids) - len(successful)
        if failed_count:
            self.logger.warning(
                "get_multiple_users_partial_failure_summary",
                failed_count=failed_count,
                success_count=len(successful),
                requested_count=len(user_ids),
            )
        return successful


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
                print(f"  - Post {post.id}: {post.title[:50]}...")

            # 特定ユーザーの取得
            print("\n2. ユーザー情報取得（ID: 1）:")
            user = client.get_user(1)
            print(f"  - Name: {user.name}")
            print(f"  - Email: {user.email}")
            print(f"  - Company: {user.company.name}")

            # TODOの取得
            print("\n3. TODO取得（完了済み、3件）:")
            todos = client.get_todos(completed=True, limit=3)
            for todo in todos:
                status = "✓" if todo.completed else "✗"
                print(f"  {status} User {todo.user_id}: {todo.title}")

            # 新規投稿の作成（テスト用）
            print("\n4. 新規投稿作成テスト:")
            new_post = client.create_post(
                title="Test Post from API Client",
                body="This is a test post created by our API client.",
                user_id=1,
            )
            print(f"  - Created post ID: {new_post.id}")
            print(f"  - Title: {new_post.title}")

        except APIClientError as e:
            # {e}: _map_request_error()経由の場合は固定プレフィックス+クラス名のみ。デモ用表示のみ
            print(f"エラーが発生しました: {type(e).__name__}: {e}")
            if settings.debug:
                import traceback

                # chain=False: __cause__のhttpx例外チェーンのみ非表示。本体のスタックトレースは表示される  # noqa: E501
                traceback.print_exception(e, chain=False)

    print("\n=== Demo completed ===")


if __name__ == "__main__":
    # structlogはget_logger()初回呼び出し時に自動設定されるため、手動設定不要
    main()
