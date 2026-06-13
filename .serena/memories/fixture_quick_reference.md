# pytest Fixture クイックリファレンス

*最終更新: 2026年06月13日*

`tests/conftest.py`で定義された **14 フィクスチャ** のクイックリファレンス。新規テスト作成時の効率的なフィクスチャ選択を支援。

> **Note**: 行番号は編集のたびにずれて陳腐化するため記載しない。定義の正確な位置は `tests/conftest.py` を直接参照すること。
> モックHTTPは専用フィクスチャではなく **respx**（トランスポート層モック）または `client._client = AsyncMock()` で行う（後述）。

---

## 1. フィクスチャ一覧

### 1.1 基本フィクスチャ

| フィクスチャ名 | スコープ | 用途 | 依存 |
|--------------|---------|------|------|
| `test_config` | session | API設定 dict（base_url, timeout 等） | - |
| `logger` | function | テスト用ロガー | - |
| `mock_base_url` | function | unitテスト用ダミーURL `https://test.local`（外部通信なし） | - |

> **Note**: pytest-asyncio + `asyncio_mode="auto"`（pyproject.toml）で非同期テストは自動検出。`@pytest.mark.asyncio` は不要。

### 1.2 API関連フィクスチャ

| フィクスチャ名 | スコープ | 用途 | 依存 |
|--------------|---------|------|------|
| `async_client` | function | 実 `AsyncAPIClient` インスタンス（`@pytest_asyncio.fixture`・統合テスト用） | test_config |
| `sample_api_response` | function | サンプルJSONレスポンス（JSONPlaceholder TODO形式） | - |

### 1.3 テストデータファクトリー

| フィクスチャ名 | スコープ | 用途 | パラメータ例 |
|--------------|---------|------|-------------|
| `todo_data_factory` | function | TODOデータ生成 | `user_id`, `todo_id`, `title`, `completed` |
| `user_data_factory` | function | ユーザーデータ生成（住所・会社情報含む） | `user_id`, `name`, `username`, `email` |
| `post_data_factory` | function | 投稿データ生成 | `user_id`, `post_id`, `title`, `body` |

### 1.4 専門テスト用フィクスチャ

| フィクスチャ名 | スコープ | 用途 | 対象テスト |
|--------------|---------|------|-----------|
| `performance_timer` | function | 実行時間計測タイマー（start/stop/elapsed/assert_faster_than） | @pytest.mark.performance |
| `integration_test_data` | function | 大量テストデータセット（todos/users） | @pytest.mark.integration |

> **Note**: `integration_test_data` は function スコープ（デフォルト）で各テストに独立した dict を提供。

### 1.5 自動実行フィクスチャ（autouse=True）

| フィクスチャ名 | スコープ | 用途 |
|--------------|---------|------|
| `disable_sentry_for_tests` | function | Sentry送信無効化（`SENTRY__ENABLED=false`） |
| `cleanup_test_files` | function | テンポラリファイル削除（`test_*.tmp`） |
| `reset_settings` | function | 設定リロード（テスト独立性保証・yield前後の2回実行） |
| `reset_sentry_warning_state` | function | `utils.logger` の Sentry warning throttle 状態をテスト前後でリセット |

---

## 2. 使用シーン別ガイド

### 2.1 単体テスト（respx でトランスポート層モック）

実テストの標準パターンは **respx**。`mock_base_url` をベースURLに使い外部通信を発生させない。

```python
import respx

@respx.mock
async def test_api_method(mock_base_url, sample_api_response):
    """respx でHTTPトランスポート層をモック"""
    route = respx.get(f"{mock_base_url}/todos/1").respond(json=sample_api_response)
    # client = AsyncAPIClient(base_url=mock_base_url) ...
    # result = await client.get("/todos/1")
    assert route.called
```

**使用フィクスチャ**: `mock_base_url` + `sample_api_response`

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
@pytest.mark.integration
async def test_real_api(async_client):
    """実 AsyncAPIClient を使った統合テスト（asyncio_mode='auto' でマーカー不要）"""
    result = await async_client.get("/posts/1")
    assert result["id"] == 1
```

**使用フィクスチャ**: `async_client`

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

### 2.4 パフォーマンステスト

```python
@pytest.mark.performance
async def test_response_time(performance_timer, async_client):
    """レスポンス時間の計測"""
    performance_timer.start()
    await async_client.get("/posts")
    performance_timer.stop()
    performance_timer.assert_faster_than(1.0, "1秒以内に応答すべき")
```

**使用フィクスチャ**: `performance_timer` + `async_client`


### 2.5 ファクトリーパターン

| 状況 | 推奨 | 理由 |
|-----|------|------|
| 全テストで同一データ | 固定フィクスチャ (`sample_api_response`) | シンプル・高速 |
| テストごとに異なるデータ | ファクトリー (`todo_data_factory`) | 柔軟性・独立性 |
| パラメータバリエーション必要 | ファクトリー必須 | `@pytest.mark.parametrize` との組み合わせ |

```python
def test_custom_todo(todo_data_factory):
    todo = todo_data_factory(user_id=5, completed=True)
    assert todo["userId"] == 5
    assert todo["completed"] is True
```

---

## 3. 依存関係図

```
session scope
└── test_config
    └── async_client (depends on test_config)

function scope
├── logger
├── mock_base_url
├── sample_api_response
├── todo_data_factory
├── user_data_factory
├── post_data_factory
├── performance_timer
└── integration_test_data

autouse (function scope)
├── disable_sentry_for_tests
├── cleanup_test_files
├── reset_settings
└── reset_sentry_warning_state
```

---

## 4. 注意事項

### 4.1 スコープの違い

| スコープ | 生成タイミング | 使用場面 |
|---------|--------------|---------|
| `session` | テスト実行全体で1回 | 高コストな初期化 |
| `function` | テスト関数ごと | 独立性が必要なテスト（推奨・デフォルト） |

> **可変型 fixture のスコープ選択**: 可変型(list/dict)を返す fixture は `scope="function"` を推奨。session/module で共有する場合は `copy.deepcopy()` を使用。

### 4.2 async fixture の使用

```python
# ✅ async 関数として定義（asyncio_mode="auto" で自動検出）
async def test_async(async_client):
    result = await async_client.get("/posts")
```

### 4.3 autouse fixture の影響

| フィクスチャ | タイミング | 動作 |
|------------|-----------|------|
| `disable_sentry_for_tests` | テスト前 | `SENTRY__ENABLED=false` を設定（本番への誤送信防止） |
| `cleanup_test_files` | テスト後 | `test_*.tmp` を自動削除 |
| `reset_settings` | 各テスト前後 | 設定をリロード（テスト間汚染防止・yield前後2回） |
| `reset_sentry_warning_state` | 各テスト前後 | logger の Sentry warning throttle 状態をリセット |

---

## 5. 登録済みテストマーカー

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

## 6. 関連リソース

- **conftest.py**: `tests/conftest.py`（411行）
- **テスト戦略**: @memory:test_strategy_details
- **実装品質ゲート**: @memory:implementation_quality_gates
