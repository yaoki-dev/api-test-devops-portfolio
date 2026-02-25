# Claude Code Behavioral Rules

## Description
Practical rules for **api-test-devops-portfolio** project development with Claude Code.

## Project Context

**Tech Stack:** Python 3.13 + httpx + pytest + Pydantic Settings | ruff + mypy | uv | GitHub Actions

**Priority Hierarchy:**
1. **CLAUDE.md** (project root) - highest priority
2. **This RULES.md** - behavioral patterns
3. **PRINCIPLES.md** - foundational principles

**Related Serena Memories:** `@memory:implementation_quality_gates`, `@memory:coding_standards`, `@memory:command_usage_guide`

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
- **Parallel Dispatch Rule**: When 2+ independent TodoList tasks exist, dispatch each as a separate Task tool invocation (parallel recommended)
  - Independence criteria (all must be satisfied): 1. No output dependency between tasks (no A→B ordering constraint) 2. No simultaneous edits to the same file 3. No conflicting writes to shared resources (conftest.py, pyproject.toml, config files)
  - Worktree isolation: instruct each agent to invoke `/using-git-worktrees` skill in their prompt
  - Exception: if one task is 3x+ larger than the other, sequential execution is acceptable
  - On failure: apply existing rule "stop and report to the user"

**Good:** Plan → TodoWrite → Execute → Verify | **Bad:** Jump to implementation

**Reference:** `api-specification-check.md`, `execution-efficiency.md`

---

## Category: Task Completion Self-Review
**Trigger:** TodoWrite task completion | **Priority:** Important

**Learning Phase:** Self-review after each task using `/reflexion:reflect`. Fix issues before proceeding.

**Production Phase:** Review only when: 3+ files changed, security/API changes, confidence < 90%, new patterns.

---

## Category: Planning Efficiency
**Trigger:** Planning phases, TodoWrite, multi-step tasks | **Priority:** Critical

- Identify parallel vs sequential operations during planning
- Map dependencies; estimate resources; state efficiency metrics

**Reference:** `execution-efficiency.md`

---

## Category: Implementation Integrity
**Trigger:** Feature/function creation, code generation | **Priority:** Important

### Quality Gates (All Must Pass)

| Gate | Check | Recovery |
|------|-------|----------|
| 1: Tests | All pass, coverage target met | `pytest -vv` |
| 2: Linter | 0 errors | `ruff check --fix .` |
| 3: Types | 0 errors, all hints present | `mypy --strict` |
| 4: VCS | Committed with conventional message | `git add` + `/commit` |

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

**Reference:** `@memory:coding_standards`

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
**Trigger:** Multi-step operations | **Priority:** Recommended

- Choose: MCP > Native > Basic
- Parallelize independent operations
- Use MultiEdit for 3+ file changes; Grep > bash grep

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
