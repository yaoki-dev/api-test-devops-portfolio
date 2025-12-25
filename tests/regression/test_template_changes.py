"""
テンプレート変更検出回帰テスト

学習目標:
- AsyncAPIClientの動作が過去の仕様と一貫していることを検証
- API応答テンプレートの変更を検出
- 既存機能の後方互換性を保証
- リグレッション防止パターンの理解
"""

from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from utils.api_client import AsyncAPIClient


class TestAsyncClientBasicBehavior:
    """AsyncAPIClientの基本動作回帰テスト"""

    @pytest.mark.asyncio
    async def test_async_client_initialization(self):
        """非同期クライアント初期化の一貫性確認"""
        async with AsyncAPIClient(
            base_url="https://test.com", timeout=10.0, retry_count=1
        ) as client:
            assert client.base_url == "https://test.com"
            assert client.timeout == 10.0
            assert client.retry_count == 1
            assert "User-Agent" in client.default_headers
            assert client._client is not None

    @pytest.mark.asyncio
    async def test_context_manager_lifecycle(self):
        """コンテキストマネージャーのライフサイクル一貫性"""
        client = AsyncAPIClient(base_url="https://test.com")

        # 現在の設計: __init__で_clientが初期化される
        # (以前の設計: __aenter__で初期化 → 現在は__init__で初期化)
        assert client._client is not None
        assert isinstance(client._client, httpx.AsyncClient)

        async with client:
            # __aenter__後: _clientは引き続き有効
            assert client._client is not None
            assert isinstance(client._client, httpx.AsyncClient)

        # __aexit__後: _clientは閉じられる
        # 注: httpx.AsyncClient.aclose()は_clientをNoneにしないが、transportを閉じる


class TestAsyncClientRetryBehavior:
    """リトライロジックの回帰テスト"""

    @pytest.mark.asyncio
    async def test_retry_on_server_error_then_success(self, mock_httpx_client):
        """5xxサーバーエラー後の成功パターン（既知の動作確認）"""
        error_response = Mock(spec=httpx.Response)
        error_response.status_code = 500
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=Mock(),
            response=error_response,
        )

        success_response = Mock(spec=httpx.Response)
        success_response.status_code = 200
        success_response.json.return_value = {"id": 1, "title": "test"}
        success_response.raise_for_status.return_value = None

        mock_httpx_client.request = AsyncMock(
            side_effect=[error_response, error_response, success_response]
        )

        async with AsyncAPIClient(retry_count=3, retry_delay=0.1) as client:
            client._client = mock_httpx_client
            response = await client.get("/posts/1")

            # リトライが3回実行されたことを確認（既知の動作）
            assert mock_httpx_client.request.call_count == 3
            # 最終的に成功レスポンスを取得
            assert response.status_code == 200
            assert response.json() == {"id": 1, "title": "test"}

    @pytest.mark.asyncio
    async def test_timeout_then_success(self, mock_httpx_client):
        """タイムアウト後の成功パターン（既知の動作確認）"""
        success_response = Mock(spec=httpx.Response)
        success_response.status_code = 200
        success_response.json.return_value = {"id": 1}
        success_response.raise_for_status.return_value = None

        mock_httpx_client.request = AsyncMock(
            side_effect=[
                httpx.TimeoutException("Timeout 1"),
                success_response,
            ]
        )

        async with AsyncAPIClient(retry_count=2, retry_delay=0.1) as client:
            client._client = mock_httpx_client
            response = await client.get("/posts/1")

            # 2回実行されたことを確認（既知の動作）
            assert mock_httpx_client.request.call_count == 2
            # 最終的に成功
            assert response.status_code == 200


class TestAsyncClientHTTPMethods:
    """HTTPメソッドの回帰テスト"""

    @pytest.mark.asyncio
    async def test_get_request_signature(self, mock_httpx_client):
        """GETリクエストのシグネチャ一貫性"""
        success_response = Mock(spec=httpx.Response)
        success_response.status_code = 200
        success_response.json.return_value = {"id": 1}
        success_response.raise_for_status.return_value = None

        mock_httpx_client.request = AsyncMock(return_value=success_response)

        async with AsyncAPIClient() as client:
            client._client = mock_httpx_client
            await client.get("/posts/1", params={"filter": "active"})

            # リクエストが正しく呼び出されたことを確認
            assert mock_httpx_client.request.call_count == 1
            call_args = mock_httpx_client.request.call_args

            # メソッドとURLが正しい
            assert call_args[0][0] == "GET"
            assert call_args[0][1] == "/posts/1"

            # paramsが正しく渡されている
            assert call_args[1]["params"] == {"filter": "active"}

    @pytest.mark.asyncio
    async def test_post_request_signature(self, mock_httpx_client):
        """POSTリクエストのシグネチャ一貫性"""
        success_response = Mock(spec=httpx.Response)
        success_response.status_code = 201
        success_response.json.return_value = {"id": 101, "title": "created"}
        success_response.raise_for_status.return_value = None

        mock_httpx_client.request = AsyncMock(return_value=success_response)

        async with AsyncAPIClient() as client:
            client._client = mock_httpx_client
            await client.post("/posts", json={"title": "test", "body": "content"})

            # リクエストが正しく呼び出されたことを確認
            assert mock_httpx_client.request.call_count == 1
            call_args = mock_httpx_client.request.call_args

            # メソッドとURLが正しい
            assert call_args[0][0] == "POST"
            assert call_args[0][1] == "/posts"

            # jsonが正しく渡されている
            assert call_args[1]["json"] == {"title": "test", "body": "content"}

    @pytest.mark.asyncio
    async def test_put_request_signature(self, mock_httpx_client):
        """PUTリクエストのシグネチャ一貫性"""
        success_response = Mock(spec=httpx.Response)
        success_response.status_code = 200
        success_response.json.return_value = {"id": 1, "title": "updated"}
        success_response.raise_for_status.return_value = None

        mock_httpx_client.request = AsyncMock(return_value=success_response)

        async with AsyncAPIClient() as client:
            client._client = mock_httpx_client
            await client.put("/posts/1", json={"title": "updated"})

            # リクエストが正しく呼び出されたことを確認
            assert mock_httpx_client.request.call_count == 1
            call_args = mock_httpx_client.request.call_args

            # メソッドとURLが正しい
            assert call_args[0][0] == "PUT"
            assert call_args[0][1] == "/posts/1"

    @pytest.mark.asyncio
    async def test_delete_request_signature(self, mock_httpx_client):
        """DELETEリクエストのシグネチャ一貫性"""
        success_response = Mock(spec=httpx.Response)
        success_response.status_code = 200
        success_response.raise_for_status.return_value = None

        mock_httpx_client.request = AsyncMock(return_value=success_response)

        async with AsyncAPIClient() as client:
            client._client = mock_httpx_client
            await client.delete("/posts/1")

            # リクエストが正しく呼び出されたことを確認
            assert mock_httpx_client.request.call_count == 1
            call_args = mock_httpx_client.request.call_args

            # メソッドとURLが正しい
            assert call_args[0][0] == "DELETE"
            assert call_args[0][1] == "/posts/1"


class TestAsyncClientHeaderHandling:
    """ヘッダー処理の回帰テスト"""

    @pytest.mark.asyncio
    async def test_default_headers_always_present(self):
        """デフォルトヘッダーが常に存在することを確認"""
        async with AsyncAPIClient(base_url="https://test.com") as client:
            assert "Accept" in client.default_headers
            assert client.default_headers["Accept"] == "application/json"
            assert "User-Agent" in client.default_headers

    @pytest.mark.asyncio
    async def test_custom_headers_preserved(self):
        """カスタムヘッダーが保持されることを確認"""
        custom_headers = {
            "X-Custom-Header": "Value",
            "X-API-Key": "secret",
        }

        async with AsyncAPIClient(base_url="https://test.com", headers=custom_headers) as client:
            assert client.default_headers["X-Custom-Header"] == "Value"
            assert client.default_headers["X-API-Key"] == "secret"
            # デフォルトヘッダーも保持されている
            assert client.default_headers["Accept"] == "application/json"


# =============================================================================
# 学習ポイント:
#
# 1. リグレッションテストの目的:
#    - 過去に動作していた機能が現在も同じように動作することを保証
#    - コード変更によるバグ混入を早期に検出
#    - APIの後方互換性を維持
#
# 2. テストパターン:
#    - 基本動作確認: 初期化、ライフサイクル
#    - リトライロジック: エラー回復パターンの一貫性
#    - HTTPメソッド: GET/POST/PUT/DELETEのシグネチャ確認
#    - ヘッダー処理: デフォルトヘッダーとカスタムヘッダーの保持
#
# 3. モックの活用:
#    - mock_httpx_clientフィクスチャで外部依存を排除
#    - call_argsでメソッドシグネチャを検証
#    - side_effectで複数回の動作をシミュレーション
#
# 4. 既知のバグの記録:
#    - 4xxエラーもリトライされる問題（実装バグ）
#    - リグレッションテストで既知の動作を記録することで、
#      意図しない変更を検出可能
#
# 5. 保守性の向上:
#    - テストクラスで機能領域を分類
#    - @pytest.mark.regressionで識別容易
#    - 既知の動作をドキュメント化
# =============================================================================
