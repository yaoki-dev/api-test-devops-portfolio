"""Asynchronous JSONPlaceholder resource client."""

import asyncio
from typing import Any, Final, TypedDict, cast

from models.responses import Album, Comment, Photo, Post, Todo, User
from utils.exceptions import ASYNC_FATAL_EXCEPTIONS, APIClientError, APIHTTPError
from utils.http_helpers import validate_optional_int
from utils.jsonplaceholder_base_async import AsyncAPIClient
from utils.response_parsing import (
    parse_response_model,
    parse_response_model_list,
    safe_parse_json,
)

MAX_LOGGED_FAILURE_DETAILS: Final[int] = 5


class UserDataDict(TypedDict):
    """get_user_data() return type."""

    user: User
    posts: list[Post]
    todos: list[Todo]
    albums: list[Album]


class AsyncJSONPlaceholderClient(AsyncAPIClient):
    """JSONPlaceholder API専用非同期クライアント"""

    async def get_posts(self, limit: int | None = None, user_id: int | None = None) -> list[Post]:
        """投稿一覧の非同期取得

        Args:
            limit: 取得件数上限（0以上）
            user_id: ユーザーIDでフィルタリング（API側フィルタ、1以上）

        Raises:
            ValueError: limit < 0 または user_id < 1 の場合

        """
        validate_optional_int(limit, "limit", 0)
        validate_optional_int(user_id, "user_id", 1)

        params = {}
        if limit is not None:
            params["_limit"] = limit
        if user_id is not None:
            params["userId"] = user_id

        response = await self.get("/posts", params=params)
        return parse_response_model_list(response, Post)

    async def get_post(self, post_id: int) -> Post:
        """特定投稿の非同期取得"""
        response = await self.get(f"/posts/{post_id}")
        return parse_response_model(response, Post)

    async def create_post(self, title: str, body: str, user_id: int) -> Post:
        """新規投稿の非同期作成"""
        data = {"title": title, "body": body, "userId": user_id}
        response = await self.post("/posts", json=data)
        return parse_response_model(response, Post)

    async def update_post(self, post_id: int, title: str, body: str) -> dict[str, Any]:
        """投稿更新の非同期実行

        Note:
            ``title`` と ``body`` のみ送信し ``userId`` を含めない。
            JSONPlaceholder の PUT は送信フィールド ＋ ``id`` のみをエコーするため
            （実測: ``PUT /posts/1`` が ``{"title", "body", "id"}`` を返し ``userId``
            は欠落）、必須フィールド ``user_id`` ＋ ``extra="forbid"`` を持つ Post
            モデルでは検証が失敗する。``update_todo`` (PATCH) と同様、部分的な
            レスポンスを検証モデルに固定せず生の dict で返すのは意図的な設計。

        """
        data = {"title": title, "body": body}
        response = await self.put(f"/posts/{post_id}", json=data)
        return cast("dict[str, Any]", safe_parse_json(response))

    async def delete_post(self, post_id: int) -> None:
        """投稿削除の非同期実行"""
        await self.delete(f"/posts/{post_id}")

    async def get_users(self) -> list[User]:
        """ユーザー一覧の非同期取得"""
        response = await self.get("/users")
        return parse_response_model_list(response, User)

    async def get_user(self, user_id: int) -> User:
        """特定ユーザーの非同期取得"""
        response = await self.get(f"/users/{user_id}")
        return parse_response_model(response, User)

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
        validate_optional_int(limit, "limit", 0)
        validate_optional_int(user_id, "user_id", 1)

        params = {}
        if user_id is not None:
            params["userId"] = user_id
        if completed is not None:
            params["completed"] = completed
        if limit is not None:
            params["_limit"] = limit

        response = await self.get("/todos", params=params)
        return parse_response_model_list(response, Todo)

    async def get_todo(self, todo_id: int) -> Todo:
        """特定TODOの非同期取得"""
        response = await self.get(f"/todos/{todo_id}")
        return parse_response_model(response, Todo)

    async def create_todo(
        self,
        title: str,
        user_id: int,
        completed: bool = False,
    ) -> Todo:
        """新規TODOの非同期作成"""
        data = {"title": title, "userId": user_id, "completed": completed}
        response = await self.post("/todos", json=data)
        return parse_response_model(response, Todo)

    async def update_todo(self, todo_id: int, **kwargs: Any) -> dict[str, Any]:
        """TODOの非同期更新

        Note:
            ``**kwargs`` による部分更新（PATCH）のため、レスポンスは可変な
            部分オブジェクトになりうる。検証モデル（Todo）に固定せず生の dict を
            返すのは意図的な設計（必須フィールド欠落で ``extra="forbid"`` の
            検証が失敗するのを避けるため）。

        """
        response = await self.patch(f"/todos/{todo_id}", json=kwargs)
        return cast("dict[str, Any]", safe_parse_json(response))

    async def create_user(self, user_data: dict[str, Any]) -> dict[str, Any]:
        """新規ユーザーの非同期作成"""
        response = await self.post("/users", json=user_data)
        return cast("dict[str, Any]", safe_parse_json(response))

    async def bulk_create_users(self, users_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """複数ユーザーの非同期一括作成

        個別失敗を許容し、成功したユーザーのみ返却する。K8s SIGTERM 等で複数タスクが
        同時キャンセルされた場合は error ログ出力後に fatal 例外を再送出する
        （graceful shutdown 保護）。

        Args:
            users_data: 作成するユーザーデータのリスト（各要素は name/email を含む dict）

        Returns:
            成功したユーザーデータのリスト。部分失敗時は入力件数より短くなる。

        Raises:
            asyncio.CancelledError: 単一タスクがキャンセルされた場合（graceful shutdown 等）
            BaseExceptionGroup: 複数タスクが同時に fatal 例外を発生させた場合
            KeyboardInterrupt: 割り込みシグナルを受けた場合
            SystemExit: ``sys.exit()`` が呼ばれた場合
            MemoryError: メモリ不足が発生した場合
            RecursionError: 再帰上限に達した場合

        """
        tasks = [self.create_user(user_data) for user_data in users_data]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        fatal_exceptions = [r for r in results if isinstance(r, ASYNC_FATAL_EXCEPTIONS)]
        if fatal_exceptions:
            if len(fatal_exceptions) > 1:
                self.logger.error(
                    "bulk_create_multiple_fatal_errors",
                    count=len(fatal_exceptions),
                    types=[type(e).__name__ for e in fatal_exceptions],
                )
                raise BaseExceptionGroup(
                    "bulk_create_users: multiple fatal errors occurred",
                    fatal_exceptions,
                )
            exc = fatal_exceptions[0]
            raise exc

        successful: list[dict[str, Any]] = [r for r in results if isinstance(r, dict)]
        failed: list[BaseException] = [r for r in results if isinstance(r, BaseException)]

        if failed:
            failed_details = []
            for i, result in enumerate(results):
                if isinstance(result, BaseException):
                    failed_details.append(
                        {
                            "index": i,
                            "error_type": type(result).__name__,
                            **(
                                {"status_code": result.status_code}
                                if isinstance(result, APIHTTPError)
                                else {}
                            ),
                        },
                    )
            self.logger.warning(
                "bulk_create_partial_failure",
                failed_count=len(failed),
                success_count=len(successful),
                failed_details=failed_details[:MAX_LOGGED_FAILURE_DETAILS],
                details_truncated=len(failed_details) > MAX_LOGGED_FAILURE_DETAILS,
            )

        return successful

    async def get_comments(self, post_id: int | None = None) -> list[Comment]:
        """コメント一覧の非同期取得

        Args:
            post_id: 投稿IDでフィルタリング（1以上）

        Raises:
            ValueError: post_id < 1 の場合

        """
        validate_optional_int(post_id, "post_id", 1)

        if post_id is not None:
            response = await self.get(f"/posts/{post_id}/comments")
        else:
            response = await self.get("/comments")
        return parse_response_model_list(response, Comment)

    async def get_albums(self, user_id: int | None = None) -> list[Album]:
        """アルバム一覧の非同期取得

        Args:
            user_id: ユーザーIDでフィルタリング（API側フィルタ、1以上）

        Raises:
            ValueError: user_id < 1 の場合

        """
        validate_optional_int(user_id, "user_id", 1)

        params = {}
        if user_id is not None:
            params["userId"] = user_id

        response = await self.get("/albums", params=params)
        return parse_response_model_list(response, Album)

    async def get_photos(self, album_id: int | None = None) -> list[Photo]:
        """写真一覧の非同期取得

        Args:
            album_id: アルバムIDでフィルタリング（1以上）

        Raises:
            ValueError: album_id < 1 の場合

        """
        validate_optional_int(album_id, "album_id", 1)

        if album_id is not None:
            response = await self.get(f"/albums/{album_id}/photos")
        else:
            response = await self.get("/photos")
        return parse_response_model_list(response, Photo)

    async def get_user_data(self, user_id: int) -> UserDataDict:
        """ユーザーに関連するデータを並行取得

        user/posts/todos/albums の 4 取得は、集約結果 ``UserDataDict`` が全要素を
        必須とする高結合（一蓮托生）の関係にある。そのため ``asyncio.TaskGroup``
        を用い、いずれか 1 つが失敗した時点で残りを自動キャンセルして孤立タスク
        （未 await のゾンビ）を防ぐ。独立した結果回収で部分成功を許容する
        ``bulk_create_users`` の ``gather(return_exceptions=True)`` とは対照的な
        使い分けである（coding-standards.md §6）。

        Raises:
            APIClientError: いずれかの取得が失敗した場合。``TaskGroup`` が送出する
                ``ExceptionGroup`` から最初の ``APIClientError`` を取り出して送出し、
                従来どおり個別例外型（例: ``APIHTTPError`` / ``APIRetryError``）で
                呼び出し元が捕捉できる契約を維持する。

        """
        try:
            async with asyncio.TaskGroup() as tg:
                user_task = tg.create_task(self.get_user(user_id))
                posts_task = tg.create_task(self.get_posts(user_id=user_id))
                todos_task = tg.create_task(self.get_todos(user_id=user_id))
                albums_task = tg.create_task(self.get_albums(user_id=user_id))
        except* (APIClientError, ValueError) as eg:
            # 契約維持: ExceptionGroup ではなく最初の個別 APIClientError を送出。
            # ValueError は validate_optional_int（user_id < 1）由来 — 兄弟メソッド
            # get_posts/get_todos/get_albums の素の ValueError 契約と揃える。
            # （ASYNC_FATAL_EXCEPTIONS はここで捕捉されず ExceptionGroup として伝播）
            raise eg.exceptions[0] from None

        return {
            "user": user_task.result(),
            "posts": posts_task.result(),
            "todos": todos_task.result(),
            "albums": albums_task.result(),
        }

    async def health_check(self) -> bool:
        """API接続の健全性チェック

        Docker/Kubernetes readiness probe として使用可能。

        Returns:
            API到達可能なら True、エラー時は False。

        Note:
            エラー時は ``classify_error()`` を経由せず直接 ``logger.warning`` を呼び、
            ``error_type`` のみ記録する（``error`` フィールドは省略）。

        Example:
            >>> async with AsyncJSONPlaceholderClient() as client:
            ...     if await client.health_check():
            ...         print("API is healthy")

        """
        try:
            response = await self.get("/users", params={"_limit": 1})
            return response.status_code == 200
        except ASYNC_FATAL_EXCEPTIONS:
            raise
        except APIClientError as e:
            self.logger.warning(
                "health_check_failed",
                error_type=type(e).__name__,
                endpoint="/users",
            )
            return False

    async def get_multiple_users(
        self,
        user_ids: list[int],
        max_concurrent: int = 5,
    ) -> list[User]:
        """複数ユーザーを並行取得（Semaphore 制御付き）

        ``asyncio.Semaphore`` で同時実行数を制限し、Rate Limit のある API でも
        安全に並行リクエストする。

        Args:
            user_ids: 取得対象のユーザーIDリスト
            max_concurrent: 同時実行数の上限（デフォルト 5）

        Returns:
            取得成功したユーザー情報リスト（失敗した ID はスキップし warning ログ出力）。

        Raises:
            asyncio.CancelledError: タスクがキャンセルされた場合（graceful shutdown 等）
            KeyboardInterrupt: 割り込みシグナルを受けた場合
            SystemExit: ``sys.exit()`` が呼ばれた場合
            MemoryError: メモリ不足が発生した場合
            RecursionError: 再帰上限に達した場合

        Example:
            >>> async with AsyncJSONPlaceholderClient() as client:
            ...     users = await client.get_multiple_users([1, 2, 3], max_concurrent=2)
            ...     print(f"Fetched {len(users)} users")

        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def fetch_with_semaphore(user_id: int) -> User | None:
            async with semaphore:
                try:
                    return await self.get_user(user_id)
                except ASYNC_FATAL_EXCEPTIONS:
                    raise
                except APIClientError as e:
                    self.logger.warning(
                        "get_user_failed",
                        user_id=user_id,
                        error_type=type(e).__name__,
                    )
                    return None

        results = await asyncio.gather(*[fetch_with_semaphore(uid) for uid in user_ids])

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
