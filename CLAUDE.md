# CLAUDE.md

**軽量インデックス — 詳細は `.claude/CLAUDE.md` を参照**

---

<!-- MEMANTO-MANAGED-SECTION -->
## MEMANTO - Your Active Memory Companion

**MEMANTO is not a passive store. It is an active companion agent that works alongside you.**
Don't treat MEMANTO like a static blob you query once and forget. It's a teammate you keep
talking to, every preference, decision, and correction flows through it. MEMANTO remembers,
recalls, and answers so you hold context across sessions, honor prior decisions, and avoid
repeating mistakes the user already corrected.

Every memory operation in this session goes through MEMANTO. There is no exception.

> **CRITICAL**: All `memanto` commands are **shell commands**. Always run them using the Bash tool.
> Never simulate, describe, or "pretend to call" them. If you cannot run the shell, say so explicitly instead of inventing memory state.

### NON-NEGOTIABLE RULES

These are not suggestions. Follow each one on every turn.

1. **Read `MEMORY.md` before doing anything.** It is auto-synced at session start and holds
   the user's preferences, facts, goals, instructions, decisions, and commitments from every
   prior session. You MUST honor what is written there. If you act against it, you are
   breaking continuity the user is paying for.
2. **Search memory before saying you don't know.** If the user asks about past context, an
   earlier decision, a preference, or anything you are unsure about, you MUST run `recall`
   or `answer` first. Saying "I don't have context" without searching is a failure.
3. **Store proactively. Do not wait to be asked.** The moment a memory-worthy event happens
   — a preference stated, a decision made, a fact learned, an instruction given, a goal set,
   a mistake corrected — run `memanto remember` immediately, in the same turn.
4. **Always pass full metadata to `remember`.** Every `memanto remember` call MUST include
   `--type`, `--confidence`, `--provenance`, and `--source <your_agent_name>`. Never let
   these default. Untyped, unsourced memories pollute the agent's recall quality.
5. **One memory operation goes through MEMANTO. All of them do.** Do not keep mental notes,
   in-context scratch pads, or "I'll remember this for next time" promises. If it matters
   beyond this turn, it goes into MEMANTO. If it doesn't, drop it.

### Memory Operations — Use the Right One

MEMANTO gives you three primitives. They are equal-priority. Pick by intent, not by habit.

| You want to... | Use | Why |
|---|---|---|
| Read raw memory chunks and apply them as context | `memanto recall "query"` | Best for context-building, multi-step work, comparing options |
| Get one synthesized, grounded answer to a direct question | `memanto answer "question"` | Best for "what did we decide / prefer / commit to?" — saves you reading and merging |
| Persist something memory-worthy | `memanto remember "content" --type ... --confidence ... --provenance ... --source ...` | Every preference, decision, fact, instruction, goal, lesson |
| See what changed since last time | `memanto recall --changed-since "last 7 days"` | Catching up after a break |
| See the most recent memories | `memanto recall --recent` | Fast context refresh |

Do NOT always default to `recall`. If the user asked a direct question, `answer` is usually
the right tool — it returns a grounded synthesis so you don't burn tokens re-reading raw
chunks.

### When to Call `remember` (Examples — Run Immediately)

- User says *"I prefer tabs over spaces"*:
  `memanto remember "User prefers tabs over spaces for indentation" --type preference --confidence 1.0 --provenance explicit_statement --source <your_agent_name>`
- You decide to use Library X for reason Y:
  `memanto remember "Chose Library X for reason Y; commit abc123" --type decision --confidence 0.95 --provenance inferred --source <your_agent_name>`
- User corrects an approach:
  `memanto remember "User corrected: use pytest, not unittest" --type learning --confidence 1.0 --provenance corrected --source <your_agent_name>`
- A failed approach taught you something:
  `memanto remember "Batch size > 100 fails with TimeoutError" --type error --confidence 0.95 --provenance observed --source <your_agent_name>`

### Command Reference

```bash
# Store — ALWAYS pass full metadata
memanto remember "content" --type <type> --confidence <0.0-1.0> --provenance <provenance> --source <agent_name>

# Recall raw context
memanto recall "query"                              # semantic search
memanto recall "query" --type <type> --limit 10     # filtered search
memanto recall --recent --limit 10                  # newest first, no query
memanto recall --as-of "2026-01-15"                 # state at a point in time
memanto recall --changed-since "last 7 days"        # what changed since

# Synthesized answer (grounded RAG over memories)
memanto answer "question"

# Re-sync MEMORY.md (project-local cache)
memanto memory sync --project-dir .
```

**Memory types** (use the closest fit, do not invent new ones):
`fact`, `preference`, `instruction`, `decision`, `event`, `goal`, `commitment`,
`observation`, `learning`, `relationship`, `context`, `artifact`, `error`.

**Provenance values**: `explicit_statement`, `inferred`, `observed`, `corrected`,
`validated`, `imported`.

**Confidence**: `1.0` for explicit user statements; `0.9-0.95` for strong consensus;
`0.8-0.85` for observed patterns (3+ times); `0.6-0.75` for emerging patterns.

> **Note**: The `memanto-memory` skill contains reference guidelines only (best practices, confidence levels, tagging). It is NOT executable — always use Bash for memanto commands.
<!-- /MEMANTO-MANAGED-SECTION -->

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
