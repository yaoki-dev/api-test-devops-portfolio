"""
AsyncAPIClient エラーハンドリングテスト

Note:
    test_sync_client_error_handling.py と対称構造で設計。
    責務: リトライロジック + 例外ハンドリングの検証

テストケース一覧（15件）:
    - Exception (3件): hierarchy, http_error_status_preservation, retry_error_message
    - Retry (3件): server_error_then_success, exhausted, 4xx_no_retry
    - Timeout (2件): timeout_error_retry, timeout_then_success
    - Connection (2件): connection_error_retry, connection_then_success
    - Mixed Errors (2件): mixed_then_success, mixed_exhaust_retries
    - HTTP Methods (3件): post_with_retry, put_4xx_no_retry, delete_with_retry
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

# Module-level marker: All tests in this file are unit tests
pytestmark = pytest.mark.unit


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


def test_async_exception_hierarchy() -> None:
    """例外クラスの継承関係確認"""
    assert issubclass(APIConnectionError, APIClientError)
    assert issubclass(APITimeoutError, APIClientError)
    assert issubclass(APIHTTPError, APIClientError)
    assert issubclass(APIRetryError, APIClientError)
    assert issubclass(APIClientError, Exception)


def test_async_http_error_status_preservation() -> None:
    """APIHTTPError がステータスコードを保持することを確認"""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 404

    error = APIHTTPError("Not Found", status_code=404, response=mock_response)

    assert error.status_code == 404
    assert error.response == mock_response
    assert str(error) == "Not Found"


def test_async_retry_error_message() -> None:
    """APIRetryError のメッセージ確認"""
    error = APIRetryError("Max retries exceeded")
    assert str(error) == "Max retries exceeded"


# =============================================================================
# Retry Logic Tests（条件2: エラーパス）
# =============================================================================


@pytest.mark.asyncio
async def test_async_retry_on_server_error_then_success(mock_httpx_async_client: Mock) -> None:
    """サーバーエラー後に成功するケース（5xxはリトライ対象）"""
    error_response = create_mock_response(500)
    error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 Internal Server Error",
        request=Mock(spec=httpx.Request),
        response=error_response,
    )

    success_response = create_mock_response(200, json_data={"id": 1, "title": "test"})
    success_response.raise_for_status.return_value = None

    mock_httpx_async_client.request = AsyncMock(
        side_effect=[error_response, error_response, success_response],
    )

    async with AsyncAPIClient(retry_count=3, retry_delay=0.01) as client:
        client._client = mock_httpx_async_client
        response = await client.get("/posts/1")

        assert mock_httpx_async_client.request.call_count == 3
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_async_retry_exhausted(mock_httpx_async_client: Mock) -> None:
    """リトライ上限でAPIRetryErrorが発生することを確認（5xxのみリトライ）"""
    error_response = create_mock_response(500)
    error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 Internal Server Error",
        request=Mock(spec=httpx.Request),
        response=error_response,
    )

    mock_httpx_async_client.request = AsyncMock(return_value=error_response)

    async with AsyncAPIClient(retry_count=2, retry_delay=0.01) as client:
        client._client = mock_httpx_async_client

        with pytest.raises(APIRetryError) as exc_info:
            await client.get("/posts/1")

        # リトライ回数+1回（初回+リトライ2回=3回）実行されたことを確認
        assert mock_httpx_async_client.request.call_count == 3
        assert "failed after" in str(exc_info.value)


@pytest.mark.asyncio
async def test_async_4xx_error_no_retry(mock_httpx_async_client: Mock) -> None:
    """4xxクライアントエラーはリトライせず即座にAPIHTTPErrorを発生"""
    error_response = create_mock_response(404)
    error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404 Not Found",
        request=Mock(spec=httpx.Request),
        response=error_response,
    )

    mock_httpx_async_client.request = AsyncMock(return_value=error_response)

    async with AsyncAPIClient(retry_count=3, retry_delay=0.01) as client:
        client._client = mock_httpx_async_client

        with pytest.raises(APIHTTPError) as exc_info:
            await client.get("/posts/999")

        # 4xxエラーはリトライしない（1回のみ実行）
        assert mock_httpx_async_client.request.call_count == 1
        assert exc_info.value.status_code == 404


# =============================================================================
# Timeout Tests（条件2: エラーパス）
# =============================================================================


@pytest.mark.asyncio
async def test_async_timeout_error_retry(mock_httpx_async_client: Mock) -> None:
    """タイムアウト時にAPIRetryErrorが発生することを確認"""
    mock_httpx_async_client.request = AsyncMock(
        side_effect=httpx.TimeoutException("Request timed out"),
    )

    async with AsyncAPIClient(retry_count=1, retry_delay=0.01) as client:
        client._client = mock_httpx_async_client

        with pytest.raises(APIRetryError) as exc_info:
            await client.get("/posts/1")

        # リトライが実行されることを確認（初回+リトライ1回=2回）
        assert mock_httpx_async_client.request.call_count == 2
        assert isinstance(exc_info.value.__cause__, APITimeoutError)


@pytest.mark.asyncio
async def test_async_timeout_then_success(mock_httpx_async_client: Mock) -> None:
    """タイムアウト後に成功するケース"""
    success_response = Mock(spec=httpx.Response)
    success_response.status_code = 200
    success_response.json.return_value = {"id": 1}
    success_response.raise_for_status.return_value = None

    mock_httpx_async_client.request = AsyncMock(
        side_effect=[
            httpx.TimeoutException("Timeout 1"),
            success_response,
        ],
    )

    async with AsyncAPIClient(retry_count=2, retry_delay=0.01) as client:
        client._client = mock_httpx_async_client
        response = await client.get("/posts/1")

        assert mock_httpx_async_client.request.call_count == 2
        assert response.status_code == 200


# =============================================================================
# Connection Tests（条件2: エラーパス）
# =============================================================================


@pytest.mark.asyncio
async def test_async_connection_error_retry(mock_httpx_async_client: Mock) -> None:
    """接続エラー時にAPIRetryErrorが発生することを確認"""
    mock_httpx_async_client.request = AsyncMock(
        side_effect=httpx.ConnectError("Connection refused"),
    )

    async with AsyncAPIClient(retry_count=1, retry_delay=0.01) as client:
        client._client = mock_httpx_async_client

        with pytest.raises(APIRetryError) as exc_info:
            await client.get("/posts/1")

        assert mock_httpx_async_client.request.call_count == 2
        assert isinstance(exc_info.value.__cause__, APIConnectionError)


@pytest.mark.asyncio
async def test_async_connection_then_success(mock_httpx_async_client: Mock) -> None:
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
        ],
    )

    async with AsyncAPIClient(retry_count=3, retry_delay=0.01) as client:
        client._client = mock_httpx_async_client
        response = await client.get("/posts/1")

        assert mock_httpx_async_client.request.call_count == 3
        assert response.status_code == 200


# =============================================================================
# Mixed Errors Tests（条件2: エラーパス）
# =============================================================================


@pytest.mark.asyncio
async def test_async_mixed_errors_then_success(mock_httpx_async_client: Mock) -> None:
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
        ],
    )

    async with AsyncAPIClient(retry_count=3, retry_delay=0.01) as client:
        client._client = mock_httpx_async_client
        response = await client.get("/posts/1")

        assert mock_httpx_async_client.request.call_count == 3
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_async_mixed_errors_exhaust_retries(mock_httpx_async_client: Mock) -> None:
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
        ],
    )

    async with AsyncAPIClient(retry_count=2, retry_delay=0.01) as client:
        client._client = mock_httpx_async_client

        with pytest.raises(APIRetryError):
            await client.get("/posts/1")

        assert mock_httpx_async_client.request.call_count == 3


# =============================================================================
# HTTP Methods Tests（条件2: エラーパス）
# =============================================================================


@pytest.mark.asyncio
async def test_async_post_with_retry(mock_httpx_async_client: Mock) -> None:
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

    async with AsyncAPIClient(retry_count=2, retry_delay=0.01) as client:
        client._client = mock_httpx_async_client
        response = await client.post(
            "/posts",
            json={"title": "test", "body": "content", "userId": 1},
        )

        assert mock_httpx_async_client.request.call_count == 2
        assert response.status_code == 201


@pytest.mark.asyncio
async def test_async_put_4xx_no_retry(mock_httpx_async_client: Mock) -> None:
    """PUTリクエストで4xxエラーはリトライせず即座にAPIHTTPErrorを発生"""
    error_response = create_mock_response(400)
    error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "400 Bad Request",
        request=Mock(spec=httpx.Request),
        response=error_response,
    )

    mock_httpx_async_client.request = AsyncMock(return_value=error_response)

    async with AsyncAPIClient(retry_count=3, retry_delay=0.01) as client:
        client._client = mock_httpx_async_client

        with pytest.raises(APIHTTPError) as exc_info:
            await client.put("/posts/1", json={"title": "updated"})

        # 4xxエラーはリトライしない（1回のみ実行）
        assert mock_httpx_async_client.request.call_count == 1
        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_async_delete_with_retry(mock_httpx_async_client: Mock) -> None:
    """DELETEリクエストのリトライ動作確認"""
    success_response = Mock(spec=httpx.Response)
    success_response.status_code = 200
    success_response.raise_for_status.return_value = None

    mock_httpx_async_client.request = AsyncMock(
        side_effect=[
            httpx.TimeoutException("Timeout"),
            success_response,
        ],
    )

    async with AsyncAPIClient(retry_count=2, retry_delay=0.01) as client:
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
# 5. 関数構造テスト設計:
#    - フラットな関数構造で可読性向上
#    - セクションコメントで論理グループ化
#    - Async/Sync対称構造を維持
# =============================================================================
