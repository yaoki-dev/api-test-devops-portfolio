# API Test DevOps Portfolio - Architecture Overview

*Last Updated: 2026-03-07*

**Purpose**: Learning portfolio demonstrating 4,000-4,500 yen/hour technical capability
**Tech Stack**: Python 3.14 / httpx / pytest / Pydantic Settings / structlog / Docker / GitHub Actions

## Key Metrics (2026-03-07)
- Test Coverage: 92.73% (target: 85% ✅達成、CI条件: unit+integration, not external)
- Test Count: 551 tests (全件) / 483件 (CI条件: unit+integration)
- Code Lines: ~2,500 (utils/config/models)
- SOLID Compliance: 85%

## Architecture

### Core Layer
| Module | Lines | Description |
|--------|-------|-------------|
| utils/api_client.py | 972 | Sync/Async HTTP clients with retry logic |
| utils/github_client.py | 395 | GitHub API integration + input validation |
| utils/logger.py | 152 | structlog統合 + Sentry連携 |
| utils/sentry_init.py | 184 | Sentry SDK初期化 + 機密データスクラブ |
| config/settings.py | 447 | Type-safe Pydantic Settings |
| models/responses.py | 350 | 7 Pydantic response models |

### Test Layer
- **Total**: 551 tests across ~19 test files (CI対象: 483件)
- **Distribution**: unit(~11) / security(3) / integration(2) / regression(1) / performance(1) / validation(1)
- **Infrastructure**: conftest.py shared fixtures

### Dependency Structure
- No circular dependencies
- 3-layer depth (utils → config → models)

## Design Patterns

### Retry Logic
- Exponential backoff with 30% jitter
- `exponential_backoff_with_jitter()` in api_client.py

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
- **Module**: utils/sentry_init.py
- **Features**:
  - DSN設定による初期化
  - 機密データスクラブ (PII保護)
  - 環境別サンプリングレート
- **Usage**: `from utils.sentry_init import init_sentry`

### Settings Management
- Pydantic-based type-safe configuration
- Nested config with `__` separator
- SecretStr for sensitive values

### API Clients
| Class | Type | Purpose |
|-------|------|---------|
| BaseAPIClient | Sync | Base HTTP client |
| JSONPlaceholderClient | Sync | JSONPlaceholder API |
| AsyncAPIClient | Async | Async HTTP client |
| AsyncJSONPlaceholderClient | Async | Async JSONPlaceholder |
| AsyncGitHubClient | Async | GitHub API integration |
| create_client() | Factory | Client instantiation |

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
