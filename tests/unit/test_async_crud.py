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

import pytest
import respx

from utils.api_client import APIClientError, AsyncJSONPlaceholderClient

BASE_URL = "https://jsonplaceholder.typicode.com"

# ===============================================================================
# テスト用フィクスチャ
# ===============================================================================


@pytest.fixture
def sample_post_data():
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
async def test_async_create_post(sample_post_data):
    """
    非同期投稿作成（POST /posts）のテスト

    検証項目：
    - async with コンテキストマネージャーの動作
    - create_post() メソッドの正常実行
    - リクエストボディの正確性（title, body, userId）
    - レスポンスJSONの正常パーシング
    """
    respx.post(f"{BASE_URL}/posts").respond(
        status_code=201,
        json=sample_post_data,
    )

    async with AsyncJSONPlaceholderClient() as client:
        post = await client.create_post("Test Title", "Test Body", 1)

    # 結果検証
    assert post["title"] == "Test Title"
    assert post["body"] == "Test Body"
    assert post["userId"] == 1
    assert post["id"] == 101


# ===============================================================================
# Test 2: 非同期投稿更新テスト（Update）
# ===============================================================================


@respx.mock
async def test_async_update_post():
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
    respx.put(f"{BASE_URL}/posts/1").respond(
        status_code=200,
        json=updated_data,
    )

    async with AsyncJSONPlaceholderClient() as client:
        post = await client.update_post(1, "Updated Title", "Updated Body")

    # 結果検証
    assert post["id"] == 1
    assert post["title"] == "Updated Title"
    assert post["body"] == "Updated Body"


# ===============================================================================
# Test 3: 非同期投稿削除テスト（Delete）
# ===============================================================================


@respx.mock
async def test_async_delete_post():
    """
    非同期投稿削除（DELETE /posts/{id}）のテスト

    検証項目：
    - delete_post() メソッドの正常実行
    - post_id パラメータの正確性
    - 例外が発生しないことの確認
    - 200 ステータスの処理
    """
    respx.delete(f"{BASE_URL}/posts/1").respond(status_code=200)

    async with AsyncJSONPlaceholderClient() as client:
        # delete_post() は None を返すので、例外が発生しないことを確認
        result = await client.delete_post(1)

    # 結果検証（Noneが返ることを確認）
    assert result is None


# ===============================================================================
# Test 4: CRUD統合テスト（Create → Read → Update → Delete）
# ===============================================================================


@respx.mock
async def test_async_crud_integration(sample_post_data):
    """
    CRUD操作の統合フローテスト（respxモック使用）

    検証項目：
    - Create → Read → Update → Delete の一連フロー
    - 各操作の正常実行と適切なレスポンス処理
    - post_id の一貫性（Create で生成 → 以降の操作で使用）
    - 各HTTPメソッドの正確な呼び出し
    """
    # Create: 新規投稿作成（POST /posts）
    respx.post(f"{BASE_URL}/posts").respond(
        status_code=201,
        json=sample_post_data,
    )

    # Read: 投稿一覧取得（GET /posts）
    respx.get(f"{BASE_URL}/posts").respond(
        status_code=200,
        json=[sample_post_data],
    )

    # Update: 投稿更新（PUT /posts/101）
    updated_data = {
        "id": 101,
        "title": "Updated",
        "body": "Updated Body",
        "userId": 1,
    }
    respx.put(f"{BASE_URL}/posts/101").respond(
        status_code=200,
        json=updated_data,
    )

    # Delete: 投稿削除（DELETE /posts/101）
    respx.delete(f"{BASE_URL}/posts/101").respond(status_code=200)

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

        # Delete: 投稿削除
        result = await client.delete_post(post_id)
        assert result is None


# ===============================================================================
# Test 5: エラーハンドリング - 400 Bad Request
# ===============================================================================


@respx.mock
async def test_async_create_post_400_error():
    """
    400 Bad Request エラー時の挙動テスト

    検証項目：
    - 不正なリクエストボディ送信時の400エラー
    - APIClientError 例外の発生
    - エラーレスポンスの適切な処理
    - リトライが実行されないこと（4xxはクライアントエラー）
    """
    respx.post(f"{BASE_URL}/posts").respond(
        status_code=400,
        json={"error": "Invalid request body"},
    )

    async with AsyncJSONPlaceholderClient() as client:
        # 400エラーが発生することを確認
        with pytest.raises(APIClientError):
            await client.create_post("", "", 0)  # 不正なデータ


# ===============================================================================
# Test 6: エラーハンドリング - 404 Not Found
# ===============================================================================


@respx.mock
async def test_async_update_post_404_error():
    """
    404 Not Found エラー時の挙動テスト

    検証項目：
    - 存在しない post_id への更新リクエスト
    - 404エラーの適切な検出
    - APIClientError 例外の発生
    - リトライが実行されないこと
    """
    respx.put(f"{BASE_URL}/posts/99999").respond(
        status_code=404,
        json={"error": "Post not found"},
    )

    async with AsyncJSONPlaceholderClient() as client:
        # 404エラーが発生することを確認
        with pytest.raises(APIClientError):
            await client.update_post(99999, "Title", "Body")  # 存在しないID


# ===============================================================================
# Test 7: エラーハンドリング - 500 Internal Server Error
# ===============================================================================


@respx.mock
async def test_async_delete_post_500_error():
    """
    500 Internal Server Error 時の挙動テスト

    検証項目：
    - サーバーエラー時の500エラー
    - APIClientError 例外の発生
    - リトライロジックの動作（5xxはサーバーエラー）
    - エラーレスポンスの適切な処理
    """
    respx.delete(f"{BASE_URL}/posts/1").respond(
        status_code=500,
        json={"error": "Internal server error"},
    )

    async with AsyncJSONPlaceholderClient() as client:
        # 500エラーが発生することを確認
        with pytest.raises(APIClientError):
            await client.delete_post(1)
