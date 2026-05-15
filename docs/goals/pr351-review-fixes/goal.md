# PR #351 Review Fixes

## Objective

Resolve the approved PR #351 review feedback items #1-7 and #10, while verifying already-fixed items #8 and #9 and preserving the intended CI design that mypy failures stop downstream test evaluation.

## Original Request

Use GoalBuddy to prepare execution for PR #351 review fixes: handle #1-7 and #10; #8 is already fixed to 10; #9 is already fixed; pr-validation/post-validation integrate mypy before tests and should stop later pipeline on mypy failure.

## Intake Summary

- Input shape: `existing_plan`
- Audience: repository maintainer / portfolio reviewer
- Authority: `approved`
- Proof type: `test | artifact | review`
- Completion proof: approved items are implemented or verified as already fixed; quality gates and targeted workflow/document checks pass or are truthfully reported; final audit maps changes to #1-7,#10 and verifies #8/#9.
- Likely misfire: mechanically editing CI YAML without preserving the intentional mypy-before-tests stop behavior, or claiming #8/#9 fixed without reading the current file.
- Blind spots considered:
  - CI YAML is Rule 16 high-risk/prohibited for autonomous edits outside explicit approval.
  - README docs may need synchronization.
  - Issue comments have path-null provenance.
  - GitHub Actions behavior around `always()` and implicit `success()` must be reasoned from actual workflow structure.
- Existing plan facts:
  - #1-7 and #10 are approved for handling.
  - #8 should already be timeout 10.
  - #9 should already be fixed.
  - mypy runs in pr-validation/post-validation before tests.
  - mypy failure should stop downstream test evaluation.
  - Required tool priority order and confidence/reflect rules must be preserved.

## Goal Kind

`existing_plan`

## Current Tranche

Validate the current PR #351 branch state against the approved review items, implement only the remaining approved fixes in `.github/workflows/ci.yml` and `README.md`, run targeted and project-appropriate verification, then audit that the full requested review response is complete. Continue through safe verified slices until the full original outcome is complete.

## Non-Negotiable Constraints

- Normal outputs in Japanese.
- Do not infer; verify code, config, tests, or primary evidence before claims.
- Preserve user-stated CI design: mypy checks run before test evaluation in pr-validation/post-validation; mypy failure stops downstream pipeline/tests.
- Use tools in requested priority order during execution: graphify/code-review-graph, Serena, ast-grep, semgrep, LSP if available, Understand-Anything if needed, sequential thinking for final integration.
- If a requested tool is unavailable or returns empty, explicitly record that fact and continue to the next tool.
- `.github/workflows/ci.yml` and README edits are permitted only because the user approved this PR review response scope.
- Do not run `git commit` directly; use the available commit workflow if a commit is needed.
- Before completion, run `superpowers:verification-before-completion` and `reflexion:reflect` per user instruction.

## Stop Rule

Stop only when a final audit proves the full original outcome is complete.

Do not stop after planning, discovery, or Judge selection if a safe Worker task can be activated.

Do not stop after a single verified Worker slice while approved review items remain.

If verification fails or a requested tool is unavailable, record the exact evidence and continue only with safe local recovery work or ask the operator when ambiguity materially changes the outcome.

## Canonical Board

Machine truth lives at:

`docs/goals/pr351-review-fixes/state.yaml`

If this charter and `state.yaml` disagree, `state.yaml` wins for task status, active task, receipts, verification freshness, and completion truth.

## Run Command

```text
/goal Follow docs/goals/pr351-review-fixes/goal.md.
```

## PM Loop

On every `/goal` continuation:

1. Read this charter.
2. Read `state.yaml`.
3. Re-check worktree boundary and current branch.
4. Work only on the active board task.
5. Write a compact receipt before advancing.
6. Keep exactly one active task.
7. Finish only with a Judge/PM audit receipt that records `full_outcome_complete: true` and maps verification evidence back to the original user outcome.
