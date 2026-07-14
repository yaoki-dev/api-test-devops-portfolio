"""
GitHub API Integration Tests（実API呼び出し）

Note:
- Rate Limit制約: 認証なし60 req/h
- @pytest.mark.externalで分離（週次CIで実行）
- 手動実行コマンド: pytest -m external
"""

import pytest

from utils.github_client import AsyncGitHubClient
from utils.github_error_handler import NotFoundError

pytestmark = [pytest.mark.external, pytest.mark.integration]


async def test_get_user():
    async with AsyncGitHubClient() as client:
        user = await client.get_user("octocat")

        # 必須フィールド確認
        assert user["login"] == "octocat"
        assert "name" in user
        assert "public_repos" in user
        assert "followers" in user
        assert "created_at" in user

        # 型確認
        assert isinstance(user["login"], str)
        assert isinstance(user["public_repos"], int)


async def test_get_repos():
    async with AsyncGitHubClient() as client:
        repos = await client.get_repos("octocat", per_page=5, sort="updated")

        # 取得件数確認
        assert len(repos) <= 5

        # 必須フィールド確認
        for repo in repos:
            assert "name" in repo
            assert "full_name" in repo
            assert "stargazers_count" in repo
            assert "updated_at" in repo
            assert isinstance(repo["name"], str)
            assert isinstance(repo["stargazers_count"], int)


async def test_get_repo():
    async with AsyncGitHubClient() as client:
        repo = await client.get_repo("octocat", "Hello-World")

        # 必須フィールド確認
        assert repo["name"] == "Hello-World"
        assert repo["full_name"] == "octocat/Hello-World"
        assert "stargazers_count" in repo
        assert "forks_count" in repo
        assert "open_issues_count" in repo
        assert "description" in repo

        # 型確認
        assert isinstance(repo["stargazers_count"], int)
        assert isinstance(repo["forks_count"], int)


async def test_not_found_error():
    async with AsyncGitHubClient() as client:
        with pytest.raises(NotFoundError) as exc_info:
            await client.get_user("nonexistent-user-12345")

        assert "Resource not found" in str(exc_info.value)
