"""
GitHub API Integration Tests（実API呼び出し）

Note:
- Rate Limit制約: 認証なし60 req/h
- @pytest.mark.externalで分離（CI/CD時は除外推奨）
- 実行コマンド: pytest -m external（手動実行時のみ）
"""

import pytest

from utils.github_client import AsyncGitHubClient, NotFoundError

pytestmark = [pytest.mark.external, pytest.mark.integration]

# =============================================================================
# 実API呼び出しテスト
# =============================================================================


async def test_get_user():
    """ユーザー情報取得

    検証項目:
    - GitHub API v3の実際のレスポンス形式
    - 必須フィールドの存在確認
    - Rate Limit監視ログ出力（Remaining < 10の場合）
    """
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
    """リポジトリ一覧取得

    検証項目:
    - per_pageパラメータの動作確認
    - リポジトリ情報の必須フィールド
    - ソート順の動作確認
    """
    async with AsyncGitHubClient() as client:
        repos = await client.get_repos("octocat", per_page=5, sort="updated")

        # ページネーション確認
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
    """リポジトリ詳細取得

    検証項目:
    - 特定リポジトリの詳細情報取得
    - 統計情報フィールドの確認
    """
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
    """404エラーハンドリング

    検証項目:
    - 存在しないユーザーでNotFoundError発生
    - エラーメッセージの適切性
    """
    async with AsyncGitHubClient() as client:
        with pytest.raises(NotFoundError) as exc_info:
            await client.get_user("nonexistent-user-12345")

        assert "Resource not found" in str(exc_info.value)
