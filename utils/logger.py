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

import os
import sys
import threading
from typing import Any, cast

import structlog
from structlog.typing import FilteringBoundLogger, WrappedLogger

from config.settings import LogFormat, get_settings

# _sentry_processor の stderr 警告を per-process 1 回に抑制する module-level state
#
# structlog processor は ERROR/CRITICAL/EXCEPTION ログ毎に呼ばれるため、
# settings 失敗 × sentry-sdk 未インストール が持続する環境 (CI 破壊・.env 破損) では
# ログ1件につき 2 行の警告が stderr に出力される。エラーストーム時の log flood を避けるため
# 同一警告を process 内で 1 回のみ出力する。
#
# _sentry_warning_lock: マルチスレッド環境 (uvicorn worker / ThreadPoolExecutor) で
# check-and-set の race condition を防ぎ flag 昇格を atomic 化する。
# lock は _emit_import_error_warnings() の全処理を単一 critical section で覆い、
# get_settings() 呼び出しと flag 更新の間に TOCTOU が発生しないことを保証する。
_sentry_warning_lock = threading.Lock()
_sentry_settings_warning_emitted = False
_sentry_sdk_warning_emitted = False


def _reset_sentry_warning_state() -> None:
    """test 用: throttle flag を初期化し各テストを fresh state で実行

    process-level flag のため前テストの state が残ると警告出力検証が非決定的になる。
    """
    global _sentry_settings_warning_emitted, _sentry_sdk_warning_emitted
    with _sentry_warning_lock:
        _sentry_settings_warning_emitted = False
        _sentry_sdk_warning_emitted = False


def _emit_import_error_warnings() -> None:
    """sentry-sdk 未インストール時の stderr 警告を throttle 付きで出力

    設計方針: sentry_init.py は startup 時 Fail-Fast (RuntimeError)、
    logger.py は per-log-call coupling 回避のため警告出力で graceful degrade
    （本番デプロイ時の未インストール検知可能性を保証）。
    defensive: get_settings() が reload_settings() 後に ValidationError を
    発生させる可能性を遮断し log processor 内で例外伝播を防ぐ。

    TOCTOU 防止: lock 内で get_settings() を含む全処理を atomic 化する。
    （config/settings.py は lock を取得しないためデッドロックは発生しない）
    """
    global _sentry_settings_warning_emitted, _sentry_sdk_warning_emitted
    with _sentry_warning_lock:
        # 早期リターン: sdk 警告が既出なら後続処理不要
        # (settings 成功 × is_prod=True の正規ルートでは settings フラグは昇格しないため
        #  旧実装の「両フラグ AND」条件は機能しなかった。sdk フラグのみで判定する)
        if _sentry_sdk_warning_emitted:
            return
        try:
            is_prod = get_settings().is_production()
        # 設計意図: get_settings() は reload_settings()/ValidationError/AttributeError 等
        # 複数種の失敗モードを持ち、全て「本番環境不明」として安全側フォールバック扱いとする。
        # BLE001 はプロセッサ内で例外を再送出しない (log processor の循環失敗回避) ため許容。
        except Exception as e:  # noqa: BLE001
            is_prod = True  # 本番可能性を排除できないため安全側フォールバック
            if not _sentry_settings_warning_emitted:
                # Pydantic ValidationError は str(e) に input_value を平文含むため
                # 非SecretStr 設定値 (例: API__BASE_URL) が log aggregation に漏洩する。
                # errors(include_input=False) で input 除外した summary を生成する。
                detail = str(e)
                errors_fn = getattr(e, "errors", None)
                if callable(errors_fn):
                    try:
                        errs = list(errors_fn(include_input=False))
                        detail = f"{len(errs)} validation error(s)"
                    except Exception:  # noqa: BLE001, S110
                        detail = "details omitted"
                print(
                    f"[SENTRY_WARN] settings load failed: {type(e).__name__}: {detail}",
                    file=sys.stderr,
                )
                _sentry_settings_warning_emitted = True
        if is_prod or os.environ.get("SENTRY_DEBUG", "").lower() in ("true", "1", "yes"):
            print(
                "[SENTRY_WARN] sentry-sdk not installed, skipping Sentry capture",
                file=sys.stderr,
            )
            _sentry_sdk_warning_emitted = True


def _sentry_processor(
    logger: WrappedLogger,  # noqa: ARG001
    method_name: str,  # noqa: ARG001
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Sentry連携プロセッサー

    ERROR以上のログをSentryに送信。
    sentry-sdk未インストールまたは未初期化時はスキップ
    （本番環境または SENTRY_DEBUG 有効時は stderr に警告出力）。

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
        exc_info = event_dict.get("exc_info")

        # 追加コンテキストをextraとして送信 (exc_info/message 両経路で付与)
        extra = {
            k: v
            for k, v in event_dict.items()
            if k not in ("event", "level", "timestamp", "exc_info", "logger")
        }
        # new_scope() 内で capture_exception/capture_message 双方を実行し
        # structlog bind された追加コンテキスト (user_id, request_id 等) を Sentry event に付与
        with sentry_sdk.new_scope() as scope:
            for key, value in extra.items():
                scope.set_extra(key, value)
            if exc_info and exc_info is not True:
                sentry_sdk.capture_exception(exc_info)
            else:
                scope.capture_message(
                    message,
                    level=log_level.lower(),
                )

    except ImportError:
        _emit_import_error_warnings()
    except KeyboardInterrupt, SystemExit, MemoryError:
        # システム例外は再発生（graceful shutdown/K8s OOMKilled検知対応）
        raise
    except Exception as e:  # noqa: BLE001
        # Sentry送信失敗時はstderrへ出力（循環参照回避のためstructlog不使用）
        # 設計意図: Sentry障害時もアプリケーション継続を優先
        # ネットワークエラー、Sentry側の一時障害等を想定
        print(
            f"[SENTRY_ERROR] Failed to send to Sentry: {type(e).__name__}: {e}",
            file=sys.stderr,
        )

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

    return cast("FilteringBoundLogger", structlog.get_logger(name))


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
