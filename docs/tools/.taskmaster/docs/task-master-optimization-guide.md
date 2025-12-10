# Task Master AI MCP最適化ガイド

*最終更新: 2025年10月07日*

## 🎯 最適化の概要

### 実施内容
- **削除ツール数**: 12個（43個 → 31個）
- **削減トークン**: 約10k tokens（33k → 23k）
- **削減率**: 30%
- **残存コンテキスト使用率**: 11.5%（16.5% → 11.5%）

### 削減対象ツール

**❌ タグシステム（7ツール、約4.8k tokens）**
```
list_tags, add_tag, delete_tag, use_tag, rename_tag, copy_tag, move_task
```

**❌ その他低頻度（5ツール、約3.8k tokens）**
```
remove_subtask, clear_subtasks, update, rules, response-language, research
```

---

## 📋 有効化ツール一覧（31個）

### コアワークフロー（10ツール）
```
get_tasks, get_task, add_task, update_task, set_task_status,
next_task, generate, add_subtask, update_subtask, remove_task
```

### タスク分解・スコープ調整（6ツール）
```
expand_task, expand_all, scope_up_task, scope_down_task,
analyze_project_complexity, complexity_report
```

### 依存関係管理（4ツール）
```
add_dependency, remove_dependency, validate_dependencies, fix_dependencies
```

### 初期化・PRD（3ツール）
```
initialize_project, parse_prd, models
```

### Autopilot（8ツール）
```
autopilot_start, autopilot_resume, autopilot_next, autopilot_status,
autopilot_complete_phase, autopilot_commit, autopilot_finalize, autopilot_abort
```

---

## 🔧 設定ファイル

### `.mcp.json`（最適化版）

```json
{
  "$schema": "https://modelcontextprotocol.io/schema/mcp-config.schema.json",
  "mcpServers": {
    "task-master-ai": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "task-master-ai"],
      "env": {
        "TASK_MASTER_TOOLS": "get_tasks,get_task,add_task,update_task,set_task_status,next_task,generate,add_subtask,update_subtask,remove_task,expand_task,expand_all,scope_up_task,scope_down_task,analyze_project_complexity,add_dependency,remove_dependency,validate_dependencies,fix_dependencies,complexity_report,initialize_project,parse_prd,models,autopilot_start,autopilot_resume,autopilot_next,autopilot_status,autopilot_complete_phase,autopilot_commit,autopilot_finalize,autopilot_abort"
      },
      "metadata": {
        "description": "Task management and workflow automation (optimized - 31 tools)",
        "version": "latest",
        "source": "npm",
        "optimization": "Custom tool selection - 30% token reduction"
      }
    }
  }
}
```

---

## 🛠️ 削除機能の代替手段

### タグ管理（CLI代替）

```bash
# タグ一覧表示
npx task-master-ai list-tags

# タグ追加
npx task-master-ai add-tag feature-auth

# タグ削除
npx task-master-ai delete-tag old-feature

# タグでタスク表示
npx task-master-ai get-tasks --tag feature-auth

# タスクへのタグ割り当て（tasks.json直接編集）
# {
#   "id": 5,
#   "tags": ["feature-auth", "security"]
# }
```

### その他低頻度機能（代替方法）

**remove_subtask** → `remove_task`で代替可能
```bash
# サブタスク削除（タスクIDで指定）
npx task-master-ai remove-task 5.2
```

**clear_subtasks** → 手動削除
```bash
# 親タスク5の全サブタスク削除
npx task-master-ai remove-task 5.1,5.2,5.3
```

**update** → `update_task`で代替可能
```bash
# タスク更新
npx task-master-ai update-task --id 5 --prompt "新しい要件追加"
```

**rules, response-language** → 初回設定後は不要
```bash
# 初回のみCLIで設定
npx task-master-ai rules add cursor
npx task-master-ai response-language 日本語
```

---

## ✅ 動作検証手順

### 1. Claude Code再起動
```bash
# Claude Codeを完全終了
# プロジェクトを再度開く
```

### 2. Task Master AI接続確認
```
# Claude Codeで実行
使用可能なツールを確認: task-master-aiツールが31個表示されること
```

### 3. 基本機能テスト
```
# タスク一覧取得テスト
mcp__task-master-ai__get_tasks

# タスク追加テスト
mcp__task-master-ai__add_task
  prompt: "テスト用タスク"
  projectRoot: "/Users/yuta/Yuta/python/api-test-devops-portfolio"
```

### 4. トークン消費確認
```
# Claude Codeのトークン使用状況を確認
# 期待値: Task Master AI = 23k tokens前後（30%削減）
```

---

## 📊 期待効果

| 指標 | 最適化前 | 最適化後 | 改善 |
|------|---------|---------|------|
| ツール数 | 43個 | 31個 | -12個（-28%） |
| トークン消費 | 33k | 23k | -10k（-30%） |
| コンテキスト使用率 | 16.5% | 11.5% | -5%pt |
| 利用可能トークン | 167k | 177k | +10k |

**実用性への影響**:
- ✅ 日常ワークフロー: 100%維持
- ✅ タスク分解・スコープ: 100%維持
- ✅ 依存関係管理: 100%維持
- ✅ 初期化・PRD: 100%維持
- ✅ Autopilot: 100%維持
- ⚠️ タグ管理: CLI代替必要
- ⚠️ 一部低頻度機能: CLI代替可能

---

## 🔄 ロールバック手順

最適化で問題が発生した場合の復元手順：

### 1. バックアップから復元
```bash
cd /Users/yuta/Yuta/python/api-test-devops-portfolio
cp .mcp.json.backup .mcp.json
```

### 2. Claude Code再起動
```bash
# Claude Codeを再起動してMCP設定を再読み込み
```

### 3. 動作確認
```
# タスク一覧取得で全ツール復帰確認
mcp__task-master-ai__get_tasks
```

---

## 📅 定期レビュー

### 3ヶ月ごとのチェック項目

1. **使用頻度分析**
   - 各ツールの実際の呼び出し回数確認
   - 低頻度ツールの削減検討

2. **トークン消費モニタリング**
   - Claude Codeセッション平均トークン使用率
   - Task Master AI以外のMCPとのバランス

3. **新機能評価**
   - Task Master AIアップデートの確認
   - 新ツールの追加検討

4. **CLI使用頻度**
   - タグ管理CLI使用頻度
   - MCP復帰の必要性判断

---

## 🆘 トラブルシューティング

### Q1: ツールが読み込まれない
```bash
# 環境変数確認
echo $TASK_MASTER_TOOLS

# MCPサーバー再起動
# Claude Code再起動
```

### Q2: 一部ツールのみ有効化したい
```json
{
  "env": {
    "TASK_MASTER_TOOLS": "get_tasks,add_task,update_task"
  }
}
```

### Q3: 全ツール復帰したい
```json
{
  "env": {
    "TASK_MASTER_TOOLS": "all"
  }
}
```

### Q4: プリセット使用（標準15ツール）
```json
{
  "env": {
    "TASK_MASTER_TOOLS": "standard"
  }
}
```

利用可能なプリセット:
- `all`: 全43ツール（デフォルト、約33k tokens）
- `standard`: 標準15ツール（約12-15k tokens）
- `core`または`lean`: 最小7ツール（約6-8k tokens）

---

## 📚 参考資料

- [GitHub Issue #1280](https://github.com/eyaltoledano/claude-task-master/issues/1280): MCP token consumption reduction
- [Task Master Documentation](https://docs.task-master.dev/): 公式ドキュメント
- [Tool Analysis](../tools/task-master-tool-analysis.md): 詳細分析レポート（存在する場合）

---

## ✨ 次のステップ

1. ✅ 設定適用完了（`.mcp.json`更新済み）
2. ⏳ Claude Code再起動 → 動作検証
3. ⏳ 1週間使用 → 使用感評価
4. ⏳ 必要に応じてツール追加/削減調整

---

## 📝 変更履歴

### 2025-10-07
- 初回最適化実施
- 43ツール → 31ツール（30%削減）
- タグシステム・低頻度機能を削除
- CLI代替手段を文書化
