#!/bin/bash
# Obsidian Vault Backup Script
# 3-2-1 バックアップ戦略: ローカル + Git + アーカイブ
# P1改善: 絶対パス、シークレット検出拡張、権限設定、チェックサム検証、Vault存在チェック

set -euo pipefail

_err_trap() {
  printf '❌ エラー発生 (line %s): %s\n' "$1" "$2" >&2
}

trap '_err_trap "$LINENO" "$BASH_COMMAND"' ERR

# P0-3: シグナル処理 - 中断時の不完全バックアップ削除
# CURRENT_BACKUP="" はシグナルハンドラの [ -n "$CURRENT_BACKUP" ] ガードが
# バックアップパス未設定時に空判定となるよう意図的に空文字初期化する。
# mv 完了前にシグナルを受信した場合、存在しないファイルへの rm -f は || true で安全に扱われる。
BACKUP_IN_PROGRESS=false
CURRENT_BACKUP=""

cleanup_on_signal() {
  local sig="${1:-TERM}"
  printf '⚠️ 中断シグナル受信（SIG%s）\n' "$sig" >&2 || true
  if [ "$BACKUP_IN_PROGRESS" = true ]; then
    echo "🔄 不完全なバックアップを削除中..." >&2 || true
    # P1-2: .tmpファイルを削除（アトミック書込み対応）
    rm -f "$BACKUP_DIR"/.vault_*.tmp 2>/dev/null || true
    if [ -n "$CURRENT_BACKUP" ]; then
      rm -f "$CURRENT_BACKUP" 2>/dev/null || true
      # チェックサムファイルも削除（シグナル中断時の孤立防止）
      rm -f "${CURRENT_BACKUP%.tar.gz}.sha256" 2>/dev/null || true
    fi
  fi
  # 128+signum: SIGINT=2→130, SIGTERM=15→143（POSIX規約）
  case "$sig" in
    INT)  exit 130 ;;
    TERM) exit 143 ;;
    *)    exit 128 ;;
  esac
}
trap 'cleanup_on_signal INT' INT
trap 'cleanup_on_signal TERM' TERM

# P1-1: タイムアウト関数（NFS/SMBハング対策）
# macOSのgtimeout（coreutils）またはGNU timeout を使用
run_with_timeout() {
  local timeout_sec=$1
  shift
  if command -v gtimeout >/dev/null 2>&1; then
    gtimeout "$timeout_sec" "$@"
  elif command -v timeout >/dev/null 2>&1; then
    timeout "$timeout_sec" "$@"
  else
    echo "Error: gtimeout (brew install coreutils) または timeout コマンドが必要です" >&2
    notify_failure "timeout コマンド未インストール"
    exit 1
  fi
}

# タイムアウト設定（秒）
TAR_TIMEOUT=300
SHASUM_TIMEOUT=60

# P1-5: 依存関係チェック（早期失敗）
check_dependencies() {
  local deps=("tar" "shasum" "find" "df" "du" "python3")
  local missing=()

  for cmd in "${deps[@]}"; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      missing+=("$cmd")
    fi
  done

  if [ ${#missing[@]} -gt 0 ]; then
    echo "❌ エラー: 必要なコマンドが見つかりません: ${missing[*]}" >&2
    echo "   インストール: brew install coreutils (macOS)" >&2
    exit 127  # Command not found
  fi

  if ! command -v gtimeout >/dev/null 2>&1 && ! command -v timeout >/dev/null 2>&1; then
    echo "❌ エラー: gtimeout または timeout が必要です" >&2
    echo "   インストール: brew install coreutils (macOS)" >&2
    exit 127
  fi
}
check_dependencies

# P3-1: macOS通知関数（失敗時にNotification Centerへ表示）
# セキュリティ: on run argv パターンでメッセージをデータとして渡し AppleScript Injection を防止
notify_failure() {
  local message="${1:-バックアップ失敗}"
  if command -v osascript >/dev/null 2>&1; then
    osascript \
      -e "on run argv" \
      -e "display notification (item 1 of argv) with title \"Obsidian Vault Backup\" subtitle \"エラー発生\" sound name \"Basso\"" \
      -e "end run" \
      -- "$message" 2>/dev/null || true
  fi
}

# P1-4: 構造化ログ関数（JSON形式でファイル出力 + 監視システム統合対応）
LOG_FILE=""  # 後でLOG_DIR確定後に設定

# JSON文字列の値として安全にエスケープ（CWE-116 対策）
# python3 json.dumps で RFC 8259 §7 完全対応（C0制御文字含む）。
# python3 は必須依存だが、呼び出し失敗時はJSON破損を避けるため明示エラーにする。
_json_escape() {
  local result
  if ! result=$(python3 -c 'import json, sys; print(json.dumps(sys.argv[1], ensure_ascii=False)[1:-1], end="")' "${1-}" 2>/dev/null); then
    # python3 は必須依存（起動時チェック済み）— 生文字列返却によるJSON破損を防ぐ
    printf '_json_escape: python3 unavailable\n' >&2
    return 1
  fi
  printf '%s' "$result"
}

log_event() {
  local level="$1"
  local message="$2"
  local details="${3:-}"
  local timestamp
  timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  # timestamp/level は内部生成の固定形式（制御文字なし）のためエスケープ不要
  # message/details のみエスケープ（python3起動回数を 4→2 回に削減）
  local escaped_msg
  escaped_msg=$(_json_escape "$message") || escaped_msg="[ESCAPE_ERROR]"

  # JSON 形式でログ出力（エスケープ済み値を安全に埋め込み）
  local json_log
  if [ -n "$details" ]; then
    local escaped_details
    escaped_details=$(_json_escape "$details") || escaped_details="[ESCAPE_ERROR]"
    json_log="{\"timestamp\":\"${timestamp}\",\"level\":\"${level}\",\"message\":\"${escaped_msg}\",\"details\":\"${escaped_details}\"}"
  else
    json_log="{\"timestamp\":\"${timestamp}\",\"level\":\"${level}\",\"message\":\"${escaped_msg}\"}"
  fi

  # ファイル出力（LOG_FILE設定後のみ）
  if [ -n "$LOG_FILE" ] && [ -d "$(dirname "$LOG_FILE")" ]; then
    echo "$json_log" >> "$LOG_FILE"
  fi

}

# P1-1: 絶対パス変換（cron対応）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VAULT_PATH="$PROJECT_ROOT/obsidian-vault-local"
BACKUP_DIR="$HOME/Backups/obsidian-vault"
LOG_DIR="$PROJECT_ROOT/logs"
# P1-6: タイムスタンプ衝突防止（PID付加）
TIMESTAMP=$(date +%Y%m%d_%H%M%S)_$$

# P2: 設定値の変数化（環境変数で上書き可能）
RETENTION_DAYS=${RETENTION_DAYS:-30}

# P1-1: RETENTION_DAYSバリデーション（負値・非数値で全削除防止）
if ! [[ "$RETENTION_DAYS" =~ ^[0-9]+$ ]] || [ "$RETENTION_DAYS" -le 0 ]; then
  echo "❌ エラー: RETENTION_DAYSは正の整数である必要があります（現在値: $RETENTION_DAYS）" >&2
  exit 1
fi

# ログディレクトリ作成
mkdir -p "$LOG_DIR"
# P1-4: 構造化ログファイル設定
LOG_FILE="$LOG_DIR/backup_structured.log"

# P0-2: 並行実行保護（PIDファイル + stale lock検出）- cronで複数プロセス防止
LOCK_FILE="$LOG_DIR/backup.lock"
STALE_THRESHOLD=3600  # 1時間以上経過したロックはstaleとみなす

acquire_lock() {
  if [ -f "$LOCK_FILE" ]; then
    local lock_pid
    lock_pid=$(cat "$LOCK_FILE" 2>/dev/null)

    # プロセス存在チェック
    if [ -n "$lock_pid" ] && kill -0 "$lock_pid" 2>/dev/null; then
      # プロセスが存在→ロック有効
      return 1
    fi

    # stale lock検出（プロセス不在 or ファイルが古い）
    # P0-1: Linux/BSD両対応のstat（GNU: -c %Y, BSD: -f %m）
    local lock_age lock_mtime
    if stat --version >/dev/null 2>&1; then
      # GNU stat (Linux)
      lock_mtime=$(stat -c %Y "$LOCK_FILE" 2>/dev/null || echo 0)
    else
      # BSD stat (macOS)
      lock_mtime=$(stat -f %m "$LOCK_FILE" 2>/dev/null || echo 0)
    fi
    lock_age=$(($(date +%s) - lock_mtime))
    if [ "$lock_age" -gt "$STALE_THRESHOLD" ]; then
      echo "⚠️ 古いロックファイルを削除（${lock_age}秒経過）" >&2
      rm -f "$LOCK_FILE"
    fi
  fi

  # P1-1: アトミックロック取得（noclobberモードでTOCTOU防止）
  # set -C: ファイル存在時に>リダイレクトが失敗（アトミック）
  if (set -C; echo $$ > "$LOCK_FILE") 2>/dev/null; then
    return 0
  else
    # ロック取得失敗（別プロセスが先に取得）
    return 1
  fi
}

cleanup_lock() {
  rm -f "$LOCK_FILE"
  if [ -n "${TAR_ERR:-}" ]; then
    rm -f "$TAR_ERR"
  fi
}
trap cleanup_lock EXIT


# リストア検証関数（--verify オプション用）

verify_restore() {
  echo "🔄 リストア検証開始..."

  # mtime降順で最新ファイル取得（ls -t はスペース/特殊文字ファイル名で誤動作の恐れあり）
  # P0-1: Linux/BSD両対応のstat（既存パターン準拠）
  if stat --version >/dev/null 2>&1; then
    # GNU stat (Linux): -c "%Y %n" (既存 lock_mtime パターン準拠)
    LATEST=$(find "$BACKUP_DIR" -maxdepth 1 -name "vault_*.tar.gz" \
      -exec stat -c "%Y %n" {} \; 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)
  else
    # BSD stat (macOS)
    LATEST=$(find "$BACKUP_DIR" -maxdepth 1 -name "vault_*.tar.gz" \
      -exec stat -f "%m %N" {} \; 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)
  fi

  if [ -z "$LATEST" ]; then
    echo "❌ バックアップファイルが見つかりません" >&2
    return 1
  fi

  # ファイル存在確認（レースコンディション対策）
  if [ ! -f "$LATEST" ]; then
    echo "❌ バックアップファイルが削除されました: $LATEST" >&2
    return 1
  fi

  # P1-4: チェックサム検証
  CHECKSUM_FILE="${LATEST%.tar.gz}.sha256"
  if [ -f "$CHECKSUM_FILE" ]; then
    echo "🔐 チェックサム検証中..."
    # stderrのみ抑制、stdoutは失敗時の詳細(FAILED)のために変数に捕捉
    if ! shasum_out=$(cd "$BACKUP_DIR" && shasum -a 256 -c "$(basename "$CHECKSUM_FILE")" 2>&1); then
      echo "❌ チェックサム検証失敗: ファイル破損の可能性（詳細: ${shasum_out}）" >&2
      return 1
    fi
    echo "✅ チェックサム検証OK"
  else
    echo "⚠️ チェックサムファイルが見つかりません（スキップ）" >&2
  fi

  # 一時ディレクトリ作成（trap付き）
  local previous_int_trap previous_term_trap previous_err_trap previous_return_trap
  previous_int_trap=$(trap -p INT || true)
  previous_term_trap=$(trap -p TERM || true)
  previous_err_trap=$(trap -p ERR || true)
  previous_return_trap=$(trap -p RETURN || true)

  # shellcheck disable=SC2329  # invoked by _verify_cleanup, which is invoked via trap
  _restore_verify_traps() {
    if [ -n "$previous_int_trap" ]; then eval "$previous_int_trap"; else trap - INT; fi
    if [ -n "$previous_term_trap" ]; then eval "$previous_term_trap"; else trap - TERM; fi
    if [ -n "$previous_err_trap" ]; then eval "$previous_err_trap"; else trap - ERR; fi
    if [ -n "$previous_return_trap" ]; then eval "$previous_return_trap"; else trap - RETURN; fi
  }

  # shellcheck disable=SC2329  # trap-invoked cleanup handler
  _verify_cleanup() {
    local rc=$?
    rm -rf "$TEMP" 2>/dev/null || true
    _restore_verify_traps
    return "$rc"
  }

  TEMP=$(mktemp -d -t vault_verify.XXXXXXXXXX)
  trap '_verify_cleanup; exit 130' INT
  trap '_verify_cleanup; exit 143' TERM
  trap '_verify_cleanup' ERR
  trap _verify_cleanup RETURN
  chmod 700 "$TEMP"  # 明示的権限設定

  # P1-4: symlink攻撃検出（CVE-2008-2957対策）
  if [ -L "$TEMP" ]; then
    echo "❌ セキュリティ警告: 一時ディレクトリがシンボリックリンク" >&2
    rm -rf "$TEMP"
    return 1
  fi

  # 展開（エラーチェック付き）
  # P0-1: BSD tar（macOS）はデフォルトで絶対パスを除去するためpath traversal攻撃を防止
  # GNU tarの--no-absolute-namesと同等の動作（-Pオプションを使わない限り安全）
  if ! tar -xzf "$LATEST" -C "$TEMP" 2>/dev/null; then
    echo "❌ アーカイブ展開失敗: $LATEST" >&2
    return 1
  fi

  # ファイル数比較
  ORIG=$(find "$VAULT_PATH" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
  REST=$(find "$TEMP" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')

  # 空Vault検出（偽陽性防止）
  if [ "$ORIG" -eq 0 ]; then
    echo "⚠️ 警告: Vaultが空です（0ファイル）。データ損失の可能性があります" >&2
    return 1
  fi

  if [ "$ORIG" -eq "$REST" ]; then
    echo "✅ リストア検証OK: $ORIG ファイル一致"
    return 0
  else
    echo "❌ リストア検証失敗: 元=$ORIG, 復元=$REST" >&2
    return 1
  fi
}

# --verify オプションでリストア検証を実行（バックアップ処理をスキップ）
# P1-5: 終了コードを検証結果に基づいて設定（CI/CD統合対応）
if [ "${1:-}" = "--verify" ]; then
  verify_restore
  exit $?
fi

if ! acquire_lock; then
  echo "⚠️ 別のバックアッププロセスが実行中です（スキップ）" >&2
  log_event "INFO" "backup_skipped" "concurrent_execution_detected"
  exit 0  # 正常終了（cronログにエラー記録しない）
fi

# P1-4: バックアップ開始ログ
log_event "INFO" "backup_started" "vault=$VAULT_PATH"

# P1-5: Vault存在チェック
if [ ! -d "$VAULT_PATH" ]; then
  echo "❌ エラー: Vaultディレクトリが見つかりません: $VAULT_PATH" >&2
  log_event "ERROR" "vault_not_found" "path=$VAULT_PATH"
  notify_failure "Vaultディレクトリ未検出"
  exit 1
fi

# P1-3: シークレット検出パターン拡張（大文字小文字無視）
# Security Agent推奨: クラウドプロバイダー、DB、セッション、決済系キーを追加
SECRET_PATTERNS="(api_key|secret|password|token|credential|private[_-]?key|jwt[_-]?secret|auth[_-]?token"
SECRET_PATTERNS="${SECRET_PATTERNS}|AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|GITHUB_TOKEN"
SECRET_PATTERNS="${SECRET_PATTERNS}|OPENAI_API_KEY|ANTHROPIC_API_KEY|GCP_SERVICE_ACCOUNT"
# P1-3追加: DB/セッション/決済/Webhook
SECRET_PATTERNS="${SECRET_PATTERNS}|DATABASE_URL|MYSQL_PASSWORD|POSTGRES_PASSWORD"
SECRET_PATTERNS="${SECRET_PATTERNS}|REFRESH_TOKEN|SESSION_SECRET|COOKIE_SECRET"
SECRET_PATTERNS="${SECRET_PATTERNS}|STRIPE_[A-Z_]+_KEY|SLACK_WEBHOOK"
# P1-3追加: PEM秘密鍵ヘッダー
SECRET_PATTERNS="${SECRET_PATTERNS}|-----BEGIN[[:space:]]+(RSA|EC|OPENSSH)[[:space:]]+PRIVATE[[:space:]]+KEY-----)"

echo "🔍 機密情報チェック中..."
if grep -rE -i "$SECRET_PATTERNS" \
  "$VAULT_PATH/" --exclude-dir=.git --exclude="*.md" -q 2>/dev/null; then
  echo "❌ 機密情報検出！バックアップ中止" >&2
  echo "   ※ .mdファイルは除外されます（ドキュメント内のキーワードは許可）"
  log_event "ERROR" "secrets_detected" "vault=$VAULT_PATH"
  notify_failure "機密情報検出"
  exit 1
fi

# バックアップディレクトリ作成・権限確認
mkdir -p "$BACKUP_DIR"
# P1: ディレクトリ権限を所有者のみに制限（Security Agent推奨）
chmod 700 "$BACKUP_DIR"
if [ ! -w "$BACKUP_DIR" ]; then
  echo "❌ バックアップディレクトリに書き込み権限がありません: $BACKUP_DIR" >&2
  notify_failure "書込み権限なし"
  exit 1
fi

VAULT_SIZE_KB=$(du -sk "$VAULT_PATH" 2>/dev/null | awk '{print $1}' || echo "0")
DF_OUT=$(df -k "$BACKUP_DIR" 2>/dev/null | tail -1 | awk '{gsub(/%/,"",$5); print $4, $5}')
read -r AVAILABLE_KB DISK_USAGE <<< "$DF_OUT"
AVAILABLE_KB=${AVAILABLE_KB:-0}
DISK_USAGE=${DISK_USAGE:-0}
REQUIRED_KB=$((VAULT_SIZE_KB * 2))  # 圧縮 + 安全マージン

if [ "$VAULT_SIZE_KB" -gt 0 ] && [ "$AVAILABLE_KB" -gt 0 ]; then
  if [ "$AVAILABLE_KB" -lt "$REQUIRED_KB" ]; then
    echo "❌ エラー: ディスク容量不足（必要: $((REQUIRED_KB / 1024))MB, 利用可能: $((AVAILABLE_KB / 1024))MB）" >&2
    notify_failure "ディスク容量不足"
    exit 1
  fi
fi

# P1-8: ディスクフル事前検出（使用率95%以上で警告）
if [ "$DISK_USAGE" -ge 95 ]; then
  echo "⚠️ 警告: ディスク使用率が高い（${DISK_USAGE}%）" >&2
fi

# P1-2: アトミック書込み（.tmp + rename）
# 他プロセスは完成したファイルのみ参照可能
CURRENT_BACKUP="$BACKUP_DIR/vault_${TIMESTAMP}.tar.gz"
TEMP_BACKUP="$BACKUP_DIR/.vault_${TIMESTAMP}.tar.gz.tmp"

# P0-3: シグナル処理用の状態設定（クリティカルセクション開始）
BACKUP_IN_PROGRESS=true

# バックアップ作成（P1-1: タイムアウト付き、P1-2: tmpファイルに書込み）
# P1-3: tar stderrを捕捉してI/Oエラー検出（NFS途中切断等）
TAR_ERR=$(mktemp)
if ! run_with_timeout "$TAR_TIMEOUT" tar -czf "$TEMP_BACKUP" -C "$PROJECT_ROOT" "obsidian-vault-local/" 2>"$TAR_ERR"; then
  echo "❌ アーカイブ作成失敗（タイムアウト/ディスクフル等の可能性）" >&2
  [ -s "$TAR_ERR" ] && echo "   詳細: $(cat "$TAR_ERR")" >&2
  log_event "ERROR" "archive_failed" "stderr=$(cat "$TAR_ERR" 2>/dev/null | head -c 200)"
  rm -f "$TEMP_BACKUP" "$TAR_ERR"
  TAR_ERR=""  # 明示リセット: cleanup_lock() の ${TAR_ERR:-} ガードを確実に
  notify_failure "アーカイブ作成失敗"
  exit 1
fi
# tar成功してもstderrに警告があれば表示（Permission denied等）
if [ -s "$TAR_ERR" ]; then
  echo "⚠️ tar警告: $(cat "$TAR_ERR")" >&2
fi
rm -f "$TAR_ERR"
TAR_ERR=""  # 明示リセット: cleanup_lock() の ${TAR_ERR:-} ガードを確実に

# P1-3: バックアップ権限設定（所有者のみ読み書き可能）
chmod 600 "$TEMP_BACKUP"

# P1-2: アトミックリネーム（mv は同一ファイルシステム内でアトミック）
mv "$TEMP_BACKUP" "$CURRENT_BACKUP"

# P1-2: チェックサムもアトミック書込み（tmpファイル + rename）
# レース条件防止: 消費者がチェックサム未作成のバックアップを読むことを防止
CHECKSUM_FILE="${CURRENT_BACKUP%.tar.gz}.sha256"
TEMP_CHECKSUM="${CHECKSUM_FILE}.tmp"
if ! run_with_timeout "$SHASUM_TIMEOUT" shasum -a 256 "$CURRENT_BACKUP" > "$TEMP_CHECKSUM"; then
  echo "❌ チェックサム計算失敗（タイムアウト/I/Oエラー）" >&2
  rm -f "$CURRENT_BACKUP" "$TEMP_CHECKSUM"
  notify_failure "チェックサム計算失敗"
  exit 1
fi
chmod 600 "$TEMP_CHECKSUM"
mv "$TEMP_CHECKSUM" "$CHECKSUM_FILE"

# P0-3: クリティカルセクション終了
BACKUP_IN_PROGRESS=false

# 古いバックアップ削除（RETENTION_DAYS日以上）
# P1-3: -maxdepth 1 -type fでサブディレクトリ誤削除防止
# 2>/dev/null: 権限なしファイルの "Permission denied" を抑止; 削除失敗は || true で継続
find "$BACKUP_DIR" -maxdepth 1 -type f \
  \( -name "vault_*.tar.gz" -o -name "vault_*.sha256" \) \
  -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true

# P1-4: バックアップ成功ログ（サイズ付き）
BACKUP_SIZE=$(du -sh "$CURRENT_BACKUP" 2>/dev/null | cut -f1 || echo "unknown")
echo "✅ バックアップ完了: $CURRENT_BACKUP"
log_event "INFO" "backup_completed" "file=$CURRENT_BACKUP,size=$BACKUP_SIZE"
