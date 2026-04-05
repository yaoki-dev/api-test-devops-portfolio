"""
GitHub API非同期クライアントのUnit Tests

テスト戦略:
- respxを使用してGitHub APIの依存を排除（HTTPレイヤーモック）
- 正常系・異常系・エッジケースを網羅
- カバレッジ目標: 80%以上
"""

import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import ANY, Mock, patch

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
async def test_retry_on_server_error(mock_backoff: Mock) -> None:
    """5xxエラーで3回リトライ後、GitHubServerError発生

    検証項目:
    - 500エラー発生時に指数バックオフでリトライ
    - 3回失敗後にGitHubServerError例外
    - 例外チェーン維持（from e）
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


@respx.mock
async def test_timeout_handling():
    """タイムアウト時にGitHubAPIError発生

    検証項目:
    - httpx.TimeoutException → GitHubAPIError変換
    - 例外チェーン維持（from e）
    - 警告ログ出力
    """
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").mock(
        side_effect=httpx.TimeoutException("Request timeout")
    )

    async with AsyncGitHubClient() as client:
        with pytest.raises(GitHubAPIError) as exc_info:
            await client.get_user("octocat")

    assert "timeout" in str(exc_info.value).lower()
    # 例外チェーン確認
    assert exc_info.value.__cause__ is not None
    assert isinstance(exc_info.value.__cause__, httpx.TimeoutException)
    assert route.call_count == 1  # エラー時はリトライなし（1回のみ実行）


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
    assert client._client is None

    async with client as ctx_client:
        # __aenter__がself を返す（Self型アノテーション契約）
        assert ctx_client is client
        # __aenter__で_clientが初期化される
        assert ctx_client._client is not None
        assert isinstance(ctx_client._client, httpx.AsyncClient)

    # __aexit__でhttpx.AsyncClientがクローズされたことを確認
    assert client._client is not None
    assert client._client.is_closed


async def test_request_without_context_manager():
    """コンテキストマネージャー未使用時にRuntimeError発生"""
    client = AsyncGitHubClient()
    # async withを使わずに直接_requestを呼ぶ
    with pytest.raises(RuntimeError) as exc_info:
        await client._request("GET", "/users/octocat")

    assert "Client not initialized" in str(exc_info.value)
    assert "async with" in str(exc_info.value)


@respx.mock
async def test_httpx_timeout_exception():
    """httpx.TimeoutException処理の検証"""
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").mock(
        side_effect=httpx.TimeoutException("Connection timeout")
    )

    async with AsyncGitHubClient() as client:
        with pytest.raises(GitHubAPIError) as exc_info:
            await client.get_user("octocat")

    assert "timeout" in str(exc_info.value).lower()
    assert exc_info.value.__cause__ is not None
    assert route.call_count == 1  # エラー時はリトライなし（1回のみ実行）


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
    # 例外チェーンが保持されていることを確認（HTTPStatusError 情報を保持した cause に再ラップ）
    assert exc_info.value.__cause__ is not None
    # __cause__がhttpx.HTTPStatusErrorそのものでないことを型レベルで確認
    assert not isinstance(exc_info.value.__cause__, httpx.HTTPStatusError)
    assert type(exc_info.value.__cause__) is Exception
    assert route.call_count == 1  # エラー時はリトライなし（1回のみ実行）


@respx.mock
@patch("utils.github_client.exponential_backoff_with_jitter", return_value=0.0)
async def test_httpx_status_error_5xx(mock_backoff: Mock) -> None:
    """5xxステータスコード（response.status_code >= 500）リトライパスの検証

    リトライ動作に加え、retrying_server_error ログ出力を検証する（Issue #229）。

    検証項目:
    - attempt 値の連続性・順序・件数（list(range(1, MAX_RETRIES)) との等価比較）
    - endpoint / method フィールドが存在しないこと
      （_handle_5xx_response はリクエストコンテキスト非保持）
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
    # Note: retrying_server_error は endpoint/method を含まない
    #       （_handle_5xx_response はリクエストコンテキストを持たないため）
    for log_entry in retry_logs:
        assert "endpoint" not in log_entry, (
            f"retrying_server_error に endpoint フィールドが存在: {log_entry}"
        )
        assert "method" not in log_entry, (
            f"retrying_server_error に method フィールドが存在: {log_entry}"
        )
        assert log_entry["status_code"] == 503
        assert log_entry["max_retries"] == MAX_RETRIES
        # delay は @patch(return_value=0.0) のモック値に対応
        assert log_entry["delay"] == 0.0


@respx.mock
@patch("utils.github_client.exponential_backoff_with_jitter", return_value=0.0)
async def test_httpx_status_error_5xx_defensive_path(mock_backoff: Mock) -> None:
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

    retry_logs = [log for log in log_output if log.get("event") == "retrying_server_error"]
    assert len(retry_logs) == MAX_RETRIES - 1, (
        f"retrying_server_error ログが{MAX_RETRIES - 1}件を期待 (実際: {len(retry_logs)}件)"
    )
    bad_level = [log for log in retry_logs if log.get("log_level") != "warning"]
    assert not bad_level, f"log_level が warning でないエントリ: {bad_level}"
    actual_attempts = [log_entry.get("attempt") for log_entry in retry_logs]
    assert actual_attempts == list(range(1, MAX_RETRIES)), f"attempt 値不一致: {actual_attempts}"
    for log_entry in retry_logs:
        assert "endpoint" not in log_entry, (
            f"retrying_server_error に endpoint フィールドが存在: {log_entry}"
        )
        assert "method" not in log_entry, (
            f"retrying_server_error に method フィールドが存在: {log_entry}"
        )
        assert log_entry["status_code"] == 503
        assert log_entry["max_retries"] == MAX_RETRIES
        assert log_entry["delay"] == 0.0


@respx.mock
async def test_unexpected_exception():
    """予期しない例外処理の検証"""
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").mock(
        side_effect=ValueError("Unexpected error")
    )

    async with AsyncGitHubClient() as client:
        with pytest.raises(GitHubAPIError) as exc_info:
            await client.get_user("octocat")

    assert "Unexpected error" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert route.call_count == 1  # エラー時はリトライなし（1回のみ実行）


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

    async with AsyncGitHubClient() as client:
        with pytest.raises(GitHubAPIError, match="Invalid JSON"):
            await client.get_user("octocat")

    assert route.call_count == 1  # GETリクエストが1回発行されたことを確認


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


@pytest.mark.unit
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
            "Access forbidden",
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
    """_handle_403_response の4パステスト（D-07）

    - rate_limit_exceeded: remaining=0 → RateLimitError
    - non_rate_limit_with_message: remaining=50 + JSON message → GitHubAPIError(message)
    - non_rate_limit_no_json: remaining=50 + 非JSON → GitHubAPIError
    - invalid_header_fallback: remaining=invalid → フォールバック(-1) → GitHubAPIError
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
        assert exc_info.value.reset_time == int(reset_header)


@pytest.mark.unit
def test_handle_http_status_error_raises_on_4xx() -> None:
    """_handle_http_status_error: 4xxステータスで GitHubAPIError を raise する（D-07）"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    mock_request = httpx.Request("GET", "https://api.github.com/test")
    mock_response = httpx.Response(404, request=mock_request)
    error = httpx.HTTPStatusError(
        "HTTP 404",
        request=mock_request,
        response=mock_response,
    )
    with capture_logs() as log_output:
        with pytest.raises(GitHubAPIError, match="HTTP 404"):
            client._handle_http_status_error(error)

    http_error_logs = [log for log in log_output if log.get("event") == "http_status_error"]
    assert len(http_error_logs) == 1
    assert http_error_logs[0]["log_level"] == "warning"
    assert http_error_logs[0]["status_code"] == 404
    assert http_error_logs[0]["endpoint"] == "/test"  # url.path のみ（クエリパラメータ除外）
    assert http_error_logs[0]["method"] == "GET"


@pytest.mark.unit
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
    assert error_logs[0]["hint"] == "ETag存在時のキャッシュミスは実装バグ"


@pytest.mark.unit
@pytest.mark.asyncio
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

    - 5xx_non_final_attempt: 5xx + 非最終試行 → return（None）
    - 5xx_final_attempt: 5xx + 最終試行 → GitHubServerError を raise
    """
    async with AsyncGitHubClient(max_retries=max_retries_val) as client:
        mock_response = httpx.Response(status_code)

        if expected_exc is not None:
            with pytest.raises(expected_exc):
                await client._handle_5xx_response(mock_response, attempt)
        else:
            with capture_logs() as log_output:
                await client._handle_5xx_response(mock_response, attempt)
            retrying_logs = [
                log for log in log_output if log.get("event") == "retrying_server_error"
            ]
            assert len(retrying_logs) == 1
            log = retrying_logs[0]
            assert log["attempt"] == attempt + 1
            assert log["max_retries"] == max_retries_val
            assert log["status_code"] == status_code
            assert log["delay"] == 0.0


# ── D-07 追加: _prepare_headers / _handle_304 / _handle_403 / _update_etag_cache ──


@pytest.mark.unit
def test_prepare_headers_with_etag() -> None:
    """ETagキャッシュ存在時にIf-None-Matchヘッダーが設定される"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    client._etag_cache["/repos/test"] = "etag-abc"
    headers = client._prepare_headers("/repos/test")
    assert headers == {"If-None-Match": "etag-abc"}


@pytest.mark.unit
def test_prepare_headers_without_etag() -> None:
    """ETagキャッシュ不在時に空dictを返す"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    assert client._prepare_headers("/repos/test") == {}


@pytest.mark.unit
def test_handle_304_response_cache_hit() -> None:
    """_data_cacheヒット時にキャッシュデータを返す（D-07正常系）"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    cached = {"id": 1, "login": "user"}
    client._data_cache["/user"] = cached
    result = client._handle_304_response("/user")
    assert result == cached


@pytest.mark.unit
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
        with pytest.raises(GitHubAPIError, match="Access forbidden"):
            client._handle_403_response(response)
        warning_logs = [log for log in logs if log.get("event") == "failed_to_parse_403_message"]
        assert len(warning_logs) == 1
        assert warning_logs[0]["log_level"] == "warning"


@pytest.mark.unit
def test_parse_json_response_valid_json() -> None:
    """_parse_json_response: 有効なJSONレスポンスをパースして返す"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    response = httpx.Response(200, json={"id": 1, "login": "user"})
    result = client._parse_json_response(response, "/user")
    assert result == {"id": 1, "login": "user"}


@pytest.mark.unit
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
        with pytest.raises(GitHubAPIError, match="Invalid JSON response"):
            client._parse_json_response(response, "/test-endpoint")

    decode_logs = [log for log in log_output if log.get("event") == "json_decode_error"]
    assert len(decode_logs) == 1
    assert decode_logs[0]["endpoint"] == "/test-endpoint"
    assert "error" in decode_logs[0]


@pytest.mark.unit
def test_update_etag_cache_no_etag_header() -> None:
    """ETagヘッダー不在時にキャッシュを更新しない"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    # ETagヘッダーを含まない200レスポンス（if "ETag" in headers 条件が偽になる）
    response = httpx.Response(200, content=b"{}")
    client._update_etag_cache("/test", response, {"data": 1})
    assert "/test" not in client._etag_cache
    assert "/test" not in client._data_cache


@pytest.mark.unit
def test_update_etag_cache_with_etag_header() -> None:
    """ETagヘッダー存在時に _etag_cache と _data_cache を同時更新する"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    response = httpx.Response(200, headers={"ETag": '"abc123"'}, content=b'{"id": 1}')
    result = {"id": 1}
    client._update_etag_cache("/repos/test", response, result)
    assert client._etag_cache["/repos/test"] == '"abc123"'
    assert client._data_cache["/repos/test"] == result


@pytest.mark.unit
def test_check_rate_limit_warning_triggers_at_threshold() -> None:
    """remaining=9 (< _RATE_LIMIT_WARNING_THRESHOLD=10) で警告ログを出力する"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    headers = httpx.Headers({"X-RateLimit-Reset": "1700000000"})
    with capture_logs() as logs:
        client._check_rate_limit_warning(headers, remaining=9)
    warning_logs = [log for log in logs if log.get("log_level") == "warning"]
    assert len(warning_logs) == 1
    assert warning_logs[0]["remaining"] == 9


@pytest.mark.unit
def test_check_rate_limit_warning_no_warning_at_boundary() -> None:
    """remaining=10 (== _RATE_LIMIT_WARNING_THRESHOLD) で警告ログを出力しない"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    headers = httpx.Headers({"X-RateLimit-Reset": "1700000000"})
    with capture_logs() as logs:
        client._check_rate_limit_warning(headers, remaining=10)
    warning_logs = [log for log in logs if log.get("log_level") == "warning"]
    assert len(warning_logs) == 0


@pytest.mark.unit
def test_check_rate_limit_warning_triggers_at_zero() -> None:
    """remaining=0 (< _RATE_LIMIT_WARNING_THRESHOLD=10) で警告ログを出力する"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    headers = httpx.Headers({"X-RateLimit-Reset": "1700000000"})
    with capture_logs() as logs:
        client._check_rate_limit_warning(headers, remaining=0)
    warning_logs = [log for log in logs if log.get("log_level") == "warning"]
    assert len(warning_logs) == 1
    assert warning_logs[0]["remaining"] == 0


@pytest.mark.unit
def test_handle_http_status_error_truncates_long_body() -> None:
    """レスポンスボディはエラーメッセージに含まれない（Sentryセキュリティ対応）"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    long_body = "x" * 201
    request = httpx.Request("GET", "https://api.github.com/test")
    response = httpx.Response(422, request=request, content=long_body.encode())
    error = httpx.HTTPStatusError("422", request=request, response=response)

    with capture_logs() as log_output:
        with pytest.raises(GitHubAPIError) as exc_info:
            client._handle_http_status_error(error)

    # エラーメッセージにボディが含まれないこと
    assert "x" not in str(exc_info.value)
    # logger.warningでbody_previewが記録されること
    http_error_logs = [log for log in log_output if log.get("event") == "http_status_error"]
    assert len(http_error_logs) == 1
    assert http_error_logs[0]["log_level"] == "warning"
    assert http_error_logs[0]["body_preview"] == "x" * 200


@pytest.mark.unit
def test_handle_http_status_error_no_truncation_at_boundary() -> None:
    """境界値(200字)でもレスポンスボディはエラーメッセージに含まれない（Sentryセキュリティ対応）"""
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    exact_body = "y" * 200  # ちょうど200文字（len > 200 が偽になる境界値）
    request = httpx.Request("GET", "https://api.github.com/test")
    response = httpx.Response(422, request=request, content=exact_body.encode())
    error = httpx.HTTPStatusError("422", request=request, response=response)

    with capture_logs() as log_output:
        with pytest.raises(GitHubAPIError) as exc_info:
            client._handle_http_status_error(error)

    # エラーメッセージにボディが含まれないこと
    assert exact_body not in str(exc_info.value)
    # logger.warningでbody_previewが記録されること
    http_error_logs = [log for log in log_output if log.get("event") == "http_status_error"]
    assert len(http_error_logs) == 1
    assert http_error_logs[0]["log_level"] == "warning"
    assert http_error_logs[0]["body_preview"] == exact_body


@pytest.mark.unit
def test_handle_http_status_error_cause_excludes_response_body() -> None:
    """__cause__およびGitHubAPIError本体の両方にセンシティブデータが含まれないことを確認

    from e → from _cause 変更の核心プロパティ: センシティブなresponse bodyが
    Sentry等の例外チェーン解析ツールに露出しないことを保証する。
    """
    client = AsyncGitHubClient(max_retries=MAX_RETRIES)
    sensitive_body = "token=SUPER_SECRET_API_KEY_12345"
    request = httpx.Request("GET", "https://api.github.com/repos/test")
    response = httpx.Response(422, request=request, text=sensitive_body)
    error = httpx.HTTPStatusError("422", request=request, response=response)

    with capture_logs() as log_output:
        with pytest.raises(GitHubAPIError) as exc_info:
            client._handle_http_status_error(error)

    cause_str = str(exc_info.value.__cause__)
    # __cause__はURL+ステータスのみ保持し、response bodyを含まない
    assert sensitive_body not in cause_str
    # __cause__がhttpx.HTTPStatusErrorそのものではないことを確認
    assert not isinstance(exc_info.value.__cause__, httpx.HTTPStatusError)
    # GitHubAPIError本体にもセンシティブデータが含まれないこと
    assert sensitive_body not in str(exc_info.value)
    # logger.warningでbody_previewにセンシティブデータが記録されること（デバッグ用途）
    http_error_logs = [log for log in log_output if log.get("event") == "http_status_error"]
    assert len(http_error_logs) == 1
    assert sensitive_body in http_error_logs[0]["body_preview"]
