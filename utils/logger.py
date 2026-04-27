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
from typing import Any, Literal, cast

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
# lock は _emit_import_error_warnings() および _emit_sentry_send_error() の
# 全処理を単一 critical section で覆い、get_settings() 呼び出しと flag 更新の間に
# TOCTOU が発生しないことを保証する。
_sentry_warning_lock = threading.Lock()
_sentry_settings_warning_emitted = False
_sentry_sdk_warning_emitted = False
_sentry_send_error_emitted = False
_sentry_bug_emitted = False
_sentry_outside_except_warning_emitted = False

# structlog の "EXCEPTION" レベルを Sentry SDK が受理するレベルへ正規化するマップ。
# structlog の "exception" は Sentry 側に存在しないため "error" へマップする。
_SENTRY_LEVEL_MAP: dict[str, Literal["error", "critical"]] = {
    "error": "error",
    "critical": "critical",
    "exception": "error",  # structlog "exception" → Sentry "error" へ正規化
}

# SENTRY_DEBUG 有効時に stderr へ出力する例外詳細の最大文字数 (CWE-532 対策)
_SENTRY_DEBUG_DETAIL_MAX_LEN: int = 100


def _emit_sentry_send_error(e: Exception) -> None:
    """Sentry送信失敗の stderr 警告を per-process 1 回に throttle 出力

    DSN/HTTP レスポンスボディ漏洩防止のため SENTRY_DEBUG 有効時でも
    str(e) を 100 文字に切り詰める。
    """
    global _sentry_send_error_emitted
    with _sentry_warning_lock:
        if _sentry_send_error_emitted:
            return
        debug_enabled = os.environ.get("SENTRY_DEBUG", "").lower() in ("true", "1", "yes")
        detail = f": {str(e)[:_SENTRY_DEBUG_DETAIL_MAX_LEN]}" if debug_enabled else ""
        print(
            f"[SENTRY_ERROR] Failed to send to Sentry: {type(e).__name__}{detail}",
            file=sys.stderr,
        )
        _sentry_send_error_emitted = True


def _emit_sentry_bug_error(e: Exception) -> None:
    """Sentry内部バグの stderr 警告を per-process 1 回に throttle 出力

    SDK API 不整合等のバグを通常の Sentry 送信失敗 [SENTRY_ERROR] と区別し、
    SENTRY_DEBUG ガード + str(e)[:100] 制限で内部状態の log aggregation への漏洩を防止する
    (CWE-532 対策、_emit_sentry_send_error と同等の防御)。
    """
    global _sentry_bug_emitted
    with _sentry_warning_lock:
        if _sentry_bug_emitted:
            return
        debug_enabled = os.environ.get("SENTRY_DEBUG", "").lower() in ("true", "1", "yes")
        detail = f": {str(e)[:_SENTRY_DEBUG_DETAIL_MAX_LEN]}" if debug_enabled else ""
        print(
            f"[SENTRY_BUG] internal error in _sentry_processor: {type(e).__name__}{detail}"
            "; further [SENTRY_BUG] warnings suppressed until process restart",
            file=sys.stderr,
        )
        _sentry_bug_emitted = True


def _emit_outside_except_warning() -> None:
    """logger.exception() を except ブロック外で呼んだ場合の per-process 1 回警告"""
    global _sentry_outside_except_warning_emitted
    with _sentry_warning_lock:
        if _sentry_outside_except_warning_emitted:
            return
        print(
            "[SENTRY_WARN] logger.exception() called outside except block,"
            " falling back to capture_message",
            file=sys.stderr,
        )
        _sentry_outside_except_warning_emitted = True


def _safe_error_summary(e: Exception) -> str:
    """例外を安全にサマリ化 (情報漏洩防止)

    Pydantic ValidationError の場合は errors(include_input=False) で input 値を除外し
    エラー件数のみ返す。それ以外は型名のみ返す (str(e) は呼び出さない)。
    """
    errors_fn = getattr(e, "errors", None)
    if callable(errors_fn):
        try:
            errs = list(errors_fn(include_input=False))
            return f"{len(errs)} validation error(s)"
        except MemoryError, RecursionError:
            raise
        except Exception:  # noqa: BLE001, S110
            # errors() 呼出失敗 (Pydantic v3 互換性等) も無視し型名のみ返す
            pass
    return f"{type(e).__name__} (details sanitized)"


def _emit_import_error_warnings() -> None:
    """sentry-sdk 未インストール時の stderr 警告を throttle 付きで出力

    設計方針: sentry_init.py は startup 時 Fail-Fast (RuntimeError)、
    logger.py は per-log-call coupling 回避のため警告出力で graceful degrade
    （本番デプロイ時の未インストール検知可能性を保証）。
    defensive: get_settings() が reload_settings() 後に ValidationError を
    発生させる可能性を遮断し log processor 内で例外伝播を防ぐ。

    TOCTOU 防止: lock 内で get_settings() を含む全処理を atomic 化する。

    ⚠️ コントラクト (将来変更時注意): config/settings.py は内部で lock を取得しない
    前提を維持する必要がある。settings.py に lock が追加されると _sentry_warning_lock
    との取得順序により循環待ちが発生し本関数でデッドロックが起こる。settings.py を
    変更する際はこの依存関係を確認し、lock 追加時は本関数の lock スコープから
    get_settings() を外に出すリファクタリングが必要となる。
    """
    global _sentry_settings_warning_emitted, _sentry_sdk_warning_emitted
    with _sentry_warning_lock:
        # 早期リターン: sdk 警告が既出なら後続処理不要
        # (settings 成功 × is_prod=True の正規ルートでは settings フラグは昇格しないため
        #  旧実装の「両フラグ AND」条件は機能しなかった。sdk フラグのみで判定する)
        if _sentry_sdk_warning_emitted:
            return
        try:
            is_prod = get_settings().is_production_like()
        # 設計意図: get_settings() は reload_settings()/ValidationError/AttributeError 等
        # 複数種の失敗モードを持ち、全て「本番環境不明」として安全側フォールバック扱いとする。
        # BLE001 はプロセッサ内で例外を再送出しない (log processor の循環失敗回避) ため許容。
        except Exception as e:  # noqa: BLE001
            is_prod = True  # 本番可能性を排除できないため安全側フォールバック
            if not _sentry_settings_warning_emitted:
                # Pydantic ValidationError は str(e) に input_value を平文含むため
                # 非SecretStr 設定値 (例: API__BASE_URL) が log aggregation に漏洩する。
                # _safe_error_summary() で input 除外した summary を生成する。
                detail = _safe_error_summary(e)
                print(
                    f"[SENTRY_WARN] settings load failed: {type(e).__name__}: {detail}",
                    file=sys.stderr,
                )
                _sentry_settings_warning_emitted = True
        # 警告出力有無に関わらず処理済みマークを立てる。
        # 早期リターン (line 78) を後続呼び出しで発火させ get_settings() 再評価を回避する。
        # 非prod + SENTRY_DEBUG 未設定 path で flag 昇格漏れ → 毎回 lock取得 + get_settings()
        # 呼び出しが発生する logic gap を解消する (設計コメント line 76-77 整合)。
        _sentry_sdk_warning_emitted = True
        if is_prod or os.environ.get("SENTRY_DEBUG", "").lower() in ("true", "1", "yes"):
            print(
                "[SENTRY_WARN] sentry-sdk not installed, skipping Sentry capture",
                file=sys.stderr,
            )


def _sentry_processor(  # noqa: C901
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
            if exc_info is True:
                # except ブロック外では sys.exc_info()[1] が None → capture_exception(None) は
                # 空イベントになるため capture_message へフォールバックしメッセージを保持する。
                if sys.exc_info()[1] is not None:
                    scope.capture_exception(None)
                else:
                    _emit_outside_except_warning()
                    scope.capture_message(
                        message,
                        level=_SENTRY_LEVEL_MAP.get(log_level.lower(), "error"),
                    )
            elif exc_info:
                scope.capture_exception(exc_info)
            else:
                scope.capture_message(
                    message,
                    level=_SENTRY_LEVEL_MAP.get(log_level.lower(), "error"),
                )

    except ImportError:
        try:
            _emit_import_error_warnings()
        except MemoryError, RecursionError:
            # システム例外は再発生させ OOMKilled / 無限再帰検知を妨げない
            raise
        except Exception as warn_err:  # noqa: BLE001
            print(
                f"[SENTRY_WARN] Failed to emit import warning: {type(warn_err).__name__}",
                file=sys.stderr,
            )
    except KeyboardInterrupt, SystemExit, MemoryError, RecursionError:
        # システム例外は再発生（graceful shutdown/K8s OOMKilled検知対応）
        raise
    except (AttributeError, TypeError) as e:
        # logger 内部または Sentry SDK API 不整合のバグ可能性 — 通常 [SENTRY_ERROR] とは区別
        _emit_sentry_bug_error(e)
    except Exception as e:  # noqa: BLE001
        # ネットワーク・SDK 一時障害等の運用エラー
        _emit_sentry_send_error(e)

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
