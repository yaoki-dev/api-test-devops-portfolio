# Runtime healthcheck

## Sub-features

- Validate Compose YAML before creating containers.
- Start the `runtime` image as the `app` service with the selected environment.
- Verify settings load and Docker health status.
- Run the isolated `test` profile when containerized pytest evidence is needed.

## How to get to it (user POV)

This repository has no listening application port. A user reaches the runtime
feature by starting the Compose configuration demo and inspecting its health:

```bash
docker compose config --quiet
docker compose up -d --wait --wait-timeout 120 --build app
docker compose ps
```

The `app` service must report `healthy`; its startup command prints a config
loaded line and then stays alive for the healthcheck.

## Driving it with the Python verification harness

Capture the visible container state, health field, and logs:

```bash
set -euo pipefail
EVIDENCE_DIR="${EVIDENCE_DIR:-/tmp/api-test-devops-portfolio-verification/runtime}"
mkdir -p "$EVIDENCE_DIR"
docker compose config --quiet
docker compose up -d --wait --wait-timeout 120 --build app
docker compose ps | tee "$EVIDENCE_DIR/compose-ps.log"
CONTAINER_ID="$(docker compose ps -q app)"
test -n "$CONTAINER_ID"
HEALTH="$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_ID")"
printf 'health=%s\n' "$HEALTH" | tee "$EVIDENCE_DIR/compose-health.log"
test "$HEALTH" = healthy
docker compose logs --tail=1000 app | tee "$EVIDENCE_DIR/compose-app.log"
```

For the test-container path, use the repository's profile and preserve its
coverage/log artifacts:

```bash
set +e
docker compose --profile test run --build --rm test 2>&1 \
  | tee "$EVIDENCE_DIR/compose-test-output.log"
pipeline_status=("${PIPESTATUS[@]}")
set -e
test_exit_code="${pipeline_status[0]}"
tee_exit_code="${pipeline_status[1]}"
printf 'test_exit_code=%s tee_exit_code=%s\n' "$test_exit_code" "$tee_exit_code" \
  | tee -a "$EVIDENCE_DIR/compose-test-output.log"
test "$test_exit_code" -eq 0
test "$tee_exit_code" -eq 0
```

## Gotchas

- `docker compose up -d` can return zero even when a service later fails; inspect `docker compose ps` and the health field explicitly.
- The `app` service exposes no port because the project is a client library, not a server.
- Staging and production settings require `SECURITY__API_KEY` or `SECURITY__JWT_SECRET`; use development/testing for local verification unless those secrets are intentionally provided.
- Compose instances from the same checkout are not parallel-safe; run `docker compose down --remove-orphans --timeout=10` after the proof and keep the evidence directory.
