"""
GitHub API非同期クライアントのUnit Tests

テスト戦略:
- respxを使用してGitHub APIの依存を排除（HTTPレイヤーモック）
- 正常系・異常系・エッジケースを網羅
- カバレッジ目標: 80%以上
"""

import asyncio
import json
import re
from datetime import UTC, datetime
from unittest.mock import ANY, AsyncMock, Mock, call, patch

import httpx
import pytest
import respx
from structlog.testing import capture_logs

from utils.github_client import (
    AsyncGitHubClient,
    GitHubAPIError,
    GitHubServerError,
    NotFoundError,
    RateLimitError,
    _redact_body_preview,
    _SanitizedJSONDecodeError,
    validate_github_repo,
    validate_github_username,
)

pytestmark = pytest.mark.unit
# @pytest.mark.asyncio: asyncio_mode = "auto" (pyproject.toml) のため、@pytest.mark.asyncio は不要
# pytest-asyncio が async テストを自動検出する

GITHUB_API_BASE_URL = "https://api.github.com"
MAX_RETRIES = 3

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
@patch("utils.github_client.exponential_backoff_with_jitter", return_value=0.0)
@patch("utils.github_client.asyncio.sleep", new_callable=AsyncMock)
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
        "utils.github_client.exponential_backoff_with_jitter",
        return_value=0.0,
    ) as mock_backoff:
        with patch("utils.github_client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
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
    sensitive_detail = "https://api.example.com/internal?token=SECRET_API_KEY_12345"
    timeout_exception = httpx.ConnectTimeout(sensitive_detail)
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").mock(side_effect=timeout_exception)

    with patch(
        "utils.github_client.exponential_backoff_with_jitter",
        return_value=0.0,
    ) as mock_backoff:
        with patch("utils.github_client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
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
    timeout_exception = httpx.ConnectTimeout("https://example.com?token=secret")
    respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").mock(side_effect=timeout_exception)

    with patch(
        "utils.github_client.exponential_backoff_with_jitter",
        return_value=0.0,
    ):
        with patch("utils.github_client.asyncio.sleep", new_callable=AsyncMock):
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
        "utils.github_client.exponential_backoff_with_jitter",
        return_value=0.0,
    ) as mock_backoff:
        with patch("utils.github_client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
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
    """NetworkError最終リトライ時にERRORレベルで github_retry_failed がログ出力される。

    PR#347 review fix #3: 最終試行後の ERROR ログ欠落の回帰テスト。
    """
    respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").mock(side_effect=network_exception)

    with patch(
        "utils.github_client.exponential_backoff_with_jitter",
        return_value=0.0,
    ):
        with patch("utils.github_client.asyncio.sleep", new_callable=AsyncMock):
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
    sensitive_detail = "https://api.example.com/internal?token=SECRET_API_KEY_12345"
    transport_exception = exception_class(sensitive_detail)
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").mock(side_effect=transport_exception)

    with patch(
        "utils.github_client.exponential_backoff_with_jitter",
        return_value=0.0,
    ) as mock_backoff:
        with patch("utils.github_client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
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
    sensitive_detail = "https://api.example.com/internal?token=SECRET_API_KEY_12345"
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
        assert "/users/octocat" in client._etag_cache
        assert client._etag_cache["/users/octocat"] == '"abc123"'
        assert "/users/octocat" in client._data_cache
        assert client._data_cache["/users/octocat"] == {"login": "octocat", "id": 1}

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
    """__aexit__ で httpx.CloseError / OSError は warning ログのみ出力する（PR#347 #18）。

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
    # PR#347 review Q2: third-party 例外起点モジュール識別のため error_module を併用
    assert warning_logs[0]["error_module"] == expected_module
    assert client._client is None
    # 既知例外では error ログは出ない
    unexpected_event = "async_github_client_aclose_unexpected_error"
    error_logs = [log for log in log_output if log.get("event") == unexpected_event]
    assert len(error_logs) == 0
    # PR#347 review #3-1: else節スキップ検証。aclose() 例外時は __aexit__ の
    # else 節 (utils/github_client.py L291-292) が実行されず "async_github_client_closed"
    # info ログは出力されない設計意図 (test_aexit_normal_close_logs_info L2431 の対照)。
    closed_logs = [log for log in log_output if log.get("event") == "async_github_client_closed"]
    assert len(closed_logs) == 0


async def test_aexit_aclose_unexpected_exception_reraises_when_no_body_exception() -> None:
    """__aexit__ で body 例外なし + 予期しない close 例外 → close_exc を re-raise する。

    （PR#347 二段構え）

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
    # PR#347 review Q2: third-party 例外起点モジュール識別のため error_module を併用
    assert error_logs[0]["error_module"] == "builtins"
    assert error_logs[0]["has_body_exception"] is False
    # exc_info=True によりスタックトレースが記録される（PR#347 二段構え）
    assert error_logs[0].get("exc_info") is True
    # 予期しない例外では warning ログは出ない
    known_event = "async_github_client_aclose_failed"
    warning_logs = [log for log in log_output if log.get("event") == known_event]
    assert len(warning_logs) == 0
    # PR#347 review #3-1: else節スキップ検証。aclose() 例外時は __aexit__ の
    # else 節 (utils/github_client.py L291-292) が実行されず "async_github_client_closed"
    # info ログは出力されない設計意図 (test_aexit_normal_close_logs_info L2431 の対照)。
    closed_logs = [log for log in log_output if log.get("event") == "async_github_client_closed"]
    assert len(closed_logs) == 0


async def test_aclose_standalone_success_sets_client_none() -> None:
    """standalone aclose() 正常系 → else 節で _client=None + info ログ。

    （PR#347 SF-3: __aexit__ を経由しない finally 用クローズ経路の直接検証）
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
    例外を上書きしないよう常に抑制する（AsyncAPIClient.aclose と対称, PR#347 SF-3）。
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

    PR#347 review Q8: body 例外 (exc_val) が close 例外で上書きされないこと
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

    # close 例外は re-raise しない。body 例外は ValueError として外側に伝播。
    # RuntimeError は予期しない例外 → error ログ (has_body_exception=True)
    unexpected_event = "async_github_client_aclose_unexpected_error"
    error_logs = [log for log in log_output if log.get("event") == unexpected_event]
    assert len(error_logs) == 1
    assert error_logs[0]["error_type"] == "RuntimeError"
    assert error_logs[0]["error_module"] == "builtins"
    assert error_logs[0]["has_body_exception"] is True
    # exc_info=True によりスタックトレースが記録される（PR#347 二段構え）
    assert error_logs[0].get("exc_info") is True
    # warning ログは出ない
    known_event = "async_github_client_aclose_failed"
    warning_logs = [log for log in log_output if log.get("event") == known_event]
    assert len(warning_logs) == 0
    # PR#347 review #3-1: else節スキップ検証。body+close 二重例外時も
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
            patch.object(client, "_update_etag_cache", side_effect=fatal_exc),
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
            patch.object(client, "_update_etag_cache", side_effect=RuntimeError("cache failed")),
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
@patch("utils.github_client.exponential_backoff_with_jitter", return_value=0.0)
@patch("utils.github_client.asyncio.sleep", new_callable=AsyncMock)
async def test_httpx_status_error_5xx(mock_sleep: AsyncMock, mock_backoff: Mock) -> None:
    """5xxステータスコード（response.status_code >= 500）リトライパスの検証

    リトライ動作に加え、retrying_server_error ログ出力を検証する（Issue #229）。

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

    # リトライ中間試行のログ出力検証（Issue #229）
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
@patch("utils.github_client.exponential_backoff_with_jitter", return_value=0.0)
@patch("utils.github_client.asyncio.sleep", new_callable=AsyncMock)
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
    _handle_403_response() を経由してGitHubAPIError（Access forbidden: {msg}）を発生させる。

    検証項目:
    - httpx.HTTPStatusError(403・JSONメッセージ付き)がGitHubAPIErrorに変換されること
    - "Access forbidden: {message}"形式のメッセージが含まれること
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
        with pytest.raises(GitHubAPIError, match="Access forbidden: Resource not accessible"):
            await client.get_user("octocat")

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
# システム例外伝播テスト（Issue #222）
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
# Rate Limitヘッダー不正値テスト（Issue #230）
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


def test_missing_rate_limit_header_returns_default_without_warning() -> None:
    """Rate Limitヘッダー未設定時はwarningなしでdefaultを返す。"""
    client = AsyncGitHubClient()

    with capture_logs() as log_output:
        result = client._parse_rate_limit_header(
            httpx.Headers(),
            "X-RateLimit-Remaining",
            999,
        )

    assert result == 999
    assert not [log for log in log_output if log.get("event") == "invalid_rate_limit_header"]


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


# =============================================================================
# ハンドラメソッド直接テスト（D-07: 複雑ハンドラ unit test）
# =============================================================================


@pytest.mark.parametrize(
    ("remaining_header", "reset_header", "json_body", "expected_exc", "match"),
    [
        pytest.param(
            "0",
            "1700000000",
            None,
            RateLimitError,
            None,
            id="rate_limit_exceeded",
        ),
        pytest.param(
            "50",
            "0",
            {"message": "Blocked"},
            GitHubAPIError,
            "Blocked",
            id="non_rate_limit_with_message",
        ),
        pytest.param(
            "50",
            "0",
            None,
            GitHubAPIError,
            "Access forbidden",
            id="non_rate_limit_no_json",
        ),
        pytest.param(
            "invalid",
            "0",
            None,
            GitHubAPIError,
            "Access forbidden",
            id="invalid_header_fallback",
        ),
        pytest.param(
            "50",
            "0",
            {"message": 999},
            GitHubAPIError,
            "^Access forbidden$",
            id="non_str_message_field",
        ),
    ],
)
def test_handle_403_response(
    remaining_header: str,
    reset_header: str,
    json_body: dict | None,
    expected_exc: type[Exception],
    match: str | None,
) -> None:
    """_handle_403_response の5パステスト（D-07）

    - rate_limit_exceeded: remaining=0 → RateLimitError
    - non_rate_limit_with_message: remaining=50 + JSON message → GitHubAPIError(message)
    - non_rate_limit_no_json: remaining=50 + 非JSON → GitHubAPIError
    - invalid_header_fallback: remaining=invalid → フォールバック(-1) → GitHubAPIError
    - non_str_message_field: remaining=50 + JSON message(非str) → GitHubAPIError
    """
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    # 403レスポンスを構築
    headers = {
        "X-RateLimit-Remaining": remaining_header,
        "X-RateLimit-Reset": reset_header,
    }
    if json_body is not None:
        content = json.dumps(json_body).encode()
        content_type = "application/json"
    else:
        content = b"not json"
        content_type = "text/plain"

    response = httpx.Response(
        403,
        headers={**headers, "Content-Type": content_type},
        content=content,
    )

    with pytest.raises(expected_exc, match=match) as exc_info:
        client._handle_403_response(response)
    if expected_exc is RateLimitError:
        rate_limit_error = exc_info.value
        assert isinstance(rate_limit_error, RateLimitError)
        assert rate_limit_error.reset_time == int(reset_header)
        assert rate_limit_error.__cause__ is None  # from None: PII防止のため例外連鎖切断
    else:
        assert exc_info.value.__cause__ is None  # from None: PII防止のため例外連鎖切断
    assert exc_info.value.__context__ is None


def test_redact_body_preview_returns_fixed_format() -> None:
    """_redact_body_preview: [redacted:SHA256_16chars]形式を返す"""
    result = _redact_body_preview("any content here")
    assert re.fullmatch(r"\[redacted:[0-9a-f]{16}\]", result)


def test_redact_body_preview_empty_string() -> None:
    """_redact_body_preview: 空文字列→確定的ハッシュ"""
    assert _redact_body_preview("") == "[redacted:e3b0c44298fc1c14]"


def test_redact_body_preview_deterministic() -> None:
    """_redact_body_preview: 同一入力→同一出力（冪等性）"""
    body = "A" * 200
    assert _redact_body_preview(body) == _redact_body_preview(body)


def test_handle_http_status_error_uses_debug_for_other_4xx() -> None:
    """_handle_http_status_error: 401以外の other 4xx (400) では debug ログを使う

    リファクタ後: 404/429/403 は専用例外に変換されるため、ログパスの検証は
    400 (Bad Request) 等の other 4xx で実施する。
    """
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    mock_request = httpx.Request("GET", "https://api.github.com/test")
    mock_response = httpx.Response(400, request=mock_request)
    with patch.object(client, "logger") as mock_logger:
        with pytest.raises(GitHubAPIError, match=r"^HTTP 400 error$") as exc_info:
            client._handle_http_status_error(mock_response, "/test", "GET")
        assert exc_info.value.__cause__ is None
        # PII保護回帰テスト: __context__ に HTTPStatusError(response) が残存しないことを継続検証。
        # 現実装では `raise ... from None` が except 外のため常に None だが、将来 except 内へ
        # 移動した場合のレスポンスボディ経由 PII 露出リグレッションをこの assertion が検出する。
        assert exc_info.value.__context__ is None
        mock_logger.debug.assert_called_once_with(
            "http_status_error",
            status_code=400,
            endpoint="/test",
            method="GET",
            body_preview=_redact_body_preview(""),
        )
        mock_logger.warning.assert_not_called()


def test_handle_http_status_error_404_raises_not_found_error() -> None:
    """_handle_http_status_error: 404 は NotFoundError に変換される

    リファクタ後: _handle_http_status_error が 404 を識別し NotFoundError を raise する。
    """
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    mock_request = httpx.Request("GET", "https://api.github.com/test")
    mock_response = httpx.Response(404, request=mock_request)

    with pytest.raises(NotFoundError, match="Resource not found: /test") as exc_info:
        client._handle_http_status_error(mock_response, "/test", "GET")

    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None


def test_handle_http_status_error_uses_warning_for_401() -> None:
    """_handle_http_status_error: 401ステータスでは warning ログを使う"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    mock_request = httpx.Request("GET", "https://api.github.com/test")
    mock_response = httpx.Response(401, request=mock_request)

    with patch.object(client, "logger") as mock_logger:
        with pytest.raises(GitHubAPIError, match=r"^HTTP 401 error$") as exc_info:
            client._handle_http_status_error(mock_response, "/test", "GET")
        assert exc_info.value.__cause__ is None
        # PII保護回帰テスト: 将来 except 内移動時のレスポンスボディ経由 PII 露出を検出する。
        assert exc_info.value.__context__ is None
        mock_logger.warning.assert_called_once_with(
            "http_status_error",
            status_code=401,
            endpoint="/test",
            method="GET",
            body_preview=_redact_body_preview(""),
        )
        mock_logger.debug.assert_not_called()


def test_handle_http_status_error_warning_truncates_body_preview_for_401() -> None:
    """_handle_http_status_error: 401レスポンスで body_preview が200バイトに切り詰められる"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    mock_request = httpx.Request("GET", "https://api.github.com/test")
    mock_response = httpx.Response(401, content=b"A" * 201, request=mock_request)

    with patch.object(client, "logger") as mock_logger:
        with pytest.raises(GitHubAPIError, match=r"^HTTP 401 error$"):
            client._handle_http_status_error(mock_response, "/test", "GET")
        mock_logger.warning.assert_called_once_with(
            "http_status_error",
            status_code=401,
            endpoint="/test",
            method="GET",
            body_preview=_redact_body_preview("A" * 200),
        )
        mock_logger.debug.assert_not_called()


def test_handle_http_status_error_with_5xx_raises_github_api_error() -> None:
    """_handle_http_status_error: 5xxでもGitHubAPIErrorをraiseする（防御的安全網）"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    request = httpx.Request("GET", "https://api.github.com/test")
    response = httpx.Response(503, request=request)

    with pytest.raises(GitHubAPIError, match=r"^HTTP 503 error$"):
        client._handle_http_status_error(response, "/test", "GET")


def test_handle_304_response_cache_miss() -> None:
    """キャッシュミス時にGitHubAPIErrorを発生させる（防御的コードパス D-07）"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    # _etag_cacheにエントリを設定するが_data_cacheには設定しない（不整合状態）
    client._etag_cache["/test"] = "etag-value"
    # _data_cacheは空のまま

    with capture_logs() as log_output:
        with pytest.raises(GitHubAPIError, match="Cache inconsistency"):
            client._handle_304_response("/test")

    error_logs = [log for log in log_output if log.get("event") == "cache_miss_on_304"]
    assert len(error_logs) == 1
    assert error_logs[0]["log_level"] == "error"
    assert error_logs[0]["etag"] == "etag-value"
    assert error_logs[0]["endpoint"] == "/test"
    assert "hint" in error_logs[0]


@pytest.mark.parametrize(
    ("status_code", "attempt", "max_retries_val", "expected_exc"),
    [
        pytest.param(
            503,
            0,
            MAX_RETRIES,
            None,
            id="5xx_non_final_attempt",
        ),
        pytest.param(
            503,
            MAX_RETRIES - 1,
            MAX_RETRIES,
            GitHubServerError,
            id="5xx_final_attempt",
        ),
    ],
)
@patch("utils.github_client.exponential_backoff_with_jitter", return_value=0.0)
async def test_handle_5xx_response(
    mock_backoff: Mock,
    status_code: int,
    attempt: int,
    max_retries_val: int,
    expected_exc: type[Exception] | None,
) -> None:
    """_handle_5xx_response の2パステスト（D-07）

    - 5xx_non_final_attempt: 5xx + 非最終試行
      → None を return（呼び出し元の await ...; continue へ）
    - 5xx_final_attempt: 5xx + 最終試行 → GitHubServerError を raise
    """
    async with AsyncGitHubClient(max_retries=max_retries_val) as client:
        mock_response = httpx.Response(status_code)

        if expected_exc is not None:
            with pytest.raises(expected_exc, match=r"Server error: 503 after \d+ attempts"):
                await client._handle_5xx_response(
                    mock_response,
                    attempt,
                    "/test",
                    "GET",
                )
        else:
            with capture_logs() as log_output:
                await client._handle_5xx_response(
                    mock_response,
                    attempt,
                    "/test",
                    "GET",
                )
            retrying_logs = [
                log for log in log_output if log.get("event") == "retrying_server_error"
            ]
            assert len(retrying_logs) == 1
            log = retrying_logs[0]
            assert log["attempt"] == attempt + 1
            assert log["max_retries"] == max_retries_val
            assert log["status_code"] == status_code
            assert log["delay"] == 0.0
            assert log["endpoint"] == "/test"
            assert log["method"] == "GET"


# ── D-07 追加: _prepare_headers / _handle_304 / _handle_403 / _update_etag_cache ──


def test_prepare_headers_with_etag() -> None:
    """ETagキャッシュ存在時にIf-None-Matchヘッダーが設定される"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    client._etag_cache["/repos/test"] = "etag-abc"
    headers = client._prepare_headers("/repos/test")
    assert headers == {"If-None-Match": "etag-abc"}


def test_prepare_headers_without_etag() -> None:
    """ETagキャッシュ不在時に空dictを返す"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    assert client._prepare_headers("/repos/test") == {}


def test_handle_304_response_cache_hit() -> None:
    """_data_cacheヒット時にキャッシュデータを返す（D-07正常系）"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    cached = {"id": 1, "login": "user"}
    client._data_cache["/user"] = cached
    result = client._handle_304_response("/user")
    assert result == cached


def test_update_etag_cache_evicts_oldest_entry_when_limit_exceeded() -> None:
    """ETag/dataキャッシュは max_cache_entries を超えたら古いendpointから削除する"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES, max_cache_entries=2)
    first_response = httpx.Response(200, headers={"ETag": '"etag-1"'})
    second_response = httpx.Response(200, headers={"ETag": '"etag-2"'})
    third_response = httpx.Response(200, headers={"ETag": '"etag-3"'})

    client._update_etag_cache("/first", first_response, {"id": 1})
    client._update_etag_cache("/second", second_response, {"id": 2})
    client._update_etag_cache("/third", third_response, {"id": 3})

    assert "/first" not in client._etag_cache
    assert "/first" not in client._data_cache
    assert list(client._etag_cache) == ["/second", "/third"]
    assert list(client._data_cache) == ["/second", "/third"]


def test_update_etag_cache_refreshes_existing_entry_before_eviction() -> None:
    """既存キー更新時は挿入順を更新し、直近更新エントリを削除しない。"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES, max_cache_entries=2)

    client._update_etag_cache(
        "/first",
        httpx.Response(200, headers={"ETag": '"etag-1"'}),
        {"id": 1},
    )
    client._update_etag_cache(
        "/second",
        httpx.Response(200, headers={"ETag": '"etag-2"'}),
        {"id": 2},
    )
    client._update_etag_cache(
        "/first",
        httpx.Response(200, headers={"ETag": '"etag-1b"'}),
        {"id": 10},
    )
    client._update_etag_cache(
        "/third",
        httpx.Response(200, headers={"ETag": '"etag-3"'}),
        {"id": 3},
    )

    assert list(client._etag_cache) == ["/first", "/third"]
    assert list(client._data_cache) == ["/first", "/third"]
    assert client._etag_cache["/first"] == '"etag-1b"'
    assert client._data_cache["/first"] == {"id": 10}


def test_enforce_cache_limit_evicts_multiple_entries_when_excess_gt_one() -> None:
    """_enforce_cache_limit: excess > 1 でも複数エントリ削除と件数ログが正しい"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES, max_cache_entries=2)
    for index in range(5):
        key = f"/entry-{index}"
        client._etag_cache[key] = f"etag-{index}"
        client._data_cache[key] = {"id": index}

    with patch.object(client, "logger") as mock_logger:
        client._enforce_cache_limit()

    assert list(client._etag_cache) == ["/entry-3", "/entry-4"]
    assert list(client._data_cache) == ["/entry-3", "/entry-4"]
    assert len(client._etag_cache) == client.max_cache_entries
    assert len(client._data_cache) == client.max_cache_entries
    mock_logger.info.assert_called_once_with(
        "cache_entries_evicted",
        evicted_count=3,
        current_size=2,
        max_size=2,
    )
    mock_logger.error.assert_not_called()


def test_update_etag_cache_enforces_limit_before_insert_with_reserve() -> None:
    """_update_etag_cache は挿入前に reserve=1 で退避する（瞬間 max+1 防止, PR#347 #9）。

    max+1 は呼び出し中の過渡状態のため返却後のサイズでは観測できない。代わりに
    _enforce_cache_limit 呼び出し時点を捕捉し、(a) reserve=1 が渡ること、(b) その時点で
    新規キーが未挿入＝挿入前に enforce が走ることを検証する。挿入後 enforce（reserve なし）
    に戻すと両アサーションが失敗する true lock-in。
    """
    client = AsyncGitHubClient(max_retries=MAX_RETRIES, max_cache_entries=2)
    # キャッシュを max まで充填する
    for index in range(2):
        client._etag_cache[f"/old-{index}"] = f"etag-{index}"
        client._data_cache[f"/old-{index}"] = {"id": index}

    captured: dict[str, object] = {}
    original_enforce = client._enforce_cache_limit

    def spy(reserve: int = 0) -> None:
        captured["reserve"] = reserve
        captured["new_key_present_at_call"] = "/new" in client._etag_cache
        original_enforce(reserve)

    response = httpx.Response(
        200,
        headers={"ETag": '"new-etag"'},
        request=httpx.Request("GET", "https://api.github.com/new"),
    )
    with patch.object(client, "_enforce_cache_limit", side_effect=spy):
        client._update_etag_cache("/new", response, {"id": 99})

    # 新規 1 件分を予約して挿入前に退避する
    assert captured["reserve"] == 1
    # enforce 呼び出し時点で新規キーは未挿入（= 挿入前 enforce）
    assert captured["new_key_present_at_call"] is False
    # 最終的にエントリ数は max を超えない
    assert len(client._etag_cache) == client.max_cache_entries
    assert len(client._data_cache) == client.max_cache_entries


def test_enforce_cache_limit_invariant_violation_clears_both_caches() -> None:
    """invariant違反検出時は logger.error + 両キャッシュ clear で safe-fallback する。

    production安全策: assert文はpython -Oで削除されるため、Python条件分岐+
    logger.errorで invariant violation を可観測化 + recovery する。
    """
    client = AsyncGitHubClient(max_retries=MAX_RETRIES, max_cache_entries=2)
    # 異常状態を直接構築（_etag_cache=1件、_data_cache=2件 → invariant違反）
    client._etag_cache["/first"] = "etag-1"
    client._data_cache["/first"] = {"id": 1}
    client._data_cache["/orphan"] = {"id": 99}

    with patch.object(client, "logger") as mock_logger:
        client._enforce_cache_limit()

    # 両キャッシュclear確認
    assert client._etag_cache == {}
    assert client._data_cache == {}
    # logger.error呼び出し検証（Sentry捕捉対象）
    # PR#347 review #3-2: etag_only_keys_truncated/data_only_keys_truncated は
    # 実際に切り詰められた場合のみ True。本テストは 0/1 件のため False。
    mock_logger.error.assert_called_once_with(
        "cache_invariant_violation",
        etag_cache_size=1,
        data_cache_size=2,
        etag_only_keys=[],
        data_only_keys=["/orphan"],
        etag_only_keys_truncated=False,
        data_only_keys_truncated=False,
        action="cleared_both_caches",
    )


def test_enforce_cache_limit_strips_query_strings_from_invariant_logs() -> None:
    """cache invariant のログは query string を落として endpoint だけ残す。"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES, max_cache_entries=2)
    client._etag_cache["/repos/octocat/Hello-World?sort=updated"] = "etag-updated"
    client._data_cache["/repos/octocat/Hello-World?sort=created"] = {"id": 1}

    with patch.object(client, "logger") as mock_logger:
        client._enforce_cache_limit()

    assert client._etag_cache == {}
    assert client._data_cache == {}
    mock_logger.error.assert_called_once_with(
        "cache_invariant_violation",
        etag_cache_size=1,
        data_cache_size=1,
        etag_only_keys=["/repos/octocat/Hello-World"],
        data_only_keys=["/repos/octocat/Hello-World"],
        etag_only_keys_truncated=False,
        data_only_keys_truncated=False,
        action="cleared_both_caches",
    )


def test_enforce_cache_limit_detects_key_divergence_with_same_length() -> None:
    """同件数だがキー集合が異なる invariant 違反も検出する (set-equality)。

    旧来の ``len`` 比較では「1 件抜けて 1 件余分」状態を検出できなかった。
    ``dict.keys()`` の集合等価比較に切り替えたことで、defense-in-depth として
    キー差異も invariant violation として捕捉する。
    """
    client = AsyncGitHubClient(max_retries=MAX_RETRIES, max_cache_entries=4)
    # 異常状態: 同件数 (2件ずつ) だがキー集合が異なる
    client._etag_cache["/a"] = "etag-a"
    client._etag_cache["/b"] = "etag-b"
    client._data_cache["/a"] = {"id": 1}
    client._data_cache["/c"] = {"id": 3}  # /b ではなく /c (divergence)

    with patch.object(client, "logger") as mock_logger:
        client._enforce_cache_limit()

    # 両キャッシュclear確認
    assert client._etag_cache == {}
    assert client._data_cache == {}
    # logger.error 呼び出し検証 (sizeはlogに残るが判定はkeys()で行われる)
    # PR#347 review #3-2: etag_only_keys_truncated/data_only_keys_truncated は
    # 実際に切り詰められた場合のみ True。本テストは 1 件のため False。
    mock_logger.error.assert_called_once_with(
        "cache_invariant_violation",
        etag_cache_size=2,
        data_cache_size=2,
        etag_only_keys=["/b"],
        data_only_keys=["/c"],
        etag_only_keys_truncated=False,
        data_only_keys_truncated=False,
        action="cleared_both_caches",
    )


def test_enforce_cache_limit_invariant_violation_truncated_flag_requires_over_limit() -> None:
    """truncated flag は表示上限ちょうどではなく、上限超過時のみ True になる。"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES, max_cache_entries=10)
    for index in range(6):
        client._etag_cache[f"/etag-only-{index}"] = f"etag-{index}"
    client._data_cache["/data-only"] = {"id": 1}

    with patch.object(client, "logger") as mock_logger:
        client._enforce_cache_limit()

    mock_logger.error.assert_called_once()
    _, kwargs = mock_logger.error.call_args
    assert kwargs["etag_only_keys"] == [
        "/etag-only-0",
        "/etag-only-1",
        "/etag-only-2",
        "/etag-only-3",
        "/etag-only-4",
    ]
    assert kwargs["etag_only_keys_truncated"] is True
    assert kwargs["data_only_keys"] == ["/data-only"]
    assert kwargs["data_only_keys_truncated"] is False


def test_handle_403_response_no_json_log() -> None:
    """非JSONボディ時にfailed_to_parse_403_messageログ（warning）が出力される"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    response = httpx.Response(
        403,
        headers={
            "X-RateLimit-Remaining": "50",
            "X-RateLimit-Reset": "0",
            "Content-Type": "text/plain",
        },
        content=b"not json",
    )
    with capture_logs() as logs:
        # _handle_403_response は NoReturn のため pytest.raises は必須（ログ検証が目的）
        with pytest.raises(GitHubAPIError, match="Access forbidden") as exc_info:
            client._handle_403_response(response)
        warning_logs = [log for log in logs if log.get("event") == "failed_to_parse_403_message"]
        assert len(warning_logs) == 1
        assert warning_logs[0]["log_level"] == "warning"
        assert "error" not in warning_logs[0]
        assert warning_logs[0].get("error_type") == "JSONDecodeError"
        assert warning_logs[0].get("error_module") == "json.decoder"
        assert isinstance(warning_logs[0].get("error_pos"), int)
        assert isinstance(warning_logs[0].get("error_lineno"), int)
        # from None: PII防止のため例外連鎖切断（__cause__ は None）
        assert exc_info.value.__cause__ is None
        assert exc_info.value.__context__ is None


def test_handle_403_response_truncates_message_to_200_chars() -> None:
    """403 JSON message は 200 文字で切り詰められる"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    long_message = "z" * 201
    response = httpx.Response(
        403,
        headers={
            "X-RateLimit-Remaining": "50",
            "X-RateLimit-Reset": "0",
            "Content-Type": "application/json",
        },
        content=json.dumps({"message": long_message}).encode(),
    )

    with pytest.raises(GitHubAPIError, match=f"Access forbidden: {'z' * 200}"):
        client._handle_403_response(response)


def test_handle_403_response_no_truncation_at_boundary() -> None:
    """403 JSON messageが200文字ちょうどの場合は切り詰めない"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    exact_message = "z" * 200
    response = httpx.Response(
        403,
        headers={
            "X-RateLimit-Remaining": "50",
            "X-RateLimit-Reset": "0",
            "Content-Type": "application/json",
        },
        content=json.dumps({"message": exact_message}).encode(),
    )

    with pytest.raises(GitHubAPIError, match=f"Access forbidden: {exact_message}"):
        client._handle_403_response(response)


def test_parse_json_response_valid_json() -> None:
    """_parse_json_response: 有効なJSONレスポンスをパースして返す"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    response = httpx.Response(200, json={"id": 1, "login": "user"})
    result = client._parse_json_response(response, "/user")
    assert result == {"id": 1, "login": "user"}


def test_parse_json_response_invalid_json_uses_sanitized_cause() -> None:
    """_parse_json_response: 破損JSONでbodyを保持しない専用causeを使う"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    # 明示的に不正JSONコンテンツを持つレスポンスを構築
    response = httpx.Response(
        200,
        content=b"not-valid-json",
        headers={"Content-Type": "application/json"},
    )
    with capture_logs() as log_output:
        with pytest.raises(GitHubAPIError, match="Invalid JSON response") as exc_info:
            client._parse_json_response(response, "/test-endpoint")

    # __cause__は sanitized cause であるが、raw JSONコンテンツは保持しない
    assert exc_info.value.__cause__ is not None
    assert isinstance(exc_info.value.__cause__, _SanitizedJSONDecodeError)
    assert not isinstance(exc_info.value.__cause__, json.JSONDecodeError)
    assert exc_info.value.__cause__.error_type == (
        f"{json.JSONDecodeError.__module__}.{json.JSONDecodeError.__qualname__}"
    )
    assert isinstance(exc_info.value.__cause__.pos, int)
    assert isinstance(exc_info.value.__cause__.lineno, int)
    assert "not-valid-json" not in str(exc_info.value.__cause__)
    # __context__は完全切断（PII隔離保証）
    assert exc_info.value.__context__ is None
    assert "not-valid-json" not in str(exc_info.value)
    decode_logs = [log for log in log_output if log.get("event") == "json_decode_error"]
    assert len(decode_logs) == 1
    assert decode_logs[0]["endpoint"] == "/test-endpoint"
    assert "error" not in decode_logs[0]
    assert decode_logs[0]["error_type"] == json.JSONDecodeError.__qualname__
    assert decode_logs[0]["error_module"] == json.JSONDecodeError.__module__
    assert isinstance(decode_logs[0]["error_pos"], int)
    assert isinstance(decode_logs[0]["error_lineno"], int)


def test_sanitized_jsondecodeerror_str_contains_no_response_body() -> None:
    """_SanitizedJSONDecodeError.__str__() は型・位置情報のみで body を含まない（PR#347 T-2）。

    現状の PII 漏洩防止は __cause__ チェーン切断（__context__=None）に依存するが、
    __str__ 出力自体が response body を構造的に保持しないことを直接検証し、
    将来のフォーマット変更による回帰を検出する。colno は PR#347 Q-3 で追加した診断情報。
    """
    cause = _SanitizedJSONDecodeError(
        "json.JSONDecodeError",
        msg="Expecting value",
        pos=42,
        lineno=3,
        colno=7,
    )

    rendered = str(cause)
    # 型・msg・位置情報のみが厳密に含まれる（body 由来の文字列を混入させる余地がない）。
    # msg は json.JSONDecodeError.msg（静的パーサ診断文字列）で PII 非含有（PR#347 SF-1）。
    assert rendered == "json.JSONDecodeError: Expecting value pos=42, lineno=3, colno=7"
    assert cause.msg == "Expecting value"  # PR#347 SF-1: 破損種別識別用 msg を保持
    assert cause.pos == 42
    assert cause.lineno == 3
    assert cause.colno == 7  # PR#347 Q-3: 診断用 colno を保持
    # 仮にレスポンス body 由来の機密文字列があっても __str__ には現れない
    assert "password" not in rendered
    assert "token" not in rendered


def test_sanitized_jsondecodeerror_reduce_roundtrip_preserves_fields() -> None:
    """_SanitizedJSONDecodeError は __reduce__ で全フィールドを復元できる（PR#347 Q-2）。

    非標準 __init__ シグネチャ（5 引数）のため __reduce__ を実装。pytest-xdist の
    worker→controller 例外転送や Sentry SDK シリアライズが依存する pickle プロトコル
    の契約（``cls(*args)`` で再構築可能）を直接検証する。pickle.loads は CWE-502 回避の
    ため使わず、__reduce__ の戻り値から手動で再構築して TypeError にならないことを保証する。
    """
    original = _SanitizedJSONDecodeError(
        "json.JSONDecodeError",
        msg="Expecting value",
        pos=42,
        lineno=3,
        colno=7,
    )

    cls, args = original.__reduce__()
    restored = cls(*args)

    assert isinstance(restored, _SanitizedJSONDecodeError)
    assert restored.error_type == "json.JSONDecodeError"
    assert restored.msg == "Expecting value"
    assert restored.pos == 42
    assert restored.lineno == 3
    assert restored.colno == 7
    assert str(restored) == str(original)


def test_parse_json_response_unexpected_parse_error_propagates() -> None:
    """_parse_json_response: JSONDecodeError以外のパース例外は呼び出し元へ伝播"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    sensitive_detail = "https://api.example.com/internal?token=SECRET_API_KEY_12345"
    response = Mock(spec=httpx.Response)
    response.json.side_effect = RuntimeError(sensitive_detail)

    with capture_logs() as log_output:
        with pytest.raises(RuntimeError, match=re.escape(sensitive_detail)):
            client._parse_json_response(response, "/test-endpoint")

    assert not [log for log in log_output if log.get("event") == "json_parse_unexpected_error"]


def test_update_etag_cache_no_etag_header() -> None:
    """ETagヘッダー不在時にキャッシュを更新しない"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    # ETagヘッダーを含まない200レスポンス（if "ETag" in headers 条件が偽になる）
    response = httpx.Response(200, content=b"{}")
    client._update_etag_cache("/test", response, {"data": 1})
    assert "/test" not in client._etag_cache
    assert "/test" not in client._data_cache


def test_update_etag_cache_with_etag_header() -> None:
    """ETagヘッダー存在時に _etag_cache と _data_cache を同時更新する"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    response = httpx.Response(200, headers={"ETag": '"abc123"'}, content=b'{"id": 1}')
    result = {"id": 1}
    client._update_etag_cache("/repos/test", response, result)
    assert client._etag_cache["/repos/test"] == '"abc123"'
    assert client._data_cache["/repos/test"] == result


@pytest.mark.parametrize(
    ("cache_key", "expected_logged_endpoint"),
    [
        pytest.param("/repos/test", "/repos/test", id="no_query_params"),
        pytest.param(
            "/repos/test?per_page=30&sort=updated",
            "/repos/test",
            id="query_params_stripped_from_log",
        ),
    ],
)
def test_update_etag_cache_clears_stale_cache_and_logs_endpoint(
    cache_key: str, expected_logged_endpoint: str
) -> None:
    """ETag消失時、キャッシュを削除しログはクエリ無しendpointを出力する."""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    client._etag_cache[cache_key] = '"stale"'
    client._data_cache[cache_key] = {"id": 1}
    response = httpx.Response(200, content=b'{"id": 2}')

    with patch.object(client, "logger") as mock_logger:
        client._update_etag_cache(cache_key, response, {"id": 2})
        mock_logger.info.assert_called_once_with("etag_removed", endpoint=expected_logged_endpoint)

    assert cache_key not in client._etag_cache
    assert cache_key not in client._data_cache


def test_update_etag_cache_invalid_etag_evicts_stale_cache() -> None:
    """無効な形式のETag受信時、既存の stale キャッシュを破棄する（PR#347 review fix）。

    従来は warning ログ後に return するのみで _etag_cache/_data_cache が残存し、
    次回リクエストで古い ETag による 304 経路で stale データが再利用される恐れがあった。
    """
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    cache_key = "/repos/octocat/hello"
    client._etag_cache[cache_key] = '"stale-valid-etag"'
    client._data_cache[cache_key] = {"id": 1}
    # 不正形式（前後のダブルクォートなし）の ETag を持つレスポンス
    response = httpx.Response(200, headers={"ETag": "bad-etag-no-quotes"}, content=b'{"id": 2}')

    with patch.object(client, "logger") as mock_logger:
        client._update_etag_cache(cache_key, response, {"id": 2})
        mock_logger.warning.assert_called_once()
        assert mock_logger.warning.call_args.args[0] == "invalid_etag_format"

    # stale キャッシュが破棄されていること（修正の核心）
    assert cache_key not in client._etag_cache
    assert cache_key not in client._data_cache


@pytest.mark.parametrize(
    "remaining",
    [
        pytest.param(9, id="threshold"),
        pytest.param(0, id="zero"),
    ],
)
def test_check_rate_limit_warning_triggers(remaining: int) -> None:
    """remaining が _RATE_LIMIT_WARNING_THRESHOLD(10) 未満のとき警告ログを出力する
    戻り値として X-RateLimit-Reset のエポック秒 (int) を返す
    """
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    headers = httpx.Headers({"X-RateLimit-Reset": "1700000000"})
    with capture_logs() as logs:
        result = client._check_rate_limit_warning(headers, remaining=remaining)
    warning_logs = [log for log in logs if log.get("log_level") == "warning"]
    assert len(warning_logs) == 1
    assert warning_logs[0]["remaining"] == remaining
    assert warning_logs[0]["reset_time"] == datetime.fromtimestamp(1700000000, tz=UTC).isoformat()
    assert result == 1700000000  # PR#347: return value verification


def test_check_rate_limit_warning_no_warning_at_boundary() -> None:
    """remaining=10 (== _RATE_LIMIT_WARNING_THRESHOLD) で警告ログを出力しない
    戻り値として None を返す
    """
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    headers = httpx.Headers({"X-RateLimit-Reset": "1700000000"})
    with capture_logs() as logs:
        result = client._check_rate_limit_warning(headers, remaining=10)
    warning_logs = [log for log in logs if log.get("log_level") == "warning"]
    assert len(warning_logs) == 0
    for log in logs:
        assert "remaining" not in log  # threshold以上では remaining フィールドを出力しない
    assert result is None  # PR#347: return value verification


def test_handle_http_status_error_truncates_long_body() -> None:
    """レスポンスボディはエラーメッセージに含まれない（Sentryセキュリティ対応）"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    long_body = "x" * 201
    request = httpx.Request("GET", "https://api.github.com/test")
    response = httpx.Response(422, request=request, content=long_body.encode())

    with patch.object(client, "logger") as mock_logger:
        with pytest.raises(GitHubAPIError) as exc_info:
            client._handle_http_status_error(response, "/test", "GET")
        assert mock_logger.debug.call_args.kwargs["body_preview"] == _redact_body_preview("x" * 200)

    # エラーメッセージにボディが含まれないこと
    assert "x" not in str(exc_info.value)


def test_handle_http_status_error_no_truncation_at_boundary() -> None:
    """境界値(200字)でもレスポンスボディはエラーメッセージに含まれない（Sentryセキュリティ対応）"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    exact_body = "y" * 200  # ちょうど200文字（[:200]スライスで切り詰めが発生しない境界値）
    request = httpx.Request("GET", "https://api.github.com/test")
    response = httpx.Response(422, request=request, content=exact_body.encode())

    with patch.object(client, "logger") as mock_logger:
        with pytest.raises(GitHubAPIError) as exc_info:
            client._handle_http_status_error(response, "/test", "GET")
        assert mock_logger.debug.call_args.kwargs["body_preview"] == _redact_body_preview("y" * 200)

    # エラーメッセージにボディが含まれないこと
    assert exact_body not in str(exc_info.value)


def test_handle_http_status_error_truncates_multibyte_body_to_200_bytes() -> None:
    """多バイト文字のbody_previewも200バイトで切り詰める（境界はerrors='replace'で補完）"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    # "あ" は UTF-8 で3バイト。201文字 = 603バイト → 200バイトスライス後:
    # 66文字分(198バイト) + 2バイト(不完全な"あ") → errors="replace" で U+FFFD に置換
    multibyte_body = "あ" * 201
    request = httpx.Request("GET", "https://api.github.com/test")
    response = httpx.Response(422, request=request, content=multibyte_body.encode("utf-8"))

    with patch.object(client, "logger") as mock_logger:
        with pytest.raises(GitHubAPIError) as exc_info:
            client._handle_http_status_error(response, "/test", "GET")
        assert mock_logger.debug.call_args.kwargs["body_preview"] == _redact_body_preview(
            ("あ" * 201).encode("utf-8")[:200].decode("utf-8", errors="replace")
        )

    assert multibyte_body not in str(exc_info.value)


def test_handle_http_status_error_with_invalid_bytes() -> None:
    """不正UTF-8バイト列でもUnicodeDecodeErrorが発生しない（errors='replace'検証）"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    request = httpx.Request("GET", "https://api.github.com/test")
    # encoding=None をシミュレート: content に不正バイト列を設定
    response = httpx.Response(400, request=request, content=b"\xff\xfe invalid bytes \x80\x81")

    with pytest.raises(GitHubAPIError, match=r"^HTTP 400 error$"):
        client._handle_http_status_error(response, "/test", "GET")


def test_429_handled_as_rate_limit_error_via_handle_http_status_error() -> None:
    """_handle_http_status_error直接呼び出しで429がRateLimitErrorに変換されることの確認

    リファクタ後: _handle_http_status_errorが429→RateLimitErrorの変換を担う。
    X-RateLimit-Resetヘッダーなしの場合は reset_time=0（フォールバック）。
    """
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    request = httpx.Request("GET", "https://api.github.com/test")
    response = httpx.Response(429, request=request)

    with pytest.raises(RateLimitError) as exc_info:
        client._handle_http_status_error(response, "/test", "GET")

    assert exc_info.value.reset_time == 0
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None


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
    assert "unknown" in str(exc_info.value)  # else分岐のメッセージ内容を保護 (PR#347)
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
    assert "unknown" in str(exc_info.value)  # else分岐のメッセージ内容を保護 (PR#347)
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


def test_handle_http_status_error_cause_excludes_response_body() -> None:
    """from None による完全 PII 遮断を確認

    __cause__ is None であるため、センシティブな response body が
    Sentry 等の例外チェーン解析ツールに露出しないことを保証する。
    """
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    sensitive_body = "token=SUPER_SECRET_API_KEY_12345"
    request = httpx.Request("GET", "https://api.github.com/repos/test")
    response = httpx.Response(422, request=request, text=sensitive_body)

    with patch.object(client, "logger") as mock_logger:
        with pytest.raises(GitHubAPIError) as exc_info:
            client._handle_http_status_error(response, "/repos/test", "GET")
        # logger.debug で body_preview はリダクション済み（[redacted:hash] 形式）であること
        body_preview_logged = mock_logger.debug.call_args.kwargs["body_preview"]
        assert body_preview_logged.startswith("[redacted:")
        assert "]" in body_preview_logged
        # センシティブデータはログに含まれないこと
        assert sensitive_body not in body_preview_logged
        # 例外オブジェクト本体への PII 混入リグレッション検出
        assert sensitive_body not in str(exc_info.value)
        # 例外チェーン遮断検証：from None により __cause__ は None
        assert exc_info.value.__cause__ is None
        # 例外チェーン遮断検証：__context__ にも PII 含有オブジェクトが残存しない
        assert exc_info.value.__context__ is None


# =============================================================================
# _cache_key テスト（ETagキャッシュキーにクエリパラメータを含める）
# =============================================================================


def test_cache_key_no_params_returns_endpoint() -> None:
    """params=None の場合、endpoint をそのまま返す"""
    assert AsyncGitHubClient._cache_key("/users/octocat") == "/users/octocat"
    assert AsyncGitHubClient._cache_key("/users/octocat", None) == "/users/octocat"


def test_cache_key_empty_params_returns_endpoint() -> None:
    """params={} の場合、endpoint をそのまま返す"""
    assert AsyncGitHubClient._cache_key("/users/octocat", {}) == "/users/octocat"


def test_cache_key_with_params_produces_query_string() -> None:
    """params ありの場合、endpoint?key=value 形式を返す"""
    key = AsyncGitHubClient._cache_key(
        "/users/octocat/repos", {"sort": "updated", "per_page": "30"}
    )
    assert key == "/users/octocat/repos?per_page=30&sort=updated"


def test_cache_key_params_are_sorted_for_determinism() -> None:
    """パラメータの順序が異なっても同じキャッシュキーを返す（決定論的）"""
    key1 = AsyncGitHubClient._cache_key("/repos", {"b": "2", "a": "1"})
    key2 = AsyncGitHubClient._cache_key("/repos", {"a": "1", "b": "2"})
    assert key1 == key2


def test_cache_key_different_params_produce_different_keys() -> None:
    """異なるパラメータで異なるキャッシュキーを生成する"""
    key_a = AsyncGitHubClient._cache_key(
        "/users/octocat/repos", {"sort": "updated", "per_page": "30"}
    )
    key_b = AsyncGitHubClient._cache_key(
        "/users/octocat/repos", {"sort": "created", "per_page": "10"}
    )
    assert key_a != key_b


def test_cache_key_int_and_str_params_are_equivalent() -> None:
    """整数パラメータと文字列パラメータが同一のキャッシュキーを生成する。

    urlencode は int を文字列変換するため、{"per_page": 30} と
    {"per_page": "30"} が同一キーになることは重要な仕様である。
    """
    key_int = AsyncGitHubClient._cache_key("/repos", {"per_page": 30})
    key_str = AsyncGitHubClient._cache_key("/repos", {"per_page": "30"})
    assert key_int == key_str


def test_cache_key_url_encodes_spaces_as_percent20() -> None:
    """スペースを含むパラメータ値が %20 でエンコードされる（+ ではない）。

    _cache_key() は quote_via=quote を指定しており、urllib.parse.quote
    はスペースを %20 にエンコードする。+ エンコード（application/x-www-form-urlencoded
    標準）とは異なるため、キャッシュキー一致の回帰検出に必要。
    """
    key = AsyncGitHubClient._cache_key("/search", {"q": "hello world"})
    assert "hello%20world" in key
    assert "hello+world" not in key


def test_cache_key_encodes_special_chars_in_value() -> None:
    """``&`` や ``=`` を含むパラメータ値が ``%26`` / ``%3D`` にエンコードされる。

    ``_cache_key()`` は ``quote_via=quote`` を指定しており、urllib.parse.quote は
    クエリパラメータ区切り記号として予約された ``&`` / ``=`` も percent-encode する。
    これにより値内に区切り記号が含まれてもキャッシュキー衝突（異なるパラメータの
    キャッシュエントリが同一キーに丸まる事象）が防止されることを検証する。
    """
    key = AsyncGitHubClient._cache_key("/search", {"q": "a&b=c"})
    assert "%26" in key  # & はエンコードされる
    assert "%3D" in key  # = はエンコードされる
    # 生の & / = が値部分に出現しないこと（key/value 区切りの & / = は除外）
    assert "q=a&b=c" not in key


def test_cache_key_non_ascii_key_is_percent_encoded() -> None:
    """非ASCIIキー名が UTF-8 percent-encode される。

    型シグネチャ ``dict[str, str | int]`` は非ASCIIキー名を許容する。
    ``_cache_key()`` は ``quote_via=quote`` を指定しており、urllib.parse.quote
    は非ASCII文字を UTF-8 バイト列の percent-encode に変換する（生のマルチバイト
    文字をキャッシュキーに残さない）。キャッシュキーの一意性・安全性の境界値検証。
    """
    key = AsyncGitHubClient._cache_key("/search", {"クエリ": "value"})
    # "クエリ" は UTF-8 で %E3%82%AF%E3%82%A8%E3%83%AA に変換される
    assert key == "/search?%E3%82%AF%E3%82%A8%E3%83%AA=value"
    # 生の非ASCII文字がキーに残らないこと
    assert "クエリ" not in key


def test_cache_key_non_ascii_value_is_percent_encoded() -> None:
    """非ASCIIパラメータ値が UTF-8 percent-encode される。

    値側の日本語・絵文字も quote_via=quote により UTF-8 バイト列へ
    percent-encode され、生のマルチバイト文字がキャッシュキーに残らないことを検証。
    """
    key_jp = AsyncGitHubClient._cache_key("/search", {"q": "こんにちは"})
    assert key_jp == "/search?q=%E3%81%93%E3%82%93%E3%81%AB%E3%81%A1%E3%81%AF"
    assert "こんにちは" not in key_jp

    key_emoji = AsyncGitHubClient._cache_key("/search", {"q": "🎉"})
    assert key_emoji == "/search?q=%F0%9F%8E%89"


def test_cache_key_non_ascii_keys_are_deterministic() -> None:
    """非ASCIIキー名でもソートにより決定論的なキャッシュキーを生成する。

    パラメータ順序が異なっても同一キーになること（キャッシュ一意性保証）を
    非ASCIIキーで検証する。
    """
    key1 = AsyncGitHubClient._cache_key("/s", {"あ": "1", "い": "2"})
    key2 = AsyncGitHubClient._cache_key("/s", {"い": "2", "あ": "1"})
    assert key1 == key2


def test_handle_304_response_cache_miss_error_omits_query_params() -> None:
    """304キャッシュミス時のエラーメッセージからクエリパラメータが除去される。

    _handle_304_response は endpoint_only = cache_key.split("?")[0] により
    クエリ文字列を除去したエンドポイントのみをエラーメッセージに含める。
    """
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    cache_key = "/users/octocat/repos?per_page=30&sort=updated"
    client._etag_cache[cache_key] = "etag-value"

    with pytest.raises(GitHubAPIError, match="Cache inconsistency") as exc_info:
        client._handle_304_response(cache_key)

    assert "?" not in str(exc_info.value)
    assert "/users/octocat/repos" in str(exc_info.value)


def test_update_etag_cache_no_etag_removes_existing_cache() -> None:
    """ETag未含有レスポンス受信時に既存のetag/dataキャッシュが両方削除される。

    _update_etag_cache の else 分岐（ETagなし）では、cache_key が
    _etag_cache または _data_cache に存在する場合に両方を削除する。
    """
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    cache_key = "/users/octocat/repos"
    mock_request = httpx.Request("GET", "https://api.github.com/users/octocat/repos")
    mock_response = httpx.Response(200, request=mock_request)

    client._etag_cache[cache_key] = "existing-etag"
    client._data_cache[cache_key] = [{"id": 1}]

    client._update_etag_cache(cache_key, mock_response, [{"id": 2}])

    assert cache_key not in client._etag_cache
    assert cache_key not in client._data_cache


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


# =============================================================================
# PR#347 追加テスト（3件）
# =============================================================================


def test_rate_limit_error_overflow_fallback() -> None:
    """RateLimitError: 極端な reset_time で OverflowError/OSError → unix:{reset_time} フォールバック

    datetime.fromtimestamp は 2**63 のような極端な値で OverflowError または OSError を発生させる。
    フォールバックとして "unix:{reset_time}" 形式のメッセージが生成されることを確認する。
    """
    extreme_reset_time = 2**63
    err = RateLimitError(extreme_reset_time)
    assert f"unix:{extreme_reset_time}" in str(err)
    assert err.reset_time == extreme_reset_time


@pytest.mark.parametrize(
    "negative_reset_time",
    [
        pytest.param(-1, id="negative_one"),
        pytest.param(-100, id="negative_hundred"),
        pytest.param(0, id="zero_boundary"),
    ],
)
def test_rate_limit_error_negative_or_zero_reset_time(negative_reset_time: int) -> None:
    """RateLimitError: reset_time が 0 以下の場合 "unknown" フォールバック (PR#347 review T-1)

    実装 (utils/github_client.py:128-134) は `if reset_time > 0: ... else: reset_str = "unknown"`。
    負値 / 0 はいずれも else 分岐へ流れ "unknown" メッセージを生成する。
    境界値カバレッジ確保のための regression gate。
    """
    err = RateLimitError(negative_reset_time)
    assert err.reset_time == negative_reset_time
    assert "unknown" in str(err)


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


def test_cache_key_raises_github_api_error_on_type_error() -> None:
    """_cache_key: シリアライズ不可能なパラメータ値で GitHubAPIError が発生する。"""

    class NonSerializable:
        def __repr__(self) -> str:
            raise TypeError("not serializable")

        def __str__(self) -> str:
            raise TypeError("not serializable")

    with pytest.raises(GitHubAPIError, match="cache_key"):
        AsyncGitHubClient._cache_key("/repos", {"key": NonSerializable()})


def test_cache_key_raises_github_api_error_on_unicode_encode_error() -> None:
    """_cache_key: UnicodeEncodeError も PII-safe な GitHubAPIError に変換する。"""

    class NonEncodable:
        def __str__(self) -> str:
            raise UnicodeEncodeError("ascii", "秘密", 0, 1, "not encodable")

    with pytest.raises(GitHubAPIError, match="UnicodeEncodeError") as exc_info:
        AsyncGitHubClient._cache_key("/repos", {"key": NonEncodable()})

    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True


def test_cache_key_error_suppresses_cause_for_pii_safety() -> None:
    """_cache_key: from None により __cause__ が None になり PII 漏洩を防止する。"""

    class NonSerializable:
        def __repr__(self) -> str:
            raise TypeError("not serializable")

        def __str__(self) -> str:
            raise TypeError("not serializable")

    with pytest.raises(GitHubAPIError) as exc_info:
        AsyncGitHubClient._cache_key("/repos", {"key": NonSerializable()})
    assert exc_info.value.__cause__ is None  # from None prevents PII leak


def test_cache_key_build_failure_logs_endpoint_and_error_type_without_pii() -> None:
    """#2-6: _cache_key 失敗時に endpoint と error_type のみ構造化ログに記録し、
    param 値 (PII 含有可能性) はログ引数に含めないことを検証する。"""

    class NonSerializable:
        def __str__(self) -> str:
            raise TypeError("not serializable")

    with capture_logs() as log_output, pytest.raises(GitHubAPIError):
        AsyncGitHubClient._cache_key("/repos", {"secret_param": NonSerializable()})

    # 他テストと統一して structlog capture_logs で検証する（_module_logger への
    # patch は内部実装名に密結合し rename で壊れるため。PR#347 T-1）。
    warnings = [log for log in log_output if log["event"] == "cache_key_build_failed"]
    assert len(warnings) == 1
    log = warnings[0]
    assert log["log_level"] == "warning"
    assert log["endpoint"] == "/repos"
    assert log["error_type"] == "TypeError"
    # PII-safe: param キー名・値はログ引数に含めない
    assert "secret_param" not in str(log)


def test_cache_key_unicode_encode_error_logs_endpoint_and_error_type_without_pii() -> None:
    """#2-6 + codex review: _cache_key の UnicodeEncodeError 経路でも endpoint と
    error_type のみ構造化ログに記録し、param 値・例外内の非 ASCII PII を含めないことを検証する。

    TypeError 版 (上記) と対をなし、both error branches のログ契約を網羅する。
    UnicodeEncodeError は例外メッセージに非 ASCII payload (ここでは "秘密") を保持するため、
    それがログ引数へ漏れないことも確認する。
    """

    class NonEncodable:
        def __str__(self) -> str:
            raise UnicodeEncodeError("ascii", "秘密", 0, 1, "not encodable")

    with capture_logs() as log_output, pytest.raises(GitHubAPIError):
        AsyncGitHubClient._cache_key("/repos", {"secret_param": NonEncodable()})

    # 他テストと統一して structlog capture_logs で検証する（PR#347 T-1）。
    warnings = [log for log in log_output if log["event"] == "cache_key_build_failed"]
    assert len(warnings) == 1
    log = warnings[0]
    assert log["log_level"] == "warning"
    assert log["endpoint"] == "/repos"
    assert log["error_type"] == "UnicodeEncodeError"
    # PII-safe: param キー名・値・例外内の非 ASCII payload をログ引数に含めない
    assert "secret_param" not in str(log)
    assert "秘密" not in str(log)


# =============================================================================
# _check_rate_limit_warning: 閾値インタラクションテスト（Fix #10-QC-3）
# =============================================================================


def test_check_rate_limit_warning_threshold_interaction() -> None:
    """_check_rate_limit_warning: remaining < _RATE_LIMIT_WARNING_THRESHOLD(=10) で
    警告が発生し、reset_time が正しく返ることを確認する。"""
    from utils.github_client import _RATE_LIMIT_WARNING_THRESHOLD

    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    # 閾値ちょうど1つ下の値
    remaining = _RATE_LIMIT_WARNING_THRESHOLD - 1
    expected_reset_time = 1700000001
    headers = httpx.Headers({"X-RateLimit-Reset": str(expected_reset_time)})

    with capture_logs() as logs:
        result = client._check_rate_limit_warning(headers, remaining=remaining)

    warning_logs = [log for log in logs if log.get("event") == "rate_limit_low"]
    assert len(warning_logs) == 1
    assert warning_logs[0]["remaining"] == remaining
    assert result == expected_reset_time  # 有効な Unix タイムスタンプが返る
    assert result >= 1  # 戻り値 >= 1: 有効な Unix タイムスタンプ


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
