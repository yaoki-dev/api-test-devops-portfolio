# Domain Documentation Layout

## Layout Type
**Single-context**

## Structure

```
repo-root/
├── CONTEXT.md           # Minimal domain context (EXISTS, sparse)
├── docs/
│   └── adr/             # Architecture Decision Records (TO BE CREATED)
└── .claude/
    └── CLAUDE.md        # Agent instructions (includes CRITICAL RULES)
```

## Consumer Rules

### For skills reading CONTEXT.md (`improve-codebase-architecture`, `diagnose`, `tdd`)

1. **Read `CONTEXT.md` at repo root** — single source of truth for domain language
2. **Check `docs/adr/` for architectural decisions** — if directory exists, read all ADRs
3. **No CONTEXT-MAP.md** — do not look for per-context CONTEXT.md files
4. **If files don't exist, proceed silently** — don't flag absence; don't suggest creating them upfront (per seed template guidance)

### CONTEXT.md Actual Content (as of 2026-06-26)

The current `CONTEXT.md` is minimal — only contains:
- CD実証 (CD verification) definition

It does **not** yet contain the full domain glossary. The richer domain context lives in:
- `.claude/CLAUDE.md` — project overview, tech stack, workflow rules
- `models/responses.py` — domain entities (Album, Comment, Photo, Post, Todo, User)
- `utils/api_client.py` — API contracts (JSONPlaceholder, GitHub API)
- `config/settings.py` — Pydantic Settings configuration

### ADR Directory

Currently **does not exist**. When created:
- Use Markdown ADR format (title, status, context, decision, consequences)
- Number sequentially: `001-<short-title>.md`
- Reference from CONTEXT.md when relevant

## Future Migration

If repo becomes multi-context (e.g., frontend/backend split):
1. Create `CONTEXT-MAP.md` at root mapping contexts
2. Move `CONTEXT.md` to `docs/contexts/<name>/CONTEXT.md`
3. Update this file to `multi-context`
