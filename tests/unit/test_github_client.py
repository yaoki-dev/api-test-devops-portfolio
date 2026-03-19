"""
GitHub API非同期クライアントのUnit Tests

テスト戦略:
- respxを使用してGitHub APIの依存を排除（HTTPレイヤーモック）
- 正常系・異常系・エッジケースを網羅
- カバレッジ目標: 80%以上
"""

import asyncio
from unittest.mock import ANY, Mock, patch

import httpx
import pytest
import respx

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

    async with AsyncGitHubClient(max_retries=3) as client:
        with pytest.raises(GitHubServerError) as exc_info:
            await client.get_user("octocat")

    assert route.call_count == 3
    assert "Server error: 500" in str(exc_info.value)
    assert "after 3 attempts" in str(exc_info.value)
    assert mock_backoff.call_count == 2  # 3試行 → attempt=0,1でバックオフ（attempt=2は発生しない）


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
    # 例外チェーンが保持されていることを確認（from e でラップ）
    assert isinstance(exc_info.value.__cause__, httpx.HTTPStatusError)
    assert route.call_count == 1  # エラー時はリトライなし（1回のみ実行）


@respx.mock
@patch("utils.github_client.exponential_backoff_with_jitter", return_value=0.0)
async def test_httpx_status_error_5xx(mock_backoff: Mock) -> None:
    """httpx.HTTPStatusError（5xx）処理の検証"""
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [
        httpx.Response(503, headers={"X-RateLimit-Remaining": "60"}),
        httpx.Response(503, headers={"X-RateLimit-Remaining": "60"}),
        httpx.Response(503, headers={"X-RateLimit-Remaining": "60"}),
    ]

    async with AsyncGitHubClient(max_retries=3) as client:
        with pytest.raises(GitHubServerError) as exc_info:
            await client.get_user("octocat")

    assert "Server error: 503" in str(exc_info.value)
    assert route.call_count == 3
    assert mock_backoff.call_count == 2  # 3試行 → attempt=0,1でバックオフ（attempt=2は発生しない）


@respx.mock
@patch("utils.github_client.exponential_backoff_with_jitter", return_value=0.0)
async def test_httpx_status_error_5xx_defensive_path(mock_backoff: Mock) -> None:
    """httpx.HTTPStatusError（5xx）防御的コードパスの検証

    L368 の except httpx.HTTPStatusError パスを直接テストする。
    通常L328-343で先に処理されるが、HTTPStatusErrorが直接発生した場合の
    バックオフ・ログ・リトライ動作を検証する。

    検証項目:
    - retrying_http_status_error ログイベント出力
    - delay を含むログフィールド（サイレント障害検知）
    - バックオフ後リトライ（sleep + continue）
    - 最終試行後に GitHubServerError 発生
    """
    request = httpx.Request("GET", f"{GITHUB_API_BASE_URL}/users/octocat")
    response_503 = httpx.Response(503, request=request)
    error_503 = httpx.HTTPStatusError("503 Server Error", request=request, response=response_503)

    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [error_503, error_503, error_503]

    async with AsyncGitHubClient(max_retries=3) as client:
        with pytest.raises(GitHubServerError) as exc_info:
            await client.get_user("octocat")

    assert "Failed after 3 attempts" in str(exc_info.value)
    assert route.call_count == 3
    assert mock_backoff.call_count == 2  # 3試行 → attempt=0,1でバックオフ（attempt=2は発生しない）


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
# validate_github_repo バリデーションテスト
# =============================================================================


def test_repo_validation_valid() -> None:
    """有効なリポジトリ名でValueError未発生を確認"""
    validate_github_repo("my-repo")
    validate_github_repo("a")
    validate_github_repo("a" * 100)  # 上限（100文字）


def test_repo_validation_invalid() -> None:
    """無効なリポジトリ名でValueError発生（セキュリティ境界テスト）

    GITHUB_REPO_PATTERN = r"^[a-zA-Z0-9._-]{1,100}$" に基づく検証。
    Path Traversal・文字数超過・空文字列・特殊文字の4境界をテストする。
    バリデーションはHTTPリクエスト前に完了するため非同期不要。
    """
    # Path Traversal攻撃パターン（'/'はREGEX許可文字外）
    with pytest.raises(ValueError, match="Invalid GitHub repository name"):
        validate_github_repo("../etc/passwd")

    # 文字数上限超過（101文字 > 上限100文字）
    with pytest.raises(ValueError, match="Invalid GitHub repository name"):
        validate_github_repo("a" * 101)

    # 空文字列（`not repo` が True → REGEX到達前にValueError）
    with pytest.raises(ValueError, match="Invalid GitHub repository name"):
        validate_github_repo("")

    # 特殊文字（スペース・! はREGEX許可文字外）
    with pytest.raises(ValueError, match="Invalid GitHub repository name"):
        validate_github_repo("repo name!")
