# PreCompact Hook 分析結果

*最終更新: 2026年01月29日*

## セッション概要

PreCompact hookの公式仕様分析とベストプラクティス検討を実施。

## 主要な発見

### 1. PreCompact hookの技術的制約

- **type: "command"のみ対応**: bashコマンド実行のみ可能
- **type: "prompt"非対応**: LLM評価はStop/SubagentStopイベントのみ
- **MCPサーバー直接呼び出し不可**: Claude Code経由でないとアクセスできない

### 2. 既存ツールとの重複分析

| 要望機能 | 既存ツール | 対応状況 |
|---------|-----------|---------|
| handoff_summary | `/sc:save --summarize` | 対応済み |
| memory_registration | Serena `write_memory` | 対応済み |
| todo_update | Claude内部ツール | 外部から不可 |

### 3. 結論

**PreCompact hook作成は不要**

理由:
1. `/sc:save`スキルが既に同等機能を提供
2. bashからMCP/スキルを呼び出す技術的手段がない
3. 新規スクリプト作成は車輪の再発明

### 4. 推奨ワークフロー

```
長時間セッション → 定期的に /sc:save
/compact実行前 → /sc:save を先に実行
セッション終了時 → /sc:save --type all
```

## 参考資料

- 公式ドキュメント: https://code.claude.com/docs/en/hooks
- 詳細レポート: claudedocs/research_precompact_hook_analysis_20260129.md

## 学習ポイント

1. hook制約（command vs prompt）の理解
2. 既存ツール活用優先の設計判断
3. DRY原則の適用
