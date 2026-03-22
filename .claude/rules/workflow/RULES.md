# Claude Code Behavioral Rules

## Description
Practical rules for **api-test-devops-portfolio** project development with Claude Code.

## Project Context

**Tech Stack:** Python 3.14 + httpx + pytest + Pydantic Settings | ruff + mypy | uv | GitHub Actions

**Priority Hierarchy:**
1. **CLAUDE.md** (project root) - highest priority
2. **This RULES.md** - behavioral patterns
3. **PRINCIPLES.md** - foundational principles

**Related Serena Memories:** `@memory:implementation_quality_gates`, `@memory:command_usage_guide`
**Coding Standards:** `.claude/rules/python/coding-standards.md`

---

## Priority System

**Levels:** Critical (security/data safety) | Important (quality/maintainability) | Recommended (optimization/style)

**Conflict Resolution:** Safety First > Scope > Features > Quality > Speed

---

## Category: Workflow Rules
**Trigger:** All development tasks | **Priority:** Important

- Follow: Understand → Plan (parallelization) → TodoWrite (3+ tasks) → Execute → Track → Verify
- Batch independent operations; validate before/after execution
- One task per subagent invocation; avoid multi-task delegation to maintain context focus; if a subagent reports failure or partial completion (any task where not all specified artifacts have reached their expected final state), stop and report to the user instead of silently continuing.
- This applies to task delegation; reflexion retry logic in CLAUDE.md governs implementation quality checks.
- Within a single agent turn, parallel *tool calls* (Read, Grep, Bash, Task etc.) remain encouraged (see "Batch independent operations" above); this is distinct from delegating multiple unrelated tasks to a single subagent.
- Session pattern: Load → Work → Checkpoint (30 min) → Save
- Use `/sc:load` and `/sc:save` if superclaude available
- **Parallel Dispatch Rule** (extension of "One task per subagent invocation" above — each agent still handles exactly one task): When 2+ independent TodoList tasks exist, dispatch each as a separate Task tool invocation (parallel recommended)
  - Independence criteria (all must be satisfied):
    1. No output dependency between tasks (no A→B ordering constraint)
    2. No simultaneous edits to the same file
    3. No conflicting **writes** to shared resources (examples: conftest.py, pyproject.toml, uv.lock, config files, .env files — read-only access does not count as conflicting; when write conflicts cannot be ruled out, treat as shared)
  - Worktree isolation: instruct each agent to use fixed worktrees at `${HOME}/projects/python/.worktrees/wt-feature0[1-3]`（個人環境ごとにカスタマイズ）
  - Exception: if one task has 3x+ more TodoWrite sub-items (or estimated file changes) than the other, sequential execution is acceptable
  - **GSD exception**: When `/gsd:execute-phase` is active, skip this rule for wave-internal tasks only (GSD manages its own wave-based parallel execution). Apply this rule normally to independent tasks that arise after wave completion. **Decision criteria**: Treat as wave-internal only when `/gsd:execute-phase` execution is confirmed in the conversation context. If not confirmable, the fail-safe is to **stop and report to the user** (applying Rule 12 is prohibited — it would spawn parallel subagents mid-GSD-session, risking duplicate task execution). **After context compression (compact)**: wave state becomes unrecoverable — stop and report to user; resume only after re-establishing the session with `/gsd:resume-work`.
  - On failure: if **any** agent reports failure or partial completion, the parent agent must (1) allow already-running invocations to complete (Task tool has no cancel API), (2) collect and log agent statuses (success/failure/unknown), and (3) report full status summary to user before further action
  - Silent continuation after ambiguous/empty results is prohibited
  - On completion: after all parallel agents complete, the parent agent must explicitly verify that each artifact exists in its expected final state before marking the parent task complete
  - Context refinement (parent agent determines applicability before dispatch):
    **Applicability check**: does the task prompt contain 1+ specific file paths (paths resolving to individual files with extension; glob patterns like `utils/*.py` and directory paths like `utils/` count as NO)?
    - YES: Context refinement is optional (when skipping, record reason as `[SKIP: <reason>]` in agent response)
    - NO (includes ambiguous cases): Context refinement is required
    When applicable (YES case where agent opts in, or NO case where it is required), include `Skill(iterative-retrieval)` skill instructions
    (dispatch → evaluate → refine → loop, max 3 cycles per task invocation) in the agent prompt
    - Agent failure definition: empty response, timeout, error message, or partial response (investigation stopped mid-way) — all count as failure; failed cycle output is excluded from convergence evaluation (i.e., not used as comparison baseline for file list stability check) but may inform the next cycle's investigation scope
    - Failed cycles consume 1 cycle each (infinite retry prohibited)
    - Task restart (= new Task tool invocation issued) resets the cycle counter
    - **Convergence criteria**: The impact scope boundary is finalized — the list of investigated files is stable (unchanged from the previous successful cycle) and no further investigation is needed
    - Fallback triggers when ANY of: (a) 3 cycles reached, OR (b) 2 consecutive failures (consecutive = two immediately sequential cycles both counted as failed; a successful or partially-successful cycle resets the consecutive-failure counter to 0)
      Report to parent agent: (i) cycles consumed (ii) context summary per cycle (iii) unresolved gap list (iv) which condition blocked convergence
      Parent agent reports to user and awaits explicit user direction before proceeding

**Task Classification**: Before dispatching, classify the task type:
- **Implementation** : code writing, feature development, bug fixes, test authoring
- **Investigation** : research, analysis, debugging, codebase exploration
- **Review** : code review, PR review, security audit, documentation review
- **Design** : architecture design, API spec, system planning

**Agent Selection**: Map task type to agents (reference: `~/.claude/docs/AGENTS_CATALOG.md`):

| Task Type | Recommended Agents |
|-----------|-------------------|
| Implementation: Python/Test | `python-expert`, `debugger`, `api-testing` |
| Implementation: Refactoring | `refactoring-expert`, `debugger` |
| Implementation: Docker/Infra | `docker-devops`, `devops-engineer` |
| Implementation: CI/CD | `ci/cd-pipeline`, `ci/cd-github-engineer`, `devops-engineer` |
| Investigation | `researcher`, `Explore` (built-in Task subagent) |
| Review | `code-review:*`, `pr-review-toolkit:*` (parallel) |
| Design | `system-architect`, `backend-architect`, `devops-architect` |

**Dispatch Automation**: When 2+ independent tasks exist post-classification, invoke `Skill(superpowers:subagent-driven-development)` skill via Skill tool. After all agents complete and all TodoWrite tasks are marked done, `Skill(superpowers:verification-before-completion)` → `Skill(reflexion:reflect)` runs per CLAUDE.md Rule 11 ("ALWAYS after completing all tasks in `todowrite`, Use Skill tool to run `Skill(superpowers:verification-before-completion)` → then `Skill(reflexion:reflect)`") (this dispatch context already satisfies Rule 11 at the parent agent level — no duplicate call needed within subagents). Subagent context disambiguation: when a subagent cannot determine its own context (Dispatch Automation vs GSD wave-internal), execute `Skill(superpowers:verification-before-completion)` as a failsafe (false-negative prohibited). **Detection criteria for "cannot determine"**: a subagent is in undetermined context when ALL of: (1) its task prompt contains no reference to `/gsd:execute-phase`, AND (2) no `/gsd:execute-phase` execution record is visible in the subagent's conversation context — when both conditions are met, treat as Dispatch Automation context and execute verification. **Context compression exception (GSD exception priority)**: If the two conditions above are met AND there are signs of context compression (e.g., the task is GSD-related — references GSD phases, files, or workflows — but no `/gsd:execute-phase` context is present), GSD exception takes priority: **STOP + report to user** (do not treat as Dispatch Automation). Rationale: context compression may have erased GSD wave state; continuing as Dispatch Automation risks duplicate task execution. On verification failure (i.e., `Skill(superpowers:verification-before-completion)` reports incomplete work): apply CLAUDE.md Step 4 retry policy (max 3 retries; report to user and stop on 4th consecutive failure — counter resets on success).

**Good:** Plan → TodoWrite → Execute → Verify | **Bad:** Jump to implementation

**Reference:** `api-specification-check.md`, `execution-efficiency.md`

---

## Category: Task Management (Persistent Layer)
**Trigger:** Multi-session or large-scale tasks | **Priority:** Important

For large-scale or multi-session tasks,
record plans in `~/.claude/tasks/todo.md` (complements the ephemeral TodoWrite tool):
1. **Plan First**: Write a checkable item list before starting
2. **Verify Plan**: Align with the user before implementation
3. **Track Progress**: Mark items as complete
4. **Document Results**: Append review section after completion
5. **Capture Lessons**: Update `~/.claude/tasks/lessons.md` after any corrections

Usage distinction:
- TodoWrite = in-session UI display (unchanged)
- `~/.claude/tasks/todo.md` = persistent record for large tasks spanning sessions

**Reference:** CLAUDE.md Section「🔄 開発ワークフロー」Step 0（全体開発ワークフローとの統合コンテキスト）

---

## Category: Task Completion Self-Review
**Trigger:** TodoWrite task completion | **Priority:** Important

**Learning Phase:** Self-review after each task: `Skill(superpowers:verification-before-completion)` → `Skill(reflexion:reflect)`. Fix issues before proceeding.

**Production Phase:** Review only when: 3+ files changed, security/API changes, confidence < 90%, new patterns.

---

## Category: Planning Efficiency
**Trigger:** Planning phases, TodoWrite, multi-step tasks | **Priority:** Critical

- Identify parallel vs sequential operations during planning
- Map dependencies; estimate resources; state efficiency metrics
- When plan doc needed: create in claudedocs/plans/ per PLANS.md §使用閾値
- Record AskUserQuestion results and design decisions in Decision Log (see PLANS.md)

**Reference:** `execution-efficiency.md` (execution details) | `PLANS.md` (plan template)

---

## Category: Implementation Integrity
**Trigger:** Feature/function creation, code generation | **Priority:** Important

### Quality Gates (All Must Pass)

| Gate | Check | Recovery |
|------|-------|----------|
| 1: Tests | All pass, coverage target met | `pytest -vv` |
| 2: Linter | 0 errors | `ruff check --fix .` |
| 3: Types | 0 errors, all hints present | `mypy --strict` |
| 4: VCS | Committed with conventional message | `git add` + `Skill(commit)` |

**Verification:**
```bash
uv run pytest --cov-fail-under=[target] && uv run ruff check . && uv run mypy utils/ config/ models/ && git status
```

**Reference:** `@memory:implementation_quality_gates`, `api-specification-check.md`

---

## Category: Scope Discipline
**Trigger:** Ambiguous requirements, feature extensions | **Priority:** Important

**Requirement Counting:** Distinct user-facing feature = 1 item. Implementation details = sub-items.

| Count | Decision | Action |
|-------|----------|--------|
| <= 3 | Implement | Build all requested |
| 4-7 | MVP Consider | AskUserQuestion for priority |
| >= 8 | Mandatory Split | Phase 1-3 incremental |

**Multipliers:** Architecture (+2), External integration (+1 each), Security (+1), Performance (+1)

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

**Prohibited without evidence:** "blazing fast", "100% secure", "revolutionary", "enterprise-grade", "perfect solution"

**Evidence-Based Alternatives:**

| Avoid | Use Instead |
|-------|-------------|
| "blazing fast" | "50ms response time (benchmarked)" |
| "100% secure" | "implements OWASP Top 10 mitigations" |
| "production-ready" | "passes 85% test coverage, no critical bugs" |

**Rules:** Evidence-based claims, honest tradeoffs, constructive disagreement, realistic status terms (MVP/Prototype/Alpha/Beta), metrics with context and timeframe.

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
- Use MultiEdit for 3+ file changes; Grep > bash grep
- **Explicit Tool Compliance**: When the user explicitly specifies tools in their prompt (e.g., `use ast-grep`, `use CodeGraphContext mcp`, `use mgrep`), those tools MUST be used. If technically inapplicable, report the reason in one sentence (implicit omission is prohibited). When dispatching subagents, include a "Tool Usage Evidence" section in the output format (usage result or inapplicability reason for each specified tool)

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

## Category: Time Awareness
**Trigger:** Date/time references, version checks | **Priority:** Critical

- Always check current date from environment
- Don't assume knowledge cutoff; verify "latest" versions
- Base calculations on verified date

---

## Quick Reference

### Decision Trees

**File Operations:** Read existing → Understand patterns → Edit (or Check structure → Place appropriately for new)

**New Feature:** Scope unclear → brainstorm | 3+ steps → TodoWrite mandatory | Patterns exist → Follow | Tests exist → Run first

### Tool Selection

| Task | Preferred |
|------|-----------|
| Multi-file edits | MultiEdit |
| Complex analysis | Task Agent |
| Code search | Grep |
| Documentation | Context7 MCP |

### Priority Actions

**CRITICAL:** `git status && git branch` first | Read before write | Feature branches only | Root cause analysis

**IMPORTANT:** TodoWrite for 3+ steps | Build only what asked (MVP) | Professional language | Clean workspace

**RECOMMENDED:** Parallel > sequential | Descriptive naming | MCP tools | Batch operations
