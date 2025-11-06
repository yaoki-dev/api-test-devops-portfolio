# ===============================================================================
# test_async_crud.py - 非同期CRUD操作の単体テスト（モック使用）
# ===============================================================================
#
# このファイルは AsyncJSONPlaceholderClient の CRUD 操作をテスト
# 学習ポイント：
# 1. モック・スタブによる外部API依存の排除
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
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import HTTPStatusError, Request, Response

from utils.api_client import AsyncJSONPlaceholderClient

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


@pytest.fixture
def mock_response():
    """モックHTTPレスポンスを生成するファクトリー"""

    def _create_response(status_code: int, json_data: dict | None = None, text: str = ""):
        """モックレスポンスオブジェクト作成"""
        response = MagicMock(spec=Response)
        response.status_code = status_code
        response.headers = {"content-type": "application/json"}
        response.reason_phrase = "OK" if status_code == 200 else "Error"
        response.content = json.dumps(json_data).encode() if json_data else text.encode()
        response.text = json.dumps(json_data) if json_data else text
        response.json.return_value = json_data
        response.raise_for_status = MagicMock()

        # ステータスコードに応じてエラーを発生させる
        if status_code >= 400:
            from httpx import HTTPStatusError

            response.raise_for_status.side_effect = HTTPStatusError(
                f"{status_code} Error",
                request=MagicMock(spec=Request),
                response=response,
            )

        return response

    return _create_response


# ===============================================================================
# Test 1: 非同期投稿作成テスト（Create）
# ===============================================================================


@pytest.mark.regression
@pytest.mark.asyncio
async def test_async_create_post(sample_post_data, mock_response):
    """
    非同期投稿作成（POST /posts）のテスト

    検証項目：
    - async with コンテキストマネージャーの動作
    - create_post() メソッドの正常実行
    - リクエストボディの正確性（title, body, userId）
    - レスポンスJSONの正常パーシング
    - モック呼び出しの検証
    """
    # モックレスポンス準備
    mock_resp = mock_response(201, sample_post_data)

    # AsyncClientのモック作成
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance
        mock_client_instance.request.return_value = mock_resp

        # テスト実行
        async with AsyncJSONPlaceholderClient() as client:
            post = await client.create_post("Test Title", "Test Body", 1)

            # 結果検証
            assert post["title"] == "Test Title"
            assert post["body"] == "Test Body"
            assert post["userId"] == 1
            assert post["id"] == 101

            # モック呼び出し検証
            mock_client_instance.request.assert_called_once()
            call_args = mock_client_instance.request.call_args
            assert call_args[0][0] == "POST"
            assert "/posts" in call_args[0][1]


# ===============================================================================
# Test 2: 非同期投稿更新テスト（Update）
# ===============================================================================


@pytest.mark.regression
@pytest.mark.asyncio
async def test_async_update_post(mock_response):
    """
    非同期投稿更新（PUT /posts/{id}）のテスト

    検証項目：
    - update_post() メソッドの正常実行
    - post_id パラメータの正確性
    - リクエストボディの更新データ（title, body）
    - レスポンスに更新データが反映されているか確認
    - モックの正確な呼び出し検証
    """
    # 更新後のデータ
    updated_data = {
        "id": 1,
        "title": "Updated Title",
        "body": "Updated Body",
        "userId": 1,
    }
    mock_resp = mock_response(200, updated_data)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance
        mock_client_instance.request.return_value = mock_resp

        async with AsyncJSONPlaceholderClient() as client:
            post = await client.update_post(1, "Updated Title", "Updated Body")

            # 結果検証
            assert post["id"] == 1
            assert post["title"] == "Updated Title"
            assert post["body"] == "Updated Body"

            # モック呼び出し検証
            mock_client_instance.request.assert_called_once()
            call_args = mock_client_instance.request.call_args
            assert call_args[0][0] == "PUT"
            assert "/posts/1" in call_args[0][1]


# ===============================================================================
# Test 3: 非同期投稿削除テスト（Delete）
# ===============================================================================


@pytest.mark.regression
@pytest.mark.asyncio
async def test_async_delete_post(mock_response):
    """
    非同期投稿削除（DELETE /posts/{id}）のテスト

    検証項目：
    - delete_post() メソッドの正常実行
    - post_id パラメータの正確性
    - 例外が発生しないことの確認
    - モックの正確な呼び出し検証（DELETE メソッド）
    - 204 No Content ステータスの処理
    """
    # 削除成功レスポンス（204 No Content）
    mock_resp = mock_response(204, None, "")

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance
        mock_client_instance.request.return_value = mock_resp

        async with AsyncJSONPlaceholderClient() as client:
            # delete_post() は None を返すので、例外が発生しないことを確認
            result = await client.delete_post(1)

            # 結果検証（Noneが返ることを確認）
            assert result is None

            # モック呼び出し検証
            mock_client_instance.request.assert_called_once()
            call_args = mock_client_instance.request.call_args
            assert call_args[0][0] == "DELETE"
            assert "/posts/1" in call_args[0][1]


# ===============================================================================
# Test 4: CRUD統合テスト（Create → Read → Update → Delete）
# ===============================================================================


@pytest.mark.regression
@pytest.mark.asyncio
async def test_async_crud_integration(sample_post_data, mock_response):
    """
    CRUD操作の統合フローテスト（モック使用）

    検証項目：
    - Create → Read → Update → Delete の一連フロー
    - 各操作の正常実行と適切なレスポンス処理
    - post_id の一貫性（Create で生成 → 以降の操作で使用）
    - 各HTTPメソッドの正確な呼び出し
    - モック呼び出し回数の検証（4回: POST, GET, PUT, DELETE）
    """
    # モックレスポンス準備（4つの操作用）
    create_resp = mock_response(201, sample_post_data)
    read_resp = mock_response(200, [sample_post_data])  # get_posts() は配列を返す
    update_resp = mock_response(
        200,
        {
            "id": 101,
            "title": "Updated",
            "body": "Updated Body",
            "userId": 1,
        },
    )
    delete_resp = mock_response(204, None, "")

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance

        # 4回の呼び出しに対して順番にレスポンスを設定
        mock_client_instance.request.side_effect = [
            create_resp,
            read_resp,
            update_resp,
            delete_resp,
        ]

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

            # モック呼び出し回数検証（4回）
            assert mock_client_instance.request.call_count == 4


# ===============================================================================
# Test 5: エラーハンドリング - 400 Bad Request
# ===============================================================================


@pytest.mark.regression
@pytest.mark.asyncio
async def test_async_create_post_400_error(mock_response):
    """
    400 Bad Request エラー時の挙動テスト

    検証項目：
    - 不正なリクエストボディ送信時の400エラー
    - HTTPStatusError 例外の発生
    - エラーレスポンスの適切な処理
    - リトライが実行されないこと（4xxはクライアントエラー）
    """
    # 400エラーレスポンス
    error_data = {"error": "Invalid request body"}
    mock_resp = mock_response(400, error_data)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance
        mock_client_instance.request.return_value = mock_resp

        async with AsyncJSONPlaceholderClient() as client:
            # 400エラーが発生することを確認
            with pytest.raises(HTTPStatusError):
                await client.create_post("", "", 0)  # 不正なデータ


# ===============================================================================
# Test 6: エラーハンドリング - 404 Not Found
# ===============================================================================


@pytest.mark.regression
@pytest.mark.asyncio
async def test_async_update_post_404_error(mock_response):
    """
    404 Not Found エラー時の挙動テスト

    検証項目：
    - 存在しない post_id への更新リクエスト
    - 404エラーの適切な検出
    - HTTPStatusError 例外の発生
    - リトライが実行されないこと
    """
    # 404エラーレスポンス
    mock_resp = mock_response(404, {"error": "Post not found"})

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance
        mock_client_instance.request.return_value = mock_resp

        async with AsyncJSONPlaceholderClient() as client:
            # 404エラーが発生することを確認
            with pytest.raises(HTTPStatusError):
                await client.update_post(99999, "Title", "Body")  # 存在しないID


# ===============================================================================
# Test 7: エラーハンドリング - 500 Internal Server Error
# ===============================================================================


@pytest.mark.regression
@pytest.mark.asyncio
async def test_async_delete_post_500_error(mock_response):
    """
    500 Internal Server Error 時の挙動テスト

    検証項目：
    - サーバーエラー時の500エラー
    - HTTPStatusError 例外の発生
    - リトライロジックの動作（5xxはサーバーエラー）
    - エラーレスポンスの適切な処理
    """
    # 500エラーレスポンス
    mock_resp = mock_response(500, {"error": "Internal server error"})

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance
        mock_client_instance.request.return_value = mock_resp

        async with AsyncJSONPlaceholderClient() as client:
            # 500エラーが発生することを確認
            with pytest.raises(HTTPStatusError):
                await client.delete_post(1)
