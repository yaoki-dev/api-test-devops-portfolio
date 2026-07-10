# pytest Fixture クイックリファレンス

*最終更新: 2026年07月10日*

`tests/conftest.py`で定義された **7 フィクスチャ** のクイックリファレンス。新規テスト作成時の効率的なフィクスチャ選択を支援。

> **Note**: 行番号は編集のたびにずれて陳腐化するため記載しない。定義の正確な位置は `tests/conftest.py` を直接参照すること。
> モックHTTPは専用フィクスチャではなく **respx**（トランスポート層モック）または `client._client = AsyncMock()` で行う（後述）。

---

## 1. フィクスチャ一覧

### 1.1 基本フィクスチャ

| フィクスチャ名 | スコープ | 用途 | 依存 |
|--------------|---------|------|------|
| `logger` | function | テスト用ロガー | - |
| `mock_base_url` | function | unitテスト用ダミーURL `https://test.local`（外部通信なし） | - |

> **Note**: pytest-asyncio + `asyncio_mode="auto"`（pyproject.toml）で非同期テストは自動検出。`@pytest.mark.asyncio` は不要。

### 1.2 自動実行フィクスチャ（autouse=True）

| フィクスチャ名 | スコープ | 用途 |
|--------------|---------|------|
| `disable_sentry_for_tests` | function | Sentry送信無効化（`SENTRY__ENABLED=false`） |
| `isolate_proxy_env` | session | プロキシ系環境変数（HTTP_PROXY等）を除去し、httpxクライアント生成を実行環境から隔離 |
| `cleanup_test_files` | function | テンポラリファイル削除（`test_*.tmp`） |
| `reset_settings` | function | 設定リロード（テスト独立性保証・各テスト実行前に1回） |
| `reset_sentry_warning_state` | function | `utils.logger` の Sentry warning throttle 状態をテスト前後でリセット |

---

## 2. 使用シーン別ガイド

### 2.1 単体テスト（respx でトランスポート層モック）

実テストの標準パターンは **respx**。`mock_base_url` をベースURLに使い外部通信を発生させない。

```python
import respx

@respx.mock
async def test_api_method(mock_base_url):
    """respx でHTTPトランスポート層をモック"""
    sample_response = {"userId": 1, "id": 1, "title": "delectus aut autem", "completed": False}
    route = respx.get(f"{mock_base_url}/todos/1").respond(json=sample_response)
    # client = AsyncAPIClient(base_url=mock_base_url) ...
    # result = await client.get("/todos/1")
    assert route.called
```

**使用フィクスチャ**: `mock_base_url`（テストデータはテスト内でインラインに定義）

別法（クライアント内部の httpx を直接差し替え）:

```python
from unittest.mock import AsyncMock

async def test_with_asyncmock():
    client = AsyncAPIClient(base_url="https://test.local")
    client._client = AsyncMock()  # 内部 httpx.AsyncClient を差し替え
    # ...
```

### 2.2 統合テスト（実API）

```python
# マーカーはファイル冒頭の pytestmark で付与済み（例: pytestmark = [pytest.mark.integration, ...]）
async def test_real_api() -> None:
    """実 AsyncJSONPlaceholderClient を使った統合テスト（asyncio_mode='auto' で @pytest.mark.asyncio 不要）"""
    async with AsyncJSONPlaceholderClient() as client:
        post = await client.get_post(post_id=1)
        assert post.id == 1
```

**使用フィクスチャ**: なし（クライアントはテスト内で `async with AsyncJSONPlaceholderClient() as client:` により直接構築）

### 2.3 エラーハンドリングテスト（respx の side_effect）

```python
import httpx
import respx

@respx.mock
async def test_timeout_handling(mock_base_url):
    """タイムアウト例外を respx で注入"""
    respx.get(f"{mock_base_url}/posts").mock(side_effect=httpx.TimeoutException("timeout"))
    # タイムアウト時の挙動を検証
```

**使用フィクスチャ**: `mock_base_url`

---

## 3. 注意事項

### 3.1 スコープの違い

| スコープ | 生成タイミング | 使用場面 |
|---------|--------------|---------|
| `session` | テスト実行全体で1回 | 高コストな初期化 |
| `function` | テスト関数ごと | 独立性が必要なテスト（推奨・デフォルト） |

> **可変型 fixture のスコープ選択**: 可変型(list/dict)を返す fixture は `scope="function"` を推奨。session/module で共有する場合は `copy.deepcopy()` を使用。

### 3.2 async fixture の使用

```python
# ✅ async 関数として定義（asyncio_mode="auto" で自動検出）
async def test_async() -> None:
    async with AsyncJSONPlaceholderClient() as client:
        result = await client.get_post(post_id=1)
```

### 3.3 autouse fixture の影響

| フィクスチャ | タイミング | 動作 |
|------------|-----------|------|
| `disable_sentry_for_tests` | テスト前 | `SENTRY__ENABLED=false` を設定（本番への誤送信防止） |
| `isolate_proxy_env` | セッション開始時（1回） | プロキシ系環境変数を除去し httpx クライアント生成を実行環境から隔離 |
| `cleanup_test_files` | テスト後 | `test_*.tmp` を自動削除 |
| `reset_settings` | 各テスト前 | 設定をリロード（テスト間汚染防止・実行前1回） |
| `reset_sentry_warning_state` | 各テスト前後 | logger の Sentry warning throttle 状態をリセット |

---

## 4. 登録済みテストマーカー

conftest.py `pytest_configure()` で登録:

| マーカー | 用途 |
|---------|------|
| `smoke` | スモークテスト（main PR用） |
| `unit` | 単体テスト |
| `integration` | 統合テスト |
| `external` | 外部API依存テスト |
| `slow` | 実行時間の長いテスト |
| `performance` | パフォーマンステスト |

---

## 5. 関連リソース

- **conftest.py**: `tests/conftest.py`（203行）
- **テスト戦略**: @memory:test_strategy_details
- **実装品質ゲート**: @memory:implementation_quality_gates
