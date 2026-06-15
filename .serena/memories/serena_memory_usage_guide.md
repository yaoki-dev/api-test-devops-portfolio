# Serenaメモリ活用ガイド

*最終更新: 2025年12月27日*
*参照整合性検証済み*
*用途: 作業タイプ別のSerenaメモリ読み取り戦略、品質バイアス防止*
*アクセス頻度: 中（新しい作業タイプ開始時、エラー発生時）*

---

## 目的

このガイドは、実装・テスト・分析・要件定義・設計・DevOps・ドキュメント作成などの作業時に、**どのSerenaメモリを最低限読み取るべきか**を定義し、以下の品質バイアスを防止します：

- ❌ テスト戦略の見落とし
- ❌ アーキテクチャ原則の不一致
- ❌ コーディングルール違反
- ❌ プロジェクト特有の共通認識欠如

**設計原則**: Progressive Disclosure Pattern（段階的開示）により、トークン効率とコンテキスト完全性を両立

---

## 作業タイプ定義（7タイプ）

APItest + Docker + CI/CDプロジェクト（6週プラン）における作業を7タイプに分類：

| タイプ | 説明 | 具体例 | 6週プランでの頻度 |
|--------|------|--------|------------------|
| **Implementation** | コード実装 | utils, config, modelsの新規機能追加 | 高（毎日） |
| **Testing** | テスト作成・実行 | pytest実行、カバレッジ向上、マーカー活用 | 高（毎日） |
| **DevOps** | Docker/CI/CD作業 | Dockerfile作成、docker compose構築、GitHub Actions | 中（Week 3-4集中） |
| **Analysis** | コード・メトリクス分析 | カバレッジレポート分析、アーキテクチャレビュー | 中（週1-2回） |
| **Requirements** | 仕様・要件定義 | PRD作成、機能要件定義 | 低（フェーズ開始時） |
| **Design** | 設計・アーキテクチャ | 技術選定、パターン決定、システム設計 | 低（フェーズ開始時） |
| **Documentation** | ドキュメント作成 | README更新、学習ノート作成 | 中（週1回） |

---

## MUST/SHOULD/MAY判定基準

| レベル | 定義 | 読み取りタイミング | ファイルサイズ目安 |
|--------|------|-------------------|------------------|
| **🔴 MUST** | 品質バイアス防止に必須、常に参照すべき | 作業開始時に自動読み込み | <150行推奨 |
| **🟡 SHOULD** | 品質向上に推奨、特定条件で参照 | エラー発生時、品質改善時 | 150-300行 |
| **⚪ MAY** | 任意、特定状況で有用 | ユーザー明示的要求時のみ | >300行 |

---

## 作業タイプ × メモリマトリクス（完全版）

### Implementation（コード実装）

**🔴 MUST（作業開始時に必読）**:
- `coding_standards`（→`.claude/rules/python/coding-standards.md`参照） - コーディングルール違反防止（命名規則、型ヒント、テスト規約）
- `implementation_quality_gates` - 4ゲート品質基準確認（pytest, ruff, mypy, git）
- `project_architecture` - アーキテクチャ原則遵守（設計パターン、SOLID原則）

**🟡 SHOULD（条件付き）**:
- `project_file_structure` - ファイル配置ルール確認（新規ファイル作成時）
- `ai_collaboration_workflow` - Phase 2協働実装ガイド（学習期間Week 1-7）

**⚪ MAY（任意）**:
- `workflow_playbooks_guide` - WF-04新規APIエンドポイント実装（API作成時）
- `command_usage_guide` - ツール選択ガイド（実装コマンド選択時）

**条件付き読み込みルール**:
```
pytest失敗時 → @memory:implementation_quality_gates Section 1（Gate 1詳細）
型エラー時 → .claude/rules/python/coding-standards.md Section 2-3（型ヒント規約）
アーキテクチャ質問 → @memory:project_architecture（全体設計）
```

---

### Testing（テスト作成・実行）

**🔴 MUST（作業開始時に必読）**:
- `test_strategy_details` - テスト戦略全体像（4層アーキテクチャ、7種類マーカー）
- `fixture_quick_reference` - フィクスチャ早見表（スコープ、用途一覧）
- `implementation_quality_gates` - Gate 1 pytest要件（カバレッジ目標、合格基準）

**🟡 SHOULD（条件付き）**:
- `test_strategy_details` - カバレッジ不足時（58% → 85%戦略、CIセキュリティチェック）
- `coding_standards`（→`.claude/rules/python/coding-standards.md`参照） - テスト規約確認（フィクスチャ、モック規約）

**⚪ MAY（任意）**:
- `ai_collaboration_workflow` - Phase 2テスト作成ガイド（学習期間）

**条件付き読み込みルール**:
```
カバレッジ<目標値 → @memory:test_strategy_details Section 3（カバレッジ戦略）
CIセキュリティ設定 → @memory:test_strategy_details Section 4（CIセキュリティチェック）
pytest並列実行エラー → @memory:test_strategy_details Section 4（トラブルシューティング）
```

---

### DevOps（Docker/CI/CD）

**🔴 MUST（作業開始時に必読）**:
- `project_architecture` - Container Architecture（Docker設定）
- `project_architecture` - Multi-stage buildパターン（設計パターン）

**🟡 SHOULD（条件付き）**:
- `project_file_structure` - Docker関連ファイル配置（ディレクトリ構造）
- `implementation_quality_gates` - 品質検証基準（Docker imageスキャン）
- `workflow_playbooks_guide` - WF-03 DevOps戦略、WF-05コンテナ化

**⚪ MAY（任意）**:
- `command_usage_guide` - Docker/CI/CDコマンド選択
- `ai_collaboration_workflow` - Phase 2 Docker学習ガイド

**条件付き読み込みルール**:
```
Docker構築エラー → @memory:project_architecture（Dockerfileパターン確認）
CI/CD設計時 → @memory:workflow_playbooks_guide Section 3（WF-03, WF-05）
セキュリティスキャン → @memory:test_strategy_details Section 4（CIセキュリティチェック）
```

---

### Analysis（コード・メトリクス分析）

**🔴 MUST**: なし（分析は条件付きで開始）

**🟡 SHOULD（条件付き）**:
- `project_file_structure` - プロジェクト構造理解（全体把握）
- `project_architecture` - アーキテクチャメトリクス基準（SOLID準拠率85%）
- `test_strategy_details` - テストカバレッジ基準（目標85%）
- `implementation_quality_gates` - 品質ゲート基準（4ゲート詳細）

**⚪ MAY（任意）**:
- `test_strategy_details` - カバレッジ詳細分析
- `coding_standards`（→`.claude/rules/python/coding-standards.md`参照） - コード品質基準

**条件付き読み込みルール**:
```
アーキテクチャレビュー時 → @memory:project_architecture
カバレッジ分析時 → @memory:test_strategy_details Section 3（カバレッジ戦略）
品質メトリクス確認時 → @memory:implementation_quality_gates
```

---

### Requirements / Design

**🔴 MUST**: なし（要件定義・設計は条件付き）

**🟡 SHOULD（条件付き）**:
- `workflow_playbooks_guide` - WF-01曖昧アイデア具体化、WF-02アーキテクチャ設計
- `ai_collaboration_workflow` - Phase 1概念理解ガイド
- `project_architecture` - 既存設計パターン理解（Design時）

**⚪ MAY（任意）**:
- `project_file_structure` - プロジェクト構造参考
- `command_usage_guide` - ブレインストーミングコマンド

**条件付き読み込みルール**:
```
要件定義開始時 → @memory:workflow_playbooks_guide Section 2（WF-01）
アーキテクチャ設計時 → @memory:workflow_playbooks_guide Section 2（WF-02）
新技術学習時 → @memory:ai_collaboration_workflow Phase 1
```

---

### Documentation

**🔴 MUST**: なし（ドキュメント作成は条件付き）

**🟡 SHOULD（条件付き）**:
- `project_file_structure` - ドキュメント配置ルール
- `coding_standards`（→`.claude/rules/python/coding-standards.md`参照） - ドキュメント規約（最終更新日記載等）

**⚪ MAY（任意）**:
- `workflow_playbooks_guide` - WF-13 API文書化
- `command_usage_guide` - ドキュメント更新コマンド

**条件付き読み込みルール**:
```
README更新時 → @memory:project_file_structure
API文書作成時 → @memory:workflow_playbooks_guide Section 7（WF-13）
```

---

## Progressive Disclosure Pattern（段階的開示戦略）

### 3段階読み込みフロー

```
【Phase 1: MUST自動読み込み】
作業開始時に必須メモリを自動ロード
→ 品質バイアス防止の基礎コンテキスト確立
→ トークン: 基本1,000トークン（必須情報のみ）

       ↓ 作業開始

【Phase 2: SHOULD条件付き読み込み】
エラー・品質ギャップ検出時のみ追加ロード
→ 問題解決に必要な詳細情報のみ取得
→ トークン: 追加2,000-4,000トークン（条件次第）

       ↓ 特定状況・明示的要求

【Phase 3: MAY オンデマンド読み込み】
ユーザー明示的要求時のみロード
→ 深堀調査・学習目的の詳細情報
→ トークン: 追加4,000-8,000トークン（ケース依存）
```

### トークン効率化効果

**従来方式（全メモリ一括読み込み）**:
- 13メモリ × 平均1,000トークン = 13,000トークン
- 不要情報率: 70-80%（大半が未使用）

**Progressive Disclosure方式**:
- Phase 1（MUST）: 1,000トークン（80%のセッションで十分）
- Phase 2（SHOULD）: +2,000トークン（20%のセッション）
- Phase 3（MAY）: +4,000トークン（5%のセッション）
- 平均トークン使用: `1,000 × 0.8 + 3,000 × 0.2 + 7,000 × 0.05` = **1,750トークン**
- **削減効果**: 86.5%削減（13,000 → 1,750）

---

## 条件付き読み込みルール（完全版）

| トリガー条件 | 追加読み込みメモリ | セクション | 理由 |
|-------------|------------------|-----------|------|
| **pytest失敗** | implementation_quality_gates | Section 1 | Gate 1詳細確認（カバレッジ、マーカー） |
| **カバレッジ不足** | test_strategy_details | Section 3 | 58% → 85%戦略（カバレッジ戦略） |
| **型エラー** | coding-standards.md（直接ファイル参照） | Section 2-3 | 型ヒント規約、PascalCase/snake_case |
| **Docker構築エラー** | project_architecture | Dockerfileパターン | Multi-stage build、Layer caching |
| **セキュリティ警告** | test_strategy_details | Section 4 | CIセキュリティチェック（bandit/gitleaks/Dependabot） |
| **品質ゲート不合格** | implementation_quality_gates | 該当ゲート | Gate 2（ruff）、Gate 3（mypy）詳細 |
| **並列テストエラー** | test_strategy_details | Section 4 | トラブルシューティング |
| **CI/CD設計** | workflow_playbooks_guide | Section 3 | WF-03 DevOps戦略、WF-08本番障害 |
| **要件定義開始** | workflow_playbooks_guide | Section 2 | WF-01曖昧アイデア具体化 |
| **アーキテクチャ設計** | workflow_playbooks_guide | Section 2 | WF-02システム設計 |

---

## 使用例

### 例1: 新規API実装タスク（Implementation）

```
【作業内容】
JSONPlaceholder APIのPOSTエンドポイント実装

【Phase 1: MUST自動読み込み】
作業開始時に以下を並列読み込み（1.0秒、1,000トークン）:
→ .claude/rules/python/coding-standards.md（命名規則、型ヒント確認）
→ @memory:implementation_quality_gates（4ゲート基準確認）
→ @memory:project_architecture（エラーハンドリングパターン確認）

【実装中のイベント】
pytest実行 → 5テスト失敗検出

【Phase 2: SHOULD条件付き読み込み】
トリガー「pytest失敗」発動（0.5秒、2,000トークン）:
→ @memory:implementation_quality_gates Section 1
  - Gate 1詳細: カバレッジ目標（Week別、最終版.md準拠）
  - 失敗原因: async testのfixture scope誤り

【問題解決後】
カバレッジ45% < 目標60% 検出

【Phase 2: SHOULD条件付き読み込み（2回目）】
トリガー「カバレッジ不足」発動（0.5秒、3,000トークン）:
→ @memory:test_strategy_details Section 3（カバレッジ戦略）
  - Week別目標: 6週プラン（Week 1-6）に準拠
  - 戦略: CRUDメソッドテスト追加

【累積トークン】: 1,000 + 2,000 + 3,000 = 6,000トークン
【全メモリ一括読み込みとの比較】: 13,000メモリ → 54%削減
```

---

### 例2: Docker Multi-stage build作成（DevOps）

```
【作業内容】
本番用Dockerfile作成（4-stage構成）

【Phase 1: MUST自動読み込み】
作業開始時（0.8秒、1,000トークン）:
→ @memory:project_architecture Container Architecture
→ @memory:project_architecture（Multi-stage buildパターン）

【実装中のイベント】
Docker build失敗: Layer cache無効化エラー

【Phase 2: SHOULD条件付き読み込み】
トリガー「Docker構築エラー」発動（0.5秒、2,500トークン）:
→ @memory:project_architecture（Dockerfileパターン詳細）
  - Layer caching戦略
  - COPY --from活用法

【次のイベント】
セキュリティスキャンでCritical脆弱性検出

【Phase 2: SHOULD条件付き読み込み（2回目）】
トリガー「セキュリティ警告」発動（0.5秒、3,500トークン）:
→ @memory:test_strategy_details Section 4（CIセキュリティチェック）
  - bandit/gitleaks/Trivy設定
  - Dependabot依存関係チェック

【累積トークン】: 1,000 + 2,500 + 3,500 = 7,000トークン
【削減効果】: 13,000トークン → 46%削減
```

---

### 例3: カバレッジ60%達成タスク（Testing）

```
【作業内容】
テストカバレッジ58% → 60%達成

【Phase 1: MUST自動読み込み】
作業開始時（0.8秒、1,000トークン）:
→ @memory:test_strategy_details（全体戦略、4層アーキテクチャ）
→ @memory:fixture_quick_reference（フィクスチャ早見表）
→ @memory:implementation_quality_gates（Gate 1要件）

【Phase 2: SHOULD条件付き読み込み】
トリガー「カバレッジ分析開始」自動発動（0.5秒、4,000トークン）:
→ @memory:test_strategy_details Section 3（カバレッジ戦略）
  - 現状58.56%分析（utils 19.30%, models 0%）
  - Week別目標60%達成戦略
  - 優先順位: utils/api_client.py CRUD追加

【累積トークン】: 1,000 + 4,000 = 5,000トークン
【削減効果】: 13,000トークン → 62%削減
```

---

## トークン最適化戦略

### 1. @memory:記法の活用（推奨）

```python
# ❌ 非効率: Read tool直接呼び出し
Read(".claude/rules/python/coding-standards.md", limit=100)
# → 2,000トークン消費、最適化なし

# ✅ 効率的: @memory記法
@memory:implementation_quality_gates
# → 1,000トークン消費（50%削減）、Serena自動最適化
```

### 2. 並列バッチ読み込み

```python
# ❌ 逐次読み込み（4.5秒）
Read(".claude/rules/python/coding-standards.md")       # 1.5秒
Read("implementation_quality_gates.md")  # 1.5秒
Read("project_architecture.md")   # 1.5秒

# ✅ 並列読み込み（1.5秒、66%時間削減）
Read(".claude/rules/python/coding-standards.md") | Read("implementation_quality_gates.md") | Read("project_architecture.md")
```

### 3. 部分読み込み（大ファイル対策）

```python
# test_strategy_details.md（全体300行）の部分読み込み
Read("test_strategy_details.md", offset=0, limit=50)    # Section 1-2のみ
Read("test_strategy_details.md", offset=100, limit=50)  # Section 5のみ

# トークン削減: 6,000 → 1,000（83%削減）
```

### 4. セッションキャッシング

```python
# 同一セッション内での再読み込み回避
# 1回目: @memory:implementation_quality_gates（1,000トークン）
# 2回目: キャッシュヒット（0トークン）
```

---

## 保守ガイドライン

### メモリ追加時のチェックリスト

- [ ] 既存7作業タイプのどれに該当するか判定
- [ ] MUST/SHOULD/MAY基準に基づき分類
- [ ] 条件付き読み込みルール追加の要否判断
- [ ] マトリクステーブル更新（このファイル）
- [ ] CLAUDE.md登録済みメモリ一覧更新

### メモリ更新時のチェックリスト

- [ ] ファイルサイズ変更確認（150行超 → offset/limit推奨に変更）
- [ ] MUST/SHOULD判定の再評価
- [ ] 条件付き読み込みルールの妥当性確認
- [ ] 最終更新日付更新

### 新しい作業タイプ追加時

1. **作業タイプ定義**: 説明、具体例、頻度を明確化
2. **MUST/SHOULD/MAY判定**: 13メモリ全てを評価
3. **条件付きルール定義**: エラー・状況ごとのトリガー設定
4. **使用例作成**: 実際のワークフロー例を1-2件作成
5. **CLAUDE.md更新**: クイックリファレンステーブルに行追加

---

## 参照

- **CLAUDE.md**: クイックリファレンス、登録済みメモリ一覧
- **@memory:project_file_structure**: Serenaメモリの物理配置
- **@memory:command_usage_guide**: コマンド選択ガイド
- **@memory:workflow_playbooks_guide**: ワークフロー実行手順
