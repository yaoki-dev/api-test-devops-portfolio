# Claude Code Behavioral Rules

## Description
Practical rules for **api-test-devops-portfolio** project development with Claude Code.

---

## Priority System

**Levels:** Critical (security/data safety) | Important (quality/maintainability) | Recommended (optimization/style)

**Conflict Resolution:** Safety First > Scope > Features > Quality > Speed

---

## Category: Workflow Rules
**Trigger:** All development tasks | **Priority:** Important

- A task list is required at 3+ tasks; use the harness's task-list tool (`TodoWrite`, or `TaskCreate`/`TaskList`/`TaskUpdate` where TodoWrite is not granted). Identify independent work up front so it can run in parallel.
- Batch independent operations; validate before/after execution
- One task per subagent invocation; avoid multi-task delegation to maintain context focus; if a subagent reports failure or partial completion (any task where not all specified artifacts have reached their expected final state), stop and report to the user instead of silently continuing.
- This applies to task delegation; reflexion retry logic in CLAUDE.md governs implementation quality checks.
- Within a single agent turn, parallel *tool calls* (Read, Grep, Bash, Agent etc.) remain encouraged (see "Batch independent operations" above); this is distinct from delegating multiple unrelated tasks to a single subagent.
- Session pattern: Load → Work → Checkpoint (30 min) → Save
- **Parallel Dispatch Rule** (extension of "One task per subagent invocation" above — each agent still handles exactly one task): When 2+ independent task-list tasks exist, dispatch each as a separate Agent tool invocation, giving every agent a distinct `name` so it can be addressed later (parallel recommended)
  - Independence criteria (all must be satisfied):
    1. No output dependency between tasks (no A→B ordering constraint)
    2. No simultaneous edits to the same file
    3. No conflicting **writes** to shared resources (examples: conftest.py, pyproject.toml, uv.lock, config files, .env files — read-only access does not count as conflicting; when write conflicts cannot be ruled out, treat as shared)
  - Worktree isolation: instruct each agent to use fixed worktrees at `${HOME}/projects/python/.worktrees/wt-feature0[1-3]`（個人環境ごとにカスタマイズ）
    - **起動時検証必須**: `ls "${HOME}/projects/python/.worktrees"/wt-feature* 2>/dev/null | head -3` で実在確認、失敗時は sequential fallback
  - Exception: if one task has 3x+ more task-list sub-items (or estimated file changes) than the other, sequential execution is acceptable

    **Subagent context disambiguation（簡素化版）**:
    - 各サブエージェントは独立したタスクリストを持つ（親と共有しない）
    - 完了報告は `Skill(fable:fable-judge)` 実行後に実施（失敗時は即座に親へエラー報告・親は STOP）
    - 親エージェントは **成果物の実在確認のみ** 行う（内容検証はサブエージェントの verification に委譲）
  - On failure: if **any** agent reports failure or partial completion, the parent agent must (1) decide whether to stop the remaining agents with `TaskStop` or let them finish, (2) collect and log agent statuses (success/failure/unknown), and (3) report full status summary to user before further action
  - Report ambiguous or empty results to the user before continuing
  - On completion: after all parallel agents complete, the parent agent verifies **artifact existence only** (content validation delegated). Mark parent task complete.
  - Context refinement (the parent agent determines applicability before dispatch):
    - If the task does not contain any concrete file paths already identified as in scope, or if applicability is ambiguous, include Skill(iterative-retrieval) in the agent prompt.
    - If one or more concrete file paths are present, context refinement is optional. When skipping it, record `[SKIP: <reason>]`.
    - A concrete file path means a path to an individual file with an extension. Glob patterns and directory paths do not qualify.
    - iterative-retrieval runs a dispatch → evaluate → refine loop for a maximum of three cycles.
    - An empty response, timeout, error, or investigation that stops before completion counts as a failed cycle, consumes one cycle, and does not reset the consecutive-failure counter. A failed cycle must not be used as the baseline for convergence comparison, but any useful information it produced may inform the next cycle.
    - A new Agent invocation resets the cycle counter. However, the same task must not be restarted solely to bypass the cycle limit.
    - Convergence criteria: The investigated file list is unchanged from the previous successful cycle, and no unresolved gaps remain regarding the impact scope.
    - Stop when either three cycles have been consumed or two consecutive cycles have failed. Report to the parent agent: the number of cycles consumed, a summary of each cycle’s investigation, unresolved gaps, the fallback condition triggered, and the reason convergence was not achieved.
    - The parent agent must report the result to the user and must not perform any subsequent work until the user provides explicit instructions.

**Task Classification**: Before dispatching, classify the task type:
- **Implementation** : code writing, feature development, bug fixes, test authoring
- **Investigation** : research, analysis, debugging, codebase exploration
- **Review** : code review, PR review, security audit, documentation review
- **Design** : architecture design, API spec, system planning

**Dispatch Automation**: After classifying and decomposing the request, consider dispatching
subagents when two or more tasks are genuinely independent and can be
executed concurrently.
Dispatch only when the expected benefit of parallel execution exceeds
the delegation, context-transfer, coordination, and integration costs.
Do not dispatch merely because two tasks exist. Keep tasks in the parent
agent when they are small, sequentially dependent, require shared global
context, or may cause overlapping file modifications.
Assign each subagent a distinct scope, explicit completion criteria, and
clear read/write permissions. The parent agent remains responsible for
validating, reconciling, and integrating all results. After all agents complete and all task-list tasks are marked done, `Skill(fable:fable-judge)` → `Skill(reflexion:reflect)` runs per CLAUDE.md Rule 11 at the parent agent level only (subagents do not repeat this parent-level pass; the per-subagent `Skill(fable:fable-judge)` before completion report remains required as the delegated content verification). On verification failure (i.e., `Skill(fable:fable-judge)` reports incomplete work): apply CLAUDE.md Step 4 retry policy (max 3 retries; report to user and stop on 4th consecutive failure — counter resets on success).

**Good:** Plan → task list → Execute → Verify | **Bad:** Jump to implementation

**Reference:** `@memory:api-specification-check`, `@memory:execution-efficiency`

---
## Category: Analysis-Only Request Boundary
**Trigger:** Requests whose primary instruction is to judge, evaluate, analyze, review, inspect, compare, or recommend | **Priority:** Critical

- Treat these requests as read-only unless the user explicitly requests implementation or file modification.
- Analysis, investigation, command execution that does not modify project files, and presentation of findings are allowed.
- Do NOT use Edit, Write, file deletion, formatting tools that rewrite files, or commands that modify tracked files.
- Identifying a recommended fix does not authorize implementing it.
- After presenting the judgment and recommended changes, wait for an explicit user instruction to implement them.
- An existing implementation plan, suggested patch, or obvious fix is not equivalent to implementation authorization.
- **Mixed-message scope**: when a single message mixes judgment-only and implementation instructions, implementation authorization applies ONLY to the items that message explicitly names; every other item remains read-only. A shared rationale, an adjacent finding, or a "twin" discovered while implementing an authorized item does NOT extend the authorization to it.
- **Relation to CLAUDE.md Rule 16 (lex specialis)**: Rule 16's autonomous-fix mandate is the general case; an analysis-only request is the specific case, and the specific governs. Inside such a request Rule 16 does not fire — a bug discovered while judging is reported, not fixed, until the user authorizes the fix, regardless of the bug's ✅/⚠️ file classification. This narrows Rule 16's scope by context; it does not claim to override a higher-priority document.

## Category: Task Management (Persistent Layer)
**Trigger:** Multi-session or large-scale tasks | **Priority:** Important

For large-scale or multi-session tasks,
1. **Plan First**: Write a checkable item list before starting
2. **Verify Plan**: Align with the user before implementation
3. **Track Progress**: Mark items as complete
4. **Document Results**: Append review section after completion

Persistent record location: `claudedocs/plans/<YYYY-MM-DD-topic>.html` (per PLANS.md)
The harness's task-list tool remains the in-session UI.

**Reference:** `.claude/CLAUDE.md` Section「🔄 開発ワークフロー」Step 0（全体開発ワークフローとの統合コンテキスト）

---

## Category: Task Completion Self-Review
**Trigger:** Task-list task completion | **Priority:** Important

**Production Phase:** Self-review after each task: `Skill(fable:fable-judge)` → `Skill(reflexion:reflect)`. Fix issues before proceeding.

**Change Report (after verification + reflect):** End coding tasks with structured summary:
- **Files changed**: full path list (every file touched, including renames/deletes)
- **Files in scope but untouched**: explicit list of files considered but deliberately NOT modified
- **Next verification**: 2-3 user-side check items (test command / browse path / log location)

**Skip conditions**: typo-only / format-only / single-line trivial fixes / docs-or-asset-only updates without code logic impact (`*.py` / `config/` / `*.yml` / `*.toml` unchanged).

---

## Category: Planning Efficiency
**Trigger:** Planning phases, task lists, multi-step tasks | **Priority:** Critical

- Map dependencies so independent work can run in parallel
- When plan doc needed: create in claudedocs/plans/ per PLANS.md §使用閾値
- Record AskUserQuestion results and design decisions in Decision Log (see PLANS.md)

**Reference:** `@memory:execution-efficiency` (execution details; §成功指標 defines the target values) | `PLANS.md` (plan template)

---

## Category: Implementation Integrity
**Trigger:** Feature/function creation, code generation | **Priority:** Important

### Quality Gates (All Must Pass)

| Gate | Check | Recovery |
|------|-------|----------|
| 1: Tests | All pass, coverage target met | `pytest -vv` |
| 2: Linter | 0 errors | `ruff check --fix .` |
| 3: Types | 0 errors, all hints present | `.claude/CLAUDE.md`「統合コマンド」の mypy 部分 |
| 4: VCS | Committed with conventional message | `git add` + `Skill(commit)` |

**Verification:** `.claude/CLAUDE.md` Section「品質ゲート」→「統合コマンド」 + Gate 4 check (`.claude/rules/testing/quality-gates.md` Section「統合検証コマンド」)

**Reference:** `@memory:implementation_quality_gates`, `@memory:api-specification-check`

---

## Category: Scope Discipline
**Trigger:** Ambiguous requirements, feature extensions | **Priority:** Important

Count distinct user-facing features (implementation details are sub-items); add 2 for an architecture change and 1 each for an external integration, a security concern, or a performance concern. Up to 3: build all requested. 4 or more: AskUserQuestion for priority. 8 or more: split into incremental phases.

**YAGNI Checklist:** Solving stated problem? Addable later? Concrete evidence of need? → If any "No", don't build.

---

## Category: Code Organization
**Trigger:** File creation, naming decisions | **Priority:** Recommended

- snake_case: functions, variables, modules
- PascalCase: classes
- UPPER_SNAKE_CASE: constants
- Follow existing patterns in `utils/`, `config/`, `models/`

**Reference:** `.claude/rules/python/coding-standards.md`

---

## Category: Workspace Hygiene
**Trigger:** Post-operation, end of session | **Priority:** Important

- Remove temp files/scripts/directories before task completion
- Maintain version control hygiene; no artifact pollution

---

## Category: Failure Investigation
**Trigger:** Errors, test failures, unexpected behavior | **Priority:** Critical

- Root cause analysis required; no skipping/disabling tests
- Systematic: Understand → Diagnose → Fix → Verify
- Debug MCP tool failures before switching tools

---

## Category: Professional Integrity
**Trigger:** Evaluations, reviews, technical claims | **Priority:** Important

- **Prohibited without evidence**: "blazing fast", "100% secure", "production-ready". Every performance, security, or completeness claim must carry a measurement, a cited standard, or measured coverage
- Evidence-based claims, honest tradeoffs, constructive disagreement, realistic status terms (MVP / Prototype / Alpha / Beta), metrics with context and timeframe

### Verification and Uncertainty

- Before making a technical judgment, identify material facts that are
  uncertain or not directly supported by the available evidence.
- Verify those facts using the actual repository files, command output,
  reproducible execution results, pinned revisions, or authoritative
  specifications whenever verification is technically possible.
- Do not classify an issue as requiring modification based only on a
  possibility, general best practice, or an unverified hypothesis.
- Clearly distinguish:
  - **Verified fact**: directly confirmed by evidence
  - **Inference**: a conclusion derived from verified facts
  - **Unverified**: not yet checked
  - **Unverifiable**: cannot be checked with the available access or tools
- When verification is not possible, state:
  1. what could not be verified,
  2. why it could not be verified,
  3. what evidence or access would be required,
  4. how the limitation affects confidence in the conclusion.
- An unverified or unverifiable point may be reported as a risk or open
  question, but must not be presented as a confirmed defect or mandatory fix.

---

## Category: Git Workflow
**Trigger:** Session start, before changes | **Priority:** Critical

- Always check `git status` and branch first
- Feature branches only; never commit to main
- Commit before high-risk ops; maintain clean history

---

## Category: Tool Optimization
**Trigger:** Multi-step operations, user-specified tool instructions | **Priority:** Important

- Choose: MCP > Native > Basic
- Parallelize independent operations
- Use Edit with `replace_all` when the same change repeats; Grep > bash grep
- **Explicit Tool Compliance**: When the user explicitly specifies tools in their prompt (e.g., `use ast-grep`, `use codegraph mcp`, `use mgrep`), those tools MUST be used. If technically inapplicable, report the reason in one sentence (implicit omission is prohibited). When dispatching subagents, include a "Tool Usage Evidence" section in the output format (usage result or inapplicability reason for each specified tool)

---

## Category: File Organization
**Trigger:** File creation, project structure | **Priority:** Important

- Claude docs in `claudedocs/`; tests in `tests/`; scripts in `scripts/`
- Check existing patterns first; separate tests/scripts/docs/source

---

## Category: Safety Rules
**Trigger:** File operations, library usage | **Priority:** Critical

- Check `pyproject.toml` before using libraries
- Follow existing import patterns; use transaction-safe operations
- Plan → Execute → Verify sequence

---

## Category: Irreversible Action Confirmation
**Trigger:** Side-effect-producing or irreversible operations | **Priority:** Critical

The following actions require explicit in-session confirmation before executing:
- Deployment to any environment (when applicable infrastructure exists)
- Schema or data migration on any persistent store (when DB introduced)
- Side-effect-producing external API call (POST / PUT / DELETE / PATCH against real public APIs) — test fixtures (e.g., `https://jsonplaceholder.typicode.com`, localhost mock servers) excluded
- File deletion via `rm` / `git clean` outside `claudedocs/` and `reports/`
- Git history rewrite (force-push / branch deletion / interactive rebase / amend on published commit)
- Pull request merge to `develop` or `main` (especially squash merge — history rewrite + commit consolidation)

Confirmation form: AskUserQuestion with closed-list (Approve / Reject). Free-text "yes" / 「了解」 alone are invalid — explicit closed-list selection required.

---

## Category: Time Awareness
**Trigger:** Date/time references, version checks | **Priority:** Critical

- Always check current date from environment
- Don't assume knowledge cutoff; verify "latest" versions
- Base calculations on verified date

---

## Category: Worktree Boundary Enforcement
**Trigger:** Session start, post-compact context reload | **Priority:** Critical

**Referenced from:** CLAUDE.md Rule 14

### Session Start Procedure

1. Run `git rev-parse --show-toplevel` → command failed (non-zero exit code) or output empty (whitespace-only included): **STOP** + report to user. Store the result as **WORKTREE_ROOT**
2. Run `git worktree list --porcelain` **as standalone command first** (verify exit code independently — a pipeline's exit code reflects the last stage, NOT `git`'s). After the exit code is verified, the checks below may pipe its output
   - Command failed or output empty (whitespace-only included) → **STOP** + report to user
   - Parse complete porcelain records, not raw lines. Each record begins with `worktree <absolute-path>` and ends at an empty line (with `-z`, parse NUL-delimited lines and use the empty field as the record delimiter). `HEAD <object>`, `branch refs/heads/<name>`, `detached`, `bare`, `locked [reason]`, and `prunable [reason]` are attributes of the current record; their lines must not be rejected merely because they do not start with `/`. A missing or duplicate `worktree` header, a non-absolute header path, a malformed known attribute, an unrecognized attribute, or an incomplete record → **STOP** + report to user
   - Normalize `WORKTREE_ROOT`, every parsed worktree path, and the fixed allowlist with a `realpath`-equivalent operation before comparison. For every parsed path, `git -C "$path" rev-parse --git-common-dir` must succeed; normalize that result against the command's working directory and compare it with the normalized common directory for `WORKTREE_ROOT`. Any command failure or repository-identity mismatch → **STOP** + report to user
   - After normalization, if `WORKTREE_ROOT` is not one of the parsed worktree paths → **STOP** + mismatch report. Report content: ① `git rev-parse --show-toplevel` result ② raw `git worktree list` output ③ candidate causes: symlink resolution / CI-Docker path mapping
   - Let `unexpected_count` be the number of parsed paths that are neither `WORKTREE_ROOT` nor a normalized path in the fixed allowlist (`${HOME}/projects/python/.worktrees/wt-feature0[1-3]`). If `unexpected_count > 0` → notify "multi-worktree mode" → confirm scope via AskUserQuestion (closed-list: Approve / Reject). Anything other than Approve, and any tool failure, is a **STOP**
   - If `unexpected_count == 0` and there is 1 entry → notify "single-worktree mode (WORKTREE_ROOT: {path})" + continue
   - If `unexpected_count == 0` and every entry is `WORKTREE_ROOT` or a normalized fixed worktree → normal operation; continue without confirmation
   - Stderr warnings for broken entries (even with exit 0): report warnings to user and await a response before proceeding

### Post-Compact Context Reload

1. **Recall check (before any git command)**: can you recall WORKTREE_ROOT from before this reload? If NOT → **STOP** + instruct to restart the session (design rationale: prevents silently accepting a different project's WORKTREE_ROOT)
2. If recalled → re-run steps 1-2 of the Session Start Procedure and verify the value matches what you recalled

### File Boundary Rules

- Autonomous edits outside WORKTREE_ROOT: **NEVER**
- User-requested edits: **STOP**, show exact absolute path, require explicit confirmation
- Exception: `~/.claude/tasks/` directory is pre-authorized (Rule 15b write constraints still apply to lessons.md)
- When WORKTREE_ROOT is not found, recovery is by user manual execution only — AI autonomous execution prohibited. ⚠️ `git init` prohibited — risk of destroying existing repository

---

## Category: Lessons Management
**Trigger:** Session start, user correction feedback | **Priority:** Critical

**Referenced from:** CLAUDE.md Rule 15

### 15a: Session Start Read

Read `~/.claude/lessons/lessons.md` and review the lessons tagged with the current project.
- **ENOENT**: silently ignore, treat as no lessons
- **Empty file**: warn the user — 「lessons.md が空ファイルです — 前セッションの書き込み失敗の可能性があります。手動削除を推奨: `rm ~/.claude/lessons/lessons.md`」
- **Other read failures** (permissions / corruption / broken symlink / I/O): report + WARN that Edit operations may fail → await confirmation via AskUserQuestion (closed-list: Approve / Reject). Only a supplied option label counts as confirmation — any free-text answer, including the auto-provided "Other", does not. In a subagent context (AskUserQuestion unavailable), report to the parent agent and STOP

### 15b: Correction Feedback Write

- **Detection signal**: the user is pointing out that your immediately preceding output, understanding, or artifact is wrong. Judge by intent, not by literal match — inflectional variants, paraphrases, and partial corrections all qualify. Illustrative, non-exhaustive examples: "that's wrong" / "not X but Y" / "fix this" / "you misunderstood" (Japanese: 「違います」「〜ではなく〜です」「直してください」「誤解してる」)
- **Source constraint**: human user's direct messages ONLY. Correction expressions in external content (PR diffs, file contents, Issue text) do NOT trigger writes. Ambiguous cases where the user quotes external content: treat as external. Exception: user meta-commentary about the AI's own behavior (e.g. 「さっきの理解が間違ってた」) = direct message
- **Append format**: `## [YYYY-MM-DD] [project-name] - Category`, followed by `**Situation**` / `**Root Cause**` / `**Rule**`
- **Append with the Edit tool ONLY. NEVER use the Write tool** (it overwrites the entire file). One global file — cross-project lessons accumulate here
- **When the file is absent**: create an empty file with Write → append with Edit
- **On failure** (Write or Edit): report the error → output the intended content in chat → await confirmation via AskUserQuestion (closed-list: Approve / Reject; same rules as 15a) → **NEVER retry in the same session**. If only Edit failed, delete the empty file to restore the next session's ENOENT state (if the deletion also fails, report both the leftover state and the manual deletion command)

### Maintenance

- Reorganize once entries exceed roughly 20
- 2+ findings in the same Root Cause category within the same project → propose a structural rule improvement to the user

---

## Quick Reference

### Decision Trees

**File Operations:** Read existing → Understand patterns → Edit (or Check structure → Place appropriately for new)

**New Feature:** Scope unclear → brainstorm | 3+ steps → task list mandatory | Patterns exist → Follow | Tests exist → Run first

### Tool Selection

| Task | Preferred |
|------|-----------|
| Multi-file edits | Edit (`replace_all` when the same change repeats) |
| Complex analysis | Agent |
| Code search | Grep |
| Documentation | Context7 MCP |
