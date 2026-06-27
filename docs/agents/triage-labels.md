# Triage Label Vocabulary

## Mapping (Canonical Role → GitHub Label)

| Canonical Role | GitHub Label | Status | Notes |
|----------------|--------------|--------|-------|
| needs-triage | `needs-triage` | **Active** | New issues start here |
| needs-info | — | **Removed** | Not used; ask via comments instead |
| ready-for-agent | `ready-for-execute` | **Active** | Fully specified, agent can implement |
| ready-for-human | `ready-for-human` | **Defined, not used** | Reserved for future human-only tasks |
| wontfix | `wontfix` | **Active** | Explicit closure |

## Two Label Systems — Important Distinction

This repo uses **two separate label vocabularies** for different purposes:

| System | Purpose | Labels | Skill |
|--------|---------|--------|-------|
| **create-issue** | Issue *type* classification | `bug`, `documentation`, `enhancement`, `dependencies` | `/create-issue` |
| **triage** | Issue *state* in workflow | `needs-triage`, `ready-for-execute`, `wontfix` | `/triage` |

**Do not mix them.** Triage labels track workflow progress; create-issue labels categorize the work type. An issue has one type label and one triage state label simultaneously.

## Rationale

- **needs-info removed**: Single-developer project; `create-issue` templates enforce complete info upfront. Comments suffice for clarification.
- **ready-for-execute renamed**: More intuitive than `ready-for-agent` → `ready-for-execute`.
- **ready-for-human kept (inactive)**: Definition preserved for schema compatibility with mattpocock/skills; operational use is zero currently.

## State Machine (when triage skill runs)

```
New Issue → needs-triage
  ├─ Complete spec → ready-for-execute
  ├─ Info needed (rare) → Comment + stays needs-triage
  └─ Won't fix → wontfix
```

## GitHub Label Creation

Run once to create **triage** labels:
```bash
gh label create "needs-triage" --color "FBCA04" --description "Awaiting triage evaluation"
gh label create "ready-for-execute" --color "0E8A16" --description "Ready for agent execution"
gh label create "wontfix" --color "FFFFFF" --description "Will not be addressed"
```

> **Note**: `ready-for-human` label intentionally not created (unused). create-issue type labels (`bug`, `documentation`, `enhancement`, `dependencies`) are created separately via `/create-issue` workflow.
