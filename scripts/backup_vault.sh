#!/bin/bash
# Obsidian Vault Backup Script
# 3-2-1 バックアップ戦略: ローカル + Git + アーカイブ
# P1改善: 絶対パス、シークレット検出拡張、権限設定、チェックサム検証、Vault存在チェック

set -e

# P1-1: 絶対パス変換（cron対応）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VAULT_PATH="$PROJECT_ROOT/obsidian-vault-local"
BACKUP_DIR="$HOME/Backups/obsidian-vault"
LOG_DIR="$PROJECT_ROOT/logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# P2: 設定値の変数化（環境変数で上書き可能）
RETENTION_DAYS=${RETENTION_DAYS:-30}

# ログディレクトリ作成
mkdir -p "$LOG_DIR"

# P1-5: Vault存在チェック
if [ ! -d "$VAULT_PATH" ]; then
  echo "❌ エラー: Vaultディレクトリが見つかりません: $VAULT_PATH"
  exit 1
fi

# P1-2: シークレット検出パターン拡張（大文字小文字無視）
# Security Agent推奨: AWS/GitHub/OpenAI等のクラウドプロバイダーキーを追加
SECRET_PATTERNS="(api_key|secret|password|token|credential|private[_-]?key|jwt[_-]?secret|auth[_-]?token"
SECRET_PATTERNS="${SECRET_PATTERNS}|AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|GITHUB_TOKEN"
SECRET_PATTERNS="${SECRET_PATTERNS}|OPENAI_API_KEY|ANTHROPIC_API_KEY|GCP_SERVICE_ACCOUNT)"

echo "🔍 機密情報チェック中..."
if grep -rE -i "$SECRET_PATTERNS" \
  "$VAULT_PATH/" --exclude-dir=.git --exclude="*.md" -q 2>/dev/null; then
  echo "❌ 機密情報検出！バックアップ中止"
  echo "   ※ .mdファイルは除外されます（ドキュメント内のキーワードは許可）"
  exit 1
fi

# バックアップディレクトリ作成・権限確認
mkdir -p "$BACKUP_DIR"
# P1: ディレクトリ権限を所有者のみに制限（Security Agent推奨）
chmod 700 "$BACKUP_DIR"
if [ ! -w "$BACKUP_DIR" ]; then
  echo "❌ バックアップディレクトリに書き込み権限がありません: $BACKUP_DIR"
  exit 1
fi

# バックアップ作成（P2: 明示的エラーチェック追加）
if ! tar -czf "$BACKUP_DIR/vault_${TIMESTAMP}.tar.gz" -C "$PROJECT_ROOT" "obsidian-vault-local/"; then
  echo "❌ アーカイブ作成失敗（ディスクフル等の可能性）"
  rm -f "$BACKUP_DIR/vault_${TIMESTAMP}.tar.gz"  # 部分ファイル削除
  exit 1
fi

# P1-3: バックアップ権限設定（所有者のみ読み書き可能）
chmod 600 "$BACKUP_DIR/vault_${TIMESTAMP}.tar.gz"

# チェックサム作成
shasum -a 256 "$BACKUP_DIR/vault_${TIMESTAMP}.tar.gz" > "$BACKUP_DIR/vault_${TIMESTAMP}.sha256"
chmod 600 "$BACKUP_DIR/vault_${TIMESTAMP}.sha256"

# 古いバックアップ削除（RETENTION_DAYS日以上）
find "$BACKUP_DIR" -name "vault_*.tar.gz" -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true
find "$BACKUP_DIR" -name "vault_*.sha256" -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true

echo "✅ バックアップ完了: $BACKUP_DIR/vault_${TIMESTAMP}.tar.gz"

# P1-4: リストア検証関数（週次実行用）- チェックサム検証追加
verify_restore() {
  echo "🔄 リストア検証開始..."

  LATEST=$(ls -t "$BACKUP_DIR"/vault_*.tar.gz 2>/dev/null | head -1)

  if [ -z "$LATEST" ]; then
    echo "❌ バックアップファイルが見つかりません"
    return 1
  fi

  # ファイル存在確認（レースコンディション対策）
  if [ ! -f "$LATEST" ]; then
    echo "❌ バックアップファイルが削除されました: $LATEST"
    return 1
  fi

  # P1-4: チェックサム検証
  CHECKSUM_FILE="${LATEST%.tar.gz}.sha256"
  if [ -f "$CHECKSUM_FILE" ]; then
    echo "🔐 チェックサム検証中..."
    if ! (cd "$BACKUP_DIR" && shasum -a 256 -c "$(basename "$CHECKSUM_FILE")" 2>/dev/null); then
      echo "❌ チェックサム検証失敗: ファイル破損の可能性"
      return 1
    fi
    echo "✅ チェックサム検証OK"
  else
    echo "⚠️ チェックサムファイルが見つかりません（スキップ）"
  fi

  # 一時ディレクトリ作成（trap付き）
  TEMP=$(mktemp -d -t vault_verify.XXXXXXXXXX)
  trap 'rm -rf "$TEMP"' EXIT ERR INT TERM

  # 展開（エラーチェック付き）
  if ! tar -xzf "$LATEST" -C "$TEMP" 2>/dev/null; then
    echo "❌ アーカイブ展開失敗: $LATEST"
    return 1
  fi

  # ファイル数比較
  ORIG=$(find "$VAULT_PATH" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
  REST=$(find "$TEMP" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')

  # 空Vault検出（偽陽性防止）
  if [ "$ORIG" -eq 0 ]; then
    echo "⚠️ 警告: Vaultが空です（0ファイル）。データ損失の可能性があります"
    return 1
  fi

  if [ "$ORIG" -eq "$REST" ]; then
    echo "✅ リストア検証OK: $ORIG ファイル一致"
    return 0
  else
    echo "❌ リストア検証失敗: 元=$ORIG, 復元=$REST"
    return 1
  fi
}

# --verify オプションでリストア検証を実行
if [ "$1" = "--verify" ]; then
  verify_restore
fi
