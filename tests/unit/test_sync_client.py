"""
SyncAPIClient 基本機能テスト

Note:
    test_async_client.py と対称構造で設計。
    責務: 基本CRUD操作 + Edge Cases + DevOps

テストケース一覧（9件）:
    - Basic Operations (4件): GET, POST, PUT, DELETE
    - Edge Cases (4件): context_manager, empty_response, malformed_json, boundary
    - DevOps (1件): health_check
"""

import sys
from unittest.mock import Mock

import pytest

from tests.conftest import create_mock_response
from utils.api_client import APIConnectionError, SyncAPIClient, SyncJSONPlaceholderClient

# =============================================================================
# Basic Operations (4件)
# =============================================================================


def test_sync_get_user(mock_httpx_sync_client: Mock) -> None:
    """GETリクエスト検証"""
    mock_response = create_mock_response(200, json_data={"id": 1, "name": "Test User"})
    mock_response.raise_for_status.return_value = None
    mock_httpx_sync_client.request.return_value = mock_response

    with SyncAPIClient() as client:
        client._client = mock_httpx_sync_client
        response = client.get("/users/1")

        assert response.status_code == 200
        assert response.json()["id"] == 1
        mock_httpx_sync_client.request.assert_called_once()


def test_sync_post_create_user(mock_httpx_sync_client: Mock) -> None:
    """POSTリクエスト検証"""
    mock_response = create_mock_response(
        201,
        json_data={"id": 101, "name": "New User", "email": "new@example.com"},
    )
    mock_response.raise_for_status.return_value = None
    mock_httpx_sync_client.request.return_value = mock_response

    with SyncAPIClient() as client:
        client._client = mock_httpx_sync_client
        response = client.post("/users", json={"name": "New User", "email": "new@example.com"})

        assert response.status_code == 201
        assert response.json()["id"] == 101


def test_sync_put_update_user(mock_httpx_sync_client: Mock) -> None:
    """PUTリクエスト検証"""
    mock_response = create_mock_response(200, json_data={"id": 1, "name": "Updated"})
    mock_response.raise_for_status.return_value = None
    mock_httpx_sync_client.request.return_value = mock_response

    with SyncAPIClient() as client:
        client._client = mock_httpx_sync_client
        response = client.put("/users/1", json={"name": "Updated"})

        assert response.status_code == 200
        assert response.json()["name"] == "Updated"


def test_sync_delete_user(mock_httpx_sync_client: Mock) -> None:
    """DELETEリクエスト検証（httpx.Response返却を検証）"""
    mock_response = create_mock_response(204, json_data={})
    mock_response.raise_for_status.return_value = None
    mock_httpx_sync_client.request.return_value = mock_response

    with SyncAPIClient() as client:
        client._client = mock_httpx_sync_client
        response = client.delete("/users/1")

        assert response.status_code == 204


# =============================================================================
# Edge Cases (4件)
# Note: 例外クラス階層テストは test_sync_client_error_handling.py に集約（SRP準拠）
# =============================================================================


def test_sync_context_manager_cleanup(mock_httpx_sync_client: Mock) -> None:
    """with文コンテキストマネージャーのクリーンアップ検証"""
    mock_httpx_sync_client.close = Mock()

    with SyncAPIClient() as client:
        client._client = mock_httpx_sync_client
        # コンテキスト内でクライアントが使用可能
        assert client._client is not None

    # with文を抜けた後、closeが呼ばれることを検証
    # Note: SyncAPIClient.__exit__でself._client.close()が呼ばれる
    mock_httpx_sync_client.close.assert_called_once()


def test_sync_empty_response_handling(mock_httpx_sync_client: Mock) -> None:
    """空レスポンス（{}）の安全処理検証"""
    mock_response = create_mock_response(200, json_data={})
    mock_response.raise_for_status.return_value = None
    mock_httpx_sync_client.request.return_value = mock_response

    with SyncAPIClient() as client:
        client._client = mock_httpx_sync_client
        response = client.get("/empty")

        assert response.json() == {}


def test_sync_malformed_json_handling(mock_httpx_sync_client: Mock) -> None:
    """不正JSON時の例外処理検証"""
    mock_response = create_mock_response(200, json_data={})
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_response.raise_for_status.return_value = None
    mock_httpx_sync_client.request.return_value = mock_response

    with SyncAPIClient() as client:
        client._client = mock_httpx_sync_client
        response = client.get("/malformed")

        with pytest.raises(ValueError, match="Invalid JSON"):
            response.json()


@pytest.mark.parametrize("user_id", [0, -1, sys.maxsize], ids=["zero", "negative", "max_int"])
def test_sync_boundary_user_id(mock_httpx_sync_client: Mock, user_id: int) -> None:
    """境界値テスト: user_id=0, -1, MAX_INT（parametrize化）"""
    mock_response = create_mock_response(200, json_data={"id": user_id})
    mock_response.raise_for_status.return_value = None
    mock_httpx_sync_client.request.return_value = mock_response

    with SyncAPIClient() as client:
        client._client = mock_httpx_sync_client
        response = client.get(f"/users/{user_id}")

        assert response.json()["id"] == user_id


# =============================================================================
# DevOps (1件)
# =============================================================================


def test_sync_health_check(mock_httpx_sync_client: Mock) -> None:
    """
    API ヘルスチェック機能のテスト（同期版）

    検証項目：
    - health_check()メソッドの動作
    - 正常時: True返却
    - エラー時: False返却（graceful degradation）

    学習ポイント:
    - Docker/Kubernetes readiness probe対応
    - Sync/Async両対応の統一インターフェース設計
    """
    # Test 1: 正常時 → True
    healthy_response = create_mock_response(200, json_data=[{"id": 1, "name": "User 1"}])
    healthy_response.raise_for_status.return_value = None
    mock_httpx_sync_client.request.return_value = healthy_response

    with SyncJSONPlaceholderClient() as client:
        client._client = mock_httpx_sync_client
        result = client.health_check()

        assert result is True

        # _limit=1パラメータで軽量クエリ確認
        call_args = mock_httpx_sync_client.request.call_args
        assert "params" in call_args[1]
        assert call_args[1]["params"]["_limit"] == 1

    # Test 2: APIClientError時 → False（graceful degradation）
    mock_httpx_sync_client.reset_mock()
    mock_httpx_sync_client.request.side_effect = APIConnectionError("Connection refused")

    with SyncJSONPlaceholderClient() as client:
        client._client = mock_httpx_sync_client
        result = client.health_check()

        assert result is False


# =============================================================================
# 学習ポイント:
#
# 1. Sync/Async対称構造:
#    - test_async_client.py と同一のテスト設計
#    - 責務分離（SRP）: 基本操作 vs エラーハンドリング
#
# 2. pytest.mark.parametrize:
#    - 境界値テストの効率的な実装
#    - ids引数でテスト名を明確化
#
# 3. Mock fixtureの活用:
#    - mock_httpx_sync_client: 同期クライアント用
#    - create_mock_response: レスポンスファクトリ
#
# =============================================================================


# =============================================================================
# Issue #173: 同期クライアント未テストメソッドのカバレッジ追加
# =============================================================================


# =============================================================================
# SyncJSONPlaceholderClient: Posts API Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.parametrize(
    "limit,expected_count",
    [(2, 2), (None, 5), (0, 0), (100, 5)],
    ids=["with_limit", "no_limit", "zero_limit", "excessive_limit"],
)
def test_sync_get_posts(
    mock_httpx_sync_client: Mock, limit: int | None, expected_count: int
) -> None:
    """
    SyncJSONPlaceholderClient.get_posts()のlimitパラメータ検証

    検証項目：
    - limit指定時に正しくパラメータが送信される
    - limit=Noneで全件取得
    - limit=0で0件取得（API仕様では空配列返却、境界値検証）

    学習ポイント:
    - 同期APIクライアントのテストパターン
    - unittest.mockを使用した同期テスト
    - API実動作に基づくテスト設計（推測ではなく検証）
    """
    all_posts = [
        {"id": i, "userId": 1, "title": f"Post {i}", "body": f"Content {i}"} for i in range(1, 6)
    ]

    # limitパラメータに応じてモックデータを設定
    if limit is None:
        mock_data = all_posts
    elif limit == 0:
        # API仕様: _limit=0は空配列[]を返却
        mock_data = []
    else:
        mock_data = all_posts[:limit]

    mock_response = create_mock_response(200, json_data=mock_data)
    mock_response.raise_for_status.return_value = None
    mock_httpx_sync_client.request.return_value = mock_response

    with SyncJSONPlaceholderClient() as client:
        client._client = mock_httpx_sync_client
        result = client.get_posts(limit=limit)

    assert len(result) == expected_count
    assert result == mock_data


@pytest.mark.unit
def test_sync_get_post_success(mock_httpx_sync_client: Mock) -> None:
    """
    SyncJSONPlaceholderClient.get_post()の正常系テスト

    検証項目：
    - post_id指定で特定投稿を取得
    - レスポンスデータが正確に返却される

    学習ポイント:
    - RESTful API: 個別リソース取得パターン
    - _safe_parse_json()による安全なJSONパース
    """
    post_id = 1
    expected_post = {"id": 1, "userId": 1, "title": "Test Post", "body": "Test Content"}

    mock_response = create_mock_response(200, json_data=expected_post)
    mock_response.raise_for_status.return_value = None
    mock_httpx_sync_client.request.return_value = mock_response

    with SyncJSONPlaceholderClient() as client:
        client._client = mock_httpx_sync_client
        result = client.get_post(post_id)

    assert result == expected_post
    assert result["id"] == post_id


@pytest.mark.unit
def test_sync_create_post(mock_httpx_sync_client: Mock) -> None:
    """
    SyncJSONPlaceholderClient.create_post()の正常系テスト

    検証項目：
    - title/body/user_id指定で投稿作成
    - レスポンスにidが付与される（サーバー生成）
    - POSTリクエストが正しく送信される

    学習ポイント:
    - RESTful POST: リソース作成操作
    - レスポンスデータ: サーバー生成フィールド（id）の確認
    """
    title = "New Post"
    body = "This is a new post content"
    user_id = 1

    expected_response = {
        "id": 101,  # サーバーが生成したID
        "userId": user_id,
        "title": title,
        "body": body,
    }

    mock_response = create_mock_response(201, json_data=expected_response)
    mock_response.raise_for_status.return_value = None
    mock_httpx_sync_client.request.return_value = mock_response

    with SyncJSONPlaceholderClient() as client:
        client._client = mock_httpx_sync_client
        result = client.create_post(title=title, body=body, user_id=user_id)

    assert result["id"] == 101
    assert result["userId"] == user_id
    assert result["title"] == title
    assert result["body"] == body


# =============================================================================
# SyncJSONPlaceholderClient: Todos API Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.parametrize(
    "user_id,completed,limit,expected_count",
    [
        (1, True, 5, 2),
        (1, None, None, 3),
        (None, False, 10, 2),
        (None, None, None, 5),
    ],
    ids=["all_params", "user_id_only", "completed_and_limit", "no_params"],
)
def test_sync_get_todos(
    mock_httpx_sync_client: Mock,
    user_id: int | None,
    completed: bool | None,
    limit: int | None,
    expected_count: int,
) -> None:
    """
    SyncJSONPlaceholderClient.get_todos()の複数パラメータ組み合わせ検証

    検証項目：
    - user_id/completed/limitの全組み合わせ動作確認
    - クエリパラメータが正確に構築される
    - Noneパラメータは送信されない

    学習ポイント:
    - pytest.parametrize: 3パラメータの組み合わせテスト
    - 同期APIクライアントのフィルタ処理検証
    """
    all_todos = [
        {"id": 1, "userId": 1, "title": "Todo 1", "completed": True},
        {"id": 2, "userId": 1, "title": "Todo 2", "completed": False},
        {"id": 3, "userId": 1, "title": "Todo 3", "completed": True},
        {"id": 4, "userId": 2, "title": "Todo 4", "completed": True},
        {"id": 5, "userId": 2, "title": "Todo 5", "completed": False},
    ]

    # パラメータに応じてフィルタされたモックデータを作成
    filtered_todos = all_todos
    if user_id:
        filtered_todos = [t for t in filtered_todos if t["userId"] == user_id]
    if completed is not None:
        filtered_todos = [t for t in filtered_todos if t["completed"] == completed]
    if limit:
        filtered_todos = filtered_todos[:limit]

    mock_response = create_mock_response(200, json_data=filtered_todos)
    mock_response.raise_for_status.return_value = None
    mock_httpx_sync_client.request.return_value = mock_response

    with SyncJSONPlaceholderClient() as client:
        client._client = mock_httpx_sync_client
        result = client.get_todos(user_id=user_id, completed=completed, limit=limit)

    assert len(result) == expected_count
    assert result == filtered_todos


# =============================================================================
# Issue #173: Albums API テスト追加（カバレッジ85%達成）
# =============================================================================


@pytest.mark.unit
@pytest.mark.parametrize(
    "user_id,expected_count",
    [(1, 2), (None, 5), (2, 1)],
    ids=["user_id_1", "no_user_id", "user_id_2"],
)
def test_sync_get_albums(
    mock_httpx_sync_client: Mock, user_id: int | None, expected_count: int
) -> None:
    """
    SyncJSONPlaceholderClient.get_albums()のuser_idパラメータ検証

    検証項目：
    - user_id指定時に正しくパラメータが送信される
    - user_id=Noneで全件取得
    - フィルタ結果が期待通りの件数である

    学習ポイント:
    - Albums API: ユーザーごとのアルバム管理
    - 同期APIクライアントのテストパターン
    """
    # モックデータ（5件のアルバム、複数ユーザー）
    all_albums = [
        {"id": 1, "userId": 1, "title": "Album 1"},
        {"id": 2, "userId": 1, "title": "Album 2"},
        {"id": 3, "userId": 2, "title": "Album 3"},
        {"id": 4, "userId": 3, "title": "Album 4"},
        {"id": 5, "userId": 3, "title": "Album 5"},
    ]

    # パラメータに応じてフィルタ
    if user_id:
        mock_data = [a for a in all_albums if a["userId"] == user_id]
    else:
        mock_data = all_albums

    mock_response = create_mock_response(200, json_data=mock_data)
    mock_response.raise_for_status.return_value = None
    mock_httpx_sync_client.request.return_value = mock_response

    with SyncJSONPlaceholderClient() as client:
        client._client = mock_httpx_sync_client
        result = client.get_albums(user_id=user_id)

    assert len(result) == expected_count
    assert result == mock_data


# =============================================================================
# Photos API テスト追加
# =============================================================================


@pytest.mark.unit
@pytest.mark.parametrize(
    "album_id,expected_count",
    [(1, 2), (None, 6), (2, 1)],
    ids=["album_id_1", "no_album_id", "album_id_2"],
)
def test_sync_get_photos(
    mock_httpx_sync_client: Mock, album_id: int | None, expected_count: int
) -> None:
    """
    SyncJSONPlaceholderClient.get_photos()のalbum_idパラメータ検証

    検証項目：
    - album_id指定時に正しくエンドポイントが構築される（/albums/{album_id}/photos）
    - album_id=Noneで全件取得（/photos）
    - フィルタ結果が期待通りの件数である

    学習ポイント:
    - Photos API: アルバムごとの写真管理
    - エンドポイント分岐ロジック: パラメータ有無で異なるURL
    """
    # モックデータ（6件の写真、複数アルバム）
    all_photos = [
        {"id": 1, "albumId": 1, "title": "Photo 1", "url": "https://example.com/1.jpg"},
        {"id": 2, "albumId": 1, "title": "Photo 2", "url": "https://example.com/2.jpg"},
        {"id": 3, "albumId": 2, "title": "Photo 3", "url": "https://example.com/3.jpg"},
        {"id": 4, "albumId": 3, "title": "Photo 4", "url": "https://example.com/4.jpg"},
        {"id": 5, "albumId": 3, "title": "Photo 5", "url": "https://example.com/5.jpg"},
        {"id": 6, "albumId": 3, "title": "Photo 6", "url": "https://example.com/6.jpg"},
    ]

    # パラメータに応じてフィルタ
    if album_id:
        mock_data = [p for p in all_photos if p["albumId"] == album_id]
    else:
        mock_data = all_photos

    mock_response = create_mock_response(200, json_data=mock_data)
    mock_response.raise_for_status.return_value = None
    mock_httpx_sync_client.request.return_value = mock_response

    with SyncJSONPlaceholderClient() as client:
        client._client = mock_httpx_sync_client
        result = client.get_photos(album_id=album_id)

    assert len(result) == expected_count
    assert result == mock_data
