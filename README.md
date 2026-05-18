# API Test + DevOps Portfolio

*最終更新: 2026年03月22日*

## 概要

このプロジェクトは、APIテストとDevOps技術を統合した実践的なポートフォリオです。

[![CI/CD Pipeline](https://github.com/yuta158/api-test-portfolio/actions/workflows/ci.yml/badge.svg)](https://github.com/yuta158/api-test-portfolio/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-93.43%25-brightgreen)](https://yuta158.github.io/api-test-portfolio/htmlcov/)
![Python](https://img.shields.io/badge/Python-3.14-blue)
[![Docker](https://img.shields.io/badge/docker-multi--stage-blue)](./Dockerfile)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](https://mypy-lang.org/)
[![Security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
[![Dependencies: safety](https://img.shields.io/badge/dependencies-safety--checked-green.svg)](https://safetycli.com/)

> **Python/Docker/CI/CDを統合したAPIテスト自動化ポートフォリオ。588件のテスト（CI品質ゲート: 575件/93.43%）。**

## 概要

- **588件のテストスイート**: Unit(549, うちSlow 1件含む) / Integration(31, うちExternal 5件含む) / Performance(5, 週次のみ) / Smoke(3) / E2E(実装予定)
- **カバレッジ: 93.43%**（unit+integration条件）: 継続的な品質向上
- **CI実行テスト: 575件**（unit+integration条件, external・performance・smoke除外）
  - 内訳: Unit 549件 + Integration 26件（31件のうちexternal 5件を除外）
- **CI/CD自動化**: GitHub Actions による多段階パイプライン
- **セキュリティ**: CI/CD品質ゲート（pytest + ruff + mypy + Trivy）
- **GitHub API統合**: 実務的なAPI統合スキルを証明（Rate Limit管理、ETag活用、非同期処理）

## デモ

> 3つのGIFで主要機能を視覚的に確認できます（合計35秒）

### 1. テスト実行

![Test Demo - pytest実行で基本テスト19件合格（全588件中の抽出実行、CI環境での全体カバレッジ: 93.43%）。テスト自動化スキルを実証](assets/demo-test.gif)

> **📝 デモ内容**: クイック実行例（基本テスト19件、デモ時間短縮のため抽出。全588件は約60秒）
> **🔍 全588件を今すぐ確認**: [GitHub Actions CI/CD](https://github.com/yuta158/api-test-portfolio/actions) でフルテスト結果＋カバレッジレポートを閲覧

**何がわかるか**:

- pytest + pytest-covによる自動テスト実行
- カバレッジレポートによる品質可視化
- テスト実行: 基本19件 ~5秒、全588件 ~60秒

<details>
<summary>全テスト実行コマンド（588件、約60秒）</summary>

```bash
# 全テスト実行（588件）
uv run pytest --cov=utils --cov=config --cov=models --cov-report=term -q --color=yes

# クイック実行（unit tests）
uv run pytest tests/unit/test_api_client.py --cov=utils --cov=config --cov=models --cov-report=term -q --color=yes
```

</details>

### 2. Docker操作

![Docker Demo - 4-stage Multi-stage buildでコンテナビルド。DevOpsスキルを実証](assets/demo-docker.gif)

> **📝 デモ内容**: Docker Multi-stage buildによるコンテナビルド
> **⏳ Week3対応予定**: docker-compose.yamlによる4環境（dev/test/demo/prod）オーケストレーション

**何がわかるか**:

- Docker Multi-stage builds（4段階: base/dependencies/runtime/test）
- 非rootユーザーでのセキュアな実行
- 本番イメージサイズ最適化（< 200MB目標）

### 3. CI/CD自動化

![CI/CD Demo - git pushでGitHub Actions自動起動、多段階パイプラインで品質保証。CI/CDスキルを実証](assets/demo-cicd.gif)

> **📝 デモ内容**: git push後GitHub Actionsで自動テスト・デプロイ

**何がわかるか**:

- GitHub Actionsによる自動化パイプライン
- コード変更時の自動テスト実行
- 多段階パイプライン（[CI/CD 多段階パイプライン](#cicd-多段階パイプライン)参照）

## 技術スタック

| カテゴリ | 技術 |
|---------|-----|
| **言語** | Python 3.14 |
| **HTTP Client** | httpx（同期/非同期対応） |
| **設定管理** | Pydantic Settings（型安全） |
| **テスト** | pytest + pytest-cov + pytest-asyncio |
| **リンター** | ruff（高速、Rust製） |
| **型チェック** | mypy（strict mode） |
| **パッケージ管理** | uv（高速、Rust製） |
| **CI/CD** | GitHub Actions（多段階パイプライン） |
| **エラー監視** | Sentry SDK + MCP統合 |
| **ログ** | structlog（構造化ログ） |

## ブランチ戦略（軽量Git Flow）

```
main ─────────────────────────────────────────→ (production)
  │                                       ↑
  ├─→ develop ────────────────────────────┘ (integration)
  │      │              ↑         ↑
  │      └─→ feature/* ─┘         │
  │                               │
  └─→ hotfix/* ───────────────────┘
```

※ hotfix/*: main + develop の両方にマージ

| ブランチ | 用途 | マージ先 |
|---------|------|---------|
| `main` | 本番環境（タグ付きリリース） | - |
| `develop` | 開発統合（次期リリース準備） | main |
| `feature/*` | 新機能開発 | develop |
| `hotfix/*` | 本番緊急修正 | main + develop |

## クイックスタート

### 前提条件

| 要件 | バージョン | 確認コマンド |
|------|-----------|-------------|
| Python | 3.14 | `uv run python --version` |
| uv | 0.4+ | `uv --version` |
| Git | 2.0+ | `git --version` |
| Docker (任意) | 24.0+ | `docker --version` |

<details>
<summary>uvのインストール方法</summary>

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# pip経由
pip install uv
```

</details>

### セットアップ

```bash
# 1. リポジトリクローン
git clone https://github.com/yuta158/api-test-portfolio.git
cd api-test-portfolio

# 2. 依存関係インストール（uv使用、約10秒）
uv sync

# 3. テスト実行（並列）
uv run pytest -n auto

# 4. カバレッジ付きテスト（並列）
uv run pytest -n auto --cov=utils --cov=config --cov=models --cov-report=term

# 5. 特定マーカーのテスト実行
uv run pytest -n auto -m unit        # 単体テストのみ
uv run pytest -n auto -m integration # 統合テストのみ

# 6. 高速実行（並列、manual/external除外）
uv run pytest -n auto -m "not external and not manual"  # CI/CD相当の自動実行可能テストのみ

# 7. 週次手動実行（Rate Limit管理）
uv run pytest -m "manual or external"  # GitHub API統合テスト（週1回推奨、60 req/h制約）
```

## プロジェクト構成

```
api-test-devops-portfolio/
├── config/              # 設定管理（Pydantic Settings）
├── utils/               # ユーティリティ（APIクライアント等）
├── models/              # データモデル
├── tests/               # テストスイート（588件）
│   ├── unit/            # 単体テスト
│   ├── integration/     # 統合テスト
│   ├── performance/     # パフォーマンステスト
│   └── e2e/             # E2Eテスト（Playwright導入予定）
├── assets/              # デモGIF・画像
├── scripts/             # 自動化スクリプト
├── docs/                # ドキュメント
└── .github/workflows/   # CI/CDパイプライン
```

## アーキテクチャ

### システム構成図

```mermaid
graph TB
    subgraph "APIクライアント設計"
        BC[SyncAPIClient<br/>同期クライアント]
        BC --> JP[SyncJSONPlaceholderClient]
        AC[AsyncAPIClient<br/>非同期クライアント]
        AC --> AJP[AsyncJSONPlaceholderClient]
        AGH[AsyncGitHubClient<br/>GitHub API統合]
    end

    subgraph "設定管理"
        PS[Pydantic Settings] --> ENV[.env]
    end

    subgraph "品質保証"
        UT[Unit Tests] --> IT[Integration Tests]
        IT --> SEC[Security Tests]
        SEC --> PERF[Performance Tests]
    end
```

### 設計判断（Design Decisions）

API特性駆動でクライアントごとに実装範囲を最適化しています。

| 判断 | 選択 | 技術的根拠 |
|------|------|----------|
| **JSONPlaceholderClient: Sync/Async両実装** | 両パラダイム対応 | 認証なし・Rate Limit無のシンプルAPI。Django/Flask/CLI (Sync) から FastAPI/並行fetch (Async) まで広範なユースケースに対応。共通設定解決ロジックは `_resolve_client_config` / `_classify_error` で重複削減 |
| **GitHubClient: Async特化** | 非同期のみ | 認証 + Rate Limit (5000/h) + ETag対応のAPI特性により、並行fetch (`asyncio.gather`) と条件付きリクエスト (304 Not Modified) の恩恵が大きい。Sync caller は `asyncio.run()` で代替可 |
| **JSONPlaceholderClient → APIClient 継承** | クラス継承 | LSP遵守 (HTTP動詞契約維持) + boilerplate削減。汎用HTTP層とドメインメソッドの責務分離 (SRP) |
| **GitHubClient: 独立実装** | 継承せず | 戻り値型契約差異 (`httpx.Response` vs parsed JSON) と ETag/RateLimit/PII redaction の固有要件により、継承すると LSP違反。共通化は例外階層 (`GitHubAPIError(APIClientError)`) と utility 関数レベルに限定 |

詳細な決定背景・トレードオフ分析は ADR (Architecture Decision Records) 参照: `claudedocs/adr/`（ローカル保管・バージョン管理外）

### 将来の拡張ポイント（本番運用時）

本プロジェクトはポートフォリオとして設計されていますが、本番環境への移行時には以下の追加を推奨します：

| 拡張項目 | 目的 | 実装案 |
|---------|------|--------|
| **Circuit Breaker** | 障害時の連鎖的リトライ防止 | `tenacity`ライブラリまたは自前実装 |
| **Connection Pool** | 高負荷時のリソース最適化 | `httpx.Limits(max_keepalive_connections=20)` |
| **Distributed Tracing** | マイクロサービス間の追跡 | OpenTelemetry統合 |
| **Rate Limit Client** | API制限への適応 | Retry-Afterヘッダー活用 |

## エラー監視・可観測性

### Sentry統合

本プロジェクトでは、Sentry SDKを統合し、ERROR以上のログを自動でSentryに送信します。

**主な機能**:

- 🛡️ **機密データ保護**: 39種類の機密キーを自動スクラブ（password, token, api_key等）
- 🔄 **structlog連携**: ERROR/CRITICAL/EXCEPTIONレベルを自動送信
- ⚡ **サイレント失敗**: Sentry障害時もアプリケーション継続
- 🔐 **SecretStr保護**: DSNの平文出力防止

**環境変数設定**:

```bash
# Sentry設定（.envファイル）
SENTRY__ENABLED=true
SENTRY__DSN=https://xxx@xxx.ingest.us.sentry.io/xxx
SENTRY__ENVIRONMENT=production
SENTRY__TRACES_SAMPLE_RATE=0.1
SENTRY__SEND_DEFAULT_PII=false
```

**初期化（アプリケーション起動時）**:

```python
from utils.sentry_init import init_sentry

if init_sentry():
    logger.info("Sentry monitoring enabled")
```

> 📚 詳細はCLAUDE.mdの「Sentry統合」セクションを参照

## テスト戦略

### テストサマリー

| 種別 | 件数 | CI対象 | 備考 |
|------|------|--------|------|
| Unit tests | 549件 | ✅ | ビジネスロジック検証（Slow 1件含む） |
| Integration tests | 31件（CI対象: 26件） | ✅（external 5件除外） | API統合検証 |
| **CI合計（カバレッジ計測対象）** | **575件** | | |
| **カバレッジ** | **93.43%** | | unit+integration条件 |

**カバレッジ計測対象外テスト**

| 種別 | 件数 | 除外理由 |
|------|------|---------|
| Performance tests | 5件 | 週次のみ実行（performanceマーカーのみ、PR CI除外） |
| External API tests | 5件 | 実ネットワーク依存（Integration 31件の内数） |
| Smoke tests | 3件 | カバレッジ計測対象外（--no-covで実行） |
| E2E tests | 実装予定 | — |

> **合計テスト数（参考）**: 588件（全テスト）/ CI計測対象: 575件
> カバレッジはCI安定性確保のため、決定論的テスト（unit + integration）のみを計測対象としています。

### テストピラミッド

```mermaid
graph TB
    subgraph "Test Pyramid - 588件（CI対象: 575件）"
        E2E["🔝 E2E<br/>0件 → 5%目標"]
        Integration["🔗 Integration<br/>31件（CI対象: 26件）→ 25%目標"]
        Unit["🧱 Unit<br/>549件 → 70%目標"]
    end
    E2E --> Integration --> Unit

    style E2E fill:#ff6b6b,color:#fff
    style Integration fill:#1e90ff,color:#fff
    style Unit fill:#2ed573,color:#fff
```

**戦略根拠**: テストピラミッド原則に基づき、CI速度と信頼性のバランスを考慮

- **Unit (70%)**: ビジネスロジックの品質担保（高速・安定）
- **Integration (25%)**: API・DB接続の検証（中速・実環境近似）
- **E2E (5%)**: クリティカルパスのみ（低速・高信頼）

> **Note**: Slow testsはunit/integrationマーカーを併用のためCI対象(575件)に含む。Performance tests(5件)はweeklyのみ実行（PR CI除外）。External testsはintegration markerを併用のためIntegration(31件)の内数。Smoke tests(3件)のみカバレッジCI対象外（全PRに--no-covで実行）。

### テスト実行特性（CI最適化）

| マーカー | 用途 | CI実行タイミング |
|---------|------|-----------------|
| `unit` | 単体テスト | 全PR |
| `integration` | 統合テスト | 全PR |
| `smoke` | 基本機能確認 | 全PR（--no-cov、実API疎通確認） |
| `slow` | 実行時間 >3秒 | unit/integration併用テストのみCI対象（slow単独は除外） |
| `external` | 外部API依存 | 週次のみ |
| `performance` | 性能測定 | 週次のみ |
| `e2e` | E2Eテスト | Playwright導入後 |

> **CI最適化戦略**: `external`マーカーを週次実行に分離し、PRバリデーションを高速化（目標: 10分以内）

### CI/CD 多段階パイプライン

| Stage | トリガー | テスト内容 | timeout |
|-------|---------|-----------|---------|
| PR Validation | Pull Request | mypy + Unit + Integration + smoke | 15分 |
| PR Markdown Quality Check | Pull Request| markdownlint && textlint | 5分 |
| PR Trivy scan | Pull Request | Trivy脆弱性スキャン | 20分 |
| Post Validation | Push to main/develop | mypy + Smoke + e2e | 15分 |
| Post Trivy scan | Push to main/develop | Docker Build + Trivy | 20分 |
| Weekly Extended Test | Weekly | Performance + External API | 30分 |
| Weekly Link Check | Weekly | Markdown link check | 15分 |
| Status Report | 全トリガー | Pipeline結果集約 | 5分 |

### Trivy Security Scan（SARIF形式 + 3層検証）

Trivyセキュリティスキャンは**SARIF（Static Analysis Results Format）**形式で出力し、**3層検証**により確実性を担保：

```mermaid
graph LR
    A[Trivy Scan] --> B[Layer 1: File Existence]
    B --> C[Layer 2: Size Check ≥100 bytes]
    C --> D[Layer 3: JSON Validity]
    D --> E[GitHub Security Tab Upload]
```

**検証フロー**:

1. **Layer 1**: SARIFファイル存在確認
2. **Layer 2**: ファイルサイズ検証（≥100 bytes、空ファイル検出）
3. **Layer 3**: JSON妥当性検証（`jq empty`）

**エラーハンドリング**:

- `continue-on-error: true`: Trivyスキャン失敗時もパイプライン継続
- 各層で明確なエラーメッセージ出力
- Filesystem/Image scan個別に検証実行

**実装詳細**: 3層検証ロジックはComposite Actionとして実装され、pr-trivy-scan/post-trivy-scanの計4箇所（fs/imageスキャン各2）で再利用されています。

> 📚 詳細実装は [CI/CD運用ガイド](docs/guides/ci_cd_guide.md) を参照

---

## ライセンス

MIT

## お問い合わせ

- **GitHub**: [@yuta158](https://github.com/yuta158)
- **LinkedIn**: *プロフィール準備中*
