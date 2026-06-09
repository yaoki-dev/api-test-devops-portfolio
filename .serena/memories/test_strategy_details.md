# テスト戦略・詳細実装ガイド

*最終更新: 2026年06月07日*

> **概要版**: @memory:test_strategy を参照

---

## 1. テストアーキテクチャ詳細

### 1.1 テストピラミッド実装

| テスト層 | 比率 | 実行時間 | 環境 | 目的 |
|---------|------|---------|------|------|
| Unit | 70% | <0.5s/test | ローカル | モック中心、外部依存排除 |
| Integration | 30% | 1-3s/test | docker-compose | 実API、コンポーネント連携 |

**設計根拠**: Mike Cohn提唱（2009年）、Google Testing Blog推奨構成

### 1.2 テスト層実装例

#### Unit Test (モック中心)
```python
@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_get_user_with_mock(mock_httpx_client, sample_user_data):
    """モックを使った非同期ユーザー取得テスト"""
    mock_httpx_client.get.return_value = mock_response(
        status_code=200, json_data=sample_user_data
    )
    async with AsyncAPIClient() as client:
        client._client = mock_httpx_client
        user = await client.get("/users/1")
    assert user["id"] == 1
    mock_httpx_client.get.assert_called_once()
```

#### Integration Test (実API)
```python
@pytest.mark.integration
@pytest.mark.external
@pytest.mark.asyncio
async def test_real_api_user_workflow():
    """実API使用: ユーザーデータ取得ワークフロー"""
    async with AsyncJSONPlaceholderClient() as client:
        user = await client.get_user(user_id=1)
        assert user["id"] == 1
        posts = await client.get_user_posts(user_id=1)
        assert len(posts) > 0
```

---

## 2. フィクスチャ設計パターン

### 2.1 Factory Pattern
```python
@pytest.fixture
def todo_data_factory():
    """TODOテストデータファクトリー"""
    def create_todo(user_id: int = 1, todo_id: int = 1, 
                    title: str = "Test TODO", completed: bool = False):
        return {"userId": user_id, "id": todo_id, 
                "title": title, "completed": completed}
    return create_todo
```

### 2.2 Async Fixture
```python
@pytest_asyncio.fixture
async def async_client(test_config) -> AsyncGenerator[AsyncAPIClient, None]:
    """非同期HTTPクライアント（テスト用）"""
    async with AsyncAPIClient(
        base_url=test_config["api"]["base_url"],
        timeout=test_config["api"]["timeout"],
    ) as client:
        yield client
```

### 2.3 スコープ選択基準
- `session`: 重い初期化（test_config）
- `module`: 共有可能データ
- `function`: テスト独立性優先（デフォルト）

---

## 3. カバレッジ戦略

### 3.1 優先モジュール

1. **utils/api_client.py** (1,653行 wc -l / 435 stmts)
   - リトライロジック (lines 117-247)
   - 非同期並行処理 (lines 509-582)
   - エラーハンドリング (lines 324-395)
   - **カバレッジ: 92.22%**（残未カバー: 437, 636-637, 827-828, 1307-1308, 1317-1319, 1518, 1562, 1595, 1612-1637, 1641-1646）

2. **models/responses.py** (~350行)
   - Pydanticモデル
   - @field_validator
   - sanitize_user_content() XSS保護

3. **config/settings.py** (~450行 wc -l / 205 stmts) ✅ 97.59%達成

### 3.3 除外パターン
```python
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if self.debug:",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]
```

---

## 4. CIセキュリティチェック

> **Note**: 本プロジェクトではセキュリティテストを実装せず、CI/CDでの静的解析に集約する方針（2025-12-25決定）

### 4.1 静的セキュリティ解析（CI実行）

```bash
# Pythonコードの脆弱性スキャン
uv run bandit -r utils/ config/ models/ -f json -o reports/bandit.json
```

### 4.2 コンテナセキュリティ（Docker）

```bash
# TrivyによるDockerイメージスキャン
trivy image --severity HIGH,CRITICAL api-test:latest
```

### 4.3 シークレット検出（gitleaks）

```bash
# ハードコードされたシークレット検出
gitleaks detect --source . --verbose
```

### 4.4 チェック頻度

| チェック | 実行タイミング | ツール |
|--------|--------------|--------|
| コード脆弱性 | 毎 PR | bandit |
| シークレット検出 | 毎 PR | gitleaks |
| 依存関係 | 週次 | Dependabot |
| filesystem scan | 毎 PR (develop/main) | Trivy |
| コンテナ image scan | main向け PR + リリース時 | Trivy |

---

## 5. 実行戦略

### 5.1 マーカー組み合わせ

| シナリオ | マーカー | 時間目安 |
|---------|---------|---------|
| ローカル開発 | `unit and not slow` | <30秒 |
| コミット前 | `(unit or integration) and not external` | <3分 |
| 週次包括 | `security or performance` | 5-15分 |

### 5.2 CI/CDステージ

| ステージ | トリガー | テスト種別 |
|---------|---------|-----------|
| PR Validation (develop) | pull_request to develop | unit + integration (cov) → smoke |
| PR Validation (main) | pull_request to main | unit + integration (cov) → smoke（developと同一） |
| Post-Merge | push to main | + smoke |
| Weekly | schedule (日曜) | + security + performance |

### 5.3 品質ゲート
```bash
# Week別統合検証
uv run pytest -n auto -m "(unit or integration) and not external" \
  --cov=utils --cov=config --cov=models --cov-report=term-missing \
  && uv run ruff check . \
  && uv run mypy utils/ config/ models/ \
  && git status
```

---

## 6. 非同期テストパターン

### 6.1 pytest-asyncio設定
```python
# pyproject.toml
asyncio_mode = "auto"  # 非同期テスト自動検出
```

### 6.2 並行テスト
```python
@pytest.mark.asyncio
async def test_concurrent_requests(async_client):
    users = await asyncio.gather(
        async_client.get("/users/1"),
        async_client.get("/users/2"),
        async_client.get("/users/3"),
    )
    assert len(users) == 3
```

### 6.3 セマフォ制限
```python
semaphore = asyncio.Semaphore(3)  # 同時3リクエストまで
async def fetch_user(user_id: int):
    async with semaphore:
        return await async_client.get(f"/users/{user_id}")
```

---

## 7. パフォーマンステスト

### 7.1 performance_timer Fixture
```python
@pytest.fixture
def performance_timer():
    class Timer:
        def start(self): self.start_time = time.perf_counter()
        def stop(self): self.end_time = time.perf_counter()
        @property
        def elapsed(self): return self.end_time - self.start_time
        def assert_faster_than(self, threshold, message=""):
            if self.elapsed > threshold:
                pytest.fail(f"{self.elapsed:.3f}s > {threshold:.3f}s. {message}")
    return Timer()
```

### 7.2 メトリクス
- P50, P95, P99 応答時間
- スループット (req/sec)
- メモリ使用量

---

## 8. メンテナンス

### 8.1 テストコード品質
- **DRY**: Factory Pattern活用
- **命名**: `test_[機能]_[ケース]`
- **docstring必須**: 検証項目明記

### 8.2 技術的負債管理
```python
@pytest.mark.skip(reason="TODO: Week 6実装予定")
def test_future_feature():
    pass
```

### 8.3 週次レビューチェックリスト
- [ ] TODOコメント確認
- [ ] Skipマーカー解除可能か
- [ ] カバレッジ変動確認
- [ ] テスト実行時間確認

---

## 9. トラブルシューティング

| 問題 | 原因 | 解決策 |
|------|------|--------|
| カバレッジが上がらない | モジュール指定ミス | `--cov=utils --cov=config` |
| Event loop is closed | asyncio_mode未設定 | `asyncio_mode = "auto"` |
| 並列実行で失敗 | グローバル状態汚染 | reset_settings autouse |
| モック動作しない | spec未指定 | `Mock(spec=TargetClass)` |
| タイムアウト頻発 | CI環境遅延 | CI_MULTIPLIER = 3 |

---

## 10. 将来計画 (Week 6完了後)

### 検討項目
- **負荷テスト**: Locust統合
- **Mutation Testing**: mutmut導入
- **Property-Based Testing**: Hypothesis
- **E2Eテスト**: Web UI 実装時に再評価（現状スコープ外）

### 成功の定義
1. カバレッジ85%達成
2. CI/CD品質ゲート自動化
3. OWASP API Security Top 10準拠
4. P95応答時間 <500ms
