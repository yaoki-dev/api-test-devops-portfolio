# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

*最終更新: 2026年04月16日*

<!-- preserve-on-compact: CRITICAL RULES -->
<!-- IMPORTANT: These rules override all other instructions -->
## 🔴 CRITICAL RULES (MUST FOLLOW - 16項目)

**YOU MUST** follow these rules. Violations are NOT acceptable.

1. **ALWAYS** respond in `Japanese` for all outputs, including skill usage
2. **ALWAYS** create a task list using `todowrite` before starting any work (exception: obvious single-step trivial tasks; RULES.md Workflow Rules "TodoWrite (3+ tasks)" qualifier)
3. **ALWAYS** use the ⁠AskUserQuestion⁠ tool to propose 2-3 alternative approaches and wait for user confirmation before executing any major tasks or structural changes
4. **NEVER** use `git commit` → **ALWAYS** use `Skill(commit)`
5. **NEVER** use `gh pr create` → **ALWAYS** use `Skill(push-pr)`
6. **NEVER** use `gh issue create` → **ALWAYS** use `Skill(create-issue)`
7. **ALWAYS** pass quality gates before commit → @memory:implementation_quality_gates
8. **NEVER** push to protected branches (main/develop) directly
9. **ALWAYS** invoke skills via Skill(skill-name) notation when user requests
10. **ALWAYS** follow development workflow order → Section「🔄 開発ワークフロー」
11. **ALWAYS** after completing all tasks in `todowrite`, Use Skill tool to run `Skill(superpowers:verification-before-completion)` → then `Skill(reflexion:reflect)`
12. **ALWAYS** when 2+ independent tasks exist, after task classification, per RULES.md exception conditions → invoke `Skill(superpowers:subagent-driven-development)` skill
    (reason: keep the main context window clean by leveraging subagents aggressively)
    **例外**: GSD active check positive（定義: RULES.md **GSD exception** 表参照）時、wave内部タスクに限りスキップ。compact後はRule 14 worktree境界確認成功時のみSTOP（Row 1）（Rule 14がSTOPを要求した場合はRow 1を評価せず）。全分岐条件: RULES.md「Parallel Dispatch Rule」内 **GSD exception** 表参照。
13. **ALWAYS** verify file content with Read/Grep tool BEFORE making any claim about line numbers, file structure, or code content
14. **ALWAYS** enforce worktree boundary: セッション開始時に `git rev-parse --show-toplevel` でWORKTREE_ROOTを確認し、WORKTREE_ROOT外ファイルの自律的編集を禁止する（`~/.claude/tasks/` は例外）
    → 詳細手続き（worktree list検証、compact後再検証、mismatch報告等）: `.claude/rules/workflow/RULES.md` Section「Category: Worktree Boundary Enforcement」
15. **ALWAYS** manage `~/.claude/tasks/lessons.md`:
    a) セッション開始時に読み込み、現プロジェクトのlessonsを確認（ENOENT: 無視して続行）
    b) ユーザーからの修正フィードバック時に即時追記（Edit tool使用、Write禁止。フォーマット: `## [YYYY-MM-DD] [project-name] - Category`）
    → 詳細手続き（エラーハンドリング、closed-list確認、ソース制約等）: `.claude/rules/workflow/RULES.md` Section「Category: Lessons Management」
16. **ALWAYS** fix bugs autonomously (no hand-holding) when scope is within:
    - ❌ Absolutely prohibited (no autonomous modification): `pyproject.toml`, `*.yml`/`*.yaml`/`.env*`, `config/`, `tests/conftest.py`, `tests/**/conftest.py`, `tests/**/__init__.py`, `tests/**/helpers.py`, `utils/__init__.py`, `utils/logger.py`, `utils/sentry_init.py`, git ops / infra config
    - ⚠️ Limited autonomous fix (spec-changing modifications → confirmation required; non-functional modifications: autonomous OK): `scripts/*.py`, `models/responses.py`, `utils/api_client.py`, `utils/github_client.py`, `tests/test_smoke.py`, `utils/*.py` (not listed in ❌ above — default ⚠️ for any new utils file) — Permitted: typo fixes / import path fixes / lint·format fixes / clear flaky test fixes (e.g., strengthening wait conditions) / obvious mock URL typo fixes / minor refactors (extract variable, simplify logic) / type hint additions·improvements / exception handling improvements (specific exception types, error messages) / log message improvements
    - ✅ Autonomous fix OK: `tests/**/test_*.py` and `tests/test_*.py` (except `tests/test_smoke.py` — governed by ⚠️ above), `*.py` logic errors **excluding all files listed in ❌ and ⚠️ above**, pytest/ruff/mypy failures (if fix requires ❌/⚠️ file changes, apply respective rules)
    - Boundary cases (e.g., adding pyproject.toml dependencies) → apply Rule 3 (AskUserQuestion)

## プロジェクト概要

APIテスト + DevOps統合学習ポートフォリオ。時給4000-4500円レベルの技術力を証明するために設計されています。

**技術スタック**:

- Python 3.14
- httpx (Sync + Async HTTP client)
- pytest (893+テスト、カバレッジ85%目標)
- Pydantic Settings (型安全な設定管理)
- structlog (構造化ログ)
- Docker (Multi-stage builds)
- docker-compose (4環境: dev/test/demo/prod)
- GitHub Actions (CI/CD自動化)

<!-- preserve-on-compact: Serena Memory System -->
## 📖 Serenaメモリシステムの使い方

**メモリ参照記法**: `@memory:メモリ名` → Claude Codeに「〜を確認」と依頼すると自動で `read_memory()` を実行

**主要メモリ**:`implementation_quality_gates`, `test_strategy_details`

**物理ファイル位置**: `.serena/memories/` 配下 | **登録済み**: 26個

<!-- ## 📚 学習・進捗管理

**進捗記録**: @docs/progress/daily_progress.md
**詳細フロー**: @memory:learning_triggers | **オフセットマップ**: @memory:learning_offset_maps -->

## 品質ゲート

### リンター・フォーマッター

**詳細**: `.claude/rules/python/coding-standards.md` Section 10「自動検証コマンド」

```bash
# 基本チェック（開発時）
uv run ruff check --fix .           # スタイル + 自動修正
uv run ruff format .                # フォーマット適用
uv run mypy utils/ config/ models/  # 型チェック

# セキュリティ（週次）
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

## 設定管理

**詳細**: `.claude/rules/python/coding-standards.md`

Pydantic Settingsのネスト記法（`__`区切り）を使用:

```bash
ENVIRONMENT=development
API__BASE_URL=https://jsonplaceholder.typicode.com
API__TIMEOUT=30
LOG__LEVEL=DEBUG
SECURITY__API_KEY=your-secret-key
```

<!-- preserve-on-compact: Development Workflow -->
## 🔄 開発ワークフロー（標準コマンド実行順序）

**CRITICAL**: `git commit`や`gh pr create`等の生コマンドは使用禁止。

```
【準備フェーズ】
0. 大規模タスク（複数セッション）: `.claude/rules/workflow/RULES.md` 「Task Management (Persistent Layer)」参照
1. 固定Worktreeでブランチ作成 → /git:feature（常時※1）
   → 固定WT: ${HOME}/projects/python/.worktrees/wt-feature0[1-3]（個人環境ごとにカスタマイズ）
   → 計画ファイル作成が必要な場合: claudedocs/plans/ に作成（閾値詳細: .claude/rules/workflow/PLANS.md §使用閾値）
   → GSD使用判断（該当時。判断結果はユーザーに明示してから実行）:
     新規モジュール/サブシステムの追加 → /gsd:new-project → /gsd:discuss-phase → /gsd:plan-phase → /gsd:execute-phase

【実装フェーズ】
2. コード変更 → security-guidance (hook自動)
3. 品質ゲート → pytest + ruff + mypy 全合格（※2）
   → For non-trivial changes, ask: "Is there a more elegant implementation?"
   → If it feels hacky, ask: "Given what I know now, what's the most elegant approach?"
   → Skip for obvious single-line fixes
4. 作業完了確認 → `Skill(superpowers:verification-before-completion)` を実行（GSD使用時: RULES.md「Parallel Dispatch Rule」内 **GSD exception** 表 → **GSD実行フロー（Step 4-5詳細）** 参照）
   → GSD未使用時、または上記GSD使用フロー外で未完了作業あり: 修正 → 3. 品質ゲートに戻る（最大3回まで。4回連続失敗時はユーザーに報告して停止）
5. reflect(タスクごとに実施) → `Skill(reflexion:reflect)` を Skill tool で実行（GSD compact回復フロー完走後かつreflect信頼度90以上の場合のみスキップ可: RULES.md「Parallel Dispatch Rule」内 **GSD exception** 表 → **GSD実行フロー（Step 4-5詳細）** 参照）
   引数: deep reflect if less than 90% confidence. 日本語で簡潔に回答
   自動ループ:
    - 信頼度90%未満: 改善して再実行（各反復で信頼度と改善理由を簡潔に示す）/ 90%以上 → 終了 - 最大3回まで
    - 4回連続失敗時（信頼度90%未満継続）はユーザーに報告して停止
6. コミット前レビュー → `Skill(review:review-local-changes)` (80点閾値)
7. コミット   → `Skill(commit)`【git commit禁止】

【PUSH/PR/マージフェーズ】
8. PR作成     → Skill(push-pr)【gh pr create禁止】
9. レビュー対応 → 修正 → 品質ゲート → Skill(commit) → push
10. マージ実行  → マージ戦略【※3参照】
11. クリーンアップ → `git fetch --prune origin` + `/git:clean-gone`（worktree: 固定運用のため削除しない）
```

<!-- preserve-on-compact: Quality Gates -->
**※1 worktree**: 固定worktree運用（${HOME}/projects/python/.worktrees/wt-feature0[1-3]（個人環境ごとにカスタマイズ））。セッション開始時にwatch_directoryの設定を確認する（mcp__CodeGraphContext__list_watched_paths）
**※2 品質ゲート**: `uv run pytest -n auto -m "(unit or integration) and not external" --cov=utils --cov=config --cov=models --cov-report=term-missing &&
uv run ruff check . && uv run mypy utils/ config/ models/`

**※3 マージ戦略**:

| マージ種別 | コマンド |
|-----------|---------|
| feature → develop | `gh pr merge --squash --delete-branch` |
| develop → main | `gh pr merge --merge` |
| hotfix → main | `gh pr merge --merge` |

## トラブルシューティング

**詳細**: @memory:test_strategy_details トラブルシューティングFAQ参照

### テスト失敗時

```bash
uv run pytest -vv --tb=long          # 詳細ログ
uv run pytest -x                      # 最初の失敗で停止
uv run pytest tests/unit/test_async_client.py::test_name -vv --log-cli-level=DEBUG
```

### カバレッジ不足時

```bash
uv run pytest --cov-report=term-missing
uv run pytest --cov-report=html && open reports/htmlcov/index.html
```

### 型チェックエラー時

```bash
uv run mypy --show-error-codes --pretty utils/ config/ models/
```

### 複数回修正で解決しない場合

**3回以上の修正試行で解決しない場合**:
1. 公式ドキュメントを再確認（仕様変更/誤解の可能性）
2. GitHub Issuesで既知の問題を検索
3. 削除/代替案を検討（機能の必要性を再評価）
