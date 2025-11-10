# Claude Code プラグイン活用ガイド

*最終更新: 2025年10月28日*

## 📚 目次

1. [プラグイン概要](#プラグイン概要)
2. [インストール済みプラグイン](#インストール済みプラグイン)
3. [基本的な使用方法](#基本的な使用方法)
4. [Week 7-10での推奨使用シナリオ](#week-7-10での推奨使用シナリオ)
5. [プラグイン連携パターン](#プラグイン連携パターン)
6. [トラブルシューティング](#トラブルシューティング)

---

## プラグイン概要

### インストール確認

本プロジェクトでは、以下の6つのclaude-code-templatesプラグインをインストールしています：

```bash
# インストール済みプラグイン確認
cat ~/.claude/plugins/installed_plugins.json
```

### プラグインの実態

**重要な発見**:
- 言及された6つのプラグイン（devops-automation、documentation-generator等）は独立したプラグインではなく、**ccplugins（claude-code-plugins）フレームワーク**または**SuperClaudeフレームワーク**の一部
- 実際には `/test`, `/implement`, `/security-scan`, `/docs`, `/refactor` 等の汎用コマンドが該当機能を提供

---

## インストール済みプラグイン

### 1. devops-automation（実装: `/implement`）

**主要機能**:
- タスク自動化とワークフロー実装
- セッション継続型の段階的実装
- 進捗追跡と状態管理

**本プロジェクトでの推奨用途**:
- Docker 4-stage実装（Week 7）
- docker-compose 4環境構築（Week 7）
- GitHub Actions workflow実装（Week 8）

**基本使用方法**:
```bash
# チェックリストベース実装
/implement docs/プロジェクト再編/Week7_Docker実装完了チェックリスト.md

# 自然言語タスク指定
/implement "GitHub Actions test workflow実装"

# 仕様書ベース実装
/implement docs/プロジェクト再編/Week8_Day44_CICD最適化強化仕様.md
```

**特徴**:
- ✅ セッション継続: `implement/state.json`で中断・再開可能
- ✅ 進捗追跡: `implement/plan.md`で実装計画・進捗可視化
- ✅ AI協働80%: 実装の80%をAIが自動実行

---

### 2. documentation-generator（実装: `/docs`）

**主要機能**:
- 全ドキュメント一括同期更新
- バッジ自動生成（shields.io統合）
- 技術的正確性検証

**本プロジェクトでの推奨用途**:
- README.md更新（Docker/CI/CDセクション）
- CHANGELOG.md自動更新
- 技術ガイド作成・更新

**基本使用方法**:
```bash
# 全ドキュメント同期更新
/docs update

# 特定ドキュメント更新
/docs update README.md

# バッジ追加
/docs badges
```

**自動更新対象**:
- `README.md`
- `CHANGELOG.md`
- `docs/docker_guide.md`
- `docs/DOCKER_DEVOPS_INTEGRATION_MASTER_PLAN.md`

**ROI**: +20円/時給（ドキュメント作成時間63%削減）

---

### 3. git-workflow（関連機能含む）

**主要機能**:
- Git操作自動化
- コミットメッセージ生成
- ブランチ管理

**本プロジェクトでの推奨用途**:
- 実装完了時の自動コミット
- Pull Request作成支援
- ブランチ戦略管理

**基本使用方法**:
```bash
# 変更内容から自動コミット
git add .
claude commit  # Conventional Commits形式で自動生成

# Pull Request作成
claude pr create
```

---

### 4. performance-optimizer（関連機能含む）

**主要機能**:
- パフォーマンスボトルネック特定
- 最適化提案
- ベンチマーク自動化

**本プロジェクトでの推奨用途**:
- pytest実行時間最適化（Week 5-6）
- Docker build時間削減（Week 7）
- CI/CDパイプライン高速化（Week 8）

**基本使用方法**:
```bash
# パフォーマンス分析
/analyze performance

# ボトルネック特定
/analyze bottlenecks tests/

# 最適化実装
/implement "pytest並列実行最適化"
```

**Week 8での具体的活用**:
- Cache Strategy最適化: 2分30秒 → 15秒（90%削減）
- Parallel Job最適化: 8分 → 5分（40%削減）

---

### 5. security-pro（実装: `/security-scan`）

**主要機能**:
- 脆弱性自動検出
- セキュリティ自動修正
- セッション継続型修正フロー

**本プロジェクトでの推奨用途**:
- Dockerfileセキュリティスキャン（Week 7）
- 依存関係脆弱性チェック（Week 8）
- 本番環境セキュリティ検証（Week 10）

**基本使用方法**:
```bash
# Dockerfileスキャン
/security-scan Dockerfile docker-compose.yml

# Python依存関係スキャン
/security-scan requirements.txt

# 全体スキャン
/security-scan
```

**自動修正フロー**:
1. 脆弱性検出（Critical/High/Medium分類）
2. 修正計画生成（`security-scan/plan.md`）
3. 段階的自動修正（AI協働70%）
4. 再スキャン検証

**ROI**: +30円/時給（セキュリティ修正時間50%削減）

---

### 6. testing-suite（実装: `/test`）

**主要機能**:
- コンテキスト検出型テスト実行
- 失敗時自動修正（Cold Start検出）
- テスト戦略最適化

**本プロジェクトでの推奨用途**:
- pytest自動実行・カバレッジ測定（Week 1-6）
- Docker環境テスト（Week 7）
- CI/CD統合テスト（Week 8）

**基本使用方法**:
```bash
# 自動コンテキスト検出テスト
/test

# 特定テスト実行
/test tests/unit/test_async_client.py

# カバレッジレポート生成
/test --coverage

# Docker環境テスト
/test "docker-compose up dev"
```

**コンテキスト検出機能**:
- `git diff`でDockerfile変更検知 → Docker関連テスト自動実行
- `.github/workflows/`変更検知 → CI/CD統合テスト自動実行
- `tests/`変更検知 → pytest自動実行

**ROI**: +80円/時給（テスト実行・デバッグ時間53%削減）

---

## 基本的な使用方法

### プラグインコマンド実行

```bash
# 利用可能なコマンド一覧表示
/help

# プラグイン管理
/plugin                    # インタラクティブ管理UI
/plugin enable <name>      # プラグイン有効化
/plugin disable <name>     # プラグイン無効化
/plugin uninstall <name>   # プラグイン削除
```

### 推奨ワークフロー

```mermaid
graph LR
    A[/implement] --> B[実装]
    B --> C[/test]
    C --> D{Pass?}
    D -->|Yes| E[/security-scan]
    D -->|No| F[自動修正]
    F --> C
    E --> G{脆弱性0?}
    G -->|Yes| H[/docs update]
    G -->|No| I[自動修正]
    I --> E
    H --> J[git commit]
```

---

## Week 7-10での推奨使用シナリオ

### Week 7: Docker実装（Day 37-42, 42時間）

#### Day 37-39: Dockerfile 4-stage実装

**使用コマンド**: `/implement` + `/test`

**実行手順**:
```bash
# 1. 実装開始（朝8:00-9:00, 1h）
cd /Users/yuta/Yuta/python/api-test-devops-portfolio
/implement docs/プロジェクト再編/Week7_Docker実装完了チェックリスト.md

# 自動実行フロー:
# - Phase 1: チェックリスト解析（AI）
# - Phase 2: 実装計画生成（implement/plan.md作成）
# - Phase 3: 段階的実装開始

# 2. 各stage実装・検証（9:00-16:00, 6h）
# builder stage実装 → 自動検証
# dev stage実装 → 自動検証
# test stage実装 → 自動検証
# ci stage実装 → 自動検証
# prod stage実装 → 自動検証

# 3. セキュリティスキャン（16:00-17:00, 1h）
/security-scan Dockerfile
```

**期待効果**:
- 実装時間: 30h → 15h（50%削減）
- AI協働率: 80%
- 品質保証: 各stage自動検証

---

#### Day 40-41: docker-compose 4環境構築

**使用コマンド**: `/implement` + `/test`

**実行手順**:
```bash
# 1. 実装開始（朝8:00-10:00, 2h）
/implement "docker-compose 4環境構築（dev/test/ci/prod）"

# 2. 環境別実装・検証（10:00-17:00, 6h）
# dev環境実装 → /test "docker-compose up dev"
# test環境実装 → /test "docker-compose run test"
# ci環境実装 → /test "docker-compose run ci"
# prod環境実装 → /test "docker-compose up prod"

# 3. 統合テスト（最終確認）
/test  # 全環境自動テスト
```

**期待効果**:
- 実装時間: 15h → 7h（53%削減）
- エラー自動修正: Portコンフリクト、Volume permission等
- 統合テスト: 全環境自動検証

---

#### Day 42: セキュリティ・最適化

**使用コマンド**: `/security-scan` + `/docs`

**実行手順**:
```bash
# 1. セキュリティスキャン（朝8:00-11:00, 3h）
/security-scan Dockerfile docker-compose.yml

# 自動実行フロー:
# - Hardcoded secrets検出 → 環境変数化（自動修正）
# - Base imageセキュリティスキャン → 更新提案
# - Volume permission問題検出 → 自動修正

# 2. ドキュメント更新（午後13:00-16:00, 3h）
/docs update

# 自動更新対象:
# - README.md Dockerセクション追加
# - CHANGELOG.md Week 7エントリ追加
# - docs/docker_guide.md 更新

# 3. Week 7振り返り（16:00-17:00, 1h）
# - 実装完了確認
# - チェックリストスコアリング
```

**期待効果**:
- セキュリティ修正: 12h → 6h（50%削減）
- ドキュメント作成: 8h → 3h（63%削減）
- 脆弱性ゼロ確認: 自動再スキャン

---

### Week 8: CI/CD統合（Day 43-48, 42時間）

#### Day 43: GitHub Actions基礎実装

**使用コマンド**: `/implement` + `/test`

**実行手順**:
```bash
# 1. workflow実装開始（朝8:00-10:00, 2h）
/implement "GitHub Actions test workflow実装"

# 実装内容:
# - .github/workflows/test.yml設計・実装
# - Matrix戦略設計（Python 3.10-3.12並列）
# - pytest統合設定

# 2. 動作確認（10:00-17:00, 6h）
git add .github/workflows/test.yml
git commit -m "feat(ci): add test workflow"
git push

# workflow失敗時:
/test  # ログ解析 → 自動修正提案
```

**期待効果**:
- workflow実装: 18h → 9h（50%削減）
- 失敗時自動修正: uv install追加、timeout設定等

---

#### Day 44: CI/CD最適化強化（最重要）

**使用コマンド**: `/implement`

**実行手順**:
```bash
# 朝（8:00-10:00, 2h）
/implement docs/プロジェクト再編/Week8_Day44_CICD最適化強化仕様.md

# Section 2自動実行（最大ROI）:
# 1. Cache Strategy Deep Dive（1h）:
#    - 3層キャッシュ実装（uv/pip/pre-commit）
#    - Hash-based invalidation設定
#    - 効果測定: 2分30秒 → 15秒（90%削減）
#
# 2. Parallel Job Optimization（0.5h）:
#    - test/quality並列Job実装
#    - Job dependency DAG可視化
#    - 実行時間削減: 8分 → 5分（40%削減）
#
# 3. Workflow Monitoring Setup（0.5h）:
#    - Build time alerts設定（5分超過検知）
#    - Slack failure notifications実装

# 実装（10:00-17:00, 6h）
# - Quality Gate自動化（1.5h）
# - GitHub Actions Matrix戦略（1.5h）
# - 理解度確認問題実施（1h）
```

**期待効果**:
- **ROI最大**: +108円/時給効果
- **Cache効果**: ビルド時間90%削減
- **Parallel効果**: 実行時間40%削減

---

#### Day 46: セキュリティスキャン統合

**使用コマンド**: `/security-scan` + `/implement`

**実行手順**:
```bash
# 1. safety統合（朝8:00-11:00, 3h）
/implement "safety + CodeQL統合実装"

# 2. セキュリティ検証（午後13:00-16:00, 3h）
/security-scan

# 自動実行フロー:
# - False positive判定
# - 脆弱性ゼロ確認
# - セキュリティレポート生成
```

**期待効果**:
- セキュリティ統合: AI協働75%
- ROI: +24円/時給

---

#### Day 47: ドキュメント最終化

**使用コマンド**: `/docs`

**実行手順**:
```bash
# ドキュメント一括更新（朝8:00-11:00, 3h）
/docs update

# 自動更新内容:
# - README.md CI/CDセクション追加
# - CHANGELOG.md Week 8エントリ追加
# - docs/DOCKER_DEVOPS_INTEGRATION_MASTER_PLAN.md 更新
# - バッジ自動生成（Test/Coverage/Security/Python）
```

**期待効果**:
- ROI: +20円/時給
- バッジ自動追加: shields.io統合

---

### Week 9-10: ポートフォリオ最適化・応募準備

#### Week 9（Day 49-54）: README最適化

**使用コマンド**: `/docs` + `/implement`

**実行手順**:
```bash
# 1. README大幅改善（Day 49-52）
/docs update README.md

# 自動最適化内容:
# - 技術スタック可視化（バッジ・図表追加）
# - 実装ハイライト明確化
# - 使用方法・セットアップガイド改善

# 2. Case Study作成（Day 53-54）
/implement "Docker + CI/CD Case Study作成"

# 成果物:
# - docs/case_studies/docker_cicd_implementation.md
# - 問題・解決・成果の構造化文書
```

**期待効果**:
- ポートフォリオ訴求力向上
- 市場価値: 4,000-4,500円/時給達成

---

#### Week 10（Day 55-60）: 応募準備・初回応募

**使用コマンド**: `/docs` + `/security-scan`

**実行手順**:
```bash
# 1. 最終セキュリティ検証（Day 55-56）
/security-scan

# 2. 最終ドキュメントレビュー（Day 57）
/docs update

# 3. 応募準備（Day 58-60）
# - 応募書類作成（AI協働50%）
# - GitHub Profile README更新
# - ポートフォリオURL整理
```

**期待効果**:
- 応募準備効率化: 30%削減
- 最終品質保証: 脆弱性ゼロ確認

---

## プラグイン連携パターン

### パターン1: Docker実装フロー（Week 7）

```bash
/implement → /test → /security-scan → /docs update → commit
```

**具体例**:
```bash
# 1. Dockerfile実装
/implement docs/プロジェクト再編/Week7_Docker実装完了チェックリスト.md

# 2. ビルド検証
/test

# 3. セキュリティスキャン
/security-scan Dockerfile

# 4. ドキュメント更新
/docs update

# 5. コミット
git add . && git commit -m "feat(docker): implement 4-stage Dockerfile"
```

---

### パターン2: CI/CD統合フロー（Week 8）

```bash
/implement → git push → /test → /security-scan → /docs update → commit
```

**具体例**:
```bash
# 1. GitHub Actions実装
/implement "GitHub Actions test workflow実装"

# 2. 動作確認（GitHub Actions実行）
git add .github/workflows/ && git commit -m "feat(ci): add test workflow"
git push

# 3. workflow検証
/test  # workflow失敗時は自動修正提案

# 4. セキュリティ統合
/security-scan

# 5. ドキュメント更新
/docs update
```

---

### パターン3: 緊急修正フロー

```bash
/security-scan → 自動修正 → /test → commit
```

**具体例**:
```bash
# 1. セキュリティスキャン（脆弱性検出）
/security-scan

# 自動修正フロー:
# - Critical脆弱性自動修正
# - High脆弱性修正提案

# 2. 修正検証
/test

# 3. コミット
git add . && git commit -m "fix(security): resolve CVE-XXXX vulnerability"
```

---

## トラブルシューティング

### プラグインコマンドが見つからない場合

```bash
# 利用可能なコマンド確認
/help

# プラグイン状態確認
/plugin

# 再インストール（必要時）
/plugin uninstall testing-suite@claude-code-templates
/plugin install testing-suite@claude-code-templates
```

---

### `/test`が期待通り動作しない場合

**症状**: コンテキスト検出が失敗

**解決策**:
```bash
# 明示的なテスト指定
/test tests/unit/

# カバレッジ指定
/test --coverage --cov-fail-under=85

# Docker環境テスト
/test "docker-compose up dev"
```

---

### `/security-scan`で修正が適用されない場合

**症状**: 脆弱性検出後、自動修正が実行されない

**解決策**:
```bash
# セッション状態確認
ls security-scan/

# 手動修正実行
/security-scan resume

# 強制再スキャン
/security-scan --force
```

---

### `/docs`でドキュメントが更新されない場合

**症状**: README.md等が更新されない

**解決策**:
```bash
# 特定ドキュメント明示
/docs update README.md

# 変更差分確認
git diff

# 手動確認後、必要なら手動編集
```

---

## 自動化効果まとめ

### Week 7-8総合効果

| 指標 | 従来手法 | プラグイン活用 | 改善率 |
|------|---------|--------------|--------|
| 総学習時間 | 83h | 40h | **52%削減** |
| エラー修正時間 | 20h | 8h | **60%削減** |
| ドキュメント作成時間 | 8h | 3h | **63%削減** |
| セキュリティ修正時間 | 12h | 6h | **50%削減** |
| テストデバッグ時間 | 15h | 7h | **53%削減** |

### 優先度別推奨順位

| 優先度 | コマンド | Week 7-8使用頻度 | ROI（時給換算） | 理由 |
|--------|---------|----------------|----------------|------|
| 🔴 Critical | `/implement` | 10回以上 | +150円/h | 実装自動化の中核 |
| 🔴 Critical | `/test` | 15回以上 | +80円/h | 自動検証・失敗時修正 |
| 🟡 High | `/security-scan` | 5回 | +30円/h | セキュリティ自動修正 |
| 🟡 High | `/docs` | 3回 | +25円/h | 全ドキュメント同期 |
| 🟢 Medium | `/refactor` | 1-2回 | +15円/h | コード品質向上 |

---

## 参考リソース

### 公式ドキュメント

- [Claude Code公式ドキュメント](https://docs.claude.com/en/docs/claude-code/claude_code_docs_map.md)
- [claude-code-templates GitHub](https://github.com/davila7/claude-code-templates)
- [プラグイン開発ガイド](https://docs.claude.com/en/docs/claude-code/plugins.md)

### 本プロジェクト関連ドキュメント

- `docs/プロジェクト再編/Week7_Docker実装完了チェックリスト.md`
- `docs/プロジェクト再編/Week8_Day44_CICD最適化強化仕様.md`
- `docs/プロジェクト再編/ポートフォリオ戦略分析_改善版.md`
- `CLAUDE.md`（本ファイル）

---

**総評**: 本プラグイン活用戦略により、Week 7-8の学習時間を43時間削減（52%）し、時給4,000-4,500円達成に最適化された効率的なDevOps学習・実装フローを実現できます。
