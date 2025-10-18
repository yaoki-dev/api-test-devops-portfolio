# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

*最終更新: 2025年10月01日*

## プロジェクト概要

APIテスト + DevOps統合学習ポートフォリオ。時給6000-8000円レベルの技術力を証明するために設計されています。

**技術スタック**: Python 3.10+, httpx, pytest, pydantic-settings, structlog

## 開発環境セットアップ

```bash
# 依存関係のインストール
uv sync

# pre-commitフックのインストール（ruff自動フォーマット・修正）
uv run pre-commit install
```

## テスト実行コマンド

### 基本テスト実行
```bash
# 全テスト実行（カバレッジ85%以上必須）
uv run pytest

# マーカー別実行
uv run pytest -m unit           # 単体テストのみ
uv run pytest -m integration    # 統合テストのみ
uv run pytest -m performance    # パフォーマンステストのみ
uv run pytest -m security       # セキュリティテストのみ

# 並列テスト実行（高速化）
uv run pytest -n auto

# カバレッジレポート生成
uv run pytest --cov-report=html  # reports/htmlcov/index.html
```

### 個別テスト実行
```bash
# 特定ファイル
uv run pytest tests/unit/test_async_client.py -v

# 特定テスト関数
uv run pytest tests/unit/test_async_client.py::test_async_get_user -v

# キーワード検索
uv run pytest -k "async" --asyncio-mode=auto
```

## コード品質管理

### リンター・フォーマッター
```bash
# ruff チェック（自動修正付き）
uv run ruff check --fix .

# ruff フォーマット
uv run ruff format .

# mypy 型チェック
uv run mypy utils/ config/

# bandit セキュリティスキャン
uv run bandit -r utils/ config/

# safety 脆弱性チェック
uv run safety check
```

### pre-commit（軽量版）
コミット時に自動実行（ruffのみ、3秒以内）:
- `ruff --fix`: 自動修正
- `ruff-format`: 自動フォーマット

重いチェック（mypy, bandit, pytest）はCI/CDで実行

## アーキテクチャ概要

### コアモジュール構成

```
utils/api_client.py          # APIクライアント実装
├── BaseAPIClient            # 同期HTTPクライアント（リトライロジック付き）
├── JSONPlaceholderClient    # JSONPlaceholder API専用クライアント
├── AsyncAPIClient           # 非同期HTTPクライアント（async/await）
└── AsyncJSONPlaceholderClient  # 非同期専用クライアント（並行処理対応）

config/settings.py           # 設定管理
├── Settings                 # Pydantic Settings統合管理
├── APIConfig                # API設定（タイムアウト、リトライ等）
├── LogConfig                # ログ設定（structlog対応）
├── TestConfig               # テスト設定
└── SecurityConfig           # セキュリティ設定（SecretStr対応）
```

### 設計パターンの重要ポイント

**エラーハンドリング階層**:
- `APIClientError`: 基底例外クラス
- `APIConnectionError`: 接続エラー
- `APITimeoutError`: タイムアウト
- `APIHTTPError`: HTTPステータスエラー（4xx/5xx分離）
- `APIRetryError`: リトライ上限エラー

**リトライロジック**:
- 4xxエラーは即座に失敗（クライアントエラー）
- 5xxエラーはリトライ対象（サーバーエラー）
- 設定可能なリトライ回数・間隔（`config/settings.py`）

**非同期処理**:
- `AsyncAPIClient`: async/awaitパターン
- `httpx.AsyncClient`: 非同期HTTPクライアント
- `asyncio.gather()`: 並行処理（例: `AsyncJSONPlaceholderClient.get_user_data()`）

### テスト構成

```
tests/conftest.py            # pytest共通設定・フィクスチャ
├── async_client             # 非同期クライアントフィクスチャ
├── mock_httpx_client        # モック化HTTPXクライアント
├── todo_data_factory        # テストデータファクトリー
├── user_data_factory        # ユーザーデータファクトリー
├── performance_timer        # パフォーマンス計測タイマー
└── security_payloads        # セキュリティテスト用ペイロード

tests/unit/                  # 単体テスト（モック中心）
tests/integration/           # 統合テスト（実API呼び出し）
tests/performance/           # パフォーマンステスト
tests/security/              # セキュリティテスト
```

## 設定管理

### 環境変数設定（`.env`）

Pydantic Settingsのネスト記法（`__`区切り）を使用:

```bash
# 環境設定
ENVIRONMENT=development      # development|testing|staging|production
DEBUG=true

# API設定
API__BASE_URL=https://jsonplaceholder.typicode.com
API__TIMEOUT=30
API__RETRY_COUNT=3
API__RETRY_DELAY=1.0
API__MAX_CONNECTIONS=10

# ログ設定
LOG__LEVEL=DEBUG            # DEBUG|INFO|WARNING|ERROR|CRITICAL
LOG__FORMAT=console         # console|json
LOG__FILE=/var/log/app/api-test.log

# テスト設定
TEST__EXTERNAL_API_ENABLED=true
TEST__PERFORMANCE_TEST_ENABLED=false

# セキュリティ設定
SECURITY__API_KEY=your-secret-key
SECURITY__RATE_LIMIT_REQUESTS=100
```

### 設定アクセス方法

```python
from config.settings import settings

# API設定
base_url = settings.api.base_url
timeout = settings.api.timeout

# 環境判定
if settings.is_development():
    # 開発環境固有の処理
    pass
```

## 重要な学習ポイント

### 1. 非同期プログラミング
- `async/await`パターンの実装（`utils/api_client.py:399-762`）
- `asyncio.gather()`による並行処理（`api_client.py:741-761`）
- 非同期コンテキストマネージャー（`__aenter__/__aexit__`）

### 2. エラーハンドリング戦略
- 階層的な例外設計（`api_client.py:24-57`）
- HTTPステータスコード別処理（4xx即失敗、5xxリトライ）
- リトライロジック実装（`api_client.py:132-219`）

### 3. テスト設計パターン
- pytest fixtureスコープの使い分け（session/module/function）
- ファクトリーパターンによるテストデータ生成（`conftest.py:172-238`）
- モック・スタブの活用（`conftest.py:123-164`）
- パフォーマンステスト（`conftest.py:246-274`）

### 4. 設定管理ベストプラクティス
- Pydantic Settingsによる型安全な設定（`config/settings.py`）
- 環境変数の自動読み込み・バリデーション
- `SecretStr`によるシークレット保護（`settings.py:142-155`）

## 開発時の注意事項

### コーディング規約
- Python: PEP 8準拠、型ヒント必須
- 命名規則: snake_case
- docstring: すべての公開関数・クラスに必須
- コメント: 日本語可、ただしコード内変数・関数名は英語

### Git運用
- featureブランチで作業、mainへの直接コミット禁止
- コミットメッセージ: prefix使用（feat:, fix:, docs:, test:, refactor:）

### テストカバレッジ
- 目標: 85%以上（pytest設定: `--cov-fail-under=85`）
- テスト不足時はpytestが自動的に失敗

### ファイル除外設定
- `tests/Q&A/`: 学習用ファイル（pre-commit・品質チェック除外）
- `node_modules/`, `venv/`, `__pycache__/`: 自動生成ファイル

## トラブルシューティング

### テスト失敗時
```bash
# 詳細ログ出力
uv run pytest -vv --tb=long

# 最初の失敗で停止
uv run pytest -x

# 特定テストのみデバッグ実行
uv run pytest tests/unit/test_async_client.py::test_name -vv --log-cli-level=DEBUG
```

### カバレッジ不足時
```bash
# カバレッジレポート確認
uv run pytest --cov-report=term-missing

# HTMLレポート生成
uv run pytest --cov-report=html
open reports/htmlcov/index.html
```

### 型チェックエラー時
```bash
# mypy詳細出力
uv run mypy --show-error-codes --pretty utils/ config/
```
