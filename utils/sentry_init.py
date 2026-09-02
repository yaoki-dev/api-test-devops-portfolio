"""Sentry SDK初期化モジュール

エラー監視サービスSentryとの統合を提供。
structlogと連携し、ERROR以上のログをSentryに送信。

依存関係:
    - config/settings.py: SentryConfig（DSN、有効化フラグ等）
    - sentry-sdk[httpx] >= 2.61.0: before_send / new_scope APIを使用

初期化タイミング:
    アプリケーション起動時、ログ設定後に一度だけ呼び出し。
    structlogのconfigure()後、最初のログ出力前が推奨。

使用例:
    from utils.sentry_init import init_sentry

    # アプリケーション起動時
    if init_sentry():
        logger.info("Sentry monitoring enabled")

デバッグ:
    初期化失敗時は warning ログを常時出力する（本番監視対応）。

セキュリティ:
    - before_sendフックで機密データを自動除外（46種類のキーパターン）
    - DSNはSecretStrで管理（config/settings.py）
    - enabled=Falseで完全無効化可能
"""

from __future__ import annotations

import sys
import threading

from config.settings import get_settings
from utils.logger import get_logger
from utils.sentry_scrub_events import _before_send

_logger = get_logger(__name__)

# 遅延初期化フラグ
_sentry_initialized: bool = False
_sentry_init_lock = threading.Lock()


def init_sentry() -> bool:
    """Sentry SDKをプロセス内で一度だけ初期化する。"""
    with _sentry_init_lock:
        if _sentry_initialized:
            return True
        return _init_sentry_unlocked()


def _init_sentry_unlocked() -> bool:  # noqa: C901
    """Sentry SDK初期化（呼び出し側で _sentry_init_lock を保持していること）。

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

    # is_production_like() を関数先頭で一度だけ評価しローカル変数に保持。
    # except 内で get_settings() を再呼び出しすると、環境変数変化や reload_settings()
    # の race により ValidationError が発生し、元の例外（ImportError / 初期化失敗）を
    # マスクしてデバッグを困難化するリスクがあるため (CWE-755 例外マスク防止)。
    is_production_like = settings.is_production_like()

    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            traces_sample_rate=sentry_config.traces_sample_rate,
            profiles_sample_rate=sentry_config.profiles_sample_rate,
            send_default_pii=sentry_config.send_default_pii,
            before_send=_before_send,
            # transaction イベントは before_send を通らない（SDK仕様）。同一 scrub 経路へ
            # 配線し、span data / WSGI-ASGI 由来の request を PII スクラブする
            # per-event scrub コストは traces_sample_rate（既定 0.1 = 低サンプリング）で
            # 上限が画定されるため、現設定では累積負荷は許容範囲
            before_send_transaction=_before_send,
        )

        _sentry_initialized = True
        return True

    except ImportError as exc:
        # sentry-sdk未インストール
        # 本番環境では必須 → Fail-Fast（依存関係漏れを即座に検出）
        if is_production_like:
            raise RuntimeError(
                f"Sentry SDK not installed in production: {exc}. Add 'sentry-sdk' to dependencies.",
            ) from exc

        # 開発/テスト環境では許容（ログ警告のみ）
        # warnings.warn は filterwarnings('error') 環境で UserWarning を raise し、
        # __context__ 経由で DSN が漏洩するリスクがあるため _logger.warning に変更。
        try:
            _logger.warning(
                "sentry_sdk_not_installed",
                error_type=type(exc).__name__,
                error_module=type(exc).__module__,
            )
        except Exception as logger_exc:  # noqa: BLE001
            # ロガー失敗時は stderr へフォールバック（PII 非露出）。
            # _emit_scrub_failure_to_sentry と同様にエラー型/モジュールを記録し設計を統一
            print(
                "[SENTRY_WARN] sentry_sdk_not_installed "
                f"original_error_type={type(exc).__name__} "
                f"original_error_module={type(exc).__module__} "
                f"logger_error_type={type(logger_exc).__name__} "
                f"logger_error_module={type(logger_exc).__module__}",
                file=sys.stderr,
                flush=True,
            )
        return False

    except Exception as exc:
        # その他の初期化失敗 - 本番環境では例外を発生させる（Fail-Fast）
        if is_production_like:
            raise RuntimeError(
                f"Sentry initialization failed in production: {type(exc).__name__}",
            ) from exc

        # 開発/テスト環境ではログ警告のみ
        # warnings.warn は filterwarnings('error') 環境で UserWarning を raise し、
        # __context__ 経由で DSN が漏洩するリスクがあるため _logger.warning に変更。
        try:
            _logger.warning(
                "sentry_init_failed",
                error_type=type(exc).__name__,
                error_module=type(exc).__module__,
            )
        except Exception as logger_exc:  # noqa: BLE001
            # ロガー失敗時は stderr へフォールバック（PII 非露出）。
            # _emit_scrub_failure_to_sentry と同様にエラー型/モジュールを記録し設計を統一
            print(
                "[SENTRY_WARN] sentry_init_failed "
                f"original_error_type={type(exc).__name__} "
                f"original_error_module={type(exc).__module__} "
                f"logger_error_type={type(logger_exc).__name__} "
                f"logger_error_module={type(logger_exc).__module__}",
                file=sys.stderr,
                flush=True,
            )
        return False


def is_sentry_initialized() -> bool:
    """Sentry初期化状態の確認

    Returns:
        True: 初期化済み
        False: 未初期化

    """
    with _sentry_init_lock:
        return _sentry_initialized


def reset_sentry_state() -> None:
    """Sentry状態リセット（テスト用）

    Warning:
        本番コードでは使用しないでください。

    """
    global _sentry_initialized  # noqa: PLW0603
    with _sentry_init_lock:
        _sentry_initialized = False
