"""GitHub API非同期クライアントのUnit Tests"""

import asyncio
import json
import sys
from datetime import UTC, datetime
from unittest.mock import ANY, AsyncMock, Mock, call, patch

import httpx
import pytest
import respx
from structlog.testing import capture_logs

from utils.exceptions import APIClientError
from utils.github_client import AsyncGitHubClient, validate_github_repo, validate_github_username
from utils.github_error_handler import (
    GitHubAPIError,
    GitHubServerError,
    NotFoundError,
    RateLimitError,
    SanitizedJSONDecodeError,
    redact_body_preview,
)
from utils.github_rate_limit import RATE_LIMIT_WARNING_THRESHOLD

pytestmark = pytest.mark.unit
# @pytest.mark.asyncio: asyncio_mode = "auto" (pyproject.toml) のため、@pytest.mark.asyncio は不要
# pytest-asyncio が async テストを自動検出する

GITHUB_API_BASE_URL = "https://api.github.com"
MAX_RETRIES = 3


def test_github_api_error_uses_shared_api_client_error() -> None:
    """GitHub例外は分割後も共有API例外階層に属する。"""
    assert issubclass(GitHubAPIError, APIClientError)


def test_gw1_public_contract_symbols_are_promoted() -> None:
    """GW1で固定契約シンボルを責務別モジュールから公開する。"""
    cause = SanitizedJSONDecodeError("json.JSONDecodeError", "Expecting value", 0, 1, 1)

    assert RATE_LIMIT_WARNING_THRESHOLD == 10
    assert redact_body_preview("") == "[redacted:e3b0c44298fc1c14]"
    assert str(cause) == "json.JSONDecodeError: Expecting value pos=0, lineno=1, colno=1"


# =============================================================================
# 基本機能テスト（正常系）
# =============================================================================


@respx.mock
async def test_get_user_success():
    """ユーザー情報取得成功

    検証項目:
    - async withコンテキストマネージャーの動作
    - HTTPXクライアントのリクエスト実行
    - JSONレスポンスの正常パーシング
    """
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=200,
        json={
            "login": "octocat",
            "name": "The Octocat",
            "public_repos": 8,
        },
        headers={"X-RateLimit-Remaining": "59"},
    )

    async with AsyncGitHubClient() as client:
        user = await client.get_user("octocat")

    assert user["login"] == "octocat"
    assert user["name"] == "The Octocat"
    assert user["public_repos"] == 8
    assert route.call_count == 1  # GETリクエストが1回発行されたことを確認


@respx.mock
async def test_get_repos_success():
    """リポジトリ一覧取得成功"""
    route = respx.get(
        f"{GITHUB_API_BASE_URL}/users/octocat/repos", params={"sort": "updated", "per_page": 2}
    ).respond(
        status_code=200,
        json=[
            {"name": "Hello-World", "stargazers_count": 100},
            {"name": "Spoon-Knife", "stargazers_count": 50},
        ],
        headers={"X-RateLimit-Remaining": "58"},
    )

    async with AsyncGitHubClient() as client:
        repos = await client.get_repos("octocat", per_page=2)

    assert len(repos) == 2
    assert repos[0]["name"] == "Hello-World"
    assert repos[1]["stargazers_count"] == 50
    assert route.call_count == 1  # GETリクエストが1回発行されたことを確認


@pytest.mark.parametrize(
    "sort",
    [
        pytest.param("stars", id="unsupported_sort"),
        pytest.param("", id="empty_sort"),
    ],
)
async def test_get_repos_rejects_invalid_sort(sort: str) -> None:
    """get_repos() は GitHub API に渡す前に sort 許容値を検証する"""
    async with AsyncGitHubClient() as client:
        with pytest.raises(ValueError, match="sort must be one of"):
            await client.get_repos("octocat", sort=sort)


@pytest.mark.parametrize(
    "per_page",
    [
        pytest.param(0, id="below_min"),
        pytest.param(101, id="above_max"),
    ],
)
async def test_get_repos_rejects_invalid_per_page(per_page: int) -> None:
    """get_repos() は GitHub API に渡す前に per_page 範囲を検証する"""
    async with AsyncGitHubClient() as client:
        with pytest.raises(ValueError, match="per_page must be between 1 and 100"):
            await client.get_repos("octocat", per_page=per_page)


@respx.mock
async def test_get_repo_success():
    """リポジトリ詳細取得成功"""
    route = respx.get(f"{GITHUB_API_BASE_URL}/repos/octocat/Hello-World").respond(
        status_code=200,
        json={
            "name": "Hello-World",
            "full_name": "octocat/Hello-World",
            "stargazers_count": 100,
            "forks_count": 50,
        },
        headers={"X-RateLimit-Remaining": "57"},
    )

    async with AsyncGitHubClient() as client:
        repo = await client.get_repo("octocat", "Hello-World")

    assert repo["name"] == "Hello-World"
    assert repo["stargazers_count"] == 100
    assert route.call_count == 1  # GETリクエストが1回発行されたことを確認


# =============================================================================
# エラーハンドリングテスト（異常系）
# =============================================================================


@respx.mock
async def test_get_user_not_found():
    """ユーザーが存在しない（404 Not Found）

    検証項目:
    - 404ステータスコードでNotFoundError例外発生
    - エラーメッセージにエンドポイント含む
    """
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/nonexistent-user-12345").respond(
        status_code=404,
        headers={"X-RateLimit-Remaining": "60"},
    )

    async with AsyncGitHubClient() as client:
        with pytest.raises(NotFoundError) as exc_info:
            await client.get_user("nonexistent-user-12345")

    assert "Resource not found" in str(exc_info.value)
    assert "/users/nonexistent-user-12345" in str(exc_info.value)
    assert route.call_count == 1  # GETリクエストが1回発行されたことを確認


@respx.mock
async def test_rate_limit_exceeded():
    """Rate Limit超過（403 Forbidden）

    検証項目:
    - 403ステータスコードでRateLimitError例外発生
    - reset_time属性が正しく設定される
    """
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=403,
        headers={
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": "1640000000",
        },
    )

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.reset_time == 1640000000
    assert "Rate limit exceeded" in str(exc_info.value)
    assert route.call_count == 1  # GETリクエストが1回発行されたことを確認


@respx.mock
@patch("utils.github_error_handler.exponential_backoff_with_jitter", return_value=0.0)
@patch("utils.github_error_handler.asyncio.sleep", new_callable=AsyncMock)
async def test_retry_on_server_error(mock_sleep: AsyncMock, mock_backoff: Mock) -> None:
    """5xxエラーで3回リトライ後、GitHubServerError発生

    検証項目:
    - 500エラー発生時に指数バックオフでリトライ
    - 3回失敗後にGitHubServerError例外
    - 最終試行後にサーバーエラー情報を保持
    """
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
    assert mock_backoff.call_count == MAX_RETRIES - 1  # MAX_RETRIES試行 → 最終試行以外でバックオフ
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
    """タイムアウト時に再試行後、GitHubAPIError発生

    検証項目:
    - httpx.TimeoutException系 → retry 後に GitHubAPIError 変換
    - retry 回数が max_retries に一致すること
    - 例外チェーン切断（from None）: PII漏洩防止のため __cause__ を抑制
    - 警告ログ出力
    """
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
    """タイムアウト例外メッセージがログフィールド値・例外チェーンに漏洩しないこと検証

    検証項目:
    - httpx.TimeoutException msg内のsensitive文字列(token/URL等)がログ全フィールドに含まれない
    - GitHubAPIError msgにもsensitive文字列が漏洩しない
    - __cause__ chain切断（from None）で Sentry/traceback walker 経由の PII 漏洩を防止
    """
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
    """最終タイムアウト失敗時に非PIIのERRORサマリログを出力する"""
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
    """NetworkError最終リトライ時にERRORレベルで、github_retry_failed がログ出力される。

    最終試行後の、ERRORログ欠落の回帰テスト
    """
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
    """NetworkError/RemoteProtocolError例外メッセージがログフィールド値へ漏洩しないこと検証"""
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
    """LocalProtocolErrorはクライアント側protocol violationのためretry対象外。"""
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


# =============================================================================
# Rate Limit監視テスト
# =============================================================================


@respx.mock
async def test_rate_limit_warning_log():
    """Rate Limit残数が10未満の場合、警告ログ出力

    検証項目:
    - X-RateLimit-Remaining < 10で警告ログ
    - reset_time情報をログに含む
    """
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=200,
        json={"login": "octocat"},
        headers={
            "X-RateLimit-Remaining": "5",  # < 10 → 警告ログトリガー
            "X-RateLimit-Reset": "1640000000",
        },
    )

    async with AsyncGitHubClient() as client:
        with patch.object(client.logger, "warning") as mock_warning:
            await client.get_user("octocat")

            # 警告ログ呼び出し確認（引数順序変更に強い形式）
            mock_warning.assert_called_once_with(
                "rate_limit_low",
                remaining=5,
                reset_time=ANY,
            )

    assert route.call_count == 1  # GETリクエストが1回発行されたことを確認


# =============================================================================
# ETagキャッシュテスト（Conditional Requests）
# =============================================================================


@respx.mock
async def test_etag_cache_hit():
    """ETagキャッシュヒット時304 Not Modified処理

    検証項目:
    - 1回目: 200 + ETag保存 + データキャッシュ保存
    - 2回目: If-None-Matchヘッダー送信 + 304レスポンス
    - 304時はキャッシュデータを返却
    """
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [
        httpx.Response(
            200,
            json={"login": "octocat", "id": 1},
            headers={"ETag": '"abc123"', "X-RateLimit-Remaining": "50"},
        ),
        httpx.Response(304, headers={"X-RateLimit-Remaining": "50"}),
    ]

    async with AsyncGitHubClient() as client:
        user1 = await client.get_user("octocat")
        assert user1["login"] == "octocat"

        # ETag/データキャッシュ確認
        assert "/users/octocat" in client._cache._etag_cache
        assert client._cache._etag_cache["/users/octocat"] == '"abc123"'
        assert "/users/octocat" in client._cache._data_cache
        assert client._cache._data_cache["/users/octocat"] == {"login": "octocat", "id": 1}

        user2 = await client.get_user("octocat")
        assert user2 == {"login": "octocat", "id": 1}  # 304時はキャッシュデータ返却

    assert route.call_count == 2


# =============================================================================
# コンテキストマネージャーテスト
# =============================================================================


async def test_context_manager_initialization():
    """async withコンテキストマネージャーの初期化・終了処理"""
    client = AsyncGitHubClient()
    managed_client: httpx.AsyncClient | None = None
    assert client._client is None

    async with client as ctx_client:
        # __aenter__がself を返す（Self型アノテーション契約）
        assert ctx_client is client
        # __aenter__で_clientが初期化される
        assert ctx_client._client is not None
        assert isinstance(ctx_client._client, httpx.AsyncClient)
        managed_client = ctx_client._client

    # __aexit__でhttpx.AsyncClientがクローズされたことを確認
    assert managed_client is not None
    assert managed_client.is_closed


@pytest.mark.parametrize(
    ("close_exception", "expected_type", "expected_module"),
    [
        (OSError("connection reset"), "OSError", "builtins"),
        (httpx.CloseError("close failed"), "CloseError", "httpx"),
    ],
)
async def test_aexit_aclose_known_exception_is_suppressed_with_warning(
    close_exception: Exception, expected_type: str, expected_module: str
) -> None:
    """__aexit__ で httpx.CloseError / OSError は warning ログのみ出力する。

    既知のクローズ時例外は warning レベルで記録し、body 例外を上書きしない。
    """
    client = AsyncGitHubClient()
    client._client = AsyncMock()
    client._client.aclose = AsyncMock(side_effect=close_exception)

    with capture_logs() as log_output:
        await client.__aexit__(None, None, None)

    known_event = "async_github_client_aclose_failed"
    warning_logs = [log for log in log_output if log.get("event") == known_event]
    assert len(warning_logs) == 1
    assert warning_logs[0]["error_type"] == expected_type
    # third-party 例外起点モジュール識別のため error_module を併用
    assert warning_logs[0]["error_module"] == expected_module
    assert client._client is None
    # 既知例外では error ログは出ない
    unexpected_event = "async_github_client_aclose_unexpected_error"
    error_logs = [log for log in log_output if log.get("event") == unexpected_event]
    assert len(error_logs) == 0
    # else節スキップ検証。aclose() 例外時は __aexit__ の
    # else 節 (utils/github_client.py L291-292) が実行されず "async_github_client_closed"
    # info ログは出力されない設計意図 (test_aexit_normal_close_logs_info L2431 の対照)
    closed_logs = [log for log in log_output if log.get("event") == "async_github_client_closed"]
    assert len(closed_logs) == 0


async def test_aexit_aclose_unexpected_exception_reraises_when_no_body_exception() -> None:
    """__aexit__ で body 例外なし + 予期しない close 例外 → close_exc を re-raise する。
    body 例外がない状態（exc_type is None）では、aclose() の予期しない例外は
    実装バグとして呼び出し元に伝播させる。
    error ログ（has_body_exception=False, exc_info=True）が記録されてから re-raise。
    """
    client = AsyncGitHubClient()
    client._client = AsyncMock()
    client._client.aclose = AsyncMock(side_effect=RuntimeError("close-failed"))

    with pytest.raises(RuntimeError, match="close-failed"), capture_logs() as log_output:
        await client.__aexit__(None, None, None)

    unexpected_event = "async_github_client_aclose_unexpected_error"
    error_logs = [log for log in log_output if log.get("event") == unexpected_event]
    assert len(error_logs) == 1
    assert error_logs[0]["error_type"] == "RuntimeError"
    # third-party 例外起点モジュール識別のため error_module を併用
    assert error_logs[0]["error_module"] == "builtins"
    assert error_logs[0]["has_body_exception"] is False
    # exc_info=True によりスタックトレースが記録される
    assert error_logs[0].get("exc_info") is True
    # 予期しない例外では warning ログは出ない
    known_event = "async_github_client_aclose_failed"
    warning_logs = [log for log in log_output if log.get("event") == known_event]
    assert len(warning_logs) == 0
    # else節スキップ検証。aclose() 例外時は __aexit__ の
    # else 節 (utils/github_client.py L291-292) が実行されず "async_github_client_closed"
    # info ログは出力されない設計意図 (test_aexit_normal_close_logs_info L2431 の対照)
    closed_logs = [log for log in log_output if log.get("event") == "async_github_client_closed"]
    assert len(closed_logs) == 0


async def test_aclose_standalone_success_sets_client_none() -> None:
    """standalone aclose() 正常系 → else 節で _client=None + info ログ

    __aexit__ を経由しない finally 用クローズ経路の直接検証
    """
    client = AsyncGitHubClient()
    client._client = AsyncMock()

    with capture_logs() as log_output:
        await client.aclose()

    # 全経路規約: 正常クローズ後は _client=None（ダブル aclose 防止）
    assert client._client is None
    closed_logs = [log for log in log_output if log.get("event") == "async_github_client_closed"]
    assert len(closed_logs) == 1


async def test_aclose_standalone_known_close_error_warns_and_sets_none() -> None:
    """standalone aclose() で既知の CloseError → warning のみ・re-raise しない・_client=None。"""
    client = AsyncGitHubClient()
    client._client = AsyncMock()
    client._client.aclose = AsyncMock(side_effect=httpx.CloseError("known-close"))

    with capture_logs() as log_output:
        await client.aclose()  # CloseError は warning 化され伝播しない

    assert client._client is None
    warning_logs = [
        log for log in log_output if log.get("event") == "async_github_client_aclose_failed"
    ]
    assert len(warning_logs) == 1
    assert warning_logs[0]["error_type"] == "CloseError"


async def test_aclose_standalone_fatal_reraises_and_sets_none() -> None:
    """standalone aclose() で ASYNC_FATAL（CancelledError）→ _client=None 後 re-raise。"""
    client = AsyncGitHubClient()
    client._client = AsyncMock()
    client._client.aclose = AsyncMock(side_effect=asyncio.CancelledError())

    with pytest.raises(asyncio.CancelledError):
        await client.aclose()

    # 致命例外でも CloseError/else 節と対称に _client=None を設定する
    assert client._client is None


async def test_aclose_standalone_unexpected_is_suppressed() -> None:
    """standalone aclose() で予期しない例外 → 抑制（re-raise しない）・error ログ・_client=None。

    __aexit__ は body 例外なし時に re-raise するが、standalone aclose は伝播中の
    例外を上書きしないよう常に抑制する（AsyncAPIClient.aclose と対称)
    """
    client = AsyncGitHubClient()
    client._client = AsyncMock()
    client._client.aclose = AsyncMock(side_effect=RuntimeError("unexpected-close"))

    with capture_logs() as log_output:
        await client.aclose()  # 抑制されるため例外は伝播しない

    assert client._client is None
    error_logs = [
        log
        for log in log_output
        if log.get("event") == "async_github_client_aclose_unexpected_error"
    ]
    assert len(error_logs) == 1
    assert error_logs[0]["error_type"] == "RuntimeError"
    assert error_logs[0]["action"] == "suppressed_standalone_aclose"


async def test_aclose_standalone_idempotent_when_client_none() -> None:
    """standalone aclose() は _client が既に None なら早期 return（ダブル aclose 冪等性）。"""
    client = AsyncGitHubClient()
    client._client = None

    with capture_logs() as log_output:
        await client.aclose()  # 早期 return — 何も起きない

    assert client._client is None
    # 早期 return のためクローズ系ログは一切出ない
    assert log_output == []


async def test_aexit_body_exception_not_overridden_by_close_exception() -> None:
    """__aexit__ で本体例外発生中に aclose() も予期しない例外を出すケース。

    body 例外 (exc_val) が close 例外で上書きされないこと
    (re-raise しない) を end-to-end で検証する。設計意図:
    ``async with`` body 例外 + aclose 例外の両発生時、原因情報 (body 例外) を
    優先伝播させて debuggability を維持する (CWE-755 例外マスク回避)。
    RuntimeError は予期しない例外ブランチ → error ログ + has_body_exception=True。
    body 例外あり時は close_exc を re-raise しない（二段構え）。
    """
    client = AsyncGitHubClient()

    with pytest.raises(ValueError, match="body-error"), capture_logs() as log_output:
        async with client:
            # __aenter__ で初期化された _client を AsyncMock に差し替えて
            # aclose() を例外化する。
            client._client = AsyncMock()
            client._client.aclose = AsyncMock(side_effect=RuntimeError("close-failed"))
            raise ValueError("body-error")

    # close 例外は re-raise しない。body 例外は ValueError として外側に伝播
    # RuntimeError は予期しない例外 → error ログ (has_body_exception=True)
    unexpected_event = "async_github_client_aclose_unexpected_error"
    error_logs = [log for log in log_output if log.get("event") == unexpected_event]
    assert len(error_logs) == 1
    assert error_logs[0]["error_type"] == "RuntimeError"
    assert error_logs[0]["error_module"] == "builtins"
    assert error_logs[0]["has_body_exception"] is True
    # exc_info=True によりスタックトレースが記録される
    assert error_logs[0].get("exc_info") is True
    # warning ログは出ない
    known_event = "async_github_client_aclose_failed"
    warning_logs = [log for log in log_output if log.get("event") == known_event]
    assert len(warning_logs) == 0
    # else節スキップ検証。body+close 二重例外時も
    # else 節 (utils/github_client.py L291-292) は実行されず "async_github_client_closed"
    # info ログは出力されない (test_aexit_normal_close_logs_info L2431 の対照)。
    closed_logs = [log for log in log_output if log.get("event") == "async_github_client_closed"]
    assert len(closed_logs) == 0


@pytest.mark.parametrize(
    "fatal_exc",
    [MemoryError("OOM"), RecursionError("maximum recursion depth exceeded")],
)
async def test_aexit_fatal_close_exception_propagates_even_with_body_exception(
    fatal_exc: MemoryError | RecursionError,
) -> None:
    """__aexit__ で body 例外併発時でも aclose() の MemoryError / RecursionError は
    握りつぶさず fail-fast で伝播する。

    両者は ``Exception`` 派生（MemoryError は ``Exception`` 直系、RecursionError は
    ``RuntimeError`` 派生）のため ``except Exception`` の has_body_exception 抑制ロジックに
    捕捉されうるが、専用 except 句で先取りし即時 re-raise する設計
    （api_client._close_async_client / sentry_init と同一方針）。
    ``test_aexit_body_exception_not_overridden_by_close_exception``（RuntimeError は
    body 例外保護のため抑制）と対になり、「fatal のみ has_body_exception を貫いて伝播する」
    不変条件を固定する回帰防止テスト。fix 除去時に RED 化する。
    """
    client = AsyncGitHubClient()

    with pytest.raises(type(fatal_exc)), capture_logs() as log_output:
        async with client:
            # __aenter__ で初期化された _client を AsyncMock に差し替えて aclose() を fatal 化。
            client._client = AsyncMock()
            client._client.aclose = AsyncMock(side_effect=fatal_exc)
            raise ValueError("body-error")

    # 専用 except 句が except Exception より先に re-raise するため、
    # unexpected_error（error ログ）も known-exception warning も記録されない。
    unexpected_event = "async_github_client_aclose_unexpected_error"
    error_logs = [log for log in log_output if log.get("event") == unexpected_event]
    assert len(error_logs) == 0
    known_event = "async_github_client_aclose_failed"
    warning_logs = [log for log in log_output if log.get("event") == known_event]
    assert len(warning_logs) == 0
    # aclose 失敗のため else 節（closed ログ）は未到達。
    closed_logs = [log for log in log_output if log.get("event") == "async_github_client_closed"]
    assert len(closed_logs) == 0


async def test_request_without_context_manager():
    """コンテキストマネージャー未使用時にRuntimeError発生"""
    client = AsyncGitHubClient()
    # async withを使わずに直接_requestを呼ぶ
    with pytest.raises(RuntimeError) as exc_info:
        await client._request("GET", "/users/octocat")

    assert "Client not initialized" in str(exc_info.value)
    assert "async with" in str(exc_info.value)


@pytest.mark.parametrize(
    "fatal_exc",
    [
        pytest.param(MemoryError("OOM"), id="memory_error"),
        pytest.param(RecursionError("maximum recursion depth exceeded"), id="recursion_error"),
    ],
)
@respx.mock
async def test_request_etag_cache_fatal_exception_propagates(
    fatal_exc: MemoryError | RecursionError,
) -> None:
    """_update_etag_cache の fatal 例外は GitHubAPIError に変換せず伝播する。"""
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=200,
        json={"login": "octocat"},
        headers={"ETag": '"etag-value"'},
    )

    async with AsyncGitHubClient() as client:
        with (
            patch.object(client._cache, "_update_etag_cache", side_effect=fatal_exc),
            pytest.raises(type(fatal_exc)),
        ):
            await client.get_user("octocat")

    assert route.call_count == 1


@respx.mock
async def test_request_etag_cache_non_fatal_exception_logs_error_and_returns_response() -> None:
    """_update_etag_cache の non-fatal 例外はerrorログを残し、正常レスポンスを返す。"""
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=200,
        json={"login": "octocat"},
        headers={"ETag": '"etag-value"'},
    )

    async with AsyncGitHubClient() as client:
        with (
            patch.object(
                client._cache,
                "_update_etag_cache",
                side_effect=RuntimeError("cache failed"),
            ),
            capture_logs() as logs,
        ):
            result = await client.get_user("octocat")

    assert result == {"login": "octocat"}
    assert route.call_count == 1
    error_logs = [log for log in logs if log.get("event") == "etag_cache_update_failed"]
    assert len(error_logs) == 1
    assert error_logs[0]["log_level"] == "error"
    assert error_logs[0]["error_type"] == "RuntimeError"
    assert error_logs[0]["method"] == "GET"
    assert error_logs[0]["endpoint"] == "/users/octocat"


@respx.mock
async def test_request_uses_composed_helpers_not_temporary_facade_wrappers() -> None:
    """GW3: _request は暫定facade wrapperを経由せず、分割済みhelper/cacheへ直接委譲する。"""
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=200,
        json={"login": "octocat"},
        headers={"ETag": '"etag-value"', "X-RateLimit-Remaining": "50"},
    )

    async with AsyncGitHubClient() as client:
        blocked_wrappers = (
            "_cache_key",
            "_prepare_headers",
            "_parse_rate_limit_header",
            "_check_rate_limit_warning",
            "_parse_json_response",
            "_update_etag_cache",
        )
        for wrapper_name in blocked_wrappers:
            setattr(
                client,
                wrapper_name,
                Mock(side_effect=AssertionError(f"{wrapper_name} wrapper was called")),
            )

        assert await client.get_user("octocat") == {"login": "octocat"}
        assert client._cache._etag_cache["/users/octocat"] == '"etag-value"'

    assert route.call_count == 1


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
    """httpx.HTTPStatusError（4xx）処理の検証"""
    # 401 Unauthorized: respxでステータスコードを返す
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=401,
        headers={"X-RateLimit-Remaining": "60"},
    )

    async with AsyncGitHubClient() as client:
        with pytest.raises(GitHubAPIError) as exc_info:
            await client.get_user("octocat")

    # GitHubAPIError であり、httpx.HTTPStatusError ではないことを明示検証
    assert not isinstance(exc_info.value, httpx.HTTPStatusError)
    # from None による完全PII遮断: __cause__ は None
    assert exc_info.value.__cause__ is None
    # except外raiseパターン: HTTPStatusErrorが__context__に残存しないこと（PII漏洩防止）
    assert exc_info.value.__context__ is None
    assert route.call_count == 1  # エラー時はリトライなし（1回のみ実行）
    # メッセージ形式検証: ボディ除去後の正確なフォーマット確認
    assert str(exc_info.value) == "HTTP 401 error"


@respx.mock
@patch("utils.github_error_handler.exponential_backoff_with_jitter", return_value=0.0)
@patch("utils.github_error_handler.asyncio.sleep", new_callable=AsyncMock)
async def test_httpx_status_error_5xx(mock_sleep: AsyncMock, mock_backoff: Mock) -> None:
    """5xxステータスコード（response.status_code >= 500）リトライパスの検証

    リトライ動作に加え、retrying_server_error ログ出力を検証する。

    検証項目:
    - attempt 値の連続性・順序・件数（list(range(1, MAX_RETRIES)) との等価比較）
    - endpoint / method フィールドの値
      （_handle_5xx_response はリクエストコンテキストを保持）
    - status_code / max_retries / delay フィールドの値
    """
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
    assert mock_backoff.call_count == MAX_RETRIES - 1  # MAX_RETRIES試行 → 最終試行以外でバックオフ
    assert mock_sleep.await_count == MAX_RETRIES - 1

    # リトライ中間試行のログ出力検証
    retry_logs = [log for log in log_output if log.get("event") == "retrying_server_error"]
    assert len(retry_logs) == MAX_RETRIES - 1, (
        f"retrying_server_error ログが{MAX_RETRIES - 1}件を期待 (実際: {len(retry_logs)}件)"
    )
    bad_level = [log for log in retry_logs if log.get("log_level") != "warning"]
    assert not bad_level, f"log_level が warning でないエントリ: {bad_level}"
    # 順序・値・件数の統合検証: リトライがattempt 1〜MAX_RETRIES-1の昇順で実行されること
    actual_attempts = [log_entry.get("attempt") for log_entry in retry_logs]
    assert actual_attempts == list(range(1, MAX_RETRIES)), f"attempt 値不一致: {actual_attempts}"
    # フィールド検証（順序非依存）
    for log_entry in retry_logs:
        assert log_entry["endpoint"] == "/users/octocat"
        assert log_entry["method"] == "GET"
        assert log_entry["status_code"] == 503
        assert log_entry["max_retries"] == MAX_RETRIES
        # delay は @patch(return_value=0.0) のモック値に対応
        assert log_entry["delay"] == 0.0


@respx.mock
@patch("utils.github_error_handler.exponential_backoff_with_jitter", return_value=0.0)
@patch("utils.github_error_handler.asyncio.sleep", new_callable=AsyncMock)
async def test_httpx_status_error_5xx_defensive_path(
    mock_sleep: AsyncMock,
    mock_backoff: Mock,
) -> None:
    """httpx.HTTPStatusError（5xx）防御的コードパスの検証

    C2修正後: httpx.HTTPStatusError として直接 5xx が発生した場合も
    _handle_5xx_response() を経由してリトライし、GitHubServerError を発生させる。

    検証項目:
    - MAX_RETRIES 回リトライ後に GitHubServerError が発生すること
    - route.call_count が MAX_RETRIES であること
    - retrying_server_error ログが MAX_RETRIES - 1 件出力されること
    """
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
    """403レスポンス（Rate Limit超過）が RateLimitError に変換されることの検証

    通常パス: respx.respond(403) で 403 レスポンスを返し、
    _handle_http_status_error → _handle_403_response 経由で RateLimitError が発生する。

    検証項目:
    - 403 + RateLimitヘッダーありで RateLimitError が発生すること
    - reset_time 属性が正しく設定されること
    - リクエストが1回のみ実行されること
    """
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
    """httpx.HTTPStatusError（403・非Rate Limit）防御的コードパスの検証

    防御的パス: Rate Limitヘッダーなしの403をhttpx.HTTPStatusErrorとして受信した場合、
    _handle_403_response() を経由してGitHubAPIError（Access forbidden）を発生させる。

    検証項目:
    - httpx.HTTPStatusError(403・Rate Limitヘッダーなし)がGitHubAPIErrorに変換されること
    - "Access forbidden"メッセージが含まれること
    - リクエストが1回のみ実行されること
    """
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
    """httpx.HTTPStatusError（403・JSONメッセージ付き）防御的コードパスの検証

    防御的パス: Rate Limitヘッダーなし・JSONボディ付き403をhttpx.HTTPStatusErrorとして受信した場合、
    _handle_403_response() を経由して固定文言のGitHubAPIErrorを発生させる。

    検証項目:
    - httpx.HTTPStatusError(403・JSONメッセージ付き)がGitHubAPIErrorに変換されること
    - 外部APIのmessageを含まない固定文言であること
    - リクエストが1回のみ実行されること
    """
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
    """予期しない例外処理の検証"""
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
    assert route.call_count == 1  # エラー時はリトライなし（1回のみ実行）
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
    """ResponseNotRead は unexpected_error に包まずそのまま伝播する"""
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [httpx.ResponseNotRead()]
    async with AsyncGitHubClient() as client:
        with pytest.raises(httpx.ResponseNotRead):
            await client.get_user("octocat")
    assert route.call_count == 1


# =============================================================================
# セキュリティ改善テスト（OWASP A03:2021対策）
# =============================================================================


@pytest.mark.parametrize(
    "username",
    [
        pytest.param("octocat", id="simple_name"),
        pytest.param("user-name", id="hyphen"),
        pytest.param("a", id="single_char"),
        pytest.param("a" * 39, id="max_length"),  # 上限（39文字）
        pytest.param("1user", id="leading_digit"),
        pytest.param("user123", id="digits_in_name"),
        pytest.param("MyUser", id="uppercase"),
    ],
)
def test_username_validation_valid(username: str) -> None:
    """有効なユーザー名でValueError未発生を確認"""
    validate_github_username(username)


async def test_username_validation_invalid():
    """無効なユーザー名でValueError発生（Path Traversal防止）"""
    async with AsyncGitHubClient() as client:
        # Path Traversal攻撃パターン
        with pytest.raises(ValueError, match="Invalid GitHub username"):
            await client.get_user("../../../etc/passwd")

        # 空文字列
        with pytest.raises(ValueError, match="Invalid GitHub username"):
            await client.get_user("")

        # 40文字超過
        with pytest.raises(ValueError, match="Invalid GitHub username"):
            await client.get_user("a" * 40)


@respx.mock
async def test_403_non_rate_limit():
    """403エラー（Rate Limit以外）でGitHubAPIError発生"""
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [
        httpx.Response(
            403,
            json={"message": "Repository access blocked"},
            headers={"X-RateLimit-Remaining": "50"},
        ),
        httpx.Response(
            403,
            json={"message": "Repository access blocked"},
            headers={"X-RateLimit-Remaining": "50"},
        ),
    ]

    async with AsyncGitHubClient() as client:
        with pytest.raises(GitHubAPIError, match="Access forbidden"):
            await client.get_user("octocat")

        # 2回目: GitHubAPIErrorが発生し、RateLimitErrorではないことを確認
        with pytest.raises(GitHubAPIError, match="Access forbidden") as exc_info:
            await client.get_user("octocat")
        assert not isinstance(exc_info.value, RateLimitError)


@respx.mock
async def test_json_decode_error():
    """JSONパース失敗時にGitHubAPIError発生"""
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

    assert route.call_count == 1  # GETリクエストが1回発行されたことを確認
    decode_logs = [log for log in logs if log.get("event") == "json_decode_error"]
    assert len(decode_logs) == 1
    assert decode_logs[0]["endpoint"] == "/users/octocat"
    assert "error" not in decode_logs[0]
    assert decode_logs[0]["error_type"] == json.JSONDecodeError.__qualname__
    assert decode_logs[0]["error_module"] == json.JSONDecodeError.__module__
    assert isinstance(decode_logs[0]["error_pos"], int)
    assert isinstance(decode_logs[0]["error_lineno"], int)


@respx.mock
async def test_get_user_type_guard_rejects_non_dict():
    """get_user: APIが非dictレスポンスを返した場合にGitHubAPIErrorを発生"""
    respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=200,
        json=[{"id": 1}],  # list instead of dict
        headers={"X-RateLimit-Remaining": "50"},
    )
    async with AsyncGitHubClient() as client:
        with pytest.raises(GitHubAPIError, match="Expected dict response, got list"):
            await client.get_user("octocat")


@respx.mock
async def test_get_repos_type_guard_rejects_non_list():
    """get_repos: APIが非listレスポンスを返した場合にGitHubAPIErrorを発生"""
    respx.get(f"{GITHUB_API_BASE_URL}/users/octocat/repos").respond(
        status_code=200,
        json={"id": 1},  # dict instead of list
        headers={"X-RateLimit-Remaining": "50"},
    )
    async with AsyncGitHubClient() as client:
        with pytest.raises(GitHubAPIError, match="Expected list response, got dict"):
            await client.get_repos("octocat")


@respx.mock
async def test_get_repo_type_guard_rejects_non_dict():
    """get_repo: APIが非dictレスポンスを返した場合にGitHubAPIErrorを発生"""
    respx.get(f"{GITHUB_API_BASE_URL}/repos/octocat/Hello-World").respond(
        status_code=200,
        json=[{"id": 1}],  # list instead of dict
        headers={"X-RateLimit-Remaining": "50"},
    )
    async with AsyncGitHubClient() as client:
        with pytest.raises(GitHubAPIError, match="Expected dict response, got list"):
            await client.get_repo("octocat", "Hello-World")


# =============================================================================
# システム例外伝播テスト
# =============================================================================
# KeyboardInterruptはpytest自体がSIGINTハンドラとして処理するためunitテストでの検証は省略
# SystemExit / MemoryError / CancelledError の3種で例外伝播パスをカバー


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


# =============================================================================
# Rate Limitヘッダー不正値テスト
# =============================================================================


@respx.mock
async def test_invalid_rate_limit_header_remaining():
    """X-RateLimit-Remaining に不正値が含まれる場合、warningログ出力して処理継続

    検証項目:
    - ValueError が外部に伝播しないこと（正常完了）
    - invalid_rate_limit_header warning ログが出力されること
    - header/value フィールドがログに含まれること
    """
    respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=200,
        json={"login": "octocat"},
        headers={"X-RateLimit-Remaining": "N/A"},
    )

    with capture_logs() as log_output:
        async with AsyncGitHubClient() as client:
            result = await client.get_user("octocat")

    assert result["login"] == "octocat"
    warning_logs = [log for log in log_output if log.get("event") == "invalid_rate_limit_header"]
    assert len(warning_logs) == 1
    assert warning_logs[0]["log_level"] == "warning"
    assert warning_logs[0]["header"] == "X-RateLimit-Remaining"
    assert warning_logs[0]["value"] == repr("N/A")


@respx.mock
async def test_invalid_rate_limit_header_403():
    """403応答時にX-RateLimit-Remainingが不正値の場合、warningログ後 GitHubAPIError 発生

    検証項目:
    - フォールバック -1 により rate_remaining == 0 は偽 → GitHubAPIError("Access forbidden") が発生
    - invalid_rate_limit_header warning ログが1件出力されること
      （X-RateLimit-Remainingの二重パースを避ける）
    - header/value フィールドがログに含まれること
    """
    respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=403,
        json={"message": "Forbidden"},
        headers={"X-RateLimit-Remaining": "invalid"},
    )

    with capture_logs() as log_output:
        async with AsyncGitHubClient() as client:
            with pytest.raises(GitHubAPIError):
                await client.get_user("octocat")

    warning_logs = [log for log in log_output if log.get("event") == "invalid_rate_limit_header"]
    assert len(warning_logs) == 1
    for log_entry in warning_logs:
        assert log_entry["log_level"] == "warning"
        assert log_entry["header"] == "X-RateLimit-Remaining"
        assert log_entry["value"] == repr("invalid")


@respx.mock
async def test_invalid_rate_limit_reset_header_low_remaining():
    """remaining<10かつX-RateLimit-Resetが不正値の場合、2つのwarningログを出力して処理継続

    検証項目:
    - ValueError が外部に伝播しないこと（正常完了）
    - invalid_rate_limit_header warning ログが出力されること
      （header="X-RateLimit-Reset", value="not-a-timestamp"）
    - rate_limit_low warning ログが出力されること（remaining=5）
    - reset_time はフォールバック値（epoch: 1970-01-01T00:00:00+00:00）になること
    """
    respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=200,
        json={"login": "octocat"},
        headers={
            "X-RateLimit-Remaining": "5",
            "X-RateLimit-Reset": "not-a-timestamp",
        },
    )

    with capture_logs() as log_output:
        async with AsyncGitHubClient() as client:
            result = await client.get_user("octocat")

    assert result["login"] == "octocat"

    # invalid_rate_limit_header warning（X-RateLimit-Reset不正値）
    invalid_header_logs = [
        log for log in log_output if log.get("event") == "invalid_rate_limit_header"
    ]
    assert len(invalid_header_logs) == 1
    assert invalid_header_logs[0]["log_level"] == "warning"
    assert invalid_header_logs[0]["header"] == "X-RateLimit-Reset"
    assert invalid_header_logs[0]["value"] == repr("not-a-timestamp")

    # rate_limit_low warning（remaining=5 < 10）
    rate_limit_low_logs = [log for log in log_output if log.get("event") == "rate_limit_low"]
    assert len(rate_limit_low_logs) == 1
    assert rate_limit_low_logs[0]["log_level"] == "warning"
    assert rate_limit_low_logs[0]["remaining"] == 5
    # フォールバック: reset_time=0 → epoch（1970-01-01T00:00:00+00:00）
    expected_reset_time = datetime(1970, 1, 1, 0, 0, tzinfo=UTC).isoformat()
    assert rate_limit_low_logs[0]["reset_time"] == expected_reset_time


@respx.mock
async def test_invalid_rate_limit_reset_header_rate_limit_exceeded():
    """rate_remaining==0かつX-RateLimit-Resetが不正値の場合、警告ログ後RateLimitError発生

    検証項目:
    - RateLimitError が発生すること（rate_remaining==0のため）
    - invalid_rate_limit_header warning ログが1件出力されること
      （共通remaining<10チェックパスのX-RateLimit-Resetパース結果を再利用する）
    - rate_limit_low warning ログが1件出力されること（remaining=0 < 10）
    - header="X-RateLimit-Reset", value="broken" がログに含まれること
    """
    respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=403,
        json={"message": "Forbidden"},
        headers={
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": "broken",
        },
    )

    with capture_logs() as log_output:
        async with AsyncGitHubClient() as client:
            with pytest.raises(RateLimitError):
                await client.get_user("octocat")

    # invalid_rate_limit_header warningは共通パスで1件のみ（resetヘッダー二重パース回避）
    invalid_header_logs = [
        log for log in log_output if log.get("event") == "invalid_rate_limit_header"
    ]
    assert len(invalid_header_logs) == 1
    for log_entry in invalid_header_logs:
        assert log_entry["log_level"] == "warning"
        assert log_entry["header"] == "X-RateLimit-Reset"
        assert log_entry["value"] == repr("broken")

    # rate_limit_low warningが1件（remaining=0 < 10）
    rate_limit_low_logs = [log for log in log_output if log.get("event") == "rate_limit_low"]
    assert len(rate_limit_low_logs) == 1
    assert rate_limit_low_logs[0]["log_level"] == "warning"
    assert rate_limit_low_logs[0]["remaining"] == 0
    # フォールバック: reset_time=0 → epoch（1970-01-01T00:00:00+00:00）
    expected_reset_time = datetime(1970, 1, 1, 0, 0, tzinfo=UTC).isoformat()
    assert rate_limit_low_logs[0]["reset_time"] == expected_reset_time


# =============================================================================
# validate_github_repo バリデーションテスト
# =============================================================================


@pytest.mark.parametrize(
    "repo",
    [
        pytest.param("my-repo", id="hyphen"),
        pytest.param("a", id="single_char"),
        pytest.param("a" * 100, id="max_length"),  # 上限（100文字）
        pytest.param("my_repo", id="underscore"),
        pytest.param("my.repo", id="dot"),
        pytest.param(".github", id="github_special_repository"),
        pytest.param("123", id="digits_only"),
    ],
)
def test_repo_validation_valid(repo: str) -> None:
    """有効なリポジトリ名でValueError未発生を確認"""
    validate_github_repo(repo)


@pytest.mark.parametrize(
    "repo",
    [
        pytest.param("../etc/passwd", id="path_traversal"),
        pytest.param("a" * 101, id="too_long"),
        pytest.param("", id="empty_string"),
        pytest.param("repo name!", id="special_chars"),
        pytest.param("repo\x00name", id="null_byte"),
        pytest.param(".", id="dot_single"),
        pytest.param("..", id="dot_double"),
    ],
)
def test_repo_validation_invalid(repo: str) -> None:
    """無効なリポジトリ名でValueError発生（セキュリティ境界テスト）"""
    with pytest.raises(ValueError, match="Invalid GitHub repository name"):
        validate_github_repo(repo)


# ── D-07 追加: _prepare_headers / _handle_304 / _handle_403 / _update_etag_cache ──


def test_sanitized_jsondecodeerror_str_contains_no_response_body() -> None:
    """SanitizedJSONDecodeError.__str__() は型・位置情報のみで body を含まない

    現状の PII 漏洩防止は __cause__ チェーン切断（__context__=None）に依存するが、
    __str__ 出力自体が response body を構造的に保持しないことを直接検証し、
    将来のフォーマット変更による回帰を検出する。
    """
    cause = SanitizedJSONDecodeError(
        "json.JSONDecodeError",
        msg="Expecting value",
        pos=42,
        lineno=3,
        colno=7,
    )

    rendered = str(cause)
    # 型・msg・位置情報のみが厳密に含まれる（body 由来の文字列を混入させる余地がない）。
    # msg は json.JSONDecodeError.msg（静的パーサ診断文字列）で PII 非含有
    assert rendered == "json.JSONDecodeError: Expecting value pos=42, lineno=3, colno=7"
    assert cause.msg == "Expecting value"  # 破損種別識別用 msg を保持
    assert cause.pos == 42
    assert cause.lineno == 3
    assert cause.colno == 7  # 診断用 colno を保持
    # 仮にレスポンス body 由来の機密文字列があっても __str__ には現れない
    assert "password" not in rendered
    assert "token" not in rendered


def test_sanitized_jsondecodeerror_reduce_roundtrip_preserves_fields() -> None:
    """SanitizedJSONDecodeError は __reduce__ で全フィールドを復元可能

    非標準 __init__ シグネチャ（5 引数）のため __reduce__ を実装。pytest-xdist の
    worker→controller 例外転送や Sentry SDK シリアライズが依存する pickle プロトコル
    の契約（``cls(*args)`` で再構築可能）を直接検証する。pickle.loads は CWE-502 回避の
    ため使わず、__reduce__ の戻り値から手動で再構築して TypeError にならないことを保証する。
    """
    original = SanitizedJSONDecodeError(
        "json.JSONDecodeError",
        msg="Expecting value",
        pos=42,
        lineno=3,
        colno=7,
    )

    cls, args = original.__reduce__()
    restored = cls(*args)

    assert isinstance(restored, SanitizedJSONDecodeError)
    assert restored.error_type == "json.JSONDecodeError"
    assert restored.msg == "Expecting value"
    assert restored.pos == 42
    assert restored.lineno == 3
    assert restored.colno == 7
    assert str(restored) == str(original)


@respx.mock
async def test_429_response_raises_rate_limit_error() -> None:
    """429 Too Many RequestsはRateLimitErrorに変換される（_requestレベル・通常パス）

    GitHub Secondary Rate LimitはHTTP 429を返す。_requestは429を検出し、
    X-RateLimit-ResetヘッダーからリセットタイムをパースしてRateLimitErrorを発生させる。
    """
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        429,
        headers={"X-RateLimit-Reset": "1700000000"},
    )

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.reset_time == 1700000000
    assert route.call_count == 1


@respx.mock
async def test_httpx_status_error_429_defensive_path() -> None:
    """429レスポンスが RateLimitError に変換されることの検証

    通常パス: respx.respond(429) で 429 レスポンスを返し、
    _handle_http_status_error 経由で RateLimitError が発生する。

    検証項目:
    - 429 + X-RateLimit-Reset ヘッダーありで RateLimitError が発生すること
    - reset_time 属性が正しく設定されること
    - リクエストが1回のみ実行されること
    """
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        429,
        headers={"X-RateLimit-Reset": "1640000000"},
    )

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.__context__ is None  # active exception context 外 raise による PII 防止
    assert exc_info.value.reset_time == 1640000000
    assert "Rate limit exceeded" in str(exc_info.value)
    assert route.call_count == 1


@respx.mock
async def test_429_response_missing_reset_header_falls_back_to_zero() -> None:
    """X-RateLimit-Resetヘッダー欠損時は reset_time=0 にフォールバックする（通常パス）"""
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(429)

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.reset_time == 0
    assert "unknown" in str(exc_info.value)  # else分岐のメッセージ内容を保護
    assert route.call_count == 1


@respx.mock
async def test_httpx_status_error_429_missing_reset_header_falls_back_to_zero() -> None:
    """X-RateLimit-Resetヘッダー欠損時は reset_time=0 にフォールバックする（防御的パス）"""
    request = httpx.Request("GET", f"{GITHUB_API_BASE_URL}/users/octocat")
    response_429 = httpx.Response(429, request=request)
    error_429 = httpx.HTTPStatusError(
        "429 Too Many Requests", request=request, response=response_429
    )

    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [error_429]

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.reset_time == 0
    assert "unknown" in str(exc_info.value)  # else分岐のメッセージ内容を保護
    assert route.call_count == 1


@respx.mock
async def test_httpx_status_error_403_defensive_path_uses_rate_limit_headers() -> None:
    """403の防御的パスでも RateLimitError 判定と reset_time を通常パスに揃える。"""
    request = httpx.Request("GET", f"{GITHUB_API_BASE_URL}/users/octocat")
    response_403 = httpx.Response(
        403,
        headers={
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": "1700000000",
        },
        request=request,
    )
    error_403 = httpx.HTTPStatusError("403 Forbidden", request=request, response=response_403)

    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [error_403]

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.reset_time == 1700000000
    assert exc_info.value.__context__ is None
    assert route.call_count == 1


@respx.mock
async def test_httpx_status_error_404_defensive_path_raises_not_found_error() -> None:
    """404の防御的パスでも NotFoundError に揃うことを確認する"""
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


# =============================================================================
# _cache_key テスト（ETagキャッシュキーにクエリパラメータを含める）
# =============================================================================


@respx.mock
async def test_etag_cache_key_includes_query_params() -> None:
    """get_repos() の sort/per_page が異なると異なるキャッシュキーを使用する

    1回目: sort=updated, per_page=30 → 200 + ETag保存
    2回目: sort=created, per_page=10 → 200 (別キーでキャッシュヒットせず)
    """
    updated_route = respx.get(
        f"{GITHUB_API_BASE_URL}/users/octocat/repos",
        params={"sort": "updated", "per_page": "30"},
    )
    created_route = respx.get(
        f"{GITHUB_API_BASE_URL}/users/octocat/repos",
        params={"sort": "created", "per_page": "10"},
    )
    updated_route.side_effect = [
        httpx.Response(
            200,
            json=[{"name": "repo-a", "pushed_at": "2025-01-01"}],
            headers={"ETag": '"updated-etag"', "X-RateLimit-Remaining": "50"},
        ),
        httpx.Response(304, headers={"X-RateLimit-Remaining": "50"}),
    ]
    created_route.respond(
        200,
        json=[{"name": "repo-b", "created_at": "2024-01-01"}],
        headers={"ETag": '"created-etag"', "X-RateLimit-Remaining": "50"},
    )

    async with AsyncGitHubClient() as client:
        repos1 = await client.get_repos("octocat", sort="updated", per_page=30)
        assert repos1[0]["name"] == "repo-a"

        repos2 = await client.get_repos("octocat", sort="created", per_page=10)
        assert repos2[0]["name"] == "repo-b"

        # 再度 updated を呼ぶと304キャッシュが返る
        repos3 = await client.get_repos("octocat", sort="updated", per_page=30)
        assert repos3[0]["name"] == "repo-a"

    assert updated_route.call_count == 2  # 200 + 304
    assert created_route.call_count == 1  # 200 only
    # 2回目リクエスト (304条件付き) で If-None-Match ヘッダーが正しく送出されている
    second_request = updated_route.calls[1].request
    assert "if-none-match" in second_request.headers
    assert second_request.headers["if-none-match"] == '"updated-etag"'


@respx.mock
async def test_304_returns_correct_cached_data_per_params() -> None:
    """sort 違いのキャッシュが混ざらないこと

    1. sort=updated → 200, data=[repo-updated]
    2. sort=created → 200, data=[repo-created]
    3. sort=updated → 304, data=[repo-updated] (not repo-created)
    """
    octocat_base = f"{GITHUB_API_BASE_URL}/users/octocat/repos"

    updated_route = respx.get(octocat_base, params={"sort": "updated", "per_page": "30"})
    created_route = respx.get(octocat_base, params={"sort": "created", "per_page": "30"})

    updated_route.side_effect = [
        httpx.Response(
            200,
            json=[{"name": "repo-updated"}],
            headers={"ETag": '"updated"', "X-RateLimit-Remaining": "50"},
        ),
        httpx.Response(304, headers={"X-RateLimit-Remaining": "50"}),
    ]
    created_route.side_effect = [
        httpx.Response(
            200,
            json=[{"name": "repo-created"}],
            headers={"ETag": '"created"', "X-RateLimit-Remaining": "50"},
        ),
    ]

    async with AsyncGitHubClient() as client:
        r1 = await client.get_repos("octocat", sort="updated", per_page=30)
        assert r1[0]["name"] == "repo-updated"

        r2 = await client.get_repos("octocat", sort="created", per_page=30)
        assert r2[0]["name"] == "repo-created"

        # 304 → updated のキャッシュが返るべき
        r3 = await client.get_repos("octocat", sort="updated", per_page=30)
        assert r3[0]["name"] == "repo-updated"

    assert updated_route.call_count == 2
    assert created_route.call_count == 1


@pytest.mark.parametrize(
    "invalid_value",
    [
        pytest.param(0, id="zero"),
        pytest.param(-1, id="negative_one"),
        pytest.param(-100, id="negative_hundred"),
    ],
)
def test_async_github_client_max_cache_entries_validation(invalid_value: int) -> None:
    """AsyncGitHubClient: max_cache_entries が 1 未満の値で ValueError を送出する

    max_cache_entries=0 / -1 / -100 はいずれも不正値であり、
    "max_cache_entries must be >= 1" メッセージの ValueError を発生させる。
    """
    with pytest.raises(ValueError, match="max_cache_entries must be >= 1"):
        AsyncGitHubClient(max_cache_entries=invalid_value)


def test_async_github_client_max_cache_entries_delegates_to_cache() -> None:
    """max_cache_entries は GitHubETagCache への委譲であり、facade 側で値を持たない。

    分割後のミラーテストは cache を直接検証するため、client -> cache の委譲の継ぎ目
    （github_client.py の property）だけがテストの死角になりうる。ここで固定する。
    """
    client = AsyncGitHubClient(max_cache_entries=7)

    assert client.max_cache_entries == 7
    assert client.max_cache_entries == client._cache.max_cache_entries


async def test_aexit_normal_close_logs_info() -> None:
    """__aexit__ 正常クローズ時に "async_github_client_closed" の info ログが1回出力される

    aclose() が例外なく完了した場合（else 節）に structlog の info ログが記録されることを
    capture_logs で検証する。
    """
    with capture_logs() as log_output:
        async with AsyncGitHubClient():
            pass  # 正常終了

    closed_logs = [log for log in log_output if log.get("event") == "async_github_client_closed"]
    assert len(closed_logs) == 1
    assert closed_logs[0]["log_level"] == "info"


# =============================================================================
# _check_rate_limit_warning: 異常 reset_time フォールバックテスト
# =============================================================================


@respx.mock
async def test_check_rate_limit_warning_overflow_reset_time() -> None:
    """_check_rate_limit_warning: 極端に大きい X-RateLimit-Reset でも例外が伝播しないこと

    検証項目:
    - OverflowError/OSError が呼び出し元に伝播しないこと（正常完了）
    - rate_limit_low warning ログが1件出力されること
    - reset_time ログフィールドが "unix:{reset_time}" 形式のフォールバック文字列になること
    - 戻り値（_request 内での reset_time）は元の int 値が保持されること
      （result["login"] が正常取得できることで間接確認）

    既存パターン準拠:
    - RateLimitError.__init__ の try/except (OverflowError, OSError) と同じ保護
    - フォールバック形式 "unix:{reset_time}" は L130 と完全一致
    """
    # 2**63 はほとんどのプラットフォームで datetime.fromtimestamp が
    # OverflowError または OSError を送出する値
    overflow_reset: int = 2**63

    respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=200,
        json={"login": "octocat"},
        headers={
            "X-RateLimit-Remaining": "5",  # < 10 → _check_rate_limit_warning 実行
            "X-RateLimit-Reset": str(overflow_reset),
        },
    )

    with capture_logs() as log_output:
        async with AsyncGitHubClient() as client:
            # 例外が伝播しないことを確認（正常完了）
            result = await client.get_user("octocat")

    # (3) 戻り値: 正常取得できること
    assert result["login"] == "octocat"

    # (1) 例外が伝播しないこと → ここまで到達できれば検証済み

    # (2) rate_limit_low warning ログが1件出力されること
    rate_limit_low_logs = [log for log in log_output if log.get("event") == "rate_limit_low"]
    assert len(rate_limit_low_logs) == 1
    assert rate_limit_low_logs[0]["log_level"] == "warning"
    assert rate_limit_low_logs[0]["remaining"] == 5

    # (2) reset_time フィールドが "unix:{reset_time}" フォールバック形式になること
    assert rate_limit_low_logs[0]["reset_time"] == f"unix:{overflow_reset}"


# =============================================================================
# _cache_key エラーパステスト（Fix #12-Q-9）
# =============================================================================


# =============================================================================
# _check_rate_limit_warning: 閾値インタラクションテスト（Fix #10-QC-3）
# =============================================================================


# =============================================================================
# 429 E2E test with warning_reset_time handoff（Fix #15-Q-6）
# =============================================================================


@respx.mock
async def test_429_uses_warning_reset_time_from_rate_limit_check() -> None:
    """429 応答受信時に _check_rate_limit_warning が返した warning_reset_time を
    RateLimitError の reset_time として使用することを検証する。

    フロー:
    1. X-RateLimit-Remaining=5（閾値未満）→ _check_rate_limit_warning が reset_time を返す
    2. 429 応答 → warning_reset_time が非 None なので X-RateLimit-Reset の再パースを省略
    3. RateLimitError(reset_time) が発生
    """
    expected_reset_time = 1700000999
    respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        429,
        headers={
            "X-RateLimit-Remaining": "5",  # < 10 → _check_rate_limit_warning が実行される
            "X-RateLimit-Reset": str(expected_reset_time),
        },
    )

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.reset_time == expected_reset_time
    assert exc_info.value.__cause__ is None  # from None で PII 漏洩防止
