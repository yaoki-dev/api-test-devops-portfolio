# Task Master AI ツール使用分析

*最終更新: 2025年10月07日*

## 使用状況サマリー

- **総ツール数**: 43個
- **現在トークン消費**: 約33k tokens（コンテキストの16.5%）
- **使用頻度**: ほぼ毎日
- **主要用途**: タスク管理、PRD→タスク生成、進捗追跡

---

## ツール分類（優先度別）

### 🟢 Tier 1: コアワークフロー（必須 - 10ツール、約7.5k tokens）

**基本CRUD**
- `get_tasks` (723 tokens): タスク一覧取得
- `get_task` (703 tokens): タスク詳細取得
- `add_task` (851 tokens): 新規タスク追加
- `update_task` (790 tokens): タスク更新
- `set_task_status` (822 tokens): ステータス変更

**ワークフロー支援**
- `next_task` (690 tokens): 次のタスク取得
- `generate` (685 tokens): タスクファイル生成
- `add_subtask` (863 tokens): サブタスク追加
- `update_subtask` (795 tokens): サブタスク更新
- `remove_task` (750 tokens): タスク削除

**合計**: 7,672 tokens

---

### 🟡 Tier 2: 高度な管理機能（重要 - 10ツール、約7.4k tokens）

**タスク分解・スコープ調整**
- `expand_task` (787 tokens): タスク分解
- `expand_all` (787 tokens): 全タスク分解
- `scope_up_task` (784 tokens): スコープ拡大
- `scope_down_task` (784 tokens): スコープ縮小
- `analyze_project_complexity` (892 tokens): 複雑度分析

**依存関係管理**
- `add_dependency` (720 tokens): 依存関係追加
- `remove_dependency` (715 tokens): 依存関係削除
- `validate_dependencies` (669 tokens): 依存関係検証
- `fix_dependencies` (654 tokens): 依存関係自動修正

**その他**
- `complexity_report` (651 tokens): 複雑度レポート

**合計**: 7,443 tokens

---

### 🟠 Tier 3: 初期化・セットアップ（条件付 - 3ツール、約2.6k tokens）

**プロジェクト初期化**
- `initialize_project` (976 tokens): プロジェクト初期化
- `parse_prd` (959 tokens): PRD→タスク生成
- `models` (1,000 tokens): モデル設定

**使用頻度**: 月数回（新規プロジェクト時）
**判定**: ⚠️ **条件付保持**（CLIで代替可能だが利便性高い）

**合計**: 2,935 tokens

---

### 🔴 Tier 4: 低頻度機能（削除候補 - 20ツール、約14.1k tokens）

**タグシステム（7ツール、約4.8k tokens）**
- `list_tags` (671 tokens)
- `add_tag` (773 tokens)
- `delete_tag` (692 tokens)
- `use_tag` (668 tokens)
- `rename_tag` (691 tokens)
- `copy_tag` (724 tokens)
- `move_task`のタグ関連機能 (878 tokens)

**Autopilotワークフロー（8ツール、約5.5k tokens）**
- `autopilot_start` (761 tokens)
- `autopilot_resume` (630 tokens)
- `autopilot_next` (639 tokens)
- `autopilot_status` (622 tokens)
- `autopilot_complete_phase` (785 tokens)
- `autopilot_commit` (704 tokens)
- `autopilot_finalize` (631 tokens)
- `autopilot_abort` (636 tokens)

**その他低頻度（5ツール、約3.8k tokens）**
- `remove_subtask` (752 tokens): 代替: remove_task
- `clear_subtasks` (712 tokens): 低頻度
- `update` (791 tokens): update_taskで代替可能
- `rules` (846 tokens): 設定ファイルで管理
- `response-language` (686 tokens): 初期設定のみ
- `research` (916 tokens): 未使用

**合計**: 14,138 tokens

---

## 最適化シナリオ

### シナリオA: バランス型（推奨）
**保持**: Tier 1 + Tier 2 + Tier 3 = 20ツール
**削減**: Tier 4 = 20ツール削除
**トークン削減**: 14.1k → **43%削減**
**残存トークン**: 18.9k（コンテキストの9.5%）

### シナリオB: 積極削減型
**保持**: Tier 1 + Tier 2 = 20ツール
**削減**: Tier 3 + Tier 4 = 23ツール削除
**トークン削減**: 16.7k → **51%削減**
**残存トークン**: 16.3k（コンテキストの8.2%）
**トレードオフ**: 初期化はCLI必須

### シナリオC: 最小構成型
**保持**: Tier 1のみ = 10ツール
**削減**: Tier 2-4 = 33ツール削除
**トークン削減**: 25.4k → **77%削減**
**残存トークン**: 7.7k（コンテキストの3.8%）
**トレードオフ**: タスク分解・依存関係管理はCLI必須

---

## 推奨構成: シナリオA（バランス型）

### 有効化ツールリスト（20ツール）

```json
[
  "get_tasks",
  "get_task",
  "add_task",
  "update_task",
  "set_task_status",
  "next_task",
  "generate",
  "add_subtask",
  "update_subtask",
  "remove_task",
  "expand_task",
  "expand_all",
  "scope_up_task",
  "scope_down_task",
  "analyze_project_complexity",
  "add_dependency",
  "remove_dependency",
  "validate_dependencies",
  "fix_dependencies",
  "complexity_report",
  "initialize_project",
  "parse_prd",
  "models"
]
```

### 期待効果
- ✅ 日常ワークフロー維持
- ✅ タスク分解・スコープ調整可能
- ✅ 依存関係管理可能
- ✅ 初期化機能保持（CLI不要）
- ⚠️ タグ機能は手動管理
- ⚠️ Autopilotは使用不可

---

## CLI代替コマンド（削除機能の補完）

### タグ管理
```bash
# タグ追加（tasks.jsonを直接編集）
npx task-master-ai add-tag feature-auth

# タグ一覧
npx task-master-ai list-tags
```

### Autopilot（使用予定がある場合）
```bash
# Autopilot開始
npx task-master-ai autopilot start --task-id 5

# ステータス確認
npx task-master-ai autopilot status
```

---

## 運用ガイドライン

### 定期レビュー（3ヶ月ごと）
1. 実際の使用頻度を確認
2. Tier 2-3の必要性を再評価
3. 新機能の追加を検討

### モニタリング指標
- Claude Codeセッションのトークン使用率
- Task Master AI機能の呼び出し頻度
- CLI使用頻度（削除機能の代替）

---

## 次のステップ

1. ✅ バックアップ: 現在の`.mcp.json`を保存
2. ⏳ 設定更新: 最適化版`.mcp.json`適用
3. ⏳ 動作検証: Task Master AI機能テスト
4. ⏳ トークン測定: 削減効果の定量評価
