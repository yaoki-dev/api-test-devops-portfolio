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

import json
import sys

import httpx
import pytest
import respx

from tests.unit.helpers import mock_get_route
from utils.api_client import SyncAPIClient, SyncJSONPlaceholderClient

pytestmark = pytest.mark.unit

BASE_URL = "https://jsonplaceholder.typicode.com"


# =============================================================================
# Basic Operations (4件)
# =============================================================================


@respx.mock
def test_sync_get_user() -> None:
    """GETリクエスト検証"""
    respx.get(f"{BASE_URL}/users/1").respond(json={"id": 1, "name": "Test User"})

    with SyncAPIClient() as client:
        response = client.get("/users/1")

    assert response.status_code == 200
    assert response.json()["id"] == 1


@respx.mock
def test_sync_post_create_user() -> None:
    """POSTリクエスト検証"""
    respx.post(f"{BASE_URL}/users").respond(
        status_code=201,
        json={"id": 101, "name": "New User", "email": "new@example.com"},
    )

    with SyncAPIClient() as client:
        response = client.post("/users", json={"name": "New User", "email": "new@example.com"})

    assert response.status_code == 201
    assert response.json()["id"] == 101


@respx.mock
def test_sync_put_update_user() -> None:
    """PUTリクエスト検証"""
    respx.put(f"{BASE_URL}/users/1").respond(json={"id": 1, "name": "Updated"})

    with SyncAPIClient() as client:
        response = client.put("/users/1", json={"name": "Updated"})

    assert response.status_code == 200
    assert response.json()["name"] == "Updated"


@respx.mock
def test_sync_delete_user() -> None:
    """DELETEリクエスト検証（httpx.Response返却を検証）"""
    respx.delete(f"{BASE_URL}/users/1").respond(status_code=204, content=b"")

    with SyncAPIClient() as client:
        response = client.delete("/users/1")

    assert response.status_code == 204


# =============================================================================
# Edge Cases (4件)
# Note: 例外クラス階層テストは test_sync_client_error_handling.py に集約（SRP準拠）
# =============================================================================


def test_sync_context_manager_cleanup() -> None:
    """with文コンテキストマネージャーのクリーンアップ検証

    Note:
        SyncAPIClient.__exit__でself._client.close()が呼ばれることを検証。
        patch.objectでhttpx.Clientのcloseメソッドをスパイし、
        コンテキストマネージャー終了時に呼ばれることを確認する。
    """
    from unittest.mock import patch

    client_instance = SyncAPIClient()
    with patch.object(client_instance._client, "close") as mock_close:
        with client_instance:
            # コンテキスト内でクライアントが使用可能
            assert client_instance._client is not None

    # with文を抜けた後、SyncAPIClient.close()→httpx.Client.close()が呼ばれる
    mock_close.assert_called_once()


@respx.mock
def test_sync_empty_response_handling() -> None:
    """空レスポンス（{}）の安全処理検証"""
    respx.get(f"{BASE_URL}/empty").respond(json={})

    with SyncAPIClient() as client:
        response = client.get("/empty")

    assert response.json() == {}


@respx.mock
def test_sync_malformed_json_handling() -> None:
    """不正JSON時の例外処理検証"""
    respx.get(f"{BASE_URL}/malformed").respond(
        content=b"invalid json",
        headers={"content-type": "application/json"},
    )

    with SyncAPIClient() as client:
        response = client.get("/malformed")

    with pytest.raises(ValueError):
        response.json()


@pytest.mark.parametrize("user_id", [0, -1, sys.maxsize], ids=["zero", "negative", "max_int"])
@respx.mock
def test_sync_boundary_user_id(user_id: int) -> None:
    """境界値テスト: user_id=0, -1, MAX_INT（parametrize化）"""
    respx.get(f"{BASE_URL}/users/{user_id}").respond(json={"id": user_id})

    with SyncAPIClient() as client:
        response = client.get(f"/users/{user_id}")

    assert response.json()["id"] == user_id


# =============================================================================
# DevOps (1件)
# =============================================================================


@respx.mock
def test_sync_health_check_success() -> None:
    """
    API ヘルスチェック正常系テスト（同期版）

    検証項目：
    - health_check()メソッドの正常動作
    - 正常時: True返却

    学習ポイント:
    - Docker/Kubernetes readiness probe対応
    - 軽量クエリ（_limit=1）でサーバー負荷最小化
    """
    route = respx.get(f"{BASE_URL}/users", params={"_limit": 1}).respond(
        json=[{"id": 1, "name": "User 1"}]
    )

    with SyncJSONPlaceholderClient() as client:
        result = client.health_check()

    assert result is True
    assert route.call_count == 1


@respx.mock
def test_sync_health_check_connection_error() -> None:
    """
    API ヘルスチェック接続エラー時のテスト（同期版）

    検証項目：
    - 接続エラー時: False返却（graceful degradation）
    - httpx.ConnectError → APIConnectionErrorに変換 → health_checkでキャッチ

    学習ポイント:
    - respxのside_effectでhttpxネイティブ例外をシミュレート（patch不要）
    - サービス継続性: 例外時はFalse返却
    """
    route = respx.get(f"{BASE_URL}/users", params={"_limit": 1}).mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    with SyncJSONPlaceholderClient(retry_count=0) as client:
        result = client.health_check()

    assert result is False
    assert route.call_count == 1  # retry_count=0なのでリトライなし（1回のみ実行）


def test_sync_client_timeout_zero_not_overridden() -> None:
    """timeout=0.0がデフォルト設定値に上書きされないことを確認（r2850768833回帰テスト）

    httpxでは timeout=0.0 は即座にタイムアウト（TimeoutException発生）する設定値。
    falsyな値として `or` パターンで設定値に上書きされてはならない。

    学習ポイント:
    - is not None パターンの必要性: 0/0.0/False 等の有効なfalsy値を保護する
    - timeout=0.0 の用途: 即座にタイムアウトさせたい場合に使用（無効化には timeout=None）
    """
    client = SyncAPIClient(timeout=0.0)
    assert client.timeout == 0.0, (
        "timeout=0.0 はhttpxで有効な設定値（即座にタイムアウト）のため"
        "デフォルト設定値に上書きされてはならない"
    )


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
# 3. respxによるHTTPモック:
#    - @respx.mock: 同期テスト用デコレータ（@pytest.mark.asyncioは不要）
#    - respx.get/post/put/delete().respond(): レスポンス定義
#    - side_effect: 例外シミュレーション
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
@respx.mock
def test_sync_get_posts(limit: int | None, expected_count: int) -> None:
    """
    SyncJSONPlaceholderClient.get_posts()のlimitパラメータ検証

    検証項目：
    - limit指定時に正しくパラメータが送信される
    - limit=Noneで全件取得
    - limit=0で0件取得（API仕様では空配列返却、境界値検証）

    学習ポイント:
    - 同期APIクライアントのテストパターン
    - respxを使用した同期テスト
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

    # クエリパラメータ検証: limitが指定された場合はparams=でマッチ
    params = {"_limit": limit} if limit is not None else None
    route = mock_get_route(f"{BASE_URL}/posts", params, mock_data)

    with SyncJSONPlaceholderClient() as client:
        result = client.get_posts(limit=limit)

    assert len(result) == expected_count
    assert result == mock_data
    assert route.call_count == 1  # GETリクエストが1回のみ発行されたことを確認


@pytest.mark.unit
@pytest.mark.parametrize(
    "user_id,expected_count",
    [
        (None, 5),  # user_id=Noneで全投稿取得
        (1, 2),  # user_id=1でユーザー1の投稿のみ
        (2, 1),  # user_id=2でユーザー2の投稿のみ
        (999, 0),  # user_id=999で存在しないユーザー
    ],
    ids=["no_filter", "user_1", "user_2", "nonexistent_user"],
)
@respx.mock
def test_sync_get_posts_user_filter(user_id: int | None, expected_count: int) -> None:
    """
    SyncJSONPlaceholderClient.get_posts()のuser_idパラメータ検証

    検証項目：
    - user_id=None: フィルタなしで全投稿取得
    - user_id=1/2: 指定ユーザーの投稿のみ取得（API側フィルタ）
    - user_id=999: 存在しないユーザーで空配列返却

    学習ポイント:
    - API側フィルタリング: クライアント側フィルタリングと比較して90%転送削減
    - クエリパラメータ: /posts?userId=X
    - パフォーマンス最適化: ネットワーク転送量削減
    """
    all_posts = [
        {"id": 1, "userId": 1, "title": "Post 1", "body": "Content 1"},
        {"id": 2, "userId": 2, "title": "Post 2", "body": "Content 2"},
        {"id": 3, "userId": 1, "title": "Post 3", "body": "Content 3"},
        {"id": 4, "userId": 3, "title": "Post 4", "body": "Content 4"},
        {"id": 5, "userId": 3, "title": "Post 5", "body": "Content 5"},
    ]

    # user_idパラメータに応じてモックデータを設定
    if user_id is None:
        mock_data = all_posts
    elif user_id == 999:
        mock_data = []
    else:
        mock_data = [p for p in all_posts if p["userId"] == user_id]

    # クエリパラメータ検証: user_idが指定された場合はparams=でマッチ
    params = {"userId": user_id} if user_id is not None else None
    route = mock_get_route(f"{BASE_URL}/posts", params, mock_data)

    with SyncJSONPlaceholderClient() as client:
        result = client.get_posts(user_id=user_id)

    assert len(result) == expected_count
    assert result == mock_data
    assert route.call_count == 1  # GETリクエストが1回のみ発行されたことを確認
    if user_id is not None and user_id != 999:
        assert all(post["userId"] == user_id for post in result)


@pytest.mark.unit
@pytest.mark.parametrize(
    "limit,user_id,expected_error",
    [
        (-1, None, "limit must be >= 0"),
        (-100, None, "limit must be >= 0"),
        (None, 0, "user_id must be >= 1"),
        (None, -1, "user_id must be >= 1"),
        (-1, 0, "limit must be >= 0"),
    ],
    ids=[
        "negative_limit",
        "very_negative_limit",
        "zero_user_id",
        "negative_user_id",
        "both_invalid_limit_first",
    ],
)
def test_sync_get_posts_validation_error(
    limit: int | None, user_id: int | None, expected_error: str
) -> None:
    """
    SyncJSONPlaceholderClient.get_posts()の入力値バリデーション検証

    検証項目：
    - limit < 0: ValueError発生
    - user_id < 1: ValueError発生（JSONPlaceholder APIはID=1から）

    学習ポイント:
    - 早期エラー検出: API呼び出し前にクライアント側で検証
    - Fail-Fast原則: 無効な入力は即座に拒否
    """
    with SyncJSONPlaceholderClient() as client:
        with pytest.raises(ValueError, match=expected_error):
            client.get_posts(limit=limit, user_id=user_id)


@pytest.mark.unit
@respx.mock
def test_sync_get_post_success() -> None:
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

    respx.get(f"{BASE_URL}/posts/{post_id}").respond(json=expected_post)

    with SyncJSONPlaceholderClient() as client:
        result = client.get_post(post_id)

    assert result == expected_post
    assert result["id"] == post_id


@pytest.mark.unit
@respx.mock
def test_sync_create_post() -> None:
    """
    SyncJSONPlaceholderClient.create_post()の正常系テスト

    検証項目：
    - title/body/user_id指定で投稿作成
    - リクエストボディの正確性（title, body, userId）
    - レスポンスにidが付与される（サーバー生成）

    学習ポイント:
    - RESTful POST: リソース作成操作
    - respx route.calls でリクエストボディを直接検証するパターン
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

    route = respx.post(f"{BASE_URL}/posts").respond(status_code=201, json=expected_response)

    with SyncJSONPlaceholderClient() as client:
        result = client.create_post(title=title, body=body, user_id=user_id)

    # リクエストボディ検証: create_post()が正しいフィールドを送信しているか確認
    assert route.call_count == 1
    request_body = json.loads(route.calls[0].request.content)
    assert request_body["title"] == title
    assert request_body["body"] == body
    assert request_body["userId"] == user_id

    # レスポンス検証
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
@respx.mock
def test_sync_get_todos(
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
    if user_id is not None:
        filtered_todos = [t for t in filtered_todos if t["userId"] == user_id]
    if completed is not None:
        filtered_todos = [t for t in filtered_todos if t["completed"] == completed]
    if limit is not None:
        filtered_todos = filtered_todos[:limit]

    # クエリパラメータ検証: 指定されたパラメータのみparams=でマッチ
    # dict comprehensionでNoneを除外（completed=Falseは有効なパラメータとして保持）
    params = {
        k: v
        for k, v in {"userId": user_id, "completed": completed, "_limit": limit}.items()
        if v is not None
    } or None
    route = mock_get_route(f"{BASE_URL}/todos", params, filtered_todos)

    with SyncJSONPlaceholderClient() as client:
        result = client.get_todos(user_id=user_id, completed=completed, limit=limit)

    assert len(result) == expected_count
    assert result == filtered_todos
    assert route.call_count == 1  # GETリクエストが1回のみ発行されたことを確認

    # completed パラメータのエンコード検証
    # httpxはFalseを"false"、Trueを"true"にエンコードする（小文字）
    if completed is not None:
        assert route.calls[0].request.url.params.get("completed") == str(completed).lower(), (
            f"completed={completed} はhttpxにより '{str(completed).lower()}' にエンコードされるべき"
        )


# =============================================================================
# Issue #173: get_todos() 入力値バリデーション
# =============================================================================


@pytest.mark.unit
@pytest.mark.parametrize(
    "limit,user_id,expected_error",
    [
        (-1, None, "limit must be >= 0"),
        (-100, None, "limit must be >= 0"),
        (None, 0, "user_id must be >= 1"),
        (None, -1, "user_id must be >= 1"),
        (-1, 0, "limit must be >= 0"),
    ],
    ids=[
        "negative_limit",
        "very_negative_limit",
        "zero_user_id",
        "negative_user_id",
        "both_invalid_limit_first",
    ],
)
def test_sync_get_todos_validation_error(
    limit: int | None, user_id: int | None, expected_error: str
) -> None:
    """
    SyncJSONPlaceholderClient.get_todos()の入力値バリデーション検証

    検証項目：
    - limit < 0: ValueError発生
    - user_id < 1: ValueError発生（JSONPlaceholder APIはID=1から）

    学習ポイント:
    - Fail-Fast原則: 無効な入力は即座に拒否
    - get_posts()と同一パターンのバリデーション一貫性
    """
    with SyncJSONPlaceholderClient() as client:
        with pytest.raises(ValueError, match=expected_error):
            client.get_todos(limit=limit, user_id=user_id)


# =============================================================================
# Issue #173: Albums API テスト追加（カバレッジ85%達成）
# =============================================================================


@pytest.mark.unit
@pytest.mark.parametrize(
    "user_id,expected_count",
    [(1, 2), (None, 5), (2, 1)],
    ids=["user_id_1", "no_user_id", "user_id_2"],
)
@respx.mock
def test_sync_get_albums(user_id: int | None, expected_count: int) -> None:
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
    if user_id is not None:
        mock_data = [a for a in all_albums if a["userId"] == user_id]
    else:
        mock_data = all_albums

    # クエリパラメータ検証: user_idが指定された場合はparams=でマッチ
    params = {"userId": user_id} if user_id is not None else None
    route = mock_get_route(f"{BASE_URL}/albums", params, mock_data)

    with SyncJSONPlaceholderClient() as client:
        result = client.get_albums(user_id=user_id)

    assert len(result) == expected_count
    assert result == mock_data
    assert route.call_count == 1  # GETリクエストが1回のみ発行されたことを確認


# =============================================================================
# Issue #173: get_albums() 入力値バリデーション
# =============================================================================


@pytest.mark.unit
@pytest.mark.parametrize(
    "user_id,expected_error",
    [
        (0, "user_id must be >= 1"),
        (-1, "user_id must be >= 1"),
    ],
    ids=["zero_user_id", "negative_user_id"],
)
def test_sync_get_albums_validation_error(user_id: int, expected_error: str) -> None:
    """
    SyncJSONPlaceholderClient.get_albums()の入力値バリデーション検証

    検証項目：
    - user_id < 1: ValueError発生（JSONPlaceholder APIはID=1から）

    学習ポイント:
    - Fail-Fast原則: 無効な入力は即座に拒否
    - get_posts()と同一パターンのバリデーション一貫性
    """
    with SyncJSONPlaceholderClient() as client:
        with pytest.raises(ValueError, match=expected_error):
            client.get_albums(user_id=user_id)


# =============================================================================
# Photos API テスト追加
# =============================================================================


@pytest.mark.unit
@pytest.mark.parametrize(
    "album_id,expected_count",
    [(1, 2), (None, 6), (2, 1)],
    ids=["album_id_1", "no_album_id", "album_id_2"],
)
@respx.mock
def test_sync_get_photos(album_id: int | None, expected_count: int) -> None:
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

    # パラメータに応じてフィルタとエンドポイントを設定
    if album_id is not None:
        mock_data = [p for p in all_photos if p["albumId"] == album_id]
        route = respx.get(f"{BASE_URL}/albums/{album_id}/photos").respond(json=mock_data)
    else:
        mock_data = all_photos
        route = respx.get(f"{BASE_URL}/photos").respond(json=mock_data)

    with SyncJSONPlaceholderClient() as client:
        result = client.get_photos(album_id=album_id)

    assert len(result) == expected_count
    assert result == mock_data
    assert route.call_count == 1


# =============================================================================
# get_comments / get_photos 入力バリデーションテスト
# =============================================================================


@pytest.mark.unit
@pytest.mark.parametrize(
    "post_id",
    [0, -1, -100],
    ids=["post_id_zero", "post_id_negative", "post_id_large_negative"],
)
def test_sync_get_comments_invalid_post_id(post_id: int, respx_mock: respx.MockRouter) -> None:
    """
    SyncJSONPlaceholderClient.get_comments()の無効post_idバリデーション

    検証項目：
    - post_id=0 は ValueError を発生させる（JSONPlaceholder API は1-based ID）
    - 負数のpost_idも同様に ValueError を発生させる
    - HTTP リクエストは発行されない

    学習ポイント:
    - 境界値テスト: 0 は偽値（falsy）であるため `if post_id:` では検出できないバグ
    - `if post_id is not None and post_id < 1:` による正確な検証パターン
    """
    with SyncJSONPlaceholderClient() as client:
        with pytest.raises(ValueError, match="post_id must be >= 1"):
            client.get_comments(post_id=post_id)

    # HTTPリクエストが発行されていないことを確認（スコープ付きルーター使用）
    assert len(respx_mock.calls) == 0


@pytest.mark.unit
@pytest.mark.parametrize(
    "album_id",
    [0, -1, -100],
    ids=["album_id_zero", "album_id_negative", "album_id_large_negative"],
)
def test_sync_get_photos_invalid_album_id(album_id: int, respx_mock: respx.MockRouter) -> None:
    """
    SyncJSONPlaceholderClient.get_photos()の無効album_idバリデーション

    検証項目：
    - album_id=0 は ValueError を発生させる（JSONPlaceholder API は1-based ID）
    - 負数のalbum_idも同様に ValueError を発生させる
    - HTTP リクエストは発行されない

    学習ポイント:
    - album_id=0 を渡すと API は空配列を返すが、正しいエラーではない（サイレント失敗）
    - 明示的な ValueError により呼び出し側でバグを早期発見できる
    """
    with SyncJSONPlaceholderClient() as client:
        with pytest.raises(ValueError, match="album_id must be >= 1"):
            client.get_photos(album_id=album_id)

    # HTTPリクエストが発行されていないことを確認（スコープ付きルーター使用）
    assert len(respx_mock.calls) == 0


# =============================================================================
# SyncAPIClient基底クラス: HTTP PATCHメソッド
# =============================================================================


@pytest.mark.unit
@respx.mock
def test_sync_patch_method() -> None:
    """SyncAPIClient.patch() HTTP PATCHメソッドの動作確認

    検証項目:
    - PATCHリクエストが正しく送信される
    - HTTPメソッドが "PATCH" である
    - リクエストボディが正確に送信される

    学習ポイント:
    - HTTP PATCH: リソースの部分更新操作
    - PUT vs PATCH: PUTは全体更新、PATCHは部分更新
    """
    endpoint = "/todos/1"
    patch_data = {"completed": True}
    full_response = {"id": 1, "title": "Test Todo", "completed": True, "userId": 1}

    # PATCHレスポンスをモック化
    route = respx.patch(f"{BASE_URL}{endpoint}").respond(status_code=200, json=full_response)

    with SyncJSONPlaceholderClient() as client:
        result = client.update_todo(1, completed=True)

    # レスポンス検証
    assert result == full_response
    assert result["completed"] is True

    # リクエスト検証
    assert route.call_count == 1
    assert route.calls[0].request.method == "PATCH"

    # リクエストボディ検証
    import json as json_module

    request_body = json_module.loads(route.calls[0].request.content)
    assert request_body == patch_data


# =============================================================================
# SyncJSONPlaceholderClient: 未テストメソッド
# =============================================================================


@pytest.mark.unit
@respx.mock
def test_sync_get_users() -> None:
    """SyncJSONPlaceholderClient.get_users() ユーザー一覧取得の動作確認

    検証項目:
    - GET /users リクエストが送信される
    - ユーザーリストが正しく返される
    - call_count で1回のリクエストを確認

    学習ポイント:
    - respx: パラメータなしのGETリクエストモック
    """
    mock_users = [
        {"id": 1, "name": "Leanne Graham", "email": "sincere@april.biz"},
        {"id": 2, "name": "Ervin Howell", "email": "shanna@melissa.tv"},
    ]

    route = respx.get(f"{BASE_URL}/users").respond(json=mock_users)

    with SyncJSONPlaceholderClient() as client:
        result = client.get_users()

    assert len(result) == 2
    assert result[0]["name"] == "Leanne Graham"
    assert result[1]["id"] == 2
    assert route.call_count == 1


@pytest.mark.unit
@respx.mock
def test_sync_get_todo() -> None:
    """SyncJSONPlaceholderClient.get_todo() 特定TODO取得の動作確認

    検証項目:
    - GET /todos/{id} リクエストが送信される
    - 正しいTODOデータが返される

    学習ポイント:
    - respx: パスパラメータを含むURLのモック
    """
    mock_todo = {"id": 1, "userId": 1, "title": "delectus aut autem", "completed": False}

    route = respx.get(f"{BASE_URL}/todos/1").respond(json=mock_todo)

    with SyncJSONPlaceholderClient() as client:
        result = client.get_todo(1)

    assert result["id"] == 1
    assert result["title"] == "delectus aut autem"
    assert result["completed"] is False
    assert route.call_count == 1


@pytest.mark.unit
@respx.mock
def test_sync_create_todo() -> None:
    """SyncJSONPlaceholderClient.create_todo() 新規TODO作成の動作確認

    検証項目:
    - POST /todos リクエストが送信される
    - リクエストボディに title/userId/completed が含まれる
    - 201 Created レスポンスが正しく処理される

    学習ポイント:
    - respx: POSTリクエストのボディ検証
    - respx: route.calls[0].request.content でボディ確認
    """
    import json as json_module

    new_todo_response = {
        "id": 201,
        "title": "Buy groceries",
        "userId": 1,
        "completed": False,
    }

    route = respx.post(f"{BASE_URL}/todos").respond(status_code=201, json=new_todo_response)

    with SyncJSONPlaceholderClient() as client:
        result = client.create_todo(title="Buy groceries", user_id=1, completed=False)

    # レスポンス検証
    assert result["id"] == 201
    assert result["title"] == "Buy groceries"
    assert route.call_count == 1

    # リクエストボディ検証: title/userId/completedが正しく送信されたか
    request_body = json_module.loads(route.calls[0].request.content)
    assert request_body["title"] == "Buy groceries"
    assert request_body["userId"] == 1
    assert request_body["completed"] is False
