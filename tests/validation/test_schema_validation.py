"""
APIスキーマ検証回帰テスト

学習目標:
- JSONレスポンスの構造が期待通りであることを検証
- APIスキーマの後方互換性を保証
- データ型とフィールド存在の一貫性を確認
- スキーマ変更検出による回帰防止
"""

from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from utils.api_client import AsyncJSONPlaceholderClient


class TestPostsSchema:
    """投稿APIスキーマの回帰テスト"""

    @pytest.mark.asyncio
    async def test_get_posts_schema(self, mock_httpx_async_client):
        """投稿一覧取得のスキーマ一貫性確認"""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": 1,
                "userId": 1,
                "title": "sunt aut facere repellat provident",
                "body": "quia et suscipit\nsuscipit recusandae",
            },
            {
                "id": 2,
                "userId": 1,
                "title": "qui est esse",
                "body": "est rerum tempore vitae\nsequi sint nihil",
            },
        ]
        mock_response.raise_for_status.return_value = None

        mock_httpx_async_client.request = AsyncMock(return_value=mock_response)

        async with AsyncJSONPlaceholderClient() as client:
            client._client = mock_httpx_async_client
            posts = await client.get_posts(limit=2)

            # スキーマ検証: 必須フィールドの存在確認
            assert len(posts) == 2
            for post in posts:
                assert "id" in post
                assert "userId" in post
                assert "title" in post
                assert "body" in post

                # データ型検証
                assert isinstance(post["id"], int)
                assert isinstance(post["userId"], int)
                assert isinstance(post["title"], str)
                assert isinstance(post["body"], str)

    @pytest.mark.asyncio
    async def test_get_post_schema(self, mock_httpx_async_client):
        """単一投稿取得のスキーマ一貫性確認"""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 1,
            "userId": 1,
            "title": "sunt aut facere repellat provident",
            "body": "quia et suscipit\nsuscipit recusandae",
        }
        mock_response.raise_for_status.return_value = None

        mock_httpx_async_client.request = AsyncMock(return_value=mock_response)

        async with AsyncJSONPlaceholderClient() as client:
            client._client = mock_httpx_async_client
            post = await client.get_post(1)

            # 必須フィールドとデータ型の検証
            assert "id" in post
            assert "userId" in post
            assert "title" in post
            assert "body" in post

            assert isinstance(post["id"], int)
            assert isinstance(post["userId"], int)
            assert isinstance(post["title"], str)
            assert isinstance(post["body"], str)

    @pytest.mark.asyncio
    async def test_create_post_schema(self, mock_httpx_async_client):
        """投稿作成レスポンスのスキーマ一貫性確認"""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": 101,
            "userId": 1,
            "title": "Test Post",
            "body": "Test content",
        }
        mock_response.raise_for_status.return_value = None

        mock_httpx_async_client.request = AsyncMock(return_value=mock_response)

        async with AsyncJSONPlaceholderClient() as client:
            client._client = mock_httpx_async_client
            post = await client.create_post(title="Test Post", body="Test content", user_id=1)

            # 作成レスポンスのスキーマ検証
            assert "id" in post
            assert "userId" in post
            assert "title" in post
            assert "body" in post

            assert isinstance(post["id"], int)
            assert post["id"] == 101


class TestUsersSchema:
    """ユーザーAPIスキーマの回帰テスト"""

    @pytest.mark.asyncio
    async def test_get_users_schema(self, mock_httpx_async_client):
        """ユーザー一覧取得のスキーマ一貫性確認"""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": 1,
                "name": "Leanne Graham",
                "username": "Bret",
                "email": "Sincere@april.biz",
                "address": {
                    "street": "Kulas Light",
                    "suite": "Apt. 556",
                    "city": "Gwenborough",
                    "zipcode": "92998-3874",
                    "geo": {"lat": "-37.3159", "lng": "81.1496"},
                },
                "phone": "1-770-736-8031 x56442",
                "website": "hildegard.org",
                "company": {
                    "name": "Romaguera-Crona",
                    "catchPhrase": "Multi-layered client-server neural-net",
                    "bs": "harness real-time e-markets",
                },
            }
        ]
        mock_response.raise_for_status.return_value = None

        mock_httpx_async_client.request = AsyncMock(return_value=mock_response)

        async with AsyncJSONPlaceholderClient() as client:
            client._client = mock_httpx_async_client
            users = await client.get_users()

            # スキーマ検証: 必須フィールドの存在確認
            assert len(users) == 1
            user = users[0]

            # トップレベルフィールド
            assert "id" in user
            assert "name" in user
            assert "username" in user
            assert "email" in user
            assert "address" in user
            assert "phone" in user
            assert "website" in user
            assert "company" in user

            # データ型検証
            assert isinstance(user["id"], int)
            assert isinstance(user["name"], str)
            assert isinstance(user["email"], str)

            # ネストオブジェクトのスキーマ検証
            assert isinstance(user["address"], dict)
            assert "street" in user["address"]
            assert "city" in user["address"]
            assert "geo" in user["address"]
            assert isinstance(user["address"]["geo"], dict)

            assert isinstance(user["company"], dict)
            assert "name" in user["company"]
            assert isinstance(user["company"]["name"], str)

    @pytest.mark.asyncio
    async def test_get_user_schema(self, mock_httpx_async_client):
        """単一ユーザー取得のスキーマ一貫性確認"""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 1,
            "name": "Leanne Graham",
            "username": "Bret",
            "email": "Sincere@april.biz",
            "address": {
                "street": "Kulas Light",
                "city": "Gwenborough",
                "geo": {"lat": "-37.3159", "lng": "81.1496"},
            },
            "company": {"name": "Romaguera-Crona"},
        }
        mock_response.raise_for_status.return_value = None

        mock_httpx_async_client.request = AsyncMock(return_value=mock_response)

        async with AsyncJSONPlaceholderClient() as client:
            client._client = mock_httpx_async_client
            user = await client.get_user(1)

            # 必須フィールド検証
            assert "id" in user
            assert "name" in user
            assert "email" in user
            assert "company" in user
            assert "name" in user["company"]

            # データ型検証
            assert isinstance(user["id"], int)
            assert isinstance(user["name"], str)
            assert isinstance(user["email"], str)


class TestTodosSchema:
    """TODO APIスキーマの回帰テスト"""

    @pytest.mark.asyncio
    async def test_get_todos_schema(self, mock_httpx_async_client):
        """TODO一覧取得のスキーマ一貫性確認"""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": 1,
                "userId": 1,
                "title": "delectus aut autem",
                "completed": False,
            },
            {
                "id": 2,
                "userId": 1,
                "title": "quis ut nam facilis et officia qui",
                "completed": True,
            },
        ]
        mock_response.raise_for_status.return_value = None

        mock_httpx_async_client.request = AsyncMock(return_value=mock_response)

        async with AsyncJSONPlaceholderClient() as client:
            client._client = mock_httpx_async_client
            todos = await client.get_todos(user_id=1, limit=2)

            # スキーマ検証: 必須フィールドの存在確認
            assert len(todos) == 2
            for todo in todos:
                assert "id" in todo
                assert "userId" in todo
                assert "title" in todo
                assert "completed" in todo

                # データ型検証
                assert isinstance(todo["id"], int)
                assert isinstance(todo["userId"], int)
                assert isinstance(todo["title"], str)
                assert isinstance(todo["completed"], bool)

    @pytest.mark.asyncio
    async def test_get_todo_schema(self, mock_httpx_async_client):
        """単一TODO取得のスキーマ一貫性確認"""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 1,
            "userId": 1,
            "title": "delectus aut autem",
            "completed": False,
        }
        mock_response.raise_for_status.return_value = None

        mock_httpx_async_client.request = AsyncMock(return_value=mock_response)

        async with AsyncJSONPlaceholderClient() as client:
            client._client = mock_httpx_async_client
            todo = await client.get_todo(1)

            # 必須フィールドとデータ型の検証
            assert "id" in todo
            assert "userId" in todo
            assert "title" in todo
            assert "completed" in todo

            assert isinstance(todo["id"], int)
            assert isinstance(todo["userId"], int)
            assert isinstance(todo["title"], str)
            assert isinstance(todo["completed"], bool)

    @pytest.mark.asyncio
    async def test_create_todo_schema(self, mock_httpx_async_client):
        """TODO作成レスポンスのスキーマ一貫性確認"""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": 201,
            "userId": 1,
            "title": "New Todo",
            "completed": False,
        }
        mock_response.raise_for_status.return_value = None

        mock_httpx_async_client.request = AsyncMock(return_value=mock_response)

        async with AsyncJSONPlaceholderClient() as client:
            client._client = mock_httpx_async_client
            todo = await client.create_todo(title="New Todo", user_id=1)

            # 作成レスポンスのスキーマ検証
            assert "id" in todo
            assert "userId" in todo
            assert "title" in todo
            assert "completed" in todo

            assert isinstance(todo["id"], int)
            assert todo["id"] == 201


class TestCommentsSchema:
    """コメントAPIスキーマの回帰テスト"""

    @pytest.mark.asyncio
    async def test_get_comments_schema(self, mock_httpx_async_client):
        """コメント一覧取得のスキーマ一貫性確認"""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": 1,
                "postId": 1,
                "name": "id labore ex et quam laborum",
                "email": "Eliseo@gardner.biz",
                "body": "laudantium enim quasi est quidem magnam",
            },
            {
                "id": 2,
                "postId": 1,
                "name": "quo vero reiciendis velit similique earum",
                "email": "Jayne_Kuhic@sydney.com",
                "body": "est natus enim nihil est dolore omnis",
            },
        ]
        mock_response.raise_for_status.return_value = None

        mock_httpx_async_client.request = AsyncMock(return_value=mock_response)

        async with AsyncJSONPlaceholderClient() as client:
            client._client = mock_httpx_async_client
            comments = await client.get_comments(post_id=1)

            # スキーマ検証: 必須フィールドの存在確認
            assert len(comments) == 2
            for comment in comments:
                assert "id" in comment
                assert "postId" in comment
                assert "name" in comment
                assert "email" in comment
                assert "body" in comment

                # データ型検証
                assert isinstance(comment["id"], int)
                assert isinstance(comment["postId"], int)
                assert isinstance(comment["name"], str)
                assert isinstance(comment["email"], str)
                assert isinstance(comment["body"], str)

    @pytest.mark.asyncio
    async def test_get_all_comments_schema(self, mock_httpx_async_client):
        """全コメント取得のスキーマ一貫性確認"""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": 1,
                "postId": 1,
                "name": "comment name",
                "email": "test@example.com",
                "body": "comment body",
            }
        ]
        mock_response.raise_for_status.return_value = None

        mock_httpx_async_client.request = AsyncMock(return_value=mock_response)

        async with AsyncJSONPlaceholderClient() as client:
            client._client = mock_httpx_async_client
            comments = await client.get_comments()

            # スキーマ検証
            assert len(comments) == 1
            comment = comments[0]

            assert "id" in comment
            assert "postId" in comment
            assert "name" in comment
            assert "email" in comment
            assert "body" in comment


class TestAlbumsSchema:
    """アルバムAPIスキーマの回帰テスト"""

    @pytest.mark.asyncio
    async def test_get_albums_schema(self, mock_httpx_async_client):
        """アルバム一覧取得のスキーマ一貫性確認"""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": 1, "userId": 1, "title": "quidem molestiae enim"},
            {"id": 2, "userId": 1, "title": "sunt qui excepturi placeat culpa"},
        ]
        mock_response.raise_for_status.return_value = None

        mock_httpx_async_client.request = AsyncMock(return_value=mock_response)

        async with AsyncJSONPlaceholderClient() as client:
            client._client = mock_httpx_async_client
            albums = await client.get_albums(user_id=1)

            # スキーマ検証: 必須フィールドの存在確認
            assert len(albums) == 2
            for album in albums:
                assert "id" in album
                assert "userId" in album
                assert "title" in album

                # データ型検証
                assert isinstance(album["id"], int)
                assert isinstance(album["userId"], int)
                assert isinstance(album["title"], str)

    @pytest.mark.asyncio
    async def test_get_all_albums_schema(self, mock_httpx_async_client):
        """全アルバム取得のスキーマ一貫性確認"""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": 1, "userId": 1, "title": "album title"}]
        mock_response.raise_for_status.return_value = None

        mock_httpx_async_client.request = AsyncMock(return_value=mock_response)

        async with AsyncJSONPlaceholderClient() as client:
            client._client = mock_httpx_async_client
            albums = await client.get_albums()

            # スキーマ検証
            assert len(albums) == 1
            album = albums[0]

            assert "id" in album
            assert "userId" in album
            assert "title" in album


class TestPhotosSchema:
    """写真APIスキーマの回帰テスト"""

    @pytest.mark.asyncio
    async def test_get_photos_schema(self, mock_httpx_async_client):
        """写真一覧取得のスキーマ一貫性確認"""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": 1,
                "albumId": 1,
                "title": "accusamus beatae ad facilis cum similique qui sunt",
                "url": "https://via.placeholder.com/600/92c952",
                "thumbnailUrl": "https://via.placeholder.com/150/92c952",
            },
            {
                "id": 2,
                "albumId": 1,
                "title": "reprehenderit est deserunt velit ipsam",
                "url": "https://via.placeholder.com/600/771796",
                "thumbnailUrl": "https://via.placeholder.com/150/771796",
            },
        ]
        mock_response.raise_for_status.return_value = None

        mock_httpx_async_client.request = AsyncMock(return_value=mock_response)

        async with AsyncJSONPlaceholderClient() as client:
            client._client = mock_httpx_async_client
            photos = await client.get_photos(album_id=1)

            # スキーマ検証: 必須フィールドの存在確認
            assert len(photos) == 2
            for photo in photos:
                assert "id" in photo
                assert "albumId" in photo
                assert "title" in photo
                assert "url" in photo
                assert "thumbnailUrl" in photo

                # データ型検証
                assert isinstance(photo["id"], int)
                assert isinstance(photo["albumId"], int)
                assert isinstance(photo["title"], str)
                assert isinstance(photo["url"], str)
                assert isinstance(photo["thumbnailUrl"], str)

                # URL形式の基本検証
                assert photo["url"].startswith("http")
                assert photo["thumbnailUrl"].startswith("http")

    @pytest.mark.asyncio
    async def test_get_all_photos_schema(self, mock_httpx_async_client):
        """全写真取得のスキーマ一貫性確認"""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": 1,
                "albumId": 1,
                "title": "photo title",
                "url": "https://example.com/photo.jpg",
                "thumbnailUrl": "https://example.com/thumb.jpg",
            }
        ]
        mock_response.raise_for_status.return_value = None

        mock_httpx_async_client.request = AsyncMock(return_value=mock_response)

        async with AsyncJSONPlaceholderClient() as client:
            client._client = mock_httpx_async_client
            photos = await client.get_photos()

            # スキーマ検証
            assert len(photos) == 1
            photo = photos[0]

            assert "id" in photo
            assert "albumId" in photo
            assert "title" in photo
            assert "url" in photo
            assert "thumbnailUrl" in photo


# =============================================================================
# 学習ポイント:
#
# 1. スキーマ検証の重要性:
#    - APIレスポンスの構造が期待通りであることを確認
#    - フィールドの追加・削除・型変更を早期に検出
#    - 後方互換性の維持を保証
#
# 2. リグレッションテストのパターン:
#    - 各リソースタイプごとにテストクラスを分類
#    - 一覧取得・単一取得・作成の各操作でスキーマを検証
#    - 必須フィールドの存在確認とデータ型の検証
#
# 3. ネストオブジェクトの検証:
#    - User.address, User.company のような階層構造を検証
#    - 各レベルで必須フィールドとデータ型を確認
#    - geo座標などの深いネスト構造もカバー
#
# 4. データ型の厳密な検証:
#    - int, str, bool, dict の型チェック
#    - URL形式の基本検証（http/httpsで始まることを確認）
#    - ネストオブジェクトの型チェック
#
# 5. 保守性の向上:
#    - リソースタイプごとのテストクラス分類で管理しやすい
#    - @pytest.mark.regression で識別容易
#    - 日本語ドキュメントで意図を明確化
# =============================================================================
