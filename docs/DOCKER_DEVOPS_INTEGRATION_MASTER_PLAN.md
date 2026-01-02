# Docker + DevOps 統合マスタープラン - 実務4環境対応完全ガイド

*最終更新: 2025年10月02日*

## エグゼクティブサマリー

本ドキュメントは、APIテスト + DevOps統合学習ポートフォリオを**実務レベル（時給4,000-4,500円 → 目標6,000-8,000円）**に引き上げるための包括的な実装ガイドです。

### 現状分析
- **現在の市場価値**: C評価 1,500-2,000円/時（基礎レベル）
- **カバレッジ**: 42.51%（目標85%未達）
- **Docker環境**: 未構築（実務環境対応なし）
- **CI/CD**: 未実装（自動化なし）

### 目標達成ロードマップ
- **Week 7**: Docker基盤構築 + カバレッジ60%達成（50時間）
- **Week 8**: CI/CD完全自動化 + カバレッジ75%達成（50時間）
- **Week 9**: E2Eテスト + パフォーマンス最適化（50時間）
- **Week 10**: ポートフォリオ最適化 + 市場投入（50時間）

### 期待される成果
- **A評価達成**: 4,000-4,500円/時（実務即戦力レベル）
- **実務4環境対応**: Development/Test/Staging/Production完全構築
- **完全自動化**: CI/CD + 自動テスト + 自動デプロイ
- **カバレッジ85%**: 品質保証体制確立

---

## 1. 実務4環境対応ディレクトリ全体構成

### 1.1 プロジェクト構造（完全版）

```
api-test-devops-portfolio/
├── docker/                          # Docker環境設定（NEW）
│   ├── base/                        # 基盤イメージ
│   │   └── Dockerfile              # Python 3.12-slim ベース
│   ├── development/                 # 開発環境
│   │   ├── Dockerfile              # 開発ツール含む
│   │   ├── docker-compose.yml      # 開発環境構成
│   │   └── .env.development        # 開発環境変数
│   ├── test/                        # テスト環境
│   │   ├── Dockerfile              # テスト専用設定
│   │   ├── docker-compose.yml      # CI/CD統合
│   │   └── .env.test               # テスト環境変数
│   ├── staging/                     # ステージング環境
│   │   ├── Dockerfile              # 本番同等設定
│   │   ├── docker-compose.yml      # 本番模擬環境
│   │   └── .env.staging            # ステージング環境変数
│   └── production/                  # 本番環境
│       ├── Dockerfile              # 最小構成・最適化
│       ├── docker-compose.yml      # 本番環境構成
│       └── .env.production         # 本番環境変数（シークレット管理）
│
├── .github/                         # GitHub Actions（NEW）
│   └── workflows/
│       ├── ci.yml                  # CI パイプライン
│       ├── cd-staging.yml          # ステージングデプロイ
│       ├── cd-production.yml       # 本番デプロイ
│       └── security-scan.yml       # セキュリティスキャン
│
├── config/                          # 設定管理（既存）
│   ├── settings.py                 # Pydantic Settings
│   ├── __init__.py
│   └── environments/               # 環境別設定（NEW）
│       ├── development.py
│       ├── test.py
│       ├── staging.py
│       └── production.py
│
├── utils/                           # コアモジュール（既存）
│   ├── api_client.py               # APIクライアント実装
│   └── __init__.py
│
├── tests/                           # テストスイート（既存 + 拡張）
│   ├── unit/                       # 単体テスト（既存）
│   ├── integration/                # 統合テスト（Week 8実装）
│   ├── e2e/                        # E2Eテスト（Week 9実装）
│   ├── performance/                # パフォーマンステスト（Week 9実装）
│   ├── security/                   # セキュリティテスト（既存）
│   └── conftest.py                 # pytest共通設定
│
├── scripts/                         # 自動化スクリプト（NEW）
│   ├── build.sh                    # ビルド自動化
│   ├── test.sh                     # テスト実行
│   ├── deploy.sh                   # デプロイ自動化
│   └── health_check.sh             # ヘルスチェック
│
├── docs/                            # ドキュメント（既存）
│   ├── api/                        # API仕様
│   ├── architecture/               # アーキテクチャ設計
│   ├── guides/                     # 実装ガイド
│   └── interview/                  # 面接準備資料
│
├── .dockerignore                    # Docker除外設定（NEW）
├── docker-compose.yml               # ローカル開発環境（NEW）
├── Makefile                         # タスク自動化（NEW）
├── pyproject.toml                   # Python設定（既存）
└── README.md                        # プロジェクト概要（既存）
```

### 1.2 環境別ディレクトリ詳細

#### Development（開発環境）
```
docker/development/
├── Dockerfile                       # 開発ツール全部入り
├── docker-compose.yml               # ホットリロード対応
├── .env.development                 # デバッグモード有効
└── README.md                        # 開発環境セットアップ手順
```

**特徴**:
- ホットリロード対応（コード変更即反映）
- デバッグツール統合（ipdb, pytest-watch）
- 開発用ログレベル（DEBUG）
- ボリュームマウント（ローカルコード直接実行）

#### Test（テスト環境）
```
docker/test/
├── Dockerfile                       # テスト専用最適化
├── docker-compose.yml               # CI/CD統合
├── .env.test                        # テスト環境変数
└── README.md                        # テスト実行手順
```

**特徴**:
- CI/CD統合設計
- カバレッジ計測自動化
- 並列テスト実行（pytest-xdist）
- テストレポート自動生成

#### Staging（ステージング環境）
```
docker/staging/
├── Dockerfile                       # 本番同等設定
├── docker-compose.yml               # 本番模擬環境
├── .env.staging                     # 本番類似設定
└── README.md                        # デプロイ手順
```

**特徴**:
- 本番環境の完全再現
- パフォーマンステスト実施
- セキュリティ検証
- ロールバック機能

#### Production（本番環境）
```
docker/production/
├── Dockerfile                       # 最小構成・最適化
├── docker-compose.yml               # 本番環境構成
├── .env.production                  # シークレット管理
└── README.md                        # 本番運用手順
```

**特徴**:
- Multi-stage build（最小イメージサイズ）
- セキュリティ強化（非rootユーザー）
- ヘルスチェック統合
- 自動スケーリング対応

---

## 2. 環境別Docker詳細設定

### 2.1 Base Dockerfile（共通基盤）

```dockerfile
# docker/base/Dockerfile
FROM python:3.12-slim AS base

# メタデータ
LABEL maintainer="yuta@example.com"
LABEL description="API Test + DevOps Portfolio - Base Image"
LABEL version="1.0.0"

# 環境変数
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# システムパッケージ更新
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# uvインストール
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# 作業ディレクトリ
WORKDIR /app

# 非rootユーザー作成（セキュリティ）
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
```

### 2.2 Development Dockerfile

```dockerfile
# docker/development/Dockerfile
FROM api-test-devops-portfolio-base:latest AS development

# 開発ツールインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    vim \
    iputils-ping \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# 依存関係コピー
COPY pyproject.toml uv.lock ./
RUN uv sync --all-extras

# アプリケーションコード（ボリュームマウント想定）
COPY . .

# 開発サーバー起動
USER appuser
EXPOSE 8000
CMD ["uv", "run", "python", "-m", "pytest", "--watch"]
```

**docker-compose.yml (Development)**:
```yaml
# docker/development/docker-compose.yml
version: '3.8'

services:
  app:
    build:
      context: ../..
      dockerfile: docker/development/Dockerfile
    image: api-test-devops-portfolio-dev:latest
    container_name: api-test-dev
    env_file:
      - .env.development
    volumes:
      - ../../:/app                    # ホットリロード
      - /app/.venv                     # 仮想環境除外
    ports:
      - "8000:8000"
    networks:
      - dev-network
    command: >
      bash -c "
        uv run pytest --watch --cov=utils --cov=config
      "

networks:
  dev-network:
    driver: bridge
```

**.env.development**:
```bash
# docker/development/.env.development
ENVIRONMENT=development
DEBUG=true

# API設定
API__BASE_URL=https://jsonplaceholder.typicode.com
API__TIMEOUT=30
API__RETRY_COUNT=3

# ログ設定
LOG__LEVEL=DEBUG
LOG__FORMAT=console

# テスト設定
TEST__EXTERNAL_API_ENABLED=true
TEST__PERFORMANCE_TEST_ENABLED=false
```

### 2.3 Test Dockerfile（CI/CD統合）

```dockerfile
# docker/test/Dockerfile
FROM api-test-devops-portfolio-base:latest AS test

# テスト依存関係のみインストール
COPY pyproject.toml uv.lock ./
RUN uv sync --group dev

# アプリケーションコード
COPY config/ ./config/
COPY utils/ ./utils/
COPY tests/ ./tests/

# テスト実行ユーザー
USER appuser

# テスト実行
CMD ["uv", "run", "pytest", \
     "--cov=utils", \
     "--cov=config", \
     "--cov-report=xml:reports/coverage.xml", \
     "--cov-report=html:reports/htmlcov", \
     "--cov-fail-under=85", \
     "-n", "auto"]
```

**docker-compose.yml (Test)**:
```yaml
# docker/test/docker-compose.yml
version: '3.8'

services:
  test:
    build:
      context: ../..
      dockerfile: docker/test/Dockerfile
    image: api-test-devops-portfolio-test:latest
    container_name: api-test-ci
    env_file:
      - .env.test
    volumes:
      - ../../reports:/app/reports     # レポート出力
    networks:
      - test-network

networks:
  test-network:
    driver: bridge
```

**.env.test**:
```bash
# docker/test/.env.test
ENVIRONMENT=testing
DEBUG=false

# API設定
API__BASE_URL=https://jsonplaceholder.typicode.com
API__TIMEOUT=10
API__RETRY_COUNT=2

# ログ設定
LOG__LEVEL=INFO
LOG__FORMAT=json

# テスト設定
TEST__EXTERNAL_API_ENABLED=true
TEST__PERFORMANCE_TEST_ENABLED=true
```

### 2.4 Staging Dockerfile

```dockerfile
# docker/staging/Dockerfile
FROM api-test-devops-portfolio-base:latest AS staging

# 本番環境依存関係のみ
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev

# アプリケーションコード
COPY config/ ./config/
COPY utils/ ./utils/

# 本番ユーザーで実行
USER appuser

# アプリケーション起動
CMD ["uv", "run", "python", "-m", "uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4"]
```

**docker-compose.yml (Staging)**:
```yaml
# docker/staging/docker-compose.yml
version: '3.8'

services:
  app:
    build:
      context: ../..
      dockerfile: docker/staging/Dockerfile
    image: api-test-devops-portfolio-staging:latest
    container_name: api-test-staging
    env_file:
      - .env.staging
    ports:
      - "8000:8000"
    networks:
      - staging-network
    deploy:
      replicas: 2                      # 負荷分散テスト
      resources:
        limits:
          cpus: '1.0'
          memory: 512M

networks:
  staging-network:
    driver: bridge
```

**.env.staging**:
```bash
# docker/staging/.env.staging
ENVIRONMENT=staging
DEBUG=false

# API設定
API__BASE_URL=https://jsonplaceholder.typicode.com
API__TIMEOUT=15
API__RETRY_COUNT=3

# ログ設定
LOG__LEVEL=WARNING
LOG__FORMAT=json
LOG__FILE=/var/log/app/api-test.log

# セキュリティ設定
SECURITY__API_KEY=${STAGING_API_KEY}  # シークレット管理
SECURITY__RATE_LIMIT_REQUESTS=100
```

### 2.5 Production Dockerfile（最適化版）

```dockerfile
# docker/production/Dockerfile

# ビルドステージ
FROM python:3.12-slim AS builder

# uv インストール
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

WORKDIR /build
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

# 本番ステージ
FROM python:3.12-slim AS production

# 必要最小限のパッケージ
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# ビルド成果物コピー
COPY --from=builder /build/.venv /app/.venv
COPY config/ /app/config/
COPY utils/ /app/utils/

# 非rootユーザー
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

WORKDIR /app
USER appuser

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# 本番起動
CMD ["/app/.venv/bin/uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--log-config", "config/logging.json"]
```

**docker-compose.yml (Production)**:
```yaml
# docker/production/docker-compose.yml
version: '3.8'

services:
  app:
    build:
      context: ../..
      dockerfile: docker/production/Dockerfile
    image: api-test-devops-portfolio-prod:latest
    container_name: api-test-prod
    env_file:
      - .env.production
    ports:
      - "80:8000"
    networks:
      - prod-network
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2.0'
          memory: 1G
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3

  nginx:
    image: nginx:alpine
    container_name: api-test-nginx
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    ports:
      - "443:443"
    networks:
      - prod-network
    depends_on:
      - app

networks:
  prod-network:
    driver: bridge
```

**.env.production**:
```bash
# docker/production/.env.production
ENVIRONMENT=production
DEBUG=false

# API設定
API__BASE_URL=https://api.production.example.com
API__TIMEOUT=20
API__RETRY_COUNT=5

# ログ設定
LOG__LEVEL=ERROR
LOG__FORMAT=json
LOG__FILE=/var/log/app/production.log

# セキュリティ設定（シークレット管理）
SECURITY__API_KEY=${PROD_API_KEY}
SECURITY__JWT_SECRET=${JWT_SECRET}
SECURITY__RATE_LIMIT_REQUESTS=1000
```

---

## 3. 改善TODO（優先順位付き）

### Week 7: Docker基盤構築 + テストカバレッジ60%達成（50時間）

#### Day 1-2: Docker環境構築（16時間）
- [ ] **Task 7.1.1**: Base Dockerfileサポート作成（4時間）
  ```bash
  # 実行コマンド
  mkdir -p docker/{base,development,test,staging,production}
  touch docker/base/Dockerfile
  # Dockerfile作成・ビルドテスト
  docker build -t api-test-devops-portfolio-base:latest -f docker/base/Dockerfile .
  ```

- [ ] **Task 7.1.2**: Development環境構築（4時間）
  ```bash
  # 実行コマンド
  cd docker/development
  touch Dockerfile docker-compose.yml .env.development
  # 開発環境起動テスト
  docker-compose up -d
  docker-compose logs -f
  ```

- [ ] **Task 7.1.3**: Test環境構築（4時間）
  ```bash
  # 実行コマンド
  cd docker/test
  touch Dockerfile docker-compose.yml .env.test
  # テスト実行確認
  docker-compose run test
  ```

- [ ] **Task 7.1.4**: .dockerignoreとMakefile作成（4時間）
  ```bash
  # .dockerignore作成
  cat > .dockerignore << 'EOF'
  .git
  .venv
  __pycache__
  *.pyc
  .pytest_cache
  reports/
  docs/
  EOF

  # Makefile作成（タスク自動化）
  cat > Makefile << 'EOF'
  .PHONY: build test deploy clean

  build:
      docker-compose -f docker/development/docker-compose.yml build

  test:
      docker-compose -f docker/test/docker-compose.yml run test

  deploy-staging:
      docker-compose -f docker/staging/docker-compose.yml up -d

  clean:
      docker-compose down -v
      docker system prune -f
  EOF
  ```

#### Day 3-4: テストカバレッジ改善（16時間）
- [ ] **Task 7.2.1**: utils/api_client.py テストカバレッジ向上（8時間）
  - リトライロジックテスト実装
  - エラーハンドリングテスト実装
  - BaseAPIClient包括的テスト
  - **目標**: カバレッジ 33.96% → 70%

- [ ] **Task 7.2.2**: config/settings.py テストカバレッジ向上（4時間）
  - 環境別設定テスト実装
  - バリデーションテスト
  - **目標**: カバレッジ 66.92% → 85%

- [ ] **Task 7.2.3**: tests/での統合（4時間）
  - httpx直接使用 → JSONPlaceholderClient活用
  - conftest.pyフィクスチャ拡張

#### Day 5: 品質保証（10時間）
- [ ] **Task 7.3.1**: 自動品質チェック統合（6時間）
  ```bash
  # pre-commit強化
  cat >> .pre-commit-config.yaml << 'EOF'
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
  EOF

  # CI/CD基本パイプライン
  mkdir -p .github/workflows
  # ci.yml作成（後述）
  ```

- [ ] **Task 7.3.2**: カバレッジ60%達成確認（4時間）
  ```bash
  # カバレッジ測定
  docker-compose -f docker/test/docker-compose.yml run test
  uv run pytest --cov-report=term-missing
  # HTMLレポート確認
  open reports/htmlcov/index.html
  ```

#### 成功指標（Week 7）
- [x] Docker 4環境構築完了
- [x] カバレッジ 60%達成
- [x] 自動テスト実行成功
- [x] 開発環境ホットリロード動作

---

### Week 8: CI/CD完全自動化 + カバレッジ75%達成（50時間）

#### Day 1-2: CI/CDパイプライン構築（16時間）
- [ ] **Task 8.1.1**: GitHub Actions CI設定（8時間）
  ```yaml
  # .github/workflows/ci.yml
  name: CI Pipeline

  on:
    push:
      branches: [ main, develop ]
    pull_request:
      branches: [ main ]

  jobs:
    test:
      runs-on: ubuntu-latest
      strategy:
        matrix:
          python-version: [3.10, 3.11, 3.12]

      steps:
        - uses: actions/checkout@v4

        - name: Set up Docker
          uses: docker/setup-buildx-action@v3

        - name: Build test image
          run: docker-compose -f docker/test/docker-compose.yml build

        - name: Run tests
          run: docker-compose -f docker/test/docker-compose.yml run test

        - name: Upload coverage
          uses: codecov/codecov-action@v4
          with:
            file: ./reports/coverage.xml
            fail_ci_if_error: true
  ```

- [ ] **Task 8.1.2**: CD（Staging）パイプライン（8時間）
  ```yaml
  # .github/workflows/cd-staging.yml
  name: Deploy to Staging

  on:
    push:
      branches: [ develop ]

  jobs:
    deploy:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4

        - name: Build staging image
          run: docker-compose -f docker/staging/docker-compose.yml build

        - name: Deploy to staging
          run: docker-compose -f docker/staging/docker-compose.yml up -d

        - name: Health check
          run: |
            sleep 10
            curl -f http://localhost:8000/health || exit 1
  ```

#### Day 3-4: 統合テスト実装（16時間）
- [ ] **Task 8.2.1**: 統合テスト設計・実装（12時間）
  ```python
  # tests/integration/test_api_workflow.py
  import pytest
  from utils.api_client import JSONPlaceholderClient

  @pytest.mark.integration
  async def test_user_posts_workflow():
      """ユーザー→投稿→コメント統合フロー"""
      async with JSONPlaceholderClient() as client:
          # ユーザー取得
          users = await client.get_users()
          assert len(users) > 0

          # 投稿取得
          posts = await client.get_user_posts(users[0]['id'])
          assert len(posts) > 0

          # コメント取得
          comments = await client.get_post_comments(posts[0]['id'])
          assert len(comments) > 0
  ```

- [ ] **Task 8.2.2**: 統合テスト実行・検証（4時間）

#### Day 5: カバレッジ75%達成（10時間）
- [ ] **Task 8.3.1**: カバレッジギャップ分析（4時間）
- [ ] **Task 8.3.2**: 追加テスト実装（6時間）

#### 成功指標（Week 8）
- [x] CI/CD自動化完了
- [x] カバレッジ 75%達成
- [x] 統合テスト実装完了
- [x] 自動デプロイ成功

---

### Week 9: E2Eテスト + パフォーマンス最適化（50時間）

#### Day 1-2: E2Eテスト実装（16時間）
- [ ] **Task 9.1.1**: E2Eテストフレームワーク構築（8時間）
  ```python
  # tests/e2e/test_complete_workflow.py
  import pytest
  from playwright.async_api import async_playwright

  @pytest.mark.e2e
  async def test_api_dashboard_workflow():
      """API Dashboard E2Eテスト"""
      async with async_playwright() as p:
          browser = await p.chromium.launch()
          page = await browser.new_page()

          # ダッシュボード表示
          await page.goto('http://localhost:8000/dashboard')

          # APIテスト実行
          await page.click('button#run-test')

          # 結果確認
          result = await page.text_content('.test-result')
          assert 'PASSED' in result
  ```

- [ ] **Task 9.1.2**: E2Eテストシナリオ実装（8時間）

#### Day 3-4: パフォーマンス最適化（16時間）
- [ ] **Task 9.2.1**: パフォーマンス監視実装（8時間）
  ```python
  # utils/performance_monitor.py
  import time
  import psutil
  from structlog import get_logger

  logger = get_logger()

  class PerformanceMonitor:
      def __init__(self):
          self.metrics = []

      async def measure_request(self, func, *args, **kwargs):
          start = time.perf_counter()
          result = await func(*args, **kwargs)
          duration = time.perf_counter() - start

          self.metrics.append({
              'function': func.__name__,
              'duration': duration,
              'memory': psutil.Process().memory_info().rss / 1024 / 1024
          })

          logger.info(
              "performance_measured",
              function=func.__name__,
              duration_ms=duration * 1000
          )

          return result
  ```

- [ ] **Task 9.2.2**: 負荷テスト実装（8時間）
  ```python
  # tests/performance/test_load_testing.py
  import pytest
  from locust import HttpUser, task, between

  class APITestUser(HttpUser):
      wait_time = between(1, 3)

      @task
      def get_users(self):
          self.client.get("/users")

      @task(3)
      def get_posts(self):
          self.client.get("/posts")
  ```

#### Day 5: 最適化検証（10時間）
- [ ] **Task 9.3.1**: パフォーマンスベンチマーク（6時間）
- [ ] **Task 9.3.2**: 最適化効果測定（4時間）

#### 成功指標（Week 9）
- [x] E2Eテスト実装完了
- [x] パフォーマンス監視稼働
- [x] 負荷テスト成功
- [x] レスポンス時間 < 200ms

---

### Week 10: ポートフォリオ最適化 + 市場投入（50時間）

#### Day 1-2: ドキュメント最適化（16時間）
- [ ] **Task 10.1.1**: README.md完全版作成（8時間）
  - プロジェクト概要
  - アーキテクチャ図
  - クイックスタート
  - API仕様
  - デプロイ手順

- [ ] **Task 10.1.2**: 面接デモスクリプト作成（8時間）
  - 技術スタック説明
  - 設計判断理由
  - トラブルシューティング事例

#### Day 3-4: 品質最終確認（16時間）
- [ ] **Task 10.2.1**: カバレッジ85%達成（8時間）
- [ ] **Task 10.2.2**: セキュリティスキャン（8時間）
  ```bash
  # セキュリティスキャン実行
  uv run bandit -r utils/ config/ -f json -o reports/security.json
  uv run safety check --json > reports/vulnerabilities.json
  ```

#### Day 5: 市場投入準備（10時間）
- [ ] **Task 10.3.1**: GitHub公開準備（6時間）
  - リポジトリ整理
  - LICENSE追加
  - 貢献ガイドライン

- [ ] **Task 10.3.2**: ポートフォリオサイト公開（4時間）

#### 成功指標（Week 10）
- [x] カバレッジ 85%達成
- [x] セキュリティスキャン合格
- [x] GitHub公開完了
- [x] 面接デモ準備完了

---

## 4. 品質評価ロードマップ

### 現状評価と目標

| 評価項目 | 現状 | Week 7 | Week 8 | Week 9 | Week 10 | 目標 |
|---------|------|--------|--------|--------|---------|------|
| **カバレッジ** | 42.51% | 60% | 75% | 80% | 85% | 85%+ |
| **Docker環境** | なし | 4環境構築 | CI/CD統合 | 最適化 | 本番対応 | 完全自動化 |
| **CI/CD** | なし | 基本構築 | 完全自動化 | E2E統合 | 本番デプロイ | フル自動化 |
| **市場価値** | C: 1,500-2,000円 | C+: 2,000-2,500円 | B: 2,500-3,500円 | B+: 3,500-4,000円 | A: 4,000-4,500円 | A+: 6,000-8,000円 |

### グレード詳細

#### C評価（現状）: 1,500-2,000円/時
**特徴**:
- 基本的なAPIテスト実装
- Pytestの基礎理解
- カバレッジ不足（42.51%）
- Docker未対応
- CI/CD未実装

**到達度**: 30%

#### B評価（Week 8目標）: 2,500-3,500円/時
**特徴**:
- Docker環境構築完了
- CI/CD基本自動化
- カバレッジ75%達成
- 統合テスト実装

**到達度**: 60%

#### A評価（Week 10目標）: 4,000-4,500円/時
**特徴**:
- 実務4環境完全対応
- CI/CD完全自動化
- カバレッジ85%達成
- E2Eテスト + パフォーマンス最適化
- セキュリティ対応完了

**到達度**: 85%

#### A+評価（最終目標）: 6,000-8,000円/時
**特徴**:
- 本番環境運用経験
- スケーラビリティ実証
- 包括的監視システム
- 実務プロジェクト実績

**到達度**: 100%（実務6ヶ月後）

---

## 5. 実行コマンド一覧

### 5.1 Docker環境構築コマンド

```bash
# 1. Base イメージビルド
docker build -t api-test-devops-portfolio-base:latest -f docker/base/Dockerfile .

# 2. Development環境起動
cd docker/development
docker-compose up -d
docker-compose logs -f

# 3. Test環境実行
cd docker/test
docker-compose run test

# 4. Staging環境デプロイ
cd docker/staging
docker-compose up -d

# 5. Production環境デプロイ
cd docker/production
docker-compose up -d

# 6. 全環境停止・クリーンアップ
docker-compose down -v
docker system prune -f
```

### 5.2 テスト実行コマンド

```bash
# 開発環境でのテスト
docker-compose -f docker/development/docker-compose.yml exec app \
  uv run pytest -v

# CI/CDテスト実行
docker-compose -f docker/test/docker-compose.yml run test

# カバレッジ測定
docker-compose -f docker/test/docker-compose.yml run test \
  --cov-report=term-missing

# 並列テスト実行
docker-compose -f docker/test/docker-compose.yml run test -n auto

# 特定マーカーテスト
docker-compose -f docker/test/docker-compose.yml run test -m integration
```

### 5.3 品質管理コマンド

```bash
# Ruff チェック・フォーマット
docker-compose -f docker/development/docker-compose.yml exec app \
  uv run ruff check --fix .
docker-compose -f docker/development/docker-compose.yml exec app \
  uv run ruff format .

# Mypy 型チェック
docker-compose -f docker/development/docker-compose.yml exec app \
  uv run mypy utils/ config/

# Bandit セキュリティスキャン
docker-compose -f docker/development/docker-compose.yml exec app \
  uv run bandit -r utils/ config/ -f json -o reports/security.json

# Safety 脆弱性チェック
docker-compose -f docker/development/docker-compose.yml exec app \
  uv run safety check --json > reports/vulnerabilities.json
```

### 5.4 デプロイコマンド

```bash
# Staging デプロイ
make deploy-staging

# Production デプロイ
make deploy-production

# ヘルスチェック
curl -f http://localhost:8000/health

# ログ確認
docker-compose -f docker/production/docker-compose.yml logs -f app
```

### 5.5 Makefileタスク

```bash
# ビルド
make build

# テスト実行
make test

# Stagingデプロイ
make deploy-staging

# Productionデプロイ
make deploy-production

# クリーンアップ
make clean

# カバレッジレポート
make coverage

# セキュリティスキャン
make security-scan
```

---

## 6. 成功指標

### 6.1 定量的指標

| 指標 | 現状 | Week 7 | Week 8 | Week 9 | Week 10 | 目標 |
|------|------|--------|--------|--------|---------|------|
| **テストカバレッジ** | 42.51% | 60% | 75% | 80% | 85% | ✅ 85%+ |
| **テスト数** | 106 | 150 | 200 | 250 | 300 | ✅ 300+ |
| **ビルド時間** | N/A | 5分 | 3分 | 2分 | 1分 | ✅ <2分 |
| **デプロイ時間** | N/A | 10分 | 5分 | 3分 | 2分 | ✅ <3分 |
| **レスポンス時間** | N/A | 500ms | 300ms | 200ms | 150ms | ✅ <200ms |
| **Docker イメージサイズ** | N/A | 500MB | 400MB | 300MB | 250MB | ✅ <300MB |

### 6.2 定性的指標

#### Week 7成功基準
- [x] Docker 4環境構築完了
- [x] 開発環境ホットリロード動作
- [x] テスト環境CI/CD統合準備
- [x] カバレッジ60%達成

#### Week 8成功基準
- [x] CI/CD完全自動化
- [x] 統合テスト実装完了
- [x] カバレッジ75%達成
- [x] 自動デプロイ成功

#### Week 9成功基準
- [x] E2Eテスト実装完了
- [x] パフォーマンス監視稼働
- [x] 負荷テスト成功
- [x] レスポンス時間 < 200ms

#### Week 10成功基準
- [x] カバレッジ85%達成
- [x] セキュリティスキャン合格
- [x] GitHub公開完了
- [x] 面接デモ準備完了

### 6.3 市場価値指標

#### 現状（C評価）: 1,500-2,000円/時
- 基本的なAPIテスト能力
- Pytest基礎理解
- カバレッジ不足

#### Week 8（B評価）: 2,500-3,500円/時
- Docker環境構築能力
- CI/CD基本理解
- 統合テスト実装能力

#### Week 10（A評価）: 4,000-4,500円/時
- 実務4環境対応能力
- CI/CD完全自動化
- E2E + パフォーマンステスト

#### 最終目標（A+評価）: 6,000-8,000円/時
- 本番環境運用経験
- スケーラビリティ実証
- 実務プロジェクト実績

---

## 7. リスク管理

### 7.1 技術的リスク

| リスク | 影響度 | 発生確率 | 対策 |
|--------|--------|----------|------|
| Docker環境構築失敗 | 高 | 中 | 段階的構築、Base→Dev→Testの順で検証 |
| カバレッジ目標未達 | 中 | 中 | 優先度付け、重要機能から実装 |
| CI/CD統合エラー | 高 | 低 | ローカルテスト徹底、段階的デプロイ |
| パフォーマンス低下 | 中 | 低 | 事前ベンチマーク、最適化余地確保 |

### 7.2 スケジュールリスク

| リスク | 影響度 | 発生確率 | 対策 |
|--------|--------|----------|------|
| 時間超過 | 中 | 高 | バッファ時間確保（各週10時間） |
| 優先度誤り | 中 | 中 | 週次レビュー、柔軟な計画調整 |
| スキル不足 | 低 | 低 | AI協働フル活用、段階的学習 |

### 7.3 品質リスク

| リスク | 影響度 | 発生確率 | 対策 |
|--------|--------|----------|------|
| テスト品質低下 | 高 | 中 | コードレビュー、自動品質チェック |
| セキュリティ脆弱性 | 高 | 低 | 定期スキャン、最新パッチ適用 |
| 技術的負債増大 | 中 | 中 | リファクタリング時間確保 |

---

## 8. 次のアクション

### 即座実行（今日）
1. **Docker基盤ディレクトリ作成**
   ```bash
   mkdir -p docker/{base,development,test,staging,production}
   ```

2. **Base Dockerfile作成**
   - 上記「2.1 Base Dockerfile」を実装
   - ビルドテスト実行

3. **Development環境構築**
   - Dockerfile、docker-compose.yml、.env作成
   - 起動テスト実行

### Week 7計画
- Day 1-2: Docker環境構築
- Day 3-4: テストカバレッジ改善
- Day 5: 品質保証

### Week 8以降
- Week 8: CI/CD完全自動化
- Week 9: E2Eテスト + パフォーマンス最適化
- Week 10: ポートフォリオ最適化 + 市場投入

---

## 9. 参考資料

### 公式ドキュメント
- [Docker公式ドキュメント](https://docs.docker.com/)
- [Docker Compose](https://docs.docker.com/compose/)
- [GitHub Actions](https://docs.github.com/en/actions)
- [Pytest](https://docs.pytest.org/)
- [uv](https://github.com/astral-sh/uv)

### ベストプラクティス
- [12 Factor App](https://12factor.net/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [CI/CD Best Practices](https://www.atlassian.com/continuous-delivery/principles/continuous-integration-vs-delivery-vs-deployment)

### セキュリティ
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Docker Security](https://docs.docker.com/engine/security/)

---

## 10. まとめ

本マスタープランは、APIテスト + DevOpsポートフォリオを**実務即戦力レベル（A評価: 4,000-4,500円/時）**に引き上げるための包括的なロードマップです。

### 重要なポイント
1. **段階的実装**: Week 7→8→9→10で着実に品質向上
2. **実務4環境対応**: Development/Test/Staging/Production完全構築
3. **完全自動化**: CI/CD + 自動テスト + 自動デプロイ
4. **品質保証**: カバレッジ85%、セキュリティスキャン合格

### 期待される成果
- **市場価値向上**: C評価（1,500-2,000円/時） → A評価（4,000-4,500円/時）
- **実務即戦力**: Docker + CI/CD + テスト自動化の実践経験
- **ポートフォリオ完成**: GitHub公開、面接デモ準備完了

---

**作成日**: 2025年10月02日
**次回レビュー**: Week 7完了時（2025年10月09日予定）
**責任者**: Yuta
