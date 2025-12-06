# 改善2: GitHub API統合（HIGH）:該当week5

*最終更新: 2025年11月26日*

## 3.1 課題と解決策

**課題**: JSONPlaceholderは学習用のため、実務的な技術力の証明が弱い

**解決策**: GitHub APIの公開エンドポイント（認証不要）を統合し、実用的なAPI操作を実装

**選定理由**:
- 認証不要（Rate Limit: 60 req/hour、実装・テストに十分）
- 開発者親和性が高い（採用担当者がエンジニアの場合、共感を得やすい）
- ポートフォリオで自然（自分のリポジトリ情報取得で実用的）

## 3.2 API比較（GitHub vs 他）

| API | 認証 | Rate Limit | 開発者親和性 | 実装難易度 |
|-----|------|-----------|------------|-----------|
| **GitHub REST API** | 不要 | 60 req/h | ★★★★★ | ★★☆☆☆ |
| Twitter API v2 | 必要 | 500 req/15min | ★★★★☆ | ★★★☆☆ |
| Qiita API | 必要 | 60 req/h | ★★★☆☆ | ★★☆☆☆ |
| Stripe API | 必要 | Unlimited | ★★☆☆☆ | ★★★★☆ |

**GitHub API選定理由**:
- 認証不要（`.env`管理不要、セキュリティリスク低）
- ポートフォリオとして自然（自リポジトリ統計取得）
- 採用担当者の理解促進（GitHubは全エンジニアが利用）

---

## 3.3 実装ファイル構成

```
utils/
├── api_client.py
└── github_client.py          # 新規作成

tests/
├── unit/
│   └── test_github_client.py # 新規作成
└── integration/
    └── test_github_api.py     # 新規作成

config/
└── settings.py               # 変更なし（既存のAPI設定を流用）
```

---

## 3.4 例外階層設計

```python
# utils/github_client.py

class GitHubAPIError(Exception):
    """GitHub API基底例外"""
    pass

class RateLimitError(GitHubAPIError):
    """Rate Limit超過エラー（403 Forbidden）"""
    def __init__(self, reset_time: int):
        self.reset_time = reset_time
        super().__init__(f"Rate limit exceeded. Reset at {reset_time}")

class NotFoundError(GitHubAPIError):
    """リソースが見つからない（404 Not Found）"""
    pass

class GitHubServerError(GitHubAPIError):
    """GitHub側のサーバーエラー（5xx）"""
    pass
```

---

## 3.5 AsyncGitHubClient実装

```python
# utils/github_client.py

import httpx
from typing import Dict, List, Optional
from datetime import datetime

class AsyncGitHubClient:
    """GitHub API非同期クライアント

    特徴:
    - Rate Limit自動対応（X-RateLimit-Remaining監視）
    - Conditional Requests対応（ETag活用）
    - リトライロジック（5xxエラーのみ）
    """

    BASE_URL = "https://api.github.com"

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        user_agent: str = "AsyncGitHubClient/1.0"
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent
        self._client: Optional[httpx.AsyncClient] = None
        self._etag_cache: Dict[str, str] = {}  # URL -> ETag

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=self.timeout,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": self.user_agent,
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def get_user(self, username: str) -> Dict:
        """ユーザー情報取得

        Args:
            username: GitHubユーザー名

        Returns:
            ユーザー情報（name, bio, public_repos等）

        Raises:
            NotFoundError: ユーザーが存在しない
            RateLimitError: Rate Limit超過

        Example:
            >>> async with AsyncGitHubClient() as client:
            ...     user = await client.get_user("octocat")
            ...     print(user["name"])  # "The Octocat"
        """
        return await self._request("GET", f"/users/{username}")

    async def get_repos(
        self,
        username: str,
        sort: str = "updated",
        per_page: int = 30
    ) -> List[Dict]:
        """ユーザーのリポジトリ一覧取得

        Args:
            username: GitHubユーザー名
            sort: ソート順（created, updated, pushed, full_name）
            per_page: 1ページあたりの件数（最大100）

        Returns:
            リポジトリ情報リスト

        Example:
            >>> repos = await client.get_repos("octocat", sort="stars")
            >>> print(repos[0]["name"])  # 最もスターが多いリポジトリ
        """
        params = {"sort": sort, "per_page": per_page}
        return await self._request("GET", f"/users/{username}/repos", params=params)

    async def get_repo(self, owner: str, repo: str) -> Dict:
        """リポジトリ詳細取得

        Args:
            owner: オーナー名
            repo: リポジトリ名

        Returns:
            リポジトリ詳細（stars, forks, open_issues等）

        Example:
            >>> repo = await client.get_repo("octocat", "Hello-World")
            >>> print(repo["stargazers_count"])  # スター数
        """
        return await self._request("GET", f"/repos/{owner}/{repo}")

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None
    ) -> Dict | List[Dict]:
        """内部リクエストメソッド

        機能:
        - Rate Limit監視（X-RateLimit-Remaining < 10で警告ログ）
        - Conditional Requests（ETag活用、304 Not Modified対応）
        - 5xxエラーリトライ（指数バックオフ）
        - 4xxエラー即失敗（NotFoundError, RateLimitError例外）
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context.")

        # Conditional Requests: ETagヘッダー追加
        headers = {}
        if endpoint in self._etag_cache:
            headers["If-None-Match"] = self._etag_cache[endpoint]

        for attempt in range(self.max_retries):
            try:
                response = await self._client.request(
                    method,
                    endpoint,
                    params=params,
                    headers=headers
                )

                # Rate Limit監視
                remaining = int(response.headers.get("X-RateLimit-Remaining", 999))
                if remaining < 10:
                    reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                    reset_dt = datetime.fromtimestamp(reset_time)
                    # TODO: structlog警告ログ追加
                    print(f"⚠️  Rate limit low: {remaining} requests remaining. Reset at {reset_dt}")

                # ステータスコード処理
                if response.status_code == 304:
                    # 304 Not Modified: キャッシュ有効
                    return {}

                if response.status_code == 404:
                    raise NotFoundError(f"Resource not found: {endpoint}")

                if response.status_code == 403:
                    # Rate Limit超過
                    reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                    raise RateLimitError(reset_time)

                if response.status_code >= 500:
                    # 5xxエラー: リトライ
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # 指数バックオフ
                        continue
                    raise GitHubServerError(f"Server error: {response.status_code}")

                response.raise_for_status()

                # ETagキャッシュ更新
                if "ETag" in response.headers:
                    self._etag_cache[endpoint] = response.headers["ETag"]

                return response.json()

            except httpx.HTTPStatusError as e:
                if e.response.status_code < 500:
                    # 4xxエラー: リトライしない
                    raise
                if attempt == self.max_retries - 1:
                    raise GitHubServerError(f"Failed after {self.max_retries} retries")
```

**セキュリティ注意**:
- ✅ 認証トークン不要（公開API使用）
- ✅ Rate Limit対応（`X-RateLimit-Remaining`監視）
- ✅ User-Agentヘッダー設定（GitHub要求事項）
- ⚠️ 本番環境では認証トークン使用推奨（Rate Limit: 60 → 5000 req/h）

---

## 3.6 テストケース設計

### Unit Tests（3件）

```python
# tests/unit/test_github_client.py

import pytest
from unittest.mock import AsyncMock, patch
from utils.github_client import AsyncGitHubClient, NotFoundError, RateLimitError

@pytest.mark.asyncio
async def test_get_user_success():
    """ユーザー情報取得成功"""
    async with AsyncGitHubClient() as client:
        with patch.object(client._client, 'request', new_callable=AsyncMock) as mock:
            mock.return_value.status_code = 200
            mock.return_value.json.return_value = {"login": "octocat", "name": "The Octocat"}
            mock.return_value.headers = {"X-RateLimit-Remaining": "59"}

            user = await client.get_user("octocat")

            assert user["login"] == "octocat"
            assert user["name"] == "The Octocat"

@pytest.mark.asyncio
async def test_get_user_not_found():
    """ユーザーが存在しない（404）"""
    async with AsyncGitHubClient() as client:
        with patch.object(client._client, 'request', new_callable=AsyncMock) as mock:
            mock.return_value.status_code = 404

            with pytest.raises(NotFoundError):
                await client.get_user("nonexistent-user-12345")

@pytest.mark.asyncio
async def test_rate_limit_exceeded():
    """Rate Limit超過（403）"""
    async with AsyncGitHubClient() as client:
        with patch.object(client._client, 'request', new_callable=AsyncMock) as mock:
            mock.return_value.status_code = 403
            mock.return_value.headers = {"X-RateLimit-Reset": "1640000000"}

            with pytest.raises(RateLimitError) as exc_info:
                await client.get_user("octocat")

            assert exc_info.value.reset_time == 1640000000
```

### Integration Tests（2件）

```python
# tests/integration/test_github_api.py

import pytest
from utils.github_client import AsyncGitHubClient

@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_user_real_api():
    """実API: ユーザー情報取得"""
    async with AsyncGitHubClient() as client:
        user = await client.get_user("octocat")

        assert user["login"] == "octocat"
        assert "name" in user
        assert "public_repos" in user

@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_repos_real_api():
    """実API: リポジトリ一覧取得"""
    async with AsyncGitHubClient() as client:
        repos = await client.get_repos("octocat", per_page=5)

        assert len(repos) <= 5
        assert all("name" in repo for repo in repos)
```

---

## 3.7 実装手順（Day 26）

### Step 1: 例外クラス定義（0.5H）

```bash
# utils/github_client.py に例外階層追加
# GitHubAPIError, RateLimitError, NotFoundError, GitHubServerError
```

### Step 2: AsyncGitHubClient実装（1.5H）

```bash
# utils/github_client.py にAsyncGitHubClient実装
# 機能: get_user, get_repos, get_repo, _request
```

### Step 3: Unit Tests作成（0.5H）

```bash
# tests/unit/test_github_client.py に3件のテスト追加
uv run pytest tests/unit/test_github_client.py -v
```

### Step 4: Integration Tests作成（0.5H）

```bash
# tests/integration/test_github_api.py に2件のテスト追加
uv run pytest tests/integration/test_github_api.py -v --integration
```

### Step 5: カバレッジ確認（0.5H）

```bash
uv run pytest --cov=utils.github_client --cov-report=term-missing
# 目標: 75%以上（Rate Limit警告ログ部分は除外可）
```

---

## 3.8 成功基準（L2改善: 定量的KPI明記）

*検証完了: 2025年11月28日*

**実装完了**:
- [✔︎] `AsyncGitHubClient`実装完了（3メソッド: get_user, get_repos, get_repo）
- [✔︎] 例外階層実装完了（4クラス: GitHubAPIError, RateLimitError, NotFoundError, GitHubServerError）
- [✔︎] Rate Limit対応実装済み（`X-RateLimit-Remaining`監視）
- [✔︎] Conditional Requests実装済み（ETagキャッシュ）

**テスト品質**:
- [✔︎] Unit Tests 3件作成・全合格 → **18件達成**（目標の6倍）
- [✔︎] Integration Tests 2件作成・全合格 → **5件達成**（目標の2.5倍）
- [✔︎] カバレッジ75%以上（`utils/github_client.py`） → **91.67%達成**

**品質ゲート**:
- [✔︎] pytest全合格（0 failed） → 18 unit + 5 integration passed
- [✔︎] ruff check合格（0 errors） → "All checks passed!"
- [✔︎] mypy strict合格（0 errors） → "Success: no issues found"

**統合確認**:
- [✔︎] 実API呼び出し成功（`octocat`ユーザー情報取得）
- [✔︎] Rate Limit警告ログ出力確認（Remaining < 10の場合） → structlog実装
- [✔︎] 404エラー時にNotFoundError例外発生確認

---

## 3.9 Rate Limit管理戦略

### 開発環境（認証なし）

**制限**: 60 requests/hour

**対策**:
1. **テストモック化**: Integration Tests以外は全てモック使用
2. **キャッシュ活用**: ETagによるConditional Requests（304 Not Modified時はRate Limit消費なし）
3. **警告ログ**: Remaining < 10で警告表示

### 本番環境（認証あり、将来対応）

**制限**: 5000 requests/hour（Personal Access Token使用時）

**実装例**（参考、Week 6以降の拡張）:
```python
class AsyncGitHubClient:
    def __init__(self, token: Optional[str] = None, ...):
        self.token = token
        # ...

    async def __aenter__(self):
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": self.user_agent,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=self.timeout,
            headers=headers
        )
        return self
```
