# JSONPlaceholder Users

## Sub-features

- Parse a user with nested address, geo, and company models.
- Resolve the API's `catchPhrase` field to the model's `catch_phrase` attribute.
- Aggregate a user's posts, todos, and albums through the async client.
- Preserve successful results in the related-data flow when the real API responds.

## How to get to it (user POV)

A caller reaches this feature through the async public client. The maintained
real-user path is represented by the integration module:

```bash
TEST__EXTERNAL_API_ENABLED=true uv run pytest tests/integration/test_jsonplaceholder_users.py \
  -m integration -v --no-cov
```

## Driving it with the Python verification harness

Run from the repository root and capture the transcript and exit code:

```bash
EVIDENCE_DIR="${EVIDENCE_DIR:-/tmp/api-test-devops-portfolio-verification/users}"
mkdir -p "$EVIDENCE_DIR"
set -o pipefail
TEST__EXTERNAL_API_ENABLED=true uv run pytest tests/integration/test_jsonplaceholder_users.py \
  -m integration -v --no-cov 2>&1 | tee "$EVIDENCE_DIR/integration.log"
users_exit_code=$?
printf 'users_exit_code=%s\n' "$users_exit_code" | tee -a "$EVIDENCE_DIR/integration.log"
test "$users_exit_code" -eq 0
```

The observable end state is a zero exit code plus assertions for `User`,
`Post`, `Todo`, and `Album` instances, nested aliases, and matching user IDs.

## Gotchas

- This is a real external-API proof, not a mock-based unit test; network failure is a bounded environmental failure, not evidence that the model contract passed.
- The async client is the maintained path for related-data aggregation; do not replace it with private helpers in a proof.
- The aggregation makes multiple remote reads. Keep one client context per test path and do not run duplicate probes unnecessarily.
- No persistent local or remote write is expected from these user reads.
