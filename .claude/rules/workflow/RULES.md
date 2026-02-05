# Claude Code Behavioral Rules

## Description
Practical rules for **api-test-devops-portfolio** project development with Claude Code.

## Project Context

**This document contains project-specific behavioral rules for api-test-devops-portfolio.**

**Tech Stack:**
- Python 3.12 + httpx + pytest + Pydantic Settings
- Quality tools: ruff (linter) + mypy (type checker)
- Package manager: uv
- CI/CD: GitHub Actions

**Priority Hierarchy:**
1. **CLAUDE.md** (project root) - highest priority
2. **This RULES.md** - behavioral patterns
3. **PRINCIPLES.md** - foundational principles

**Related Serena Memories (on-demand reference):**
- `@memory:implementation_quality_gates` - detailed gate specifications
- `@memory:coding_standards` - Python coding conventions
- `@memory:command_usage_guide` - skill/command reference

---

## Priority System

### Levels
- **Critical:** Security, data safety, production environment disruption - never compromise.
- **Important:** Quality, maintainability, professionalism - strongly recommended.
- **Recommended:** Optimization, style, best practices - apply when practical.

### Conflict Resolution
1. **Safety First:** Security/data rules always take precedence.
2. **Scope > Features:** Build only what is asked for > completing everything.
3. **Quality > Speed:** Except in truly urgent cases.
4. **Context Matters:** Prototypes and production have different requirements.

---

## Category: Workflow Rules
**Trigger:** All development tasks
**Priority:** Important

- Follow the pattern: Understand → Plan (including parallelization analysis) → TodoWrite (3+ tasks) → Execute → Track → Verify.
- Batch operations: Always default to parallelizing tool calls unless there are dependencies.
- Validation gate: Always validate before execution and confirm after completion.
- Discovery first: Complete a project-wide analysis before making systemic changes.
- Session lifecycle: Initialize context, create periodic checkpoints, and save before exiting.
- Session pattern: Load context → Work → Checkpoint (every 30 mins) → Save context.
- Checkpoint triggers: On task completion, at 30-minute intervals, before high-risk operations.
- **Note**: If superclaude plugin available, use `/sc:load` and `/sc:save` for enhanced context management.

**Example (Good):** Plan → TodoWrite → Execute → Verify
**Example (Bad):** Jumping directly into implementation without a plan.

---

## Category: Task Completion Self-Review
**Trigger:** TodoWrite task completion
**Priority:** Important

### Learning Phase (Current Default)
- Execute self-review after each TodoWrite task completion.
- Applies to all execution methods including superpowers execute-plan.
- Goal: Build review habits, learn from error patterns early.
- **Note**: If reflexion plugin available, use `/reflexion:reflect` for structured self-review.

### Execution Flow
1. TodoWrite Task completed
2. Run `/reflexion:reflect`
3. No issues → proceed to next task
4. Issues found → fix before proceeding

### Superpowers Integration
- **execute-plan**: Reflect after each task within batch (before batch completion).
- **subagent-driven-development**: Supplement existing 2-stage review as needed.

### Production Phase (Future Transition)
Execute reflect only when:
- 3+ files changed
- Security/API contract changes
- Self-assessment < 90% confidence
- New patterns or unfamiliar domains

**Example (Good):** Auth logic implementation → self-review required
**Example (Bad):** README typo fix → skip review (unnecessary overhead)

---

## Category: Planning Efficiency
**Trigger:** All planning phases, TodoWrite operations, multi-step tasks
**Priority:** Critical

- Parallelization analysis: Identify which operations can run in parallel during planning.
- Tool optimization plan: Plan the optimal combination of MCP servers and batch operations.
- Dependency mapping: Separate sequential dependencies from parallelizable tasks.
- Resource estimation: Consider token usage and execution time.
- Efficiency metrics: State expected parallelization benefit (e.g. "3 parallel ops = 60% time savings").

**Example (Good):** Plan: 1) Parallel [Read 5 files] → 2) Sequential [Analyze] → 3) Parallel [Edit all files]
**Example (Bad):** Plan: Read file1 → Read file2 → Analyze → Edit file1 → Edit file2

---

## Category: Implementation Integrity
**Trigger:** Feature creation, function creation, code generation
**Priority:** Important

### Quality Gate Requirements (All Must Pass)

Before considering any implementation complete, verify all 4 quality gates:

**Gate 1: Tests Pass**
- All test cases pass (0 failed)
- Coverage meets phase target
- Test markers pass (unit, integration)

**Gate 2: Linter Pass**
- Linter detects 0 errors
- Auto-fixable warnings resolved
- Style guidelines enforced

**Gate 3: Type Check Pass**
- Type checker detects 0 errors
- All public functions have type hints/annotations
- Return types specified

**Gate 4: Version Control**
- Changes committed to git
- Meaningful commit message (conventional commits)
- No untracked implementation artifacts

**Gate Failure Recovery**:
- Gate 1 fail → Run `pytest -vv` for detailed failure analysis
- Gate 2 fail → Run `ruff check --fix .` for auto-fixes
- Gate 3 fail → Add type hints incrementally, verify with `mypy --strict`
- Gate 4 fail → Stage changes with `git add` + commit with conventional format

**Integrated Verification (One-liner)**:
```bash
# Project standard verification
uv run pytest --cov-fail-under=[target] && uv run ruff check . && uv run mypy utils/ config/ models/ && git status
# Note: [target] = phase-specific coverage goal. See @memory:implementation_quality_gates
```

**Implementation Activity Recognition**:
- Recognized: All 4 gates pass + committed + no TODO in production paths
- Not Recognized: Tests failing/skipped, linter/type errors, uncommitted, stub implementations

**Project-Specific Targets**: Reference `@memory:implementation_quality_gates`

**Example (Good):**
```python
def calculate_tax(price: float, tax_rate: float) -> float:
    """Calculate tax with validation."""
    if price < 0 or tax_rate < 0:
        raise ValueError("Must be non-negative")
    return price * tax_rate
# All gates pass
```

**Example (Bad):**
```python
def calculate_tax(price, tax_rate):  # No type hints (Gate 3 fail)
    # TODO: add validation  # TODO comment (Gate 4 fail)
    return price * tax_rate
```

**Detection Command:**
```bash
# Check TODO in production code
grep -r "TODO" --include="*.py" --exclude-dir={tests,docs} .

# Check stub implementations
grep -r "raise NotImplementedError\|throw new Error.*Not implemented" .
```

---

## Category: Scope Discipline
**Trigger:** Ambiguous requirements, feature extensions, architecture decisions
**Priority:** Important

### Scope Assessment Framework

Before implementation, analyze requirement complexity:

**1. Count Explicit Requirements**
- Parse user request for distinct feature items
- Separate must-have from nice-to-have
- Identify implied vs stated requirements

**Requirement Counting Rules**:
- Distinct user-facing feature = 1 item
- Implementation details of same feature = sub-items (don't count separately)
- Example: "User auth with Google OAuth" = 1 item (not 3: login + OAuth + session)
- Example: "Add caching" = 1 item (not 3: Redis setup + cache logic + invalidation)

**2. Scope Decision Matrix**

| Requirement Count | Decision | Action |
|------------------|----------|--------|
| <= 3 items | Immediate Implementation | Build all requested features |
| 4-7 items | MVP Consideration | Use AskUserQuestion to clarify priority |
| >= 8 items | Mandatory MVP Split | Break into Phase 1-3, deliver incrementally |

**3. Complexity Multipliers** (adjust count):
- Architecture changes: +2
- External integrations: +1 each
- Security requirements: +1
- Performance targets: +1

**Multiplier Example**:
```
Request: "Add real-time notifications"
- Base: 1 item (notification UI)
- +2 for architecture (WebSocket server, pub/sub pattern)
- +1 for integration (email/SMS providers)
- Total: 4 items → MVP Consideration zone → AskUserQuestion
```

**Implementation Guidelines**:

**For <= 3 items**:
```
User: "Add error retry logic to API client"
Action: Implement exponential backoff + retry count + logging
Scope: Exactly what was asked, no more
```

**For 4-7 items**:
```
User: "Build dashboard with profile, settings, activity log, notifications"
Action: AskUserQuestion - "Prioritize in phases?
  Phase 1: Profile + Settings (core)
  Phase 2: Activity log + Notifications (enhancements)"
Await: User clarification before proceeding
```

**For >= 8 items**:
```
User: "Build complete e-commerce system"
Action: Auto-propose 3-phase MVP
  Phase 1: Cart + Checkout + Payment (minimum viable)
  Phase 2: Inventory + Orders + Shipping (operations)
  Phase 3: Analytics + Reviews (enhancements)
Deliver: Phase 1 first, iterate after feedback
```

**YAGNI Enforcement Checklist**:
- [ ] Solving a stated problem?
- [ ] Can be added later without refactoring?
- [ ] Concrete evidence of need?

If any "No" → Don't build it

**Example (Good):** "Add user auth" → Login + password validation + session management (3 items)
**Example (Bad):** "Add user auth" → Login + registration + reset + 2FA + OAuth + SAML (7+ items, YAGNI violation)

**Detection Command:**
```bash
# Review recent commits for scope creep
git log --oneline --since="1 week ago" | grep -E "feat:|add:" | wc -l
# If > 10 features/week in solo project → possible over-engineering
```

---

## Category: Code Organization
**Trigger:** File creation, project structure, naming decisions
**Priority:** Recommended

- Use snake_case for functions, variables, modules (Python convention)
- Use PascalCase for classes
- Use UPPER_SNAKE_CASE for constants
- Descriptive names for clarity
- Logical directory structure by feature/domain
- Follow existing project patterns in `utils/`, `config/`, `models/`

**Example (Good):** `get_user_data()`, `user_data.py`, `UserResponse`
**Example (Bad):** `getUserData()`, `userData.py`, `user_response`

**Reference**: `@memory:coding_standards` for detailed conventions

---

## Category: Workspace Hygiene
**Trigger:** Post-operation, end of session, temporary file creation
**Priority:** Important

- Post-operation cleanup: Remove temporary files, scripts, directories.
- No artifact pollution.
- Clean up temp files before task completion.
- Maintain a professional, uncluttered workspace.
- End-of-session cleanup required.
- Maintain version control hygiene.
- Manage resources to avoid workspace bloat.

**Example (Good):** Run `rm temp_script.py` after use.
**Example (Bad):** Leaving `debug.sh`, `test.log`, or `temp/` directories.

---

## Category: Failure Investigation
**Trigger:** Errors, test failures, unexpected behavior, tool failures
**Priority:** Critical

- Root cause analysis required.
- No skipping or disabling tests.
- No skipping validation.
- Perform systematic debugging.
- Fix underlying issues, not symptoms.
- Debug MCP tool failures before switching.
- Maintain quality integrity.
- Systematic problem solving: Understand → Diagnose → Fix → Verify.

**Example (Good):** Analyze stack trace → Identify cause → Fix properly.
**Example (Bad):** Commenting out failing tests.

**Detection Command:**
`grep -r "skip\|disable\|TODO" tests/`

---

## Category: Professional Integrity
**Trigger:** Evaluations, reviews, recommendations, technical claims
**Priority:** Important

### Prohibited Marketing Language

Never use these terms without evidence:

**Performance Claims** (without benchmarks):
- "blazing fast", "lightning fast", "instant"
- "zero latency", "real-time" (for non-RT systems)
- "highly optimized", "maximum performance"

**Quality Claims** (without verification):
- "100% secure", "completely safe", "unhackable"
- "bug-free", "production-ready" (for untested code)
- "enterprise-grade", "world-class" (unless required by context)

**Impact Claims** (without data):
- "revolutionary", "game-changing", "groundbreaking"
- "cutting-edge", "state-of-the-art" (for standard practices)
- "industry-leading", "best-in-class"

**Superlatives** (avoid unless provable):
- "perfect solution", "ultimate", "ideal"
- "flawless", "seamless", "effortless"

### Evidence-Based Alternatives

| Avoid | Use Instead |
|-------|-------------|
| "blazing fast" | "50ms response time (benchmarked)" |
| "100% secure" | "implements OWASP Top 10 mitigations" |
| "production-ready" | "passes 85% test coverage, no critical bugs" |
| "revolutionary" | "introduces async processing (30% faster than v1)" |
| "enterprise-grade" | "supports 10k concurrent users (load tested)" |
| "perfect solution" | "meets requirements with tradeoffs: ..." |

### Professional Communication Rules

**1. Evidence-Based Claims**:
```
Bad: "This caching strategy is amazing and will solve all issues!"
Good: "Redis caching reduced response time from 450ms to 85ms (81% improvement)"
```

**2. Honest Tradeoffs**:
```
Bad: "Use microservices for everything!"
Good: "Microservices offer scalability but increase complexity. For MVP, monolith is simpler."
```

**3. Constructive Disagreement**:
```
Bad: "This approach is wrong and will never work."
Good: "This may face scalability issues at 10k users. Alternative: connection pooling."
```

**4. Realistic Status Terms**:
- "MVP" - Minimum viable product (limited features)
- "Prototype" - Proof of concept (not production)
- "Alpha" - Early testing (unstable)
- "Beta" - Feature-complete (testing)
- "Untested" - No test coverage
- "Work in Progress" - Incomplete

**5. Metric Accuracy** (provide context with timeframe):
```
Bad: "95% test coverage" (lines only, no date)
Good: "95% line coverage, 78% branch coverage (pytest 8.0, 2024-11-14)"

Bad: "Handles 10k req/s" (on what hardware?)
Good: "10k req/s on 4-core CPU, 8GB RAM (AWS t3.xlarge, 2024-11-14)"
```

**Detection via Pre-commit Hook** (recommended):
```bash
# .git/hooks/pre-commit
if VIOLATIONS=$(git diff --cached | grep -iE "blazing fast|100% secure|revolutionary|game-changing|perfect solution"); then
  echo "❌ Marketing language detected:"
  echo "$VIOLATIONS"
  echo "💡 Suggested fix: Replace with benchmarked metrics (see RULES.md line 287)"
  echo "Run: grep -rE 'blazing fast|100% secure' . to find instances"
  exit 1
fi
```

**Exceptions** (when marketing language is acceptable):
- Marketing materials in `docs/marketing/` or `blog/` → allowed with disclaimer
- User-facing copy (landing pages, emails) → allowed if backed by `docs/evidence/`
- Technical docs, code comments, commit messages → no exceptions

**Manual Detection**:
```bash
# Scan for prohibited terms
grep -rE "blazing fast|100% secure|revolutionary|game-changing|perfect solution" \
  --include="*.md" --include="*.py" --include="*.js" \
  --exclude-dir={node_modules,venv,.git} .
```

**Example (Good):**
```
Performance Improvements:
- API response: 450ms → 85ms (81% improvement via connection pooling)
- Load test: sustained 5k req/s for 10min (AWS t3.xlarge)
- Tradeoffs: +200MB memory (Redis cache), +1 dependency
```

**Example (Bad):**
```
Revolutionary Performance Boost!
Blazing fast optimization delivers enterprise-grade performance!
100% production-ready. Perfect architecture for world-class systems!
```

---

## Category: Git Workflow
**Trigger:** Session start, before changes, before high-risk operations
**Priority:** Critical

- Always check `git status` and branch.
- Use feature branches; never commit to main.
- Commit frequently with meaningful messages.
- Review with `git diff` before staging.
- Commit before high-risk ops.
- Branch for experiments.
- Maintain clean commit history.
- Non-destructive workflow (rollback ready).

**Example (Good):** `git checkout -b feature/auth → work → commit → PR`
**Example (Bad):** Working directly on main.

**Detection Command:**
`git branch` should show a feature branch, not main/master.

---

## Category: Tool Optimization
**Trigger:** Multi-step operations, performance requirements, complex tasks
**Priority:** Recommended

- Choose optimal tool (MCP > Native > Basic).
- Parallelize independent operations.
- Use task agents for 3+ step operations.
- Utilize specialized MCP servers (e.g. morphllm).
- Use batch operations like MultiEdit.
- Prefer powerful search tools (Grep > bash grep).
- Prioritize efficiency and speed.
- Match tools to their intended domain.

**Example (Good):** Using MultiEdit for 3+ file changes.
**Example (Bad):** Sequential edits, using bash grep.

---

## Category: File Organization
**Trigger:** File creation, project structure, documentation
**Priority:** Important

- Think before writing new files.
- Place Claude-specific docs in `claudedocs/`.
- Place tests in `tests/`, `__tests__/`, or `test/`.
- Place scripts in `scripts/`, `tools/`, or `bin/`.
- Check existing patterns first.
- Don’t scatter tests next to source.
- Avoid random scripts in root.
- Separate tests, scripts, docs, and source.

**Example (Good):** `tests/auth.test.js`, `scripts/deploy.sh`, `claudedocs/analysis.md`
**Example (Bad):** `auth.test.js` next to `auth.js`, `debug.sh` in root.

---

## Category: Safety Rules
**Trigger:** File operations, library usage, codebase changes
**Priority:** Critical

- Check `pyproject.toml` before using libraries.
- Follow existing import patterns in `utils/`, `config/`, `models/`.
- Use transaction-safe operations.
- Follow Plan → Execute → Verify sequence.

**Example (Good):** Check dependencies → Follow patterns → Execute safely.
**Example (Bad):** Ignoring conventions, unplanned changes.

---

## Category: Time Awareness
**Trigger:** Date/time references, version checks, deadlines, “latest” keyword
**Priority:** Critical

- Always check current date from environment.
- Don’t assume knowledge cutoff.
- Explicitly state date/time sources.
- Verify “latest” versions against current date.
- Base time calculations on verified date.

**Example (Good):** “Today is 2025-08-15, so Q3 deadline is…”
**Example (Bad):** “Since it’s January 2025…”

**Detection Command:**
Date reference without prior env verification.

---

## Quick Reference

### Decision Tree: Before File Operations
**Prompt:** Is a file operation needed?
- If Write/Edit:
  1. Read existing file.
  2. Understand patterns.
  3. Edit.
- If Create New:
  1. Check existing structure.
  2. Place appropriately.

**Safety Check:** Use absolute paths only. No auto-commits.

---

### Decision Tree: Starting a New Feature
**Prompt:** Is it a new feature request?
- If scope unclear → Use brainstorming mode.
- If more than 3 steps → TodoWrite is mandatory.
- If patterns exist → Follow strictly.
- If tests exist → Run them first.

**Rule:** Check `pyproject.toml` for dependencies before proceeding.

---

### Tool Selection Matrix
| From | To |
|------|----|
| Multiple file edits | MultiEdit > individual Edit |
| Complex analysis | Task Agent > native reasoning |
| Code search | Grep > bash grep |
| UI components | Magic MCP > manual coding |
| Documentation | Context7 MCP > web search |
| Browser testing | Playwright MCP > unit tests |

---

### Priority Actions

#### CRITICAL (Never Compromise)
- `git status && git branch` before starting
- Read before write/edit
- Feature branches only
- Root cause analysis
- Use absolute paths; no auto-commits

#### IMPORTANT (Strongly Recommended)
- Use TodoWrite for 3+ step tasks
- Complete all implementations you start
- Build only what is asked for (MVP first)
- Use professional, non-marketing language
- Clean workspace (delete temporary files)

#### RECOMMENDED (Apply When Practical)
- Prefer parallel over sequential operations
- Use descriptive naming conventions
- Prefer MCP tools
- Batch operations when possible
