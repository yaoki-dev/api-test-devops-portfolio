"""structlogロガー取得モジュール

プロジェクト共通のstructlogロガーを提供。
config/settings.pyのLogConfigと連携して動作。

使用例:
    from utils.logger import get_logger

    logger = get_logger(__name__)
    logger.info("処理開始", user_id=123, action="login")
"""

from __future__ import annotations

from typing import Any, cast

import structlog
from structlog.typing import FilteringBoundLogger

from config.settings import LogFormat, get_settings


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
    # 共通プロセッサー
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.set_exc_info,
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
