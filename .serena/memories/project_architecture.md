# API Test DevOps Portfolio - Architecture Overview

*Last Updated: 2026-03-22*

**Purpose**: Learning portfolio demonstrating 4,000-4,500 yen/hour technical capability
**Tech Stack**: Python 3.14 / httpx / pytest / Pydantic Settings / structlog / Docker / GitHub Actions

## Key Metrics (2026-03-22)
- Test Coverage: 93.43% (target: 85% ✅達成、CI条件: unit+integration, not external)
- Test Count: 588 tests (全件) / 575件 (CI条件: unit+integration, performance除外)
- Code Lines: ~2,500 (utils/config/models)
- SOLID Compliance: 85%

## Architecture

### Core Layer
| Module | Lines | Description |
|--------|-------|-------------|
| utils/jsonplaceholder_base_sync.py | 350 | Sync base HTTP client (SyncAPIClient) |
| utils/jsonplaceholder_base_async.py | 570 | Async base HTTP client (AsyncAPIClient) |
| utils/jsonplaceholder_client_sync.py | 220 | Sync JSONPlaceholder API client |
| utils/jsonplaceholder_client_async.py | 480 | Async JSONPlaceholder API client |
| utils/retry.py | 30 | Exponential backoff with jitter |
| utils/exceptions.py | 50 | API exception hierarchy |
| utils/http_helpers.py | 340 | Error handling, config, validation |
| utils/response_parsing.py | 120 | JSON parse + Pydantic model transform |
| utils/github_client.py | 913 | GitHub API facade (AsyncGitHubClient) + input validation |
| utils/github_error_handler.py | 254 | GitHub exception hierarchy + 403/5xx/JSON error handlers (PII-safe) |
| utils/github_rate_limit.py | 92 | GitHub rate-limit helpers (RATE_LIMIT_WARNING_THRESHOLD) |
| utils/logger.py | 152 | structlog統合 + Sentry連携 |
| utils/sentry_init.py | 196 | Sentry SDK初期化 |
| utils/sentry_scrub_events.py | 658 | Sentryイベント単位のスクラブ (_before_send) |
| utils/sentry_scrub_values.py | 193 | 値の再帰スクラブ (URL / クエリ文字列) |
| utils/sentry_scrub_primitives.py | 200 | 機密キー判定 (SENSITIVE_KEYS) + 共通ログヘルパー |
| config/settings.py | 447 | Type-safe Pydantic Settings |
| models/responses.py | 350 | 7 Pydantic response models |

### Test Layer
- **Total**: 588 tests across ~19 test files (CI対象: 575件)
- **Distribution (test files)**: unit(14) / integration(3) / performance(1) / smoke(1)
- **Infrastructure**: conftest.py shared fixtures

### Dependency Structure
- No circular dependencies
- 3-layer depth (utils → config → models)

## Design Patterns

### Retry Logic
- Exponential backoff with 30% jitter
- `exponential_backoff_with_jitter()` in utils/retry.py

### Error Handling Hierarchy
- 4xx: Immediate fail (client error)
- 5xx: Retry with backoff (server error)

### Logging (structlog統合)
- **Module**: utils/logger.py
- **Features**:
  - FilteringBoundLogger (型安全)
  - 環境別設定 (console/json format)
  - Sentry統合 (ERROR以上を自動送信)
  - シングルトンパターン (lazy initialization)
- **Usage**: `from utils.logger import get_logger`

### Observability (Sentry統合)
- **Modules**: utils/sentry_init.py（初期化）+ utils/sentry_scrub_{events,values,primitives}.py（PIIスクラブ）
- **Features**:
  - DSN設定による初期化
  - 機密データスクラブ (PII保護)
  - 環境別サンプリングレート
- **Usage**: `from utils.sentry_init import init_sentry`

### Settings Management
- Pydantic-based type-safe configuration
- Nested config with `__` separator
- SecretStr for sensitive values

### API Clients (フラットモジュール構造)
| Class | Module | Type | Purpose |
|-------|--------|------|---------|
| SyncAPIClient | jsonplaceholder_base_sync | Sync | Base HTTP client with retry |
| AsyncAPIClient | jsonplaceholder_base_async | Async | Async HTTP client with retry |
| SyncJSONPlaceholderClient | jsonplaceholder_client_sync | Sync | JSONPlaceholder API (sync) |
| AsyncJSONPlaceholderClient | jsonplaceholder_client_async | Async | JSONPlaceholder API (async) |
| AsyncGitHubClient | github_client | Async | GitHub API integration |
| create_client() | jsonplaceholder_client_sync | Factory | Client instantiation |

## Response Models (models/responses.py)
- Post / Comment / Company / User / Todo / Album / Photo
- sanitize_user_content() - XSS防止ユーティリティ

## Exception Hierarchy

```
APIClientError (base)
├── APIConnectionError
├── APITimeoutError
├── APIHTTPError
├── APIRetryError
└── APIJSONDecodeError

GitHubAPIError (base)
├── RateLimitError
├── NotFoundError
└── GitHubServerError
```

## Container Architecture

### 4-Stage Multi-stage Build (Dockerfile)

```
Stage 1: base        → 共通ベースイメージ（セキュリティ更新、非rootユーザー）
Stage 2: dependencies → uv依存関係インストール（--frozen --no-dev）
Stage 3: runtime     → 本番実行環境（最小限コピー、HEALTHCHECK）
Stage 4: test        → テスト実行環境（全依存関係、pytest）
```

### Security Best Practices
- SHA256 digest pinning（サプライチェーン攻撃防止）
- Non-root user execution（appuser:appgroup）
- OS security updates in base stage
- Minimal runtime image（不要ファイル削除）

### Layer Caching Strategy
- pyproject.toml + uv.lock 先行COPY（依存関係キャッシュ）
- COPY --from=dependencies（仮想環境転送）
- __pycache__ 削除（イメージサイズ最適化）

### Quality Targets
- Image size: < 200MB
- Build time: < 3分

## Reference
- Implementation: See CLAUDE.md for detailed guidance
- Test Strategy: @memory:test_strategy
- Coding Standards: .claude/rules/python/coding-standards.md
