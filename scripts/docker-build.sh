#!/usr/bin/env bash
# ========================================
# Docker BuildKit最適化ビルドスクリプト
# ========================================

set -euo pipefail

# BuildKit有効化
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# カラー出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ========================================
# 初回ビルド（全Stage）
# ========================================
build_initial() {
    log_info "初回ビルド開始（全Stageキャッシュ作成）"

    time docker build \
        --target base \
        --cache-from api-test-devops:base \
        -t api-test-devops:base \
        . && \
    docker build \
        --target dependencies \
        --cache-from api-test-devops:base \
        --cache-from api-test-devops:dependencies \
        -t api-test-devops:dependencies \
        . && \
    docker build \
        --target runtime \
        --cache-from api-test-devops:base \
        --cache-from api-test-devops:dependencies \
        --cache-from api-test-devops:runtime \
        -t api-test-devops:runtime \
        . && \
    docker build \
        --target test \
        --cache-from api-test-devops:base \
        --cache-from api-test-devops:dependencies \
        --cache-from api-test-devops:runtime \
        -t api-test-devops:test \
        .

    log_info "初回ビルド完了（推定時間: 1.5-2分）"
}

# ========================================
# 高速再ビルド（コード変更時）
# ========================================
build_fast() {
    local TARGET="${1:-runtime}"

    log_info "高速再ビルド開始（Target: $TARGET）"

    time docker build \
        --target "$TARGET" \
        --cache-from api-test-devops:base \
        --cache-from api-test-devops:dependencies \
        --cache-from api-test-devops:runtime \
        -t "api-test-devops:$TARGET" \
        .

    log_info "高速再ビルド完了（推定時間: 5-8秒）"
}

# ========================================
# テスト実行（キャッシュ活用）
# ========================================
test_run() {
    log_info "テスト実行開始"

    docker compose run --rm test

    log_info "テスト実行完了"
}

# ========================================
# キャッシュクリーンアップ
# ========================================
cache_clean() {
    log_warn "キャッシュクリーンアップ開始"

    docker builder prune -af --filter "until=24h"

    log_info "キャッシュクリーンアップ完了"
}

# ========================================
# イメージサイズ分析
# ========================================
analyze_size() {
    log_info "イメージサイズ分析"

    echo ""
    echo "Stage別イメージサイズ:"
    docker images api-test-devops --format "table {{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"

    echo ""
    echo "Layer分析（runtime）:"
    docker history api-test-devops:runtime --no-trunc --human
}

# ========================================
# メイン処理
# ========================================
main() {
    case "${1:-help}" in
        init)
            build_initial
            ;;
        fast)
            build_fast "${2:-runtime}"
            ;;
        test)
            test_run
            ;;
        clean)
            cache_clean
            ;;
        analyze)
            analyze_size
            ;;
        *)
            echo "使用方法:"
            echo "  $0 init           # 初回ビルド（全Stageキャッシュ作成）"
            echo "  $0 fast [target]  # 高速再ビルド（デフォルト: runtime）"
            echo "  $0 test           # テスト実行"
            echo "  $0 clean          # キャッシュクリーンアップ"
            echo "  $0 analyze        # イメージサイズ分析"
            exit 1
            ;;
    esac
}

main "$@"
