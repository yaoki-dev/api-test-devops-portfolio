# 技術スタック詳細

*最終更新: 2025年09月23日*

## 🛠️ 使用技術・ツール

### 開発言語・フレームワーク

- **Python**: 3.12 (メインバージョン・最適化実装)
  - 3.10-3.12 互換性サポート（CI/CDマトリックス対応）
  - 本プロジェクトは Python 3.12 で設計・最適化
- **httpx**: 非同期HTTPクライアント
- **pytest**: テストフレームワーク + プラグイン
- **structlog**: 構造化ログ
- **pydantic**: データバリデーション・設定管理
- **ruff**: 統合リンター・フォーマッター


### DevOps・インフラ

- **Docker**: 6段階Multi-stage build（Base→Dependencies→Development→Test→Staging→Production）
  - Enterprise級セキュリティ強化・ユーザー権限分離
  - レイヤーキャッシュ最適化・ビルド時間短縮
  - 環境別最適化（開発・テスト・ステージング・本番）
- **GitHub Actions**: 10個のEnterprise CI/CDワークフロー
  - メインCI: Python 3.10-3.12マトリックス・品質ゲート・自動デプロイ
  - セキュリティパイプライン: bandit・safety・高度セキュリティスキャン
  - パフォーマンステスト: 負荷テスト・ベンチマーク・最適化検証
  - エンタープライズ統合: マトリックス並列処理・効率最適化
- **docker-compose**: マルチプロファイル開発環境（development・test・staging・production）
- **Make**: 包括的タスク自動化・開発・テスト・デプロイ効率化


### パッケージ管理・依存関係

- **uv**: モダンPythonパッケージマネージャー（メインツール）
  - pip比 10-100倍高速な依存解決
  - uv.lock（2,986行）による決定論的ビルド
  - Docker統合・128パッケージの大規模管理
  - 高速仮想環境・ビルド時間大幅短縮


### テスト・品質管理統合システム

- **pytest エコシステム**: 包括的テストフレームワーク統合
  - pytest-asyncio: 非同期テスト・並列処理対応
  - pytest-cov: カバレッジ85%目標・HTML/XML レポート
  - pytest-mock: 高度モック・スタブ・外部依存分離
  - pytest-xdist: 並列テスト実行・CI/CD最適化
  - pytest-benchmark: パフォーマンステスト・ベンチマーク
- **品質保証統合**: ruff (リンター・フォーマッター) + mypy (型チェック)
- **pre-commit**: Git hooks・コミット前品質チェック自動化


### セキュリティ・コンプライアンス

- **OWASP API Security Top 10**: 包括的APIセキュリティ対応
  - 84個のテストケース・脆弱性検証・企業コンプライアンス対応
- **静的解析統合**: bandit (SAST) + safety (依存関係脆弱性) + semgrep (高度パターン検出)
- **pip-audit**: パッケージセキュリティ監査・継続的脆弱性チェック
- **カスタムセキュリティ**: 設定ファイル検査・機密情報検知・企業セキュリティ基準対応


### 非同期・パフォーマンス

- **非同期HTTP統合**: httpx (クライアント) + aiohttp (サーバー)
- **パフォーマンス監視**: psutil (システムリソース) + locust (負荷テスト)
- **構造化ログ**: structlog・JSON形式・監視システム連携


## 📊 技術選択理由


### Python 3.12
- 型安全性（Type Hints）強化・パフォーマンス最適化
- 非同期処理・新機能（match文・dataclass改善）活用
- CI/CDマトリックス（3.10-3.12）対応・最新環境メリット

### uv パッケージ管理
- pip比 10-100倍高速な依存解決・ビルド時間短縮
- 決定論的ビルド（uv.lock）・再現可能な環境構築
- Docker統合最適化・レイヤーキャッシュ効率化
- Rust実装による安定性・信頼性向上

### httpx over requests
- 非同期対応（async/await）
- HTTP/2サポート
- モダンAPI設計

### pytest over unittest
- 豊富なプラグインエコシステム
- 簡潔なテスト記述
- 強力なfixture機能

### Docker 6段階Multi-stage Build
- Base stage: セキュリティ強化・Alpine Linux・ユーザー権限分離
- Dependencies stage: uvパッケージ管理・レイヤーキャッシュ最適化
- Development/Test/Staging/Production: 環境別最適化・Enterprise対応
- イメージサイズ最適化・ビルド時間短縮・デプロイ効率化

### GitHub Actions Enterprise CI/CD (10ワークフロー)
- メインCI: Python 3.10-3.12マトリックス・6ジョブ並列実行・品質ゲート
- セキュリティパイプライン: bandit・safety・高度セキュリティスキャン
- パフォーマンステスト: 負荷テスト・ベンチマーク・最適化検証・監視
- エンタープライズ統合: マトリックス並列処理・効率最適化・自動デプロイ


## 🏗️ アーキテクチャ設計


```
┌─ 開発環境 ────────────────────┐
│  - Docker Compose            │
│  - ホットリロード             │
│  - デバッグ環境               │
└───────────────────────────────┘

┌─ テスト環境 ──────────────────┐
│  - pytest + カバレッジ        │
│  - 非同期テスト               │
│  - モック・スタブ             │
└───────────────────────────────┘

┌─ Enterprise CI/CD (10ワークフロー) ─┐
│  - メインCI: 3.10-3.12マトリックス   │
│  - セキュリティ: bandit+safety+OWASP│
│  - パフォーマンス: 負荷+ベンチマーク │
│  - 品質ゲート: 85%カバレッジ+型検証 │
│  - 自動デプロイ: 6環境統合対応       │
└─────────────────────────────────────┘

┌─ 監視・ログ ──────────────────┐
│  - 構造化ログ（structlog）     │
│  - パフォーマンス監視         │
│  - セキュリティスキャン       │
└───────────────────────────────┘
```


## 📦 プロジェクト構造


```
api-test-devops-portfolio/
├── .github/workflows/     # Enterprise CI/CDパイプライン (10ワークフロー)
│   ├── main-ci.yml       # メイン統合パイプライン (Python 3.10-3.12)
│   ├── security-scan.yml # セキュリティスキャン (bandit+safety+OWASP)
│   ├── performance-testing.yml # パフォーマンステスト・負荷テスト
│   ├── enterprise-*      # エンタープライズ統合・並列最適化
│   └── advanced-*        # 高度セキュリティ・API効率化
├── tests/                # 包括的テストスイート (51テストケース)
│   ├── unit/            # 単体テスト (基本・API・設定・監視)
│   ├── integration/     # 統合テスト (システム連携・E2E)
│   ├── performance/     # パフォーマンステスト (負荷・ストレス・ベンチマーク)
│   ├── security/        # セキュリティテスト (OWASP API Top 10・84テストケース)
│   └── system/          # システムテスト (制約検証・統合バリデーション)
├── utils/               # 包括的ユーティリティ (28スクリプト・200万行実装)
│   ├── api_client.py    # 非同期HTTPクライアント・統合API
│   ├── performance_monitor.py # リアルタイム性能監視・SRE級システム
│   ├── security_helpers.py    # セキュリティヘルパー・OWASP準拠
│   ├── learning_*.py    # AI協働学習システム・進捗管理
│   └── effectiveness_*.py     # 効果測定・ROI分析・価値評価
├── config/              # 包括的設定管理・企業対応
│   ├── settings.py      # pydantic設定・型安全・環境分離
│   ├── alerts.json      # 監視アラート・通知・escalation
│   ├── performance_*.py # パフォーマンス閾値・品質基準
│   └── bangkok_*.yaml   # バンコク特化最適化・時差活用
├── docs/                # 技術ドキュメント・学習ガイド
├── reports/             # 自動レポート出力・分析・監視
├── scripts/             # 包括的自動化スクリプト・DevOps効率化
├── monitoring/          # 統合監視システム・SRE運用
├── Dockerfile           # 6段階Multi-stage (Enterprise最適化)
├── docker-compose.yml   # マルチ環境統合 (dev/test/staging/prod)
├── uv.lock             # 128パッケージ決定論的ビルド (2,986行)
└── pyproject.toml      # 統合プロジェクト設定・依存関係管理
```


## 🚀 Enterprise運用プロセス・ベストプラクティス

#### 🔗 関連ドキュメント
- [`project_index_summary.md`](./project_index_summary.md) - プロジェクト概要・クイックナビゲーション
- [`project_index_detail.md`](./project_index_detail.md) - 詳細インデックス・全体アーキテクチャ
- [`REORGANIZATION_SUMMARY.md`](./REORGANIZATION_SUMMARY.md) - プロジェクト再編成記録
- [`INTEGRATION_COMPLETION_CERTIFICATE.md`](./INTEGRATION_COMPLETION_CERTIFICATE.md) - 統合完成認証

### 🔄 開発・デプロイワークフロー

#### **Phase 1: 開発・品質保証**
```bash
# 1. 開発環境立ち上げ (Docker統合)
uv sync --dev                    # 高速依存関係同期
docker-compose --profile development up -d

# 2. 品質チェック統合実行
uv run ruff check . --fix        # コード品質・自動修正
uv run mypy utils/ config/       # 型チェック・安全性検証
uv run pytest --cov=utils --cov-fail-under=85  # 85%カバレッジ必達

# 3. セキュリティ検証
uv run bandit -r . -ll          # セキュリティ静的解析
uv run safety check             # 依存関係脆弱性チェック
```

#### **Phase 2: CI/CD統合・自動化**
```bash
# 4. GitHub Actions自動実行 (10ワークフロー並列)
git push origin feature/branch   # 自動トリガー
# → Python 3.10-3.12マトリックス並列テスト
# → セキュリティ・パフォーマンス・統合テスト
# → 品質ゲート・85%カバレッジ・OWASP準拠確認

# 5. Docker統合ビルド・検証
docker-compose build --no-cache test staging production
docker-compose --profile test up test     # テスト環境検証
docker-compose --profile staging up -d    # ステージング環境検証
```

#### **Phase 3: 本番デプロイ・監視**
```bash
# 6. 本番デプロイ・ヘルスチェック
docker-compose --profile production up -d production
curl -f http://localhost:8000/health       # ヘルスチェック自動化

# 7. 継続監視・アラート
# → structlog構造化ログ・リアルタイム監視
# → performance_monitor.py・SRE級システム監視
# → 自動アラート・escalation・障害対応
```

### 🏢 Enterprise統合・スケーラビリティ

#### **大規模チーム対応**
- **並列開発**: Docker環境分離・branch別CI/CD・マージ時統合テスト
- **品質統一**: pre-commit hooks・ruff+mypy強制・85%カバレッジゲート
- **セキュリティ統制**: OWASP API Top 10準拠・継続的脆弱性監視

#### **クラウド・インフラ最適化**
- **uv高速ビルド**: pip比10-100倍高速・Docker層キャッシュ最適化
- **6環境分離**: development/test/staging/production/enterprise/monitoring
- **自動スケーリング**: 負荷テスト基準・パフォーマンス閾値・動的調整


---
