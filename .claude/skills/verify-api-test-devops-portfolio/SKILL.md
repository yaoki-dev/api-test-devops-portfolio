---
name: verify-api-test-devops-portfolio
description: "Verify the api-test-devops-portfolio Python API-client library, its real JSONPlaceholder/GitHub integrations, and its Docker runtime healthcheck. Use when a change needs user-path evidence rather than unit-test-only confidence."
---

# Verify api-test-devops-portfolio

## Surface

The primary user-facing surface is a Python library: callers use the public
`SyncJSONPlaceholderClient`, `AsyncJSONPlaceholderClient`, and
`AsyncGitHubClient` APIs. This checkout has no web UI, CLI, or HTTP server.
The Docker `app` service is a long-running runtime/configuration health demo,
not an API server; it exposes no port.

The default proof is deliberately read-only against JSONPlaceholder. The
repository's external integration tests also exercise write-shaped JSONPlaceholder
calls, but JSONPlaceholder documents those writes as non-persistent and they
must not be treated as durable side effects.

## Launch

For the library surface, launch means preparing the locked Python environment:

```bash
uv sync --dev --frozen
uv run python --version
```

Readiness is an exit code of `0`, Python `3.14`, and successful imports of the
settings and public client modules:

```bash
uv run python -c 'from config.settings import settings; from utils.jsonplaceholder_client_sync import SyncJSONPlaceholderClient; from utils.jsonplaceholder_client_async import AsyncJSONPlaceholderClient; from utils.github_client import AsyncGitHubClient; print(settings.environment.value, "clients-imported")'
```

There is no library process to keep alive or tear down. Do not invent a port
or use `curl` for the primary proof.

Optional Docker runtime verification starts the repository's own healthcheck
demo:

```bash
docker compose config --quiet
docker compose up -d --wait --wait-timeout 120 app
docker compose ps
CONTAINER_ID="$(docker compose ps -q app)"
HEALTH="$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_ID")"
printf 'health=%s\n' "$HEALTH"
test "$HEALTH" = healthy
```

The `app` row must report `healthy`. Its command first imports settings and
prints `[startup] config loaded:` before sleeping; the Dockerfile healthcheck
repeats settings validation. Stop only this Compose project during cleanup:

```bash
docker compose down --remove-orphans --timeout=10
```

## Doctor

Run this read-only doctor before investigating a failed drive. It checks the
checkout, locked environment, import boundary, and test collection without
calling an external API:

```bash
test "$(git rev-parse --show-toplevel)" = "$PWD" && \
uv run python --version && \
uv run python -c 'from config.settings import settings; from utils.jsonplaceholder_client_sync import SyncJSONPlaceholderClient; from utils.jsonplaceholder_client_async import AsyncJSONPlaceholderClient; from utils.github_client import AsyncGitHubClient; print(f"environment={settings.environment.value} clients=ok")' && \
uv run pytest --collect-only -q --no-cov tests/integration/test_jsonplaceholder_posts.py tests/integration/test_jsonplaceholder_users.py tests/integration/test_github_api.py
```

`--collect-only` does not drive the network. If Docker is the target, add
`docker compose config --quiet`; a non-zero result means the instance is not
worth driving yet. A passed doctor proves local readiness, not external API
availability or authenticated GitHub behavior.

## Drive

The harness is the checked-in Python helper at
`scripts/drive_jsonplaceholder_posts.py`. It uses the public synchronous
client, calls the real JSONPlaceholder service, and verifies a bounded,
read-only path (`get_post(1)` plus `get_posts(limit=2, user_id=1)`). It does
not call internal methods, test-only endpoints, or mocks.

```bash
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
EVIDENCE_DIR="${EVIDENCE_DIR:-/tmp/api-test-devops-portfolio-verification/$RUN_ID}"
mkdir -p "$EVIDENCE_DIR"
set -o pipefail
uv run python .claude/skills/verify-api-test-devops-portfolio/scripts/drive_jsonplaceholder_posts.py \
  2>&1 | tee "$EVIDENCE_DIR/posts-drive.log"
drive_exit_code=$?
printf 'drive_exit_code=%s\n' "$drive_exit_code" | tee -a "$EVIDENCE_DIR/posts-drive.log"
test "$drive_exit_code" -eq 0
```

The command must exit `0` and print a final JSON object with
`verification_status: "passed"`. For the complete external Posts contract,
including create/update/delete and the 404 behavior, run the repository's
real integration test module explicitly:

```bash
TEST__EXTERNAL_API_ENABLED=true uv run pytest tests/integration/test_jsonplaceholder_posts.py \
  -m integration -v --no-cov 2>&1 | tee "$EVIDENCE_DIR/posts-integration.log"
integration_exit_code=$?
printf 'integration_exit_code=%s\n' "$integration_exit_code" | tee -a "$EVIDENCE_DIR/posts-integration.log"
test "$integration_exit_code" -eq 0
```

If httpx fails before the first request with `InvalidURL: Invalid port: ':'`,
inspect the ambient `NO_PROXY`/`no_proxy` value. This checkout's test fixture
documents a known httpx failure with IPv6 `NO_PROXY` entries. For this public
external-only probe, retry with the no-proxy list removed while retaining any
configured HTTP(S) proxy:

```bash
NO_PROXY= no_proxy= uv run python .claude/skills/verify-api-test-devops-portfolio/scripts/drive_jsonplaceholder_posts.py \
  2>&1 | tee "$EVIDENCE_DIR/posts-drive-proxy-workaround.log"
workaround_exit_code=$?
printf 'workaround_exit_code=%s\n' "$workaround_exit_code" | tee -a "$EVIDENCE_DIR/posts-drive-proxy-workaround.log"
test "$workaround_exit_code" -eq 0
```

Do not treat the retry as proof that the original environment is healthy; keep
the failure transcript and report the transport-environment limitation.

Other mapped features have their exact commands in `features/`. Run one
feature per proof and do not parallelize Compose instances from the same
checkout: the Compose project name, build context, and bind-mounted reports
are shared. The read-only helper itself has no local mutable state, but it
still consumes real external API availability.

## Evidence

Every proof must preserve the action and the resulting state. Keep the
terminal transcript under `$EVIDENCE_DIR` (default:
`/tmp/api-test-devops-portfolio-verification/<UTC timestamp>`), including the
command's exit status. For the Docker path also capture:

```bash
set -euo pipefail
docker compose ps | tee "$EVIDENCE_DIR/compose-ps.log"
CONTAINER_ID="$(docker compose ps -q app)"
test -n "$CONTAINER_ID"
HEALTH="$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_ID")"
printf 'health=%s\n' "$HEALTH" | tee "$EVIDENCE_DIR/compose-health.log"
test "$HEALTH" = healthy
docker compose logs --tail=1000 app | tee "$EVIDENCE_DIR/compose-app.log"
```

The proof standard is the real user path: public client calls, their returned
validated models/dicts, and the observed exit code. For the read-only default
path there is no file, row, or message side effect to verify. For the
JSONPlaceholder write-shaped tests, record the repository-documented fact that
POST/PUT/DELETE are not persistent rather than claiming durable state. Mocks
remain appropriate only in the existing unit boundary; they are not evidence
of real integration behavior. Do not trust a command named `--no-cov` or a
test marker as proof that no network occurred: inspect the command and use the
read-only helper when network behavior must be explicit.

## Cleanup

The library helper is short-lived and needs no process cleanup. If the
optional Docker path was started, tear down only the Compose project created
by this run:

```bash
docker compose down --remove-orphans --timeout=10
```

Never kill by process name. Do not delete `$EVIDENCE_DIR`; evidence must
survive teardown. Remove only disposable scratch state after confirming the
evidence exists. If a failed pytest run generated ignored `reports/` files,
leave them for diagnosis or remove them explicitly after preserving the
transcript; they are not the proof itself.

## Helpers

`scripts/drive_jsonplaceholder_posts.py` is executable and has no hidden
setup. Invoke it from the repository root with:

```bash
uv run python .claude/skills/verify-api-test-devops-portfolio/scripts/drive_jsonplaceholder_posts.py
```

It emits only bounded JSON fields (IDs, counts, model types, and the requested
filter) so the transcript is useful without copying response bodies wholesale.

## Maintenance

When public methods, integration markers, Docker commands, or observable
contracts change, update this skill and the corresponding feature map before
relying on a new proof. Use `/maintain-verification-skill` for that review.
