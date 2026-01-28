# Project Index: api-test-devops-portfolio

**Generated:** 2026-01-28 14:35 JST
**Last Commit:** 1bf45d5 (2026-01-28 13:57:52 +0700)
**Version:** 0.1.0
**Python:** >=3.12

---

## 📁 Project Structure

```
api-test-devops-portfolio/
├── config/                 # 設定管理（Pydantic Settings）
│   ├── __init__.py
│   └── settings.py        # 型安全な環境変数管理
├── models/                 # データモデル定義
│   ├── __init__.py
│   └── responses.py       # APIレスポンスモデル
├── utils/                  # コアユーティリティ
│   ├── __init__.py
│   ├── api_client.py      # HTTP API クライアント（同期/非同期）
│   ├── github_client.py   # GitHub API 専用クライアント
│   ├── logger.py          # 構造化ログ（structlog）
│   └── sentry_init.py     # エラー監視（Sentry SDK）
├── tests/                  # テストスイート（19 test files）
│   ├── unit/              # ユニットテスト（14 files）
│   ├── integration/       # 統合テスト（3 files）
│   ├── performance/       # パフォーマンステスト（1 file）
│   ├── e2e/               # E2Eテスト（準備中）
│   ├── conftest.py        # pytest fixtures
│   └── test_smoke.py      # スモークテスト（1 file）
├── scripts/                # 自動化スクリプト
│   ├── error_tracker.py   # エラー追跡
│   ├── evaluate_4dimensions.py
│   ├── update_readme_metrics.py
│   └── week_improver.py
├── docs/                   # プロジェクトドキュメント
├── .github/                # CI/CD workflows
├── reports/                # テスト・カバレッジレポート
└── logs/                   # アプリケーションログ
```

---

## 🚀 Entry Points

### CLI / Scripts
- **Error Tracker**: `scripts/error_tracker.py` - エラー発生履歴の記録・分析
- **Metrics Updater**: `scripts/update_readme_metrics.py` - README.md メトリクス自動更新
- **4-Dimension Evaluator**: `scripts/evaluate_4dimensions.py` - 学習進捗4次元評価

### API Clients
- **Generic API Client**: `utils/api_client.py` - 汎用HTTP API クライアント
- **GitHub API Client**: `utils/github_client.py` - GitHub API 専用クライアント

### Tests
- **Unit Tests**: `pytest tests/unit/` - ユニットテスト実行
- **Integration Tests**: `pytest tests/integration/` - 統合テスト実行
- **All Tests**: `pytest` - 全テスト実行

---

## 📦 Core Modules

### Module: config
- **Path**: `config/settings.py`
- **Exports**: `Settings`, `settings` (singleton)
- **Purpose**: Pydantic Settingsによる型安全な環境変数管理。ネスト構造（`__`区切り）対応。

### Module: utils.api_client
- **Path**: `utils/api_client.py`
- **Exports**: `APIClient` (同期), `AsyncAPIClient` (非同期)
- **Purpose**: HTTP API クライアント。リトライロジック・エラーハンドリング・コネクションプール実装。

### Module: utils.github_client
- **Path**: `utils/github_client.py`
- **Exports**: `GitHubClient` (同期), `AsyncGitHubClient` (非同期)
- **Purpose**: GitHub API 専用クライアント。認証ヘッダー自動付与。

### Module: utils.logger
- **Path**: `utils/logger.py`
- **Exports**: `get_logger()`, `configure_logging()`
- **Purpose**: structlogベースの構造化ログ。ERROR以上をSentryに自動送信（opt-in）。

### Module: utils.sentry_init
- **Path**: `utils/sentry_init.py`
- **Exports**: `init_sentry()`
- **Purpose**: Sentry SDK初期化。29種類の機密キー自動スクラブ。httpx統合。

### Module: models.responses
- **Path**: `models/responses.py`
- **Exports**: `TodoResponse`, `PostResponse`, `UserResponse`
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
- **CLAUDE.md**: Claude Code 向けプロジェクト指示書（開発ワークフロー、品質ゲート等）

### Development Guides
- **docs/main/6週プラン/**: 6週間学習計画（Week 1-6詳細）
- **docs/progress/daily_progress.md**: 日次進捗記録
- **docs/main/interview/**: 面接準備資料

### Agent Configuration
- **.claude/agents/**: カスタムエージェント定義（7 files: silent-failure-hunter, security-code-reviewer等）
- **.claude/commands/**: カスタムコマンド定義（2 files: review-pr, code-review-excellence）

---

## 🧪 Test Coverage

### Test Statistics
- **Total Test Files**: 19
- **Unit Tests**: 14 files (tests/unit/)
- **Integration Tests**: 3 files (tests/integration/)
- **Performance Tests**: 1 file (tests/performance/)
- **Smoke Tests**: 1 file (tests/test_smoke.py)
- **E2E Tests**: 0 files (tests/e2e/ - prepared but empty)

### Coverage Metrics
- **Current Coverage**: 79.0%
- **Target Coverage**: 85% (Week 7-10 goal)
- **Coverage Reports**: `reports/coverage.json`, `reports/htmlcov/`

### Test Execution
```bash
# 全テスト実行（カバレッジ付き）
uv run pytest --cov=. --cov-report=term-missing

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
- **structlog** (>=23.1.0): 構造化ログ
- **pydantic** (>=2.0.0): データバリデーション
- **pydantic-settings** (>=2.0.0): 型安全な設定管理
- **sentry-sdk[httpx]** (>=2.48.0): エラー監視（httpx統合）
- **psutil** (>=6.1.1): システムメトリクス
- **pyyaml** (>=6.0): YAML設定ファイル読み込み

### Development
- **pytest** (>=8.0.0): テストフレームワーク
- **pytest-asyncio** (>=1.1.0): 非同期テスト対応
- **pytest-cov** (>=4.1.0): カバレッジ測定
- **pytest-xdist** (>=3.5.0): 並列テスト実行
- **respx** (>=0.22.0): httpx用モックライブラリ
- **ruff** (>=0.8.0): Linter + Formatter
- **mypy** (>=1.13.0): 型チェッカー

---

## 📝 Quick Start

### 1. Setup
```bash
# Python 3.12以上確認
python3.12 --version

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
>>> from utils.api_client import APIClient
>>> client = APIClient()
>>> response = client.get("/todos/1")
>>> print(response)
```

### 3. Test
```bash
# 全テスト実行
uv run pytest

# カバレッジ付き実行
uv run pytest --cov=. --cov-report=html
open reports/htmlcov/index.html

# 品質ゲート（4段階チェック）
uv run pytest --cov-fail-under=79 && \
uv run ruff check . && \
uv run mypy utils/ config/ models/ && \
git status
```

### 4. Development Workflow
```bash
# 1. Issue作成
/create-issue

# 2. ブランチ作成（Git Flow + worktree）
/feature <task-name>

# 3. 実装 + 品質ゲート
# （コード変更後）
uv run pytest && uv run ruff check . && uv run mypy utils/ config/ models/

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
- **同期/非同期の統一インターフェース**: `APIClient` / `AsyncAPIClient`
- **リトライロジック**: 指数バックオフ + 30%ジッター
- **エラーハンドリング階層**: 4xx即失敗、5xxリトライ
- **コネクションプール**: 最大10接続（設定可能）

### 2. エラー監視（Sentry統合）
- **自動エラー送信**: ERROR以上のログをSentryに送信
- **機密情報スクラブ**: 29種類のキー（API_KEY, PASSWORD等）自動除外
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

## 📊 Project Metrics

| Metric | Value | Target |
|--------|-------|--------|
| Test Coverage | 79.0% | 85% (Week 7-10) |
| Test Files | 19 | - |
| Python Version | 3.12+ | - |
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
