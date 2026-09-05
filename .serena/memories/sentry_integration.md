# Sentry統合ガイド

*最終更新: 2026年07月27日*
*用途: Sentry SDK設定・機密データ保護・MCP統合*
*アクセス頻度: 低（Sentry設定・デバッグ時のみ）*

## 概要

Sentry SDKを統合し、ERROR以上のログを自動でSentryに送信。エラー調査→修正サイクルを加速。

**コアモジュール**（PR#534 で責務別に4分割。依存は上から下への一方向）:
- `utils/sentry_init.py`: SDK初期化のみ（`init_sentry` / `is_sentry_initialized` / `reset_sentry_state`）
- `utils/sentry_scrub_events.py`: イベント単位のスクラブ（`_before_send` / exception / tags / spans）
- `utils/sentry_scrub_values.py`: 値の再帰スクラブ（`_scrub_sensitive_data` / URL・クエリ文字列）
- `utils/sentry_scrub_primitives.py`: 機密キー判定（`SENSITIVE_KEYS` / `_is_sensitive_key`）と共通ログヘルパー
- `utils/logger.py`: structlog連携プロセッサー
- `config/settings.py`: SentryConfig設定クラス

---

## 環境変数

DSN は機密のため `.env` に書かず、OS 環境変数で注入する（write-only の ingest キーだが
コミット対象ファイルには置かない）。`.env` 側は `SENTRY__ENABLED=false` のまま残し、
有効化はローカルの一時環境変数で行う。

```bash
export SENTRY__DSN=<your-dsn>   # 例: https://xxx@oNNN.ingest.us.sentry.io/NNN
# init_sentry() は成功時も内部ログを出さない設計のため、戻り値を明示的に表示する
SENTRY__ENABLED=true uv run python -c "from utils.sentry_init import init_sentry; print('Sentry initialized:', init_sentry())"
```

任意の調整項目（`.env` に書いてよい非機密値）:

```bash
SENTRY__ENVIRONMENT=production  # 省略時: settings.environmentを使用
SENTRY__TRACES_SAMPLE_RATE=0.1  # トレースサンプリング率
SENTRY__PROFILES_SAMPLE_RATE=0.1  # プロファイルサンプリング率
SENTRY__SEND_DEFAULT_PII=false  # PII送信無効（推奨・既定値）
```

### 推奨設定

| 用途 | SENTRY__ENABLED | 理由 |
|------|-----------------|------|
| **開発・CI・README記載のデモ** | `false`（既定） | 再現性確保（レビュアーはDSN未所持）、ノイズ削減、シークレット非露出 |
| **ローカルでの動作確認** | `true`（一時的にOS envで） | observability機能・PIIスクラブの実挙動を確認する場合のみ |

> 本プロジェクトは実運用インフラ（Cloud Run/ECS/K8s等）への本番デプロイ未実装のポートフォリオのため、
> 「本番運用時にtrue」という区分は該当しない。Sentry統合は実装能力のshowcaseとして位置づけ、
> 実行系のデモには含めない（README「Sentry統合」セクション参照）。

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

`before_send`フックで以下**46種類**の機密キーを自動スクラブ:

| カテゴリ | キー | 個数 |
|---------|------|------|
| **認証系（基本）** | password, token, secret, api_key, dsn, authorization, cookie, session, credential | 9 |
| **認証系（拡張）** | bearer, jwt, access_token, refresh_token, private_key, client_secret, x-api-key, auth_token, authtoken, usertoken, userpassword, passwd | 12 |
| **暗号化** | encryption_key, cipher_key | 2 |
| **OAuth** | oauth_token | 1 |
| **二要素認証** | otp, mfa, totp | 3 |
| **個人情報** | email, ip_address, username, database_url, ssn, credit_card, cvv, card_number, phone, phone_number | 10 |
| **HTTPヘッダー/レスポンス** | body_preview, access_key, proxy-authorization, set-cookie, x-auth-token, csrf_token, x-csrf-token, x-refresh-token, x-access-token | 9 |
| **合計** | - | **46** |

**注記 (個数 baseline)**:

- `CHANGELOG.md` の「32 → 44（+12件）」表記は**その時点の**最終状態と一致する
  （現在は `phone` / `phone_number` 追加後の 46 件）。
  起点 32 は **PR#340 で `email` / `ip_address` / `body_preview` 追加後の件数**。
  PR#340 前起点では **29 → 44（+15件）**。
- 現ステージ済 PR で追加された **12 件** の内訳（CHANGELOG.md と同一）:
  - 認証系 1 件: `access_key`
  - HTTP ヘッダー 7 件: `proxy-authorization`, `set-cookie`, `x-auth-token`,
    `csrf_token`, `x-csrf-token`, `x-refresh-token`, `x-access-token`
  - 複合語バリアント 3 件: `authtoken`, `usertoken`, `userpassword`
  - 個人情報 1 件: `username`（PR#347 review follow-up で追加）
- 現在の状態は **46 件**（`utils/sentry_scrub_primitives.py` 実装・`test_sentry_scrub_primitives.py::assert len(SENSITIVE_KEYS) == 46` と一致）。

**確認元**: `utils/sentry_scrub_primitives.py` (`SENSITIVE_KEYS` frozenset)
**マッチング方式**: `_is_sensitive_key` は **単語境界マッチ + ハイフン/アンダースコア
正規化** で判定する (`_SENSITIVE_KEY_PATTERN = (?:^|[_\d])(?:KEY)(?=[^a-z]|$)`)。
これにより composite key (例: `user_password`, `email_address`, `X-Auth-Token`)
や数字サフィックス付きキー (例: `password2`, `api_key2`) も全て redact される
(defense-in-depth)。一方で `prototype` / `photo_url` 等の機密語を**部分文字列として
含むだけ**の非機密キーは過剰検出されない (PR#347 で substring → 単語境界へ変更)。

履歴:
- PR#340 以前: substring 一致 → 過剰検出あり
- PR#347 fix #1: substring → exact 一致で composite key 漏洩 regression 発生 → 修正
- PR#347 fix #2: 末尾境界に `\d` 追加 (`password2` 系を補足)

詳細は `utils/sentry_scrub_primitives.py` の `_NORMALIZED_SENSITIVE_KEYS` /
`_SENSITIVE_KEY_PATTERN` 周辺コメント、契約テストは
`tests/unit/test_sentry_scrub_primitives.py::TestSensitiveKeysCompleteness` を参照。

---

## MCP統合

このポートフォリオでは、開発時のエラー調査に Sentry MCP サーバーを利用できます。これは開発者が使うツールであり、アプリケーションが実行時にエラーを送信する Sentry SDK 統合とは別のレイヤーです。

接続設定は利用するAIコーディングツールのローカル設定が保持するため、本リポジトリには含めません。

**参照**: [Sentry MCP Docs](https://docs.sentry.io/product/sentry-mcp/)

---

## テスト

```bash
uv run pytest -k sentry -v --no-cov
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
from utils.sentry_scrub_primitives import SENSITIVE_KEYS
print(len(SENSITIVE_KEYS))  # 46
```
