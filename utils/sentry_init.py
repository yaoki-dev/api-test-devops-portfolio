"""Sentry SDK初期化モジュール

エラー監視サービスSentryとの統合を提供。
structlogと連携し、ERROR以上のログをSentryに送信。

依存関係:
    - config/settings.py: SentryConfig（DSN、有効化フラグ等）
    - sentry-sdk >= 2.0.0: before_send APIを使用

初期化タイミング:
    アプリケーション起動時、ログ設定後に一度だけ呼び出し。
    structlogのconfigure()後、最初のログ出力前が推奨。

使用例:
    from utils.sentry_init import init_sentry

    # アプリケーション起動時
    if init_sentry():
        logger.info("Sentry monitoring enabled")

デバッグ:
    環境変数 SENTRY_DEBUG=true で初期化失敗の警告を有効化。

セキュリティ:
    - before_sendフックで機密データを自動除外（29種類のキーパターン）
    - DSNはSecretStrで管理（config/settings.py）
    - enabled=Falseで完全無効化可能
"""

from __future__ import annotations

import os
import warnings
from typing import TYPE_CHECKING, Any

from config.settings import get_settings

# デバッグモード（環境変数で有効化）
SENTRY_DEBUG: bool = os.environ.get("SENTRY_DEBUG", "").lower() in ("true", "1", "yes")

if TYPE_CHECKING:
    from sentry_sdk.types import Event, Hint

# 機密データキーのパターン（Security Auditor推奨を反映）
SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        # 認証系（基本）
        "password",
        "token",
        "secret",
        "api_key",
        "dsn",
        "authorization",
        "cookie",
        "session",
        "credential",
        # 認証系（拡張）
        "bearer",
        "jwt",
        "access_token",
        "refresh_token",
        "private_key",
        "client_secret",
        "x-api-key",
        "auth_token",
        "passwd",
        # 暗号化
        "encryption_key",
        "cipher_key",
        # OAuth
        "oauth_token",
        # 二要素認証
        "otp",
        "mfa",
        "totp",
        # 個人情報
        "email",  # GDPR/個人情報保護法: メールアドレスは個人識別情報
        "database_url",
        "ssn",
        "credit_card",
        "cvv",
        "card_number",
    },
)

# 遅延初期化フラグ
_sentry_initialized: bool = False


# 再帰制限のデフォルト値
MAX_SCRUB_DEPTH: int = 10


def _scrub_sensitive_data(data: Any, _depth: int = 0) -> Any:
    """機密データを再帰的にスクラブ

    Args:
        data: スクラブ対象のデータ
        _depth: 現在の再帰深度（内部使用）

    Returns:
        スクラブ済みデータ（元データは変更しない）

    Note:
        MAX_SCRUB_DEPTH（デフォルト10）を超えると再帰を停止し、
        循環参照による無限ループを防止する。

    """
    if not isinstance(data, dict):
        return data

    # 再帰制限チェック（循環参照対策）
    if _depth >= MAX_SCRUB_DEPTH:
        return "[MAX_DEPTH_EXCEEDED]"

    result: dict[str, Any] = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in SENSITIVE_KEYS):
            result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            result[key] = _scrub_sensitive_data(value, _depth + 1)
        elif isinstance(value, list):
            result[key] = [
                _scrub_sensitive_data(item, _depth + 1) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def _before_send(event: Event, hint: Hint) -> Event | None:  # noqa: ARG001
    """Sentry送信前フック（機密データ除外）

    Args:
        event: Sentryイベント
        hint: 追加コンテキスト（未使用）

    Returns:
        処理済みイベント、またはNone（送信キャンセル）

    """
    # リクエストデータのスクラブ
    if "request" in event:
        request = event["request"]
        if isinstance(request, dict):
            if "headers" in request:
                request["headers"] = _scrub_sensitive_data(request["headers"])
            if "data" in request:
                request["data"] = _scrub_sensitive_data(request["data"])

    # 追加データのスクラブ
    if "extra" in event:
        event["extra"] = _scrub_sensitive_data(event["extra"])

    # タグのスクラブ
    if "tags" in event:
        event["tags"] = _scrub_sensitive_data(event["tags"])

    return event


def init_sentry() -> bool:
    """Sentry SDK初期化

    config/settings.pyのSentryConfigに基づいて初期化。
    enabled=Falseまたは空DSNの場合はスキップ。

    Returns:
        True: 初期化成功
        False: スキップまたは失敗

    Example:
        if init_sentry():
            logger.info("Sentry monitoring enabled")

    """
    global _sentry_initialized  # noqa: PLW0603

    # 二重初期化防止
    if _sentry_initialized:
        return True

    settings = get_settings()
    sentry_config = settings.sentry

    # 無効化チェック
    if not sentry_config.enabled:
        return False

    # DSN取得・検証
    dsn = sentry_config.dsn.get_secret_value()
    if not dsn:
        return False

    # 環境名（フォールバック）
    # Note: DSN検証はsentry_sdk.init()に委任（SDK内部でバリデーション実施）
    environment = sentry_config.environment or settings.environment.value

    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            traces_sample_rate=sentry_config.traces_sample_rate,
            profiles_sample_rate=sentry_config.profiles_sample_rate,
            send_default_pii=sentry_config.send_default_pii,
            before_send=_before_send,
        )

        _sentry_initialized = True
        return True

    except ImportError as exc:
        # sentry-sdk未インストール
        # 本番環境では必須 → Fail-Fast（依存関係漏れを即座に検出）
        settings = get_settings()
        if settings.is_production():
            raise RuntimeError(
                f"Sentry SDK not installed in production: {exc}. Add 'sentry-sdk' to dependencies.",
            ) from exc

        # 開発/テスト環境では許容（警告のみ）
        if SENTRY_DEBUG:
            warnings.warn(
                f"Sentry SDK not installed: {exc}",
                UserWarning,
                stacklevel=2,
            )
        return False

    except Exception as exc:
        # その他の初期化失敗 - 本番環境では例外を発生させる（Fail-Fast）
        settings = get_settings()
        if settings.is_production():
            raise RuntimeError(
                f"Sentry initialization failed in production: {type(exc).__name__}: {exc}",
            ) from exc

        # 開発/テスト環境では警告のみ
        if SENTRY_DEBUG:
            warnings.warn(
                f"Sentry initialization failed: {type(exc).__name__}: {exc}",
                UserWarning,
                stacklevel=2,
            )
        return False


def is_sentry_initialized() -> bool:
    """Sentry初期化状態の確認

    Returns:
        True: 初期化済み
        False: 未初期化

    """
    return _sentry_initialized


def reset_sentry_state() -> None:
    """Sentry状態リセット（テスト用）

    Warning:
        本番コードでは使用しないでください。

    """
    global _sentry_initialized  # noqa: PLW0603
    _sentry_initialized = False
