"""
GitHubClient ユニットテスト

Note:
    関数構造（フラット）で設計。
    責務: バリデーション + 例外ハンドリング + クライアント動作の検証

テストケース一覧（32件）:
    - Validation Username (7件): boundary values + invalid patterns
    - Validation Repo (5件): boundary values + invalid patterns
    - Exception Hierarchy (4件): 例外クラス構造
    - Client Error Paths (6件): 404, 403, 5xx, timeout, JSON error
    - Valid Equivalence (3件): 正常系パス
    - Public API (4件): get_user, get_repos, get_repo
    - Edge Cases (3件): 304 Not Modified, ETag cache, invalid JSON
"""

import json
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from utils.api_client import APIClientError
from utils.github_client import (
    AsyncGitHubClient,
    GitHubAPIError,
    GitHubServerError,
    NotFoundError,
    RateLimitError,
    validate_github_repo,
    validate_github_username,
)

pytestmark = pytest.mark.unit

# =============================================================================
# Validation: Username Tests（条件1: 境界値）
# =============================================================================


def test_validate_username_valid_min_length() -> None:
    """最小長（1文字）のユーザー名が有効"""
    validate_github_username("a")  # Should not raise


def test_validate_username_valid_max_length() -> None:
    """最大長（39文字）のユーザー名が有効"""
    validate_github_username("a" * 39)  # Should not raise


def test_validate_username_invalid_too_long() -> None:
    """40文字以上のユーザー名は無効"""
    with pytest.raises(ValueError) as exc_info:
        validate_github_username("a" * 40)
    assert "Invalid GitHub username" in str(exc_info.value)


def test_validate_username_invalid_empty() -> None:
    """空文字列のユーザー名は無効"""
    with pytest.raises(ValueError) as exc_info:
        validate_github_username("")
    assert "Invalid GitHub username" in str(exc_info.value)


def test_validate_username_invalid_starts_with_hyphen() -> None:
    """ハイフンで始まるユーザー名は無効"""
    with pytest.raises(ValueError) as exc_info:
        validate_github_username("-username")
    assert "Invalid GitHub username" in str(exc_info.value)


def test_validate_username_invalid_ends_with_hyphen() -> None:
    """ハイフンで終わるユーザー名は無効"""
    with pytest.raises(ValueError) as exc_info:
        validate_github_username("username-")
    assert "Invalid GitHub username" in str(exc_info.value)


def test_validate_username_invalid_consecutive_hyphens() -> None:
    """連続ハイフンを含むユーザー名は無効"""
    with pytest.raises(ValueError) as exc_info:
        validate_github_username("user--name")
    assert "Invalid GitHub username" in str(exc_info.value)


# =============================================================================
# Validation: Repository Tests（条件1: 境界値）
# =============================================================================


def test_validate_repo_valid_min_length() -> None:
    """最小長（1文字）のリポジトリ名が有効"""
    validate_github_repo("a")  # Should not raise


def test_validate_repo_valid_max_length() -> None:
    """最大長（100文字）のリポジトリ名が有効"""
    validate_github_repo("a" * 100)  # Should not raise


def test_validate_repo_invalid_too_long() -> None:
    """101文字以上のリポジトリ名は無効"""
    with pytest.raises(ValueError) as exc_info:
        validate_github_repo("a" * 101)
    assert "Invalid GitHub repository name" in str(exc_info.value)


def test_validate_repo_invalid_empty() -> None:
    """空文字列のリポジトリ名は無効"""
    with pytest.raises(ValueError) as exc_info:
        validate_github_repo("")
    assert "Invalid GitHub repository name" in str(exc_info.value)


def test_validate_repo_invalid_special_chars() -> None:
    """不正な特殊文字を含むリポジトリ名は無効"""
    with pytest.raises(ValueError) as exc_info:
        validate_github_repo("repo/name")  # slash not allowed
    assert "Invalid GitHub repository name" in str(exc_info.value)


# =============================================================================
# Exception Hierarchy Tests（条件2: エラーパス）
# =============================================================================


def test_exception_hierarchy_github_api_error() -> None:
    """GitHubAPIErrorがAPIClientErrorを継承（統一例外階層）"""
    assert issubclass(GitHubAPIError, APIClientError)
    assert issubclass(GitHubAPIError, Exception)  # 後方互換性確認


def test_exception_hierarchy_not_found_error() -> None:
    """NotFoundErrorがGitHubAPIErrorを継承"""
    assert issubclass(NotFoundError, GitHubAPIError)


def test_exception_hierarchy_rate_limit_error() -> None:
    """RateLimitErrorがGitHubAPIErrorを継承"""
    assert issubclass(RateLimitError, GitHubAPIError)
    # RateLimitErrorはreset_timeを保持
    error = RateLimitError(1234567890)
    assert error.reset_time == 1234567890


def test_exception_hierarchy_server_error() -> None:
    """GitHubServerErrorがGitHubAPIErrorを継承"""
    assert issubclass(GitHubServerError, GitHubAPIError)


# =============================================================================
# Client Error Path Tests（条件2: エラーパス）
# =============================================================================


@pytest.mark.asyncio
async def test_client_not_initialized_raises_runtime_error() -> None:
    """クライアント未初期化でRuntimeError発生"""
    client = AsyncGitHubClient()
    # _client is None without context manager
    with pytest.raises(RuntimeError) as exc_info:
        await client._request("GET", "/users/test")
    assert "not initialized" in str(exc_info.value)


@pytest.mark.asyncio
async def test_client_404_raises_not_found_error() -> None:
    """404レスポンスでNotFoundError発生"""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 404
    mock_response.headers = {}

    mock_httpx_client = AsyncMock()
    mock_httpx_client.request = AsyncMock(return_value=mock_response)
    mock_httpx_client.aclose = AsyncMock()

    async with AsyncGitHubClient() as client:
        client._client = mock_httpx_client

        with pytest.raises(NotFoundError) as exc_info:
            await client._request("GET", "/users/nonexistent")

        assert "not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_client_403_rate_limit_raises_rate_limit_error() -> None:
    """403 + Rate Limit超過でRateLimitError発生"""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 403
    mock_response.headers = {
        "X-RateLimit-Remaining": "0",
        "X-RateLimit-Reset": "1234567890",
    }

    mock_httpx_client = AsyncMock()
    mock_httpx_client.request = AsyncMock(return_value=mock_response)
    mock_httpx_client.aclose = AsyncMock()

    async with AsyncGitHubClient() as client:
        client._client = mock_httpx_client

        with pytest.raises(RateLimitError) as exc_info:
            await client._request("GET", "/users/test")

        assert exc_info.value.reset_time == 1234567890


@pytest.mark.asyncio
async def test_client_403_other_raises_github_api_error() -> None:
    """403 + Rate Limit以外でGitHubAPIError発生"""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 403
    mock_response.headers = {"X-RateLimit-Remaining": "100"}
    mock_response.json.return_value = {"message": "IP blocked"}

    mock_httpx_client = AsyncMock()
    mock_httpx_client.request = AsyncMock(return_value=mock_response)
    mock_httpx_client.aclose = AsyncMock()

    async with AsyncGitHubClient() as client:
        client._client = mock_httpx_client

        with pytest.raises(GitHubAPIError) as exc_info:
            await client._request("GET", "/users/test")

        assert "forbidden" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_client_timeout_raises_github_api_error() -> None:
    """タイムアウトでGitHubAPIError発生"""
    mock_httpx_client = AsyncMock()
    mock_httpx_client.request = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
    mock_httpx_client.aclose = AsyncMock()

    async with AsyncGitHubClient() as client:
        client._client = mock_httpx_client

        with pytest.raises(GitHubAPIError) as exc_info:
            await client._request("GET", "/users/test")

        assert "timeout" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_client_5xx_exhausted_raises_server_error() -> None:
    """5xxエラーでリトライ上限後GitHubServerError発生"""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_response.headers = {"X-RateLimit-Remaining": "100"}

    mock_httpx_client = AsyncMock()
    mock_httpx_client.request = AsyncMock(return_value=mock_response)
    mock_httpx_client.aclose = AsyncMock()

    async with AsyncGitHubClient(max_retries=1) as client:
        client._client = mock_httpx_client

        with pytest.raises(GitHubServerError) as exc_info:
            await client._request("GET", "/users/test")

        assert "500" in str(exc_info.value) or "retries" in str(exc_info.value).lower()


# =============================================================================
# Valid Equivalence Class Tests（条件4: 有効同値クラス）
# =============================================================================


def test_validate_username_valid_with_hyphen() -> None:
    """ハイフンを含む有効なユーザー名"""
    validate_github_username("octo-cat")  # Should not raise


def test_validate_repo_valid_with_special_chars() -> None:
    """ドット・アンダースコア・ハイフンを含む有効なリポジトリ名"""
    validate_github_repo("my-repo_v1.0")  # Should not raise


@pytest.mark.asyncio
async def test_client_successful_response() -> None:
    """正常レスポンスでJSONデータ返却"""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"X-RateLimit-Remaining": "100"}
    mock_response.json.return_value = {"login": "octocat", "id": 1}
    mock_response.raise_for_status = Mock()

    mock_httpx_client = AsyncMock()
    mock_httpx_client.request = AsyncMock(return_value=mock_response)
    mock_httpx_client.aclose = AsyncMock()

    async with AsyncGitHubClient() as client:
        client._client = mock_httpx_client

        result = await client._request("GET", "/users/octocat")

        assert result == {"login": "octocat", "id": 1}


# =============================================================================
# Public API Tests（条件4: 有効同値クラス）
# =============================================================================


@pytest.mark.asyncio
async def test_get_user_returns_user_data() -> None:
    """get_user()がユーザー情報を返却"""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"X-RateLimit-Remaining": "100"}
    mock_response.json.return_value = {"login": "octocat", "id": 1, "name": "The Octocat"}
    mock_response.raise_for_status = Mock()

    mock_httpx_client = AsyncMock()
    mock_httpx_client.request = AsyncMock(return_value=mock_response)
    mock_httpx_client.aclose = AsyncMock()

    async with AsyncGitHubClient() as client:
        client._client = mock_httpx_client

        result = await client.get_user("octocat")

        assert result["login"] == "octocat"
        assert result["name"] == "The Octocat"


@pytest.mark.asyncio
async def test_get_user_invalid_username_raises_value_error() -> None:
    """get_user()に無効なユーザー名でValueError発生"""
    async with AsyncGitHubClient() as client:
        with pytest.raises(ValueError) as exc_info:
            await client.get_user("-invalid")

        assert "Invalid GitHub username" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_repos_returns_list() -> None:
    """get_repos()がリポジトリリストを返却"""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"X-RateLimit-Remaining": "100"}
    mock_response.json.return_value = [{"name": "repo1"}, {"name": "repo2"}]
    mock_response.raise_for_status = Mock()

    mock_httpx_client = AsyncMock()
    mock_httpx_client.request = AsyncMock(return_value=mock_response)
    mock_httpx_client.aclose = AsyncMock()

    async with AsyncGitHubClient() as client:
        client._client = mock_httpx_client

        result = await client.get_repos("octocat")

        assert isinstance(result, list)
        assert len(result) == 2


@pytest.mark.asyncio
async def test_get_repo_returns_repo_data() -> None:
    """get_repo()がリポジトリ情報を返却"""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"X-RateLimit-Remaining": "100"}
    mock_response.json.return_value = {"name": "Hello-World", "stargazers_count": 100}
    mock_response.raise_for_status = Mock()

    mock_httpx_client = AsyncMock()
    mock_httpx_client.request = AsyncMock(return_value=mock_response)
    mock_httpx_client.aclose = AsyncMock()

    async with AsyncGitHubClient() as client:
        client._client = mock_httpx_client

        result = await client.get_repo("octocat", "Hello-World")

        assert result["name"] == "Hello-World"
        assert result["stargazers_count"] == 100


# =============================================================================
# Edge Case Tests（条件2: エラーパス追加）
# =============================================================================


@pytest.mark.asyncio
async def test_client_304_not_modified_returns_empty_dict() -> None:
    """304 Not Modifiedでキャッシュヒットとして空dict返却"""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 304
    mock_response.headers = {"X-RateLimit-Remaining": "100"}

    mock_httpx_client = AsyncMock()
    mock_httpx_client.request = AsyncMock(return_value=mock_response)
    mock_httpx_client.aclose = AsyncMock()

    async with AsyncGitHubClient() as client:
        client._client = mock_httpx_client

        result = await client._request("GET", "/users/test")

        assert result == {}


@pytest.mark.asyncio
async def test_client_etag_cache_update() -> None:
    """成功レスポンスでETagがキャッシュされる"""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {
        "X-RateLimit-Remaining": "100",
        "ETag": '"abc123"',
    }
    mock_response.json.return_value = {"login": "octocat"}
    mock_response.raise_for_status = Mock()

    mock_httpx_client = AsyncMock()
    mock_httpx_client.request = AsyncMock(return_value=mock_response)
    mock_httpx_client.aclose = AsyncMock()

    async with AsyncGitHubClient() as client:
        client._client = mock_httpx_client

        await client._request("GET", "/users/octocat")

        assert client._etag_cache.get("/users/octocat") == '"abc123"'


@pytest.mark.asyncio
async def test_client_invalid_json_raises_github_api_error() -> None:
    """不正なJSONレスポンスでGitHubAPIError発生"""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"X-RateLimit-Remaining": "100"}
    mock_response.json.side_effect = json.JSONDecodeError("Invalid", "doc", 0)
    mock_response.raise_for_status = Mock()

    mock_httpx_client = AsyncMock()
    mock_httpx_client.request = AsyncMock(return_value=mock_response)
    mock_httpx_client.aclose = AsyncMock()

    async with AsyncGitHubClient() as client:
        client._client = mock_httpx_client

        with pytest.raises(GitHubAPIError) as exc_info:
            await client._request("GET", "/users/test")

        assert "Invalid JSON" in str(exc_info.value)


# =============================================================================
# 学習ポイント:
#
# 1. バリデーション境界値テスト:
#    - 最小値・最大値・超過値のテスト
#    - 正規表現パターンの網羅的検証
#    - エラーメッセージの内容確認
#
# 2. 例外クラス設計テスト:
#    - 継承関係の検証（issubclass）
#    - 追加属性（reset_time等）の保持確認
#    - 例外メッセージの意味的な検証
#
# 3. 非同期クライアントテスト:
#    - コンテキストマネージャー使用の強制
#    - HTTPステータスコード別のエラーハンドリング
#    - Rate Limit判定ロジックの検証
#
# 4. モック活用パターン:
#    - patch.objectによるインスタンス属性モック
#    - AsyncMockによる非同期メソッドモック
#    - side_effectによる例外シミュレーション
#
# 5. 関数構造テスト設計:
#    - フラットな関数構造で可読性向上
#    - セクションコメントで論理グループ化
#    - 条件ベースの分類（境界値/エラーパス/有効同値）
# =============================================================================
