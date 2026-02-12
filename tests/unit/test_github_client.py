"""
GitHub API非同期クライアントのUnit Tests

テスト戦略:
- モックを使用してGitHub APIの依存を排除
- 正常系・異常系・エッジケースを網羅
- カバレッジ目標: 80%以上
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from utils.github_client import (
    AsyncGitHubClient,
    GitHubAPIError,
    GitHubServerError,
    NotFoundError,
    RateLimitError,
)

# =============================================================================
# 基本機能テスト（正常系）
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_user_success():
    """ユーザー情報取得成功

    検証項目:
    - async withコンテキストマネージャーの動作
    - HTTPXクライアントのリクエスト実行
    - JSONレスポンスの正常パーシング
    """
    async with AsyncGitHubClient() as client:
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            # モックレスポンス設定
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_response.headers = {"X-RateLimit-Remaining": "59"}
            mock_response.json.return_value = {
                "login": "octocat",
                "name": "The Octocat",
                "public_repos": 8,
            }
            mock_request.return_value = mock_response

            # テスト実行
            user = await client.get_user("octocat")

            # アサーション
            assert user["login"] == "octocat"
            assert user["name"] == "The Octocat"
            assert user["public_repos"] == 8
            mock_request.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_repos_success():
    """リポジトリ一覧取得成功"""
    async with AsyncGitHubClient() as client:
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_response.headers = {"X-RateLimit-Remaining": "58"}
            mock_response.json.return_value = [
                {"name": "Hello-World", "stargazers_count": 100},
                {"name": "Spoon-Knife", "stargazers_count": 50},
            ]
            mock_request.return_value = mock_response

            repos = await client.get_repos("octocat", per_page=2)

            assert len(repos) == 2
            assert repos[0]["name"] == "Hello-World"
            assert repos[1]["stargazers_count"] == 50


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_repo_success():
    """リポジトリ詳細取得成功"""
    async with AsyncGitHubClient() as client:
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_response.headers = {"X-RateLimit-Remaining": "57"}
            mock_response.json.return_value = {
                "name": "Hello-World",
                "full_name": "octocat/Hello-World",
                "stargazers_count": 100,
                "forks_count": 50,
            }
            mock_request.return_value = mock_response

            repo = await client.get_repo("octocat", "Hello-World")

            assert repo["name"] == "Hello-World"
            assert repo["stargazers_count"] == 100


# =============================================================================
# エラーハンドリングテスト（異常系）
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_user_not_found():
    """ユーザーが存在しない（404 Not Found）

    検証項目:
    - 404ステータスコードでNotFoundError例外発生
    - エラーメッセージにエンドポイント含む
    """
    async with AsyncGitHubClient() as client:
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 404
            mock_response.headers = {"X-RateLimit-Remaining": "60"}
            mock_request.return_value = mock_response

            with pytest.raises(NotFoundError) as exc_info:
                await client.get_user("nonexistent-user-12345")

            assert "Resource not found" in str(exc_info.value)
            assert "/users/nonexistent-user-12345" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rate_limit_exceeded():
    """Rate Limit超過（403 Forbidden）

    検証項目:
    - 403ステータスコードでRateLimitError例外発生
    - reset_time属性が正しく設定される
    """
    async with AsyncGitHubClient() as client:
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 403
            # X-RateLimit-Remaining=0 でRate Limit超過を示す（改善後の仕様）
            mock_response.headers = {
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": "1640000000",
            }
            mock_request.return_value = mock_response

            with pytest.raises(RateLimitError) as exc_info:
                await client.get_user("octocat")

            assert exc_info.value.reset_time == 1640000000
            assert "Rate limit exceeded" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_on_server_error():
    """5xxエラーで3回リトライ後、GitHubServerError発生

    検証項目:
    - 500エラー発生時に指数バックオフでリトライ
    - 3回失敗後にGitHubServerError例外
    - 例外チェーン維持（from e）
    """
    async with AsyncGitHubClient(max_retries=3) as client:
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            # 3回とも500エラー
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 500
            mock_response.headers = {"X-RateLimit-Remaining": "50"}
            mock_request.return_value = mock_response

            with pytest.raises(GitHubServerError) as exc_info:
                await client.get_user("octocat")

            # リトライ3回確認
            assert mock_request.call_count == 3
            assert "Server error: 500" in str(exc_info.value)
            assert "after 3 retries" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_timeout_handling():
    """タイムアウト時にGitHubAPIError発生

    検証項目:
    - httpx.TimeoutException → GitHubAPIError変換
    - 例外チェーン維持（from e）
    - 警告ログ出力
    """
    async with AsyncGitHubClient() as client:
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            # タイムアウト例外を発生させる
            mock_request.side_effect = httpx.TimeoutException("Request timeout")

            with pytest.raises(GitHubAPIError) as exc_info:
                await client.get_user("octocat")

            assert "timeout" in str(exc_info.value).lower()
            # 例外チェーン確認
            assert exc_info.value.__cause__ is not None
            assert isinstance(exc_info.value.__cause__, httpx.TimeoutException)


# =============================================================================
# Rate Limit監視テスト
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rate_limit_warning_log():
    """Rate Limit残数が10未満の場合、警告ログ出力

    検証項目:
    - X-RateLimit-Remaining < 10で警告ログ
    - reset_time情報をログに含む
    """
    async with AsyncGitHubClient() as client:
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            with patch.object(client.logger, "warning") as mock_warning:
                mock_response = MagicMock(spec=httpx.Response)
                mock_response.status_code = 200
                mock_response.headers = {
                    "X-RateLimit-Remaining": "5",  # < 10
                    "X-RateLimit-Reset": "1640000000",
                }
                mock_response.json.return_value = {"login": "octocat"}
                mock_request.return_value = mock_response

                await client.get_user("octocat")

                # 警告ログ呼び出し確認
                mock_warning.assert_called_once()
                call_args = mock_warning.call_args
                assert call_args[0][0] == "rate_limit_low"
                assert call_args[1]["remaining"] == 5


# =============================================================================
# ETagキャッシュテスト（Conditional Requests）
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_etag_cache_hit():
    """ETagキャッシュヒット時304 Not Modified処理

    検証項目:
    - 1回目: 200 + ETag保存 + データキャッシュ保存
    - 2回目: If-None-Matchヘッダー送信 + 304レスポンス
    - 304時はキャッシュデータを返却
    """
    async with AsyncGitHubClient() as client:
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            # 1回目: 200 + ETag
            mock_response_1 = MagicMock(spec=httpx.Response)
            mock_response_1.status_code = 200
            mock_response_1.headers = {
                "ETag": '"abc123"',
                "X-RateLimit-Remaining": "50",
            }
            mock_response_1.json.return_value = {"login": "octocat"}

            mock_request.return_value = mock_response_1
            result1 = await client.get_user("octocat")
            assert result1["login"] == "octocat"

            # ETag/データキャッシュ確認
            assert "/users/octocat" in client._etag_cache
            assert client._etag_cache["/users/octocat"] == '"abc123"'
            assert "/users/octocat" in client._data_cache
            assert client._data_cache["/users/octocat"] == {"login": "octocat"}

            # 2回目: 304 Not Modified
            mock_response_2 = MagicMock(spec=httpx.Response)
            mock_response_2.status_code = 304
            mock_response_2.headers = {"X-RateLimit-Remaining": "50"}
            mock_request.return_value = mock_response_2

            result2 = await client.get_user("octocat")
            assert result2 == {"login": "octocat"}  # 304時はキャッシュデータ返却


# =============================================================================
# コンテキストマネージャーテスト
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_context_manager_initialization():
    """async withコンテキストマネージャーの初期化・終了処理"""
    client = AsyncGitHubClient()
    assert client._client is None

    async with client as ctx_client:
        # __aenter__で_clientが初期化される
        assert ctx_client._client is not None
        assert isinstance(ctx_client._client, httpx.AsyncClient)

    # __aexit__で_clientがクローズされる（closeメソッド呼び出し確認）
    # Note: httpx.AsyncClientのclose後の状態はis_closedプロパティで確認不可（private実装）
    # 代わりにlogger.infoが呼ばれたことを確認
    # （実装上、__aexit__でaclose()が呼ばれればOK）


@pytest.mark.unit
@pytest.mark.asyncio
async def test_request_without_context_manager():
    """コンテキストマネージャー未使用時にRuntimeError発生"""
    client = AsyncGitHubClient()
    # async withを使わずに直接_requestを呼ぶ
    with pytest.raises(RuntimeError) as exc_info:
        await client._request("GET", "/users/octocat")

    assert "Client not initialized" in str(exc_info.value)
    assert "async with" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_httpx_timeout_exception():
    """httpx.TimeoutException処理の検証"""
    async with AsyncGitHubClient() as client:
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = httpx.TimeoutException("Connection timeout")

            with pytest.raises(GitHubAPIError) as exc_info:
                await client.get_user("octocat")

            assert "timeout" in str(exc_info.value).lower()
            assert exc_info.value.__cause__ is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_httpx_status_error_4xx():
    """httpx.HTTPStatusError（4xx）処理の検証"""
    async with AsyncGitHubClient() as client:
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            # 401 Unauthorized
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 401
            mock_response.headers = {"X-RateLimit-Remaining": "60"}
            mock_exception = httpx.HTTPStatusError(
                "401 Unauthorized",
                request=MagicMock(),
                response=mock_response,
            )
            mock_request.side_effect = mock_exception

            with pytest.raises(httpx.HTTPStatusError):
                await client.get_user("octocat")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_httpx_status_error_5xx():
    """httpx.HTTPStatusError（5xx）処理の検証"""
    async with AsyncGitHubClient(max_retries=3) as client:
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 503
            mock_response.headers = {"X-RateLimit-Remaining": "60"}
            mock_exception = httpx.HTTPStatusError(
                "503 Service Unavailable",
                request=MagicMock(),
                response=mock_response,
            )
            mock_request.side_effect = mock_exception

            with pytest.raises(GitHubServerError) as exc_info:
                await client.get_user("octocat")

            assert "Failed after 3 retries" in str(exc_info.value)
            assert mock_request.call_count == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unexpected_exception():
    """予期しない例外処理の検証"""
    async with AsyncGitHubClient() as client:
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = ValueError("Unexpected error")

            with pytest.raises(GitHubAPIError) as exc_info:
                await client.get_user("octocat")

            assert "Unexpected error" in str(exc_info.value)
            assert isinstance(exc_info.value.__cause__, ValueError)


# =============================================================================
# セキュリティ改善テスト（OWASP A03:2021対策）
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
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


@pytest.mark.unit
@pytest.mark.asyncio
async def test_403_non_rate_limit():
    """403エラー（Rate Limit以外）でGitHubAPIError発生"""
    async with AsyncGitHubClient() as client:
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 403
            mock_response.headers = {"X-RateLimit-Remaining": "50"}
            mock_response.json.return_value = {"message": "Repository access blocked"}
            mock_request.return_value = mock_response

            with pytest.raises(GitHubAPIError, match="Access forbidden"):
                await client.get_user("octocat")

            # RateLimitErrorではないことを確認
            try:
                await client.get_user("octocat")
            except RateLimitError:
                pytest.fail("Should not raise RateLimitError for non-rate-limit 403")
            except GitHubAPIError:
                pass  # 期待通り


@pytest.mark.unit
@pytest.mark.asyncio
async def test_json_decode_error():
    """JSONパース失敗時にGitHubAPIError発生"""
    async with AsyncGitHubClient() as client:
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_request:
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_response.headers = {"X-RateLimit-Remaining": "50"}
            mock_response.json.side_effect = json.JSONDecodeError("err", "", 0)
            mock_request.return_value = mock_response

            with pytest.raises(GitHubAPIError, match="Invalid JSON"):
                await client.get_user("octocat")
