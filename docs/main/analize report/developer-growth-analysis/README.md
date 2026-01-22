# Developer Growth Analysis Reports

*最終更新: 2026年01月21日*

このディレクトリには、Claude Codeの`/developer-growth-analysis`スキルによって生成された開発者成長分析レポートを格納します。

## Purpose

- **開発パターンの可視化**: 過去48時間の作業傾向を数値化
- **改善領域の特定**: データに基づく具体的な課題抽出
- **学習リソースのキュレーション**: 課題に直結した参考資料
- **進捗トラッキング**: 週次・月次での成長確認

## File Naming Convention

```
YYYY-MM-DD_growth_report.md
```

例: `2026-01-21_growth_report.md`

## Report Structure

各レポートは以下のセクションで構成されています:

| Section | Content |
|---------|---------|
| Executive Summary | 主要な発見事項の要約 |
| Work Activity Analysis | 時間帯別・技術別の作業分布 |
| Improvement Areas | 優先度付き改善領域（P1-P4） |
| Strengths Observed | 観測された強み |
| Action Items | 具体的なアクション計画 |
| Weekly Progress Tracking | 進捗メトリクスと目標 |
| Appendix | 分析手法・学習リソース索引 |

## How to Generate

Claude Codeで以下のコマンドを実行:

```
/developer-growth-analysis
```

## Recommended Usage

1. **週次レビュー**: 毎週末にレポート生成
2. **振り返り**: 過去レポートと比較して進捗確認
3. **計画調整**: Action Itemsを週次計画に組み込む

## Related Files

- `@memory:ai_collaboration_workflow`: AI協働学習フロー
- `docs/progress/daily_progress.md`: 日次進捗記録
- `docs/progress/progress_state.yaml`: 進捗状態データ

## Reports Index

| Date | Focus Areas | Key Actions |
|------|-------------|-------------|
| [2026-01-21](./2026-01-21_growth_report.md) | Git Workflow, AI Collaboration, CI/CD | git reflog練習, 指示テンプレート作成 |
