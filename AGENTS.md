# Project Instructions

## Project Defaults

- このリポジトリは Python 3.14、`uv`、`pytest`、`ruff`、`mypy` を前提にする。
- 実装前に既存コードと既存テストを読む。まず既存パターンに合わせ、必要最小限の差分で直す。
- 変数名、関数名、クラス構造、例外設計、テストスタイルは既存実装を優先して合わせる。

## Python Rules

- 本番コードでは型ヒントを維持し、例外処理では原因連鎖を壊さない。
- 非同期コードでは既存の並行処理パターンとキャンセル挙動を崩さない。
- セキュリティ上危険な実装は避ける。例: `eval()`, `exec()`, `shell=True`, 安全でないデシリアライズ、文字列連結によるクエリ生成。

## Quality Gates

- 実装後は、変更範囲に応じて `ruff`、`mypy`、`pytest` を通す。
- 基本コマンド:
- `uv run ruff check --fix .`
- `uv run ruff format .`
- `uv run mypy utils/ config/ models/ tests/conftest.py`
- `uv run pytest -n auto -m "(unit or integration) and not external"`
- コミットは、品質ゲート通過後に実施する。
- コミット用の標準ワークフローまたは専用自動化がある場合は、それを必須手順として扱う。
- コミットメッセージは Conventional Commits の意図を維持する。
- Markdown を変更したら、必要に応じて `npm run lint:md` と `npm run lint:text` を実行する。

## Testing Strategy

- まず `unit` と `integration` を優先し、`external` 依存テストは通常の変更で無理に回さない。
- 失敗したテストを無効化して通さない。原因を特定してから直す。
- カバレッジや品質ゲートに影響する変更では、変更対象に近いテストから順に確認し、必要なら全体検証へ広げる。

## High-Risk Files

- 次の変更は慎重に扱い、影響範囲を明示する。
- `pyproject.toml`
- `*.yml`
- `*.yaml`
- `.env*`
- `config/`
- CI/CD 設定
- 共有テスト基盤

<!-- preserve-on-compact: CRITICAL RULES -->
<!-- IMPORTANT: These rules override all other instructions -->
## 🔴 CRITICAL RULES (MUST FOLLOW - 16項目)

**YOU MUST** follow these rules. Violations are NOT acceptable.

1. **ALWAYS** respond in `Japanese` for all outputs, including skill usage
2. **ALWAYS** create a task list using `todowrite` before starting any work (exception: obvious single-step trivial tasks; RULES.md Workflow Rules "TodoWrite (3+ tasks)" qualifier)
3. **ALWAYS** use the AskUserQuestion tool to propose 2-3 alternative approaches and wait for user confirmation before executing any major tasks or structural changes (exception: explicit slash command invocation (e.g., `/commit`, `/push-pr`), subagent execution context — parent agent owns the AskUserQuestion call, user-directed single-line trivial fix)
4. **NEVER** use `git commit` → **ALWAYS** use `Skill(commit)`
5. **NEVER** use `gh pr create` → **ALWAYS** use `Skill(push-pr)`
6. **NEVER** use `gh issue create` → **ALWAYS** use `Skill(create-issue)`
7. **ALWAYS** pass quality gates before commit → @memory:implementation_quality_gates
8. **NEVER** push to protected branches (main/develop) directly
9. **ALWAYS** invoke skills via Skill(skill-name) notation when user requests
10. **ALWAYS** follow development workflow order → Section「🔄 開発ワークフロー」
11. **ALWAYS** after completing all tasks in `todowrite`, Use Skill tool to run `Skill(fable:fable-judge)` → then `Skill(reflexion:reflect)`
12. **ALWAYS** when using Fable model → invoke `Skill(efficient-fable)`
13. **ALWAYS** verify file content with Read/Grep tool BEFORE making any claim about line numbers, file structure, or code content
14. **ALWAYS** enforce worktree boundary: セッション開始時に `git rev-parse --show-toplevel` でWORKTREE_ROOTを確認し、WORKTREE_ROOT外ファイルの自律的編集を禁止する（`~/.claude/tasks/` は例外）
    → 詳細手続き（worktree list検証、compact後再検証、mismatch報告等）: `.claude/rules/workflow/RULES.md` Section「Category: Worktree Boundary Enforcement」
15. **ALWAYS** manage `~/.claude/lessons/lessons.md`:
    a) セッション開始時に読み込み、現プロジェクトのlessonsを確認（ENOENT: 無視して続行）
    b) ユーザーからの修正フィードバック時に即時追記（Edit tool使用、Write禁止。フォーマット: `## [YYYY-MM-DD] [project-name] - Category`）
    → 詳細手続き（エラーハンドリング、closed-list確認、ソース制約等）: `.claude/rules/workflow/RULES.md` Section「Category: Lessons Management」
16. **ALWAYS** fix bugs autonomously (no hand-holding) when scope is within:
    - ⛔ 例外（本ルール不適用）: ユーザーの依頼の**主目的**が判断・評価・分析・レビューの場合。修正指示を明示的に含む依頼（例:「分析して修正して」）は主目的が実装であり対象外。該当判定はユーザーの文言に基づき、エージェントの自己申告で拡大解釈しない
      → `.claude/rules/workflow/RULES.md` Section「Category: Analysis-Only Request Boundary」
    - ❌ Absolutely prohibited (no autonomous modification): `pyproject.toml`, `*.yml`/`*.yaml`/`.env*`, `config/`, `tests/conftest.py`, `tests/**/conftest.py`, `tests/**/__init__.py`, `tests/**/helpers.py`, `utils/__init__.py`, `utils/logger.py`, `utils/sentry_init.py`, git ops / infra config
    - ⚠️ Limited autonomous fix (spec-changing modifications → confirmation required; non-functional modifications: autonomous OK): `scripts/*.py`, `models/responses.py`, `utils/github_client.py`, `tests/test_smoke.py`, `utils/*.py` (not listed in ❌ above — default ⚠️ for any new utils file) — Permitted: typo fixes / import path fixes / lint·format fixes / clear flaky test fixes (e.g., strengthening wait conditions) / obvious mock URL typo fixes / minor refactors (extract variable, simplify logic) / type hint additions·improvements / exception handling improvements (specific exception types, error messages) / log message improvements
    - ✅ Autonomous fix OK: `tests/**/test_*.py` and `tests/test_*.py` (except `tests/test_smoke.py` — governed by ⚠️ above), `*.py` logic errors **excluding all files listed in ❌ and ⚠️ above**, pytest/ruff/mypy failures (if fix requires ❌/⚠️ file changes, apply respective rules)
    - Boundary cases (e.g., adding pyproject.toml dependencies) → apply Rule 3 (AskUserQuestion)
    - さらに: 変更ファイル数 3 以上 / 不可逆操作 / 既存外部契約 (公開API / 環境変数 / CI設定) 変更 を伴う場合は ⚠️ 同等扱い (= Rule 3 適用)
      - 除外条件: ドキュメント (`*.md` / `docs/` / `claudedocs/`) ・バイナリ資産 (画像 / PDF) のみの更新で、 コードロジック (`*.py` / `config/` / `*.yml` / `*.toml`) 未変更の場合

## プロジェクト概要

APIテスト + DevOps統合学習ポートフォリオ。時給4000-4500円レベルの技術力を証明するために設計されています。

**技術スタック**:

- Python 3.14
- httpx (Sync + Async HTTP client)
- pytest（CI計測対象: unit, integration。カバレッジ下限は `pyproject.toml` の `--cov-fail-under`）
- Pydantic Settings (型安全な設定管理)
- structlog (構造化ログ)
- Docker (Multi-stage builds)
- docker compose (4環境: development/testing/staging/production)
- GitHub Actions (CI/CD自動化)

<!-- preserve-on-compact: Serena Memory System -->
## 📖 Serenaメモリシステムの使い方

**メモリ参照**: メモリ名（例: `implementation_quality_gates`）は Serena の `read_memory()`（または相当ツール）で明示的に参照する

**主要メモリ**:`implementation_quality_gates`, `test_strategy_details`

**物理ファイル位置**: `.serena/memories/` 配下


### リンター・フォーマッター

**詳細**: `.claude/rules/python/coding-standards.md` Section 10「自動検証コマンド」

```bash
# 基本チェック（開発時）
uv run ruff check --fix .           # スタイル + 自動修正
uv run ruff format .                # フォーマット適用

# セキュリティ（手動実行・CI未統合。CIでは ruff S-rules + gitleaks が代替）
uv run bandit -r utils/ config/ models/
uv run safety scan
```

### pre-commit（軽量版）

**セットアップ**: `uv run pre-commit install`
**戦略**: コミット時はruffのみ（3秒以内）、重いチェックはCI/CDで実行
**詳細**: `.claude/rules/python/coding-standards.md` Section 10「自動検証コマンド」

### Markdown品質チェック

**ツール**: markdownlint + textlint + markdown-link-check
**設定**: `.markdownlint.json`, `.textlintrc`, `.textlintignore`
**CI**: PRごとに`md-quality`ジョブで自動実行、週次で`weekly-link-check`

```bash
npm run lint:md && npm run lint:text   # ローカル実行
```

## アーキテクチャ概要

**詳細**: memory `~/projects/python/api-test-devops-portfolio/.serena/memories/project_architecture.md`

## 設定管理

**詳細**: `~/projects/python/api-test-devops-portfolio/.claude/rules/python/coding-standards.md`

Pydantic Settingsのネスト記法（`__`区切り）を使用:

```bash
ENVIRONMENT=development
API__BASE_URL=https://jsonplaceholder.typicode.com
API__TIMEOUT=30
LOG__LEVEL=DEBUG
SECURITY__API_KEY=your-secret-key
```

## Sentry統合（エラー監視）

**詳細**: memory `~/projects/python/api-test-devops-portfolio/.serena/memories/sentry_integration.md`
**概要**: ERROR以上のログを自動でSentryに送信。44種類の機密キーを自動スクラブ。
**開発時無効化推奨**: `SENTRY__ENABLED=false`（demo/prod環境のみ有効化）

## 開発時の注意事項

**基本規約**: memory `~/projects/python/api-test-devops-portfolio/.claude/rules/testing/quality-gates.md`, `~/projects/python/api-test-devops-portfolio/.claude/rules/python/coding-standards.md`

<!-- preserve-on-compact: Git Flow -->
**Git運用** (Git Flow):

| ブランチ | 用途 | マージ戦略 |
|---------|------|-----------|
| `main` | 本番リリース | Regular Merge |
| `develop` | 開発統合 | Squash Merge (from feature) |
| `feature/*` | 機能開発 | → develop |
| `hotfix/*` | 緊急修正 | → main + develop |

**Conventional Commits**: `type(scope): subject` 形式

| type | 意味 | 例 |
|------|------|-----|
| feat | 新機能 | `feat(client): 認証ヘッダー自動付与` |
| fix | バグ修正 | `fix(client): タイムアウト処理修正` |
| docs | ドキュメント | `docs(readme): テスト手順追加` |
| test | テスト | `test(security): OWASP Top 10テスト` |
| refactor | 整理 | `refactor(config): Pydantic Settings移行` |
| chore | 設定変更 | `chore(docker): ベースイメージ更新` |
| perf | 性能改善 | `perf(client): コネクションプール導入` |
| ci | CI/CD | `ci(actions): 並列テスト実行` |
| security | セキュリティ | `security(config): SecretStr導入` |

**scope例**: api / client / config / docker / ci / test / docs / utils

**Git Flow（補助コマンドがある場合）**:
- feature作成（developから分岐）
- hotfix作成（mainから分岐）
- [gone]ブランチクリーンアップ

**PRマージ後の推奨ワークフロー**:
```bash
gh pr merge <PR番号> --squash --delete-branch && \
git fetch --prune origin && \
git checkout -b feature/<次のタスク> origin/develop
```

## 📏 出力品質基準

**CRITICAL**: 全ての出力（計画、レポート、ドキュメント、コメント）に適用。

**根拠**: 業界標準（Google Developer Guide、JIS X 0121、日本TC協会）+ 実測データ（プロジェクト内簡潔文書）

### 文字数制限の明示的定義

| 表現 | 最大文字数 | 適用対象 | 根拠 |
|------|-----------|---------|------|
| **簡潔** | **600-900字** | 技術ドキュメント、計画書、レポート | Google Guide中央値 + TC協会標準 + 実測(quality-gates.md: 900字) |
| **詳細** | **1,500-3,000字** | アーキテクチャ設計、仕様書、ガイド | JIS X 0121（詳細） + Chicago Manual of Style（Brief） |
| **包括的** | **4,000-6,000字** | 最終レポート、完全なガイド、マニュアル | CLAUDE.md実測 + Chicago Article |

**検証方法**:
- 英語出力: `wc -w` で語数計測
- 日本語出力: `wc -m` で文字数計測

**毎セッション確認項目**:
- [ ] 「簡潔」出力は 600-900字に収まるか
- [ ] セッション初期化時に本基準を再読込

**参考**: memory `~/projects/python/api-test-devops-portfolio/.claude/rules/testing/quality-gates.md`

<<!-- preserve-on-compact: Development Workflow -->
## 🔄 開発ワークフロー（標準コマンド実行順序）

**CRITICAL**: `git commit`や`gh pr create`等の生コマンドは使用禁止。

```
【準備フェーズ】
0. 大規模タスク（複数セッション）: `.claude/rules/workflow/RULES.md` 「Task Management (Persistent Layer)」参照
1. 固定Worktreeでブランチ作成 → /git:feature（常時※1）
   → 固定WT: ${HOME}/projects/python/.worktrees/wt-feature0[1-3]（個人環境ごとにカスタマイズ）
   → 計画ファイル作成が必要な場合: claudedocs/plans/ に作成（閾値詳細: .claude/rules/workflow/PLANS.md §使用閾値）

【実装フェーズ】
2. コード変更 → security-guidance (hook自動)
3. 品質ゲート → pytest + ruff + mypy 全合格（※2）
   → For non-trivial changes, ask: "Is there a more elegant implementation?"
   → If it feels hacky, ask: "Given what I know now, what's the most elegant approach?"
   → Skip for obvious single-line fixes
4. 作業完了確認 → `Skill(fable:fable-judge)` を実行
5. reflect(タスクごとに実施) → `Skill(reflexion:reflect)` を実行
   引数: deep reflect if less than 90% confidence. 日本語で簡潔に回答
   自動ループ:
    - 信頼度90%未満: 改善して再実行（各反復で信頼度と改善理由を簡潔に示す）/ 90%以上 → 終了 - 最大3回まで
    - 4回連続失敗時（信頼度90%未満継続）はユーザーに報告して停止
6. コミット前レビュー → `Skill(code-review)`
7. コミット前確認（重要変更の場合） → `Skill(judgment-day)`を実行
8. コミット   → `Skill(commit)`【git commit禁止】

【PUSH/PR/マージフェーズ】
9. PR作成     → Skill(push-pr)【gh pr create禁止】
10. レビュー対応 → 修正 → 品質ゲート →  `Skill(fable:fable-judge)` を実行 →  `Skill(reflexion:reflect)` を実行 → `Skill(code)`を実行 → `Skill(judgment-day)`を実行（重要変更の場合） → Skill(commit) → push
11. マージ実行  → マージ戦略【※3参照】
12. クリーンアップ → `git fetch --prune origin` + `/git:clean-gone`（worktree: 固定運用のため削除しない）
```

<!-- preserve-on-compact: Quality Gates -->
**※1 worktree**: 固定worktree運用（${HOME}/projects/python/.worktrees/wt-feature0[1-3]（個人環境ごとにカスタマイズ））。セッション開始時にwatch_directoryの設定を確認する（mcp__CodeGraphContext__list_watched_paths）
**※2 品質ゲート**: 本ファイル Section「品質ゲート」→「統合コマンド」を使用する

```bash
uv run pytest -n auto -m "(unit or integration) and not external" \
  --cov=utils --cov=config --cov=models --cov-report=term-missing && \
uv run ruff check . && \
uv run mypy utils/ config/ models/ tests/conftest.py
```

**※3 PR前レビュー規模判定**:

| 条件 | レビューツール |
|------|--------------|
| セキュリティファイル変更 OR ≥200行 OR API契約変更 | `code-review:review-pr` |
| <200行 AND 非セキュリティ | `review:review-local-changes`（または同等） |

セキュリティ関連: `utils/sentry_init.py`, `utils/sentry_scrub_*.py`, `utils/logger.py`, `config/settings.py`, `*.env*`
API契約変更対象: `models/responses.py`, `utils/jsonplaceholder_*.py` public methods

**※4 マージ戦略**:

| マージ種別 | コマンド |
|-----------|---------|
| feature → develop | `gh pr merge --squash --delete-branch` |
| develop → main | `gh pr merge --merge` |
| hotfix → main | `gh pr merge --merge` |

## トラブルシューティング

**詳細**: @memory:test_strategy_details トラブルシューティングFAQ参照

### 複数回修正で解決しない場合

**3回以上の修正試行で解決しない場合**:
1. 公式ドキュメントを再確認（仕様変更/誤解の可能性）
2. GitHub Issuesで既知の問題を検索
3. 削除/代替案を検討（機能の必要性を再評価）

## Notes

- `.claude/CLAUDE.md` と `.claude/rules/` は元資料として参照してよいが、Claude 固有のマクロやスラッシュコマンド等は Codex の運用に読み替える（本ファイルではそれらの表記に依存しない）。
- Codex 環境でのトークン最適化ガイドは `~/.codex/RTK.md` を参照する。

<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes` or `query_graph` instead of Grep
- **Understanding impact**: `get_impact_radius` instead of manually tracing imports
- **Code review**: `detect_changes` + `get_review_context` instead of reading entire files
- **Finding relationships**: `query_graph` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview` + `list_communities`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

| Tool | Use when |
|------|----------|
| `detect_changes` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context` | Need source snippets for review — token-efficient |
| `get_impact_radius` | Understanding blast radius of a change |
| `get_affected_flows` | Finding which execution paths are impacted |
| `query_graph` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes` | Finding functions/classes by name or keyword |
| `get_architecture_overview` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.
