# GitHub API

## Sub-features

- Fetch a validated user with `AsyncGitHubClient.get_user`.
- Fetch a bounded repository list with `get_repos`.
- Fetch one repository with `get_repo`.
- Map a missing user to `NotFoundError`.
- Exercise the client's rate-limit-aware and ETag-capable request boundary through real calls.

## How to get to it (user POV)

From the repository root, use the maintained external integration module:

```bash
uv run pytest tests/integration/test_github_api.py -m external -v --no-cov
```

The module uses the public async client against `https://api.github.com` and
the documented `octocat`/`Hello-World` fixtures.

## Driving it with the Python verification harness

Capture the complete command and result; the client is async and the test
module is the repository's existing user-path harness:

```bash
EVIDENCE_DIR="${EVIDENCE_DIR:-/tmp/api-test-devops-portfolio-verification/github}"
mkdir -p "$EVIDENCE_DIR"
set -o pipefail
uv run pytest tests/integration/test_github_api.py -m external -v --no-cov \
  2>&1 | tee "$EVIDENCE_DIR/integration.log"
github_exit_code=$?
printf 'github_exit_code=%s\n' "$github_exit_code" | tee -a "$EVIDENCE_DIR/integration.log"
test "$github_exit_code" -eq 0
```

The end state is a zero exit code with validated login/repository fields and
the expected `NotFoundError` assertion. A failed or rate-limited request is
not a passing proof.

## Gotchas

- The integration tests use unauthenticated GitHub access; their module notes a 60 requests/hour rate limit.
- Keep `per_page=5` and the existing fixture identities to bound request volume and make the assertion meaningful.
- This feature is async-only by design; do not infer that a synchronous GitHub client exists.
- A passing local run proves the observed API response at that time, not authenticated production behavior or future GitHub schema stability.
