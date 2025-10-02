# 改訂版28週間学習プラン - AI協働最適化版

*最終更新: 2025年10月01日*

## プラン概要

**目標**: Python + API Testing + DevOps スキルで時給4,500円のフリーランス案件獲得
**期間**: 28週間 (従来24週から4週延長)
**AI協働方針**: 学習60-70%支援 → 実務30-35%支援への段階的移行
**重要変更点**: 復習週追加、認知負荷管理、自律スキル検証の組み込み

### 目標時給推移

| Phase | Week | 開始時給 | 終了時給 | 到達レベル |
|-------|------|---------|---------|----------|
| Phase 1 | 1-14 | 2,200円 | 3,200円 | Junior Python/API Developer |
| Phase 2 | 15-24 | 3,200円 | 4,200円 | Junior-Mid DevOps Engineer |
| Phase 3 | 25-28 | 4,200円 | 4,500円+ | Market-Ready DevOps Engineer |

## Phase 1: Foundation & Fundamentals (Week 1-14)

### Week 1-2: Python基礎 + httpx入門

**学習時間**: 40時間 (1日6時間 × 6日 + 復習4時間)
**AI協働率**: 70% (学習加速期)

#### 技術目標
```python
# 習得内容
- httpx.Client basics (GET/POST/PUT/DELETE)
- Response handling (status codes, JSON parsing)
- Basic error handling (try/except patterns)
- Type hints (str, int, dict, List, Optional)
```

#### 実装課題
1. **JSONPlaceholder API Client v0.1**
   ```python
   # 必須実装メソッド
   - get_user(user_id: int) -> dict
   - get_posts(user_id: int | None) -> list[dict]
   - create_post(title: str, body: str, user_id: int) -> dict
   ```

2. **エラーハンドリング基礎**
   ```python
   # 実装必須例外
   class APIClientError(Exception): pass
   class APIConnectionError(APIClientError): pass
   class APITimeoutError(APIClientError): pass
   ```

#### 成果物
- [ ] api_client.py (200-300行)
- [ ] 20テストケース (pytest)
- [ ] README.md (使い方ドキュメント)

**Week 2金曜: 自律スキルチェック**
```
AI禁止で以下実装:
- get_todos(user_id: int) メソッド追加
- 5テストケース作成
- 目標: 60分以内完成、テスト全パス
```

---

### Week 3-4: Async/Await + Advanced Error Handling

**学習時間**: 40時間
**AI協働率**: 65% (段階的自律化開始)

#### 技術目標
```python
# 習得内容
- asyncio basics (async/await, gather())
- httpx.AsyncClient patterns
- Context managers (async with)
- Exception hierarchy design
```

#### 実装課題
1. **Async API Client**
   ```python
   class AsyncAPIClient:
       async def get_user_data(self, user_id: int) -> dict:
           # 並行実行パターン
           user, posts, todos = await asyncio.gather(
               self.get_user(user_id),
               self.get_posts(user_id),
               self.get_todos(user_id)
           )
   ```

2. **リトライロジック実装**
   ```python
   async def _make_request_with_retry(
       self, method: str, endpoint: str, max_retries: int = 3
   ) -> httpx.Response:
       # 4xx: immediate fail, 5xx: retry
   ```

#### 成果物
- [ ] async_api_client.py (400-500行)
- [ ] 40テストケース (pytest-asyncio)
- [ ] パフォーマンス比較ドキュメント (sync vs async)

**Week 4金曜: 自律スキルチェック**
```
AI禁止で以下実装:
- Async get_albums()メソッド
- リトライロジック単体テスト3件
- 目標: 90分以内、カバレッジ80%以上
```

---

### Week 5-6: Pydantic Settings + Logging

**学習時間**: 40時間
**AI協働率**: 60%

#### 技術目標
```python
# 習得内容
- Pydantic BaseSettings patterns
- Environment variable management (__delimiter)
- structlog configuration
- Log levels and filtering
```

#### 実装課題
1. **Type-Safe Configuration**
   ```python
   class Settings(BaseSettings):
       model_config = SettingsConfigDict(
           env_file=".env",
           env_nested_delimiter="__"
       )
       api: APIConfig
       log: LogConfig
   ```

2. **Structured Logging**
   ```python
   logger = structlog.get_logger()
   logger.info("api_request",
               endpoint=endpoint,
               method=method,
               status_code=response.status_code)
   ```

#### 成果物
- [ ] config/settings.py (200-300行)
- [ ] .env.example (全設定項目文書化)
- [ ] 60テストケース (設定バリデーション含む)

---

### Week 7: 復習週 + 自律実装チャレンジ ⭐

**目的**: これまでの学習を統合し、自律能力を測定
**AI使用**: 完全禁止 (概念確認のみドキュメント参照可)

#### 実装課題: Mini API Client (完全自律)
```
要件:
1. 新API統合 (例: OpenWeatherMap or GitHub API)
2. Sync + Async両対応
3. Pydantic設定管理
4. エラーハンドリング完備
5. 50テストケース (カバレッジ75%以上)

評価基準:
- 完成度: 全機能動作 (40点)
- コード品質: ruff + mypy合格 (30点)
- テスト: カバレッジ + 全パス (20点)
- ドキュメント: README明瞭性 (10点)

合格ライン: 70点以上
不合格時: Week 1-6復習モードに1週間追加
```

---

### Week 8-9: Pytest Advanced + Fixtures

**学習時間**: 40時間
**AI協働率**: 60%

#### 技術目標
```python
# 習得内容
- Fixture scope management (session/module/function)
- Parametrized testing (@pytest.mark.parametrize)
- Factory patterns for test data
- Mock and patch strategies
```

#### 実装課題
1. **Advanced Test Suite**
   ```python
   @pytest.fixture(scope="session")
   async def async_client(test_config):
       async with AsyncAPIClient(test_config) as client:
           yield client

   @pytest.mark.parametrize("user_id,expected_posts", [
       (1, 10), (2, 10), (3, 10)
   ])
   async def test_get_posts_count(async_client, user_id, expected_posts):
       posts = await async_client.get_posts(user_id)
       assert len(posts) >= expected_posts
   ```

2. **Test Data Factories**
   ```python
   @pytest.fixture
   def user_data_factory():
       def create_user(user_id=1, name="Test User", **kwargs):
           return {"id": user_id, "name": name, **kwargs}
       return create_user
   ```

#### 成果物
- [ ] tests/conftest.py (300-400行)
- [ ] 100テストケース (累計)
- [ ] テスト設計ドキュメント

**Week 9金曜: 自律スキルチェック**
```
AI禁止で以下実装:
- Parametrizedテスト5件
- Factory fixture 1件
- 目標: 60分以内、全テストパス
```

---

### Week 10-11: Code Quality Tools (ruff, mypy, bandit)

**学習時間**: 40時間
**AI協働率**: 55%

#### 技術目標
```bash
# 習得ツール
- ruff check + format (linting)
- mypy (type checking)
- bandit (security scanning)
- safety (dependency vulnerability)
```

#### 実装課題
1. **Pre-commit Setup**
   ```yaml
   # .pre-commit-config.yaml
   repos:
     - repo: https://github.com/astral-sh/ruff-pre-commit
       hooks:
         - id: ruff
           args: [--fix]
         - id: ruff-format
   ```

2. **pyproject.toml最適化**
   ```toml
   [tool.ruff]
   line-length = 100
   select = ["E", "F", "I", "N", "W"]

   [tool.mypy]
   strict = true
   warn_return_any = true
   ```

#### 成果物
- [ ] .pre-commit-config.yaml
- [ ] pyproject.toml (完全設定)
- [ ] 全ファイルでruff + mypy合格
- [ ] セキュリティスキャン結果レポート

---

### Week 12-13: Basic CI/CD (GitHub Actions)

**学習時間**: 40時間
**AI協働率**: 50% (実務移行期)

#### 技術目標
```yaml
# 習得内容
- GitHub Actions workflow syntax
- Matrix strategy (Python versions)
- Cache management (uv cache)
- Artifact upload/download
```

#### 実装課題
1. **Lint + Test Workflow**
   ```yaml
   # .github/workflows/test.yml
   name: Test
   on: [push, pull_request]
   jobs:
     test:
       runs-on: ubuntu-latest
       strategy:
         matrix:
           python-version: ["3.10", "3.11", "3.12"]
       steps:
         - uses: actions/checkout@v4
         - uses: astral-sh/setup-uv@v2
         - run: uv run pytest --cov
   ```

2. **Code Quality Workflow**
   ```yaml
   # .github/workflows/quality.yml
   - run: uv run ruff check
   - run: uv run mypy .
   - run: uv run bandit -r .
   ```

#### 成果物
- [ ] .github/workflows/test.yml
- [ ] .github/workflows/quality.yml
- [ ] CI passing badges in README
- [ ] 150テストケース (累計)

**Week 13金曜: 自律スキルチェック**
```
AI禁止で以下実装:
- Security Scan workflowを追加
- bandit + safety統合
- 目標: 90分以内、CI成功
```

---

### Week 14: Phase 1統合復習 + Mini Project ⭐⭐

**目的**: Phase 1の全スキルを統合し、実務レベル確認
**AI使用**: 最小限 (デバッグ時のヒントのみ)

#### 実装課題: Complete API Testing Portfolio
```
要件:
1. 本番品質APIクライアント
   - Sync + Async完全実装
   - エラーハンドリング完備
   - Pydantic設定管理
   - Structured logging統合

2. 包括的テストスイート
   - 150テストケース以上
   - カバレッジ80%以上
   - Parametrized + Factory patterns活用

3. CI/CD完全自動化
   - Lint + Test + Security workflows
   - Python 3.10/3.11/3.12 matrix
   - 全チェック合格

4. プロフェッショナルドキュメント
   - README (使い方 + アーキテクチャ)
   - APIリファレンス
   - パフォーマンスベンチマーク結果

評価基準:
- 技術実装: 全機能動作 (40点)
- テスト品質: カバレッジ + 設計 (30点)
- CI/CD: 全workflow成功 (20点)
- ドキュメント: プロレベル (10点)

合格ライン: 80点以上
Phase 2進行可否の最終判定
```

**Phase 1完了時の自律達成率目標: 55-60%**

---

## Phase 2: Practical DevOps Skills (Week 15-24)

### Week 15-16: Docker Fundamentals

**学習時間**: 40時間
**AI協働率**: 50%

#### 技術目標
```dockerfile
# 習得内容
- Dockerfile multi-stage builds (4段階)
- docker-compose.yml (dev + test環境)
- Volume management (data persistence)
- Network configuration (service communication)
```

#### 実装課題
1. **4-Stage Dockerfile**
   ```dockerfile
   # Stage 1: Base
   FROM python:3.12-slim AS base
   RUN pip install uv
   COPY pyproject.toml uv.lock ./
   RUN uv sync --frozen

   # Stage 2: Development
   FROM base AS dev
   RUN uv sync --dev
   COPY . .

   # Stage 3: Test
   FROM dev AS test
   RUN uv run pytest --cov

   # Stage 4: Production
   FROM base AS prod
   COPY --from=dev /app .
   CMD ["uv", "run", "python", "-m", "app"]
   ```

2. **docker-compose.yml**
   ```yaml
   services:
     app:
       build:
         context: .
         target: dev
       volumes:
         - .:/app
       environment:
         - API__BASE_URL=http://jsonplaceholder.typicode.com

     test:
       build:
         context: .
         target: test
       depends_on:
         - app
   ```

#### 成果物
- [ ] Dockerfile (4-stage optimized)
- [ ] docker-compose.yml (dev + test)
- [ ] .dockerignore
- [ ] Docker実行ドキュメント

**Week 16金曜: 自律スキルチェック**
```
AI禁止で以下実装:
- Production stage最適化 (イメージサイズ削減)
- docker-compose healthcheck追加
- 目標: 120分以内、全コンテナ起動成功
```

---

### Week 17-18: Docker + CI/CD Integration

**学習時間**: 40時間
**AI協働率**: 45%

#### 技術目標
```yaml
# 習得内容
- GitHub Actions Docker integration
- Docker layer caching strategies
- Multi-platform builds (linux/amd64, linux/arm64)
- Container Registry (GitHub Packages)
```

#### 実装課題
1. **Docker Build Workflow**
   ```yaml
   # .github/workflows/docker.yml
   - name: Build and test
     run: |
       docker-compose build
       docker-compose run test

   - name: Push to registry
     if: github.ref == 'refs/heads/main'
     run: docker push ghcr.io/${{ github.repository }}:latest
   ```

2. **Image Optimization**
   ```
   目標イメージサイズ:
   - Base: < 200MB
   - Dev: < 400MB
   - Test: < 450MB
   - Prod: < 250MB
   ```

#### 成果物
- [ ] .github/workflows/docker.yml
- [ ] GitHub Packages統合
- [ ] 220テストケース (累計)
- [ ] Docker最適化レポート

---

### Week 19-20: Security Fundamentals (OWASP Top 10)

**学習時間**: 40時間
**AI協働率**: 40% (実務レベル)

#### 技術目標
```python
# 習得内容
- Input validation (Pydantic validators)
- SQL injection prevention (parameterized queries)
- Secrets management (環境変数 + .env)
- Dependency scanning (safety, pip-audit)
```

#### 実装課題
1. **Security Test Suite**
   ```python
   # tests/security/test_input_validation.py
   @pytest.mark.security
   async def test_sql_injection_prevention():
       malicious_input = "1' OR '1'='1"
       with pytest.raises(ValidationError):
           await client.get_user(malicious_input)

   @pytest.mark.security
   def test_sensitive_data_not_logged():
       # API keyがログに出力されないことを確認
       assert "sk-" not in caplog.text
   ```

2. **Bandit + Safety Integration**
   ```yaml
   # .github/workflows/security.yml
   - run: uv run bandit -r . -f json -o bandit-report.json
   - run: uv run safety check --json > safety-report.json
   ```

#### 成果物
- [ ] tests/security/ (30セキュリティテスト)
- [ ] .github/workflows/security.yml
- [ ] セキュリティ監査レポート
- [ ] 250テストケース (累計)

---

### Week 21: Docker/Security統合復習 ⭐

**目的**: Docker + Security統合を自律実装で確認
**AI使用**: 禁止 (ドキュメント参照のみ)

#### 実装課題: Secure Dockerized Application
```
要件:
1. Production-grade Dockerfile
   - セキュリティベストプラクティス適用
   - Non-root user実行
   - Minimal attack surface

2. Security-hardened CI/CD
   - OWASP依存性チェック
   - Container image scanning
   - Secrets scanning (git-secrets)

3. セキュリティテストスイート
   - 40セキュリティテスト実装
   - OWASP Top 10カバレッジ

評価基準:
- Docker実装: Production-ready (40点)
- Security tests: 包括的 (35点)
- CI/CD統合: 完全自動化 (15点)
- ドキュメント: セキュリティガイド (10点)

合格ライン: 75点以上
```

---

### Week 22-23: Real-world Integration Project

**学習時間**: 50時間 (実務模擬)
**AI協働率**: 35% (実務レベル維持)

#### プロジェクト: フリーランス案件シミュレーション

**要件定義 (擬似クライアント要求)**
```
案件: JSONPlaceholder APIの完全ラッパーライブラリ開発
時給: 3,500円
期間: 2週間 (100時間)
納品物:
1. Python package (PyPI公開レベル)
2. 完全なAPI coverage (全エンドポイント)
3. 包括的ドキュメント (Sphinx生成)
4. CI/CD完全自動化
5. セキュリティ監査合格
```

#### 実装チェックリスト
- [ ] 全APIエンドポイント実装 (10+)
- [ ] 280テストケース (カバレッジ85%+)
- [ ] Sphinx documentation (自動生成)
- [ ] PyPI-ready setup.py
- [ ] GitHub Actions 4-workflow統合
- [ ] Docker multi-platform builds
- [ ] Security scan全合格

#### 評価基準 (実案件基準)
```
納品品質:
- コード品質: 全チェック合格 (30点)
- テストカバレッジ: 85%以上 (25点)
- ドキュメント: プロフェッショナル (20点)
- CI/CD: 完全自動化 (15点)
- セキュリティ: OWASP合格 (10点)

合格ライン: 85点以上
Phase 3進行可否の判定
```

---

### Week 24: Phase 2総合評価 + 改善

**目的**: Phase 2成果物の品質向上と弱点補強
**AI協働率**: 30%

#### 実施項目
1. **コードレビュー (自己評価)**
   - ruff --select ALL実行 (全ルール適用)
   - mypy --strict適用
   - カバレッジ85%未満箇所の補強

2. **パフォーマンステスト**
   ```python
   # tests/performance/test_benchmarks.py
   @pytest.mark.performance
   async def test_concurrent_requests_throughput():
       # 100並行リクエストで5秒以内
       start = time.time()
       results = await asyncio.gather(*[
           client.get_user(i % 10 + 1) for i in range(100)
       ])
       duration = time.time() - start
       assert duration < 5.0
   ```

3. **ドキュメント完成度チェック**
   - README: 初見者が30分で使えるか
   - API Reference: 全メソッド文書化
   - Architecture: 図解追加

**Phase 2完了時の自律達成率目標: 65-70%**

---

## Phase 3: Market Readiness (Week 25-28)

### Week 25-26: Portfolio Optimization

**学習時間**: 30時間 (営業準備重視)
**AI協働率**: 25%

#### 実施項目

1. **GitHub Repository Polish**
   ```markdown
   # README.md 強化項目
   - [x] バッジ追加 (build status, coverage, security)
   - [x] デモGIF/動画 (実行例)
   - [x] Architecture diagram (mermaid)
   - [x] Performance benchmarks (グラフ)
   - [x] English + 日本語両対応
   ```

2. **Live Demo環境構築**
   - Render.com or Railway.app無料プラン
   - Public API endpoint公開
   - Swagger UI統合

3. **Case Study作成**
   ```
   Week 22-23プロジェクトの実装過程を文書化:
   - 要件定義 → 設計 → 実装 → テスト → 納品
   - 技術的課題と解決策
   - パフォーマンス改善事例
   - セキュリティ対策内容
   ```

#### 成果物
- [ ] GitHub README (English + 日本語)
- [ ] Live demo環境 (URL公開)
- [ ] Case study PDF (5-10ページ)
- [ ] Portfolio website (簡易版)

---

### Week 27: Mock Interview & Pitch Practice

**学習時間**: 25時間
**AI協働率**: 20% (ピッチ練習のみAI活用)

#### 実施項目

1. **技術面接シミュレーション**
   ```
   想定質問30問:
   - Python: async/await, type hints, context managers
   - Testing: pytest patterns, coverage strategies
   - Docker: multi-stage builds, optimization
   - CI/CD: GitHub Actions, security integration
   - Security: OWASP Top 10, best practices
   ```

2. **ポートフォリオプレゼン練習**
   ```
   5分間ピッチ構成:
   1. 自己紹介 (30秒)
   2. 技術スタック (60秒)
   3. 主要プロジェクト紹介 (120秒)
   4. テスト/セキュリティへのこだわり (60秒)
   5. 質疑応答準備 (30秒)
   ```

3. **フリーランスプラットフォーム登録準備**
   ```
   必須項目:
   - Levtech Freelance: プロフィール + スキルシート
   - Findy Freelance: GitHub連携 + 職務経歴書
   - Foster Freelance: ポートフォリオ登録
   - Upwork: Profile + Portfolio items
   ```

#### 成果物
- [ ] 面接回答集 (30問)
- [ ] ピッチ原稿 (5分版 + 3分版)
- [ ] プラットフォーム登録完了 (4社)

---

### Week 28: Job Application Launch

**学習時間**: 20時間
**AI協働率**: 15% (応募文面チェックのみ)

#### 実施項目

1. **案件応募 (並行実施)**
   ```
   目標応募数:
   - Levtech Freelance: 5件 (4,000-5,000円/時)
   - Findy Freelance: 5件 (3,500-5,000円/時)
   - Foster Freelance: 3件 (3,500-4,500円/時)
   - Upwork: 3件 ($25-40/hour)

   優先条件:
   1. Python + API関連
   2. テスト/CI/CD要求あり
   3. リモートワーク
   4. 週2-3日稼働可能
   ```

2. **応募戦略**
   ```
   A案件 (高単価): 5,000円/時
   - ポートフォリオ全力アピール
   - Case study PDF添付

   B案件 (実績優先): 3,500-4,000円/時
   - 確実な受注を狙う
   - 初回実績作りを優先
   ```

3. **初回面談準備**
   - 想定質問への回答準備
   - ライブコーディング練習 (LeetCode Easy 10問)
   - GitHub repository説明リハーサル

#### Week 28終了時の目標
- [ ] 書類選考通過: 5件以上
- [ ] 面談実施: 3件以上
- [ ] 初回案件受注: 1件 (3,500-4,000円/時でも可)

**Phase 3完了時の自律達成率目標: 70%以上**

---

## AI協働効率測定システム

### 週次トラッキングスクリプト

```python
# scripts/ai_collaboration_tracker.py
from datetime import datetime
from pathlib import Path
import json

class AICollaborationTracker:
    def __init__(self):
        self.metrics_file = Path("docs/ai_metrics.json")

    def log_session(
        self,
        date: str,
        ai_assisted_hours: float,
        autonomous_hours: float,
        ai_code_lines: int,
        own_code_lines: int,
        ai_questions: int,
        concepts_learned: list[str]
    ):
        """毎日の学習セッション記録"""
        metrics = {
            "date": date,
            "hours": {
                "ai_assisted": ai_assisted_hours,
                "autonomous": autonomous_hours,
                "total": ai_assisted_hours + autonomous_hours
            },
            "code": {
                "ai_generated": ai_code_lines,
                "own_written": own_code_lines,
                "total": ai_code_lines + own_code_lines
            },
            "learning": {
                "ai_questions": ai_questions,
                "concepts": concepts_learned
            }
        }

        # 効率計算
        metrics["efficiency"] = {
            "ai_dependency_rate": (
                ai_assisted_hours / (ai_assisted_hours + autonomous_hours) * 100
            ),
            "autonomous_code_rate": (
                own_code_lines / (ai_code_lines + own_code_lines) * 100
            )
        }

        # ファイルに追記
        all_metrics = self._load_metrics()
        all_metrics.append(metrics)
        self._save_metrics(all_metrics)

        return metrics

    def generate_weekly_report(self, week_number: int):
        """週次レポート生成"""
        all_metrics = self._load_metrics()
        # ... レポート生成ロジック
```

### 自律スキル検証プロトコル

**毎週水曜: AI-Free Day**

```bash
# AI禁止日の作業手順
1. 朝 (9:00-12:00): 課題実装 (AI完全禁止)
   - GitHub Copilot無効化
   - Claude Code使用禁止
   - Stack Overflow/docs参照のみ

2. 昼 (13:00-15:00): テスト + デバッグ
   - pytest実行
   - ruff + mypy実行
   - エラー修正 (ドキュメントのみ参照可)

3. 夕方 (15:00-17:00): 評価 + 振り返り
   - AI使用版との比較
   - 自律達成率計算
   - 改善ポイント記録

# 評価シート (毎週記録)
自律達成率 = (完成度 × 0.4) + (品質 × 0.3) + (速度 × 0.3)
- 完成度: 要求機能の実装率 (0-100%)
- 品質: ruff/mypy合格 + テストパス (0-100%)
- 速度: 目標時間内完了 (0-100%)
```

### Phase別自律達成率目標

| Phase | Week | 目標自律達成率 | 撤退基準 |
|-------|------|---------------|---------|
| Phase 1 | 1-7 | 40-50% | <25% で復習1週追加 |
| Phase 1 | 8-14 | 50-60% | <35% で復習1週追加 |
| Phase 2 | 15-21 | 60-70% | <45% で復習1週追加 |
| Phase 2-3 | 22-28 | 70%+ | <55% でPhase 2延長 |

---

## リスク管理計画

### High Risk項目と対策

#### Risk 1: 認知過負荷 (Week 15-18 Docker導入期)

**リスク評価**: 高 (確率70%, 影響度: 中)

**対策**:
1. Docker学習をWeek 15-16に集中 (Week 17-18は統合のみ)
2. 1日の学習時間を6時間に制限 (通常7-8時間から削減)
3. Week 17に中間復習日を設定

**モニタリング**:
- 毎日の学習時間記録
- 理解度チェックテスト (60%未満で警告)

**撤退基準**:
- 2週連続で週次目標未達 → 1週間復習モード移行

---

#### Risk 2: AI過度依存 (実推定70-80%)

**リスク評価**: 高 (確率80%, 影響度: 高)

**対策**:
1. **毎週水曜AI-Free Day必須化**
2. 自律達成率が目標-15%下回ったら警告
3. Phase 2以降は実務レベル (AI協働30-35%に抑制)

**モニタリング**:
```python
# 毎週金曜実行
if autonomous_rate < target_rate - 15:
    print("⚠️ WARNING: AI dependency too high")
    print("Action: 1 week review mode required")
```

**撤退基準**:
- 3週連続で自律達成率-15%未満 → Phase巻き戻し

---

#### Risk 3: 初回案件獲得失敗

**リスク評価**: 中 (確率50%, 影響度: 中)

**対策**:
1. **Week 27-28で並行応募**
   - Levtech: 5件
   - Findy: 5件
   - Foster: 3件
   - Upwork: 3件 (計16件)

2. **段階的単価戦略**
   - 初回案件: 3,000-3,500円/時でも受諾可
   - 2件目以降: 4,000円/時目標
   - 3件目: 4,500円/時達成

3. **バックアップ案件**
   - Upwork小案件 ($15-20/hour) も検討
   - 実績作り優先期間 (1-2ヶ月)

**撤退基準**:
- Week 30までに1件も受注できない場合
  → ポートフォリオ強化 + スキル補強に2週間追加

---

## 成功指標 (KPI)

### Phase 1完了時 (Week 14)

**技術指標**
- [ ] 150テストケース (カバレッジ80%+)
- [ ] GitHub Actions 2-workflow稼働 (lint/test, quality)
- [ ] ruff + mypy全ファイル合格
- [ ] API client完全実装 (sync + async)

**学習指標**
- [ ] 自律達成率55-60%
- [ ] AI-Free Day完遂率75%以上
- [ ] 週次学習時間40時間平均維持

**市場準備**
- [ ] GitHub README完成 (日本語)
- [ ] Levtech/Findyプロフィール作成開始

---

### Phase 2完了時 (Week 24)

**技術指標**
- [ ] 280テストケース (カバレッジ85%+)
- [ ] Docker 4-stage構築完了
- [ ] GitHub Actions 4-workflow稼働
- [ ] セキュリティスキャン全合格 (Critical 0件)

**学習指標**
- [ ] 自律達成率65-70%
- [ ] AI-Free Day完遂率80%以上
- [ ] 実務レベルプロジェクト完遂 (Week 22-23)

**市場準備**
- [ ] ポートフォリオ完成 (English + 日本語)
- [ ] Case study作成完了
- [ ] Live demo公開

---

### Phase 3完了時 (Week 28)

**技術指標**
- [ ] 300テストケース (カバレッジ87%+)
- [ ] Production-ready codebase
- [ ] GitHub Stars 10+ (コミュニティ評価)

**学習指標**
- [ ] 自律達成率70%以上
- [ ] 総学習時間1,000時間達成
- [ ] AI協働最適比率確立 (実務30-35%)

**市場成果**
- [ ] 初回案件受注 (3,500-4,000円/時)
- [ ] 書類選考通過5件以上
- [ ] プラットフォーム登録完了 (4社)

---

## 週次ルーティン

### 毎週月曜 (計画)
- [ ] 今週の学習目標設定
- [ ] AIトラッキングシート準備
- [ ] GitHub Issue作成 (週次タスク)

### 毎週水曜 (自律検証)
- [ ] **AI-Free Day実施** (完全自律作業)
- [ ] 自律達成率測定
- [ ] 改善ポイント記録

### 毎週金曜 (振り返り)
- [ ] 週次学習レポート作成
- [ ] AI協働効率分析
- [ ] 次週計画調整

### 毎週日曜 (復習)
- [ ] 今週の概念復習
- [ ] ドキュメント整理
- [ ] GitHub commit整理

---

## Phase間評価基準

### Phase 1 → Phase 2 進行判定 (Week 14)

**必須条件 (全て満たすこと)**
- [ ] Mini Project 70点以上
- [ ] 自律達成率55%以上
- [ ] 150テストケース (カバレッジ80%+)
- [ ] CI/CD 2-workflow稼働

**推奨条件 (2つ以上満たすこと)**
- [ ] GitHub Stars 3+
- [ ] 技術ブログ1記事公開
- [ ] Stack Overflow貢献1件

**不合格時の対応**:
- 1週間復習モード (Week 1-14の弱点補強)
- 再評価実施 (Mini Project再実装)

---

### Phase 2 → Phase 3 進行判定 (Week 24)

**必須条件 (全て満たすこと)**
- [ ] Real-world Project 85点以上
- [ ] 自律達成率65%以上
- [ ] 280テストケース (カバレッジ85%+)
- [ ] Docker + CI/CD完全統合

**推奨条件 (2つ以上満たすこと)**
- [ ] GitHub Stars 8+
- [ ] Case study完成度80%以上
- [ ] Mock interview合格 (75%以上正答)

**不合格時の対応**:
- 2週間補強モード (弱点集中改善)
- Phase 3開始を2週間延期

---

## 最終チェックリスト (Week 28完了時)

### 技術成果物
- [ ] GitHub Repository (300+ stars目標)
- [ ] PyPI Package (公開レベル)
- [ ] Live Demo (稼働中)
- [ ] Comprehensive Documentation

### 学習成果
- [ ] 総学習時間1,000時間以上
- [ ] 自律達成率70%以上
- [ ] AI協働最適化確立

### 市場参入
- [ ] 初回案件受注 (3,500円/時以上)
- [ ] プラットフォーム登録完了 (4社)
- [ ] 継続案件見込み (2件目応募済み)

---

**最終目標**: Week 28終了時に時給4,500円の実務案件を安定受注できる実力とポートフォリオを保有
