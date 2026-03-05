"""
AsyncAPIClient エラーハンドリングテスト

Note:
    test_sync_client_error_handling.py と対称構造で設計。
    責務: リトライロジック + 例外ハンドリングの検証

    例外クラス・_safe_parse_json・_map_request_error のテストは
    test_api_client_shared.py に統合済み。

テストケース一覧（12件）:
    - Retry (3件): server_error_then_success, exhausted, 4xx_no_retry
    - Timeout (2件): timeout_error_retry, timeout_then_success
    - Connection (2件): connection_error_retry, connection_then_success
    - Mixed Errors (2件): mixed_then_success, mixed_exhaust_retries
    - HTTP Methods (3件): post_with_retry, put_4xx_no_retry, delete_with_retry
"""

from unittest.mock import Mock, patch

import httpx
import pytest
import respx

from utils.api_client import (
    APIConnectionError,
    APIHTTPError,
    APIRetryError,
    APITimeoutError,
    AsyncAPIClient,
)

# Module-level marker: All tests in this file are unit tests
pytestmark = pytest.mark.unit

BASE_URL = "https://jsonplaceholder.typicode.com"


# =============================================================================
# Retry Logic Tests（条件2: エラーパス）
# =============================================================================


@respx.mock
@patch("utils.api_client.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_retry_on_server_error_then_success(mock_backoff: Mock) -> None:
    """サーバーエラー後に成功するケース（5xxはリトライ対象）"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.Response(500),  # 初回: 失敗
        httpx.Response(500),  # リトライ1回目: 失敗
        httpx.Response(200, json={"id": 1, "title": "test"}),  # リトライ2回目: 成功
        # Note: retry_count=3（最大4回呼び出し可能）だが、
        # 2回目のリトライで成功するためリストは3要素で十分
    ]

    async with AsyncAPIClient(retry_count=3) as client:
        response = await client.get("/posts/1")

    assert route.call_count == 3
    assert response.status_code == 200
    # バックオフが2回呼ばれることを確認（attempt 0, 1で失敗→backoff、attempt 2で成功）
    assert mock_backoff.call_count == 2


@respx.mock
@patch("utils.api_client.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_retry_exhausted(mock_backoff: Mock) -> None:
    """リトライ上限でAPIRetryErrorが発生することを確認（5xxのみリトライ）"""
    retry_count = 2
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [httpx.Response(500)] * (retry_count + 1)  # 初回 + リトライ数

    async with AsyncAPIClient(retry_count=retry_count) as client:
        with pytest.raises(APIRetryError) as exc_info:
            await client.get("/posts/1")

    # リトライ回数+1回（初回+リトライ{retry_count}回={retry_count + 1}回）実行されたことを確認
    assert route.call_count == retry_count + 1
    assert f"Async request failed after {retry_count + 1} attempts" in str(exc_info.value)
    # バックオフがretry_count回呼ばれることを確認（最後の試行ではバックオフなし）
    assert mock_backoff.call_count == retry_count


@respx.mock
@patch("utils.api_client.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_4xx_error_no_retry(mock_backoff: Mock) -> None:
    """4xxクライアントエラーはリトライせず即座にAPIHTTPErrorを発生"""
    route = respx.get(f"{BASE_URL}/posts/999")
    route.side_effect = [
        httpx.Response(404),
    ]

    async with AsyncAPIClient(retry_count=3) as client:
        with pytest.raises(APIHTTPError) as exc_info:
            await client.get("/posts/999")

    # 4xxエラーはリトライしない（1回のみ実行）
    assert route.call_count == 1
    assert exc_info.value.status_code == 404
    # 4xxは即raise、バックオフに到達しないことを確認
    assert mock_backoff.call_count == 0


# =============================================================================
# Timeout Tests（条件2: エラーパス）
# =============================================================================


@respx.mock
@patch("utils.api_client.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_timeout_error_retry(mock_backoff: Mock) -> None:
    """タイムアウト時にAPIRetryErrorが発生することを確認"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.TimeoutException("Request timed out"),
        httpx.TimeoutException("Request timed out"),
    ]

    async with AsyncAPIClient(retry_count=1) as client:
        with pytest.raises(APIRetryError) as exc_info:
            await client.get("/posts/1")

    # リトライが実行されることを確認（初回+リトライ1回=2回）
    assert route.call_count == 2
    assert isinstance(exc_info.value.__cause__, APITimeoutError)
    # バックオフが1回呼ばれることを確認（最後の試行ではバックオフなし）
    assert mock_backoff.call_count == 1


@respx.mock
@patch("utils.api_client.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_timeout_then_success(mock_backoff: Mock) -> None:
    """タイムアウト後に成功するケース"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.TimeoutException("Timeout 1"),
        httpx.Response(200, json={"id": 1}),
    ]

    async with AsyncAPIClient(retry_count=2) as client:
        response = await client.get("/posts/1")

    assert route.call_count == 2
    assert response.status_code == 200
    # バックオフが1回呼ばれることを確認（attempt 0で失敗→backoff、attempt 1で成功）
    assert mock_backoff.call_count == 1


# =============================================================================
# Connection Tests（条件2: エラーパス）
# =============================================================================


@respx.mock
@patch("utils.api_client.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_connection_error_retry(mock_backoff: Mock) -> None:
    """接続エラー時にAPIRetryErrorが発生することを確認"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.ConnectError("Connection refused"),
        httpx.ConnectError("Connection refused"),
    ]

    async with AsyncAPIClient(retry_count=1) as client:
        with pytest.raises(APIRetryError) as exc_info:
            await client.get("/posts/1")

    assert route.call_count == 2
    assert isinstance(exc_info.value.__cause__, APIConnectionError)
    # バックオフが1回呼ばれることを確認（最後の試行ではバックオフなし）
    assert mock_backoff.call_count == 1


@respx.mock
@patch("utils.api_client.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_connection_then_success(mock_backoff: Mock) -> None:
    """接続エラー後に成功するケース"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.ConnectError("Connection 1"),
        httpx.ConnectError("Connection 2"),
        httpx.Response(200, json={"id": 1}),
    ]

    async with AsyncAPIClient(retry_count=3) as client:
        response = await client.get("/posts/1")

    assert route.call_count == 3
    assert response.status_code == 200
    # バックオフが2回呼ばれることを確認（attempt 0, 1で失敗→backoff、attempt 2で成功）
    assert mock_backoff.call_count == 2


# =============================================================================
# Mixed Errors Tests（条件2: エラーパス）
# =============================================================================


@respx.mock
@patch("utils.api_client.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_mixed_errors_then_success(mock_backoff: Mock) -> None:
    """タイムアウト→サーバーエラー→成功のシナリオ"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.TimeoutException("Timeout"),
        httpx.Response(503),
        httpx.Response(200, json={"id": 1}),
    ]

    async with AsyncAPIClient(retry_count=3) as client:
        response = await client.get("/posts/1")

    assert route.call_count == 3
    assert response.status_code == 200
    # バックオフが2回呼ばれることを確認（attempt 0, 1で失敗→backoff、attempt 2で成功）
    assert mock_backoff.call_count == 2


@respx.mock
@patch("utils.api_client.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_mixed_errors_exhaust_retries(mock_backoff: Mock) -> None:
    """複数のエラータイプでリトライ上限に達するケース"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.TimeoutException("Timeout"),
        httpx.ConnectError("Connection failed"),
        httpx.Response(500),
    ]

    async with AsyncAPIClient(retry_count=2) as client:
        with pytest.raises(APIRetryError) as exc_info:
            await client.get("/posts/1")

    assert route.call_count == 3
    # 最後のエラー（500 Server Error）が__causeとして記録されていることを確認
    assert isinstance(exc_info.value.__cause__, APIHTTPError)
    # バックオフが2回呼ばれることを確認（最後の試行ではバックオフなし）
    assert mock_backoff.call_count == 2


# =============================================================================
# HTTP Methods Tests（条件2: エラーパス）
# =============================================================================


@respx.mock
@patch("utils.api_client.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_post_with_retry(mock_backoff: Mock) -> None:
    """POSTリクエストのリトライ動作確認（5xxはリトライ対象）"""
    route = respx.post(f"{BASE_URL}/posts")
    route.side_effect = [
        httpx.Response(502),
        httpx.Response(201, json={"id": 101, "title": "created"}),
    ]

    async with AsyncAPIClient(retry_count=2) as client:
        response = await client.post(
            "/posts",
            json={"title": "test", "body": "content", "userId": 1},
        )

    assert route.call_count == 2
    assert response.status_code == 201
    # バックオフが1回呼ばれることを確認（attempt 0で502失敗→backoff、attempt 1で成功）
    assert mock_backoff.call_count == 1


@respx.mock
@patch("utils.api_client.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_put_4xx_no_retry(mock_backoff: Mock) -> None:
    """PUTリクエストで4xxエラーはリトライせず即座にAPIHTTPErrorを発生"""
    route = respx.put(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.Response(400),
    ]

    async with AsyncAPIClient(retry_count=3) as client:
        with pytest.raises(APIHTTPError) as exc_info:
            await client.put("/posts/1", json={"title": "updated"})

    # 4xxエラーはリトライしない（1回のみ実行）
    assert route.call_count == 1
    assert exc_info.value.status_code == 400
    # 4xxは即raise、バックオフに到達しないことを確認
    assert mock_backoff.call_count == 0


@respx.mock
@patch("utils.api_client.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_delete_with_retry(mock_backoff: Mock) -> None:
    """DELETEリクエストのリトライ動作確認"""
    route = respx.delete(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.TimeoutException("Timeout"),
        httpx.Response(200),
    ]

    async with AsyncAPIClient(retry_count=2) as client:
        response = await client.delete("/posts/1")

    assert route.call_count == 2
    assert response.status_code == 200
    # バックオフが1回呼ばれることを確認（attempt 0でTimeout失敗→backoff、attempt 1で成功）
    assert mock_backoff.call_count == 1


# =============================================================================
# 学習ポイント:
#
# 1. リトライロジック実装パターン:
#    - サーバーエラー（5xx）はリトライ対象
#    - クライアントエラー（4xx）はリトライしない
#    - タイムアウト・接続エラーはリトライ対象
#    - リトライ上限でAPIRetryErrorを発生
#
# 2. エラー回復戦略:
#    - 一時的なエラーからの自動回復
#    - リトライ間隔の設定（exponential backoffも可能）
#    - 最終的なエラーハンドリング（リトライ失敗時）
#
# 3. respxパターンB（side_effect）の活用:
#    - side_effectリストで複数回の動作シミュレーション
#    - 例外とhttpx.Responseの混在が可能
#    - call_countによるリトライ回数検証
#    - 例外の適切な検証（pytest.raises）
#
# 4. 共通テスト（例外・JSON・エラーマッピング）:
#    → test_api_client_shared.py に統合済み
# =============================================================================
