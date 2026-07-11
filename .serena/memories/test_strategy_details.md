# テスト戦略・詳細実装ガイド

*最終更新: 2026年06月07日*

> **概要版**: @memory:test_strategy を参照

---

## 1. テストアーキテクチャ詳細

### 1.1 テストピラミッド実装

| テスト層 | 比率 | 実行時間 | 環境 | 目的 |
|---------|------|---------|------|------|
| Unit | 70% | <0.5s/test | ローカル | モック中心、外部依存排除 |
| Integration | 30% | 1-3s/test | docker compose | 実API、コンポーネント連携 |

**設計根拠**: Mike Cohn提唱（2009年）、Google Testing Blog推奨構成

### 1.2 テスト層実装例

#### Unit Test (respx によるトランスポート層モック)
```python
# ファイル冒頭で pytestmark = pytest.mark.unit（モジュール単位でマーカー付与）
# @pytest.mark.asyncio: asyncio_mode = "auto" (pyproject.toml) のため不要
# pytest-asyncio が async テストを自動検出する
@respx.mock
async def test_async_get_user_parses_into_model() -> None:
    """respx で HTTP トランスポートを差し替え、実通信なしで検証する"""
    respx.get(f"{BASE_URL}/users/1").respond(json=make_canonical_user(1))

    async with AsyncJSONPlaceholderClient() as client:
        user = await client.get_user(user_id=1)

    assert user.id == 1
    assert user.address.city == "Gwenborough"
```

`make_canonical_user()` は `tests/unit/helpers.py` のテストデータ生成ヘルパー。
JSONPlaceholder 実 API に近い完全な User ペイロードを返す。
クライアント内部の `_client` を差し替えるのではなく、respx がトランスポート層で
リクエストを捕捉するため、テストは実装の内部構造に依存しない。

#### Integration Test (実API)
```python
# ファイル冒頭で pytestmark = [pytest.mark.integration, ...]
# @pytest.mark.asyncio: asyncio_mode = "auto" (pyproject.toml) のため不要
async def test_real_api_user_workflow() -> None:
    """実API使用: ユーザーデータ取得ワークフロー"""
    async with AsyncJSONPlaceholderClient() as client:
        user = await client.get_user(user_id=1)
        assert user.id == 1
        posts = await client.get_posts(user_id=1)
        assert len(posts) > 0
```

---

## 2. フィクスチャ設計パターン

### 2.1 respx によるトランスポート層モック
```python
import respx

@respx.mock
async def test_api_method(mock_base_url):
    """mock_base_url をベースURLに使い外部通信を発生させない"""
    respx.get(f"{mock_base_url}/todos/1").respond(json={"id": 1, "completed": False})
    # client = AsyncAPIClient(base_url=mock_base_url) ...
```

### 2.2 統合テストでのクライアント構築
専用の async クライアントフィクスチャは持たず、統合テストごとに
`async with AsyncJSONPlaceholderClient() as client:` でインラインに構築する
（テスト間の独立性を優先する設計）。
```python
# マーカーはファイル冒頭の pytestmark で付与済み（1.2 参照）
async def test_real_api_user_workflow() -> None:
    async with AsyncJSONPlaceholderClient() as client:
        user = await client.get_user(user_id=1)
        assert user.id == 1
```

### 2.3 スコープ選択基準
- `session`: プロセス全体で1回だけ実行すべき処理（例: `isolate_proxy_env` によるプロキシ環境変数の隔離）
- `module`: 共有可能データ
- `function`: テスト独立性優先（デフォルト）

---

## 3. カバレッジ戦略

### 3.1 優先モジュール

1. **utils/ フラットモジュール群**（旧 api_client.py を責任単位で分割）
   - `utils/jsonplaceholder_base_sync.py`: SyncAPIClient (同期ベースクライアント)
   - `utils/jsonplaceholder_base_async.py`: AsyncAPIClient (非同期ベースクライアント)
   - `utils/jsonplaceholder_client_sync.py`: SyncJSONPlaceholderClient (同期JSONPlaceholder)
   - `utils/jsonplaceholder_client_async.py`: AsyncJSONPlaceholderClient (非同期JSONPlaceholder)
   - `utils/retry.py`: 指数バックオフ + ジッター (リトライロジック)
   - `utils/exceptions.py`: API例外階層 (APIClientError 以下)
   - `utils/http_helpers.py`: エラーハンドリング、設定解決、バリデーション
   - `utils/response_parsing.py`: JSONパース + Pydanticモデル変換
   - **カバレッジ: 97.34%** (1381 tests passed)

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
trivy image --severity HIGH,CRITICAL api-test-devops:latest
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
# @pytest.mark.asyncio: asyncio_mode = "auto" (pyproject.toml) のため、@pytest.mark.asyncio は不要
# pytest-asyncio が async テストを自動検出する
async def test_concurrent_requests() -> None:
    # 3件全て必須（fail-fast）のため TaskGroup を使用（coding-standards.md §6）。
    # 部分成功を許容する場合のみ gather(return_exceptions=True) を検討する。
    async with AsyncJSONPlaceholderClient() as client:
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(client.get_user(user_id=i)) for i in (1, 2, 3)]
    users = [task.result() for task in tasks]
    assert len(users) == 3
```

### 6.3 セマフォ制限

本番コードの `AsyncJSONPlaceholderClient.get_multiple_users()`
（`utils/jsonplaceholder_client_async.py`）が `asyncio.Semaphore` による
同時実行数制御の実装例。

```python
async with AsyncJSONPlaceholderClient() as client:
    users = await client.get_multiple_users([1, 2, 3], max_concurrent=2)
```

---

## 7. パフォーマンステスト

### 7.1 メトリクス
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

## 10. 将来計画

### 検討項目
- **負荷テスト**: Locust統合
- **Mutation Testing**: mutmut導入
- **Property-Based Testing**: Hypothesis
- **E2Eテスト**: Web UI 実装時に再評価（現状スコープ外）

### 成功の定義
1. カバレッジ85%達成 (実績: 96.15%)
2. CI/CD品質ゲート自動化
3. OWASP API Security Top 10準拠
4. P95応答時間 <500ms
