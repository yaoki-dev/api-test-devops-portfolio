# JSONPlaceholder Posts

## Sub-features

- Read one post with `SyncJSONPlaceholderClient.get_post` or its async sibling.
- List/filter posts with `get_posts(limit=..., user_id=...)`.
- Create, update, and delete posts through the async integration path.
- Verify the stable 404 contract for a missing post.

## How to get to it (user POV)

From the repository root, prepare the locked environment and run the default
read-only drive:

```bash
uv sync --dev --frozen
uv run python .claude/skills/verify-api-test-devops-portfolio/scripts/drive_jsonplaceholder_posts.py
```

This is the simplest real user path for a caller who wants validated post
models without mutating a remote service.

## Driving it with the Python verification harness

Capture the helper's action, returned model facts, and exit code:

```bash
EVIDENCE_DIR="${EVIDENCE_DIR:-/tmp/api-test-devops-portfolio-verification/posts}"
mkdir -p "$EVIDENCE_DIR"
set -o pipefail
uv run python .claude/skills/verify-api-test-devops-portfolio/scripts/drive_jsonplaceholder_posts.py \
  2>&1 | tee "$EVIDENCE_DIR/drive.log"
drive_exit_code=$?
printf 'drive_exit_code=%s\n' "$drive_exit_code" | tee -a "$EVIDENCE_DIR/drive.log"
test "$drive_exit_code" -eq 0
```

For the full external contract, including the write-shaped sequence:

```bash
TEST__EXTERNAL_API_ENABLED=true uv run pytest tests/integration/test_jsonplaceholder_posts.py \
  -m integration -v --no-cov 2>&1 | tee "$EVIDENCE_DIR/integration.log"
integration_exit_code=$?
printf 'integration_exit_code=%s\n' "$integration_exit_code" | tee -a "$EVIDENCE_DIR/integration.log"
test "$integration_exit_code" -eq 0
```

## Gotchas

- The helper performs real network I/O and is not governed by pytest's skip flag.
- If httpx reports `InvalidURL: Invalid port: ':'` before connecting, the ambient IPv6 `NO_PROXY` value is the known failure mode documented by the repository's proxy-isolation fixture; retry this public probe with `NO_PROXY= no_proxy=` and preserve both transcripts.
- The integration module is skipped when `settings.test.external_api_enabled` is false; set `TEST__EXTERNAL_API_ENABLED=true` explicitly for this proof.
- JSONPlaceholder writes are not persistent: POST returns `id=101`, PUT returns a partial dict, and DELETE is checked for no exception.
- The default evidence path is read-only; do not claim a database or durable row was changed.
