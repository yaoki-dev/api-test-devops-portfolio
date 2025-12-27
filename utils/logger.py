"""structlogロガー取得モジュール

プロジェクト共通のstructlogロガーを提供。
config/settings.pyのLogConfigと連携して動作。
Sentry統合によりERROR以上のログを自動送信。

使用例:
    from utils.logger import get_logger

    logger = get_logger(__name__)
    logger.info("処理開始", user_id=123, action="login")

utils/logger.pyで示せるスキル:
  1. ✅ 設定一元化パターン（DRY原則）
  2. ✅ config.settingsとの統合（環境別設定）
  3. ✅ シングルトンパターン（lazy initialization）
  4. ✅ テスタビリティ設計
  5. ✅ 型安全（FilteringBoundLogger）
  6. ✅ Sentry統合（エラー監視）
"""

from __future__ import annotations

from typing import Any, cast

import structlog
from structlog.typing import FilteringBoundLogger, WrappedLogger

from config.settings import LogFormat, get_settings


def _sentry_processor(
    logger: WrappedLogger,  # noqa: ARG001
    method_name: str,  # noqa: ARG001
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Sentry連携プロセッサー

    ERROR以上のログをSentryに送信。
    sentry-sdk未インストールまたは未初期化時はスキップ。

    Args:
        logger: structlogラッパー（未使用）
        method_name: ログメソッド名（info, error等）
        event_dict: ログイベント辞書

    Returns:
        変更なしのevent_dict（プロセッサーチェーン継続）
    """
    # ERROR以上のみ対象
    log_level = event_dict.get("level", "").upper()
    if log_level not in ("ERROR", "CRITICAL", "EXCEPTION"):
        return event_dict

    try:
        import sentry_sdk

        # Sentry初期化済みかチェック（SDK 2.x API）
        client = sentry_sdk.get_client()
        if not client.is_active():
            return event_dict

        # イベント情報を取得
        message = event_dict.get("event", "Unknown error")

        # 例外情報があればcapture_exception
        exc_info = event_dict.get("exc_info")
        if exc_info and exc_info is not True:
            sentry_sdk.capture_exception(exc_info)
        else:
            # 例外なしの場合はcapture_message
            # 追加コンテキストをextraとして送信
            extra = {
                k: v
                for k, v in event_dict.items()
                if k not in ("event", "level", "timestamp", "exc_info", "logger")
            }
            with sentry_sdk.push_scope() as scope:
                for key, value in extra.items():
                    scope.set_extra(key, value)
                sentry_sdk.capture_message(
                    message,
                    level=log_level.lower(),
                )

    except ImportError:
        pass  # sentry-sdk未インストール（サイレントスキップ）
    except Exception:  # noqa: BLE001, S110
        pass  # Sentry送信失敗（サイレント失敗、ログ出力継続）

    return event_dict


def get_logger(name: str | None = None) -> FilteringBoundLogger:
    """名前付きロガーの取得

    Args:
        name: ロガー名（通常は__name__を指定）

    Returns:
        FilteringBoundLogger: structlogのフィルタリング対応BoundLogger

    Example:
        logger = get_logger(__name__)
        logger.info("処理完了", elapsed_ms=150)
        logger.warning("リトライ実行", attempt=2, max_attempts=3)
        logger.error("API呼び出し失敗", status_code=500, url="/api/users")
    """
    settings = get_settings()

    # 設定に基づいてstructlogを初期化（初回のみ）
    if not structlog.is_configured():
        _configure_structlog(settings.log.format, settings.get_log_level())

    return cast(FilteringBoundLogger, structlog.get_logger(name))


def _configure_structlog(log_format: LogFormat, log_level: int) -> None:
    """structlogの初期化（内部関数）

    Args:
        log_format: ログフォーマット（console/json）
        log_level: ログレベル（logging定数）
    """
    # 共通プロセッサー（Sentry連携を含む）
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.set_exc_info,
        _sentry_processor,  # Sentry連携（ERROR以上を送信）
    ]

    # フォーマット別レンダラー
    processors: list[Any]
    if log_format == LogFormat.JSON:
        processors = [
            *shared_processors,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
