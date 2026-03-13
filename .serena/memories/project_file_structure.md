# プロジェクトディレクトリ構造ルール

*最終更新: 2025年12月27日*

## 目的

このドキュメントは、api-test-devops-portfolioプロジェクトのディレクトリ構造とファイル配置ルールを定義します。RULES.md「File Organization」カテゴリの具体化版として、プロジェクト固有の構造を明示します。

---

## プロジェクト全体構造

```
api-test-devops-portfolio/
├── .claude/                    # Claude Code設定（グローバルルール）
│   ├── commands/              # カスタムスラッシュコマンド
│   └── mcp_tools/             # MCPツール設定
│
├── .serena/                   # Serena MCP長期メモリ
│   └── memories/              # プロジェクト固有メモリ（13ファイル）
│       ├── ai_collaboration_workflow.md
│       ├── coding_standards.md
│       ├── command_usage_guide.md
│       ├── fixture_quick_reference.md
│       ├── implementation_quality_gates.md
│       ├── mcp_selection_guide.md
│       ├── project_architecture.md
│       ├── project_file_structure.md (このファイル)
│       ├── serena_memory_usage_guide.md
│       ├── test_strategy.md
│       ├── test_strategy_details.md
│       └── workflow_playbooks_guide.md
│
├── .taskmaster/               # Task Master AI設定
│   ├── tasks/                 # タスク管理JSON
│   └── docs/                  # タスク関連ドキュメント
│
#├── claudedocs/               # （未使用、オプショナル）
│
├── docs/                      # プロジェクトドキュメント
│   ├── progress/              # 学習・実装進捗記録
│   │   ├── daily_progress.md  # 日次進捗（Week単位）
│   │   ├── learning_state.yaml # 学習状態管理
│   │   └── weekly_understanding.md # 週次理解度記録
│   │
│   ├── learning/              # 学習関連ドキュメント
│   │   └── understanding_check/ # 理解度確認問題
│   │
│   ├── main/                  # メインドキュメント
│   │   └── 6週プラン/            # 6週学習・実装計画
│   │
│   ├── プロジェクト再編/        # プロジェクト計画・テンプレート
│   │
│   └── tools/                 # ツール関連ドキュメント
│
├── scripts/                   # 自動化スクリプト
│   ├── setup/                 # セットアップスクリプト
│   ├── test/                  # テスト補助スクリプト
│   └── deploy/                # デプロイスクリプト（Week 8以降）
│
├── tests/                     # テストファイル（全種類）
│   ├── conftest.py            # pytest共通設定・フィクスチャ（397行）
│   ├── unit/                  # 単体テスト（モック中心）
│   ├── integration/           # 統合テスト（実API）
│   ├── performance/           # パフォーマンステスト
│   ├── security/              # セキュリティテスト（マーカー未使用）
│   ├── e2e/                   # E2Eテスト（ブラウザ自動化）
│   ├── regression/            # リグレッションテスト
│   └── validation/            # バリデーションテスト
│
├── utils/                     # コアモジュール実装
│   ├── api_client.py          # APIクライアント（972行）
│   ├── logger.py              # structlog統合ロギング
│   └── __init__.py
│
├── config/                    # 設定管理
│   ├── settings.py            # Pydantic Settings（447行）
│   └── __init__.py
│
├── models/                    # データモデル
│   ├── responses.py           # APIレスポンスモデル（350行）
│   └── __init__.py
│
├── reports/                   # テスト・品質レポート（自動生成）
│   ├── htmlcov/               # カバレッジHTMLレポート
│   ├── pytest-report.html     # pytestレポート
│   └── ruff-report.txt        # ruffチェック結果
│
├── logs/                      # ログファイル（実行時自動生成）
│   ├── api_client.log
│   └── test_execution.log
│
├── .env                       # 環境変数（Git除外）
├── .gitignore                 # Git除外設定
├── pyproject.toml             # Pythonプロジェクト設定
├── uv.lock                    # 依存関係ロックファイル
├── README.md                  # プロジェクトREADME
├── CLAUDE.md                  # Claude Code向けプロジェクト説明
└── docker-compose.yml         # Docker環境設定（Week 7実装）
```

---

## ファイル配置原則

### 1. テストファイル（`tests/`）

**原則**: ソースファイルと同じディレクトリに配置しない

✅ **Good**:
```
tests/
├── unit/
│   ├── test_api_client.py
│   └── test_settings.py
├── integration/
│   └── test_api_integration.py
```

❌ **Bad**:
```
utils/
├── api_client.py
├── test_api_client.py  # ソースファイル横に配置（非推奨）
```

**理由**:
- テストとソースの分離（単一責任原則）
- パッケージングからテスト除外が容易
- CI/CDでのテストディレクトリ指定が明確

---

### 2. スクリプト（`scripts/`）

**原則**: プロジェクトルートに散らばらせない

✅ **Good**:
```
scripts/
├── setup/
│   └── install_dependencies.sh
├── test/
│   └── run_coverage.sh
```

❌ **Bad**:
```
api-test-devops-portfolio/
├── debug.sh              # ルート直下（非推奨）
├── temp_script.py        # 一時スクリプト（非推奨）
```

**理由**:
- ワークスペースの清潔性維持
- スクリプトの用途別整理
- `.gitignore`での一括除外が容易

---

### 3. Claude Code固有ドキュメント（`claudedocs/`）

**原則**: プロジェクト一般ドキュメント（`docs/`）と分離

✅ **Good**:
```
claudedocs/
├── analysis.md           # Claude生成のコード分析
├── architecture_review.md # アーキテクチャレビュー
```

❌ **Bad**:
```
docs/
├── claude_analysis.md    # 一般ドキュメントと混在（非推奨）
```

**理由**:
- Claude Code固有の成果物を明確に分離
- プロジェクト一般ドキュメントとの混同防止
- `.gitignore`での選択的除外が可能

---

### 4. 一時ファイル・自動生成ファイル

**原則**: `.gitignore`で除外、セッション終了時に削除

✅ **Good**:
```
.gitignore:
reports/
logs/
*.log
temp_*
debug_*
```

❌ **Bad**:
```
# 一時ファイルを git add してコミット
git add debug.sh temp_analysis.md
```

**理由**:
- バージョン管理の汚染防止
- Workspace Hygiene（RULES.md）の遵守
- CI/CDでのビルドクリーン性確保

---

## ディレクトリ別の役割定義

| ディレクトリ | 役割 | Git管理 | 作成タイミング | 例 |
|------------|------|---------|-------------|-----|
| `.claude/` | Claude Code設定 | ✅ | プロジェクト初期 | commands/, mcp_tools/ |
| `.serena/` | Serena長期メモリ | ✅ | Serena初回使用時 | memories/*.md |
| `.taskmaster/` | Task Master管理 | ✅ | Task Master初回使用時 | tasks/tasks.json |
| `claudedocs/` | Claude固有ドキュメント | ⚠️ | （未使用） | オプショナル |
| `docs/` | プロジェクトドキュメント | ✅ | プロジェクト初期 | progress/, learning/ |
| `scripts/` | 自動化スクリプト | ✅ | 必要時 | setup/, test/, deploy/ |
| `tests/` | テストファイル | ✅ | Week 1~ | unit/, integration/ |
| `utils/` | コアモジュール | ✅ | Week 1~ | api_client.py |
| `config/` | 設定管理 | ✅ | Week 5~ | settings.py |
| `models/` | データモデル | ✅ | Week 5~ | responses.py |
| `reports/` | テスト・品質レポート | ❌ | テスト実行時 | htmlcov/, pytest-report.html |
| `logs/` | ログファイル | ❌ | 実行時 | api_client.log |

**Git管理凡例**:
- ✅: バージョン管理対象
- ❌: `.gitignore`で除外
- ⚠️: 選択的に管理（プロジェクト方針による）

---

## ファイル命名規則

### Python実装ファイル

```python
# ✅ Good
utils/api_client.py         # snake_case、機能を表す名前
config/settings.py          # snake_case、単数形
models/responses.py         # snake_case、複数形（モデル集）

# ❌ Bad
utils/APIClient.py          # PascalCase（ファイル名はsnake_case）
config/Config.py            # PascalCase
models/response.py          # 単数形（複数モデルを含む場合は複数形推奨）
```

### テストファイル

```python
# ✅ Good
tests/unit/test_api_client.py       # test_プレフィックス必須
tests/integration/test_api_integration.py

# ❌ Bad
tests/unit/api_client_test.py       # サフィックスは非推奨
tests/unit/test_APIClient.py        # PascalCase（snake_case推奨）
```

### ドキュメントファイル

```markdown
# ✅ Good
docs/progress/daily_progress.md     # snake_case、英語推奨
docs/learning/understanding_check/

# ⚠️ 許容（日本語ディレクトリ）
docs/プロジェクト再編/               # 既存の日本語ディレクトリは維持
docs/learning/understanding_check/day1_httpx_check.md

# ❌ Bad
docs/dailyProgress.md                # camelCase（非推奨）
docs/DailyProgress.md                # PascalCase（非推奨）
```

---

## 品質チェック除外設定

### pre-commit除外（`.pre-commit-config.yaml`）

```yaml
exclude: |
  (?x)^(
    tests/Q&A/.*|              # 学習用Q&Aファイル除外
    scripts/temp_.*|           # 一時スクリプト除外
    .*_backup\..*|             # バックアップファイル除外
    reports/.*|                # レポートファイル除外
    logs/.*                    # ログファイル除外
  )$
```

### pytest除外（`pytest.ini`）

```ini
[pytest]
testpaths = tests
norecursedirs = tests/Q&A __pycache__ .git
```

---

## ワークスペースクリーンアップチェックリスト

セッション終了時・git commit前に以下を確認:

- [ ] 一時ファイル削除（`temp_*`, `debug_*`）
- [ ] 一時スクリプト削除（ルート直下の`.sh`, `.py`）
- [ ] ログファイル確認（`logs/`が肥大化していないか）
- [ ] レポートファイル削除（`reports/`は自動生成のため削除OK）
- [ ] Untracked files確認（`git status`）

**クリーンアップコマンド**:
```bash
# 一時ファイル検索
find . -name "temp_*" -o -name "debug_*" -o -name "*.log"

# 一時ファイル削除（要確認）
find . -name "temp_*" -delete
find . -name "debug_*" -delete
```

---

## プロジェクト構造の進化

### Week 1-5.5: 学習・実装期（6週プラン）
```
- utils/ (APIクライアント, structlogロガー)
- config/ (設定管理, Pydantic Settings)
- models/ (レスポンスモデル)
- tests/ (単体・統合・性能テスト)
- docker-compose.yml (4環境: dev/test/demo/prod)
- .github/workflows/ (CI/CD自動化)
```

### Week 6: 案件応募準備期
```
+ README.md強化           # バッジ、使用例追加
+ docs/portfolio/         # ポートフォリオ資料
+ スキル証明ドキュメント
```

---

## コアモジュール構成

### APIクライアント実装（`utils/api_client.py`）

```
utils/api_client.py          # APIクライアント実装（972行）
├── BaseAPIClient            # 同期HTTPクライアント（リトライロジック付き）
├── JSONPlaceholderClient    # JSONPlaceholder API専用クライアント
├── AsyncAPIClient           # 非同期HTTPクライアント（async/await）
└── AsyncJSONPlaceholderClient  # 非同期専用クライアント（並行処理対応）
```

**行数**: 972行（2025-12-26時点）

### 設定管理（`config/settings.py`）

```
config/settings.py           # 設定管理（447行）
├── Settings                 # Pydantic Settings統合管理
├── APIConfig                # API設定（タイムアウト、リトライ等）
├── LogConfig                # ログ設定（structlog対応）
├── TestConfig               # テスト設定
└── SecurityConfig           # セキュリティ設定（SecretStr対応）
```

**行数**: 447行（2025-12-26時点）

---

## 設計パターンの重要ポイント

### エラーハンドリング階層

```python
# utils/api_client.py:24-57
APIClientError              # 基底例外クラス
├── APIConnectionError      # 接続エラー（ネットワーク障害等）
├── APITimeoutError         # タイムアウトエラー
├── APIHTTPError            # HTTPステータスエラー（4xx/5xx分離）
└── APIRetryError           # リトライ上限エラー
```

**設計意図**:
- 階層的な例外設計により、エラーハンドリングの粒度を調整可能
- 4xx（クライアントエラー）と5xx（サーバーエラー）を分離してリトライロジックを最適化

### リトライロジック

**実装方針**（`utils/api_client.py:132-219`）:
- **4xxエラー**: 即座に失敗（クライアントエラー、リトライ不要）
- **5xxエラー**: リトライ対象（サーバーエラー、一時的障害の可能性）
- **設定可能パラメータ**: リトライ回数・間隔（`config/settings.py`のAPIConfig）

**コード参照**: `utils/api_client.py:132-219`（リトライロジック実装）

### 非同期処理パターン

**使用技術**:
- `AsyncAPIClient`: async/awaitパターン（`utils/api_client.py:399-762`）
- `httpx.AsyncClient`: 非同期HTTPクライアント
- `asyncio.gather()`: 並行処理（例: `AsyncJSONPlaceholderClient.get_user_data()`で複数API呼び出しを並行実行）

**実装例**: `utils/api_client.py:741-761`（並行処理実装）

---

## テスト構成詳細

### pytest共通設定・フィクスチャ（`tests/conftest.py`）

```
tests/conftest.py            # pytest共通設定・フィクスチャ
├── async_client             # 非同期クライアントフィクスチャ（async/await対応）
├── mock_httpx_client        # モック化HTTPXクライアント（単体テスト用）
├── todo_data_factory        # テストデータファクトリー（Todoモデル）
├── user_data_factory        # ユーザーデータファクトリー（Userモデル）
├── performance_timer        # パフォーマンス計測タイマー
└── security_payloads        # セキュリティテスト用ペイロード（SQL injection等）
```

**詳細**: CLAUDE.md「テスト構成」参照

### テストディレクトリ階層

```
tests/
├── conftest.py              # pytest共通設定・フィクスチャ
├── unit/                    # 単体テスト（モック中心、外部API呼び出しなし）
├── integration/             # 統合テスト（実API呼び出し、TEST_EXTERNAL_API_ENABLED制御）
├── performance/             # パフォーマンステスト（応答時間、スループット測定）
├── security/                # セキュリティテスト（OWASP Top 10対応）
└── Q&A/                     # 学習用Q&A（品質チェック除外対象）
```

**テストマーカー運用**:
- `@pytest.mark.unit`: 単体テスト（モック中心）
- `@pytest.mark.integration`: 統合テスト（実API）
- `@pytest.mark.performance`: パフォーマンステスト
- `@pytest.mark.e2e`: E2Eテスト
- `@pytest.mark.slow`: 低速テスト
- `@pytest.mark.external`: 外部API依存テスト
- `@pytest.mark.smoke`: スモークテスト（PR用）
- ~~`@pytest.mark.security`~~: 削除済み（2025-12-25）

> **Note**: security/ディレクトリは存在するが、マーカーは未使用

**並列実行**:
```bash
uv run pytest -n auto  # pytest-xdistによる並列実行（高速化）
```

---

## 参考リソース

- **RULES.md**: ~/.claude/RULES.md「File Organization」セクション
- **coding_standards**: .serena/memories/coding_standards.md「9. 自動検証コマンド」
- **project_architecture**: .serena/memories/project_architecture.md
- **CLAUDE.md**: アーキテクチャ概要（設計パターン・テスト構成の詳細）

---

## 変更履歴

| 日付 | 変更内容 | 理由 |
|------|---------|------|
| 2025-11-14 | 初版作成 | RULES.md「File Organization」の具体化 |
| 2025-11-15 | 設計パターン・テスト構成追加 | CLAUDE.mdアーキテクチャ概要を統合（Task 2完了） |
| 2025-12-27 | 大規模更新 | 6週プラン移行、tests/構造更新、行数更新、メモリリスト更新 |
