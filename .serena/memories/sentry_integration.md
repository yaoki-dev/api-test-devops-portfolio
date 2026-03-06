# Sentry統合ガイド

*最終更新: 2025年12月29日*
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

`before_send`フックで以下**29種類**の機密キーを自動スクラブ:

| カテゴリ | キー | 個数 |
|---------|------|------|
| **認証系（基本）** | password, token, secret, api_key, dsn, authorization, cookie, session, credential | 9 |
| **認証系（拡張）** | bearer, jwt, access_token, refresh_token, private_key, client_secret, x-api-key, auth_token, passwd | 9 |
| **暗号化** | encryption_key, cipher_key | 2 |
| **OAuth** | oauth_token | 1 |
| **二要素認証** | otp, mfa, totp | 3 |
| **個人情報** | database_url, ssn, credit_card, cvv, card_number | 5 |
| **合計** | - | **29** |

**確認元**: `utils/sentry_init.py` Lines 45-83 (`SENSITIVE_KEYS` frozenset)

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
# Sentry統合テスト（31ケース）
uv run pytest tests/unit/test_sentry_init.py -v
```

---

## トラブルシューティング

### Sentry初期化失敗時

```bash
# デバッグモード有効化
export SENTRY_DEBUG=true
```

### 機密データ漏洩の確認

```python
# スクラブ対象キーの確認
from utils.sentry_init import SENSITIVE_KEYS
print(len(SENSITIVE_KEYS))  # 29
```
