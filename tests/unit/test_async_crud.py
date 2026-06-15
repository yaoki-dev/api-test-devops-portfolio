# ===============================================================================
# test_async_crud.py - 非同期CRUD操作の単体テスト（respxモック使用）
# ===============================================================================
#
# このファイルは AsyncJSONPlaceholderClient の CRUD 操作をテスト
# 学習ポイント：
# 1. respxによる外部API依存の排除（HTTPレベルモック）
# 2. 非同期CRUD操作（Create/Read/Update/Delete）のテスト
# 3. エラーハンドリングの検証（400/404/500）
# 4. 型ヒントとPydanticによる型安全性
#
# 実行方法：
#   pytest tests/unit/test_async_crud.py -v
#   pytest tests/unit/test_async_crud.py::test_async_create_post -v
#
# ===============================================================================

import json
from typing import TypedDict
from unittest.mock import Mock, patch

import pytest
import respx

from tests.constants import BASE_URL
from utils.api_client import APIHTTPError, APIRetryError, AsyncJSONPlaceholderClient

pytestmark = pytest.mark.unit

# ===============================================================================
# テスト用フィクスチャ
# ===============================================================================


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


# ===============================================================================
# Test 1: 非同期投稿作成テスト（Create）
# ===============================================================================


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
    assert post["title"] == "Test Title"
    assert post["body"] == "Test Body"
    assert post["userId"] == 1
    assert post["id"] == 101


# ===============================================================================
# Test 2: 非同期投稿更新テスト（Update）
# ===============================================================================


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


# ===============================================================================
# Test 3: 非同期投稿削除テスト（Delete）
# ===============================================================================


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


# ===============================================================================
# Test 4: CRUD統合テスト（Create → Read → Update → Delete）
# ===============================================================================


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
        post_id = post["id"]
        assert post_id == 101
        assert post["title"] == "Test Title"

        # Read: 投稿一覧取得（user_id=1）
        retrieved_posts = await client.get_posts(limit=None)
        assert len(retrieved_posts) > 0
        assert retrieved_posts[0]["id"] == post_id

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


# ===============================================================================
# Test 5: エラーハンドリング - 400 Bad Request
# ===============================================================================


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


# ===============================================================================
# Test 6: エラーハンドリング - 404 Not Found
# ===============================================================================


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


# ===============================================================================
# Test 7: エラーハンドリング - 500 Internal Server Error
# ===============================================================================


@respx.mock
@patch("utils.api_client.exponential_backoff_with_jitter", return_value=0.0)
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
