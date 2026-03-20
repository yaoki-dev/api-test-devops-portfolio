# Staging環境セットアップガイド

*最終更新: 2026年03月20日*

## 概要

Staging環境はproduction同等のセキュリティポリシーが適用されます。
`config/settings.py` の `_PRODUCTION_LIKE_ENVIRONMENTS` により、
staging と production は同一のバリデーションを受けます。

**影響範囲**: シークレット必須化 + HTTPS強制

## 必須環境変数

Staging環境（`ENVIRONMENT=staging`）では以下が必須です。

### シークレット（いずれか1つ以上）

```bash
SECURITY__API_KEY="your-api-key"       # API認証キー
SECURITY__JWT_SECRET="your-jwt-secret" # JWT署名シークレット
```

`api_key` と `jwt_secret` の少なくとも一方を設定してください。
両方未設定の場合、アプリケーション起動時に `ValueError` が発生します。

### HTTPS必須

```bash
API__BASE_URL=https://staging-api.example.com  # https:// 必須
```

`http://` を指定すると `ValueError` が発生します。

## .envファイル例（staging用）

```bash
ENVIRONMENT=staging
DEBUG=false
API__BASE_URL=https://staging-api.example.com
SECURITY__API_KEY="your-staging-key"  # placeholder example
LOG__LEVEL=INFO
SENTRY__ENABLED=true
SENTRY__ENVIRONMENT=staging
```

## 移行手順（development → staging）

1. `.env` の `ENVIRONMENT` を `staging` に変更
2. `SECURITY__API_KEY` または `SECURITY__JWT_SECRET` を設定
3. `API__BASE_URL` を `https://` URLに変更
4. `uv run python -c "from config.settings import settings; print(settings.environment)"` で検証

## エラーメッセージと対処法

### シークレット未設定

```text
ValueError: Staging environment requires at least one of: SECURITY__API_KEY or SECURITY__JWT_SECRET
```

**対処**: `SECURITY__API_KEY` または `SECURITY__JWT_SECRET` を `.env` に追加してください。

### HTTP URL使用

```text
ValueError: Staging environment requires HTTPS. Set API__BASE_URL to an https:// URL.
```

**対処**: `API__BASE_URL` を `https://` で始まるURLに変更してください。

## 技術的背景

バリデーションは `config/settings.py` の以下のバリデータで実行されます。

- `validate_production_secrets`（model_validator）: シークレット存在チェック
- `validate_production_https`（model_validator）: HTTPS強制チェック

対象環境の定義:

```python
_PRODUCTION_LIKE_ENVIRONMENTS = frozenset({Environment.PRODUCTION, Environment.STAGING})
```

## 参考

- `config/settings.py` L424-532: バリデータ実装
- `.env.example`: 環境変数テンプレート
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
