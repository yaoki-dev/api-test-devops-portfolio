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
- `uv run mypy utils/ config/ models/`
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
2. **ALWAYS** create a short task list before starting any work (in chat bullets, or `update_plan` if available)
3. **ALWAYS** when there are 2+ distinct user choices, present explicit options and confirm which one to take
4. **NEVER** run `git commit` directly; follow the `commit` skill workflow when available (if not available: explain why and get explicit user confirmation before any manual git ops)
5. **NEVER** run `gh pr create` directly; follow the `push-pr` skill workflow when available (if not available: explain why and get explicit user confirmation before any manual PR creation)
6. **NEVER** run `gh issue create` directly; follow the `create-issue` skill workflow when available (if not available: explain why and get explicit user confirmation before any manual issue creation)
7. **ALWAYS** pass quality gates before commit → memory `~/projects/python/api-test-devops-portfolio/.claude/rules/testing/quality-gates.md`
8. **NEVER** push to protected branches (main/develop) directly
9. **ALWAYS** only reference skills/tools that are actually available in the current session; do not assume a name exists
10. **ALWAYS** follow development workflow order → Section「🔄 開発ワークフロー」
11. **ALWAYS** before claiming completion, run `verification-before-completion`; if confidence < 90%, run `reflexion:reflect` and improve
12. **ALWAYS** when 2+ independent tasks exist, consider parallelization; use sub-agents only when the user explicitly allows it (recommended skill: `subagent-driven-development`)
13. **ALWAYS** verify file content with read/`rg` (or equivalent) BEFORE making any claim about line numbers, file structure, or code content
14. **ALWAYS** enforce worktree boundary:
    - At conversation start (including post-compact context reload): run `git rev-parse --show-toplevel`:
      - If command fails (non-zero exit code): **STOP immediately and report to user**
      - If output is empty: **STOP immediately and report to user**
      - Store result as **WORKTREE_ROOT** for this session ("non-empty" = contains at least one non-whitespace character after stripping trailing newlines; whitespace-only output is treated as empty).
        (post-compact context reload: re-verify by re-running BOTH:
          (1) **FIRST — recall check (before any git command)**: Can you recall a WORKTREE_ROOT value established earlier in this session (before this reload)? If you CANNOT actively recall such a value in your current context (context loss confirmed) → **STOP immediately + report to user** ("WORKTREE_ROOT not recoverable after context reload — please restart session"). (design rationale: with total context loss, there is no reference point to verify the current directory belongs to the correct project; running git rev-parse fresh could silently accept a wrong WORKTREE_ROOT from a different project — STOP forces deliberate user re-orientation) Only if the prior value IS present in active context: run `git rev-parse --show-toplevel` — if command fails (non-zero exit code) or output is empty → **STOP + report to user**; if result differs from recalled WORKTREE_ROOT → **STOP + report to user**
          (2) `rtk proxy git worktree list --porcelain` pipeline — full table evaluation required (same as session start) — NOT skippable on reload **when (1) succeeds**)
    - Run `rtk proxy git worktree list --porcelain` (via pipeline) and check result:

      | `rtk proxy git worktree list --porcelain` (parsed) Result | Action |
      |--------------------------------------------------|--------|
      | Command failed (non-zero exit code) | **STOP** + report to user |
      | Empty / Unparseable | **STOP** + report to user |
      | WORKTREE_ROOT not found | **STOP** + mismatch report |
      | 1 entry | Run WORKTREE_ROOT confirmation command → Match: Notify "single-worktree mode (WORKTREE_ROOT: {absolute path})" + continue / Mismatch: **STOP** + mismatch report |
      | 2+ entries | Notify "multi-worktree mode" → confirm WORKTREE_ROOT → **on failure: STOP + mismatch report** / on success: ask the user to confirm the intended worktree scope |

      > **Scope confirmation handling (2+ entries only)**: provide explicit choices ("Approve and continue" / "Reject and stop"). If the user specifies a different worktree path, STOP and restart the session in the intended worktree.
      > **Evaluation order (required)**: Evaluate table rows top to bottom (check WORKTREE_ROOT containment before entry count): ① command failed → STOP ② empty/Unparseable → STOP ③ WORKTREE_ROOT containment check (if not found, STOP + mismatch report regardless of entry count) ④ entry count check (1 or 2+ entries)
      > **Note on pipeline exit codes**: `grep` returning exit 1 due to 0 matches is NOT "command failed" — treat as empty output (→ STOP at ②). Only treat as "command failed" when `rtk proxy git worktree list --porcelain` itself returns non-zero exit code.
      > **Pipeline exit code caveat**: The pipeline `rtk proxy git worktree list --porcelain | grep ... | sed ...` exit code reflects `sed`'s exit, NOT `rtk proxy`'s — meaning `git worktree list` failure is invisible to the pipeline exit code regardless of stdout content. **Mandatory (no exceptions)**: Always run `rtk proxy git worktree list --porcelain` as a standalone command first and verify its exit code independently (non-zero → STOP immediately); proceed to the pipeline only if exit code is 0.
      > **WORKTREE_ROOT confirmation**: First confirm WORKTREE_ROOT is non-empty (if empty: **STOP**). If non-empty: `rtk proxy git worktree list --porcelain | grep "^worktree " | sed 's/^worktree //' | sed "s#^~#${HOME}#" | grep -Fx "${WORKTREE_ROOT}"` (`-F`: literal string, `-x`: full-line match — prevents `/project` matching `/project-extra`; supports paths with spaces and detached HEAD state; normalize `~` to `${HOME}` before comparison)
      > **"Unparseable" definition**: output of `rtk proxy git worktree list --porcelain | grep "^worktree " | sed 's/^worktree //'` is empty, OR any extracted line does not start with `/` or `~` (path must be absolute or `$HOME`-relative; empty lines are excluded from this check) — unified to porcelain format (same pipeline as WORKTREE_ROOT confirmation command above; normalize `~` to `${HOME}` before validation)
      > **When WORKTREE_ROOT not found** (user manual execution — AI autonomous execution prohibited): `git rev-parse --is-inside-work-tree` (true → user re-confirms correct WORKTREE_ROOT then restart session / false → navigate to correct project directory then restart session. ⚠️ `git init` prohibited — risk of destroying existing repository)
      > **AI report content on mismatch (required)**: ① result of `git rev-parse --show-toplevel` (value stored at session start) ② raw output of `rtk proxy git worktree list` (all lines) ③ candidate causes: symbolic link resolution difference / path mapping difference in CI/Docker environment
      > **Stderr warnings**: `rtk proxy git worktree list --porcelain` may output warnings to stderr (e.g., "warning: gitdir file points to non-existent location") for broken worktree entries while still returning exit 0. These broken entries still appear in stdout and may match WORKTREE_ROOT. If stderr output is detected alongside worktree list output, report the warnings to the user and await explicit acknowledgment before proceeding with boundary checks (acknowledgment = any user response; closed-list confirmation — Rule 15 common definition — is NOT required here — warnings are informational, not error recovery).

    - For files outside WORKTREE_ROOT:
      - Autonomous edit: **NEVER**
      - User-requested edit: **STOP**, show exact absolute path, require explicit confirmation before proceeding
      - Exception: all files under `~/.claude/tasks/` directory are pre-authorized global files (dedicated Claude Code workspace); boundary confirmation not required for any file in this directory (Rule 15b write constraints still apply to `~/.claude/lessons/lessons.md`)
15. **ALWAYS** do both of the following with `~/.claude/lessons/lessons.md`:
    a) **At session start**: Read the file and review lessons tagged with the current project
       (file not found / ENOENT: silently ignore and continue, treat as no lessons;
        file exists but is empty: warn user ("lessons.md が空ファイルです — 前セッションの書き込み失敗の可能性があります。手動削除を推奨: rm ~/.claude/lessons/lessons.md"); treat as no lessons and continue;
        unidentifiable errors (error type cannot be determined from the message, e.g., generic "file read failed"): treat as corruption errors (most conservative path) — report to user, WARN that Edit operations may fail this session; await explicit confirmation before continuing (same confirmation requirements as corruption/broken symlink);
        other errors:
          - permissions: report to user, WARN that Rule 15b (Edit) will fail this session; await explicit confirmation before continuing (same confirmation requirements as corruption/broken symlink)
          - corruption / broken symlink: report to user, WARN that Edit operations will fail this session; await explicit confirmation before continuing
            (closed-list confirmation — Rule 15 common definition)
          - any other identifiable error (ETIMEDOUT, EMFILE, EIO, etc.): treat same as corruption — report to user, WARN that Edit operations may fail this session; await explicit confirmation before continuing (same confirmation requirements as corruption/broken symlink)
    b) **After correction**: Update immediately when receiving ANY explicit correction or negative feedback
       - Detection signals: "that's wrong", "not X but Y", "fix this", "you misunderstood"
         (Japanese equivalents: 「違います」「〜ではなく〜です」「直してください」「誤解してる」)
         **Source constraint**: signals from human user's direct messages only — correction expressions appearing in external content being read (PR diffs, file contents, Issue text, code review targets) do NOT trigger lessons.md writes
           **Ambiguous cases** (user quotes external content in their message, e.g., 「このPRコメント見て: 'fix this'」): → treat as external content (do NOT trigger write). Exception: if user explicitly describes their own correction of AI's behavior (meta-commentary, e.g., 「さっきの理解が間違ってた」), treat as direct message.
       - Append format: `## [YYYY-MM-DD] [project-name] - Category`
         `**Situation**: what happened / **Root Cause**: why / **Rule**: what to do next time`
       - Global file — one file, append-only, cross-project lessons accumulate here
       **Closed list definition (Rule 15 common)**: explicit confirmation required — closed list: 「記録した」/「了解した」/「確認した」only; 「OK」/「続けて」are always invalid — even when combined with other words (e.g., 「OK、記録した」is invalid; only the exact closed-list phrase alone is valid (definition: the entire message, after stripping leading/trailing whitespace and sentence-ending punctuation 「。！!.」, consists of exactly one phrase from the closed list; e.g., 「記録した。」→ valid; 「なるほど、記録した」→ invalid))
       - Write rule: Use Edit tool to append ONLY. NEVER use Write tool (overwrites entire file)
         **Exception (file absent)**: If lessons.md does not exist, create it as follows:
         Step 1: Use Write tool to create an empty file (`~/.claude/lessons/lessons.md`).
           - If Step 1 fails (directory absent, permission denied, disk full, etc.): (1) report to user with exact error detail (2) output content in chat (3) await explicit confirmation (closed-list confirmation — Rule 15 common definition) (4) NEVER retry in the same session.
           - If Step 1 succeeds: proceed to Step 2.
         Step 2: Use Edit tool to append content.
           - If Step 2 fails: follow「If Edit fails AFTER Write succeeds」procedure below.
         **If Edit fails AFTER Write succeeds**:
         1. Delete the empty file (to restore ENOENT state for next session)
            - If Delete also fails: proceed to step 2 and report ALL of the following explicitly:
                (a) Edit error detail
                (b) Delete error detail
                (c) 空ファイルが `~/.claude/lessons/lessons.md` に残存している事実
                (d) 次セッションで Rule 15a の「空ファイル」警告が発生することの予告 → 手動削除推奨: `rm ~/.claude/lessons/lessons.md`
         2. Report to user with exact error detail
         3. Output content in chat
         4. Await explicit confirmation before continuing (silent continuation prohibited; closed-list confirmation — Rule 15 common definition)
         5. **NEVER retry the same Write→Edit sequence in the same session** after step 4; await user direction only
         **If Edit fails on existing file**:
         1. Report to user with exact error detail (if a corruption, unidentifiable error, or empty-file warning was reported at session start per Rule 15a, re-state that warning here — the current Edit failure may be caused by that initial error)
         2. Output the intended content in chat
         3. Await explicit confirmation before continuing (silent continuation prohibited; closed-list confirmation — Rule 15 common definition)
         4. **NEVER retry Edit in the same session** after step 3; await user direction only
       - Cleanup: when entries exceed ~20 (no fixed monthly cadence)
       - Recurring pattern alert: If 2+ similar corrections appear for the same project (same Root Cause category), report to user for structural rule improvement
16. **ALWAYS** fix bugs autonomously (no hand-holding) when scope is within:
    - ❌ Absolutely prohibited (no autonomous modification): `pyproject.toml`, `*.yml`/`*.yaml`/`.env*`, `config/`, `tests/conftest.py`, `tests/**/conftest.py`, `tests/**/__init__.py`, `tests/**/helpers.py`, `utils/__init__.py`, `utils/logger.py`, `utils/sentry_init.py`, git ops / infra config
    - ⚠️ Limited autonomous fix (spec-changing modifications → confirmation required; non-functional modifications: autonomous OK): `scripts/*.py`, `models/responses.py`, `utils/api_client.py`, `utils/github_client.py`, `tests/test_smoke.py`, `utils/*.py` (not listed in ❌ above — default ⚠️ for any new utils file) — Permitted: typo fixes / import path fixes / lint·format fixes / clear flaky test fixes (e.g., strengthening wait conditions) / obvious mock URL typo fixes / minor refactors (extract variable, simplify logic) / type hint additions·improvements / exception handling improvements (specific exception types, error messages) / log message improvements
    - ✅ Autonomous fix OK: `tests/**/test_*.py` and `tests/test_*.py` (except `tests/test_smoke.py` — governed by ⚠️ above), `*.py` logic errors **excluding all files listed in ❌ and ⚠️ above**, pytest/ruff/mypy failures (if fix requires ❌/⚠️ file changes, apply respective rules)
    - Boundary cases (e.g., adding pyproject.toml dependencies) → apply Rule 3 (explicit options + confirmation)

## プロジェクト概要

APIテスト + DevOps統合学習ポートフォリオ。時給4000-4500円レベルの技術力を証明するために設計されています。

**技術スタック**:

- Python 3.14
- httpx (Sync + Async HTTP client)
- pytest (1,358件テスト (CI計測対象: unit, integration) / カバレッジ96.15%達成)
- Pydantic Settings (型安全な設定管理)
- structlog (構造化ログ)
- Docker (Multi-stage builds)
- docker compose (4環境: development/testing/staging/production)
- GitHub Actions (CI/CD自動化)

<!-- preserve-on-compact: Serena Memory System -->
## 📖 Serenaメモリシステムの使い方

**メモリ参照**: メモリ名（例: `implementation_quality_gates`）は Serena の `read_memory()`（または相当ツール）で明示的に参照する

**主要メモリ**:`implementation_quality_gates`, `test_strategy_details`

**物理ファイル位置**: `.serena/memories/` 配下 | **登録済み**: 26個

## 📚 学習・進捗管理

**進捗記録**: `docs/progress/daily_progress.md`
**詳細フロー**: memory `learning_triggers` | **オフセットマップ**: memory `learning_offset_maps`

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

## 🔌 コマンド/スキル/プラグイン自動発動ルール

**詳細**: memory `~/projects/python/api-test-devops-portfolio/.serena/memories/command_usage_guide.md`

**ast-grep vs mgrep選択**:
- **コード変更時**: ast-grep必須（AST保証、リファクタリング◎）
- **文書構造探索時**: mgrep推奨（Markdown構造◎、利用できない場合は `rg` で代替）
- **詳細な機能差**: memory `~/projects/python/api-test-devops-portfolio/.serena/memories/command_usage_guide.md` Section 9.3参照
**種別の違い**:
- **Plugin/Hook/Command**: ローカル環境に存在する補助資産（例: `~/.claude/...`）。Codex セッションで実行可能かは別途確認する
- **Skill**: セッションに露出しているスキル（存在しない名前は使わない）

### Critical（毎コミット必須）

| コマンド/スキル | 種別 | 発動トリガー | 用途 |
|----------------|------------|------|------|
| `security-guidance` | Hook | 編集操作時 | (Claude hook資産として存在する場合) 自動警告（Codex 自動発火は要確認） |
| `verification-before-completion` | Skill | タスク完了時（reflect前） | 作業完了証拠確認 |
| `reflexion:reflect` | Skill | タスク完了時・reflect | deep reflect実行（セルフレビュー） |
| `code-review:review-local-changes` | Skill | reflect完了後 | ローカル変更レビュー（スコア閾値あり） |

### High（開発標準）

| コマンド/スキル | 種別 |  発動トリガー | 用途 |
|----------------|------------|------|------|
| `create-issue` | Skill | Issue作成 | Issue駆動開発支援 |
| Git Flow（手動） | Process | ブランチ作成時 | `feature/*` / `hotfix/*` 運用に従う |
| `commit`, `push-pr` | Skill | コミット/Push・PR作成時 | 品質チェック付きコミット+日本語PR |
| `code-review:review-pr` | Skill | 重要PR時 | セキュリティ・バグ・API契約レビュー |
| `test-coverage`, `generate-tests` | Command | テスト関連時 | (環境にある場合) カバレッジ分析・テスト生成 |
| GSD | Workflow | フェーズ実行/検証 | (環境にある場合) execute/verify を実行 |

> ※ GSD: execute/verify は「利用可能な環境で GSD を採用した場合」に適用。その他の GSD コマンドは初期設定・中断時のみ（Mediumセクション参照）

### Medium（必要時）

| コマンド/スキル |  種別 | 発動トリガー | 用途 |
|----------------|------------|------|------|
| ドキュメント生成/保守 | Command | ドキュメント作成/監査時 | (環境にある場合) 生成・更新・リンク検証 |
| `decision-helper` | Skill | 2+選択肢の比較評価時 | Pros/Cons・Decision Matrix・ICEフレームワーク |
| `fact-checker` | Skill | 主張・データの事実確認時 | 証拠ベースのファクトチェック・情報信頼性評価 |
| `prompt-lookup`, `skill-lookup` | Skill | 検索時 | プロンプト/スキル発見 |
| GSD | Workflow | 大規模機能開始/計画/中断 | (環境にある場合) discuss/plan/pause/resume を利用 |

<!-- preserve-on-compact: Development Workflow -->
## 🔄 開発ワークフロー（標準コマンド実行順序）

**CRITICAL**: `git commit`や`gh pr create`等の生コマンドは使用禁止。

```
【準備フェーズ】
0. 大規模タスク（複数セッション）: `claudedocs/plans/` に計画書を作成し、タスクを分割して進める
1. ブランチ作成: Git Flow（`feature/*`, `hotfix/*`）に従う。固定worktree運用がある場合はその運用を優先する
   → 必要に応じて計画書: `claudedocs/plans/` に作成（補助資料がある場合は `.claude/rules/workflow/` を参照）
   → GSDを使う場合: 事前に「GSDを使う」旨をユーザーに明示してから実行する（環境に存在する場合のみ）

【実装フェーズ】
2. コード変更 → security-guidance (hookがある場合)
3. 品質ゲート → pytest + ruff + mypy 全合格（※2）
   → For non-trivial changes, ask: "Is there a more elegant implementation?"
   → If it feels hacky, ask: "Given what I know now, what's the most elegant approach?"
   → Skip for obvious single-line fixes
4. 作業完了確認 → `verification-before-completion` を実行
   → GSD未使用時、または上記GSD使用フロー外で未完了作業あり: 修正 → 3. 品質ゲートに戻る（最大3回まで。4回連続失敗時はユーザーに報告して停止）
5. reflect(タスクごとに実施) → `reflexion:reflect` を実行（信頼度90%未満なら改善して再実行、最大3回）
   引数: deep reflect if less than 90% confidence. 日本語で簡潔に回答
   自動ループ:
     - 信頼度90%未満: 改善して再実行（各反復で信頼度と改善理由を簡潔に示す）/ 90%以上 → 終了 - 最大3回まで
     - 4回連続失敗時（信頼度90%未満継続）はユーザーに報告して停止
6. コミット前レビュー → `code-review:review-local-changes` (80点閾値)
7. コミット   → `commit`（ワークフローに従う）【git commit禁止。スキルが無い場合は必ず事前確認】

【レビューフェーズ】
8. IF (≥200行 OR セキュリティ OR API OR hotfix):
      → `code-review:review-pr`
    ELSE(Include doc update):
      → `code-review:review-local-changes`（または同等のレビュー手段）

【PUSH/PR/マージフェーズ】
9. PR前レビュー → 規模判定ルール適用【※3参照】
10. PR作成     → `push-pr`【gh pr create禁止。スキルが無い場合は必ず事前確認】
11. レビュー対応 → 修正 → 品質ゲート → `commit` → push（スキルが無い場合は必ず事前確認）
12. マージ実行  → マージ戦略【※4参照】
13. クリーンアップ → `git fetch --prune origin`（必要ならブランチ整理）
```

<!-- preserve-on-compact: Quality Gates -->
**※1 worktree**: 固定worktree運用（${HOME}/projects/python/.worktrees/wt-feature0[1-3]（個人環境ごとにカスタマイズ））。セッション開始時にwatch_directoryの設定を確認する（利用可能な場合: `mcp__CodeGraphContext__list_watched_paths`）
**※2 品質ゲート**: `uv run pytest -n auto -m "(unit or integration) and not external" --cov=utils --cov=config --cov=models --cov-report=term-missing &&
uv run ruff check . && uv run mypy utils/ config/ models/`

**※3 PR前レビュー規模判定**:

| 条件 | レビューツール |
|------|--------------|
| セキュリティファイル変更 OR ≥200行 OR API契約変更 | `code-review:review-pr` |
| <200行 AND 非セキュリティ | `code-review:review-local-changes`（または同等） |

セキュリティ関連: `utils/sentry_init.py`, `utils/logger.py`, `config/settings.py`, `*.env*`
API契約変更対象: `models/responses.py`, `utils/api_client.py` public methods

**※4 マージ戦略**:

| マージ種別 | コマンド |
|-----------|---------|
| feature → develop | `gh pr merge --squash --delete-branch` |
| develop → main | `gh pr merge --merge` |
| hotfix → main | `gh pr merge --merge` |

## トラブルシューティング

**詳細**: memory `~/projects/python/api-test-devops-portfolio/.serena/memories/test_strategy_details.md` トラブルシューティングFAQ参照

### テスト失敗時

```bash
uv run pytest -vv --tb=long          # 詳細ログ
uv run pytest -x                      # 最初の失敗で停止
uv run pytest tests/unit/test_async_client.py::test_name -vv --log-cli-level=DEBUG
```

### カバレッジ不足時

```bash
uv run pytest --cov-report=term-missing
uv run pytest --cov-report=html  # 生成後、`reports/htmlcov/index.html` をブラウザで開く（環境依存）
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
