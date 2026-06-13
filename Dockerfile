# Dockerfile - 4-stage Multi-stage builds
# 最終更新: 2026年03月08日
# 品質基準: イメージサイズ < 200MB, ビルド時間 < 3分

# ============================================================
# Stage 1: Base - 共通ベースイメージ
# ============================================================
# セキュリティ: SHA256ダイジェスト固定（サプライチェーン攻撃防止）
# 更新フロー: Dependabotが週次（月曜 09:00 JST）で自動検出・PR作成
# 手動更新: docker pull python:3.14-slim && docker inspect --format='{{index .RepoDigests 0}}' python:3.14-slim
# 変更履歴:
#   2026-02-17: Python 3.12→3.13 (セキュリティサポート延長)
#   2026-03-07: Python 3.13→3.14 (プロジェクト全体統一移行 PR#228)
#   2026-06-13: digest更新 (CVE-2026-45447 openssl-provider-legacy HIGH / 修正版 3.5.6-1~deb13u2 取込)
FROM python:3.14-slim@sha256:d7a925f9eb9639a93e455b9f12c167569358818c0f62b51b88edbc8fcf34c421 AS base

WORKDIR /app

# 環境変数設定
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# セキュリティ: OSパッケージのセキュリティアップデート + pip更新
# pip 25.3 → 26.x (>=26,<27): CVE-2026-1703 (path traversal) 修正
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir "pip>=26,<27"

# セキュリティ: 非rootユーザー作成
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# ============================================================
# Stage 2: Dependencies - 依存関係インストール
# ============================================================
FROM base AS dependencies

# uv インストール
RUN pip install --no-cache-dir "uv==0.11.17"

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

# 非rootユーザーに切り替え
USER appuser

# ヘルスチェック（設定読み込み検証で実際のアプリ依存関係を確認）
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from config.settings import settings; assert settings.environment" || exit 1

# ============================================================
# Stage 4: Test - テスト実行環境
# ============================================================
FROM base AS test

# uv インストール (root権限が必要: グローバル site-packages 配置)
# Note: test ステージは FROM base AS test で base から直接分岐するため、
# FROM base AS dependencies で生成された uv レイヤーを継承しない。
# 独立インストールは設計上必要（runtime ステージに uv が漏れないよう
# dependencies と test を別ブランチで構成する意図的設計）。
RUN pip install --no-cache-dir "uv==0.11.17"

# pytest-cov が cwd (/app) に .coverage SQLite DB を書くため、appuser に WORKDIR
# 書込権限を付与する。非再帰 chown のみで十分 (.venv とアプリコードは以降の
# `--chown=appuser:appgroup` 付き COPY と appuser 権限での `uv sync` で適切な所有に配置)。
RUN chown appuser:appgroup /app

# 非rootユーザーに切替 (uv sync 以降は appuser 権限で実行 → .venv も appuser 所有で生成)
USER appuser

# 依存関係ファイルコピー (appuser 所有で配置)
# pytest設定は pyproject.toml の [tool.pytest.ini_options] に統合済 (pytest.ini は不要)
COPY --chown=appuser:appgroup pyproject.toml uv.lock ./

# dependencies stage の本番依存 .venv をベースにキャッシュ流用 (コードのみ変更時のCI高速化)
# 後続 `uv sync` が dev 依存関係を差分追加するため、`pyproject.toml`/`uv.lock` 未変更時の
# フル再インストールを回避できる
COPY --chown=appuser:appgroup --from=dependencies /app/.venv /app/.venv

# PATH設定（uv sync 前に設定。uv は絶対パスで実行されるため動作上必須ではないが、
# 後続の COPY/RUN で .venv/bin が PATH に含まれていることを明示）
ENV PATH="/app/.venv/bin:$PATH"

# 全依存関係インストール（devパッケージ含む）
# --no-install-project: ソース未コピー状態でhatchlingエラー回避（dependencies stageと同様）
RUN uv sync --frozen --no-install-project

# アプリケーションコード全体をコピー (appuser 所有で配置)
COPY --chown=appuser:appgroup config/ ./config/
COPY --chown=appuser:appgroup utils/ ./utils/
COPY --chown=appuser:appgroup models/ ./models/
COPY --chown=appuser:appgroup tests/ ./tests/
# docker-compose.yml は tests/integration/test_docker_compose_contract.py が
# request.config.rootdir / "docker-compose.yml" で読み込むため、test ステージへ配置する。
COPY --chown=appuser:appgroup docker-compose.yml ./

# デフォルトコマンド: テスト実行
# カバレッジ scope は CI 品質ゲート (--cov=utils --cov=config --cov=models) と統一
CMD ["pytest", "--cov=utils", "--cov=config", "--cov=models", "--cov-report=term-missing", "-v"]
