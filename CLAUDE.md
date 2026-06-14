# CLAUDE.md

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

```bash
# 品質ゲート（コミット前必須）
uv run ruff check --fix . && uv run ruff format . && \
uv run mypy utils/ config/ models/ && \
uv run pytest -n auto -m "(unit or integration) and not external" --cov=utils --cov=config --cov=models --cov-report=term-missing

# テストのみ
uv run pytest -n auto -m "(unit or integration) and not external" -q

# デバッグ
uv run pytest -vv --tb=long --log-cli-level=DEBUG
```

---

## ドキュメント

| リソース | 内容 |
|---------|------|
| `.claude/CLAUDE.md` | CRITICAL RULES + 開発フロー（単一真実源） |
| `.claude/rules/` | 詳細ルール（必要時のみ参照） |
| `.serena/memories/` | Serenaメモリ（26件、自動参照） |
| `~/.claude/lessons/lessons.md` | バグパターン・教訓（全プロジェクト横断） |

---

## graphify

- アーキテクチャ質問前に `graphify-out/GRAPH_REPORT.md` を読む
- `graphify-out/wiki/index.md` がある場合は raw ファイルより優先
- コード変更後は `graphify update .` を実行

<!-- OCR:START -->
## Open Code Review Instructions

コードレビュー依頼時は `.ocr/skills/SKILL.md` を開く。
<!-- OCR:END -->

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

**Last Updated**: 2026-05-18
