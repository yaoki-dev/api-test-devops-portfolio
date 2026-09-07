# Feature map

The repository is a Python API-client library rather than a web application.
Use the public client methods and the runtime healthcheck as the user-facing
verification surfaces.

| Feature | User-facing proof |
|---|---|
| [JSONPlaceholder Posts](jsonplaceholder-posts.md) | Read-only sync drive; optional real CRUD/404 integration module |
| [JSONPlaceholder Users](jsonplaceholder-users.md) | Nested Pydantic parsing and related-data aggregation over the real API |
| [GitHub API](github-api.md) | Async user/repository retrieval and not-found behavior against GitHub |
| [Runtime healthcheck](runtime-healthcheck.md) | Docker runtime settings validation and healthy container state |

The map intentionally separates the default read-only proof from write-shaped
integration tests. JSONPlaceholder write calls are documented as
non-persistent, so a passing response is not durable storage evidence.
