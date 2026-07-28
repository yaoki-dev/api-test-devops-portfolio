"""GitHub API非同期クライアントの汎用request処理テスト"""

import asyncio
import json
import sys
from unittest.mock import AsyncMock, Mock, call, patch

import httpx
import pytest
import respx
from structlog.testing import capture_logs

from utils.github_client import AsyncGitHubClient
from utils.github_error_handler import (
    GitHubAPIError,
    GitHubServerError,
    NotFoundError,
    RateLimitError,
)

pytestmark = pytest.mark.unit

GITHUB_API_BASE_URL = "https://api.github.com"
MAX_RETRIES = 3


@respx.mock
@patch("utils.github_error_handler.exponential_backoff_with_jitter", return_value=0.0)
@patch("utils.github_error_handler.asyncio.sleep", new_callable=AsyncMock)
async def test_retry_on_server_error(mock_sleep: AsyncMock, mock_backoff: Mock) -> None:
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [
        httpx.Response(500, headers={"X-RateLimit-Remaining": "50"}),
        httpx.Response(500, headers={"X-RateLimit-Remaining": "50"}),
        httpx.Response(500, headers={"X-RateLimit-Remaining": "50"}),
    ]

    async with AsyncGitHubClient(max_retries=MAX_RETRIES) as client:
        with pytest.raises(GitHubServerError) as exc_info:
            await client.get_user("octocat")

    assert route.call_count == MAX_RETRIES
    assert "Server error: 500" in str(exc_info.value)
    assert f"after {MAX_RETRIES} attempts" in str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    assert mock_backoff.call_count == MAX_RETRIES - 1
    assert mock_sleep.await_count == MAX_RETRIES - 1
    mock_sleep.assert_has_awaits([call(0.0)] * (MAX_RETRIES - 1))


@pytest.mark.parametrize(
    ("timeout_exception", "expected_message"),
    [
        pytest.param(
            httpx.TimeoutException("Request timeout"),
            "Request timeout: TimeoutException",
            id="timeout_exception",
        ),
        pytest.param(
            httpx.ConnectTimeout("Connect timeout"),
            "Request timeout: ConnectTimeout",
            id="connect_timeout",
        ),
        pytest.param(
            httpx.ReadTimeout("Read timeout"),
            "Request timeout: ReadTimeout",
            id="read_timeout",
        ),
        pytest.param(
            httpx.WriteTimeout("Write timeout"),
            "Request timeout: WriteTimeout",
            id="write_timeout",
        ),
        pytest.param(
            httpx.PoolTimeout("Pool timeout"),
            "Request timeout: PoolTimeout",
            id="pool_timeout",
        ),
    ],
)
@respx.mock
async def test_timeout_handling(
    timeout_exception: httpx.TimeoutException,
    expected_message: str,
):
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").mock(side_effect=timeout_exception)

    with patch(
        "utils.github_rate_limit.exponential_backoff_with_jitter",
        return_value=0.0,
    ) as mock_backoff:
        with patch("utils.github_rate_limit.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with capture_logs() as log_output:
                async with AsyncGitHubClient() as client:
                    with pytest.raises(GitHubAPIError) as exc_info:
                        await client.get_user("octocat")

    assert str(exc_info.value) == expected_message
    # 例外チェーン切断確認（from None による PII 漏洩防止）
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None  # active exception context 外 raise による PII 防止
    assert route.call_count == MAX_RETRIES  # timeout は max_retries 回まで再試行
    assert mock_backoff.call_count == MAX_RETRIES - 1
    assert mock_sleep.await_count == MAX_RETRIES - 1
    mock_sleep.assert_has_awaits([call(0.0)] * (MAX_RETRIES - 1))
    timeout_logs = [log for log in log_output if log.get("event") == "request_timeout"]
    assert len(timeout_logs) == MAX_RETRIES
    for timeout_log in timeout_logs:
        assert timeout_log["error_type"] == type(timeout_exception).__qualname__
        assert timeout_log["error_module"] == type(timeout_exception).__module__
        assert timeout_log["error_context"] == "timeout"
        assert set(timeout_log) == {
            "endpoint",
            "method",
            "error_type",
            "error_module",
            "error_context",
            "event",
            "log_level",
        }
        assert "error_detail" not in timeout_log
        assert "error" not in timeout_log


@respx.mock
async def test_timeout_logging_no_pii_leak():
    """タイムアウト詳細をログと例外チェーンから除外し、PII漏洩を防止する。"""
    sensitive_detail = "https://api.example.com/internal?token=SECRET_API_KEY_12345"  # noqa: S105
    timeout_exception = httpx.ConnectTimeout(sensitive_detail)
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").mock(side_effect=timeout_exception)

    with patch(
        "utils.github_rate_limit.exponential_backoff_with_jitter",
        return_value=0.0,
    ) as mock_backoff:
        with patch("utils.github_rate_limit.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with capture_logs() as log_output:
                async with AsyncGitHubClient() as client:
                    with pytest.raises(GitHubAPIError) as exc_info:
                        await client.get_user("octocat")

    assert sensitive_detail not in str(exc_info.value)
    # __cause__ 切断検証: from None により Sentry/traceback 経由の PII 漏洩を防止
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None  # active exception context 外 raise による PII 防止
    timeout_logs = [log for log in log_output if log.get("event") == "request_timeout"]
    assert len(timeout_logs) == MAX_RETRIES
    # PII値レベル検証: 全logフィールド値にsensitive_detailが漏洩していないこと
    for timeout_log in timeout_logs:
        for value in timeout_log.values():
            assert sensitive_detail not in str(value), (
                f"sensitive_detail leaked in log field value: {value!r}"
            )
    assert route.call_count == MAX_RETRIES
    assert mock_backoff.call_count == MAX_RETRIES - 1
    assert mock_sleep.await_count == MAX_RETRIES - 1


@respx.mock
async def test_timeout_final_retry_logs_error() -> None:
    """最終失敗を観測可能にし、retry中断を見落とさないERRORログを固定する。"""
    timeout_exception = httpx.ConnectTimeout("https://example.com?token=secret")  # noqa: S105
    respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").mock(side_effect=timeout_exception)

    with patch(
        "utils.github_rate_limit.exponential_backoff_with_jitter",
        return_value=0.0,
    ):
        with patch("utils.github_rate_limit.asyncio.sleep", new_callable=AsyncMock):
            with capture_logs() as log_output:
                async with AsyncGitHubClient(max_retries=MAX_RETRIES) as client:
                    with pytest.raises(GitHubAPIError):
                        await client.get_user("octocat")

    error_logs = [log for log in log_output if log.get("event") == "github_retry_failed"]
    assert len(error_logs) == 1
    assert error_logs[0]["error_type"] == "ConnectTimeout"
    assert error_logs[0]["error_context"] == "timeout"
    assert error_logs[0]["max_retries"] == MAX_RETRIES
    # timeout/network error path では status_code フィールドが明示的に None で記録される
    # ことを継続検証する（ログスキーマ回帰防止）
    assert error_logs[0]["status_code"] is None
    assert "secret" not in str(error_logs[0])


@pytest.mark.parametrize(
    ("network_exception", "expected_message"),
    [
        pytest.param(
            httpx.ConnectError("Connection refused"),
            "Network error: ConnectError",
            id="connect_error",
        ),
        pytest.param(
            httpx.ReadError("Read failed"),
            "Network error: ReadError",
            id="read_error",
        ),
        pytest.param(
            httpx.WriteError("Write failed"),
            "Network error: WriteError",
            id="write_error",
        ),
        pytest.param(
            httpx.CloseError("Close failed"),
            "Network error: CloseError",
            id="close_error",
        ),
        pytest.param(
            httpx.RemoteProtocolError("Remote protocol failed"),
            "Network error: RemoteProtocolError",
            id="remote_protocol_error",
        ),
    ],
)
@respx.mock
async def test_network_error_retry_handling(
    network_exception: httpx.NetworkError | httpx.RemoteProtocolError,
    expected_message: str,
) -> None:
    """NetworkError/RemoteProtocolError系をretry後、GitHubAPIErrorへ安全に変換する。"""
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").mock(side_effect=network_exception)

    with patch(
        "utils.github_rate_limit.exponential_backoff_with_jitter",
        return_value=0.0,
    ) as mock_backoff:
        with patch("utils.github_rate_limit.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with capture_logs() as log_output:
                async with AsyncGitHubClient() as client:
                    with pytest.raises(GitHubAPIError) as exc_info:
                        await client.get_user("octocat")

    assert str(exc_info.value) == expected_message
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    assert route.call_count == MAX_RETRIES
    assert mock_backoff.call_count == MAX_RETRIES - 1
    assert mock_sleep.await_count == MAX_RETRIES - 1
    mock_sleep.assert_has_awaits([call(0.0)] * (MAX_RETRIES - 1))
    network_logs = [log for log in log_output if log.get("event") == "request_network_error"]
    assert len(network_logs) == MAX_RETRIES
    for network_log in network_logs:
        assert network_log["error_type"] == type(network_exception).__qualname__
        assert network_log["error_module"] == type(network_exception).__module__
        assert network_log["error_context"] == "network"
        assert set(network_log) == {
            "endpoint",
            "method",
            "error_type",
            "error_module",
            "error_context",
            "event",
            "log_level",
        }
        assert "error_detail" not in network_log
        assert "error" not in network_log


@pytest.mark.parametrize(
    "network_exception",
    [
        pytest.param(httpx.ConnectError("Connection refused"), id="connect_error"),
        pytest.param(
            httpx.RemoteProtocolError("Remote protocol failed"), id="remote_protocol_error"
        ),
    ],
)
@respx.mock
async def test_network_error_final_retry_logs_error(
    network_exception: httpx.NetworkError | httpx.RemoteProtocolError,
) -> None:
    respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").mock(side_effect=network_exception)

    with patch(
        "utils.github_rate_limit.exponential_backoff_with_jitter",
        return_value=0.0,
    ):
        with patch("utils.github_rate_limit.asyncio.sleep", new_callable=AsyncMock):
            with capture_logs() as log_output:
                async with AsyncGitHubClient() as client:
                    with pytest.raises(GitHubAPIError):
                        await client.get_user("octocat")

    final_logs = [log for log in log_output if log.get("event") == "github_retry_failed"]
    assert len(final_logs) == 1
    final_log = final_logs[0]
    assert final_log["log_level"] == "error"
    assert final_log["endpoint"] == "/users/octocat"
    assert final_log["method"] == "GET"
    assert final_log["error_type"] == type(network_exception).__qualname__
    assert final_log["error_module"] == type(network_exception).__module__
    assert final_log["error_context"] == "network"
    assert final_log["status_code"] is None
    assert final_log["max_retries"] == MAX_RETRIES
    assert set(final_log) == {
        "endpoint",
        "method",
        "error_type",
        "error_module",
        "error_context",
        "max_retries",
        "status_code",
        "event",
        "log_level",
    }


@pytest.mark.parametrize(
    "exception_class",
    [
        pytest.param(httpx.ConnectError, id="network_error"),
        pytest.param(httpx.RemoteProtocolError, id="remote_protocol_error"),
    ],
)
@respx.mock
async def test_network_and_protocol_error_logging_no_pii_leak(
    exception_class: type[Exception],
) -> None:
    """ネットワーク例外の詳細をログへ出さず、PII漏洩を防止する。"""
    sensitive_detail = "https://api.example.com/internal?token=SECRET_API_KEY_12345"  # noqa: S105
    transport_exception = exception_class(sensitive_detail)
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").mock(side_effect=transport_exception)

    with patch(
        "utils.github_rate_limit.exponential_backoff_with_jitter",
        return_value=0.0,
    ) as mock_backoff:
        with patch("utils.github_rate_limit.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with capture_logs() as log_output:
                async with AsyncGitHubClient() as client:
                    with pytest.raises(GitHubAPIError) as exc_info:
                        await client.get_user("octocat")

    assert sensitive_detail not in str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    assert route.call_count == MAX_RETRIES
    assert mock_backoff.call_count == MAX_RETRIES - 1
    assert mock_sleep.await_count == MAX_RETRIES - 1
    mock_sleep.assert_has_awaits([call(0.0)] * (MAX_RETRIES - 1))
    network_logs = [log for log in log_output if log.get("event") == "request_network_error"]
    assert len(network_logs) == MAX_RETRIES
    for network_log in network_logs:
        assert network_log["error_type"] == exception_class.__qualname__
        assert network_log["error_module"] == exception_class.__module__
        assert network_log["error_context"] == "network"
        for value in network_log.values():
            assert sensitive_detail not in str(value), (
                f"sensitive_detail leaked in log field value: {value!r}"
            )


@respx.mock
async def test_local_protocol_error_is_not_retried() -> None:
    """クライアント側protocol violationは再試行しても回復しないため、retry対象外とする。"""
    sensitive_detail = "https://api.example.com/internal?token=SECRET_API_KEY_12345"  # noqa: S105
    local_protocol_error = httpx.LocalProtocolError(sensitive_detail)
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").mock(side_effect=local_protocol_error)

    with capture_logs() as log_output:
        async with AsyncGitHubClient() as client:
            with pytest.raises(GitHubAPIError) as exc_info:
                await client.get_user("octocat")

    assert str(exc_info.value) == "Unexpected error: LocalProtocolError"
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    assert route.call_count == 1
    unexpected_logs = [log for log in log_output if log.get("event") == "unexpected_error"]
    assert len(unexpected_logs) == 1
    assert unexpected_logs[0]["error_type"] == "LocalProtocolError"
    assert unexpected_logs[0]["error_context"] == "unexpected"
    assert sensitive_detail not in str(exc_info.value)
    for value in unexpected_logs[0].values():
        assert sensitive_detail not in str(value), (
            f"sensitive_detail leaked in log field value: {value!r}"
        )


@respx.mock
async def test_request_http_status_error_is_saved_before_safe_handler_call() -> None:
    """GW3: HTTPStatusError は except 外へ退避後にPII-safe handlerへ渡す。"""
    request = httpx.Request("GET", f"{GITHUB_API_BASE_URL}/users/octocat?token=secret")
    response = httpx.Response(401, request=request, content=b"token=secret")
    status_error = httpx.HTTPStatusError("401 secret", request=request, response=response)

    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [status_error]

    def safe_handler(
        handled_response: httpx.Response,
        endpoint: str,
        method: str,
        *,
        logger: Mock,
    ) -> None:
        if sys.exception() is not None:
            raise AssertionError("HTTPStatusError handler was called inside an active exception")
        if handled_response is not response:
            raise AssertionError("HTTPStatusError response was not preserved")
        raise GitHubAPIError(f"HTTP {handled_response.status_code} error") from None

    async with AsyncGitHubClient() as client:
        with patch("utils.github_client.handle_http_status_error", side_effect=safe_handler):
            with pytest.raises(GitHubAPIError) as exc_info:
                await client.get_user("octocat")

    assert str(exc_info.value) == "HTTP 401 error"
    assert "secret" not in str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    assert route.call_count == 1


@respx.mock
async def test_httpx_status_error_4xx():
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=401,
        headers={"X-RateLimit-Remaining": "60"},
    )

    async with AsyncGitHubClient() as client:
        with pytest.raises(GitHubAPIError) as exc_info:
            await client.get_user("octocat")

    assert not isinstance(exc_info.value, httpx.HTTPStatusError)
    # from None による完全PII遮断: __cause__ は None
    assert exc_info.value.__cause__ is None
    # except外raiseパターン: HTTPStatusErrorが__context__に残存しないこと（PII漏洩防止）
    assert exc_info.value.__context__ is None
    assert route.call_count == 1
    assert str(exc_info.value) == "HTTP 401 error"


@respx.mock
@patch("utils.github_error_handler.exponential_backoff_with_jitter", return_value=0.0)
@patch("utils.github_error_handler.asyncio.sleep", new_callable=AsyncMock)
async def test_httpx_status_error_5xx(mock_sleep: AsyncMock, mock_backoff: Mock) -> None:
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [
        httpx.Response(503, headers={"X-RateLimit-Remaining": "60"}),
        httpx.Response(503, headers={"X-RateLimit-Remaining": "60"}),
        httpx.Response(503, headers={"X-RateLimit-Remaining": "60"}),
    ]

    with capture_logs() as log_output:
        async with AsyncGitHubClient(max_retries=MAX_RETRIES) as client:
            with pytest.raises(GitHubServerError) as exc_info:
                await client.get_user("octocat")

    assert "Server error: 503" in str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    assert route.call_count == MAX_RETRIES
    assert mock_backoff.call_count == MAX_RETRIES - 1
    assert mock_sleep.await_count == MAX_RETRIES - 1

    retry_logs = [log for log in log_output if log.get("event") == "retrying_server_error"]
    assert len(retry_logs) == MAX_RETRIES - 1, (
        f"retrying_server_error ログが{MAX_RETRIES - 1}件を期待 (実際: {len(retry_logs)}件)"
    )
    bad_level = [log for log in retry_logs if log.get("log_level") != "warning"]
    assert not bad_level, f"log_level が warning でないエントリ: {bad_level}"
    actual_attempts = [log_entry.get("attempt") for log_entry in retry_logs]
    assert actual_attempts == list(range(1, MAX_RETRIES)), f"attempt 値不一致: {actual_attempts}"
    for log_entry in retry_logs:
        assert log_entry["endpoint"] == "/users/octocat"
        assert log_entry["method"] == "GET"
        assert log_entry["status_code"] == 503
        assert log_entry["max_retries"] == MAX_RETRIES
        assert log_entry["delay"] == 0.0


@respx.mock
@patch("utils.github_error_handler.exponential_backoff_with_jitter", return_value=0.0)
@patch("utils.github_error_handler.asyncio.sleep", new_callable=AsyncMock)
async def test_httpx_status_error_5xx_defensive_path(
    mock_sleep: AsyncMock,
    mock_backoff: Mock,
) -> None:
    request = httpx.Request("GET", f"{GITHUB_API_BASE_URL}/users/octocat")
    response_503 = httpx.Response(503, request=request)
    error_503 = httpx.HTTPStatusError("503 Server Error", request=request, response=response_503)

    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [error_503] * MAX_RETRIES

    with capture_logs() as log_output:
        async with AsyncGitHubClient(max_retries=MAX_RETRIES) as client:
            with pytest.raises(GitHubServerError) as exc_info:
                await client.get_user("octocat")

    assert "Server error: 503" in str(exc_info.value)
    assert route.call_count == MAX_RETRIES
    assert mock_backoff.call_count == MAX_RETRIES - 1
    assert mock_sleep.await_count == MAX_RETRIES - 1

    retry_logs = [log for log in log_output if log.get("event") == "retrying_server_error"]
    assert len(retry_logs) == MAX_RETRIES - 1, (
        f"retrying_server_error ログが{MAX_RETRIES - 1}件を期待 (実際: {len(retry_logs)}件)"
    )
    bad_level = [log for log in retry_logs if log.get("log_level") != "warning"]
    assert not bad_level, f"log_level が warning でないエントリ: {bad_level}"
    actual_attempts = [log_entry.get("attempt") for log_entry in retry_logs]
    assert actual_attempts == list(range(1, MAX_RETRIES)), f"attempt 値不一致: {actual_attempts}"
    for log_entry in retry_logs:
        assert log_entry["endpoint"] == "/users/octocat"
        assert log_entry["method"] == "GET"
        assert log_entry["status_code"] == 503
        assert log_entry["max_retries"] == MAX_RETRIES
        assert log_entry["delay"] == 0.0


@respx.mock
async def test_httpx_status_error_403_defensive_path() -> None:
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        403,
        headers={
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": "1640000000",
        },
    )

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.__context__ is None  # active exception context 外 raise による PII 防止
    assert exc_info.value.reset_time == 1640000000
    assert "Rate limit exceeded" in str(exc_info.value)
    assert route.call_count == 1


@respx.mock
async def test_httpx_status_error_403_auth_error_defensive_path() -> None:
    request = httpx.Request("GET", f"{GITHUB_API_BASE_URL}/users/octocat")
    response_403 = httpx.Response(403, request=request)  # Rate Limitヘッダーなし
    error_403 = httpx.HTTPStatusError("403 Forbidden", request=request, response=response_403)

    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [error_403]

    async with AsyncGitHubClient() as client:
        with pytest.raises(GitHubAPIError, match="Access forbidden") as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.__context__ is None  # active exception context 外 raise による PII 防止
    assert route.call_count == 1


@respx.mock
async def test_httpx_status_error_403_auth_error_with_message() -> None:
    request = httpx.Request("GET", f"{GITHUB_API_BASE_URL}/users/octocat")
    response_403 = httpx.Response(
        403,
        json={"message": "Resource not accessible by integration"},
        request=request,
    )
    error_403 = httpx.HTTPStatusError("403 Forbidden", request=request, response=response_403)

    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [error_403]

    async with AsyncGitHubClient() as client:
        with pytest.raises(GitHubAPIError, match="^Access forbidden$") as exc_info:
            await client.get_user("octocat")

    assert "Resource not accessible" not in str(exc_info.value)

    assert route.call_count == 1


@respx.mock
async def test_unexpected_exception():
    sensitive_detail = "secret connection string"
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").mock(
        side_effect=ValueError(sensitive_detail)
    )

    with capture_logs() as log_output:
        async with AsyncGitHubClient() as client:
            with pytest.raises(GitHubAPIError) as exc_info:
                await client.get_user("octocat")

    assert str(exc_info.value) == "Unexpected error: ValueError"
    assert sensitive_detail not in str(exc_info.value)
    # 例外チェーンは切断し、元例外メッセージは露出しない
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    assert route.call_count == 1
    error_logs = [log for log in log_output if log.get("event") == "unexpected_error"]
    assert len(error_logs) == 1
    assert "error" not in error_logs[0]
    assert error_logs[0]["error_type"] == "ValueError"
    assert error_logs[0]["error_module"] == "builtins"
    assert error_logs[0]["error_context"] == "unexpected"
    # PII値レベル検証: 全 log フィールド値に sensitive_detail が漏洩していないこと
    for value in error_logs[0].values():
        assert sensitive_detail not in str(value), (
            f"sensitive_detail leaked in log field value: {value!r}"
        )


@respx.mock
async def test_response_not_read_propagates_without_unexpected_wrapper():
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [httpx.ResponseNotRead()]
    async with AsyncGitHubClient() as client:
        with pytest.raises(httpx.ResponseNotRead):
            await client.get_user("octocat")
    assert route.call_count == 1


@respx.mock
async def test_json_decode_error():
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=200,
        content=b"invalid json content",
        headers={
            "Content-Type": "application/json",
            "X-RateLimit-Remaining": "50",
        },
    )

    with capture_logs() as logs:
        async with AsyncGitHubClient() as client:
            with pytest.raises(GitHubAPIError, match="Invalid JSON"):
                await client.get_user("octocat")

    assert route.call_count == 1
    decode_logs = [log for log in logs if log.get("event") == "json_decode_error"]
    assert len(decode_logs) == 1
    assert decode_logs[0]["endpoint"] == "/users/octocat"
    assert "error" not in decode_logs[0]
    assert decode_logs[0]["error_type"] == json.JSONDecodeError.__qualname__
    assert decode_logs[0]["error_module"] == json.JSONDecodeError.__module__
    assert isinstance(decode_logs[0]["error_pos"], int)
    assert isinstance(decode_logs[0]["error_lineno"], int)


@pytest.mark.parametrize(
    ("exception_class", "exception_args"),
    [
        pytest.param(SystemExit, (1,), id="SystemExit"),
        pytest.param(MemoryError, ("OOM",), id="MemoryError"),
        pytest.param(asyncio.CancelledError, (), id="CancelledError"),
    ],
)
async def test_base_exception_propagates_through_request(
    exception_class: type[BaseException],
    exception_args: tuple[object, ...],
) -> None:
    """システム例外が_requestメソッドを透過的に伝播することを検証

    SystemExit/MemoryError/CancelledErrorは汎用の例外ハンドラで
    捕捉・ラップしてはならない。httpx.AsyncClientのrequestメソッドを
    patch.objectで直接置換するため、respxのHTTPインターセプト層を経由しない。
    @respx.mockは不要。

    Note:
        CancelledErrorはPython 3.8+でBaseExceptionサブクラス。
        実装のexcept節から明示的re-raise対象が削除・変更された場合の
        退行検出として機能する安全網テスト。
    """
    async with AsyncGitHubClient() as client:
        with patch.object(client._client, "request", side_effect=exception_class(*exception_args)):
            with pytest.raises(exception_class):
                await client.get_user("octocat")


@respx.mock
async def test_httpx_status_error_404_defensive_path_raises_not_found_error() -> None:
    """HTTPStatusErrorを直接受ける防御経路でも404契約を維持する。"""
    request = httpx.Request("GET", f"{GITHUB_API_BASE_URL}/users/octocat")
    response_404 = httpx.Response(404, request=request)
    error_404 = httpx.HTTPStatusError("404 Not Found", request=request, response=response_404)

    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [error_404]

    async with AsyncGitHubClient() as client:
        with pytest.raises(NotFoundError) as exc_info:
            await client.get_user("octocat")

    assert "Resource not found" in str(exc_info.value)
    assert "/users/octocat" in str(exc_info.value)
    assert exc_info.value.__context__ is None  # from None による PII 遮断の確認
    assert route.call_count == 1
