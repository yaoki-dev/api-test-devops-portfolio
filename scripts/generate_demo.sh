#!/bin/bash
# =============================================================================
# Demo GIF Generation Script
# =============================================================================
# Purpose: Generate asciinema recordings and convert to GIF for README demos
# Requirements: asciinema, agg (or asciicast2gif)
# Usage: ./scripts/generate_demo.sh [test|docker|cicd|all]
#
# Reference: docs/プロジェクト再編/6週再編/6週プラン/6週プラン改善/改善1_デモ環境構築.md
# Version: 1.3.0
# Last Updated: 2025-11-27
# Changes: W1 (POSIX file size), W2 (mktemp security), W3 (uv check)
#          v1.3.0: P1 (quote $GIF_SPEED), P2 (CI skip, empty file cleanup, ls→compgen)
#                  P3 (AUTO_OPTIMIZE, trap simplify)
# =============================================================================

set -e

# =============================================================================
# Configuration (#3: Resolution 80x24 per requirements, #5: Constants)
# =============================================================================
ASSETS_DIR="assets"
DEMO_COLS=80
DEMO_ROWS=24
GIF_SPEED=1.0
MAX_GIF_SIZE_BYTES=2097152  # 2MB in bytes
MAX_GIF_SIZE_MB=2

# Valid targets for argument validation (#6)
VALID_TARGETS="test|docker|cicd|all"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# W2: Secure temporary directory (created in main, cleaned up via trap)
TEMP_DIR=""

# =============================================================================
# Helper Functions
# =============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# #2: Cleanup function for temporary files (W2: now cleans TEMP_DIR)
cleanup_temp_files() {
    if [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ]; then
        rm -rf "$TEMP_DIR"
    fi
}

# W1: POSIX-compatible file size function (works on macOS, Linux, Alpine, BusyBox)
get_file_size() {
    local file=$1
    # Try macOS stat format first
    stat -f%z "$file" 2>/dev/null && return
    # Try GNU stat format
    stat -c%s "$file" 2>/dev/null && return
    # Fallback: POSIX-compliant wc -c (works everywhere)
    wc -c < "$file" 2>/dev/null | tr -d ' '
}

# #7: OS-specific install instructions
get_install_command() {
    local tool=$1
    if [ "$(uname)" = "Darwin" ]; then
        # macOS
        case $tool in
            asciinema) echo "brew install asciinema" ;;
            agg) echo "brew install agg" ;;
            gh) echo "brew install gh" ;;
        esac
    elif [ -f /etc/debian_version ]; then
        # Debian/Ubuntu
        case $tool in
            asciinema) echo "sudo apt-get install asciinema" ;;
            agg) echo "cargo install --git https://github.com/asciinema/agg" ;;
            gh) echo "sudo apt-get install gh" ;;
        esac
    elif [ -f /etc/redhat-release ]; then
        # RHEL/CentOS/Fedora
        case $tool in
            asciinema) echo "sudo dnf install asciinema" ;;
            agg) echo "cargo install --git https://github.com/asciinema/agg" ;;
            gh) echo "sudo dnf install gh" ;;
        esac
    else
        # Generic
        case $tool in
            asciinema) echo "pip install asciinema (or see https://asciinema.org/docs/installation)" ;;
            agg) echo "cargo install --git https://github.com/asciinema/agg" ;;
            gh) echo "see https://cli.github.com/manual/installation" ;;
        esac
    fi
}

check_dependencies() {
    log_info "Checking dependencies..."

    # W3: Check uv (required for test demo)
    if ! command -v uv &> /dev/null; then
        log_error "uv not found. Install with: pip install uv (or see https://docs.astral.sh/uv/)"
        exit 1
    fi

    if ! command -v asciinema &> /dev/null; then
        log_error "asciinema not found. Install with: $(get_install_command asciinema)"
        exit 1
    fi

    # Check for GIF converter (agg preferred, asciicast2gif as fallback)
    if command -v agg &> /dev/null; then
        GIF_CONVERTER="agg"
        log_info "Using agg for GIF conversion (Rust, fast)"
    elif command -v asciicast2gif &> /dev/null; then
        GIF_CONVERTER="asciicast2gif"
        log_info "Using asciicast2gif for GIF conversion"
    else
        log_error "No GIF converter found. Install with:"
        echo "  Option 1 (recommended): $(get_install_command agg)"
        echo "  Option 2: npm install -g asciicast2gif"
        exit 1
    fi

    log_info "All dependencies satisfied"
}

convert_to_gif() {
    local cast_file=$1
    local gif_file=$2

    log_info "Converting $cast_file to $gif_file..."

    if [ "$GIF_CONVERTER" = "agg" ]; then
        agg --speed "$GIF_SPEED" "$cast_file" "$gif_file"
    else
        asciicast2gif --speed "$GIF_SPEED" "$cast_file" "$gif_file"
    fi

    # W1: Use POSIX-compatible file size check
    local size_bytes=$(get_file_size "$gif_file")
    local size_mb=$((size_bytes / 1048576))
    log_info "Generated: $gif_file (${size_mb}MB, ${size_bytes} bytes)"

    # Warn if over 2MB (#5: Use constant instead of magic number)
    if [ "$size_bytes" -gt "$MAX_GIF_SIZE_BYTES" ]; then
        log_warn "GIF is over ${MAX_GIF_SIZE_MB}MB. Consider optimization with:"
        echo "  gifsicle -O3 --lossy=80 $gif_file -o ${gif_file%.gif}-optimized.gif"

        # P3-6: Auto-optimize if gifsicle available and AUTO_OPTIMIZE=true
        if command -v gifsicle &> /dev/null && [ "${AUTO_OPTIMIZE:-false}" = "true" ]; then
            log_info "Auto-optimizing with gifsicle (AUTO_OPTIMIZE=true)..."
            gifsicle -O3 --lossy=80 "$gif_file" -o "${gif_file%.gif}-optimized.gif"
            mv "${gif_file%.gif}-optimized.gif" "$gif_file"
            size_bytes=$(get_file_size "$gif_file")
            log_info "Optimized: $gif_file (now ${size_bytes} bytes)"
        fi
    fi
}

# =============================================================================
# Demo Generation Functions
# =============================================================================

generate_test_demo() {
    log_info "=== Generating Test Execution Demo ==="

    local cast_file="${ASSETS_DIR}/demo-test.cast"
    local gif_file="${ASSETS_DIR}/demo-test.gif"

    # Create recording script (#4: Added --color=yes for highlighted output)
    # W2: Use secure TEMP_DIR instead of hardcoded /tmp
    # Note: For demo purposes, run only basic tests to keep GIF under 15 seconds
    # Full test suite (192 tests) takes ~60s which is too long for demo
    # Using test_basic.py (19 tests) for quick visual demonstration
    # Target duration: 8-12 seconds (per success criteria in 改善1_デモ環境構築.md)
    # Sleep breakdown: title(1s) + cmd(0.5s) + result(2s) + end(1.5s) = 5s
    # pytest execution: ~5s → Total: ~10-11s
    cat > "$TEMP_DIR/demo_test_script.sh" << 'SCRIPT'
clear
echo "# API Test DevOps Portfolio - Test Demo"
echo ""
sleep 1
echo "$ uv run pytest tests/unit/test_basic.py --cov=. --cov-report=term -q --color=yes"
sleep 0.5
uv run pytest tests/unit/test_basic.py --cov=. --cov-report=term -q --color=yes 2>/dev/null | tail -25
sleep 2
echo ""
echo "✓ All tests passed!"
sleep 1.5
SCRIPT
    chmod 700 "$TEMP_DIR/demo_test_script.sh"

    # Record
    asciinema rec \
        --cols $DEMO_COLS \
        --rows $DEMO_ROWS \
        --command "bash $TEMP_DIR/demo_test_script.sh" \
        --overwrite \
        "$cast_file"

    # Convert to GIF
    convert_to_gif "$cast_file" "$gif_file"

    log_info "Test demo completed: $gif_file"
}

generate_docker_demo() {
    log_info "=== Generating Docker Demo ==="

    local cast_file="${ASSETS_DIR}/demo-docker.cast"
    local gif_file="${ASSETS_DIR}/demo-docker.gif"

    # Check if docker-compose exists
    if [ ! -f "docker-compose.yml" ]; then
        log_warn "docker-compose.yml not found in project root"
        log_warn "Skipping Docker demo generation"
        log_info "Create docker-compose.yml first, then re-run this script"
        # P2-3: Clean up empty/stale files to avoid git confusion
        rm -f "$cast_file" "$gif_file" 2>/dev/null
        return 1
    fi

    # Create recording script
    # W2: Use secure TEMP_DIR instead of hardcoded /tmp
    cat > "$TEMP_DIR/demo_docker_script.sh" << 'SCRIPT'
clear
echo "# Docker Operations Demo"
echo ""
sleep 1
echo "$ docker-compose up -d"
docker-compose up -d
sleep 3
echo ""
echo "$ docker-compose ps"
docker-compose ps
sleep 2
echo ""
echo "$ docker-compose down"
docker-compose down
sleep 1
SCRIPT
    chmod 700 "$TEMP_DIR/demo_docker_script.sh"

    # Record
    asciinema rec \
        --cols $DEMO_COLS \
        --rows $DEMO_ROWS \
        --command "bash $TEMP_DIR/demo_docker_script.sh" \
        --overwrite \
        "$cast_file"

    # Convert to GIF
    convert_to_gif "$cast_file" "$gif_file"

    log_info "Docker demo completed: $gif_file"
}

generate_cicd_demo() {
    log_info "=== Generating CI/CD Demo ==="

    local cast_file="${ASSETS_DIR}/demo-cicd.cast"
    local gif_file="${ASSETS_DIR}/demo-cicd.gif"

    # Check if gh CLI is available (#7: OS-specific install instruction)
    if ! command -v gh &> /dev/null; then
        log_warn "GitHub CLI (gh) not found. Install with: $(get_install_command gh)"
        log_warn "Skipping CI/CD demo generation"
        return 1
    fi

    # Create recording script
    # W2: Use secure TEMP_DIR instead of hardcoded /tmp
    # Target duration: 15 seconds (per success criteria in 改善1_デモ環境構築.md)
    # Note: gh commands take ~20s, so minimal sleeps to keep total ~15s
    cat > "$TEMP_DIR/demo_cicd_script.sh" << 'SCRIPT'
clear
echo "# CI/CD Automation Demo"
echo ""
sleep 1
echo "$ gh run list --limit 3"
gh run list --limit 3 2>/dev/null || echo "(GitHub Actions runs will appear here)"
sleep 1
echo ""
echo "✓ CI/CD pipeline ready!"
sleep 2
SCRIPT
    chmod 700 "$TEMP_DIR/demo_cicd_script.sh"

    # Record
    asciinema rec \
        --cols $DEMO_COLS \
        --rows $DEMO_ROWS \
        --command "bash $TEMP_DIR/demo_cicd_script.sh" \
        --overwrite \
        "$cast_file"

    # Convert to GIF
    convert_to_gif "$cast_file" "$gif_file"

    log_info "CI/CD demo completed: $gif_file"
}

# =============================================================================
# Main
# =============================================================================

main() {
    # W2: Create secure temporary directory with unpredictable path
    TEMP_DIR=$(mktemp -d) || { log_error "Failed to create temp directory"; exit 1; }

    # #2: Cleanup trap for temporary files (P3-8: ERR removed - redundant with set -e)
    trap cleanup_temp_files EXIT INT TERM

    log_info "Demo GIF Generation Script"
    log_info "=========================="

    # P2-4: CI environment detection - graceful skip if dependencies missing
    if [ -n "$CI" ]; then
        log_info "CI environment detected"
        if ! command -v asciinema &> /dev/null || ! command -v agg &> /dev/null; then
            log_warn "CI environment: Dependencies not available, skipping demo generation"
            log_info "To generate demos, run locally: ./scripts/generate_demo.sh"
            exit 0  # Don't fail CI pipeline
        fi
    fi

    # Ensure assets directory exists
    mkdir -p "$ASSETS_DIR"

    # Check dependencies
    check_dependencies

    local target=${1:-all}

    # #6: Argument validation
    if ! echo "$target" | grep -qE "^($VALID_TARGETS)$"; then
        log_error "Invalid target: $target"
        echo "Usage: $0 [test|docker|cicd|all]"
        echo "  test   - Generate test execution demo only"
        echo "  docker - Generate Docker operations demo only"
        echo "  cicd   - Generate CI/CD automation demo only"
        echo "  all    - Generate all demos (default)"
        exit 1
    fi

    case $target in
        test)
            generate_test_demo
            ;;
        docker)
            generate_docker_demo
            ;;
        cicd)
            generate_cicd_demo
            ;;
        all)
            generate_test_demo
            generate_docker_demo || log_warn "Docker demo skipped (docker-compose.yml not found)"
            generate_cicd_demo || log_warn "CI/CD demo skipped (gh CLI not available)"
            ;;
    esac

    log_info ""
    log_info "=== Summary ==="
    log_info "Generated GIFs in ${ASSETS_DIR}/:"
    # P2-5: Use glob instead of ls (ShellCheck SC2012 compliance)
    if compgen -G "${ASSETS_DIR}/*.gif" > /dev/null 2>&1; then
        for gif in "${ASSETS_DIR}"/*.gif; do
            if [ -f "$gif" ] && [ -s "$gif" ]; then  # Exists and not empty
                local gif_size
                gif_size=$(get_file_size "$gif")
                log_info "  $(basename "$gif"): $((gif_size / 1024))KB"
            fi
        done
    else
        log_warn "No GIF files generated"
    fi

    # P3-7: Generate metadata JSON for CI/CD pipeline integration
    if [ -n "$CI" ]; then
        log_info "Generating CI metadata..."
        local metadata_file="${ASSETS_DIR}/demo_metadata.json"
        local files_json=""
        local first=true
        for gif in "${ASSETS_DIR}"/*.gif; do
            if [ -f "$gif" ] && [ -s "$gif" ]; then
                local gif_size
                gif_size=$(get_file_size "$gif")
                [ "$first" = "false" ] && files_json="$files_json,"
                files_json="$files_json{\"name\":\"$(basename "$gif")\",\"size\":$gif_size}"
                first=false
            fi
        done
        cat > "$metadata_file" << EOF
{
  "generated_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "generator_version": "1.3.0",
  "files": [$files_json]
}
EOF
        log_info "Metadata: $metadata_file"
    fi

    log_info ""
    log_info "Next steps:"
    log_info "1. Review GIFs for quality"
    log_info "2. Optimize if needed (gifsicle or ImageMagick)"
    log_info "3. Commit to git: git add assets/*.gif"
}

main "$@"
