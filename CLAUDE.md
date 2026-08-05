# CLAUDE.md **Last Updated**: 2026-07-31

**軽量インデックス — 詳細は `.claude/CLAUDE.md` を参照**

---

## Project Overview

APIテスト + DevOps統合学習ポートフォリオ（Python 3.14 / httpx / pytest / Pydantic Settings）

**Tech Stack**: Python 3.14, httpx, pytest, Pydantic Settings, structlog, Docker, GitHub Actions

---

## Session Start

セッション開始時は **`.claude/CLAUDE.md`** を最初に読む（CRITICAL RULES 16項目 + 品質ゲート + 開発ワークフローを含む）。

**⚠️ 自動ロード禁止（.claudeignore で除外済み）**:
- `.claude/skill-report/` — 173MB（Skill監査レポート）
- `.claude/completions/`, `.claude/sessions/` — 履歴データ
- `.serena/`（`.serena/memories/` を除く）, `.memory_mcp/`, `.taskmaster/`
- `reports/`, `claudedocs/`, `node_modules/`, `.venv/`

---

## クイックコマンド

品質ゲートの統合コマンドは `.claude/CLAUDE.md` Section「品質ゲート」→「統合コマンド」を参照（単一真実源のため本ファイルには複製しない）。

---

## ドキュメント

| リソース | 内容 |
|---------|------|
| `.claude/CLAUDE.md` | CRITICAL RULES + 開発フロー（単一真実源） |
| `.claude/rules/` | 詳細ルール（必要時のみ参照） |
| `.serena/memories/` | Serenaメモリ（自動参照） |
| `~/.claude/lessons/lessons.md` | バグパターン・教訓（全プロジェクト横断） |

---

## graphify

アーキテクチャ質問前に `graphify-out/GRAPH_REPORT.md` を読む（ローカル生成物・gitignore対象のため未コミット）。未生成時およびコード変更後は `graphify update .` を実行。

<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

コード探索時は code-review-graph MCP ツールを Grep/Glob/Read より**先に**使う。

| 探索目的 | ツール |
|---------|--------|
| コードレビュー | `detect_changes` + `get_review_context` |
| 影響範囲 | `get_impact_radius` |
| 呼び出し関係 | `query_graph` (callers_of/callees_of/tests_for) |
| アーキテクチャ | `get_architecture_overview` + `list_communities` |
| シンボル検索 | `semantic_search_nodes` |

---

## Agent skills ([mattpocock Skills](https://github.com/mattpocock/skills))

### Issue tracker

GitHub Issues (yaoki-dev/api-test-devops-portfolio) で管理。`gh` CLI 経由で作成・更新。詳細は `docs/agents/issue-tracker.md` 参照。

### Triage labels

4ラベル運用: `needs-triage`（未評価）、`ready-for-execute`（エージェント実行可能）、`ready-for-human`（定義のみ・非使用）、`wontfix`（対応せず）。`needs-info` は不採用（コメントで代替）。詳細は `docs/agents/triage-labels.md` 参照。

### Domain docs

Single-context: ルートの `CONTEXT.md` + `docs/adr/`。詳細は `docs/agents/domain.md` 参照。
