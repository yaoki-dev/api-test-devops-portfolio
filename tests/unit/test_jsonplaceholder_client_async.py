"""Async JSONPlaceholder client tests for utils.jsonplaceholder_client_async."""

import asyncio
import json
from typing import Any, TypedDict
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
import respx
from httpx import Response
from structlog.testing import capture_logs

from models.responses import Album, Photo, Post, Todo, User
from tests.constants import BASE_URL
from tests.unit.helpers import assert_warning_log_count, make_canonical_user
from utils.exceptions import (
    APIHTTPError,
    APIRetryError,
)
from utils.jsonplaceholder_client_async import (
    MAX_LOGGED_FAILURE_DETAILS,
    AsyncJSONPlaceholderClient,
)

pytestmark = pytest.mark.unit


class PostData(TypedDict):
    """投稿データの型定義（Dict構造を明確化）"""

    id: int
    title: str
    body: str
    userId: int


@pytest.fixture
def sample_post_data() -> PostData:
    """テスト用投稿データ"""
    return {
        "id": 101,
        "title": "Test Title",
        "body": "Test Body",
        "userId": 1,
    }


@pytest.fixture
def sample_user_data():
    """テスト用ユーザーデータ"""
    return {
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
        "website": "https://hildegard.org",
        "company": {
            "name": "Romaguera-Crona",
            "catchPhrase": "Multi-layered client-server neural-net",
            "bs": "harness real-time e-markets",
        },
    }


@pytest.fixture
def sample_users_list():
    """テスト用ユーザーリスト"""
    return [
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
            "website": "https://hildegard.org",
            "company": {
                "name": "Romaguera-Crona",
                "catchPhrase": "Multi-layered client-server neural-net",
                "bs": "harness real-time e-markets",
            },
        },
        {
            "id": 2,
            "name": "Ervin Howell",
            "username": "Antonette",
            "email": "Shanna@melissa.tv",
            "address": {
                "street": "Victor Plains",
                "suite": "Suite 879",
                "city": "Wisokyburgh",
                "zipcode": "90566-7771",
                "geo": {"lat": "-43.9509", "lng": "-34.4618"},
            },
            "phone": "010-692-6593 x09125",
            "website": "https://anastasia.net",
            "company": {
                "name": "Deckow-Crist",
                "catchPhrase": "Proactive didactic contingency",
                "bs": "synergize scalable supply-chains",
            },
        },
        {
            "id": 3,
            "name": "Clementine Bauch",
            "username": "Samantha",
            "email": "Nathan@yesenia.net",
            "address": {
                "street": "Douglas Extension",
                "suite": "Suite 847",
                "city": "McKenziehaven",
                "zipcode": "59590-4157",
                "geo": {"lat": "-68.6102", "lng": "-47.0653"},
            },
            "phone": "1-463-123-4447",
            "website": "https://ramiro.info",
            "company": {
                "name": "Romaguera-Jacobson",
                "catchPhrase": "Face to face bifurcated interface",
                "bs": "e-enable strategic applications",
            },
        },
    ]


@respx.mock
async def test_async_create_post(sample_post_data: PostData) -> None:
    """
    非同期投稿作成（POST /posts）のテスト

    検証項目：
    - async with コンテキストマネージャーの動作
    - create_post() メソッドの正常実行
    - リクエストボディの正確性（title, body, userId）
    - レスポンスJSONの正常パーシング
    """
    route = respx.post(f"{BASE_URL}/posts").respond(
        status_code=201,
        json=dict(sample_post_data),
    )

    async with AsyncJSONPlaceholderClient() as client:
        post = await client.create_post("Test Title", "Test Body", 1)

    # リクエストボディ検証: create_post()が正しいフィールドを送信しているか確認
    assert route.call_count == 1
    request_body = json.loads(route.calls[0].request.content)
    assert request_body["title"] == "Test Title"
    assert request_body["body"] == "Test Body"
    assert request_body["userId"] == 1

    # レスポンス検証
    assert post.title == "Test Title"
    assert post.body == "Test Body"
    assert post.user_id == 1
    assert post.id == 101


@respx.mock
async def test_async_update_post() -> None:
    """
    非同期投稿更新（PUT /posts/{id}）のテスト

    検証項目：
    - update_post() メソッドの正常実行
    - post_id パラメータの正確性
    - リクエストボディの更新データ（title, body）
    - レスポンスに更新データが反映されているか確認
    """
    updated_data = {
        "id": 1,
        "title": "Updated Title",
        "body": "Updated Body",
        "userId": 1,
    }
    route = respx.put(f"{BASE_URL}/posts/1").respond(
        status_code=200,
        json=updated_data,
    )

    async with AsyncJSONPlaceholderClient() as client:
        post = await client.update_post(1, "Updated Title", "Updated Body")

    # リクエストボディ検証: update_post()が正しいフィールドを送信しているか確認
    # update_post は title と body のみ送信（create_post の userId とは異なり含まない）
    assert route.call_count == 1
    request_body = json.loads(route.calls[0].request.content)
    assert request_body["title"] == "Updated Title"
    assert request_body["body"] == "Updated Body"
    assert "userId" not in request_body  # PUT は部分更新: userId は送信しない

    # レスポンス検証
    assert post["id"] == 1
    assert post["title"] == "Updated Title"
    assert post["body"] == "Updated Body"


@respx.mock
async def test_async_delete_post() -> None:
    """
    非同期投稿削除（DELETE /posts/{id}）のテスト

    検証項目：
    - delete_post() メソッドの正常実行
    - post_id パラメータの正確性
    - 例外が発生しないことの確認
    - 200 ステータスの処理
    """
    route = respx.delete(f"{BASE_URL}/posts/1").respond(status_code=200)

    async with AsyncJSONPlaceholderClient() as client:
        # delete_post() は None を返す: 型宣言はランタイム動作を保証しないため
        # 実際の戻り値を明示的に検証する（204 No Content → None 変換の保証）
        result = await client.delete_post(1)  # type: ignore[func-returns-value]

    assert route.call_count == 1  # DELETEリクエストが1回発行されたことを確認
    assert result is None


@respx.mock
async def test_async_crud_integration(sample_post_data: PostData) -> None:
    """
    CRUD操作の統合フローテスト（respxモック使用）

    検証項目：
    - Create → Read → Update → Delete の一連フロー
    - 各操作の正常実行と適切なレスポンス処理
    - post_id の一貫性（Create で生成 → 以降の操作で使用）
    - 各HTTPメソッドの正確な呼び出し
    """
    # Create: 新規投稿作成（POST /posts）
    post_route = respx.post(f"{BASE_URL}/posts").respond(
        status_code=201,
        json=dict(sample_post_data),
    )

    # Read: 投稿一覧取得（GET /posts）
    get_route = respx.get(f"{BASE_URL}/posts").respond(
        status_code=200,
        json=[dict(sample_post_data)],
    )

    # Update: 投稿更新（PUT /posts/101）
    updated_data = {
        "id": 101,
        "title": "Updated",
        "body": "Updated Body",
        "userId": 1,
    }
    put_route = respx.put(f"{BASE_URL}/posts/101").respond(
        status_code=200,
        json=updated_data,
    )

    # Delete: 投稿削除（DELETE /posts/101）
    delete_route = respx.delete(f"{BASE_URL}/posts/101").respond(status_code=200)

    async with AsyncJSONPlaceholderClient() as client:
        # Create: 新規投稿作成
        post = await client.create_post("Test Title", "Test Body", 1)
        post_id = post.id
        assert post_id == 101
        assert post.title == "Test Title"

        # Read: 投稿一覧取得（user_id=1）
        retrieved_posts = await client.get_posts(limit=None)
        assert len(retrieved_posts) > 0
        assert retrieved_posts[0].id == post_id

        # Update: 投稿更新
        updated = await client.update_post(post_id, "Updated", "Updated Body")
        assert updated["id"] == post_id
        assert updated["title"] == "Updated"

        # Delete: 投稿削除（型ヒントだけでなく実際の戻り値も検証）
        delete_result = await client.delete_post(post_id)  # type: ignore[func-returns-value]
        assert delete_result is None

    # 各HTTPメソッドが1回ずつ発行されたことをトランスポート層で確認
    assert post_route.call_count == 1
    assert get_route.call_count == 1
    assert put_route.call_count == 1
    assert delete_route.call_count == 1


@respx.mock
async def test_async_create_post_400_error() -> None:
    """
    400 Bad Request エラー時の挙動テスト

    検証項目：
    - 不正なリクエストボディ送信時の400エラー
    - APIHTTPError 例外の発生（status_code=400）
    - エラーレスポンスの適切な処理
    - リトライが実行されないこと（4xxはクライアントエラー）
    """
    route = respx.post(f"{BASE_URL}/posts").respond(
        status_code=400,
        json={"error": "Invalid request body"},
    )

    async with AsyncJSONPlaceholderClient() as client:
        # 400エラーが発生することを確認
        with pytest.raises(APIHTTPError) as exc_info:
            await client.create_post("", "", 0)  # 不正なデータ
        assert exc_info.value.status_code == 400

    assert route.call_count == 1  # 4xxはリトライなし


@respx.mock
async def test_async_update_post_404_error() -> None:
    """
    404 Not Found エラー時の挙動テスト

    検証項目：
    - 存在しない post_id への更新リクエスト
    - 404エラーの適切な検出
    - APIHTTPError 例外の発生（status_code=404）
    - リトライが実行されないこと
    """
    route = respx.put(f"{BASE_URL}/posts/99999").respond(
        status_code=404,
        json={"error": "Post not found"},
    )

    async with AsyncJSONPlaceholderClient() as client:
        # 404エラーが発生することを確認
        with pytest.raises(APIHTTPError) as exc_info:
            await client.update_post(99999, "Title", "Body")  # 存在しないID
        assert exc_info.value.status_code == 404

    assert route.call_count == 1  # 4xxはリトライなし


@respx.mock
@patch("utils.jsonplaceholder_base_async.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_delete_post_500_error(mock_backoff: Mock) -> None:
    """
    500 Internal Server Error 時の挙動テスト

    検証項目：
    - サーバーエラー時の500エラー
    - APIRetryError 例外の発生（リトライ上限到達）
    - リトライロジックの動作（5xxはサーバーエラー → リトライ対象）
    - リトライ回数の正確性（デフォルトretry_count=3 → 計4回）
    - エラーレスポンスの適切な処理
    """
    route = respx.delete(f"{BASE_URL}/posts/1").respond(
        status_code=500,
        json={"error": "Internal server error"},
    )

    async with AsyncJSONPlaceholderClient() as client:
        # 500エラーが発生することを確認（5xxはリトライ上限後にAPIRetryError）
        with pytest.raises(APIRetryError):
            await client.delete_post(1)

    # リトライ回数検証: 初回 + リトライ3回 = 計4回（デフォルトretry_count=3）
    assert route.call_count == 4


@respx.mock
async def test_async_get_user(sample_user_data):
    """
    非同期APIクライアントの基本的なGETリクエストをテスト

    検証項目：
    - async with コンテキストマネージャーの動作
    - HTTPXクライアントのリクエスト実行
    - JSONレスポンスの正常パーシング
    - ログ出力の確認
    """
    # respxでエンドポイントをモック化（ルート固有のcall_countで検証）
    route = respx.get(f"{BASE_URL}/users/1").respond(json=sample_user_data)

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        result = await client.get_user(1)

        # 結果検証
        assert result.model_dump(by_alias=True) == sample_user_data
        assert result.id == 1
        assert result.name == "Leanne Graham"
        assert result.email == "Sincere@april.biz"

    # リクエストが1回発行されたことを確認（ルート固有）
    assert route.call_count == 1


@respx.mock
async def test_async_concurrent_requests(sample_users_list):
    """
    複数の非同期リクエストを並行実行するテスト

    検証項目：
    - asyncio.gather による並行実行（3並行リクエスト）
    - 各ユーザーデータの正確な取得（ID=1,2,3の確認）
    - 各ルートが1回ずつ呼ばれることの確認（route.call_count）
    """
    # 各ユーザーエンドポイントをrespxでモック化（ルート固有のcall_countで検証）
    route_user1 = respx.get(f"{BASE_URL}/users/1").respond(json=sample_users_list[0])
    route_user2 = respx.get(f"{BASE_URL}/users/2").respond(json=sample_users_list[1])
    route_user3 = respx.get(f"{BASE_URL}/users/3").respond(json=sample_users_list[2])

    # 並行実行テスト
    async with AsyncJSONPlaceholderClient() as client:
        # 3つのリクエストを並行実行
        user_ids = [1, 2, 3]
        tasks = [client.get_user(user_id) for user_id in user_ids]
        results = await asyncio.gather(*tasks)

        # 結果検証
        assert len(results) == 3
        assert all(isinstance(result, User) for result in results)
        assert results[0].id == 1
        assert results[1].id == 2
        assert results[2].id == 3

    # 各ルートが1回ずつ呼ばれたことを確認（ルート固有）
    assert route_user1.call_count == 1
    assert route_user2.call_count == 1
    assert route_user3.call_count == 1


@respx.mock
async def test_async_multiple_users_with_semaphore():
    """
    Semaphoreを使用した複数ユーザー並行取得のテスト

    検証項目：
    - get_multiple_users()が全件（5件）を正常返却すること
    - 各ユーザーエンドポイントが1回ずつ呼ばれること（重複リクエストなし）
    - max_concurrent パラメータを受け付けること

    注意（テスト設計上の制限）:
    - このテストはスパイパターンを使用しないため、respxモック環境では
      HTTPリクエストのタイミング情報が記録されず、「max_concurrent=2の
      同時実行数制限が機能している」ことは観測不可能
      （実装上はSemaphoreが機能しているが、このテストでは検証できない）
      → Semaphoreの動作検証は test_semaphore_initialized_with_correct_max_concurrent を参照
    """
    # 各ユーザーエンドポイントをrespxでモック化（ルート固有のcall_countで検証）
    routes = {}
    for i in [1, 2, 3, 4, 5]:
        routes[i] = respx.get(f"{BASE_URL}/users/{i}").respond(json=make_canonical_user(i))

    async with AsyncJSONPlaceholderClient() as client:
        # max_concurrent=2でSemaphore制御
        results = await client.get_multiple_users([1, 2, 3, 4, 5], max_concurrent=2)

        # 結果検証
        assert len(results) == 5
        assert all(isinstance(result, User) for result in results)
        assert results[0].id == 1
        assert results[4].id == 5

    # 全ユーザー取得成功確認（各ルート1回ずつ、計5回のHTTPリクエスト）
    assert all(r.call_count == 1 for r in routes.values())


@respx.mock
async def test_semaphore_initialized_with_correct_max_concurrent():
    """Semaphoreがmax_concurrent=2の同時実行数制限を実際に機能させることを検証するテスト

    検証項目：
    - get_multiple_users()が同時に実行するタスク数がmax_concurrent=2以下に抑えられること
    - asyncio.sleep(0)でevent loopにyieldし、並行実行を観測可能にする
    """
    max_concurrent_observed = 0
    current_concurrent = 0

    original_get_user = AsyncJSONPlaceholderClient.get_user

    async def spy_get_user(self: AsyncJSONPlaceholderClient, user_id: int) -> User:
        nonlocal max_concurrent_observed, current_concurrent
        current_concurrent += 1
        max_concurrent_observed = max(max_concurrent_observed, current_concurrent)
        # event loopにyieldして他タスクの並行実行を許容する（実際の遅延なし）
        await asyncio.sleep(0)
        try:
            result = await original_get_user(self, user_id)
        finally:
            current_concurrent -= 1
        return result

    # respxルート設定（5ユーザー分）
    for i in [1, 2, 3, 4, 5]:
        respx.get(f"{BASE_URL}/users/{i}").respond(json={"id": i, "name": f"User {i}"})

    with patch.object(AsyncJSONPlaceholderClient, "get_user", spy_get_user):
        async with AsyncJSONPlaceholderClient() as client:
            await client.get_multiple_users([1, 2, 3, 4, 5], max_concurrent=2)

    assert max_concurrent_observed == 2, (
        f"同時実行数2を期待 (max_concurrent=2, 実際: {max_concurrent_observed})"
    )


@respx.mock
async def test_partial_failure_graceful_degradation():
    """
    一部リクエスト失敗時のgraceful degradationテスト

    検証項目：
    - 5件中2件が失敗するシナリオ
    - 成功したリクエストは正常に取得できる
    - システム全体はクラッシュせず継続動作
    """

    # 宣言的なエンドポイントマッピング（成功: 1,3,5 / 失敗: 2,4）
    route1 = respx.get(f"{BASE_URL}/users/1").respond(json=make_canonical_user(1))
    route2 = respx.get(f"{BASE_URL}/users/2").respond(status_code=500)
    route3 = respx.get(f"{BASE_URL}/users/3").respond(json=make_canonical_user(3))
    route4 = respx.get(f"{BASE_URL}/users/4").respond(status_code=500)
    route5 = respx.get(f"{BASE_URL}/users/5").respond(json=make_canonical_user(5))

    # retry_count=0: リトライなし設定でgraceful degradationのみ検証（リトライ挙動は別テストで担保）
    with capture_logs() as log_output:
        async with AsyncJSONPlaceholderClient(retry_count=0) as client:
            results = await client.get_multiple_users([1, 2, 3, 4, 5], max_concurrent=2)

    # graceful degradation検証（成功分のみ返却パターン）
    assert len(results) == 3, f"Expected 3 successful results, got {len(results)}"
    assert all(isinstance(r, User) for r in results)

    # Expected IDs [1,3,5] in any order, no duplicates
    result_ids = [r.id for r in results]
    assert sorted(result_ids) == [1, 3, 5], f"Expected IDs [1,3,5], got {result_ids}"

    # 全5エンドポイントが各1回ずつ呼ばれたことを確認（retry_count=0のため決定論的に==1）
    assert route1.call_count == 1
    assert route2.call_count == 1
    assert route3.call_count == 1
    assert route4.call_count == 1
    assert route5.call_count == 1

    # 2件失敗（user_id=2,4）の警告ログ検証（Sentry監視の保証）
    assert_warning_log_count(log_output, "get_user_failed", 2)

    # セキュリティ: get_user_failed ログの構造検証（APIClientErrorメッセージはサニタイズ済み）
    for log in log_output:
        if log.get("event") == "get_user_failed":
            assert "error" not in log  # _classify_error と同方針で省略
            assert "error_type" in log


@respx.mock
async def test_all_requests_fail_returns_empty_list():
    """
    全リクエスト失敗時の空リスト返却テスト

    検証項目：
    - 全件が500エラーの場合、空リスト[]が返却される
    - システム全体がクラッシュせず正常終了
    - graceful degradationの最悪ケース保証
    """
    # DRY: リスト内包表記で一括設定（全件500エラー）
    routes = [respx.get(f"{BASE_URL}/users/{uid}").respond(status_code=500) for uid in [1, 2, 3]]

    # retry_count=0: リトライなし設定でgraceful degradationのみ検証（リトライ挙動は別テストで担保）
    with capture_logs() as log_output:
        async with AsyncJSONPlaceholderClient(retry_count=0) as client:
            results = await client.get_multiple_users([1, 2, 3], max_concurrent=2)

    # 全件失敗で空リスト返却
    assert results == [], f"Expected empty list, got {results}"
    assert isinstance(results, list), f"Expected list type, got {type(results)}"

    # 全3エンドポイントが各1回ずつ呼ばれたことを確認（retry_count=0のため決定論的に==1）
    assert all(r.call_count == 1 for r in routes)

    # 各ユーザー取得失敗時に警告ログが出力されることを確認（Sentry監視の保証）
    assert_warning_log_count(log_output, "get_user_failed", 3)

    # セキュリティ: get_user_failed ログの構造検証
    for log in log_output:
        if log.get("event") == "get_user_failed":
            assert "error" not in log  # _classify_error と同方針で省略
            assert "error_type" in log


@respx.mock
async def test_async_post_create_user():
    """
    非同期POST リクエスト・データ送信のテスト

    検証項目：
    - JSON データの送信
    - レスポンスの適切な処理
    - 作成されたリソースの確認
    """
    # 作成成功レスポンスをrespxでモック化（ルート固有のcall_countで検証）
    created_user = {
        "id": 101,
        "name": "New Async User",
        "email": "async@example.com",
        "phone": "123-456-7890",
    }
    route = respx.post(f"{BASE_URL}/users").respond(status_code=201, json=created_user)

    async with AsyncJSONPlaceholderClient() as client:
        # ユーザー作成データ
        user_data = {
            "name": "New Async User",
            "email": "async@example.com",
            "phone": "123-456-7890",
        }

        result = await client.create_user(user_data)

        # 結果検証
        assert result["id"] == 101
        assert result["name"] == "New Async User"
        assert result["email"] == "async@example.com"

    # POSTリクエストが1回発行されたことを確認（ルート固有）
    assert route.call_count == 1
    assert route.calls[0].request.method == "POST"

    # リクエストボディの内容を検証（フィールド名変更の退行検出）
    request_body = json.loads(route.calls[0].request.content)
    assert request_body["name"] == "New Async User"
    assert request_body["email"] == "async@example.com"
    assert request_body["phone"] == "123-456-7890"


@respx.mock
async def test_async_bulk_create_users():
    """
    複数ユーザーの並行作成テスト

    検証項目：
    - bulk_create_users メソッドの動作
    - 複数POST リクエストの並行実行（asyncio.gather使用）
    - 成功したユーザーのみ返却される動作確認

    注意: bulk_create_users は asyncio.gather で並行POST → 同一URLに複数POST。
    respx は同一ルートへの複数リクエストに対して同じレスポンスを繰り返し返す。
    レスポンスを区別するため side_effect パターンを使用。
    """
    # 複数ユーザーのテストデータ
    users_to_create = [
        {"name": "User 1", "email": "user1@test.com"},
        {"name": "User 2", "email": "user2@test.com"},
        {"name": "User 3", "email": "user3@test.com"},
    ]

    # 各リクエストで異なるレスポンスを返すためside_effectを使用
    post_route = respx.post(f"{BASE_URL}/users")
    post_route.side_effect = [
        Response(201, json={"id": 101, "name": "User 1", "email": "user1@test.com"}),
        Response(201, json={"id": 102, "name": "User 2", "email": "user2@test.com"}),
        Response(201, json={"id": 103, "name": "User 3", "email": "user3@test.com"}),
    ]

    async with AsyncJSONPlaceholderClient() as client:
        results = await client.bulk_create_users(users_to_create)

    # 結果検証
    assert len(results) == 3
    assert all(result["id"] > 100 for result in results)

    # 並行実行確認（3回のPOSTリクエスト、ルート固有）
    assert post_route.call_count == 3

    # 作成されたユーザー確認（防御的テスト）

    # respxのside_effectリストは同一ルートへの呼び出し順に
    # 消費される（決定的）。
    # asyncio.gatherの結果も入力タスク順に返却されるため順序は決定的だが、
    # インデックス位置ではなく名称の存在確認に絞ることで、将来の実装変更への耐性を高める。
    # → set/in検証: 期待される全名称が含まれることを確認

    created_names = [result["name"] for result in results]
    assert "User 1" in created_names
    assert "User 2" in created_names
    assert "User 3" in created_names


@respx.mock
async def test_async_bulk_create_users_partial_failure_4xx_returns_only_successful():
    """
    4xx部分失敗時の返却値テスト（silent partial failure + 成功分のみ返却）

    検証項目：
    - 一部リクエストが4xxエラーで失敗してもbulk_create_usersは例外を発生させない
    - 成功したユーザーのみが返却される（失敗分は除外）
    - 全リクエストが試行される（部分失敗でも中断しない）

    設計根拠：
    bulk_create_usersはasyncio.gather(return_exceptions=True)で部分失敗を吸収する。
    4xxエラー（422）は即失敗（リトライなし）のため、APIHTTPErrorが
    return_exceptionsにより捕捉され、成功分のみが返却される。

    Note: side_effectリストはリクエスト到着順に消費される。
    respxモック環境（実I/O待機なし）ではtask作成順とリクエスト送信順が一致するため決定論的。
    成功件数は厳密に2件（== 2）で検証する。
    """
    users_to_create = [
        {"name": "User 1", "email": "user1@test.com"},
        {"name": "User 2", "email": "user2@test.com"},  # この1件を422エラーで失敗させる
        {"name": "User 3", "email": "user3@test.com"},
    ]

    # 2件目のリクエストを422（Unprocessable Entity）で失敗させる
    # 4xxはリトライなし即失敗 → APIHTTPError を return_exceptions が捕捉
    post_route = respx.post(f"{BASE_URL}/users")
    post_route.side_effect = [
        Response(201, json={"id": 101, "name": "User 1", "email": "user1@test.com"}),
        Response(422, json={"error": "Unprocessable Entity"}),  # 2件目: 422で即失敗
        Response(201, json={"id": 103, "name": "User 3", "email": "user3@test.com"}),
    ]

    async with AsyncJSONPlaceholderClient() as client:
        # 例外なく完了することを確認（silent partial failure）
        results = await client.bulk_create_users(users_to_create)

    # 部分失敗: 3件中1件(422)が失敗するため成功件数は正確に2件
    # Note: respxのside_effectはリクエスト到着順（task作成順）に消費され決定論的
    assert len(results) == 2, "3件中1件(422)が失敗するため、成功件数は正確に2件であること"

    # 全リクエストが試行されたことを確認（部分失敗でも全件送信）
    assert post_route.call_count == 3

    # 成功分のみ返却確認（存在確認 + 失敗ユーザーが含まれないことを確認）
    created_names = [result["name"] for result in results]
    assert "User 1" in created_names  # 1件目成功
    assert "User 3" in created_names  # 3件目成功
    assert "User 2" not in created_names  # 2件目は422エラーで失敗、返却されない


@respx.mock
async def test_async_bulk_create_users_partial_failure_4xx_log_structure():
    """
    4xx部分失敗時のwarningログ構造テスト（Sentry監視 + PII保護）

    検証項目：
    - bulk_create_partial_failure warningログが出力されること
    - failed_count / success_count が正しいこと
    - failed_detailsにerror_type / status_code / indexが含まれること
    - errorフィールドが省略されていること（_classify_errorと同方針）
    - user_dataフィールドが含まれないこと（PII保護: emailの漏洩防止）

    設計根拠：
    ログ構造はSentry監視の基盤であり、フィールド削除はリグレッションとして検出する。
    PII（user_data）がログに混入するとセキュリティインシデントとなるため、
    不在を明示的にアサートしてセキュリティリグレッションを防止する。
    """
    users_to_create = [
        {"name": "User 1", "email": "user1@test.com"},
        {"name": "User 2", "email": "user2@test.com"},  # この1件を422エラーで失敗させる
        {"name": "User 3", "email": "user3@test.com"},
    ]

    # 2件目のリクエストを422（Unprocessable Entity）で失敗させる
    # 4xxはリトライなし即失敗 → APIHTTPError を return_exceptions が捕捉
    post_route = respx.post(f"{BASE_URL}/users")
    post_route.side_effect = [
        Response(201, json={"id": 101, "name": "User 1", "email": "user1@test.com"}),
        Response(422, json={"error": "Unprocessable Entity"}),  # 2件目: 422で即失敗
        Response(201, json={"id": 103, "name": "User 3", "email": "user3@test.com"}),
    ]

    with capture_logs() as log_output:
        async with AsyncJSONPlaceholderClient() as client:
            await client.bulk_create_users(users_to_create)

    # warningログ検証（Sentry監視の保証: ログ削除時のリグレッション検出）
    partial_log = next(
        (log for log in log_output if log.get("event") == "bulk_create_partial_failure"),
        None,
    )
    assert partial_log is not None
    assert partial_log.get("log_level") == "warning"  # warningレベルであること
    assert partial_log.get("failed_count") == 1
    assert partial_log.get("success_count") == 2

    # failed_details 構造検証（error_type+status_code、error フィールドは省略）
    failed_details = partial_log.get("failed_details", [])
    assert len(failed_details) == 1, "1件の失敗詳細が記録されていること"
    failed_item = failed_details[0]
    assert "error" not in failed_item  # _classify_error と同方針で省略
    assert "user_data" not in failed_item  # PII保護: emailは含まれないこと
    assert failed_item.get("error_type") == "APIHTTPError", "エラー種別が記録されていること"
    assert failed_item.get("status_code") == 422, "HTTPステータスコードが記録されていること"
    assert "index" in failed_item, "失敗ユーザーのインデックスが記録されていること"


@respx.mock
async def test_async_bulk_create_users_partial_failure_5xx_returns_only_successful() -> None:
    """
    5xx部分失敗時の返却値テスト（silent partial failure + 成功分のみ返却）

    検証項目：
    - 一部リクエストが5xxエラーで失敗してもbulk_create_usersは例外を発生させない
    - 成功したユーザーのみが返却される（失敗分は除外）
    - 全リクエストが試行される（部分失敗でも中断しない）

    設計根拠：
    4xx（APIHTTPError即発生）と5xx（APIRetryError）では例外型が異なる別コードパス。
    5xx: request → 500 → last_exception=APIHTTPError → retry → 上限でAPIRetryError発生
    どちらもreturn_exceptions=Trueで捕捉され、isinstance(r, dict)フィルタで除外される。

    Note: retry_count=0で5xxリトライを無効化し、side_effectを3件に固定する（決定論的）。
    respxのside_effectはHTTPリクエストの受信順に消費される（asyncio.gatherのタスク作成順と
    概ね一致するが厳密保証なし）。retry_count=0で各タスクは1リクエストのみ発行するため安定。
    成功件数は厳密に2件（== 2）で検証する。
    """
    users_to_create = [
        {"name": "User 1", "email": "user1@test.com"},
        {"name": "User 2", "email": "user2@test.com"},  # この1件を500エラーで失敗させる
        {"name": "User 3", "email": "user3@test.com"},
    ]

    # 2件目のリクエストを500（Internal Server Error）で失敗させる
    # 5xxはリトライ対象だが、retry_count=0でリトライを無効化 → 即APIRetryErrorに変換
    # → return_exceptionsで捕捉され、成功分のみ返却される
    # side_effectリスト要素数は並行タスク数と一致させること。
    # retry_count=0 の場合: 各タスクは初回(1) のみ = 3タスク × 1リクエスト = 3要素。
    # 不一致時はStopIterationが発生しデバッグが困難になる。
    post_route = respx.post(f"{BASE_URL}/users")
    post_route.side_effect = [
        Response(201, json={"id": 101, "name": "User 1", "email": "user1@test.com"}),
        Response(500, json={"error": "Internal Server Error"}),  # 2件目: 500で失敗
        Response(201, json={"id": 103, "name": "User 3", "email": "user3@test.com"}),
    ]

    # retry_count=0: 5xxリトライなし → 即APIRetryError → side_effectは3件で決定論的
    async with AsyncJSONPlaceholderClient(retry_count=0) as client:
        # 例外なく完了することを確認（silent partial failure）
        results = await client.bulk_create_users(users_to_create)

    # 部分失敗: 3件中1件(500→APIRetryError)が失敗するため成功件数は正確に2件
    assert len(results) == 2, (
        "3件中1件(5xx→APIRetryError)が失敗するため、成功件数は正確に2件であること"
    )

    # 全リクエストが試行されたことを確認（部分失敗でも全件送信）
    assert post_route.call_count == 3

    # 成功分のみ返却確認（存在確認 + 失敗ユーザーが含まれないことを確認）
    created_names = [result["name"] for result in results]
    assert "User 1" in created_names  # 1件目成功
    assert "User 3" in created_names  # 3件目成功
    assert "User 2" not in created_names  # 2件目は500エラーで失敗、返却されない


@respx.mock
async def test_async_bulk_create_users_partial_failure_5xx_log_structure() -> None:
    """
    5xx部分失敗時のwarningログ構造テスト（Sentry監視 + PII保護）

    検証項目：
    - bulk_create_partial_failure warningログが出力されること
    - failed_count / success_count が正しいこと
    - failed_detailsにerror_type / indexが含まれること
    - status_codeが含まれないこと（5xxはAPIRetryErrorのためstatus_code不在）
    - errorフィールドが省略されていること（_classify_errorと同方針）
    - user_dataフィールドが含まれないこと（PII保護: emailの漏洩防止）

    設計根拠：
    ログ構造はSentry監視の基盤であり、フィールド削除はリグレッションとして検出する。
    PII（user_data）がログに混入するとセキュリティインシデントとなるため、
    不在を明示的にアサートしてセキュリティリグレッションを防止する。
    5xxはAPIRetryError（リトライ上限到達後の例外）であり、APIHTTPErrorと異なり
    status_codeを保持しないため、status_code不在もアサートする。
    """
    users_to_create = [
        {"name": "User 1", "email": "user1@test.com"},
        {"name": "User 2", "email": "user2@test.com"},  # この1件を500エラーで失敗させる
        {"name": "User 3", "email": "user3@test.com"},
    ]

    # 2件目のリクエストを500（Internal Server Error）で失敗させる
    # 5xxはリトライ対象だが、retry_count=0でリトライを無効化 → 即APIRetryErrorに変換
    # → return_exceptionsで捕捉され、成功分のみ返却される
    # side_effectリスト要素数は並行タスク数と一致させること。
    # retry_count=0 の場合: 各タスクは初回(1) のみ = 3タスク × 1リクエスト = 3要素。
    # 不一致時はStopIterationが発生しデバッグが困難になる。
    post_route = respx.post(f"{BASE_URL}/users")
    post_route.side_effect = [
        Response(201, json={"id": 101, "name": "User 1", "email": "user1@test.com"}),
        Response(500, json={"error": "Internal Server Error"}),  # 2件目: 500で失敗
        Response(201, json={"id": 103, "name": "User 3", "email": "user3@test.com"}),
    ]

    # retry_count=0: 5xxリトライなし → 即APIRetryError → side_effectは3件で決定論的
    with capture_logs() as log_output:
        async with AsyncJSONPlaceholderClient(retry_count=0) as client:
            await client.bulk_create_users(users_to_create)

    # warningログ検証（Sentry監視の保証: ログ削除時のリグレッション検出）
    partial_log = next(
        (log for log in log_output if log.get("event") == "bulk_create_partial_failure"),
        None,
    )
    assert partial_log is not None
    assert partial_log.get("log_level") == "warning"  # warningレベルであること
    assert partial_log.get("failed_count") == 1
    assert partial_log.get("success_count") == 2
    # failed_details構造検証: 5xx→APIRetryError のためstatus_codeは含まれない
    failed_details = partial_log.get("failed_details", [])
    assert len(failed_details) == 1
    failed_item = failed_details[0]
    assert "error" not in failed_item  # _classify_error と同方針で省略
    assert "user_data" not in failed_item  # PII保護: emailは含まれないこと
    assert failed_item.get("error_type") == "APIRetryError"
    assert "status_code" not in failed_item  # 5xxはAPIHTTPErrorでないためstatus_code不在
    assert "index" in failed_item, "失敗ユーザーのインデックスが記録されていること"


async def test_async_bulk_create_users_cancelled_error_propagates() -> None:
    """複数タスク同時キャンセル時にBaseExceptionGroupで伝播されることを確認（graceful shutdown保護）

    K8s SIGTERM等で複数タスクが同時にキャンセルされた場合、
    bulk_create_users は BaseExceptionGroup に全件を格納して呼び出し元に伝播させる。
    「ログに count=N と記録された件数と、伝播する例外件数の一貫性」を保証する設計。

    Python convention（asyncio.TaskGroup と同パターン）:
    - 1件 → 直接 raise（test_async_bulk_create_users_single_cancelled_error_no_log でカバー）
    - 複数件 → BaseExceptionGroup で伝播（本テスト）

    NOTE: ExceptionGroup ではなく BaseExceptionGroup を使用する理由:
          CancelledError は BaseException サブクラスのため ExceptionGroup に格納不可。
    """
    with patch.object(
        AsyncJSONPlaceholderClient,
        "create_user",
        new_callable=AsyncMock,
    ) as mock_create:
        mock_create.side_effect = asyncio.CancelledError()
        async with AsyncJSONPlaceholderClient() as client:
            # 2タスク同時キャンセル → BaseExceptionGroup で伝播
            with pytest.raises(BaseExceptionGroup) as exc_info:
                await client.bulk_create_users([{"name": "A"}, {"name": "B"}])
    # 格納された例外がすべて CancelledError であることを確認（graceful shutdown 伝播保証）
    assert len(exc_info.value.exceptions) == 2
    assert all(isinstance(e, asyncio.CancelledError) for e in exc_info.value.exceptions)


async def test_async_bulk_create_users_single_cancelled_error_no_log() -> None:
    """単一タスクキャンセル時は logger.error を呼ばずに CancelledError を再発生させることを確認

    len(fatal_exceptions) == 1 のコードパス（ログなし・raise のみ）を検証。
    len > 1 時のみ logger.error が呼ばれる設計であり、単一キャンセルはログ対象外。

    設計根拠: 単一タスクのキャンセルは通常の graceful shutdown シーケンスであり、
    ログノイズを避けるため意図的にログ出力しない設計になっている。
    """
    with patch.object(
        AsyncJSONPlaceholderClient,
        "create_user",
        new_callable=AsyncMock,
    ) as mock_create:
        mock_create.side_effect = asyncio.CancelledError()
        async with AsyncJSONPlaceholderClient() as client:
            with patch.object(client, "logger") as mock_logger:
                with pytest.raises(asyncio.CancelledError):
                    # 1タスクのみ → len(fatal_exceptions) == 1 → ログなし
                    await client.bulk_create_users([{"name": "A"}])
                # 単一キャンセルでは logger.error は呼ばれない
                mock_logger.error.assert_not_called()


async def test_async_bulk_create_users_multiple_cancelled_errors_logged() -> None:
    """複数タスク同時キャンセル時にerrorログが出力されることを確認

    K8s SIGTERM等で全タスクが同時キャンセルされると、
    asyncio.gather(return_exceptions=True) が複数の CancelledError を収集する。
    bulk_create_users は len(fatal_exceptions) > 1 の場合に
    logger.error("bulk_create_multiple_fatal_errors", ...) を呼び出す。
    """
    with patch.object(
        AsyncJSONPlaceholderClient,
        "create_user",
        new_callable=AsyncMock,
    ) as mock_create:
        mock_create.side_effect = asyncio.CancelledError()
        async with AsyncJSONPlaceholderClient() as client:
            with patch.object(client, "logger") as mock_logger:
                # 複数タスク同時キャンセル → BaseExceptionGroup で伝播（Python convention）
                # ログの count=2 と伝播する例外件数の一貫性を保証する設計
                # NOTE: CancelledError は BaseException サブクラスのため BaseExceptionGroup を使用
                with pytest.raises(BaseExceptionGroup) as exc_info:
                    await client.bulk_create_users([{"name": "A"}, {"name": "B"}])
                # patch.objectスコープ内でassert（モックが有効な期間中に検証）
                # 2ユーザー両方がキャンセル → len > 1 → logger.error 呼び出し確認
                mock_logger.error.assert_called_once_with(
                    "bulk_create_multiple_fatal_errors",
                    count=2,
                    types=["CancelledError", "CancelledError"],
                )
        # BaseExceptionGroup の中身が CancelledError であることを確認
        assert len(exc_info.value.exceptions) == 2
        assert all(isinstance(e, asyncio.CancelledError) for e in exc_info.value.exceptions)


@pytest.mark.parametrize(
    "fatal_exc",
    [MemoryError("OOM"), RecursionError("max depth")],
)
async def test_async_bulk_create_users_fatal_exception_propagates(
    fatal_exc: BaseException,
) -> None:
    """MemoryError / RecursionError が gather 後に再発生されることを確認

    bulk_create_users は asyncio.CancelledError だけでなく ASYNC_FATAL_EXCEPTIONS
    （MemoryError / RecursionError 等）も fatal_exceptions として収集して再発生させる
    （OOM / スタック枯渇保護）。_close_async_client の
    test_aclose_fatal_exception_propagates_not_suppressed が parametrize で
    両方をカバーしているため、設計の一貫性を保つよう本テストも parametrize 化する。

    実装の isinstance チェック対象（ASYNC_FATAL_EXCEPTIONS）:
    - asyncio.CancelledError: test_async_bulk_create_users_cancelled_error_propagates でカバー
    - MemoryError / RecursionError: 本テストでカバー
    - KeyboardInterrupt: pytest がシグナルとして処理するため unit test 内での再現が困難。
      pytest.raises(KeyboardInterrupt) を使っても pytest 自体のシグナルハンドラが先に捕捉する。
    - SystemExit: 同様の理由で unit test での再現が困難。
    """
    with patch.object(
        AsyncJSONPlaceholderClient,
        "create_user",
        new_callable=AsyncMock,
    ) as mock_create:
        mock_create.side_effect = fatal_exc
        async with AsyncJSONPlaceholderClient() as client:
            with pytest.raises(type(fatal_exc)):
                await client.bulk_create_users([{"name": "A"}])


@respx.mock
async def test_async_health_check_success():
    """
    API ヘルスチェック正常系テスト

    検証項目：
    - health_check()メソッドの正常動作
    - 正常時: True返却
    """
    route = respx.get(f"{BASE_URL}/users", params={"_limit": 1}).respond(
        json=[{"id": 1, "name": "User 1"}]
    )

    async with AsyncJSONPlaceholderClient() as client:
        result = await client.health_check()

    assert result is True
    assert route.call_count == 1


@respx.mock
async def test_async_health_check_connection_error():
    """
    API ヘルスチェック接続エラー時のテスト

    検証項目：
    - 接続エラー時: False返却（graceful degradation）
    - httpx.ConnectError → _make_request_with_retry内でAPIConnectionErrorに変換
      → health_checkでキャッチ
    """
    route = respx.get(f"{BASE_URL}/users", params={"_limit": 1}).mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    async with AsyncJSONPlaceholderClient(retry_count=0) as client:
        result = await client.health_check()

    assert result is False
    assert route.call_count == 1  # retry_count=0なのでリトライなし（1回のみ実行）


@respx.mock
async def test_async_health_check_log_structure() -> None:
    """health_check失敗時のログ構造検証（error_type/endpointフィールド）"""
    respx.get(f"{BASE_URL}/users", params={"_limit": 1}).mock(
        side_effect=httpx.ConnectError("Connection refused to secret-host.internal")
    )

    async with AsyncJSONPlaceholderClient(retry_count=0) as client:
        with patch.object(client, "logger") as mock_logger:
            result = await client.health_check()

    assert result is False
    # warning は request_error と health_check_failed の2回呼ばれる
    assert mock_logger.warning.call_count == 2
    # health_check_failed の呼び出しを抽出
    health_check_call = next(
        (c for c in mock_logger.warning.call_args_list if c[0][0] == "health_check_failed"),
        None,
    )
    assert health_check_call is not None, "health_check_failed ログが出力されていない"
    # 必須フィールドの検証
    assert health_check_call[1]["error_type"] == "APIRetryError"
    assert health_check_call[1]["endpoint"] == "/users"
    # セキュリティ: error フィールド省略（_classify_error と同方針）
    assert "error" not in health_check_call[1]
    # async_all_retries_failed の error フィールド省略検証（機密情報保護）
    all_retries_call = next(
        (c for c in mock_logger.error.call_args_list if c[0][0] == "async_all_retries_failed"),
        None,
    )
    assert all_retries_call is not None, "async_all_retries_failed ログが出力されていること"
    assert "error" not in all_retries_call[1]


@respx.mock
async def test_get_user_data_parallel_requests():
    """
    get_user_data()の4並行API呼び出しとデータ整合性検証

    検証項目：
    - 4つのAPI（user/posts/todos/albums）が並行実行される
    - asyncio.TaskGroupによる効率的な並行処理
    - postsのuserIdフィルタリングが正しく機能する
    - 返却データ構造が{user, posts, todos, albums}である
    - 各フィールドに期待されるデータ型が含まれる
    """
    user_id = 1

    # 4つのAPIエンドポイントをモック化
    # User API（Userモデルに必要な全フィールドを含む）
    route_user = respx.get(f"{BASE_URL}/users/{user_id}").respond(json=make_canonical_user(user_id))

    # Posts API（user_id=1のみ - API側フィルタリング）
    route_posts = respx.get(f"{BASE_URL}/posts", params={"userId": user_id}).respond(
        json=[
            {"id": 1, "userId": 1, "title": "Post by User 1", "body": "Content 1"},
            {"id": 3, "userId": 1, "title": "Another post by User 1", "body": "Content 3"},
        ]
    )

    # Todos API（user_id=1のみ）
    route_todos = respx.get(f"{BASE_URL}/todos", params={"userId": user_id}).respond(
        json=[
            {"id": 1, "userId": 1, "title": "Todo 1", "completed": True},
            {"id": 2, "userId": 1, "title": "Todo 2", "completed": False},
        ]
    )

    # Albums API（user_id=1のみ）
    route_albums = respx.get(f"{BASE_URL}/albums", params={"userId": user_id}).respond(
        json=[
            {"id": 1, "userId": 1, "title": "Album 1"},
            {"id": 2, "userId": 1, "title": "Album 2"},
        ]
    )

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        result = await client.get_user_data(user_id)

    # データ構造検証
    assert isinstance(result["user"], User)

    # ユーザー情報検証
    assert result["user"].id == 1
    assert result["user"].name == "Leanne Graham"

    # postsフィルタリング検証（userId=1のみが含まれる）
    assert len(result["posts"]) == 2
    assert all(isinstance(post, Post) for post in result["posts"])
    assert all(post.user_id == 1 for post in result["posts"])
    assert result["posts"][0].id == 1
    assert result["posts"][1].id == 3

    # todos検証
    assert len(result["todos"]) == 2
    assert all(isinstance(todo, Todo) for todo in result["todos"])
    assert all(todo.user_id == 1 for todo in result["todos"])

    # albums検証
    assert len(result["albums"]) == 2
    assert all(isinstance(album, Album) for album in result["albums"])
    assert all(album.user_id == 1 for album in result["albums"])

    # 4つのAPIが各1回ずつ呼ばれたことを確認（TaskGroupによる並行実行の証明）
    assert route_user.call_count == 1
    assert route_posts.call_count == 1
    assert route_todos.call_count == 1
    assert route_albums.call_count == 1


@respx.mock
async def test_get_user_data_with_empty_posts():
    """
    get_user_data()で一部APIが空リスト返却時の動作検証

    検証項目：
    - posts APIが空リストを返す場合でもエラーにならない
    - 他のAPI（todos/albums）は正常に取得される
    - graceful degradation（部分失敗許容）の実装確認
    """
    user_id = 1

    # User API（Userモデルに必要な全フィールドを含む）
    route_user = respx.get(f"{BASE_URL}/users/{user_id}").respond(
        json={
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
            "website": "https://hildegard.org",
            "company": {
                "name": "Romaguera-Crona",
                "catchPhrase": "Multi-layered client-server neural-net",
                "bs": "harness real-time e-markets",
            },
        }
    )

    # Posts API: userId=1 でフィルタされた結果が空
    route_posts = respx.get(f"{BASE_URL}/posts", params={"userId": user_id}).respond(json=[])

    # Todos API
    route_todos = respx.get(f"{BASE_URL}/todos", params={"userId": user_id}).respond(
        json=[{"id": 1, "userId": 1, "title": "Todo 1", "completed": True}]
    )

    # Albums API
    route_albums = respx.get(f"{BASE_URL}/albums", params={"userId": user_id}).respond(
        json=[{"id": 1, "userId": 1, "title": "Album 1"}]
    )

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        result = await client.get_user_data(user_id)

    # posts が空リストでも正常動作
    assert result["posts"] == []
    assert len(result["todos"]) == 1
    assert len(result["albums"]) == 1
    assert isinstance(result["user"], User)
    assert all(isinstance(todo, Todo) for todo in result["todos"])
    assert all(isinstance(album, Album) for album in result["albums"])

    # 4つのAPIが各1回ずつ呼ばれたことを確認（TaskGroupによる並行実行の証明）
    assert route_user.call_count == 1
    assert route_posts.call_count == 1
    assert route_todos.call_count == 1
    assert route_albums.call_count == 1


@respx.mock
async def test_get_user_data_user_not_found():
    """
    get_user_data()でユーザーが404の場合にAPIHTTPErrorが伝播することを確認

    検証項目：
    - /users/999 が404を返す場合、APIHTTPErrorが発生する
    - status_code == 404 が正しく設定される
    - TaskGroup が送出する ExceptionGroup から個別 APIHTTPError へ unwrap され、
      呼び出し元は従来どおり APIHTTPError で捕捉できる（契約維持）
    """
    user_id = 999

    # /users/999 は 404 を返す
    route_user = respx.get(f"{BASE_URL}/users/{user_id}").respond(status_code=404)

    # posts/todos/albums は正常応答（userId フィルタ付き）
    # TaskGroup は 1 タスク失敗時に残りを自動キャンセルするため、兄弟タスクは
    # キャンセルのタイミング次第で呼ばれない場合がある（call_count <= 1）。
    route_posts = respx.get(f"{BASE_URL}/posts", params={"userId": user_id}).respond(json=[])
    route_todos = respx.get(f"{BASE_URL}/todos", params={"userId": user_id}).respond(json=[])
    route_albums = respx.get(f"{BASE_URL}/albums", params={"userId": user_id}).respond(json=[])

    # retry_count=0 でリトライなし（即時失敗）
    async with AsyncJSONPlaceholderClient(retry_count=0) as client:
        with pytest.raises(APIHTTPError) as exc_info:
            await client.get_user_data(user_id)

    assert exc_info.value.status_code == 404

    # 失敗タスク（user）は必ず1回呼ばれる。兄弟タスクは TaskGroup のキャンセルに
    # より呼ばれないことがあるため <= 1 を検証する。
    assert route_user.call_count == 1
    assert route_posts.call_count <= 1
    assert route_todos.call_count <= 1
    assert route_albums.call_count <= 1


@respx.mock
async def test_get_user_data_posts_server_error():
    """
    get_user_data()で /posts が500エラーの場合にAPIRetryErrorが伝播することを確認

    検証項目：
    - /posts が500を返す場合、APIRetryErrorが発生する
    - retry_count=0 の場合はリトライせず即時失敗する
    - TaskGroup が送出する ExceptionGroup から個別 APIRetryError へ unwrap され、
      呼び出し元は従来どおり APIRetryError で捕捉できる（契約維持）
    """
    user_id = 1

    # /users/1 は正常応答（Userモデルに必要な全フィールドを含む）
    route_user = respx.get(f"{BASE_URL}/users/{user_id}").respond(
        json={
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
            "website": "https://hildegard.org",
            "company": {
                "name": "Romaguera-Crona",
                "catchPhrase": "Multi-layered client-server neural-net",
                "bs": "harness real-time e-markets",
            },
        }
    )

    # /posts は 500 エラー（userId フィルタ付き）
    route_posts = respx.get(f"{BASE_URL}/posts", params={"userId": user_id}).respond(
        status_code=500
    )

    # todos/albums は正常応答
    route_todos = respx.get(f"{BASE_URL}/todos", params={"userId": user_id}).respond(json=[])
    route_albums = respx.get(f"{BASE_URL}/albums", params={"userId": user_id}).respond(json=[])

    # retry_count=0 でリトライなし（即時失敗）
    async with AsyncJSONPlaceholderClient(retry_count=0) as client:
        with pytest.raises(APIRetryError):
            await client.get_user_data(user_id)

    # 失敗タスク（posts）は必ず1回呼ばれる（retry_count=0 のためリトライなし）。
    # 兄弟タスク（user/todos/albums）は TaskGroup のキャンセルにより呼ばれない
    # ことがあるため <= 1 を検証する。
    assert route_posts.call_count == 1
    assert route_user.call_count <= 1
    assert route_todos.call_count <= 1
    assert route_albums.call_count <= 1


@pytest.mark.parametrize(
    "limit,expected_count,test_description",
    [
        (2, 2, "limit=2で2件取得"),
        (None, 5, "limit=Noneで全件取得（モックは5件）"),
        (0, 0, "limit=0で0件取得（境界値検証、API仕様では空配列返却）"),
        (100, 5, "limit=100で上限超過時は全件取得"),
    ],
    ids=["normal_limit", "no_limit", "zero_limit", "excessive_limit"],
)
@respx.mock
async def test_get_posts_with_various_limits(limit, expected_count, test_description):
    """
    get_posts()のlimitパラメータ動作検証（parametrize）

    検証項目：
    - limit=2: 正常に2件取得
    - limit=None: パラメータなしで全件取得
    - limit=0: 境界値で0件取得（`if limit is not None`対応後）
    - limit=100: 上限超過時は利用可能な全件取得
    """
    # モックデータ（5件の投稿）
    all_posts = [
        {"id": i, "userId": 1, "title": f"Post {i}", "body": f"Content {i}"} for i in range(1, 6)
    ]

    # limitパラメータに応じてrespxエンドポイントを設定
    if limit is None:
        # limit指定なし: クエリパラメータなしのURL
        respx.get(f"{BASE_URL}/posts").respond(json=all_posts)
        expected_posts = all_posts
    elif limit == 0:
        # limit=0: API仕様では空配列[]を返却（境界値テスト）
        respx.get(f"{BASE_URL}/posts", params={"_limit": 0}).respond(json=[])
        expected_posts = []
    else:
        # limit指定あり: クエリパラメータ付きURL
        respx.get(f"{BASE_URL}/posts", params={"_limit": limit}).respond(json=all_posts[:limit])
        expected_posts = all_posts[:limit]

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        result = await client.get_posts(limit=limit)

    # 結果検証
    actual_expected = len(expected_posts)
    assert len(result) == actual_expected, (
        f"{test_description}: expected {actual_expected}, got {len(result)}"
    )
    assert [post.model_dump(by_alias=True) for post in result] == expected_posts
    assert all(isinstance(post, Post) for post in result)


@pytest.mark.parametrize(
    "user_id,expected_count,test_description",
    [
        (None, 5, "user_id=Noneで全投稿取得（フィルタなし）"),
        (1, 2, "user_id=1でユーザー1の投稿のみ取得（API側フィルタ）"),
        (2, 1, "user_id=2でユーザー2の投稿のみ取得"),
        (999, 0, "user_id=999で存在しないユーザー（空配列返却）"),
    ],
    ids=["no_filter", "user_1", "user_2", "nonexistent_user"],
)
@respx.mock
async def test_async_get_posts_user_filter(user_id, expected_count, test_description):
    """
    get_posts()のuser_idパラメータ動作検証（API側フィルタリング）

    検証項目：
    - user_id=None: フィルタなしで全投稿取得
    - user_id=1/2: 指定ユーザーの投稿のみ取得（API側フィルタ）
    - user_id=999: 存在しないユーザーで空配列返却
    """
    # モックデータ（5件の投稿、userId=1が2件、userId=2が1件、userId=3が2件）
    all_posts = [
        {"id": 1, "userId": 1, "title": "Post 1 by User 1", "body": "Content 1"},
        {"id": 2, "userId": 2, "title": "Post 2 by User 2", "body": "Content 2"},
        {"id": 3, "userId": 1, "title": "Post 3 by User 1", "body": "Content 3"},
        {"id": 4, "userId": 3, "title": "Post 4 by User 3", "body": "Content 4"},
        {"id": 5, "userId": 3, "title": "Post 5 by User 3", "body": "Content 5"},
    ]

    # user_idパラメータに応じてrespxエンドポイントを設定
    if user_id is None:
        # user_idなし: 全件取得
        respx.get(f"{BASE_URL}/posts").respond(json=all_posts)
        expected_posts = all_posts
    elif user_id == 999:
        # 存在しないuser_id: 空配列
        respx.get(f"{BASE_URL}/posts", params={"userId": user_id}).respond(json=[])
        expected_posts = []
    else:
        # user_id指定: API側フィルタリング
        filtered_posts = [p for p in all_posts if p["userId"] == user_id]
        respx.get(f"{BASE_URL}/posts", params={"userId": user_id}).respond(json=filtered_posts)
        expected_posts = filtered_posts

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        result = await client.get_posts(user_id=user_id)

    # 結果検証
    assert len(result) == expected_count, (
        f"{test_description}: expected {expected_count}, got {len(result)}"
    )
    assert [post.model_dump(by_alias=True) for post in result] == expected_posts
    if user_id is not None and user_id != 999:
        # user_id指定時は全投稿が指定ユーザーのものであることを確認
        assert all(post.user_id == user_id for post in result)


@pytest.mark.parametrize(
    "limit,user_id,expected_error",
    [
        (-1, None, "limit must be >= 0"),
        (-100, None, "limit must be >= 0"),
        (None, 0, "user_id must be >= 1"),
        (None, -1, "user_id must be >= 1"),
        (-1, 0, "limit must be >= 0"),  # limitが先に検証される
    ],
    ids=[
        "negative_limit",
        "very_negative_limit",
        "zero_user_id",
        "negative_user_id",
        "both_invalid_limit_first",
    ],
)
async def test_async_get_posts_validation_error(limit, user_id, expected_error):
    """
    get_posts()の入力値バリデーション検証

    検証項目：
    - limit < 0: ValueError発生
    - user_id < 1: ValueError発生（JSONPlaceholder APIはID=1から）
    - 両方無効な場合: limitが先に検証される
    """
    async with AsyncJSONPlaceholderClient() as client:
        with pytest.raises(ValueError, match=expected_error):
            await client.get_posts(limit=limit, user_id=user_id)


@respx.mock
async def test_get_post_by_id_success():
    """
    get_post()の正常系テスト

    検証項目：
    - post_id指定で特定投稿を取得
    - レスポンスデータが正確に返却される
    - エンドポイントが正しく構築される（/posts/{post_id}）
    """
    post_id = 1
    expected_post = {"id": 1, "userId": 1, "title": "Test Post", "body": "Test Content"}

    # モック設定
    route = respx.get(f"{BASE_URL}/posts/{post_id}").respond(json=expected_post)

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        result = await client.get_post(post_id)

    # 結果検証
    assert result.model_dump(by_alias=True) == expected_post
    assert result.id == post_id
    assert result.title is not None
    assert result.body is not None
    assert route.call_count == 1  # HTTPリクエストが1回発行されたことを確認


@respx.mock
async def test_get_post_not_found():
    """
    get_post()の404エラーケーステスト

    検証項目：
    - 存在しないpost_idで404エラーが発生
    - APIHTTPErrorが正しく発生する
    - エラーステータスコードが404である
    """
    post_id = 999999

    # 404レスポンスをモック化
    respx.get(f"{BASE_URL}/posts/{post_id}").respond(status_code=404)

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        with pytest.raises(APIHTTPError) as exc_info:
            await client.get_post(post_id)

        # エラー詳細検証
        assert exc_info.value.status_code == 404


@respx.mock
async def test_create_post_success():
    """
    create_post()の正常系テスト

    検証項目：
    - title/body/user_id指定で投稿作成
    - レスポンスにidが付与される（サーバー生成）
    - POSTリクエストが正しく送信される
    - JSONデータが正確に送信される
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

    # モック設定（ルート固有のcall_countで検証）
    route = respx.post(f"{BASE_URL}/posts").respond(status_code=201, json=expected_response)

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        result = await client.create_post(title=title, body=body, user_id=user_id)

    # 結果検証
    assert result.id == 101
    assert result.user_id == user_id
    assert result.title == title
    assert result.body == body

    # リクエストボディの内容を検証（フィールド名変更の退行検出）
    request_body = json.loads(route.calls[0].request.content)
    assert request_body["title"] == title
    assert request_body["body"] == body
    assert request_body["userId"] == user_id


@respx.mock
async def test_create_post_with_empty_body():
    """
    create_post()でbody空文字列のエッジケーステスト

    検証項目：
    - body=空文字列でも投稿作成が成功する
    - 必須フィールド（title/user_id）のみで作成可能
    - APIが空文字列を許容する動作確認
    """
    title = "Post with Empty Body"
    body = ""  # 空文字列
    user_id = 1

    expected_response = {"id": 102, "userId": user_id, "title": title, "body": body}

    # モック設定（route変数に保存してリクエスト内容を後で検証できるようにする）
    route = respx.post(f"{BASE_URL}/posts").respond(status_code=201, json=expected_response)

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        result = await client.create_post(title=title, body=body, user_id=user_id)

    # レスポンス検証
    assert result.id == 102
    assert result.body == ""  # 空文字列が保持される

    # リクエストボディ検証: 空文字列が実際に送信されているか確認
    request_body = json.loads(route.calls[0].request.content)
    assert request_body["body"] == ""  # 空文字列が送信されていることを確認
    assert request_body["title"] == title
    assert request_body["userId"] == user_id


@pytest.mark.parametrize(
    "user_id,completed,limit,expected_params,expected_count,test_description",
    [
        (1, True, 5, {"userId": 1, "completed": True, "_limit": 5}, 2, "全パラメータ指定"),
        (1, None, None, {"userId": 1}, 3, "user_idのみ指定"),
        (None, False, 10, {"completed": False, "_limit": 10}, 2, "completedとlimit指定"),
        (None, None, None, {}, 5, "パラメータなし（全取得）"),
        (2, True, None, {"userId": 2, "completed": True}, 1, "user_id=2, completed=True"),
    ],
    ids=[
        "all_params",
        "user_id_only",
        "completed_and_limit",
        "no_params",
        "user2_completed",
    ],
)
@respx.mock
async def test_get_todos_with_filters(
    user_id, completed, limit, expected_params, expected_count, test_description
):
    """
    get_todos()の複数パラメータ組み合わせ検証（parametrize）

    検証項目：
    - user_id/completed/limitの全組み合わせ動作確認
    - クエリパラメータが正確に構築される
    - Noneパラメータは送信されない（APIデフォルト動作）
    - フィルタ結果が期待通りの件数である
    """
    # モックデータ（5件のTODO、複数ユーザー/完了状態）
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

    # respxモック設定（params__eq で厳格マッチング: 空dict=クエリなし, 非空dict=完全一致）
    route = respx.get(f"{BASE_URL}/todos", params__eq=expected_params).respond(json=filtered_todos)

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        result = await client.get_todos(user_id=user_id, completed=completed, limit=limit)

    # 結果検証
    assert len(result) == expected_count, (
        f"{test_description}: expected {expected_count}, got {len(result)}"
    )
    assert [todo.model_dump(by_alias=True) for todo in result] == filtered_todos
    assert all(isinstance(todo, Todo) for todo in result)
    assert route.call_count == 1  # HTTPリクエストが1回発行されたことを確認

    # 追加検証: フィルタ条件が結果に反映されている
    if user_id is not None:
        assert all(t.user_id == user_id for t in result)
    if completed is not None:
        assert all(t.completed == completed for t in result)


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
async def test_async_get_todos_validation_error(limit, user_id, expected_error):
    """
    get_todos()の入力値バリデーション検証

    検証項目：
    - limit < 0: ValueError発生
    - user_id < 1: ValueError発生（JSONPlaceholder APIはID=1から）
    - 両方無効な場合: limitが先に検証される
    """
    async with AsyncJSONPlaceholderClient() as client:
        with pytest.raises(ValueError, match=expected_error):
            await client.get_todos(limit=limit, user_id=user_id)


@pytest.mark.parametrize(
    "user_id,expected_count,test_description",
    [
        (1, 2, "user_id=1でアルバム取得"),
        (None, 5, "user_id指定なしで全アルバム取得"),
        (2, 1, "user_id=2でアルバム取得"),
    ],
    ids=["user_id_1", "no_user_id", "user_id_2"],
)
@respx.mock
async def test_get_albums_with_filters(user_id, expected_count, test_description):
    """
    get_albums()のuser_idパラメータ検証（parametrize）

    検証項目：
    - user_id指定時に正しくパラメータが送信される
    - user_id=Noneで全件取得
    - フィルタ結果が期待通りの件数である
    """
    # モックデータ（5件のアルバム、複数ユーザー）
    all_albums = [
        {"id": 1, "userId": 1, "title": "Album 1"},
        {"id": 2, "userId": 1, "title": "Album 2"},
        {"id": 3, "userId": 2, "title": "Album 3"},
        {"id": 4, "userId": 3, "title": "Album 4"},
        {"id": 5, "userId": 3, "title": "Album 5"},
    ]

    # パラメータフィルタ + respxモック設定（params__eq 厳格マッチング）
    filtered_albums = (
        [a for a in all_albums if a["userId"] == user_id] if user_id is not None else all_albums
    )
    expected_params = {"userId": user_id} if user_id is not None else {}
    route = respx.get(f"{BASE_URL}/albums", params__eq=expected_params).respond(
        json=filtered_albums
    )

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        result = await client.get_albums(user_id=user_id)

    # 結果検証
    assert len(result) == expected_count, (
        f"{test_description}: expected {expected_count}, got {len(result)}"
    )
    assert [album.model_dump(by_alias=True) for album in result] == filtered_albums
    assert all(isinstance(album, Album) for album in result)
    assert route.call_count == 1  # HTTPリクエストが1回発行されたことを確認

    # user_idフィルタ検証
    if user_id is not None:
        assert all(a.user_id == user_id for a in result)


@pytest.mark.parametrize(
    "user_id,expected_error",
    [
        (0, "user_id must be >= 1"),
        (-1, "user_id must be >= 1"),
    ],
    ids=["zero_user_id", "negative_user_id"],
)
async def test_async_get_albums_validation_error(user_id, expected_error):
    """
    get_albums()の入力値バリデーション検証

    検証項目：
    - user_id < 1: ValueError発生（JSONPlaceholder APIはID=1から）
    """
    async with AsyncJSONPlaceholderClient() as client:
        with pytest.raises(ValueError, match=expected_error):
            await client.get_albums(user_id=user_id)


@pytest.mark.parametrize(
    "album_id,expected_count,test_description",
    [
        (1, 2, "album_id=1で写真取得"),
        (None, 6, "album_id指定なしで全写真取得"),
        (2, 1, "album_id=2で写真取得"),
    ],
    ids=["album_id_1", "no_album_id", "album_id_2"],
)
@respx.mock
async def test_get_photos_with_filters(album_id, expected_count, test_description):
    """
    get_photos()のalbum_idパラメータ検証（parametrize）

    検証項目：
    - album_id指定時に正しくエンドポイントが構築される（/albums/{album_id}/photos）
    - album_id=Noneで全件取得（/photos）
    - フィルタ結果が期待通りの件数である
    """
    # モックデータ（6件の写真、複数アルバム）
    all_photos = [
        {
            "id": 1,
            "albumId": 1,
            "title": "Photo 1",
            "url": "https://example.com/1.jpg",
            "thumbnailUrl": "https://example.com/1-thumb.jpg",
        },
        {
            "id": 2,
            "albumId": 1,
            "title": "Photo 2",
            "url": "https://example.com/2.jpg",
            "thumbnailUrl": "https://example.com/2-thumb.jpg",
        },
        {
            "id": 3,
            "albumId": 2,
            "title": "Photo 3",
            "url": "https://example.com/3.jpg",
            "thumbnailUrl": "https://example.com/3-thumb.jpg",
        },
        {
            "id": 4,
            "albumId": 3,
            "title": "Photo 4",
            "url": "https://example.com/4.jpg",
            "thumbnailUrl": "https://example.com/4-thumb.jpg",
        },
        {
            "id": 5,
            "albumId": 3,
            "title": "Photo 5",
            "url": "https://example.com/5.jpg",
            "thumbnailUrl": "https://example.com/5-thumb.jpg",
        },
        {
            "id": 6,
            "albumId": 3,
            "title": "Photo 6",
            "url": "https://example.com/6.jpg",
            "thumbnailUrl": "https://example.com/6-thumb.jpg",
        },
    ]

    # パラメータに応じてフィルタとURL構築
    if album_id is not None:
        filtered_photos = [p for p in all_photos if p["albumId"] == album_id]
        url = f"{BASE_URL}/albums/{album_id}/photos"
    else:
        filtered_photos = all_photos
        url = f"{BASE_URL}/photos"

    # respxモック設定
    respx.get(url).respond(json=filtered_photos)

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        result = await client.get_photos(album_id=album_id)

    # 結果検証
    assert len(result) == expected_count, (
        f"{test_description}: expected {expected_count}, got {len(result)}"
    )
    assert [photo.model_dump(by_alias=True) for photo in result] == filtered_photos
    assert all(isinstance(photo, Photo) for photo in result)

    # album_idフィルタ検証
    if album_id is not None:
        assert all(p.album_id == album_id for p in result)


@respx.mock
async def test_async_get_comments_with_post_id() -> None:
    """
    AsyncJSONPlaceholderClient.get_comments()のpost_id指定時の正常系

    検証項目：
    - post_id=1 指定時に /posts/1/comments にGETリクエストが送られる
    - レスポンスのコメントリストがそのまま返される
    - リクエストが1回だけ発行される
    """
    mock_comments = [
        {"id": 1, "postId": 1, "name": "Test Comment", "email": "test@example.com", "body": "Body"},
    ]
    route = respx.get(f"{BASE_URL}/posts/1/comments").respond(json=mock_comments)

    async with AsyncJSONPlaceholderClient() as client:
        result = await client.get_comments(post_id=1)

    assert route.call_count == 1
    assert [comment.model_dump(by_alias=True) for comment in result] == mock_comments


@respx.mock
async def test_async_get_comments_without_post_id() -> None:
    """
    AsyncJSONPlaceholderClient.get_comments()のpost_id未指定時の正常系

    検証項目：
    - post_id未指定時に /comments にGETリクエストが送られる
    - 全コメントのリストがそのまま返される
    - リクエストが1回だけ発行される
    """
    mock_comments = [
        {"id": 1, "postId": 1, "name": "Comment 1", "email": "a@b.com", "body": "Body 1"},
        {"id": 2, "postId": 2, "name": "Comment 2", "email": "c@d.com", "body": "Body 2"},
    ]
    route = respx.get(f"{BASE_URL}/comments", params__eq={}).respond(json=mock_comments)

    async with AsyncJSONPlaceholderClient() as client:
        result = await client.get_comments()

    assert route.call_count == 1
    assert [comment.model_dump(by_alias=True) for comment in result] == mock_comments


@pytest.mark.parametrize(
    "post_id",
    [0, -1, -100],
    ids=["post_id_zero", "post_id_negative", "post_id_large_negative"],
)
async def test_async_get_comments_invalid_post_id(
    post_id: int,
) -> None:
    """
    AsyncJSONPlaceholderClient.get_comments()の無効post_idバリデーション

    検証項目：
    - post_id=0 は ValueError を発生させる（JSONPlaceholder API は1-based ID）
    - 負数のpost_idも同様に ValueError を発生させる
    - HTTP リクエストは発行されない（ValueError がHTTPリクエスト前に発生するため
      @respx.mock デコレータ・呼び出し検証は不要）
    """
    async with AsyncJSONPlaceholderClient() as client:
        with pytest.raises(ValueError, match="post_id must be >= 1"):
            await client.get_comments(post_id=post_id)


@pytest.mark.parametrize(
    "album_id",
    [0, -1, -100],
    ids=["album_id_zero", "album_id_negative", "album_id_large_negative"],
)
async def test_async_get_photos_invalid_album_id(album_id: int) -> None:
    """
    AsyncJSONPlaceholderClient.get_photos()の無効album_idバリデーション

    検証項目：
    - album_id=0 は ValueError を発生させる（JSONPlaceholder API は1-based ID）
    - 負数のalbum_idも同様に ValueError を発生させる
    - HTTP リクエストは発行されない（ValueError がHTTPリクエスト前に発生するため
      @respx.mock デコレータ・呼び出し検証は不要）
    """
    async with AsyncJSONPlaceholderClient() as client:
        with pytest.raises(ValueError, match="album_id must be >= 1"):
            await client.get_photos(album_id=album_id)


@respx.mock
async def test_async_get_users(sample_users_list: list[dict[str, Any]]) -> None:
    """AsyncJSONPlaceholderClient.get_users() ユーザー一覧取得の動作確認

    検証項目:
    - GET /users リクエストが送信される
    - ユーザーリストが正しく返される
    - call_count で1回のリクエストを確認
    """
    route = respx.get(f"{BASE_URL}/users").respond(json=sample_users_list[:2])

    async with AsyncJSONPlaceholderClient() as client:
        result = await client.get_users()

    assert len(result) == 2
    assert result[0].name == "Leanne Graham"
    assert result[1].id == 2
    assert route.call_count == 1


@respx.mock
async def test_async_get_users_returns_empty_list() -> None:
    """AsyncJSONPlaceholderClient.get_users() ユーザーが存在しない場合に空リストを返すことを確認

    検証項目:
    - API が空配列を返す場合、空リストを返す
    - call_count で1回のリクエストを確認
    """
    route = respx.get(f"{BASE_URL}/users").respond(json=[])

    async with AsyncJSONPlaceholderClient() as client:
        result = await client.get_users()

    assert result == []
    assert route.call_count == 1


@respx.mock
async def test_async_update_todo() -> None:
    """AsyncJSONPlaceholderClient.update_todo() TODO部分更新（PATCH）の動作確認

    検証項目:
    - PATCH /todos/{id} リクエストが送信される
    - HTTPメソッドが "PATCH" である
    - リクエストボディに kwargs が正しく含まれる
    - 更新後のデータが正しく返される
    """
    todo_id = 1
    patch_data = {"completed": True}
    full_response = {"id": todo_id, "title": "delectus aut autem", "completed": True, "userId": 1}

    route = respx.patch(f"{BASE_URL}/todos/{todo_id}").respond(status_code=200, json=full_response)

    async with AsyncJSONPlaceholderClient() as client:
        result = await client.update_todo(todo_id, completed=True)

    assert result == full_response
    assert result["completed"] is True
    assert route.call_count == 1
    assert route.calls[0].request.method == "PATCH"

    # リクエストボディが kwargs と一致することを確認
    request_body = json.loads(route.calls[0].request.content)
    assert request_body == patch_data


@respx.mock
async def test_async_update_todo_multiple_fields() -> None:
    """AsyncJSONPlaceholderClient.update_todo() 複数フィールド同時更新の動作確認

    検証項目:
    - 複数の kwargs が正しくリクエストボディに含まれる
    - title と completed の両方が更新される

    - **kwargs の多フィールド展開: 辞書としてリクエストボディに渡される
    """
    todo_id = 1
    full_response = {
        "id": todo_id,
        "title": "Updated Title",
        "completed": True,
        "userId": 1,
    }

    route = respx.patch(f"{BASE_URL}/todos/{todo_id}").respond(status_code=200, json=full_response)

    async with AsyncJSONPlaceholderClient() as client:
        result = await client.update_todo(todo_id, title="Updated Title", completed=True)

    assert result["title"] == "Updated Title"
    assert result["completed"] is True
    assert route.call_count == 1

    # 複数フィールドがリクエストボディに含まれることを確認
    request_body = json.loads(route.calls[0].request.content)
    assert request_body == {"title": "Updated Title", "completed": True}


async def test_bulk_create_users_details_truncated_false_at_max() -> None:
    """失敗が上限件数ちょうど（MAX_LOGGED_FAILURE_DETAILS）では details_truncated=False。"""
    client = AsyncJSONPlaceholderClient(base_url="https://test.com")
    with patch.object(client, "create_user", new=AsyncMock(side_effect=RuntimeError("fail"))):
        with capture_logs() as logs:
            result = await client.bulk_create_users(
                [{"name": f"u{i}"} for i in range(MAX_LOGGED_FAILURE_DETAILS)]
            )
    assert result == []
    warn = next((lg for lg in logs if lg.get("event") == "bulk_create_partial_failure"), None)
    assert warn is not None
    assert warn["failed_count"] == MAX_LOGGED_FAILURE_DETAILS
    assert warn["success_count"] == 0
    assert warn["details_truncated"] is False
    assert len(warn["failed_details"]) == MAX_LOGGED_FAILURE_DETAILS
    detail = warn["failed_details"][0]
    assert "index" in detail
    assert "error_type" in detail


async def test_bulk_create_users_details_truncated_true_above_max() -> None:
    """失敗件数が MAX_LOGGED_FAILURE_DETAILS+1 のとき details_truncated=True になる境界を検証。"""
    client = AsyncJSONPlaceholderClient(base_url="https://test.com")
    with patch.object(client, "create_user", new=AsyncMock(side_effect=RuntimeError("fail"))):
        with capture_logs() as logs:
            result = await client.bulk_create_users(
                [{"name": f"u{i}"} for i in range(MAX_LOGGED_FAILURE_DETAILS + 1)]
            )
    assert result == []
    warn = next((lg for lg in logs if lg.get("event") == "bulk_create_partial_failure"), None)
    assert warn is not None
    assert warn["failed_count"] == MAX_LOGGED_FAILURE_DETAILS + 1
    assert warn["success_count"] == 0
    assert warn["details_truncated"] is True
    assert len(warn["failed_details"]) == MAX_LOGGED_FAILURE_DETAILS
    detail = warn["failed_details"][0]
    assert "index" in detail
    assert "error_type" in detail
