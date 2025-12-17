"""
AsyncAPIClient エラーハンドリングテスト

学習目標:
- カスタム例外クラスの動作検証
- リトライロジックの実装確認
- エラーシナリオの網羅的テスト
- エラー回復パターンの理解
"""

from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from tests.conftest import create_mock_response
from utils.api_client import (
    APIClientError,
    APIConnectionError,
    APIHTTPError,
    APIRetryError,
    APITimeoutError,
    AsyncAPIClient,
)


class TestAsyncClientExceptions:
    """カスタム例外クラスのテスト"""

    def test_api_client_error_hierarchy(self):
        """例外クラスの継承関係確認"""
        # APIClientError が基底クラス
        assert issubclass(APIConnectionError, APIClientError)
        assert issubclass(APITimeoutError, APIClientError)
        assert issubclass(APIHTTPError, APIClientError)
        assert issubclass(APIRetryError, APIClientError)

    def test_api_http_error_with_status_code(self):
        """APIHTTPError がステータスコードを保持することを確認"""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 404

        error = APIHTTPError("Not Found", status_code=404, response=mock_response)

        assert error.status_code == 404
        assert error.response == mock_response
        assert str(error) == "Not Found"

    def test_api_retry_error_message(self):
        """APIRetryError のメッセージ確認"""
        error = APIRetryError("Max retries exceeded")
        assert str(error) == "Max retries exceeded"


class TestAsyncClientRetryLogic:
    """リトライロジックのテスト"""

    @pytest.mark.asyncio
    async def test_retry_on_server_error_then_success(self, mock_httpx_async_client):
        """サーバーエラー後に成功するケース（5xxはリトライ対象）"""
        # 最初の2回は500エラー、3回目で成功
        error_response = create_mock_response(500)
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=Mock(spec=httpx.Request),
            response=error_response,
        )

        success_response = create_mock_response(200, json_data={"id": 1, "title": "test"})
        success_response.raise_for_status.return_value = None

        mock_httpx_async_client.request = AsyncMock(
            side_effect=[error_response, error_response, success_response]
        )

        async with AsyncAPIClient() as client:
            client._client = mock_httpx_async_client
            response = await client.get("/posts/1")

            # 3回リクエストが実行されたことを確認
            assert mock_httpx_async_client.request.call_count == 3
            # 最終的に成功レスポンスを取得
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises_retry_error(self, mock_httpx_async_client):
        """リトライ上限でAPIRetryErrorが発生することを確認（5xxのみリトライ）"""
        error_response = create_mock_response(500)
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=Mock(spec=httpx.Request),
            response=error_response,
        )

        mock_httpx_async_client.request = AsyncMock(return_value=error_response)

        async with AsyncAPIClient(retry_count=2) as client:
            client._client = mock_httpx_async_client

            with pytest.raises(APIRetryError) as exc_info:
                await client.get("/posts/1")

            # リトライ回数+1回（初回+リトライ2回=3回）実行されたことを確認
            assert mock_httpx_async_client.request.call_count == 3
            assert "failed after" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_client_error_no_retry(self, mock_httpx_async_client):
        """4xxクライアントエラーはリトライせず即座にAPIHTTPErrorを発生

        4xxエラーはクライアント側の問題（リクエスト不正、認証失敗等）のため
        リトライしても結果は変わらない。即座にAPIHTTPErrorを発生させる。
        """
        error_response = create_mock_response(404)
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found",
            request=Mock(spec=httpx.Request),
            response=error_response,
        )

        mock_httpx_async_client.request = AsyncMock(return_value=error_response)

        async with AsyncAPIClient(retry_count=3) as client:
            client._client = mock_httpx_async_client

            with pytest.raises(APIHTTPError) as exc_info:
                await client.get("/posts/999")

            # 4xxエラーはリトライしない（1回のみ実行）
            assert mock_httpx_async_client.request.call_count == 1
            # ステータスコードが保持されていることを確認
            assert exc_info.value.status_code == 404


class TestAsyncClientTimeoutHandling:
    """タイムアウトエラーのテスト"""

    @pytest.mark.asyncio
    async def test_timeout_error_raised(self, mock_httpx_async_client):
        """タイムアウト時にAPIRetryErrorが発生することを確認"""
        mock_httpx_async_client.request = AsyncMock(
            side_effect=httpx.TimeoutException("Request timed out")
        )

        async with AsyncAPIClient(retry_count=1, retry_delay=0.1) as client:
            client._client = mock_httpx_async_client

            with pytest.raises(APIRetryError) as exc_info:
                await client.get("/posts/1")

            # リトライが実行されることを確認（初回+リトライ1回=2回）
            assert mock_httpx_async_client.request.call_count == 2
            # 元のタイムアウトエラーがチェーンされていることを確認
            assert isinstance(exc_info.value.__cause__, APITimeoutError)
            assert "timeout" in str(exc_info.value.__cause__).lower()

    @pytest.mark.asyncio
    async def test_timeout_then_success(self, mock_httpx_async_client):
        """タイムアウト後に成功するケース"""
        success_response = Mock(spec=httpx.Response)
        success_response.status_code = 200
        success_response.json.return_value = {"id": 1}
        success_response.raise_for_status.return_value = None

        mock_httpx_async_client.request = AsyncMock(
            side_effect=[
                httpx.TimeoutException("Timeout 1"),
                success_response,
            ]
        )

        async with AsyncAPIClient(retry_count=2, retry_delay=0.1) as client:
            client._client = mock_httpx_async_client
            response = await client.get("/posts/1")

            # 2回実行されたことを確認
            assert mock_httpx_async_client.request.call_count == 2
            # 最終的に成功
            assert response.status_code == 200


class TestAsyncClientConnectionHandling:
    """接続エラーのテスト"""

    @pytest.mark.asyncio
    async def test_connection_error_raised(self, mock_httpx_async_client):
        """接続エラー時にAPIRetryErrorが発生することを確認"""
        mock_httpx_async_client.request = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        async with AsyncAPIClient(retry_count=1, retry_delay=0.1) as client:
            client._client = mock_httpx_async_client

            with pytest.raises(APIRetryError) as exc_info:
                await client.get("/posts/1")

            # リトライが実行されることを確認
            assert mock_httpx_async_client.request.call_count == 2
            # 元の接続エラーがチェーンされていることを確認
            assert isinstance(exc_info.value.__cause__, APIConnectionError)
            assert "connection" in str(exc_info.value.__cause__).lower()

    @pytest.mark.asyncio
    async def test_connection_error_then_success(self, mock_httpx_async_client):
        """接続エラー後に成功するケース"""
        success_response = Mock(spec=httpx.Response)
        success_response.status_code = 200
        success_response.json.return_value = {"id": 1}
        success_response.raise_for_status.return_value = None

        mock_httpx_async_client.request = AsyncMock(
            side_effect=[
                httpx.ConnectError("Connection 1"),
                httpx.ConnectError("Connection 2"),
                success_response,
            ]
        )

        async with AsyncAPIClient(retry_count=3, retry_delay=0.1) as client:
            client._client = mock_httpx_async_client
            response = await client.get("/posts/1")

            # 3回実行されたことを確認
            assert mock_httpx_async_client.request.call_count == 3
            # 最終的に成功
            assert response.status_code == 200


class TestAsyncClientMixedErrors:
    """複数のエラータイプが混在するケース"""

    @pytest.mark.asyncio
    async def test_timeout_then_server_error_then_success(self, mock_httpx_async_client):
        """タイムアウト→サーバーエラー→成功のシナリオ"""
        server_error = create_mock_response(503)
        server_error.raise_for_status.side_effect = httpx.HTTPStatusError(
            "503 Service Unavailable",
            request=Mock(spec=httpx.Request),
            response=server_error,
        )

        success_response = create_mock_response(200, json_data={"id": 1})
        success_response.raise_for_status.return_value = None

        mock_httpx_async_client.request = AsyncMock(
            side_effect=[
                httpx.TimeoutException("Timeout"),
                server_error,
                success_response,
            ]
        )

        async with AsyncAPIClient(retry_count=3, retry_delay=0.1) as client:
            client._client = mock_httpx_async_client
            response = await client.get("/posts/1")

            # 3回実行されたことを確認
            assert mock_httpx_async_client.request.call_count == 3
            # 最終的に成功
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_mixed_errors_exhaust_retries(self, mock_httpx_async_client):
        """複数のエラータイプでリトライ上限に達するケース"""
        server_error = create_mock_response(500)
        server_error.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=Mock(spec=httpx.Request),
            response=server_error,
        )

        mock_httpx_async_client.request = AsyncMock(
            side_effect=[
                httpx.TimeoutException("Timeout"),
                httpx.ConnectError("Connection failed"),
                server_error,
            ]
        )

        async with AsyncAPIClient(retry_count=2, retry_delay=0.1) as client:
            client._client = mock_httpx_async_client

            with pytest.raises(APIRetryError):
                await client.get("/posts/1")

            # 3回実行されたことを確認（初回+リトライ2回）
            assert mock_httpx_async_client.request.call_count == 3


class TestAsyncClientHTTPMethods:
    """各HTTPメソッドのエラーハンドリング"""

    @pytest.mark.asyncio
    async def test_post_with_retry(self, mock_httpx_async_client):
        """POSTリクエストのリトライ動作確認（5xxはリトライ対象）"""
        server_error = create_mock_response(502)
        server_error.raise_for_status.side_effect = httpx.HTTPStatusError(
            "502 Bad Gateway",
            request=Mock(spec=httpx.Request),
            response=server_error,
        )

        success_response = create_mock_response(201, json_data={"id": 101, "title": "created"})
        success_response.raise_for_status.return_value = None

        mock_httpx_async_client.request = AsyncMock(side_effect=[server_error, success_response])

        async with AsyncAPIClient(retry_count=2, retry_delay=0.1) as client:
            client._client = mock_httpx_async_client
            response = await client.post(
                "/posts", json={"title": "test", "body": "content", "userId": 1}
            )

            assert mock_httpx_async_client.request.call_count == 2
            assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_put_with_client_error_no_retry(self, mock_httpx_async_client):
        """PUTリクエストで4xxエラーはリトライせず即座にAPIHTTPErrorを発生

        4xxエラーはクライアント側の問題（リクエスト不正、バリデーションエラー等）
        のためリトライしても結果は変わらない。即座にAPIHTTPErrorを発生させる。
        """
        error_response = create_mock_response(400)
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "400 Bad Request",
            request=Mock(spec=httpx.Request),
            response=error_response,
        )

        mock_httpx_async_client.request = AsyncMock(return_value=error_response)

        async with AsyncAPIClient(retry_count=3) as client:
            client._client = mock_httpx_async_client

            with pytest.raises(APIHTTPError) as exc_info:
                await client.put("/posts/1", json={"title": "updated"})

            # 4xxエラーはリトライしない（1回のみ実行）
            assert mock_httpx_async_client.request.call_count == 1
            # ステータスコードが保持されていることを確認
            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_with_retry(self, mock_httpx_async_client):
        """DELETEリクエストのリトライ動作確認"""
        success_response = Mock(spec=httpx.Response)
        success_response.status_code = 200
        success_response.raise_for_status.return_value = None

        mock_httpx_async_client.request = AsyncMock(
            side_effect=[
                httpx.TimeoutException("Timeout"),
                success_response,
            ]
        )

        async with AsyncAPIClient(retry_count=2, retry_delay=0.1) as client:
            client._client = mock_httpx_async_client
            response = await client.delete("/posts/1")

            assert mock_httpx_async_client.request.call_count == 2
            assert response.status_code == 200


# =============================================================================
# 学習ポイント:
#
# 1. カスタム例外クラス設計:
#    - 例外の継承関係による階層的エラー処理
#    - 追加情報（ステータスコード、レスポンス）の保持
#    - エラーメッセージの意味的な分類
#
# 2. リトライロジック実装パターン:
#    - サーバーエラー（5xx）はリトライ対象
#    - クライアントエラー（4xx）はリトライしない
#    - タイムアウト・接続エラーはリトライ対象
#    - リトライ上限でAPIRetryErrorを発生
#
# 3. エラー回復戦略:
#    - 一時的なエラーからの自動回復
#    - リトライ間隔の設定（exponential backoffも可能）
#    - 最終的なエラーハンドリング（リトライ失敗時）
#
# 4. テストでのモック活用:
#    - side_effectによる複数回の動作シミュレーション
#    - call_countによるリトライ回数検証
#    - 例外の適切な検証（pytest.raises）
#
# 5. 実用的なエラーハンドリング:
#    - ユーザーに適切なエラー情報を提供
#    - 本番環境での信頼性向上
#    - デバッグ・トラブルシューティングの容易化
# =============================================================================
