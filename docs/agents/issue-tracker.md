# Issue Tracker Configuration

## Tracker Type
GitHub Issues

## Repository
yaoki-dev/api-test-devops-portfolio

## CLI Tool
`gh` (GitHub CLI)

## Issue Creation
Use the `/create-issue` skill (or `create-issue` skill) which provides 6 templates:
- bug → label: `bug`
- docs → label: `documentation`
- feat → label: `enhancement`
- ci → label: `enhancement`
- security → label: `bug`
- chore → label: `dependencies`

## Conventions (aligned with seed template)

- **Create an issue**: `gh issue create --title "..." --body "..."` (use heredoc for multi-line)
- **Read an issue**: `gh issue view <number> --comments`, filter with `jq`
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '...'`
- **Comment**: `gh issue comment <number> --body "..."`
- **Apply/remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

Infer repo from `git remote -v` — `gh` does this automatically inside a clone.

## Pull Requests as Triage Surface

**PRs as a request surface: no.** (Set to `yes` if this repo treats external PRs as feature requests; `/triage` reads this flag.)

When `yes`, PRs run through the same labels and states as issues, using `gh pr` equivalents:
- **Read a PR**: `gh pr view <number> --comments` and `gh pr diff <number>`
- **List external PRs for triage**: `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments` then keep only `authorAssociation` of `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR`, or `NONE` (drop `OWNER`/`MEMBER`/`COLLABORATOR`)
- **Comment / label / close**: `gh pr comment`, `gh pr edit --add-label`/`--remove-label`, `gh pr close`

GitHub shares one number space across issues and PRs, so `#42` may be either — resolve with `gh pr view 42` and fall back to `gh issue view 42`.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.

## Two Label Systems — Important

This repo uses **two separate label vocabularies**:

| System | Purpose | Labels | Skill |
|--------|---------|--------|-------|
| **create-issue** | Issue *type* classification | `bug`, `documentation`, `enhancement`, `dependencies` | `/create-issue` |
| **triage** | Issue *state* in workflow | `needs-triage`, `ready-for-execute`, `wontfix` | `/triage` |

**Do not mix them.** Triage labels track workflow progress; create-issue labels categorize the work type. An issue has one type label and one triage state label simultaneously.

See `docs/agents/triage-labels.md` for the triage state machine.
