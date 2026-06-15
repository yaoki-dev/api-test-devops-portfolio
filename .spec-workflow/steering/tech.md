# Technology Steering Document

*最終更新: 2026年03月08日*

## 技術スタック概要

Python 3.14ベースのAPIテスト + DevOps統合プロジェクト。同期/非同期HTTPクライアント、型安全な設定管理、包括的テストスイートを特徴とする。

---

## コア技術スタック

### プログラミング言語
- **Python**: 3.14（実装環境）
  - CI/CDでは3.14固定（pyproject.toml: `requires-python = "==3.14.*"`）
  - 型ヒント必須（mypy strict mode）
  - PEP 8準拠

### HTTP通信
- **httpx**: 0.27.0+
  - 同期/非同期対応
  - リトライロジック（4xx即失敗、5xxリトライ）
  - タイムアウト設定可能
  - コンテキストマネージャー対応

### 設定管理
- **Pydantic**: 2.0+
  - 型安全なデータバリデーション
  - **Pydantic Settings**: 環境変数自動読み込み
    - ネスト記法: API__BASE_URL, LOG__LEVEL（__区切り）
    - SecretStrによるシークレット保護
  - 設定クラス: APIConfig, LogConfig, TestConfig, SecurityConfig

### ログ
- **structlog**: 26.1.0+
  - 構造化ログ（JSON/Console切替可能）
  - ログレベル: DEBUG, INFO, WARNING, ERROR, CRITICAL
  - ログファイル出力対応

---

## テスト・品質管理ツール

### テストフレームワーク
- **pytest**: 8.0.0+
  - **pytest-asyncio**: 非同期テスト対応（asyncio_mode = "auto"）
  - **pytest-cov**: カバレッジ計測（閾値85%）
  - **pytest-xdist**: 並列テスト実行（CPU数自動検出、約60%時間削減）
    - 測定条件: 575テスト、8コアCPU
    - シリアル: ~10分 → 並列: ~4分
    - `uv run pytest -n auto`: 全テスト並列実行
    - `uv run pytest --collect-only`: テスト件数確認
    - `uv run pytest -n auto -m "not external and not manual"`: ローカル開発用
  - **pytest-mock**: モック機能
  - **pytest-benchmark**: パフォーマンスベンチマーク

### テストマーカー（6種類）
- smoke: スモークテスト（main PR用、基本機能の動作確認）
- unit: 単体テスト
- integration: 統合テスト
- external: 外部API依存テスト
- slow: 実行時間の長いテスト
- performance: パフォーマンステスト

### コード品質ツール
- **ruff**: 統合リンター・フォーマッター
  - black, isort, flake8, pyupgradeを統合
  - --fix: 自動修正
  - line-length: 100
  - ルール: E, W, F, I, C90, N, UP, B, S, PTH

- **mypy**: 型チェッカー
  - strict mode（disallow_untyped_defs, warn_return_any等）
  - Python 3.14対応

- **bandit**: セキュリティスキャン
  - 脆弱性検出（SQL injection, XSS等）
  - 除外: tests/（B101: assert使用許可）

- **safety**: 依存関係脆弱性チェック

### pre-commit（軽量版）
コミット時自動実行（3秒以内）:
- ruff --fix: 自動修正
- ruff-format: 自動フォーマット

重いチェック（mypy, bandit, pytest）はCI/CDで実行

---

## DevOps技術スタック

### コンテナ化（Week 3実装予定）
- **Docker**:
  - **Multi-stage builds**: 4ステージ（base, dependencies, development, production）
  - **.dockerignore**: ビルドコンテキスト最適化
  - Layer caching戦略

- **docker compose**: 4環境構築
  - dev: 開発環境（ホットリロード、デバッグツール）
  - test: テスト環境（pytest実行、カバレッジ計測）
  - demo: デモ環境（本番相当、外部公開用）
  - prod: 本番環境（最小イメージ、セキュリティ強化）

### CI/CD（実装済み）
- **GitHub Actions**:
  - マトリクス戦略: Python 3.14（単一バージョン）
  - ジョブ構成:
    - Lint: ruff, mypy
    - Test: pytest（カバレッジ85%）
    - Security: bandit, safety
    - Build: Docker image build
  - アーティファクト: カバレッジレポート、テストレポート

### パッケージ管理
- **uv**: 高速Pythonパッケージマネージャー
  - uv sync: 依存関係インストール
  - uv run: コマンド実行
  - uv.lock: ロックファイル

---

## サードパーティサービス・API

### 外部API
- **JSONPlaceholder API**: テスト用REST API
  - エンドポイント: https://jsonplaceholder.typicode.com
  - リソース: users, posts, todos, comments
  - 認証: 不要（公開API）

### CI/CD連携（実装済み）
- **GitHub Actions**: CI/CDパイプライン（`.github/workflows/ci.yml`）
- **GitHub Container Registry**: Dockerイメージホスティング候補

---

## 技術制約・要件

### パフォーマンス要件
- **APIレスポンス**: 30秒タイムアウト（設定可能）
- **リトライロジック**:
  - リトライ回数: 3回（デフォルト）
  - リトライ間隔: 1.0秒（指数バックオフ候補）
- **並列テスト**: pytest -n auto（CPU自動検出）

### セキュリティ要件
- **シークレット管理**:
  - .envファイル（git除外）
  - SecretStr型でパスワード保護
  - 環境変数: SECURITY__API_KEY
- **脆弱性スキャン**:
  - bandit（コード静的解析）
  - safety（依存関係脆弱性）
- **インジェクション対策**: 入力検証（Pydantic）

### スケーラビリティ
- **非同期処理**: AsyncAPIClientによる並行リクエスト
- **コネクション管理**: httpx.AsyncClient（最大接続数10、設定可能）
- **Docker水平スケーリング**: docker compose scale対応（Week 3実装予定）

---

## 技術的意思決定記録（ADR）

### ADR-001: httpxを選択（2025-10-01）
**決定**: httpxをHTTPクライアントとして採用

**理由**:
- 同期/非同期API統一（requests互換 + async/await対応）
- HTTP/2サポート
- タイムアウト・リトライロジック標準装備
- モダンなPython型ヒント対応

**代替案**:
- requests: 非同期非対応
- aiohttp: 同期API非対応

---

### ADR-002: Pydantic Settingsを設定管理に採用（2025-10-01）
**決定**: Pydantic Settingsで環境変数管理

**理由**:
- 型安全なバリデーション
- 環境変数自動読み込み（.env対応）
- ネスト記法で階層的設定管理（API__BASE_URL）
- SecretStrでシークレット保護

**代替案**:
- python-decouple: 型安全性低い
- dynaconf: 学習コスト高い

---

### ADR-003: ruffを統合リンターとして採用（2025-10-01）
**決定**: ruff（black, isort, flake8統合）を採用

**理由**:
- 実行速度: black比10-100倍高速
- オールインワン: フォーマッター + リンター統合
- 自動修正: --fixで一発修正
- pre-commitで軽量化（3秒以内）

**代替案**:
- black + isort + flake8: 設定分散、実行遅い

---

### ADR-004: Docker Multi-stage buildsを採用（Week 3実装予定）
**決定**: 4ステージDockerfile（base → dependencies → development → production）

**理由**:
- イメージサイズ最適化（本番環境で開発ツール除外）
- Layer caching効率化
- 環境別ビルド（dev/test/demo/prod）

**制約**:
- ビルド時間増加（初回のみ、キャッシュ活用で軽減）

---

## 技術負債・今後の改善候補

### 6週プラン内で解消予定
- Docker 4環境実装（Week 3）
- GitHub Actions CI/CD自動化（実装済み）
- カバレッジ85%達成（現在93.43%、目標達成済み）
- セキュリティスキャン自動化（実装済み）
- pytest.ini廃止・pyproject.toml一元管理（次回タスク）

### Week 6以降で検討
- Kubernetes移行（オーケストレーション）
- Terraform導入（Infrastructure as Code）
- 負荷テスト高度化（Locust/K6）
- OpenAPI 3.0仕様書自動生成

---

## 開発環境セットアップ

### 必須ツール
- Python 3.14
- uv（パッケージマネージャー）
- Docker Desktop（Week 3以降）
- Git

### セットアップコマンド
```bash
# 依存関係インストール
uv sync

# pre-commitフック設定
uv run pre-commit install

# テスト実行
uv run pytest

# 品質チェック
uv run ruff check --fix .
uv run mypy utils/ config/ models/
uv run bandit -r utils/ config/
```

### 推奨エディタ設定
- VSCode拡張: Python, Pylance, Ruff
- mypy統合: python.linting.mypyEnabled = true
- ruff自動修正: editor.formatOnSave = true

---

## バージョン管理・ブランチ戦略

### Git Flow採用（2025-12-04決定）

**ブランチ構成**:
| ブランチ | 用途 | マージ先 |
|---------|------|---------|
| `main` | 本番リリース（タグ付き） | - |
| `develop` | 開発統合 | main |
| `feature/*` | 新機能開発 | develop |
| `release/*` | リリース準備 | main + develop |
| `hotfix/*` | 緊急修正 | main + develop |

**採用理由**:
- ポートフォリオでのGit Flow実践経験アピール
- 将来のチーム開発への準備
- CI/CD（.github/workflows/ci.yml）が既にdevelop対応済み

**コマンド**:
- `/git:feature <name>`: feature作成（developから分岐）
- `/release <version>`: release作成
- `/git:hotfix <name>`: hotfix作成（mainから分岐）
- `/flow-status`: 状態確認
- `/clean-gone` : [gone]ブランチクリーンアップ
- ブランチ完了: `/finishing-a-development-branch`
