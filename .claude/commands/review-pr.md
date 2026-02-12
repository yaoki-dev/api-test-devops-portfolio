---
allowed-tools: Bash(gh pr comment:*),Bash(gh pr diff:*),Bash(gh pr view:*)
description: Review a pull request
---

Perform a comprehensive code review using subagents for key areas:

## Execution Strategy

**IMPORTANT: Launch all 6 agents in PARALLEL using a single message with multiple Task tool calls.**

Do NOT run agents sequentially. All agents are independent and can run simultaneously.

## Agents to Launch (ALL IN PARALLEL)

Launch these 6 agents in a single message:

- code-quality-reviewer
- performance-reviewer
- test-coverage-reviewer
- documentation-accuracy-reviewer
- security-code-reviewer
- silent-failure-hunter

## Quality Threshold

Instruct each to only report issues with confidence >= 90 (Critical issues only).
Once they finish, review the feedback and post only the feedback that you also deem noteworthy.


## Post-Review

Once all agents finish, review the feedback and post only the feedback that you also deem noteworthy.

- Use inline comments for specific issues
- Use top-level comments for general observations or praise
- Keep feedback concise

Review should be in Japanese (日本語でレビューを出力してください).
