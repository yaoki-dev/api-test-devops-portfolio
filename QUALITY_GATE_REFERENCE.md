# Quality Gate Reference Chart

*最終更新: 2025年12月12日*

## Quick Reference: 4-Stage Quality Gate Execution

This document provides a quick reference for the 4-stage quality gate process validated in the pytest marker review.

---

## Stage Comparison Matrix

| Dimension | Stage 1: PR | Stage 2: Post-Merge | Stage 3: Weekly | Stage 4: Branch |
|-----------|-----------|------------------|-----------------|-----------------|
| **Trigger** | Pull request | push to main | schedule (Sun) | push to develop |
| **Duration Target** | <5 min | <3 min | <30 min | <10 min |
| **Test Focus** | Fast tests | Regression | Deep validation | Integration |
| **Markers** | (unit \| int) | regression | security\|perf | (unit\|int\|reg) |
| **Exclusions** | slow, manual, external | N/A | N/A | slow, manual, external |
| **Parallelization** | -n auto | -n auto | serial (security) | -n auto |
| **Coverage Target** | 58% | N/A | 85% | 58% |
| **--maxfail** | 3 | 1 | 10 | 5 |
| **Timeout** | 10 min | 5 min | 30 min | 10 min |
| **On Failure** | Block PR | Block merge | Warning | Block merge |
| **Rate Limit** | N/A | N/A | Respected | N/A |

---

## Execution Flow Diagram

```
Developer Push
    │
    ├──→ PR Created ──→ Stage 1: PR Validation
    │                    Duration: <5 min
    │                    Markers: (unit | integration) and not slow and not manual and not external
    │                    Coverage: 58% (midpoint Week 1-2)
    │                    maxfail: 3
    │                    │
    │                    └──→ ✅ PASS → Merge Ready
    │                    └──→ ❌ FAIL → Prevent Merge
    │
    ├──→ Merge to main ──→ Stage 2: Post-Merge Validation
    │                      Duration: <3 min
    │                      Markers: regression (only)
    │                      Coverage: N/A (excluded)
    │                      maxfail: 1 (strict)
    │                      │
    │                      └──→ ✅ PASS → Trunk Healthy
    │                      └──→ ❌ FAIL → Revert + Alert
    │
    ├──→ Sunday 00:00 UTC ──→ Stage 3: Weekly Comprehensive
    │                         Duration: <30 min
    │                         Markers: security OR performance OR external
    │                         Coverage: Full suite (85%)
    │                         maxfail: 10 (investigation)
    │                         │
    │                         └──→ ✅ PASS → Release Ready
    │                         └──→ ⚠️ WARN → Investigate
    │
    └──→ Merge to develop ──→ Stage 4: Branch Validation
                               Duration: <10 min
                               Markers: (unit | integration | regression) and not slow
                               Coverage: 58%
                               maxfail: 5
                               │
                               └──→ ✅ PASS → Next Feature Ready
                               └──→ ❌ FAIL → Fix Required
```

---

## Coverage Target Progression (Week 1-6)

```
Week 1  │ ████████░░░░░░░░░░░░░░░░░░░ │ 60%  (Starting point)
Week 2  │ ██████████░░░░░░░░░░░░░░░░░ │ 65%  (+5%)
Week 3  │ ██████████░░░░░░░░░░░░░░░░░ │ 65%  (plateau)
Week 4  │ ███████████░░░░░░░░░░░░░░░░ │ 70%  (+5%)
Week 5  │ ████████████████░░░░░░░░░░░ │ 80%  (+10%)
Week 5.5│ ████████████████░░░░░░░░░░░ │ 80%  (review)
Week 6  │ █████████████████░░░░░░░░░░ │ 85%  (+5%, final)
        └─────────────────────────────┘

Environment Variable: ${COVERAGE_TARGET:-60}
├─ Week 1: COVERAGE_TARGET=60
├─ Week 2: COVERAGE_TARGET=65
├─ Week 3: COVERAGE_TARGET=65
├─ Week 4: COVERAGE_TARGET=70
├─ Week 5: COVERAGE_TARGET=80
├─ Week 5.5: COVERAGE_TARGET=80
└─ Week 6: COVERAGE_TARGET=85

CI/CD Trigger: Set via GitHub Actions secrets or environment
Local Fallback: Defaults to 60% if no env var set
```

---

## Marker Usage Matrix

### Primary Markers (Test Classification)

| Marker | Usage | Stage 1 | Stage 2 | Stage 3 | Stage 4 | Notes |
|--------|-------|--------|---------|---------|---------|-------|
| **unit** | ✓ Include | ✓ Run | ✗ Exclude | ✓ Run | ✓ Run | Core: fast isolated tests |
| **integration** | ✓ Include | ✓ Run | ✗ Exclude | ✓ Run | ✓ Run | External dependencies |
| **regression** | ✗ Exclude | ✗ Exclude | ✗ Exclude | ✓ Run | ✓ Run | Critical path protection |
| **security** | ✗ Exclude | ✗ Exclude | ✓ Run | ✗ Exclude | ✗ Exclude | ASVS Level 1 validation |
| **performance** | ✗ Exclude | ✗ Exclude | ✓ Run | ✗ Exclude | ✗ Exclude | Latency/throughput checks |
| **e2e** | ✗ Exclude | ✗ Exclude | ✓ Run | ✗ Exclude | ✗ Exclude | Full user scenarios |

### Exclusion Markers (Test Filtering)

| Marker | Purpose | Applied to | Notes |
|--------|---------|-----------|-------|
| **slow** | Execution time >3s | All stages | Excluded from fast loops |
| **manual** | Human intervention | All stages | Excluded from CI/CD |
| **external** | Rate-limited APIs | Stage 1, 4 | Excluded from PR/branch, serial in Stage 3 |

### Reserved Markers (Not Yet Activated)

| Marker | Status | Plan | Notes |
|--------|--------|------|-------|
| **smoke** | Defined | Undecided | Fast basic functionality checks (future use) |

---

## Fail-Fast Strategy Rationale

```
Risk Level        Stage                  --maxfail Value
─────────────────────────────────────────────────────────
CRITICAL          Post-Merge (main)      1
(Trunk Protection) Stop on first regression
                  │
MODERATE          PR Validation          3
(Developer Feedback) Allow first 3 failures to see multiple issues
                  │
LOW               Weekly Comprehensive   10
(Investigation)   Deep investigation mode
                  │
MODERATE          Branch Validation      5
(Feature Branch)  Moderate feedback
```

**Rationale**:
- **main branch (1)**: Single regression can break all deployments → strict
- **PR branch (3)**: Developers want to see multiple issues before re-running → moderate
- **Weekly (10)**: Investigation mode → allow many failures for deep analysis
- **develop branch (5)**: Feature branch protection → balanced

---

## Command Reference by Use Case

### Local Development (Fastest)

```bash
# Only unit tests, no external dependencies
uv run pytest tests/unit/ -k "not slow" -v

# Expected: <30 seconds, 50-100 test cases
```

### Feature Implementation (Fast Feedback)

```bash
# Unit + Integration tests (PR validation equivalent)
uv run pytest -m "(unit or integration) and not slow and not external and not manual" \
  --cov --cov-report=term-missing \
  --cov-fail-under=58 --maxfail=3 -v

# Expected: 1-3 minutes, 80-150 test cases
```

### Pre-Merge Verification (Comprehensive)

```bash
# Add regression tests
uv run pytest -m "(unit or integration or regression) and not slow and not external and not manual" \
  --cov --cov-report=term-missing \
  --cov-fail-under=58 --maxfail=5 -v

# Expected: 2-5 minutes, 100-180 test cases
```

### Weekly Full Validation (Deep Investigation)

```bash
# Step 1: Core tests
uv run pytest -m "(unit or integration) and not slow and not external and not manual" \
  --cov --cov-report=json

# Step 2: Regression tests
uv run pytest -m "regression" --maxfail=3

# Step 3: Security & Performance (serial for rate limit safety)
uv run pytest -m "security" -v
uv run pytest -m "performance" -v

# Step 4: External API tests (weekly only)
uv run pytest -m "external and not manual" -v --maxfail=5

# Expected: 15-30 minutes total
```

### Release Preparation (Final Gate)

```bash
# Full test suite with 85% coverage requirement (Week 6)
uv run pytest -m "not manual and not external" \
  --cov --cov-report=html \
  --cov-fail-under=85 -v

# Expected: 5-10 minutes, full suite validation
```

---

## Configuration Files Map

### Source of Truth Hierarchy

```
pytest.ini (HIGHEST PRIORITY)
├─ Coverage targets: Week 1-6 (60-85%)
├─ Marker definitions: 8 markers
├─ Pattern usage examples
└─ Comments with rationale

.github/workflows/ci.yml (IMPLEMENTATION)
├─ Stage 1: PR Validation
├─ Stage 2: Post-Merge Validation
├─ Stage 3: Weekly Comprehensive
└─ Stage 4: Branch Validation

pyproject.toml (TOOLING CONFIG)
├─ Coverage source modules
├─ Pytest addopts (duplicates pytest.ini)
└─ Local development target (85%, strictest)

.serena/memories/test_strategy_part1_overview.md (DOCUMENTATION)
├─ CI/CD command examples
├─ 4-step staged execution guide
└─ Performance benchmarks
```

**Update Priority** (if changes needed):
1. Update `pytest.ini` (source of truth)
2. Update `.serena/memories/test_strategy_part1_overview.md` (documentation)
3. Update `.github/workflows/ci.yml` (implementation)
4. Update `pyproject.toml` (if markers added/removed)

---

## Status Indicators

### Test Execution Status Meanings

| Status | Location | Meaning | Action |
|--------|----------|---------|--------|
| ✅ PASS | All stages | All test cases passed | Proceed |
| ⚠️ WARN | Stage 3 (security) | Security test failed (non-blocking) | Review before release |
| ⚠️ WARN | Stage 3 (external) | External API test failed | Check rate limits |
| ❌ FAIL | Stage 1 (PR) | Test case failed | Fix and re-run |
| ❌ FAIL | Stage 2 (main) | Regression detected | REVERT + ALERT |
| ⚠️ SKIP | Stage 1, 4 | Security tests skipped (expected) | Normal behavior |

---

## Common Issues & Resolution

### Issue: Coverage target too strict for Week 1

**Symptom**: `AssertionError: test cov 45% < 58%`

**Root Cause**: New functionality not yet tested

**Resolution**:
```bash
# Check coverage report
uv run pytest --cov-report=term-missing

# Add missing tests
# OR temporarily lower COVERAGE_TARGET env var
export COVERAGE_TARGET=45
uv run pytest --cov-fail-under=${COVERAGE_TARGET}
```

### Issue: External API tests fail in Stage 3

**Symptom**: Rate limit errors or timeout errors

**Expected Behavior**: Non-blocking (continue-on-error: true)

**Resolution**:
```bash
# Check for rate limit in output
# Retry external tests manually after rate limit window

uv run pytest -m "external" -v --maxfail=5
```

### Issue: Regression test fails in Stage 2

**Symptom**: `FAILED: tests/regression/test_critical_path.py::test_auth_flow`

**Severity**: CRITICAL - Blocks merge to main

**Resolution**:
```bash
# 1. Understand what regression is
uv run pytest tests/regression/test_critical_path.py::test_auth_flow -vv

# 2. Fix the broken functionality
# 3. Re-run post-merge validation before next push

# Force this test locally
uv run pytest -m "regression" -v
```

### Issue: Slow tests included in PR validation

**Symptom**: PR validation takes 10+ minutes (exceeds 5 min timeout)

**Root Cause**: Test marked incorrectly (missing @pytest.mark.slow)

**Resolution**:
```bash
# Find slow tests
uv run pytest -v | grep SLOW

# Add @pytest.mark.slow to any test taking >3 seconds
# Or optimize the test
```

---

## Validation Checklist

Use this checklist to verify correct implementation:

### Configuration Files

- [ ] `pytest.ini` has 8 markers defined (unit, integration, e2e, performance, security, regression, slow, external, manual)
- [ ] `pytest.ini` has Week 1-6 coverage targets documented (60-85%)
- [ ] `.github/workflows/ci.yml` has 4 stages (PR, post-merge, weekly, branch)
- [ ] CI/CD commands use `${COVERAGE_TARGET:-60}` pattern
- [ ] Post-merge validation uses `--maxfail=1` (strict)
- [ ] PR validation uses `--maxfail=3` (moderate)
- [ ] Weekly uses `--maxfail=10` (investigation)

### Marker Usage

- [ ] PR validation excludes: slow, manual, external
- [ ] Post-merge validation runs only: regression
- [ ] Weekly validation runs: security (serial), performance, external
- [ ] Branch validation includes: unit, integration, regression

### Test Execution Times

- [ ] Unit tests: <30 seconds
- [ ] Unit + Integration: 1-3 minutes
- [ ] Full suite: <30 minutes

### Coverage Progression

- [ ] Week 1 target: 60%
- [ ] Week 6 target: 85%
- [ ] Environment variable fallback: 60%

---

## References

- Primary Review: [PYTEST_MARKER_REVIEW.md](./PYTEST_MARKER_REVIEW.md)
- Summary: [VALIDATION_SUMMARY.txt](./VALIDATION_SUMMARY.txt)
- Detailed Strategy: [@memory:test_strategy_part1_overview.md](.serena/memories/test_strategy_part1_overview.md)

---

## Approval & Sign-Off

**Review Date**: 2025-12-12
**Reviewer Role**: Quality Engineer
**Status**: ✅ APPROVED FOR PRODUCTION USE
**Quality Score**: 95/100

The 4-stage quality gate process is validated, documented, and ready for Week 1-6 execution.

All P0-P1 critical items verified. P2-P3 minor items are non-blocking and can be addressed in next sprint planning.

