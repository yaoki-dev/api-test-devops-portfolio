"""
AsyncAPIClient エラーハンドリングテスト

Note:
    test_sync_client_error_handling.py と対称構造で設計。
    責務: リトライロジック + 例外ハンドリングの検証

    例外クラス・_safe_parse_json・_map_request_error のテストは
    test_api_client_shared.py に統合済み。

テストケース一覧（15件）:
    - Retry (3件): server_error_then_success, exhausted, 4xx_no_retry
    - Timeout (2件): timeout_error_retry, timeout_then_success
    - Connection (2件): connection_error_retry, connection_then_success
    - Mixed Errors (2件): mixed_then_success, mixed_exhaust_retries
    - HTTP Methods (3件): post_with_retry, put_4xx_no_retry, delete_with_retry
    - Log Bypass (3件):
        non_retryable_error_logs_before_raise[TooManyRedirects-Max redirects exceeded],
        non_retryable_error_logs_before_raise[InvalidURL-Invalid URL format],
        non_retryable_error_skips_retry
"""

from unittest.mock import Mock, patch

import httpx
import pytest
import respx
from structlog.testing import capture_logs

from tests.constants import BASE_URL
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
# Log Bypass Tests（Issue #224: _map_request_error raiseでログが失われない検証）
# =============================================================================


@pytest.mark.parametrize(
    "exc,expected_error",
    [
        (httpx.TooManyRedirects("Max redirects exceeded"), "Max redirects exceeded"),
        (httpx.InvalidURL("Invalid URL format"), "Invalid URL format"),
    ],
)
@respx.mock
async def test_async_non_retryable_error_logs_before_raise(
    exc: httpx.TooManyRedirects | httpx.InvalidURL, expected_error: str
) -> None:
    """非リトライエラー時にlogger.warningが_map_request_error前に実行される

    _map_request_errorは非リトライエラーで即座にraiseするが、
    ログ出力はその前に実行されるため、デバッグ情報が失われない。
    """
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = exc

    with capture_logs() as log_output:
        with pytest.raises(APIClientError, match="Non-retryable request error"):
            async with AsyncAPIClient(retry_count=0) as client:
                await client.get("/posts/1")

    # ログが出力されていることを検証（ログバイパスが修正済み）
    warning_logs = [
        log
        for log in log_output
        if log.get("log_level") == "warning" and log.get("event") == "async_request_error"
    ]
    assert len(warning_logs) == 1, f"Expected 1 warning log, got: {log_output}"
    assert warning_logs[0]["method"] == "GET"
    assert warning_logs[0]["endpoint"] == "/posts/1"
    assert expected_error in warning_logs[0]["error"]  # error フィールド検証


@respx.mock
async def test_async_non_retryable_error_skips_retry() -> None:
    """retry_count>=1設定時でも非リトライエラーはリトライループを即 raise で脱出する

    TooManyRedirects/InvalidURL は即 raise のため、
    retry_count を増やしても1回のみの試行で APIClientError が発生する。
    """
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = httpx.TooManyRedirects("Max redirects exceeded")

    with pytest.raises(APIClientError, match="Non-retryable request error"):
        async with AsyncAPIClient(retry_count=2) as client:
            await client.get("/posts/1")

    # リトライされていないことを確認
    assert route.call_count == 1, "非リトライエラーは1回のみ試行される"


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
