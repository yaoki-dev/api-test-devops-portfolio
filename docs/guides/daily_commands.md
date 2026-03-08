# 📋 API Test DevOps Portfolio - 日常開発コマンドリファレンス

*最終更新: 2026年03月08日*

瞬時にコマンド検索・実行が可能な実用的リファレンス。コピペ用説明とサンプル実行例、実行時間目安を併記。Claude Squad統合ワークフローを含む包括的開発ガイド。

## 🔥 Daily Development Commands (高頻度 - 日次使用)

### 🧪 テスト実行コマンド

#### Unit Testing (10-20秒) - 最頻繁実行

```bash
# 単体テストのみ実行 - 開発中の高速フィードバックループ
make test-unit

# 詳細出力での単体テスト
uv run pytest tests/unit/ -v -m "unit or not integration"

# 特定テストファイルのみ実行
uv run pytest tests/unit/test_basic.py -v
```

#### Integration Testing (30-45秒)

```bash
# 統合テストのみ実行
make test-integration

# 詳細出力での統合テスト
uv run pytest tests/integration/ -v -m integration
```

#### All Tests (45-60秒)

```bash
# 全テスト実行 - push前の最終確認
make test

# 詳細出力での全テスト実行
uv run pytest tests/ -v --tb=short
```

### 🔍 品質チェックコマンド

#### Quality Checks (30秒) - 並列実行最適化

```bash
# 統合品質チェック - ruff + mypy + bandit並列実行
make quality

# 個別品質チェック実行
make format     # コードフォーマット
make lint       # リンター実行 (ruff)
make type-check # 型チェック (mypy)
make security   # セキュリティスキャン (bandit)
```

#### 並列品質チェック (15秒 - 200%高速化)

```bash
# エージェント最適化並列実行
uv run ruff check . --fix & uv run mypy utils/ config/ models/ & uv run bandit -r . -ll

# コードフォーマット + リント並列
uv run ruff format . && uv run ruff check . --fix
```

### 📊 カバレッジ・レポートコマンド

#### Coverage Analysis (45秒) - HTMLレポート付き

```bash
# カバレッジレポート生成 - 85%閾値検証
make coverage

# 高速カバレッジチェック (閾値確認のみ)
uv run pytest --cov=. --cov-fail-under=85

# HTMLカバレッジレポート表示
open reports/htmlcov/index.html
```

#### カバレッジ詳細オプション

```bash
# ブランチカバレッジ付き詳細レポート
uv run pytest --cov=. --cov-branch --cov-report=html:reports/htmlcov --cov-report=term-missing

# XMLレポート生成 (CI/CD用)
uv run pytest --cov=. --cov-report=xml:reports/coverage.xml
```

## 🚀 Integrated CI/CD Commands (中頻度 - 週次使用)

### ⚡ パフォーマンス測定コマンド

#### Performance Testing (2-3分)

```bash
# 高速パフォーマンステスト
make performance-quick

# 包括的パフォーマンス分析 (5-8分)
make performance-comprehensive

# パフォーマンステストのみ実行
make test-performance
```

#### パフォーマンステスト詳細

```bash
# ベンチマーク付きパフォーマンステスト
uv run pytest tests/performance/ --benchmark-only --benchmark-sort=mean

# メモリ使用量監視付きテスト
uv run pytest tests/performance/ -v --benchmark-warmup=3
```

### 🔒 セキュリティスキャンコマンド

#### Security Validation (25秒 - 260%高速化)

```bash
# 高速セキュリティスキャン
make security-quick

# 包括的セキュリティ分析 - CI/CD品質ゲート準拠
make security-comprehensive

# セキュリティ並列実行
make security-quick & make performance-quick
```

#### セキュリティスキャン詳細

```bash
# セキュリティ静的解析（bandit）
uv run bandit -r utils/ config/ models/ -q

# bandit セキュリティスキャン (JSON出力)
uv run bandit -r utils/ config/ models/ -f json -o reports/security-report.json

# safety 脆弱性チェック
uv run safety check --json --output reports/safety-report.json

# pip-audit 依存関係監査
uv run pip-audit --format=json --output=reports/audit-report.json
```

### 🔄 Local CI Pipeline (5-8分)

#### Complete CI/CD Simulation

```bash
# ローカルCI/CDパイプライン - push前の完全検証
make ci-local

# Docker環境CI/CDパイプライン
make ci-docker

# 包括的CI/CDパイプライン (品質+セキュリティ+パフォーマンス)
make ci-comprehensive
```

#### 最適化開発サイクル

```bash
# 開発サイクル最適化実行
make setup && make test-unit && make quality && make coverage

# Git commit前の検証サイクル
make test && make coverage && make quality && make security-quick
```

## 🛠️ Environment Management (低頻度 - 月次使用)

### 📦 Project Setup

#### 初期セットアップ

```bash
# プロジェクト初期セットアップ
make setup

# 依存関係インストール (uv使用)
make install

# 開発環境起動支援
make dev
```

#### 環境詳細設定

```bash
# uv環境同期 (開発依存含む)
uv sync --dev

# Python環境確認
python --version  # 3.14.x確認

# プロジェクトステータス確認
make status
```

### 🐳 Docker Operations

#### Docker環境管理

```bash
# 開発環境起動
make docker-up

# Docker環境でのテスト実行
make docker-test

# 環境停止・クリーンアップ
make docker-down

# Dockerイメージビルド
make docker-build
```

#### Docker詳細操作

```bash
# コンテナログ表示
make docker-logs

# コンテナシェル起動
make docker-shell

# Docker環境の完全再構築
make docker-down && make docker-build && make docker-up
```

### 🧹 Maintenance

#### クリーンアップ

```bash
# キャッシュとレポートクリア
make clean

# 完全クリーンアップ (Docker含む)
make clean-all

# Python cache削除
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
```

## 🎯 特殊用途・統合コマンド

### 🤖 MCP最適化・監視

#### MCP統合実行

```bash
# MCP最適化実行
make mcp-optimize

# MCP監視実行
make mcp-monitor

# ダッシュボード起動
make dashboard-start

# ダッシュボードデータ更新
make dashboard-update
```

### 📊 効果測定・レポート

#### Effectiveness Measurement

```bash
# 効果測定デモ実行
python scripts/run_effectiveness_measurement.py demo

# 自動スケジューラー起動
python scripts/run_effectiveness_measurement.py start-scheduler

# システムヘルスチェック
python scripts/run_effectiveness_measurement.py status
```

#### パフォーマンス追跡

```bash
# ROI追跡・品質メトリクス取得
from monitoring.effectiveness_tracker import start_task, complete_task

# ダッシュボード確認
open monitoring/reports/dashboard_latest.html
```

## 🤖 Claude Squad統合ワークフロー

### 🌅 朝の開発開始パターン

#### ステップ1: 環境状態確認 (30秒)

```bash
# プロジェクトルートに移動
cd /Users/yuta/Yuta/python/api-test-devops-portfolio

# 前日の作業状態確認
cs list --all
git status
git log --oneline -10

# ワークツリー状態確認
git worktree list
make squad-status
```

#### ステップ2: 本日の作業計画立案 (10秒)

```bash
# セッション計画表示
echo "=== 本日のClaude Squad作業計画 ==="
echo "セッション A（コア開発）: API機能強化"
echo "セッション B（テスト）: カバレッジ85%維持"
echo "セッション C（セキュリティ）: CI/CD品質ゲート確認"
echo "セッション D（パフォーマンス）: 性能最適化"
echo "セッション E（ドキュメント）: 技術文書更新"
```

#### ステップ3: 並列セッション起動 (45秒)

```bash
# メイン開発セッション起動
cs spawn --agent=claude-code --task="API機能強化開発" --workspace=../claude-squad-workspaces/squad-core-dev

# テスト強化セッション起動
cs spawn --agent=claude-code --task="テストカバレッジ強化" --workspace=../claude-squad-workspaces/squad-testing

# セキュリティチェックセッション起動（必要時）
cs spawn --agent=claude-code --task="セキュリティ検証" --workspace=../claude-squad-workspaces/squad-security

# セッション確認
cs list
```

### 🔄 日中の並列開発パターン

#### パターン1: 機能追加開発（高頻度 - 5-15分サイクル）

```bash
# API機能開発（セッション A）
cs switch core-dev-001
# → utils/api_client.py の機能拡張
# → config/settings.py の設定追加
# → 非同期HTTP処理の最適化

# 対応テスト作成（セッション B）
cs switch testing-002
# → tests/unit/test_api_client.py の拡張
# → tests/integration/ の追加テスト
# → カバレッジ確認・85%維持

# セキュリティ検証（セッション C）
cs switch security-003
# → 新機能のセキュリティテスト追加
# → CI/CD品質ゲート確認
```

#### パターン2: バグ修正・品質改善（中頻度 - 30-60分サイクル）

```bash
# 問題調査・修正（セッション A + D）
cs spawn --agent=claude-code --task="性能問題調査修正" --workspace=../claude-squad-workspaces/squad-performance
cs spawn --agent=claude-code --task="コア機能バグ修正" --workspace=../claude-squad-workspaces/squad-core-dev

# 回帰テスト強化（セッション B）
cs switch testing-002
# → 既存テストの検証・強化
# → 回帰テスト追加

# 進捗確認
cs status performance-004
cs status core-dev-001
cs status testing-002
```

#### パターン3: 大規模リファクタリング（低頻度 - 2-4時間サイクル）

```bash
# 全セッション並列リファクタリング
cs spawn --agent=claude-code --task="アーキテクチャ改善" --workspace=../claude-squad-workspaces/squad-core-dev
cs spawn --agent=aider --task="テストコード改善" --workspace=../claude-squad-workspaces/squad-testing
cs spawn --agent=claude-code --task="セキュリティ強化" --workspace=../claude-squad-workspaces/squad-security
cs spawn --agent=claude-code --task="パフォーマンス最適化" --workspace=../claude-squad-workspaces/squad-performance
cs spawn --agent=claude-code --task="ドキュメント更新" --workspace=../claude-squad-workspaces/squad-docs

# 全セッション進捗監視
watch -n 10 'cs list'
```

### 🔍 Squad統合品質チェックワークフロー

#### リアルタイム品質確認 (各セッション15-30秒)

```bash
# 開発中の継続的品質チェック
# セッション A作業後
cs switch core-dev-001
make test-unit type-check

# セッション B作業後
cs switch testing-002
make coverage test-integration

# セッション C作業後
cs switch security-003
make security-quick

# セッション D作業後
cs switch performance-004
make performance-quick
```

#### 日次品質ゲートチェック (2-3分)

```bash
# 1日の終わりの包括品質チェック
make squad-quality

# 結果確認・問題対応
if [ $? -ne 0 ]; then
    echo "⚠️  品質問題検出 - 各セッションで問題解決必要"
    cs list
    make squad-status
else
    echo "✅ 全品質チェック合格"
fi
```

### 🌆 夕方の統合・マージパターン

#### ステップ1: セッション作業完了確認 (1-2分)

```bash
# 各セッション作業状況確認
cs review core-dev-001      # コア開発変更確認
cs review testing-002       # テスト変更確認
cs review security-003      # セキュリティ変更確認（該当時）
cs review performance-004   # パフォーマンス変更確認（該当時）

# 各セッション品質ゲート確認
make squad-quality
```

#### ステップ2: セッション統合準備 (2-3分)

```bash
# 統合前のコミット・プッシュ
cs switch core-dev-001
git add . && git commit -m "feat: API機能強化 - 非同期HTTP処理最適化"
git push origin feature/core-development

cs switch testing-002
git add . && git commit -m "test: API機能テスト追加 - カバレッジ85%維持"
git push origin feature/testing-qa

# 他のセッションも同様にコミット・プッシュ
```

#### ステップ3: 統合実行 (3-5分)

```bash
# セッション統合実行
make squad-integrate

# 統合後の完全検証
make ci-comprehensive

# 統合成功確認
git log --oneline integration/squad-merge -10
```

### 🌙 バンコク時間最適化パターン

#### 深夜作業設定（JST 22:00-02:00 / BKK 20:00-24:00）

```bash
# 夜間長時間作業セッション設定
cs spawn --agent=optimizer --task="夜間パフォーマンス最適化" --schedule=later --workspace=../claude-squad-workspaces/squad-performance

# 停電対策設定
cs config --auto-save=true --interval=30s
cs config --backup-frequency=1h

# セッション永続化
cs switch performance-night-001
# Ctrl+B, D でデタッチ（バックグラウンド継続）
```

#### 朝の夜間作業確認（JST 07:00 / BKK 05:00）

```bash
# 夜間セッション結果確認
cs list --all
cs review performance-night-001

# 夜間作業の統合
if cs status performance-night-001 | grep "completed"; then
    cs merge performance-night-001 --to=integration/squad-merge
    echo "✅ 夜間作業統合完了"
else
    echo "⏳ 夜間作業継続中"
fi
```

### 🚨 緊急対応ワークフロー

#### 本番障害対応（CRITICAL - 即時実行）

```bash
# 緊急調査・修正セッション並列起動
cs spawn --agent=debugger --task="本番障害原因調査" --priority=critical --workspace=../claude-squad-workspaces/squad-core-dev
cs spawn --agent=claude-code --task="ホットフィックス作成" --priority=critical --workspace=../claude-squad-workspaces/squad-security

# 緊急テスト実行
cs spawn --agent=tester --task="緊急回帰テスト" --priority=critical --workspace=../claude-squad-workspaces/squad-testing

# 進捗リアルタイム監視
watch -n 5 'cs list | grep critical'
```

#### セキュリティ脆弱性対応（HIGH - 2時間以内）

```bash
# セキュリティ専用緊急セッション
cs spawn --agent=security --task="脆弱性対応緊急修正" --priority=critical --workspace=../claude-squad-workspaces/squad-security

# 包括セキュリティチェック
make security-comprehensive

# CI/CD品質ゲート確認（bandit + Trivy）
uv run bandit -r utils/ config/ models/ -q
```

### 📊 Squad効率化・生産性向上パターン

#### 定期メンテナンス（週1回 - 15分）

```bash
# 週次Claude Squadメンテナンス
cs cleanup --days=7                    # 古いセッション削除
cs config --optimize                   # 設定最適化
make squad-status                      # 全体状況確認

# ワークツリー最適化
git worktree prune                     # 不要ワークツリー削除
git gc --aggressive                    # Gitリポジトリ最適化
```

#### 月次効果測定（月1回 - 30分）

```bash
# 月次Claude Squad効果測定
echo "=== 月次Claude Squad効果レポート ==="
echo "セッション数: $(cs list --all | wc -l)"
echo "品質ゲート合格率: $(make squad-quality && echo 100% || echo 要改善)"
echo "テストカバレッジ: $(uv run pytest --cov=. --cov-report=term | grep TOTAL | awk '{print $4}')"

# パフォーマンス測定
python scripts/run_effectiveness_measurement.py demo
```

### 🎯 Squad専用コマンド実行例集

#### よく使用するセッション管理コマンド

```bash
# 基本セッション管理
cs list                               # アクティブセッション確認
cs spawn --agent=claude-code --task="開発タスク"  # 新規セッション
cs switch session-id                  # セッション切り替え
cs kill session-id                    # セッション終了

# 作業確認・統合
cs status session-id                  # セッション詳細確認
cs review session-id                  # 変更内容確認
cs merge session-id --to=branch       # ブランチ統合

# 品質・効率管理
make squad-status                     # 全体状況確認
make squad-quality                    # 品質チェック
make squad-integrate                  # 統合実行
make squad-cleanup                    # クリーンアップ
```

#### デバッグ・トラブルシューティング

```bash
# セッション問題対応
cs logs session-id                    # セッションログ確認
cs restart session-id                 # セッション再起動
cs recover session-id                 # セッション復旧

# 詳細診断
cs config --debug=true               # デバッグモード有効
cs spawn --verbose --task="テスト"    # 詳細ログ付きセッション
```

### 📈 Claude Squad統合効果指標

#### 定量的効果指標

- **並列開発速度**: 280-440%向上（セッション並列処理効果）
- **品質保証**: 85%テストカバレッジ継続維持
- **セキュリティ**: CI/CD品質ゲート（pytest + ruff + mypy + Trivy）
- **CI/CD効率**: 10ワークフロー最適化活用
- **24時間開発**: バンコク時差（JST+7）活用パターン

#### Squad運用ベストプラクティス

1. **朝の状態確認**: 必ず`cs list --all`と`make squad-status`実行
2. **セッション命名**: 一貫した命名規則維持（機能-用途-番号）
3. **定期統合**: 機能完了毎の`make squad-integrate`実行
4. **品質ゲート**: 作業終了時の品質チェック必須実行
5. **バックアップ**: 重要作業前の状態保存励行

## ⚡ Performance Improvement Metrics

| Command Category | Sequential Time | Parallel Time | Improvement |
|------------------|-----------------|---------------|-------------|
| Quality Checks | 45 seconds | 15 seconds | **200% faster** |
| Test + Coverage | 60 seconds | 35 seconds | **71% faster** |
| Security Scan | 90 seconds | 25 seconds | **260% faster** |
| Complete CI/CD | 8 minutes | 3.2 minutes | **150% faster** |

## 🎯 Quick Reference

### 最頻繁使用 (日次)

```bash
make test-unit      # 10-20秒 - 開発フィードバック
make quality        # 30秒 - 品質チェック
make coverage       # 45秒 - カバレッジ確認
```

### 重要検証 (週次)

```bash
make ci-local              # 5-8分 - push前完全検証
make performance-quick     # 2-3分 - パフォーマンス確認
make security-comprehensive # 5分 - セキュリティ包括確認
```

### 環境管理 (月次)

```bash
make setup         # 初期設定
make docker-up     # Docker環境
make clean-all     # 完全クリーンアップ
```

## 🔧 エラー対応・トラブルシューティング

### 一般的な問題解決

```bash
# 依存関係エラー
uv sync --dev && make install

# テスト環境リセット
make clean && make setup

# Docker環境リセット
make docker-down && make clean-all && make docker-build
```

### 品質チェック問題

```bash
# ruff警告修正
uv run ruff check . --fix

# 型エラー確認
uv run mypy utils/ config/ models/ --show-error-codes

# セキュリティ警告詳細
uv run bandit -r . -ll -v
```

---

**備考**: このリファレンスは551件のテスト（CI対象: 483件）、92.73%カバレッジ（閾値85%）、CI/CD品質ゲート（pytest + ruff + mypy + Trivy）による品質基準に基づいています。
