"""JSONPlaceholder 同期リソースクライアント"""

from typing import Any

from models.responses import Album, Comment, Photo, Post, Todo, User
from utils.exceptions import SYNC_FATAL_EXCEPTIONS, APIClientError
from utils.http_helpers import validate_optional_int
from utils.jsonplaceholder_base_sync import SyncAPIClient
from utils.response_parsing import (
    parse_response_model,
    parse_response_model_list,
    safe_parse_json_object,
)


class SyncJSONPlaceholderClient(SyncAPIClient):
    """JSONPlaceholder API専用クライアント"""

    def get_posts(self, limit: int | None = None, user_id: int | None = None) -> list[Post]:
        """投稿一覧の取得

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

        response = self.get("/posts", params=params)
        return parse_response_model_list(response, Post)

    def get_post(self, post_id: int) -> Post:
        """特定投稿の取得"""
        response = self.get(f"/posts/{post_id}")
        return parse_response_model(response, Post)

    def create_post(
        self,
        title: str,
        body: str,
        user_id: int,
        *,
        retry_non_idempotent: bool = False,
    ) -> Post:
        """新規投稿の作成。

        ``retry_non_idempotent`` は、冪等キーまたはサーバー側の重複排除契約が
        ある場合だけ有効化する。
        """
        data = {"title": title, "body": body, "userId": user_id}
        response = self.post("/posts", json=data, retry_non_idempotent=retry_non_idempotent)
        return parse_response_model(response, Post)

    def update_post(
        self,
        post_id: int,
        title: str,
        body: str,
        *,
        retry_non_idempotent: bool = False,
    ) -> dict[str, Any]:
        """投稿更新の実行

        Note:
            ``title`` と ``body`` のみ送信し ``userId`` を含めない。
            JSONPlaceholder の PUT は送信フィールド ＋ ``id`` のみをエコーするため
            （実測: ``PUT /posts/1`` が ``{"title", "body", "id"}`` を返し ``userId``
            は欠落）、必須フィールド ``user_id`` ＋ ``extra="forbid"`` を持つ Post
            モデルでは検証が失敗する。``update_todo`` (PATCH) と同様、部分的な
            レスポンスを検証モデルに固定せず生の dict で返すのは意図的な設計。

        Args:
            post_id: 更新対象の投稿ID
            title: 更新後のタイトル
            body: 更新後の本文
            retry_non_idempotent: PUTの再送を安全に許可できる場合だけTrue

        Returns:
            JSONPlaceholderが返した部分的な投稿データ

        Raises:
            APIClientError: HTTPリクエストまたはレスポンスのJSONパースに失敗した場合
                （レスポンスのトップレベルがJSONオブジェクトでない場合を含む）

        """
        data = {"title": title, "body": body}
        response = self.put(
            f"/posts/{post_id}",
            json=data,
            retry_non_idempotent=retry_non_idempotent,
        )
        return safe_parse_json_object(response)

    def delete_post(self, post_id: int) -> None:
        """投稿削除の実行

        Args:
            post_id: 削除対象の投稿ID

        Returns:
            None

        Raises:
            APIClientError: HTTPリクエストに失敗した場合

        """
        self.delete(f"/posts/{post_id}")

    def get_users(self) -> list[User]:
        """ユーザー一覧の取得"""
        response = self.get("/users")
        return parse_response_model_list(response, User)

    def get_user(self, user_id: int) -> User:
        """特定ユーザーの取得"""
        response = self.get(f"/users/{user_id}")
        return parse_response_model(response, User)

    def create_user(
        self,
        user_data: dict[str, Any],
        *,
        retry_non_idempotent: bool = False,
    ) -> dict[str, Any]:
        """新規ユーザーの作成

        Args:
            user_data: 作成するユーザーのフィールド
            retry_non_idempotent: サーバー側の重複排除契約がある場合だけPOST再送を許可

        Returns:
            JSONPlaceholderが返した作成済みユーザーデータ

        Raises:
            APIClientError: HTTPリクエストまたはレスポンスのJSONパースに失敗した場合
                （レスポンスのトップレベルがJSONオブジェクトでない場合を含む）

        """
        response = self.post("/users", json=user_data, retry_non_idempotent=retry_non_idempotent)
        return safe_parse_json_object(response)

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
        validate_optional_int(limit, "limit", 0)
        validate_optional_int(user_id, "user_id", 1)

        params = {}
        if user_id is not None:
            params["userId"] = user_id
        if completed is not None:
            params["completed"] = completed
        if limit is not None:
            params["_limit"] = limit

        response = self.get("/todos", params=params)
        return parse_response_model_list(response, Todo)

    def get_todo(self, todo_id: int) -> Todo:
        """特定TODOの取得"""
        response = self.get(f"/todos/{todo_id}")
        return parse_response_model(response, Todo)

    def create_todo(
        self,
        title: str,
        user_id: int,
        completed: bool = False,
        *,
        retry_non_idempotent: bool = False,
    ) -> Todo:
        """新規TODOの作成。

        ``retry_non_idempotent`` は、冪等キーまたはサーバー側の重複排除契約が
        ある場合だけ有効化する。
        """
        data = {"title": title, "userId": user_id, "completed": completed}
        response = self.post("/todos", json=data, retry_non_idempotent=retry_non_idempotent)
        return parse_response_model(response, Todo)

    def update_todo(
        self,
        todo_id: int,
        *,
        retry_non_idempotent: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """TODOの更新

        ``retry_non_idempotent`` は、冪等キーまたはサーバー側の重複排除契約が
        ある場合だけ有効化する。

        Note:
            ``**kwargs`` による部分更新（PATCH）のため、レスポンスは可変な
            部分オブジェクトになりうる。検証モデル（Todo）に固定せず生の dict を
            返すのは意図的な設計（必須フィールド欠落で ``extra="forbid"`` の
            検証が失敗するのを避けるため）。

        Raises:
            APIClientError: HTTPリクエストまたはレスポンスのJSONパースに失敗した場合
                （レスポンスのトップレベルがJSONオブジェクトでない場合を含む）
        """
        response = self.patch(
            f"/todos/{todo_id}",
            json=kwargs,
            retry_non_idempotent=retry_non_idempotent,
        )
        return safe_parse_json_object(response)

    def get_comments(self, post_id: int | None = None) -> list[Comment]:
        """コメント一覧の取得

        Args:
            post_id: 投稿IDでフィルタリング（1以上）

        Raises:
            ValueError: post_id < 1 の場合

        """
        validate_optional_int(post_id, "post_id", 1)

        if post_id is not None:
            response = self.get(f"/posts/{post_id}/comments")
        else:
            response = self.get("/comments")
        return parse_response_model_list(response, Comment)

    def get_albums(self, user_id: int | None = None) -> list[Album]:
        """アルバム一覧の取得

        Args:
            user_id: ユーザーIDでフィルタリング（API側フィルタ、1以上）

        Raises:
            ValueError: user_id < 1 の場合

        """
        validate_optional_int(user_id, "user_id", 1)

        params = {}
        if user_id is not None:
            params["userId"] = user_id

        response = self.get("/albums", params=params)
        return parse_response_model_list(response, Album)

    def get_photos(self, album_id: int | None = None) -> list[Photo]:
        """写真一覧の取得

        Args:
            album_id: アルバムIDでフィルタリング（1以上）

        Raises:
            ValueError: album_id < 1 の場合

        """
        validate_optional_int(album_id, "album_id", 1)

        if album_id is not None:
            response = self.get(f"/albums/{album_id}/photos")
        else:
            response = self.get("/photos")
        return parse_response_model_list(response, Photo)

    def health_check(self) -> bool:
        """API接続の健全性チェック（同期版）

        Docker/Kubernetes readiness probe として使用可能。

        Returns:
            API到達可能なら True、エラー時は False。

        Note:
            同期版は asyncio タスクキャンセル文脈を持たないため、Async版と異なり
            ``CancelledError`` の再送出処理は不要。エラー時は ``classify_error()``
            を経由せず直接 ``logger.warning`` を呼び、``error_type`` のみ記録する
            （``error`` フィールドは省略）。

        Example:
            >>> with SyncJSONPlaceholderClient() as client:
            ...     if client.health_check():
            ...         print("API is healthy")

        """
        try:
            response = self.get("/users", params={"_limit": 1})
            return response.status_code == 200
        except SYNC_FATAL_EXCEPTIONS:
            raise
        except APIClientError as e:
            self.logger.warning(
                "health_check_failed",
                error_type=type(e).__name__,
                endpoint="/users",
            )
            return False


def create_client() -> SyncJSONPlaceholderClient:
    """設定に基づいたクライアントインスタンスの作成"""
    return SyncJSONPlaceholderClient()
