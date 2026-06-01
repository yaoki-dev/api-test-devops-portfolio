# Sentry統合ガイド

*最終更新: 2026年5月26日*
*用途: Sentry SDK設定・機密データ保護・MCP統合*
*アクセス頻度: 低（Sentry設定・デバッグ時のみ）*

## 概要

Sentry SDKを統合し、ERROR以上のログを自動でSentryに送信。エラー調査→修正サイクルを加速。

**コアモジュール**:
- `utils/sentry_init.py`: SDK初期化・機密データスクラブ
- `utils/logger.py`: structlog連携プロセッサー
- `config/settings.py`: SentryConfig設定クラス

---

## 環境変数

```bash
# .envファイル
SENTRY__ENABLED=true
SENTRY__DSN=https://xxx@xxx.ingest.us.sentry.io/xxx
SENTRY__ENVIRONMENT=production  # 省略時: settings.environmentを使用
SENTRY__TRACES_SAMPLE_RATE=0.1  # トレースサンプリング率
SENTRY__PROFILES_SAMPLE_RATE=0.1  # プロファイルサンプリング率
SENTRY__SEND_DEFAULT_PII=false  # PII送信無効（推奨）
```

### 開発時の推奨設定

| 環境 | SENTRY__ENABLED | 理由 |
|------|-----------------|------|
| **開発** | `false` | ノイズ削減、トークンコスト節約 |
| **デモ/本番** | `true` | エラー監視有効化 |

---

## 初期化

```python
from utils.sentry_init import init_sentry
from utils.logger import get_logger

logger = get_logger(__name__)

# アプリケーション起動時に1回呼び出し
if init_sentry():
    logger.info("Sentry monitoring enabled")
```

---

## 機密データ保護

`before_send`フックで以下**43種類**の機密キーを自動スクラブ:

| カテゴリ | キー | 個数 |
|---------|------|------|
| **認証系（基本）** | password, token, secret, api_key, dsn, authorization, cookie, session, credential | 9 |
| **認証系（拡張）** | bearer, jwt, access_token, refresh_token, private_key, client_secret, x-api-key, auth_token, authtoken, usertoken, userpassword, passwd | 12 |
| **暗号化** | encryption_key, cipher_key | 2 |
| **OAuth** | oauth_token | 1 |
| **二要素認証** | otp, mfa, totp | 3 |
| **個人情報** | email, ip_address, database_url, ssn, credit_card, cvv, card_number | 7 |
| **HTTPヘッダー/レスポンス** | body_preview, access_key, proxy-authorization, set-cookie, x-auth-token, csrf_token, x-csrf-token, x-refresh-token, x-access-token | 9 |
| **合計** | - | **43** |

**注記 (個数 baseline)**:

- `CHANGELOG.md` の「32 → 43（+11件）」表記が最終状態と一致する。
  起点 32 は **PR#340 で `email` / `ip_address` / `body_preview` 追加後の件数**。
  PR#340 前起点では **29 → 43（+14件）**。
- 現ステージ済 PR で追加された **11 件** の内訳（CHANGELOG.md と同一）:
  - 認証系 1 件: `access_key`
  - HTTP ヘッダー 7 件: `proxy-authorization`, `set-cookie`, `x-auth-token`,
    `csrf_token`, `x-csrf-token`, `x-refresh-token`, `x-access-token`
  - 複合語バリアント 3 件: `authtoken`, `usertoken`, `userpassword`
- 最終状態は **43 件**（32 + 11、上記内訳テーブル合計と一致）。

**確認元**: `utils/sentry_init.py` (`SENSITIVE_KEYS` frozenset)
**マッチング方式**: `_is_sensitive_key` は **単語境界マッチ + ハイフン/アンダースコア
正規化** で判定する (`_SENSITIVE_KEY_PATTERN = (?:^|[_\d])(?:KEY)(?:[_\d]|$)`)。
これにより composite key (例: `user_password`, `email_address`, `X-Auth-Token`)
や数字サフィックス付きキー (例: `password2`, `api_key2`) も全て redact される
(defense-in-depth)。一方で `prototype` / `photo_url` 等の機密語を**部分文字列として
含むだけ**の非機密キーは過剰検出されない (PR#347 で substring → 単語境界へ変更)。

履歴:
- PR#340 以前: substring 一致 → 過剰検出あり
- PR#347 fix #1: substring → exact 一致で composite key 漏洩 regression 発生 → 修正
- PR#347 fix #2: 末尾境界に `\d` 追加 (`password2` 系を補足)

詳細は `utils/sentry_init.py` の `_NORMALIZED_SENSITIVE_KEYS` / `_SENSITIVE_KEY_PATTERN`
周辺コメント、契約テストは `tests/unit/test_sentry_init.py::TestSensitiveKeysCompleteness`
を参照。

---

## MCP統合

Sentry MCPサーバーでClaude Codeからエラー調査可能:

```json
// .mcp.json
"sentry": {
  "type": "http",
  "url": "https://mcp.sentry.dev/mcp"
}
```

**参照**: [Sentry MCP Docs](https://docs.sentry.io/product/sentry-mcp/)

---

## テスト

```bash
# Sentry統合テスト（106 test functions / 225 collected cases）
uv run pytest tests/unit/test_sentry_init.py -v
```

---

## トラブルシューティング

### Sentry初期化失敗時

初期化失敗時の警告は `SENTRY_DEBUG` に依存せず **常時** `_logger.warning` で出力される
（本番監視対応, PR#347 #3/#7）。`SENTRY_DEBUG` は `utils/logger.py` の
`_is_sentry_debug_enabled()` が消費する環境変数で、有効化すると Sentry 関連の
追加診断（送信失敗の詳細・ImportError 等）を stderr へ出力する:

```bash
# 追加の Sentry 診断を stderr へ出力（初期化失敗警告自体は常時出力される）
export SENTRY_DEBUG=true
```

### 機密データ漏洩の確認

```python
# スクラブ対象キーの確認
from utils.sentry_init import SENSITIVE_KEYS
print(len(SENSITIVE_KEYS))  # 43
```
