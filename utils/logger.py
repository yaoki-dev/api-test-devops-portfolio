"""structlogロガー取得モジュール

プロジェクト共通のstructlogロガーを提供。
config/settings.pyのLogConfigと連携して動作。
Sentry統合によりERROR以上のログを自動送信。

使用例:
    from utils.logger import get_logger

    logger = get_logger(__name__)
    logger.info("処理開始", user_id=123, action="login")

"""

from __future__ import annotations

import os
import sys
import threading
import time
from functools import lru_cache
from typing import Any, Literal, cast

import structlog
from structlog.typing import FilteringBoundLogger, WrappedLogger

from config.settings import LogFormat, get_settings

# _sentry_warning_lock: per-process 1 回抑制フラグ群の atomic check-and-set 用 lock。
# **重要制約**: lock 内はフラグ操作 (_sentry_warnings_emitted への add/in) と
# 純粋な文字列生成 (事前計算済み値の結合のみ) に限定すること。
# str(e) / _sentry_debug_detail(e) 等のユーザーコード呼び出しを lock 内に置くと、
# カスタム例外の __str__ が logging 経由で再帰的に lock 取得を試み
# threading.Lock (非再入) のデッドロックが発生する。詳細: _emit_permanent_warning docstring。
_sentry_warning_lock = threading.Lock()

# 4 つの permanent throttle 状態を 1 つの set に統合 (旧 4 bool flags の代替)。
# キー: "settings" / "sdk" / "bug" / "outside_except"
# 新フラグ追加時はキー文字列の追加のみで済む (`add` / `in` のみ)。
_sentry_warnings_emitted: set[str] = set()

# _sentry_send_error は permanent flag ではなく timestamp ベースで再警告を許可する
# (ネットワーク瞬断後の永続サイレント化を防止)。詳細は _emit_sentry_send_error 参照。
_sentry_send_error_last_warned: float = float("-inf")
_SENTRY_SEND_ERROR_WARN_INTERVAL: float = 300.0  # 5分

# event_dict から Sentry extra へ渡す際に除外する予約キー (frozenset で O(1) lookup)
_SENTRY_EXCLUDED_KEYS: frozenset[str] = frozenset(
    {"event", "level", "timestamp", "exc_info", "logger"}
)

# structlog の "EXCEPTION" レベルを Sentry SDK が受理するレベルへ正規化するマップ。
# structlog の "exception" は Sentry 側に存在しないため "error" へマップする。
_SENTRY_LEVEL_MAP: dict[str, Literal["error", "critical"]] = {
    "error": "error",
    "critical": "critical",
    "exception": "error",  # structlog "exception" → Sentry "error" へ正規化
}

# SENTRY_DEBUG 有効時に stderr へ出力する例外詳細の最大文字数 (CWE-532 対策)
_SENTRY_DEBUG_DETAIL_MAX_LEN: int = 100


@lru_cache(maxsize=1)
def _is_sentry_debug_enabled() -> bool:
    """SENTRY_DEBUG 環境変数が有効か判定

    結果はプロセスライフタイムでキャッシュされる (lru_cache)。
    SENTRY_DEBUG の変更を反映するにはプロセス再起動が必要。
    テストで動的に変更する場合は `_is_sentry_debug_enabled.cache_clear()` を呼ぶこと。
    """
    return os.environ.get("SENTRY_DEBUG", "").lower() in ("true", "1", "yes")


def _sentry_debug_detail(e: Exception) -> str:
    # CWE-532: str(e)[:100] でDSN/レスポンスボディ漏洩を防止
    if _is_sentry_debug_enabled():
        return f": {str(e)[:_SENTRY_DEBUG_DETAIL_MAX_LEN]}"
    return ""


def _emit_sentry_send_error(e: Exception) -> None:
    """Sentry送信失敗の stderr 警告を timestamp ベースで throttle 出力

    一時的なネットワーク瞬断 (デプロイ直後等) で永続的にサイレント化される問題を
    回避するため bool flag ではなく `_SENTRY_SEND_ERROR_WARN_INTERVAL` (5分) 経過後に
    再警告を許可する。DSN/HTTP レスポンスボディ漏洩防止のため SENTRY_DEBUG 有効時でも
    str(e) を 100 文字に切り詰める (CWE-532)。
    """
    global _sentry_send_error_last_warned
    now = time.monotonic()
    # str(e) を lock 外で評価: カスタム例外の __str__ が logging 経由で再帰的に
    # _sentry_warning_lock (非再入) を取得しようとした場合のデッドロックを防止する。
    detail = _sentry_debug_detail(e)
    message: str | None = None
    with _sentry_warning_lock:
        if now - _sentry_send_error_last_warned < _SENTRY_SEND_ERROR_WARN_INTERVAL:
            return
        _sentry_send_error_last_warned = now
        message = f"[SENTRY_ERROR] Failed to send to Sentry: {type(e).__name__}{detail}"
    print(message, file=sys.stderr)


def _emit_permanent_warning(key: str, message: str) -> None:
    """per-process 1 回限りの stderr 警告 (permanent throttle 共通実装)

    `_sentry_warnings_emitted` set への atomic な check-and-set を行い、既登録なら
    何もしない。print() は lock 解放後に実行しスタベーションを軽減する。

    `message` を eager string (str) として受け取ることで、lock 内はフラグ操作のみ
    に限定される。これにより `_sentry_debug_detail(e)` 等を含む文字列生成コードが
    lock 取得前に評価され、デッドロックリスクが型システムで構造的に排除される。
    """
    # 早期リターン (lock 外): set への要素追加は monotonic で戻らないため race-free。
    # ERROR ストーム時の lock 取得コスト積算を排除し、_emit_import_error_warnings の
    # 同等パターンと設計整合性を確保する。
    if key in _sentry_warnings_emitted:
        return
    with _sentry_warning_lock:
        if key in _sentry_warnings_emitted:
            return
        _sentry_warnings_emitted.add(key)
    print(message, file=sys.stderr)


def _emit_sentry_bug_error(e: Exception) -> None:
    """Sentry内部バグの stderr 警告を per-process 1 回に throttle 出力

    SDK API 不整合等のバグを通常の Sentry 送信失敗 [SENTRY_ERROR] と区別し、
    SENTRY_DEBUG ガード + str(e)[:100] 制限で内部状態の log aggregation への漏洩を防止する
    (CWE-532 対策、_emit_sentry_send_error と同等の防御)。
    """
    detail = _sentry_debug_detail(e)
    _emit_permanent_warning(
        "bug",
        f"[SENTRY_BUG] internal error in _sentry_processor: {type(e).__name__}{detail}"
        "; further [SENTRY_BUG] warnings suppressed until process restart",
    )


def _emit_outside_except_warning() -> None:
    """logger.exception() を except ブロック外で呼んだ場合の per-process 1 回警告"""
    _emit_permanent_warning(
        "outside_except",
        "[SENTRY_WARN] logger.exception() called outside except block,"
        " falling back to capture_message",
    )


def _safe_error_summary(e: BaseException) -> str:
    """例外を安全にサマリ化 (情報漏洩防止)

    Pydantic ValidationError の場合は errors(include_input=False) で input 値を除外し
    エラー件数のみ返す。それ以外は型名のみ返す (str(e) は呼び出さない)。

    errors() 呼出失敗時は SENTRY_DEBUG 有効時のみ stderr に型名のみ出力 (運用時の
    完全サイレント化を回避)。Pydantic v3 互換性デバッグの足がかりとして使用。

    引数型は `BaseException` を受理 (`Exception` のみならず `KeyboardInterrupt` 等
    システム例外も型システム上は安全に扱える設計とするため)。実際の呼び出し元では
    `except Exception` で捕捉した値のみ渡している。
    """
    errors_fn = getattr(e, "errors", None)
    if callable(errors_fn):
        try:
            errs = list(errors_fn(include_input=False))
            return f"{len(errs)} validation error(s)"
        except MemoryError, RecursionError:
            raise
        except Exception as summary_err:  # noqa: BLE001
            # errors() 呼出失敗 (Pydantic v3 互換性等) — DEBUG 時のみ型名を出力
            if _is_sentry_debug_enabled():
                print(
                    f"[SENTRY_WARN] _safe_error_summary failed: {type(summary_err).__name__}",
                    file=sys.stderr,
                )
    return f"{type(e).__name__} (details sanitized)"


def _emit_import_error_warnings() -> None:
    """sentry-sdk 未インストール時の stderr 警告を throttle 付きで出力

    設計方針: sentry_init.py は startup 時 Fail-Fast (RuntimeError)、
    logger.py は per-log-call coupling 回避のため警告出力で graceful degrade
    （本番デプロイ時の未インストール検知可能性を保証）。
    defensive: get_settings() が reload_settings() 後に ValidationError を
    発生させる可能性を遮断し log processor 内で例外伝播を防ぐ。

    実装方針 (deadlock-safe / starvation-safe):
      1. "sdk" マーカーの早期リターンは lock 外で実施 (set への add は monotonic
         なためダブル評価しても問題なし)
      2. `get_settings()` は lock 取得前に評価。これにより config/settings.py が将来
         独自 lock を導入しても循環待ちが発生しない構造を保証する
      3. `print()` は lock 解放後に実行。lock 内はフラグ操作とメッセージ生成のみ
    """
    # 早期リターン (lock 外): set への要素追加は monotonic で戻らないため race-free
    if "sdk" in _sentry_warnings_emitted:
        return

    # get_settings() を lock 外で評価 — settings.py 内で lock が追加された場合の
    # 循環デッドロックを構造的に排除する (TOCTOU は "sdk" マーカー昇格を per-process
    # 1 回に限定する monotonic 性で吸収)。
    settings_error: Exception | None = None
    try:
        is_prod = get_settings().is_production_like()
    except Exception as e:  # noqa: BLE001 — log processor 内で例外を再送出しない
        is_prod = True  # 本番可能性を排除できないため安全側フォールバック
        settings_error = e

    # _safe_error_summary() は SENTRY_DEBUG 有効時に内部で print() を実行する可能性が
    # あるため lock 外で評価する (他の _emit_* 関数の "lock 内はフラグ操作とメッセージ
    # 生成のみ" 設計方針への整合)。
    settings_detail: str | None = None
    if settings_error is not None:
        # Pydantic ValidationError は str(e) に input_value を平文含むため
        # 非SecretStr 設定値 (例: API__BASE_URL) が log aggregation に漏洩する。
        # _safe_error_summary() で input 除外した summary を生成する。
        settings_detail = _safe_error_summary(settings_error)

    settings_msg: str | None = None
    sdk_msg: str | None = None
    # gate: settings_msg / sdk_msg 双方を本番 or SENTRY_DEBUG 有効時のみ stderr 出力。
    # 設計一貫性: settings_detail は _safe_error_summary() 経由で input 値を除外済み
    # だが、開発環境で設定ロード失敗ログが無条件に流れる挙動は sdk_msg の throttle と
    # 非対称であり、ローカル開発時のノイズ源となるため同等のガードを掛ける。
    should_emit_warnings = is_prod or _is_sentry_debug_enabled()
    with _sentry_warning_lock:
        # 二重チェック: lock 取得待機中に他スレッドが昇格させた可能性を吸収
        if "sdk" in _sentry_warnings_emitted:
            return
        if (
            settings_error is not None
            and "settings" not in _sentry_warnings_emitted
            and should_emit_warnings
        ):
            settings_msg = (
                f"[SENTRY_WARN] settings load failed: "
                f"{type(settings_error).__name__}: {settings_detail}"
            )
            _sentry_warnings_emitted.add("settings")
        # 警告出力有無に関わらず処理済みマークを立てる。
        # 早期リターン経路を後続呼び出しで発火させ get_settings() 再評価を回避する
        # (非prod + SENTRY_DEBUG 未設定 path で flag 昇格漏れ → 毎回 lock取得 +
        # get_settings() 呼び出しが発生する logic gap を解消)。
        _sentry_warnings_emitted.add("sdk")
        if should_emit_warnings:
            sdk_msg = "[SENTRY_WARN] sentry-sdk not installed, skipping Sentry capture"

    if settings_msg is not None:
        print(settings_msg, file=sys.stderr)
    if sdk_msg is not None:
        print(sdk_msg, file=sys.stderr)


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
        logger: structlogラッパー（structlogプロセッサー規約による必須引数、本実装では未使用）
        method_name: ログメソッド名（structlogプロセッサー規約による必須引数、本実装では未使用）
        event_dict: ログイベント辞書

    Returns:
        変更なしのevent_dict（プロセッサーチェーン継続）

    """
    # ERROR以上のみ対象
    log_level = event_dict.get("level", "").upper()
    if log_level not in ("ERROR", "CRITICAL", "EXCEPTION"):
        return event_dict

    # _SENTRY_LEVEL_MAP は小文字キー前提のため一度だけ正規化し、後段の
    # capture_message(level=...) 呼び出し3箇所で再利用する (重複 .lower() 計算回避)。
    sentry_level: Literal["error", "critical"] = _SENTRY_LEVEL_MAP.get(log_level.lower(), "error")

    # sentry_sdk は sys.modules.get() で参照する (毎回の `import sentry_sdk` で
    # 発生する CPython の `_ModuleLock` 取得を回避し、ERROR ストーム時の
    # ロック競合を排除する)。テストの `patch.dict("sys.modules", {"sentry_sdk": ...})`
    # との互換性も確保される。
    sentry_sdk = sys.modules.get("sentry_sdk")
    if sentry_sdk is None:
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
        return event_dict

    try:
        # Sentry初期化済みかチェック（SDK 2.x API）
        client = sentry_sdk.get_client()
        if not client.is_active():
            return event_dict

        # イベント情報を取得
        message = event_dict.get("event", "Unknown error")
        exc_info = event_dict.get("exc_info")

        # exc_info=True の場合 sys.exc_info() を new_scope() 入場前に snapshot 取得し
        # TOCTOU を排除する (sys.exc_info() はスレッドローカルだが scope.set_extra() ループや
        # コンテキストスイッチで例外コンテキストがずれる可能性を防ぐ)。
        exc_snapshot: tuple[type[BaseException], BaseException, Any] | None = None
        if exc_info is True:
            current_exc = sys.exc_info()
            if current_exc[1] is not None:
                exc_snapshot = cast(
                    "tuple[type[BaseException], BaseException, Any]",
                    current_exc,
                )

        # 追加コンテキストをextraとして送信 (exc_info/message 両経路で付与)
        # frozenset で O(1) lookup
        extra = {k: v for k, v in event_dict.items() if k not in _SENTRY_EXCLUDED_KEYS}
        # new_scope() 内で capture_exception/capture_message 双方を実行し
        # structlog bind された追加コンテキスト (user_id, request_id 等) を Sentry event に付与
        with sentry_sdk.new_scope() as scope:
            # set_extra() は user-data の serialization 失敗で AttributeError/TypeError を
            # 投げる可能性があるため per-key で個別に try 保護し、SDK 内部バグと user-data
            # エラーを分離する。失敗キーは個別にスキップし他キーの送信を妨げない。
            for key, value in extra.items():
                try:
                    scope.set_extra(key, value)
                except AttributeError, TypeError:  # noqa: PERF203
                    # user-data serialization failure (e.g. broken __repr__ on Pydantic model)
                    # → 該当キーのみスキップし [SENTRY_BUG] には昇格させない
                    continue
            if exc_info is True:
                # except ブロック外では sys.exc_info()[1] が None → capture_exception 不可
                # snapshot 失敗時は capture_message へフォールバック。
                if exc_snapshot is not None:
                    scope.capture_exception(exc_snapshot)
                else:
                    _emit_outside_except_warning()
                    scope.capture_message(
                        message,
                        level=sentry_level,
                    )
            elif exc_info:
                # 不正な型 (structlog 契約逸脱: BaseException/tuple/True 以外) で
                # capture_exception が TypeError を raise → 外側 _emit_sentry_bug_error
                # の throttle 経路で永続silent化する failure mode を回避するため
                # type guard を入れて capture_message へフォールバックする。
                if isinstance(exc_info, (BaseException, tuple)):
                    scope.capture_exception(exc_info)
                else:
                    scope.capture_message(
                        message,
                        level=sentry_level,
                    )
            else:
                scope.capture_message(
                    message,
                    level=sentry_level,
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
