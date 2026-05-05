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
    validate_github_repo,
)

pytestmark = pytest.mark.unit

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
    respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").mock(side_effect=transport_exception)

    with patch(
        "utils.github_client.exponential_backoff_with_jitter",
        return_value=0.0,
    ):
        with patch("utils.github_client.asyncio.sleep", new_callable=AsyncMock):
            with capture_logs() as log_output:
                async with AsyncGitHubClient() as client:
                    with pytest.raises(GitHubAPIError) as exc_info:
                        await client.get_user("octocat")

    assert sensitive_detail not in str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
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


async def test_request_without_context_manager():
    """コンテキストマネージャー未使用時にRuntimeError発生"""
    client = AsyncGitHubClient()
    # async withを使わずに直接_requestを呼ぶ
    with pytest.raises(RuntimeError) as exc_info:
        await client._request("GET", "/users/octocat")

    assert "Client not initialized" in str(exc_info.value)
    assert "async with" in str(exc_info.value)


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
    """httpx.HTTPStatusError（403）防御的コードパスの検証

    防御的パス: 403をhttpx.HTTPStatusErrorとして受信した場合も
    _handle_403_response() を経由してRateLimitErrorを発生させる。

    検証項目:
    - httpx.HTTPStatusError(403)がRateLimitErrorに変換されること
    - reset_time属性が正しく設定されること
    - リクエストが1回のみ実行されること
    """
    request = httpx.Request("GET", f"{GITHUB_API_BASE_URL}/users/octocat")
    response_403 = httpx.Response(
        403,
        headers={
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": "1640000000",
        },
        request=request,
    )
    error_403 = httpx.HTTPStatusError("403 Forbidden", request=request, response=response_403)

    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [error_403]

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
    - invalid_rate_limit_header warning ログが2件出力されること
      （X-RateLimit-Remainingを共通パス（remaining監視）と403固有パス
       （rate_remaining判定）の2箇所で読み取り、どちらもValueError発生）
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
    # 共通パス(default=_RATE_LIMIT_FALLBACK_REMAINING)と403固有パス(default=_RATE_LIMIT_FORBIDDEN_FALLBACK)の2箇所でwarning発生  # noqa: E501
    # _RATE_LIMIT_FALLBACK_REMAINING(999) >= _RATE_LIMIT_WARNING_THRESHOLD(10) のため rate_limit_low は未発生、invalid_rate_limit_header のみ2件  # noqa: E501
    assert len(warning_logs) == 2
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
    - invalid_rate_limit_header warning ログが2件出力されること
      （共通remaining<10チェックパスにおけるX-RateLimit-Resetパース +
       403固有rate_remaining==0パスにおけるX-RateLimit-Resetパース の2箇所で発生）
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

    # invalid_rate_limit_header warningが2件（共通パス + 403固有パス）
    invalid_header_logs = [
        log for log in log_output if log.get("event") == "invalid_rate_limit_header"
    ]
    assert len(invalid_header_logs) == 2
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
    """_handle_http_status_error: 401以外の4xxでは debug ログを使う"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    mock_request = httpx.Request("GET", "https://api.github.com/test")
    mock_response = httpx.Response(404, request=mock_request)
    with patch.object(client, "logger") as mock_logger:
        with pytest.raises(GitHubAPIError, match=r"^HTTP 404 error$") as exc_info:
            client._handle_http_status_error(mock_response, "/test", "GET")
        assert exc_info.value.__cause__ is None
        assert exc_info.value.__context__ is None
        mock_logger.debug.assert_called_once_with(
            "http_status_error",
            status_code=404,
            endpoint="/test",
            method="GET",
            body_preview=_redact_body_preview(""),
        )
        mock_logger.warning.assert_not_called()


def test_handle_http_status_error_uses_warning_for_401() -> None:
    """_handle_http_status_error: 401ステータスでは warning ログを使う"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    mock_request = httpx.Request("GET", "https://api.github.com/test")
    mock_response = httpx.Response(401, request=mock_request)

    with patch.object(client, "logger") as mock_logger:
        with pytest.raises(GitHubAPIError, match=r"^HTTP 401 error$") as exc_info:
            client._handle_http_status_error(mock_response, "/test", "GET")
        assert exc_info.value.__cause__ is None
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
        # __cause__ なし（from None で保護）
        assert exc_info.value.__cause__ is None


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


def test_parse_json_response_invalid_json_raises() -> None:
    """_parse_json_response: 破損JSONでGitHubAPIError + json_decode_errorログ"""
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

    assert exc_info.value.__cause__ is None
    # except外raiseパターンで__context__も完全切断されていること（PII隔離保証）
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


def test_parse_json_response_unexpected_parse_error_raises_invalid_json_without_pii() -> None:
    """_parse_json_response: JSONDecodeError以外のパース例外もPII-safeにInvalid JSONへ変換"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    sensitive_detail = "https://api.example.com/internal?token=SECRET_API_KEY_12345"
    response = Mock(spec=httpx.Response)
    response.json.side_effect = RuntimeError(sensitive_detail)

    with capture_logs() as log_output:
        with pytest.raises(GitHubAPIError, match="Invalid JSON response") as exc_info:
            client._parse_json_response(response, "/test-endpoint")

    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    assert sensitive_detail not in str(exc_info.value)
    parse_logs = [log for log in log_output if log.get("event") == "json_parse_unexpected_error"]
    assert len(parse_logs) == 1
    assert parse_logs[0]["endpoint"] == "/test-endpoint"
    assert parse_logs[0]["error_type"] == "RuntimeError"
    assert parse_logs[0]["error_module"] == "builtins"
    assert "error" not in parse_logs[0]
    for value in parse_logs[0].values():
        assert sensitive_detail not in str(value), (
            f"sensitive_detail leaked in log field value: {value!r}"
        )


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


def test_update_etag_cache_clears_stale_cache_when_etag_missing() -> None:
    """ETagが消失した場合は古いキャッシュを削除する"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    endpoint = "/repos/test"
    client._etag_cache[endpoint] = '"stale"'
    client._data_cache[endpoint] = {"id": 1}
    response = httpx.Response(200, content=b'{"id": 2}')

    with patch.object(client, "logger") as mock_logger:
        client._update_etag_cache(endpoint, response, {"id": 2})
        mock_logger.debug.assert_called_once_with("etag_removed", endpoint=endpoint)

    assert endpoint not in client._etag_cache
    assert endpoint not in client._data_cache


@pytest.mark.parametrize(
    "remaining",
    [
        pytest.param(9, id="threshold"),
        pytest.param(0, id="zero"),
    ],
)
def test_check_rate_limit_warning_triggers(remaining: int) -> None:
    """remaining が _RATE_LIMIT_WARNING_THRESHOLD(10) 未満のとき警告ログを出力する"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    headers = httpx.Headers({"X-RateLimit-Reset": "1700000000"})
    with capture_logs() as logs:
        client._check_rate_limit_warning(headers, remaining=remaining)
    warning_logs = [log for log in logs if log.get("log_level") == "warning"]
    assert len(warning_logs) == 1
    assert warning_logs[0]["remaining"] == remaining
    assert warning_logs[0]["reset_time"] == datetime.fromtimestamp(1700000000, tz=UTC).isoformat()


def test_check_rate_limit_warning_no_warning_at_boundary() -> None:
    """remaining=10 (== _RATE_LIMIT_WARNING_THRESHOLD) で警告ログを出力しない"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    headers = httpx.Headers({"X-RateLimit-Reset": "1700000000"})
    with capture_logs() as logs:
        client._check_rate_limit_warning(headers, remaining=10)
    warning_logs = [log for log in logs if log.get("log_level") == "warning"]
    assert len(warning_logs) == 0
    for log in logs:
        assert "remaining" not in log  # threshold以上では remaining フィールドを出力しない


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


def test_429_handled_as_github_api_error_not_rate_limit_error() -> None:
    """_handle_http_status_error単体では429をGitHubAPIErrorとして扱う（メソッド直接呼び出し確認）

    _handle_http_status_errorは汎用4xxハンドラのため429を識別しない。
    実際の429→RateLimitError変換は_requestレベルで行う（test_429_response_raises_rate_limit_error参照）。
    """
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    request = httpx.Request("GET", "https://api.github.com/test")
    response = httpx.Response(429, request=request)

    with pytest.raises(GitHubAPIError, match=r"^HTTP 429 error$") as exc_info:
        client._handle_http_status_error(response, "/test", "GET")

    assert not isinstance(exc_info.value, RateLimitError)


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
    """httpx.HTTPStatusError（429）防御的コードパスの検証

    防御的パス: 429をhttpx.HTTPStatusErrorとして受信した場合も
    RateLimitErrorに変換される。
    """
    request = httpx.Request("GET", f"{GITHUB_API_BASE_URL}/users/octocat")
    response_429 = httpx.Response(
        429,
        headers={"X-RateLimit-Reset": "1640000000"},
        request=request,
    )
    error_429 = httpx.HTTPStatusError(
        "429 Too Many Requests", request=request, response=response_429
    )

    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [error_429]

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
    """from None による完全PII遮断を確認

    __cause__ is None であるため、センシティブなresponse bodyが
    Sentry等の例外チェーン解析ツールに露出しないことを保証する。
    """
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    sensitive_body = "token=SUPER_SECRET_API_KEY_12345"
    request = httpx.Request("GET", "https://api.github.com/repos/test")
    response = httpx.Response(422, request=request, text=sensitive_body)

    with patch.object(client, "logger") as mock_logger:
        with pytest.raises(GitHubAPIError) as exc_info:
            client._handle_http_status_error(response, "/repos/test", "GET")
        # logger.debugでbody_previewはリダクション済み（[redacted:hash]形式）であること
        body_preview_logged = mock_logger.debug.call_args.kwargs["body_preview"]
        assert body_preview_logged.startswith("[redacted:")
        assert "]" in body_preview_logged
        # センシティブデータはログに含まれないこと
        assert sensitive_body not in body_preview_logged

    # from None により __cause__ は None（完全PII遮断）
    assert exc_info.value.__cause__ is None
    # GitHubAPIError本体にもセンシティブデータが含まれないこと
    assert sensitive_body not in str(exc_info.value)
