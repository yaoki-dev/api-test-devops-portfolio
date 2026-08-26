# Project Index: api-test-devops-portfolio

**Generated:** 2026-08-25
**Version:** 0.1.0
**Python:** ==3.14.*

---

## 📁 Project Structure

```
api-test-devops-portfolio/
├── README.md                 # プロジェクト概要・セットアップ手順
├── PROJECT_INDEX.md          # リポジトリ構成と主要ドキュメントの索引
├── REVIEW.md                 # コードレビュー基準と重大度定義
├── CHANGELOG.md              # 変更履歴（Keep a Changelog / SemVer 準拠）
├── CONTEXT.md                # ドメイン用語定義（現状は「CD実証」1項目のみ）
├── CLAUDE.md                 # Claude Code 向けプロジェクト指示書
├── AGENTS.md                 # エージェント向けプロジェクト指示
├── config/                 # 設定管理（Pydantic Settings）
│   ├── __init__.py
│   └── settings.py        # 型安全な環境変数管理
├── models/                 # データモデル定義
│   ├── __init__.py
│   └── responses.py       # APIレスポンスモデル
├── utils/                  # コアユーティリティ
│   ├── __init__.py
│   ├── exceptions.py      # 共有例外階層（APIClientError 等）
│   ├── retry.py           # リトライ遅延計算ヘルパー
│   ├── http_helpers.py    # HTTP配管ヘルパー（バリデーション/エラーマッピング）
│   ├── response_parsing.py # レスポンス解析（Pydantic検証）
│   ├── jsonplaceholder_base_sync.py   # SyncAPIClient（HTTP基盤・同期）
│   ├── jsonplaceholder_base_async.py  # AsyncAPIClient（HTTP基盤・非同期）
│   ├── jsonplaceholder_client_sync.py # SyncJSONPlaceholderClient
│   ├── jsonplaceholder_client_async.py # AsyncJSONPlaceholderClient
│   ├── github_client.py   # GitHub API 専用クライアント
│   ├── logger.py          # 構造化ログ（structlog）
│   ├── sentry_init.py     # エラー監視（Sentry SDK 初期化）
│   └── sentry_scrub_*.py  # PIIスクラブ（events / values / primitives）
├── tests/                  # テストスイート（全44 test files / 2026-08-25 実測）
│   ├── unit/              # ユニットテスト（38 files）
│   ├── integration/       # 統合テスト（4 files）
│   ├── performance/       # パフォーマンステスト（1 file）
│   ├── conftest.py        # pytest fixtures
│   └── test_smoke.py      # スモークテスト（1 file）
├── docs/                   # プロジェクトドキュメント
├── .github/                # CI/CD workflows
├── reports/                # テスト・カバレッジレポート
└── logs/                   # アプリケーションログ
```

---

## 🚀 Entry Points

### API Clients
- **JSONPlaceholder API Client**: `utils/jsonplaceholder_client_sync.py` / `utils/jsonplaceholder_client_async.py` - JSONPlaceholder API クライアント（同期/非同期）
- **GitHub API Client**: `utils/github_client.py` - GitHub API 専用クライアント

### Tests
- **Unit Tests**: `pytest tests/unit/` - ユニットテスト実行
- **Integration Tests**: `pytest tests/integration/` - 統合テスト実行
- **All Tests**: `pytest` - 全テスト実行

---

## 📦 Core Modules

### Module: config
- **Path**: `config/settings.py`
- **Exports**: `Settings`, `get_settings()`, `reload_settings()`
- **Purpose**: Pydantic Settingsによる型安全な環境変数管理。ネスト構造（`__`区切り）対応。

### Module: utils.jsonplaceholder_*（旧 api_client.py を責務別に分割）
- **Path**: `utils/jsonplaceholder_base_sync.py` / `utils/jsonplaceholder_base_async.py` / `utils/jsonplaceholder_client_sync.py` / `utils/jsonplaceholder_client_async.py`
- **Exports**: `SyncAPIClient` (同期), `AsyncAPIClient` (非同期), `SyncJSONPlaceholderClient`, `AsyncJSONPlaceholderClient`, `create_client()`。例外階層（`APIClientError`, `APIConnectionError`, `APITimeoutError`, `APIHTTPError`, `APIRetryError`, `APIJSONDecodeError`）は `utils.exceptions` から import
- **Purpose**: HTTP API クライアント。リトライ（`utils/retry.py`）・HTTP配管（`utils/http_helpers.py`）・レスポンス解析（`utils/response_parsing.py`）は共有ヘルパーモジュールへ分離済み。

### Module: utils.github_client
- **Path**: `utils/github_client.py`
- **Exports**: `AsyncGitHubClient` (非同期), `GitHubAPIError`, `RateLimitError`, `NotFoundError`, `GitHubServerError`, `validate_github_username`, `validate_github_repo`
- **Purpose**: GitHub API 専用の非同期クライアント。ETagキャッシュ・Rate Limit管理・PII保護対応。認証拡張可能設計（未認証: 60 req/h）。

### Module: utils.logger
- **Path**: `utils/logger.py`
- **Exports**: `get_logger()`
- **Purpose**: structlogベースの構造化ログ。ERROR以上をSentryに自動送信（opt-in）。

### Module: utils.sentry_init
- **Path**: `utils/sentry_init.py`
- **Exports**: `init_sentry()`, `is_sentry_initialized()`, `reset_sentry_state()`
- **Purpose**: Sentry SDK初期化。httpx統合。スクラブ処理は `utils/sentry_scrub_*.py` に委譲。

### Module: utils.sentry_scrub_*
- **Path**: `utils/sentry_scrub_events.py` / `utils/sentry_scrub_values.py` / `utils/sentry_scrub_primitives.py`
- **Purpose**: `before_send` フックによるPII保護。44種類の機密キーを自動スクラブ。
  依存は events → values → primitives の一方向。

### Module: models.responses
- **Path**: `models/responses.py`
- **Exports**: `Post`, `Comment`, `User`, `Geo`, `Address`,
               `Company`, `Todo`, `Album`, `Photo`
- **Purpose**: Pydantic モデルによるAPIレスポンス型定義・バリデーション。

---

## 🔧 Configuration

### Project Configuration
- **pyproject.toml**: Python プロジェクト設定（hatchling, dependencies, dev tools）
- **.mcp.json**: MCP サーバー設定（Serena, Context7, Sequential Thinking等）
- **.serena/project.yml**: Serena プロジェクト設定（言語: typescript, python）

### Quality Assurance
- **.pre-commit-config.yaml**: Pre-commit hooks（ruff, mypy, pytest, markdownlint等）
- **.markdownlint.json**: Markdown品質ルール（23ルール無効化＋日本語対応）
- **.gitleaks.toml**: シークレットスキャン設定

### CI/CD
- **.github/workflows/**: GitHub Actions workflows（CI, PR validation, weekly checks）
- **.github/dependabot.yml**: 依存関係自動更新設定
- **.github/renovate.json**: Renovate Bot 設定

### Environment Variables
- **.env** (not in repo): 環境変数設定（`API__BASE_URL`, `LOG__LEVEL`, `SENTRY__DSN`等）

---

## 📚 Documentation

### Core Documentation
- **README.md**: プロジェクト概要・セットアップ手順・開発ガイド
- **PROJECT_INDEX.md**: リポジトリ構成と主要ドキュメントの索引
- **REVIEW.md**: コードレビュー基準と重大度定義
- **CHANGELOG.md**: 変更履歴（Keep a Changelog / SemVer 準拠）
- **CONTEXT.md**: ドメイン用語定義（`docs/agents/domain.md` の consumer rules が参照。現状は「CD実証」1項目のみ）
- **CLAUDE.md**: Claude Code 向けプロジェクト指示書（開発ワークフロー、品質ゲート等）
- **AGENTS.md**: エージェント向けプロジェクト指示（実装前提・既存パターン優先方針）

### Development Guides
- **docs/DOCS_INDEX.md**: 公開ドキュメントの索引
- **docs/reference/ci_cd_pipeline.md**: CI/CD パイプライン リファレンス
- **docs/reference/docker.md**: Docker リファレンス
- **docs/agents/**: エージェント運用ドキュメント（issue-tracker, triage-labels, domain）

### Agent Configuration
- **.claude/agents/**: カスタムエージェント定義（7 files: silent-failure-hunter, security-code-reviewer等）
- **.claude/commands/**: カスタムコマンド定義（2 files: review-pr, code-review-excellence）

---

## 🧪 Test Coverage

### Test Statistics
- **Total Test Files**: 44（2026-08-25 実測）
- **Unit Tests**: 38 files (tests/unit/)
- **Integration Tests**: 4 files (tests/integration/)
- **Performance Tests**: 1 file (tests/performance/)
- **Smoke Tests**: 1 file (tests/test_smoke.py)

### Coverage Metrics
- **Coverage**: 97.64%（2026-08-25 実測 / `unit+integration` かつ `not external`）
- **Target Coverage**: 85%（`pyproject.toml` の `--cov-fail-under=85`）✅ 達成済み
- **Coverage Reports**: `reports/coverage.json`, `reports/htmlcov/`

### Test Execution
```bash
# 全テスト実行（カバレッジ計測は pyproject.toml の addopts で自動適用）
uv run pytest

# 並列実行（高速化）
uv run pytest -n auto

# 特定カテゴリのみ
uv run pytest tests/unit/        # ユニットテスト
uv run pytest tests/integration/ # 統合テスト
uv run pytest -m "not slow"      # 高速テストのみ
```

---

## 🔗 Key Dependencies

### Production
- **httpx** (>=0.27.0): 非同期HTTPクライアント
- **structlog** (>=26.1.0): 構造化ログ
- **pydantic** (>=2.0.0): データバリデーション
- **pydantic-settings** (>=2.0.0): 型安全な設定管理
- **sentry-sdk[httpx]** (>=2.61.1,<3.0.0): エラー監視（httpx統合）
- **psutil** (>=6.1.1): システムメトリクス
- **pyyaml** (>=6.0): YAML設定ファイル読み込み

### Development
- **pytest** (>=9.0.3): テストフレームワーク
- **pytest-asyncio** (>=1.1.0): 非同期テスト対応
- **pytest-cov** (>=4.1.0): カバレッジ測定
- **pytest-xdist** (>=3.5.0): 並列テスト実行
- **respx** (>=0.23.1): httpx用モックライブラリ
- **ruff** (>=0.15.12,<0.16): Linter + Formatter
- **mypy** (>=1.20.2): 型チェッカー

---

## 📝 Quick Start

### 1. Setup
```bash
# Python 3.14以上確認
uv run python --version

# 依存関係インストール（uv推奨）
uv sync

# 環境変数設定（.envファイル作成）
cp .env.example .env
# .envファイルを編集してAPI_KEY等を設定
```

### 2. Run
```bash
# APIクライアント使用例（対話モード）
uv run python
>>> from utils.jsonplaceholder_client_sync import SyncJSONPlaceholderClient
>>> with SyncJSONPlaceholderClient() as client:
...     todo = client.get_todo(1)
...     print(todo)
```

### 3. Test
```bash
# 全テスト実行（カバレッジ計測・下限・HTMLレポートは pyproject.toml の addopts で自動適用）
uv run pytest
open reports/htmlcov/index.html

# 品質ゲート（コミット前必須）
# コマンド本体は .claude/CLAUDE.md「品質ゲート」→「統合コマンド」を参照（複製しない）
```

### 4. Development Workflow
```bash
# 1. Issue作成
/create-issue

# 2. ブランチ作成（Git Flow + worktree）
/git:feature <task-name>

# 3. 実装 + 品質ゲート
# （コード変更後）.claude/CLAUDE.md「品質ゲート」→「統合コマンド」を実行

# 4. 自己改善
/reflexion:reflect

# 5. コミット（日本語PR対応）
/commit

# 6. PR作成
/commit-push-pr
```

---

## 🔍 Key Features

### 1. API クライアント設計パターン
- **同期/非同期の統一インターフェース**: `SyncAPIClient` / `AsyncAPIClient`
- **リトライロジック**: 指数バックオフ + 30%ジッター
- **エラーハンドリング階層**: 4xx即失敗、5xxリトライ
- **コネクションプール**: 最大10接続（設定可能）

### 2. エラー監視（Sentry統合）
- **自動エラー送信**: ERROR以上のログをSentryに送信
- **機密情報スクラブ**: 44種類のキー（API_KEY, PASSWORD等）自動除外
- **環境別制御**: `SENTRY__ENABLED=false` で開発時無効化

### 3. 設定管理ベストプラクティス
- **Pydantic Settings**: 型安全な環境変数バリデーション
- **ネスト記法**: `API__BASE_URL` → `settings.api.base_url`
- **SecretStr**: パスワード・API キーの平文出力防止

### 4. テスト戦略
- **Fixture スコープ最適化**: session/module/function の使い分け
- **ファクトリーパターン**: テストデータ生成の柔軟性
- **モック・スタブ活用**: 外部API依存の排除

### 5. Git Flow + Protected Branch
- **ブランチ戦略**: main (本番) / develop (統合) / feature/* (機能開発)
- **Conventional Commits**: `feat:`, `fix:`, `docs:`, `test:` 等
- **Squash Merge**: feature → develop (履歴クリーンアップ)
- **Regular Merge**: develop → main, hotfix → main/develop

---

## 📊 Project Metrics　(CI計測対象: unit + integration)

| Metric | Value | Target |
|--------|-------|--------|
| Test Coverage | 97.64%（2026-08-25 実測） | `pyproject.toml` の `--cov-fail-under=85` |
| CI Test Files (unit+integration) | 42（2026-08-25 実測） | - |
| Python Version | 3.14 | - |
| Code Quality | ruff + mypy | 0 errors |
| Documentation | CLAUDE.md + README | - |

---

## 🎯 Learning Goals

1. **非同期プログラミング**: `async/await`, `asyncio.gather()`
2. **エラーハンドリング戦略**: 階層的例外設計、リトライロジック
3. **テスト設計パターン**: pytest fixtures, ファクトリー, モック
4. **設定管理**: Pydantic Settings, 環境変数, SecretStr
5. **DevOps統合**: Docker Multi-stage builds, GitHub Actions CI/CD

---

**Index Size**: ~11KB (plain text)
**Token Efficiency**: ~81% reduction vs. full codebase read (58KB → 11KB)
**Maintenance**: Update after major architectural changes or weekly

---

*Generated by sc:index-repo v1.1*
*Note: JSON version (PROJECT_INDEX.json) not generated due to sandbox restrictions*
