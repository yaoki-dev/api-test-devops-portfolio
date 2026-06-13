# Staging環境セットアップ

*最終更新: 2026年03月21日*

## 概要

Staging環境はproduction同等のセキュリティポリシー（シークレット必須化・HTTPS強制）が適用されます。

## 必須環境変数

Staging環境（`ENVIRONMENT=staging`）では以下が必須です。

### シークレット（いずれか1つ以上）

```bash
SECURITY__API_KEY=<REPLACE_WITH_API_KEY>        # API認証キー
SECURITY__JWT_SECRET=<REPLACE_WITH_JWT_SECRET>  # JWT署名シークレット
```

`SECURITY__API_KEY` と `SECURITY__JWT_SECRET` の少なくとも一方を設定してください。
両方未設定の場合、アプリケーション起動時に `ValidationError` が発生します。

### HTTPS必須

```bash
API__BASE_URL=https://<REPLACE_WITH_STAGING_API_URL>  # https:// 必須
```

`http://` を指定すると `ValidationError` が発生します。

## .envファイル例（staging用）

```bash
ENVIRONMENT=staging
DEBUG=false
API__BASE_URL=https://<REPLACE_WITH_STAGING_API_URL>
ALLOWED_DOMAINS=<REPLACE_WITH_STAGING_API_DOMAIN>  # デフォルトリストを上書き（置換）。複数ドメイン必要な場合はカンマ区切りで全て列挙
SECURITY__API_KEY=<REPLACE_WITH_STAGING_API_KEY>
LOG__LEVEL=INFO
SENTRY__ENABLED=true
SENTRY__ENVIRONMENT=staging
SENTRY__DSN=<REPLACE_WITH_SENTRY_DSN>
```

## 移行手順（development → staging）

1. `.env` の `ENVIRONMENT` を `staging` に変更
2. `SECURITY__API_KEY` または `SECURITY__JWT_SECRET` を設定
3. `API__BASE_URL` を `https://` URLに変更
4. アプリ起動時（Pydantic Settingsインスタンス化）にValidationErrorが発生しなければ設定は正常である。

## エラーメッセージと対処法

### シークレット未設定

```text
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
  Value error, Staging environment requires at least one of: SECURITY__API_KEY or SECURITY__JWT_SECRET [type=value_error, ...]
```

**対処**: `SECURITY__API_KEY` または `SECURITY__JWT_SECRET` を `.env` に追加してください。

### HTTP URL使用

```text
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
  Value error, Staging environment requires HTTPS. Set API__BASE_URL to an https:// URL. [type=value_error, ...]
```

**対処**: `API__BASE_URL` を `https://` で始まるURLに変更してください。

### Domain not in allowlist

```text
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
  Value error, SSRF Prevention: Domain not in allowlist. [type=value_error, ...]
```

**対処**: `ALLOWED_DOMAINS=<staging-domain>` を `.env` に追加してください。

## 参考

- `config/settings.py`: バリデータ実装（`validate_production_secrets` / `validate_production_https`）
- `.env.example`: 環境変数テンプレート
