# Dockerfile - 4-stage Multi-stage builds
# 最終更新: 2026年01月29日
# 品質基準: イメージサイズ < 200MB, ビルド時間 < 3分

# ============================================================
# Stage 1: Base - 共通ベースイメージ
# ============================================================
# セキュリティ: SHA256ダイジェスト固定（サプライチェーン攻撃防止）
# 更新フロー: Dependabotが週次（月曜 09:00 JST）で自動検出・PR作成
# 手動更新: docker pull python:3.12-slim && docker inspect --format='{{index .RepoDigests 0}}' python:3.12-slim
# 2026-02-16更新: Python 3.14→3.12 (pyproject.toml/ci.yml整合性維持)
FROM python:3.12-slim@sha256:9e01bf1ae5db7649a236da7be1e94ffbbbdd7a93f867dd0d8d5720d9e1f89fab AS base

WORKDIR /app

# 環境変数設定
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# セキュリティ: OSパッケージのセキュリティアップデート
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# セキュリティ: 非rootユーザー作成
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# ============================================================
# Stage 2: Dependencies - 依存関係インストール
# ============================================================
FROM base AS dependencies

# uv インストール
RUN pip install --no-cache-dir uv

# 依存関係ファイルのみコピー（キャッシュ効率化）
COPY pyproject.toml uv.lock ./

# 依存関係インストール（本番用、devパッケージ除外）
# --no-install-project: ローカルパッケージビルドをスキップ（ソース未コピー状態で hatchling エラー回避）
RUN uv sync --frozen --no-dev --no-install-project

# ============================================================
# Stage 3: Runtime - 本番実行環境
# ============================================================
FROM base AS runtime

# 仮想環境をコピー
COPY --from=dependencies /app/.venv /app/.venv

# PATH設定
ENV PATH="/app/.venv/bin:$PATH"

# アプリケーションコードのみコピー（テスト除外）
COPY config/ ./config/
COPY utils/ ./utils/
COPY models/ ./models/

# 不要ファイル削除（イメージサイズ最適化）
RUN find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find . -type f -name "*.pyc" -delete 2>/dev/null || true

# 非rootユーザーに切り替え
USER appuser

# ヘルスチェック（設定読み込み検証で実際のアプリ依存関係を確認）
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from config.settings import settings; assert settings.environment" || exit 1

# ============================================================
# Stage 4: Test - テスト実行環境
# ============================================================
FROM base AS test

# uv インストール
RUN pip install --no-cache-dir uv

# 依存関係ファイルコピー
COPY pyproject.toml uv.lock ./

# 全依存関係インストール（devパッケージ含む）
# --no-install-project: ソース未コピー状態でhatchlingエラー回避（dependencies stageと同様）
RUN uv sync --frozen --no-install-project

# PATH設定
ENV PATH="/app/.venv/bin:$PATH"

# アプリケーションコード全体をコピー
COPY config/ ./config/
COPY utils/ ./utils/
COPY models/ ./models/
COPY tests/ ./tests/
COPY pytest.ini ./

# 不要ファイル削除
RUN find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find . -type f -name "*.pyc" -delete 2>/dev/null || true

# 非rootユーザーに切り替え（最小権限原則）
USER appuser

# デフォルトコマンド: テスト実行
CMD ["pytest", "--cov=.", "--cov-report=term-missing", "-v"]
