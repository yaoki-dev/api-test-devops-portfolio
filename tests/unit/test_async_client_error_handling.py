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

from unittest.mock import Mock

import httpx
import pytest
import respx

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

BASE_URL = "https://jsonplaceholder.typicode.com"


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


@respx.mock
async def test_async_retry_on_server_error_then_success() -> None:
    """サーバーエラー後に成功するケース（5xxはリトライ対象）"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(500),
        httpx.Response(200, json={"id": 1, "title": "test"}),
    ]

    async with AsyncAPIClient(retry_count=3, retry_delay=0.01) as client:
        response = await client.get("/posts/1")

    assert route.call_count == 3
    assert response.status_code == 200


@respx.mock
async def test_async_retry_exhausted() -> None:
    """リトライ上限でAPIRetryErrorが発生することを確認（5xxのみリトライ）"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(500),
        httpx.Response(500),
    ]

    async with AsyncAPIClient(retry_count=2, retry_delay=0.01) as client:
        with pytest.raises(APIRetryError) as exc_info:
            await client.get("/posts/1")

    # リトライ回数+1回（初回+リトライ2回=3回）実行されたことを確認
    assert route.call_count == 3
    assert "failed after" in str(exc_info.value)


@respx.mock
async def test_async_4xx_error_no_retry() -> None:
    """4xxクライアントエラーはリトライせず即座にAPIHTTPErrorを発生"""
    route = respx.get(f"{BASE_URL}/posts/999")
    route.side_effect = [
        httpx.Response(404),
    ]

    async with AsyncAPIClient(retry_count=3, retry_delay=0.01) as client:
        with pytest.raises(APIHTTPError) as exc_info:
            await client.get("/posts/999")

    # 4xxエラーはリトライしない（1回のみ実行）
    assert route.call_count == 1
    assert exc_info.value.status_code == 404


# =============================================================================
# Timeout Tests（条件2: エラーパス）
# =============================================================================


@respx.mock
async def test_async_timeout_error_retry() -> None:
    """タイムアウト時にAPIRetryErrorが発生することを確認"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.TimeoutException("Request timed out"),
        httpx.TimeoutException("Request timed out"),
    ]

    async with AsyncAPIClient(retry_count=1, retry_delay=0.01) as client:
        with pytest.raises(APIRetryError) as exc_info:
            await client.get("/posts/1")

    # リトライが実行されることを確認（初回+リトライ1回=2回）
    assert route.call_count == 2
    assert isinstance(exc_info.value.__cause__, APITimeoutError)


@respx.mock
async def test_async_timeout_then_success() -> None:
    """タイムアウト後に成功するケース"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.TimeoutException("Timeout 1"),
        httpx.Response(200, json={"id": 1}),
    ]

    async with AsyncAPIClient(retry_count=2, retry_delay=0.01) as client:
        response = await client.get("/posts/1")

    assert route.call_count == 2
    assert response.status_code == 200


# =============================================================================
# Connection Tests（条件2: エラーパス）
# =============================================================================


@respx.mock
async def test_async_connection_error_retry() -> None:
    """接続エラー時にAPIRetryErrorが発生することを確認"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.ConnectError("Connection refused"),
        httpx.ConnectError("Connection refused"),
    ]

    async with AsyncAPIClient(retry_count=1, retry_delay=0.01) as client:
        with pytest.raises(APIRetryError) as exc_info:
            await client.get("/posts/1")

    assert route.call_count == 2
    assert isinstance(exc_info.value.__cause__, APIConnectionError)


@respx.mock
async def test_async_connection_then_success() -> None:
    """接続エラー後に成功するケース"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.ConnectError("Connection 1"),
        httpx.ConnectError("Connection 2"),
        httpx.Response(200, json={"id": 1}),
    ]

    async with AsyncAPIClient(retry_count=3, retry_delay=0.01) as client:
        response = await client.get("/posts/1")

    assert route.call_count == 3
    assert response.status_code == 200


# =============================================================================
# Mixed Errors Tests（条件2: エラーパス）
# =============================================================================


@respx.mock
async def test_async_mixed_errors_then_success() -> None:
    """タイムアウト→サーバーエラー→成功のシナリオ"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.TimeoutException("Timeout"),
        httpx.Response(503),
        httpx.Response(200, json={"id": 1}),
    ]

    async with AsyncAPIClient(retry_count=3, retry_delay=0.01) as client:
        response = await client.get("/posts/1")

    assert route.call_count == 3
    assert response.status_code == 200


@respx.mock
async def test_async_mixed_errors_exhaust_retries() -> None:
    """複数のエラータイプでリトライ上限に達するケース"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.TimeoutException("Timeout"),
        httpx.ConnectError("Connection failed"),
        httpx.Response(500),
    ]

    async with AsyncAPIClient(retry_count=2, retry_delay=0.01) as client:
        with pytest.raises(APIRetryError):
            await client.get("/posts/1")

    assert route.call_count == 3


# =============================================================================
# HTTP Methods Tests（条件2: エラーパス）
# =============================================================================


@respx.mock
async def test_async_post_with_retry() -> None:
    """POSTリクエストのリトライ動作確認（5xxはリトライ対象）"""
    route = respx.post(f"{BASE_URL}/posts")
    route.side_effect = [
        httpx.Response(502),
        httpx.Response(201, json={"id": 101, "title": "created"}),
    ]

    async with AsyncAPIClient(retry_count=2, retry_delay=0.01) as client:
        response = await client.post(
            "/posts",
            json={"title": "test", "body": "content", "userId": 1},
        )

    assert route.call_count == 2
    assert response.status_code == 201


@respx.mock
async def test_async_put_4xx_no_retry() -> None:
    """PUTリクエストで4xxエラーはリトライせず即座にAPIHTTPErrorを発生"""
    route = respx.put(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.Response(400),
    ]

    async with AsyncAPIClient(retry_count=3, retry_delay=0.01) as client:
        with pytest.raises(APIHTTPError) as exc_info:
            await client.put("/posts/1", json={"title": "updated"})

    # 4xxエラーはリトライしない（1回のみ実行）
    assert route.call_count == 1
    assert exc_info.value.status_code == 400


@respx.mock
async def test_async_delete_with_retry() -> None:
    """DELETEリクエストのリトライ動作確認"""
    route = respx.delete(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.TimeoutException("Timeout"),
        httpx.Response(200),
    ]

    async with AsyncAPIClient(retry_count=2, retry_delay=0.01) as client:
        response = await client.delete("/posts/1")

    assert route.call_count == 2
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
# 4. respxパターンB（side_effect）の活用:
#    - side_effectリストで複数回の動作シミュレーション
#    - 例外とhttpx.Responseの混在が可能
#    - call_countによるリトライ回数検証
#    - 例外の適切な検証（pytest.raises）
#
# 5. 関数構造テスト設計:
#    - フラットな関数構造で可読性向上
#    - セクションコメントで論理グループ化
#    - Async/Sync対称構造を維持
# =============================================================================
