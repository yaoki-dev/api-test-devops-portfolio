# テスト戦略・詳細実装ガイド

*最終更新: 2026年07月17日*

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
>
> **2026-08-20 改訂**: 本セクションは `.github/workflows/`、`pyproject.toml`、`.pre-commit-config.yaml` の実測に基づき全面改訂。旧版は bandit と gitleaks を「CI実行・毎PR」と記載していたが、いずれも CI 未統合であり事実に反していた。

### 4.1 静的セキュリティ解析（SAST）

**CI実行・マージブロック**: ruff の flake8-bandit ルール群（`S`）

```bash
uv run ruff check .   # .github/workflows/ci.yml の pr-validation ジョブ
```

- 有効化: `pyproject.toml` の `[tool.ruff.lint] select` に `"S"`（flake8-bandit 全体）
- 無効化: `S101`（assert）と `S603`（subprocess）をグローバル ignore、`tests/**` は `S101` を追加除外
- 現行設定での違反件数: 0

**手動実行・CI未統合**: bandit

```bash
uv run bandit -r utils/ config/ models/   # CI では実行されない
```

- `rg 'bandit|safety' .github/workflows/` → 0 hits
- ruff の `S` ルール実装数は **73**、bandit のプラグインテストIDは **42**（bandit の blacklist `B3xx`/`B4xx` は ruff の `S3xx`/`S4xx` が対応）
- bandit のみが検出できる残差: `B603`（ruff では ignore 中）、`B613`（trojansource）。`B614`/`B615`/`B703` は PyTorch / HuggingFace / Django 向けのため本プロジェクトには該当しない
- ruff のみが検出できる範囲: `S601`（bandit は `[tool.bandit] skips` で `B601` を無効化）、および `tests/**` 配下全体（bandit は `exclude_dirs = ["tests"]`）
- 結論: 現行設定では ruff の `S` ルール群のほうが bandit より検査範囲が広い。bandit の CI 統合は費用対効果が低い

**既知のギャップ**: `S603` をグローバル ignore しているため、`scripts/check_docstring_refactor.py` の `subprocess.run` 3箇所が未検査。`uv run ruff check --select S603 scripts/` で再現できる。

### 4.2 依存関係脆弱性スキャン（SCA）

**CI実行・マージブロック**: Trivy filesystem scan

- `uv.lock` を `Type=uv` として解析する
- `severity: CRITICAL,HIGH` + `exit-code: 1`（`.github/workflows/trivy-scan.yml` の「Trivy filesystem gate」ステップ）
- **カバー範囲は 85/85 パッケージ**（開発依存込み）。`fs-scan`/`fs-gate` の両ステップに `env: TRIVY_INCLUDE_DEV_DEPS: "true"` を設定し本番依存(21件)+開発依存(64件)を対象化した
- Trivy CLI の `--include-dev-deps` フラグの `--help` 説明文は「supported: npm, yarn, gradle」とのみ記載され `uv` は明記されないが、実測では `uv.lock` にも有効（`trivy fs --scanners vuln uv.lock` で 21 パッケージ、`--include-dev-deps` 追加で 85 パッケージに増加）。ヘルプ文言と実挙動が一致しない未文書化の動作であり、trivy-action には対応する `with` 入力が無いため `env: TRIVY_INCLUDE_DEV_DEPS` で有効化する
- 検出内訳（85件全体）は root 1 + direct 22 + indirect 62。うち開発依存分（Dev=true）は direct 15 + indirect 49 = 64 件、本番依存分（Dev=false）は root 1 + direct 7 + indirect 13 = 21 件。`trivy fs --include-dev-deps --list-all-pkgs --format json` で再現できる

**手動実行・CI未統合**: safety

```bash
uv run safety scan   # 対話ログインを要求するため非対話環境では未検証
```

**週次**: Dependabot（`uv` / `npm` / `github-actions` / `docker` の4エコシステム、いずれも `interval: "weekly"`）

### 4.3 コンテナセキュリティ（Docker）

**CI実行・マージブロック**: Trivy image scan（`severity: CRITICAL,HIGH` + `exit-code: 1`）

実行条件:

- PR: `github.base_ref == 'main'` または `docker` ラベル付き（`ci.yml` の `pr-trivy-scan`）
- push: `main` / `develop`（`ci.yml` の `post-trivy-scan`、`scan-image: true`）

### 4.4 シークレット検出

**ローカル pre-commit フックのみ**: gitleaks

```bash
gitleaks git --pre-commit --staged --verbose --redact   # .pre-commit-config.yaml
```

- **CI未統合**: `ci.yml` は pre-commit を実行しない。`autoupdate-precommit.yml` は pre-commit の autoupdate 用に gitleaks バイナリを導入するのみ
- CI 側は Trivy の secret scanner が代替する
- `trivy-scan.yml` の全4ステップ（fs-scan/fs-gate/image-scan/image-gate）に `scanners: "vuln,secret"` を明示固定し、既定値変更によるサイレントなスキャナードリフトを防止する。

### 4.5 チェック頻度（実測）

| 種別 | チェック内容 | 実行タイミング | ツール | マージブロック |
|------|------------|--------------|--------|--------------|
| SAST | コード脆弱性 | 毎 PR | ruff `S` ルール群 | ✅ |
| SAST | コード脆弱性 | 手動のみ | bandit | ❌ CI未統合 |
| SCA | 依存関係脆弱性 | 毎 PR + push(main/develop) | Trivy fs（本番+開発依存 85/85） | ✅ |
| SCA | 依存関係脆弱性 | 手動のみ | safety | ❌ CI未統合 |
| SCA | 依存関係更新 | 週次 | Dependabot | ❌ |
| コンテナ | image 脆弱性 | main向けPR / dockerラベルPR / push(main/develop) | Trivy image | ✅ |
| シークレット | 平文シークレット | ローカルコミット時 | gitleaks | ❌ CI未統合 |
| シークレット | 平文シークレット | 毎 PR | Trivy secret（明示 `vuln,secret`） | ✅ ブロック中 |

**補足**: 上表の「マージブロック」は各ワークフローの `exit-code: 1` 設定に基づく。実際のマージ阻止には GitHub branch protection の required status checks 登録が別途必要。

**Trivy secret の設定固定状態（ブロック状態とは別軸）**: 上表の secret 行は現在 `severity: CRITICAL,HIGH` + `exit-code: 1` により実際にブロックする。`trivy-scan.yml` の全4ステップ（fs-scan/fs-gate/image-scan/image-gate）に `scanners: "vuln,secret"` を明示固定しているため、trivy-action の既定値変更による secret スキャンのサイレントな無効化を防止する。

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
- **docstring方針**: 言い換えは削除、WHY のみ残す（coding-standards.md §4.1）

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
