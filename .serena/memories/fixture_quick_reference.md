# pytest Fixture クイックリファレンス

*最終更新: 2026年03月04日*

conftest.py（540行）から抽出した20フィクスチャのクイックリファレンス。新規テスト作成時の効率的なフィクスチャ選択を支援。

---

## 1. フィクスチャ一覧

### 1.1 基本フィクスチャ

| フィクスチャ名 | スコープ | 用途 | 依存 | 行番号 |
|--------------|---------|------|------|--------|
| `test_config` | session | API設定（base_url, timeout等） | - | L136 |
| `logger` | function | テスト用ロガー | - | L154 |

> **Note**: pytest-asyncio 1.1.0 + `asyncio_mode="auto"`で非同期テストは自動管理。

### 1.2 API関連フィクスチャ

| フィクスチャ名 | スコープ | 用途 | 依存 | 行番号 |
|--------------|---------|------|------|--------|
| `async_client` | function | 実際のAsyncAPIClientインスタンス（※非同期・pytest_asyncio） | test_config | L165 |
| `mock_httpx_client` | function | モック化httpx.AsyncClient（後方互換性用） | - | L178 |
| `mock_httpx_async_client` | function | モック化非同期HTTPXクライアント（明示的async命名） | - | L194 |
| `mock_httpx_sync_client` | function | モック化同期HTTPXクライアント（httpx.Client） | - | L211 |
| `mock_response_factory` | function | ステータス/JSON/ヘッダーを指定してモックレスポンス生成するファクトリー | - | L224 |
| `sample_api_response` | function | サンプルJSONレスポンス（JSONPlaceholder TODO形式） | - | L265 |
| `mock_successful_response` | function | 成功レスポンス（200） | sample_api_response | L271 |
| `mock_error_response` | function | エラーレスポンス（404） | - | L283 |

### 1.3 テストデータファクトリー

| フィクスチャ名 | スコープ | 用途 | パラメータ例 | 行番号 |
|--------------|---------|------|-------------|--------|
| `todo_data_factory` | function | TODOデータ生成 | `user_id`, `todo_id`, `title`, `completed` | L304 |
| `user_data_factory` | function | ユーザーデータ生成（住所・会社情報含む） | `user_id`, `name`, `username`, `email` | L324 |
| `post_data_factory` | function | 投稿データ生成 | `user_id`, `post_id`, `title`, `body` | L358 |

### 1.4 専門テスト用フィクスチャ

| フィクスチャ名 | スコープ | 用途 | 対象テスト | 行番号 |
|--------------|---------|------|-----------|--------|
| `performance_timer` | function | 実行時間計測タイマー（start/stop/elapsed/assert_faster_than） | @pytest.mark.performance | L378 |
| `error_scenarios` | function | エラーシナリオ辞書 | エラーハンドリング | L414 |
| `security_payloads` | function | 攻撃ペイロード辞書 | セキュリティテスト | L434 |
| `integration_test_data` | function | 大量テストデータセット（todos 15件, users 3件） | @pytest.mark.integration | L466 |

> **Note**: `integration_test_data`はfunctionスコープ（デフォルト）で各テストに独立したdictを提供。

### 1.5 自動実行フィクスチャ（autouse=True）

| フィクスチャ名 | スコープ | 用途 | 行番号 |
|--------------|---------|------|--------|
| `disable_sentry_for_tests` | function | Sentry送信無効化（SENTRY__ENABLED=false） | L114 |
| `cleanup_test_files` | function | テンポラリファイル削除（test_*.tmp） | L492 |
| `reset_settings` | function | 設定リロード（テスト独立性保証） | L503 |

---

## 2. 使用シーン別ガイド

### 2.1 単体テスト（モック使用）

```python
def test_api_method(mock_httpx_client, sample_api_response):
    """モックを使った単体テスト"""
    from unittest.mock import Mock

    mock_httpx_client.get.return_value = Mock(
        status_code=200,
        json=lambda: sample_api_response
    )
    # テストロジック
```

**使用フィクスチャ**: `mock_httpx_client` + `sample_api_response`

**async APIテスト時**:
```python
async def test_async_api_with_mock(mock_httpx_client):
    """
    mock_httpx_clientはconftest.pyで.get/.post等がAsyncMock()として設定済み。
    return_valueにはMock()を設定可能（AsyncMockがawait時に自動返却）。

    Note: @pytest.mark.asyncioは不要（pyproject.toml: asyncio_mode="auto"）
    """
    from unittest.mock import Mock

    # conftest.py L186: mock_client.get = AsyncMock() 済み
    mock_httpx_client.get.return_value = Mock(
        status_code=200,
        json=lambda: {"id": 1, "title": "Test"}
    )
    result = await mock_httpx_client.get("/posts/1")
    assert result.status_code == 200
```

### 2.2 統合テスト（実API）

```python
@pytest.mark.integration
async def test_real_api(async_client):
    """実APIを使った統合テスト

    Note: @pytest.mark.asyncioは不要（pyproject.toml: asyncio_mode="auto"）
    """
    result = await async_client.get("/posts/1")
    assert result["id"] == 1
```

**使用フィクスチャ**: `async_client`

### 2.3 エラーハンドリングテスト

```python
def test_timeout_handling(mock_httpx_client, error_scenarios):
    """タイムアウトエラーのテスト"""
    mock_httpx_client.get.side_effect = error_scenarios["timeout"]
    # タイムアウト時の挙動検証
```

**使用フィクスチャ**: `mock_httpx_client` + `error_scenarios`

**error_scenarios キー一覧**:
- `timeout`: httpx.TimeoutException
- `connection_error`: httpx.ConnectError
- `http_error`: httpx.HTTPStatusError (500)
- `json_decode_error`: json.JSONDecodeError

### 2.4 パフォーマンステスト

```python
@pytest.mark.performance
async def test_response_time(performance_timer, async_client):  # asyncio_mode="auto"でマーカー不要
    """レスポンス時間の計測"""
    performance_timer.start()
    await async_client.get("/posts")
    performance_timer.stop()
    performance_timer.assert_faster_than(1.0, "1秒以内に応答すべき")
```

**使用フィクスチャ**: `performance_timer` + `async_client`

### 2.5 セキュリティテスト

```python
async def test_sql_injection(async_client, security_payloads):  # asyncio_mode="auto"でマーカー不要
    """SQLインジェクション耐性テスト"""
    for payload in security_payloads["sql_injection"]:
        result = await async_client.post("/posts", json={"title": payload})
        # インジェクション攻撃が無効化されていることを確認
```

**使用フィクスチャ**: `async_client` + `security_payloads`

**security_payloads キー一覧**:
- `sql_injection`: SQLインジェクションペイロード
- `xss`: XSSペイロード
- `command_injection`: コマンドインジェクションペイロード
- `path_traversal`: パストラバーサルペイロード

### 2.6 ファクトリーパターン

**使用判断基準**:

| 状況 | 推奨 | 理由 |
|-----|------|------|
| 全テストで同一データ | 固定フィクスチャ (`sample_api_response`) | シンプル・高速 |
| テストごとに異なるデータ | ファクトリー (`todo_data_factory`) | 柔軟性・独立性 |
| パラメータバリエーション必要 | ファクトリー必須 | `@pytest.mark.parametrize`との組み合わせ |

```python
def test_custom_todo(todo_data_factory):
    """カスタムパラメータでテストデータ生成"""
    todo = todo_data_factory(user_id=5, completed=True)
    assert todo["userId"] == 5
    assert todo["completed"] is True
```

**使用フィクスチャ**: `*_data_factory`

---

## 3. 依存関係図

```
session scope
└── test_config
    └── async_client (depends on test_config)

function scope
├── sample_api_response
│   └── mock_successful_response (depends on sample_api_response)
├── mock_httpx_client
├── mock_httpx_async_client
├── mock_httpx_sync_client
├── mock_response_factory
├── mock_error_response
├── todo_data_factory
├── user_data_factory
├── post_data_factory
├── performance_timer
├── error_scenarios
├── security_payloads
├── integration_test_data
└── logger

autouse (function scope)
├── disable_sentry_for_tests
├── cleanup_test_files
└── reset_settings
```

---

## 4. 注意事項

### 4.1 スコープの違い

| スコープ | 生成タイミング | 使用場面 |
|---------|--------------|---------|
| `session` | テスト実行全体で1回 | 高コストな初期化（DB接続等） |
| `module` | モジュール単位で1回 | 関連テスト間で共有可能なデータ |
| `function` | テスト関数ごと | 独立性が必要なテスト（推奨） |

> **可変型fixtureのスコープ選択基準**:
> - 可変型(list/dict)を返すfixtureは`scope="function"`を推奨
> - module/session scopeで可変型を共有する場合は`copy.deepcopy()`を使用

### 4.2 async fixtureの使用

```python
# ✅ 正しい使用法①: async関数として定義（asyncio_mode="auto"で自動検出）
async def test_async(async_client):
    result = await async_client.get("/posts")

# ❌ エラー: sync関数かasync fixtureを使用
def test_sync(async_client):  # RuntimeError
    pass
```

### 4.3 autouse fixtureの影響

| フィクスチャ | 実行タイミング | 動作 |
|------------|--------------|------|
| `disable_sentry_for_tests` | テスト前 | `SENTRY__ENABLED=false`を設定（本番へのエラー誤送信防止） |
| `cleanup_test_files` | テスト後 | `test_*.tmp` ファイルを自動削除 |
| `reset_settings` | 各テスト前後 | 設定をリロード（テスト間汚染防止） |

**パフォーマンス注意**: `reset_settings`は各テストの**前後**で2回実行されます（yield前後）。大量テスト実行時はオーバーヘッドを考慮してください。

---

## 5. 登録済みテストマーカー

conftest.py `pytest_configure()`で登録済み:

| マーカー | 用途 | 行番号 |
|---------|------|--------|
| `unit` | 単体テスト | L88 |
| `integration` | 統合テスト | L89 |
| `slow` | 実行時間の長いテスト | L91 |
| `external` | 外部API依存テスト | L92 |
| `performance` | パフォーマンステスト | L93 |
| `smoke` | スモークテスト（main PR用） | L94 |

> **Note**: `security`マーカーは2025-12-25に削除済み（プロジェクトでセキュリティテストを実装しないため）。
> `security_payloads`フィクスチャはテストデータ例として残存。

---

## 6. 改善推奨事項

### 6.1 高優先度

1. ~~**integration_test_dataのscope変更検討**~~ → **解決済み**
   - 現状: `scope="function"`（デフォルト）で各テスト独立
   - ステータス: ✅ 問題なし

---

## 7. 関連リソース

- **conftest.py**: `tests/conftest.py`（540行）
- **テスト戦略**: @memory:test_strategy
- **詳細実装ガイド**: @memory:test_strategy_details
- **実装品質ゲート**: @memory:implementation_quality_gates
