# GitHub API統合実装 - 実践ガイド

*最終更新: 2025年12月06日*

---

## 概要

本ドキュメントは、包括的評価レポート（GITHUB_API_INTEGRATION_EVALUATION.md）に基づいた実装の具体的な手順と注意点をまとめたものです。

**想定読者**: Week 4 Day 19-21でGitHub APIクライアント実装を担当する開発者
**前提知識**: @memory:coding_standards, @memory:implementation_quality_gates

---

## Part 1: 事前準備（5分）

### 1.1 環境確認

```bash
# Python バージョン確認
python3.12 --version  # 3.12.11以上必須

# 依存関係確認
uv pip list | grep -E "httpx|pytest|mypy|ruff"

# 既存テストが動作することを確認
uv run pytest tests/unit/test_async_client.py -v --tb=short
```

### 1.2 ブランチ準備

```bash
# 現在のブランチ確認
git branch -a | grep "local/history"

# 新しいブランチ作成
git checkout -b feature/github-api-client

# 確認
git branch | grep "*"
```

---

## Part 2: Step 1 ファイル作成（10分）

### 2.1 新規ファイルの作成と初期テンプレート

```bash
# ファイル作成
touch /Users/yuta/Yuta/python/api-test-devops-portfolio/utils/github_client.py
touch /Users/yuta/Yuta/python/api-test-devops-portfolio/tests/unit/test_github_client.py
touch /Users/yuta/Yuta/python/api-test-devops-portfolio/tests/integration/test_github_api.py

# ファイルが作成されたことを確認
ls -la utils/github_client.py tests/unit/test_github_client.py
```

### 2.2 初期テンプレート（utils/github_client.py）

**ファイルの先頭に以下を記述**:

```python
"""
GitHub API v3 client for portfolio demonstration.

このモジュールは、GitHub APIの公開エンドポイントを使用して
ユーザーとリポジトリ情報を取得するための非同期クライアントを提供します。

学習目標:
- 既存AsyncAPIClientの継承パターン
- GitHubエラーハンドリング（RateLimitError, NotFoundError）
- asyncio.gather()による並列API呼び出し
- 型安全な非同期実装（mypy --strict対応）
"""
```

---

## Part 3: Step 2 AsyncGitHubClient実装（60分）

### 3.1 実装順序（推奨）

以下の順序で実装することで、デバッグと修正が効率的になります：

#### 3.1.1 例外クラス（5分）

```python
# コピー元: utils/api_client.py (52-83行)
# パターン: 既存のAPIClientError階層を参考に、GitHubAPI固有例外を定義

# 実装箇所: utils/github_client.py 1-30行
```

**実装内容**:
- GitHubAPIError（基底）
- RateLimitError（403 + X-RateLimit-Remaining: 0）
- NotFoundError（404）

**チェックリスト**:
```python
from utils.api_client import APIClientError

# 継承確認: issubclass(GitHubAPIError, APIClientError) → True
# isinstance確認: except GitHubAPIError でキャッチ可能
```

---

#### 3.1.2 __init__メソッド（10分）

```python
# 実装箇所: utils/github_client.py 31-65行

# 重点ポイント:
# 1. super().__init__(base_url=self.GITHUB_API_URL) を忘れずに
# 2. self.token は None を許容（認証なしで60 req/hour）
# 3. self._headers は dict[str, str] 型注釈が必須（mypy --strict）
# 4. "Authorization": f"Bearer {token}" で type guard必要
```

**型安全な実装例**:
```python
def __init__(self, token: str | None = None) -> None:
    """..."""
    super().__init__(base_url=self.GITHUB_API_URL)
    self.token: str | None = token  # 型注釈
    self._headers: dict[str, str] = {  # 型注釈必須
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "API-Test-Portfolio",
    }
    if token:
        self._headers["Authorization"] = f"Bearer {token}"
```

---

#### 3.1.3 _handle_response()メソッド（15分）

**実装焦点**: エラーハンドリングの正確性

```python
# 実装箇所: utils/github_client.py 66-95行

# 関键控制流（C2 fix対応）:
# 1. 404 NotFound → 即座に NotFoundError を raise
# 2. 403 Forbidden → X-RateLimit-Remaining チェック
#    - "0" の場合: RateLimitError を raise
#    - それ以外: raise_for_status()へ
# 3. その他の4xx/5xx → raise_for_status()
# 4. 200-299 → response.json() を解析

# 型安全:
async def _handle_response(
    self, response: httpx.Response
) -> dict[str, Any]:
    # ...
    return cast(dict[str, Any], response.json())
```

**デバッグのコツ**:
- response.status_code の値を print() で確認
- response.headers.get("X-RateLimit-Remaining") の値を確認

---

#### 3.1.4 単純なメソッド（20分）

以下3つのメソッドは同一パターンで、並行実装可能：

```python
# パターン:
# 1. 引数の型チェック（空文字列チェック等は後のC5対応）
# 2. self._client.get() で API呼び出し
# 3. await self._handle_response(response) でエラー処理
# 4. 戻り値の型注釈

async def get_user(self, username: str) -> dict[str, Any]:
    response = await self._client.get(
        f"/users/{username}",
        headers=self._headers
    )
    return await self._handle_response(response)

# get_repos(), get_repo_languages() も同一パターン
```

**所要時間**: 3メソッド × 6分 = 18分

---

#### 3.1.5 get_portfolio_summary() - asyncio.gather()実装（10分）

**重点ポイント**: 並列実行と例外処理

```python
async def get_portfolio_summary(
    self, username: str
) -> dict[str, Any]:
    import asyncio

    # Step 1: 2つのタスクを並列実行
    user_task = self.get_user(username)
    repos_task = self.get_repos(username, per_page=5)
    user, repos = await asyncio.gather(user_task, repos_task)

    # Step 2: トップ3のリポジトリの言語情報を並列取得
    language_tasks = [
        self.get_repo_languages(username, repo["name"])
        for repo in repos[:3]
    ]
    languages = await asyncio.gather(
        *language_tasks,
        return_exceptions=True  # ★重要: 部分的失敗を許容
    )

    # Step 3: データ集約
    return {
        "user": {...},
        "top_repos": [...],
        "languages": [...]
    }
```

**デバッグのコツ**:
- `asyncio.gather(*tasks)` の `*` を忘れないこと
- `return_exceptions=True` で例外もリストに含まれる
- 例外はフィルタリング: `if not isinstance(lang, Exception)`

---

### 3.2 実装中の品質チェック

実装完了ごとに以下を実施：

```bash
# 構文チェック
python3.12 -m py_compile utils/github_client.py

# インポート確認
uv run python -c "from utils.github_client import AsyncGitHubClient"

# 型チェック（段階的）
uv run mypy utils/github_client.py  # 初回は多数エラー想定
```

---

## Part 4: Step 3 テストケース実装（25分）

### 4.1 テスト作成の準備（5分）

```bash
# conftest.py の mock_response fixture を確認
grep -A 20 "def mock_response" tests/conftest.py

# 既存パターン参照
grep -A 30 "async def test_async_get_user" tests/unit/test_async_client.py
```

### 4.2 コア5テストの実装（20分）

#### テスト1: test_github_get_user_success（3分）

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from utils.github_client import AsyncGitHubClient

@pytest.mark.asyncio
async def test_github_get_user_success():
    """Test successful user profile retrieval."""
    user_data = {
        "login": "testuser",
        "name": "Test User",
        "followers": 100,
    }

    with patch.object(
        AsyncGitHubClient, '_client', new_callable=AsyncMock
    ) as mock_client:
        # モック応答設定
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = user_data
        mock_client.get.return_value = mock_response

        # テスト実行
        async with AsyncGitHubClient() as client:
            result = await client.get_user("testuser")

        # 検証
        assert result["login"] == "testuser"
        assert result["followers"] == 100
```

**コピーペーストのコツ**:
- mock_response のセットアップは各テストで同一パターン
- status_code, json() の return_value を変更するだけで多くのテストケースに対応

---

#### テスト2-4: test_github_get_repos, test_rate_limit, test_not_found（15分）

**実装のテンプレート化**:

```python
def create_mock_response(status_code: int, json_data: dict = None, headers: dict = None):
    """モック応答ファクトリー"""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data or {}
    response.headers = headers or {}
    response.url = "https://api.github.com/test"
    return response

# 各テストで再利用
mock_response = create_mock_response(200, {"name": "repo1"})
```

---

#### テスト5: test_github_portfolio_summary_parallel（2分）

```python
@pytest.mark.asyncio
async def test_github_portfolio_summary_parallel(mock_response):
    """Test asyncio.gather() for parallel API calls."""
    user_data = {"name": "Test", "followers": 100, "public_repos": 50}
    repos_data = [{"name": "repo1", "stargazers_count": 10, "language": "Python"}]
    languages_data = {"Python": 10000}

    with patch.object(
        AsyncGitHubClient, '_client', new_callable=AsyncMock
    ) as mock_client:
        # side_effect で複数の応答を順序指定
        mock_client.get.side_effect = [
            create_mock_response(200, user_data),
            create_mock_response(200, repos_data),
            create_mock_response(200, languages_data),
        ]

        async with AsyncGitHubClient() as client:
            result = await client.get_portfolio_summary("testuser")

        assert result["user"]["name"] == "Test"
        assert len(result["top_repos"]) >= 1
```

---

### 4.3 テスト実行と検証

```bash
# テスト実行
uv run pytest tests/unit/test_github_client.py -v

# カバレッジ確認
uv run pytest tests/unit/test_github_client.py --cov=utils.github_client --cov-report=term-missing

# 予想結果: 90%以上のカバレッジ
```

---

## Part 5: Step 4 品質ゲート実行（30分）

### 5.1 Gate 1: pytest + カバレッジ

```bash
# Week 4の目標: 70%
uv run pytest --cov=utils --cov=config --cov-fail-under=70

# 結果確認
# PASSED ... Coverage: 70% (target: 70%) ✅
```

**失敗時の対応**:
```bash
# どのファイルが未カバーか確認
uv run pytest --cov-report=term-missing

# github_client.py の未カバー行を特定
# → テストを追加
```

---

### 5.2 Gate 2: ruff check

```bash
# 自動修正含む
uv run ruff check --fix .

# 結果確認（0 errors を目指す）
uv run ruff check utils/github_client.py
```

**よくあるエラーと修正**:

| エラー | 原因 | 修正 |
|------|------|------|
| Line too long | 行が100文字超過 | 行分割 |
| Unused import | import文が不要 | 削除 |
| F821 undefined | 変数未定義 | 変数名確認 |

---

### 5.3 Gate 3: mypy --strict ★重要

```bash
# 実行
uv run mypy utils/github_client.py --strict

# 評価レポート§2で予想された 8個のエラーが出現
# 例:
# error: Need type annotation for "_headers" [var-annotated]
# error: Return type is not "dict[str, Any]" [return-value]
```

**修正手順（§2参照）**:

1. **属性型注釈追加** (5分)
   ```python
   self._headers: dict[str, str] = {...}
   ```

2. **response.json()型キャスト** (10分)
   ```python
   from typing import cast
   return cast(dict[str, Any], response.json())
   ```

3. **メソッド戻り値の型調整** (10分)
   ```python
   async def get_repo_languages(...) -> dict[str, int]:
       data = await self._handle_response(response)
       return cast(dict[str, int], data)
   ```

4. **asyncio.gather()型注釈** (15分)
   ```python
   results = await asyncio.gather(user_task, repos_task)
   user, repos = cast(
       tuple[dict[str, Any], list[dict[str, Any]]],
       results
   )
   ```

5. **再実行確認**
   ```bash
   uv run mypy utils/github_client.py --strict
   # Success: no issues found
   ```

---

### 5.4 Gate 4: git commit

```bash
# ステージング確認
git status

# 最後の見直し（mypy, ruff, pytest全合格確認）
uv run pytest --cov-fail-under=70 && \
uv run ruff check . && \
uv run mypy utils/github_client.py --strict

# コミット
git add utils/github_client.py tests/unit/test_github_client.py tests/integration/test_github_api.py

git commit -m "feat(github-api): add async GitHub API client with parallel operations

- Implement AsyncGitHubClient with get_user, get_repos, get_repo_languages
- Add get_portfolio_summary() with asyncio.gather() for parallel API calls
- Implement GitHub-specific error handling (RateLimitError, NotFoundError)
- Add comprehensive unit tests with 97% code coverage
- Full mypy --strict compliance with type hints"

# 確認
git log --oneline | head -1
```

---

## Part 6: 追加タスク（オプション、Day 20-21）

### 6.1 C5: 境界値テスト追加

Day 20に追加：

```python
# tests/unit/test_github_client.py に追加

@pytest.mark.asyncio
async def test_get_repos_with_max_per_page():
    """Test per_page=100 (GitHub API maximum)."""
    # ...

@pytest.mark.asyncio
async def test_get_user_with_empty_username():
    """Test empty username handling."""
    # ...
```

---

### 6.2 H3: Rate Limit Reset時刻活用（オプション）

```python
# utils/github_client.py に追加

async def _handle_response_with_reset(
    self, response: httpx.Response
) -> dict[str, Any]:
    """Rate Limit Reset時刻を含むレスポンス処理"""
    import time

    if response.status_code == 403:
        remaining = response.headers.get("X-RateLimit-Remaining", "1")
        if remaining == "0":
            reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
            current_time = int(time.time())
            wait_seconds = max(0, reset_time - current_time)
            raise RateLimitError(
                f"Rate limit exceeded. Retry after {wait_seconds} seconds."
            )
```

---

## Part 7: トラブルシューティング

### 7.1 よくあるエラーと対策

| エラー | 原因 | 対策 |
|------|------|------|
| `ImportError: cannot import name 'AsyncGitHubClient'` | モジュール構文エラー | 構文確認: `python -m py_compile` |
| `mypy error: Return type is not ...` | 型推論失敗 | cast()使用（§2参照） |
| `test failed: AttributeError: AsyncClient has no _client` | モック設定ミス | patch対象を確認 |
| `RateLimitError raised unexpectedly` | ヘッダー値チェック誤り | `response.headers.get()` の値を print() |

---

### 7.2 デバッグコマンド集

```bash
# 構文チェック
python3.12 -m py_compile utils/github_client.py

# インポート確認
uv run python -c "from utils.github_client import AsyncGitHubClient, RateLimitError"

# 単一テスト実行
uv run pytest tests/unit/test_github_client.py::test_github_get_user_success -vv

# 型チェック詳細
uv run mypy utils/github_client.py --show-error-codes

# カバレッジレポート HTML化
uv run pytest --cov=utils.github_client --cov-report=html:reports/htmlcov
open reports/htmlcov/index.html
```

---

## Part 8: チェックリスト

### 最終実装確認

```
[ ] ファイル作成
    [ ] utils/github_client.py
    [ ] tests/unit/test_github_client.py
    [ ] tests/integration/test_github_api.py

[ ] Step 2: AsyncGitHubClient実装
    [ ] 例外クラス（GitHubAPIError, RateLimitError, NotFoundError）
    [ ] __init__()
    [ ] _handle_response()
    [ ] get_user()
    [ ] get_repos()
    [ ] get_repo_languages()
    [ ] get_portfolio_summary()

[ ] Step 3: テスト実装
    [ ] test_github_get_user_success
    [ ] test_github_get_repos_with_pagination
    [ ] test_github_rate_limit_error
    [ ] test_github_not_found_error
    [ ] test_github_portfolio_summary_parallel

[ ] Step 4: 品質ゲート
    [ ] pytest 全テスト合格
    [ ] カバレッジ 70%以上達成
    [ ] ruff check 0 errors
    [ ] mypy --strict 0 errors
    [ ] git commit実行済み

[ ] オプション（Day 20-21）
    [ ] C5: 境界値テスト（per_page=100, empty_username）
    [ ] H3: Rate Limit Reset時刻対応
    [ ] README 更新（使用例追加）
```

---

## 参考資料

- **評価レポート**: `GITHUB_API_INTEGRATION_EVALUATION.md`（全体戦略）
- **既存パターン**: `utils/api_client.py` (901行) - AsyncAPIClient実装
- **テスト参考**: `tests/unit/test_async_client.py` (617行) - asyncio.gather()パターン
- **品質ゲート**: @memory:implementation_quality_gates
- **型注釈規約**: @memory:coding_standards

---

*このガイドに従うことで、安定した品質のGitHub APIクライアント実装が期待できます。*
*実装中の質問や不明な点は、評価レポートの関連セクションを参照してください。*
