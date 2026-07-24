"""HTTP client shared helper functions."""

import sys
from typing import Any

import httpx
from structlog.typing import FilteringBoundLogger

from config.settings import settings
from utils.exceptions import APIClientError, APIConnectionError, APITimeoutError


def validate_optional_int(value: int | None, name: str, min_value: int) -> None:
    """オプショナルな整数パラメータの最小値バリデーション。

    Args:
        value: 検証対象の値（Noneの場合はスキップ）
        name: パラメータ名（エラーメッセージ用）
        min_value: 最小許容値（含む）

    Raises:
        ValueError: valueがmin_valueより小さい場合
    """
    if value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}")


def map_request_error(e: httpx.RequestError | httpx.InvalidURL) -> APIClientError:
    """httpxネットワーク例外をカスタム例外にマッピング

    Args:
        e: httpx.RequestError または httpx.InvalidURL（またはそのサブクラス）

    Returns:
        APIClientErrorサブクラス（リトライ可能エラーの場合のみ。
        非リトライ時（TooManyRedirects / InvalidURL）は
        APIClientError 基底クラスを raise するため返らない）。

    Raises:
        APIClientError: 非リトライ可能エラー（TooManyRedirects, InvalidURL）

    Note:
        httpx例外の扱い:
        - RequestError サブクラス（リトライ可能）:
          TimeoutException (ConnectTimeout, ReadTimeout),
          NetworkError (ConnectError, ReadError, WriteError 等のサブクラスを含む)
          ※ ConnectError は NetworkError のサブクラスだが個別分岐で処理
        - RequestError サブクラス（非リトライ）:
          TooManyRedirects → 即座にraise
        - 独立例外（RequestError のサブクラスではない、非リトライ）:
          InvalidURL → 即座にraise
        生成される例外メッセージは固定プレフィックスと ``type(e).__name__``
        （例外クラス名）のみで構成され、``str(e)`` は含めない。
        非リトライエラーは ``raise ... from e`` により即座にスローされる。
        リトライ可能エラーは ``__cause__ = e`` 手動設定後に返され、
        呼び出し元で ``raise`` された際にトレースバックで確認できる。
        なお、``__cause__`` に保持される httpx 例外の文字列には
        ホスト名・プロキシ設定等の機密情報が含まれることがあり、
        ``traceback.print_exception(chain=True)``（デフォルト）では
        この ``__cause__`` チェーンが展開されるため、表示用途では
        ``chain=False`` を指定して機密漏洩を防ぐこと。
        ``main()`` で受け取る ``e`` は ``APIClientError`` なので、
        ``chain=False`` が抑止するのは ``__cause__`` 側の httpx 例外チェーンであり、
        ``APIClientError`` 本体のスタックトレースは引き続き表示される。
        参照: ``main()`` の ``traceback.print_exception(e, chain=False)`` 実装。

    """
    # Non-retryable errors - raise immediately (no point in retrying)
    if isinstance(e, httpx.TooManyRedirects | httpx.InvalidURL):
        raise APIClientError(f"Non-retryable request error: {type(e).__name__}") from e

    # Retryable errors: returnするため `raise ... from e` は使えず __cause__ を手動設定する。
    # PEP 3134: exc.__cause__ = e を設定すると __suppress_context__ が自動で True になり、
    # 呼び出し元が raise した際に `raise exc from e` と同じ例外チェーン表示になる。
    if isinstance(e, httpx.TimeoutException):
        timeout_exc = APITimeoutError(f"Request timeout: {type(e).__name__}")
        timeout_exc.__cause__ = e
        return timeout_exc
    if isinstance(e, httpx.ConnectError):
        connect_exc = APIConnectionError(f"Connection failed: {type(e).__name__}")
        connect_exc.__cause__ = e
        return connect_exc
    # NetworkError, etc. - retryable network issues
    network_exc = APIConnectionError(f"Network error: {type(e).__name__}")
    network_exc.__cause__ = e
    return network_exc


def resolve_client_config(
    base_url: str | None,
    timeout: float | None,
    retry_count: int | None,
    retry_delay: float | None,
    headers: dict[str, str] | None,
) -> tuple[str, float, int, float, dict[str, str]]:
    """Sync/Async共通の設定解決ロジック。

    引数またはsettingsから設定値を解決し、バリデーションを実行する。
    HTTPクライアント初期化・ロガー初期化は呼び出し元の責務。

    Args:
        base_url: APIのベースURL（Noneの場合settings.api.base_urlを使用）
        timeout: タイムアウト秒数（Noneの場合settings.api.timeoutを使用）
        retry_count: リトライ回数（Noneの場合settings.api.retry_countを使用）
        retry_delay: リトライ間隔秒数（Noneの場合settings.api.retry_delayを使用）
        headers: 追加ヘッダー（デフォルトヘッダーにマージ）

    Returns:
        (base_url, timeout, retry_count, retry_delay, default_headers) のタプル

    Raises:
        ValueError: base_urlが空文字列またはホワイトスペース
            （str.strip() で除去される文字）のみの文字列の場合

    """
    active_settings = settings
    base_url = base_url if base_url is not None else active_settings.api.base_url
    if not base_url.strip():
        raise ValueError("base_url が空です。引数または API__BASE_URL 環境変数を確認してください。")
    timeout = timeout if timeout is not None else active_settings.api.timeout
    retry_count = retry_count if retry_count is not None else active_settings.api.retry_count
    retry_delay = retry_delay if retry_delay is not None else active_settings.api.retry_delay

    default_headers = {
        "User-Agent": active_settings.api.user_agent,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    # `if headers:` ではなく `is not None` を使用: 空辞書({})を渡した場合も
    # update()を実行する（no-opだが、Noneと空辞書の意味論を明確に区別するため）
    if headers is not None:
        default_headers.update(headers)

    return (
        base_url,
        timeout,
        retry_count,
        retry_delay,
        default_headers,
    )


def classify_error(
    e: httpx.RequestError | httpx.InvalidURL,
    logger: FilteringBoundLogger,
    *,
    is_async: bool,
    method: str,
    endpoint: str,
) -> APIClientError:
    """Sync/Async共通のネットワークエラー分類・ログ出力。

    エラー種別に応じてERROR/WARNINGログを出力し、map_request_error()を呼び出す。
    非リトライエラー(TooManyRedirects/InvalidURL)はmap_request_error()内で即座にraiseされる。

    Args:
        e: httpxのリクエストエラーまたはInvalidURL
        logger: structlogロガーインスタンス
        is_async: 非同期クライアントからの呼び出しかどうか
        method: HTTPメソッド名
        endpoint: APIエンドポイント

    Returns:
        APIClientErrorサブクラス（リトライ可能エラーの場合）。
        TooManyRedirects / InvalidURL の場合は map_request_error() 内で
        raise されるため、呼び出し元には値が返らない。

    Raises:
        APIClientError: TooManyRedirects または InvalidURL の場合
            （logger.error でログ出力後、map_request_error() を経由して raise される）。
            注: サブクラスではなく APIClientError 基底クラスが raise される。
            リトライ可能エラーは logger.warning でログ出力し、raise されない。

    Notes:
        本関数のログ出力（``request_error_non_retryable`` / ``request_error`` イベント）では
        ``error`` フィールドを省略している。httpx 例外の文字列には
        ホスト名、プロキシ設定等の機密情報が含まれるため、``error_type``
        （例外クラス名）のみ記録してエラー分類に必須情報を確保する。
        非リトライエラー（``request_error_non_retryable``）は ``logger.error``、
        リトライ可能エラー（``request_error``）は ``logger.warning`` でログ出力される。
        例外の生成・チェーン設定の詳細は ``map_request_error()`` 参照。

    """
    if isinstance(e, httpx.TooManyRedirects | httpx.InvalidURL):
        logger.error(
            "request_error_non_retryable",
            is_async=is_async,
            method=method,
            endpoint=endpoint,
            error_type=type(e).__name__,
        )
    else:
        logger.warning(
            "request_error",
            is_async=is_async,
            method=method,
            endpoint=endpoint,
            error_type=type(e).__name__,
        )
    return map_request_error(e)


def log_error_with_stderr_fallback(
    logger: FilteringBoundLogger,
    source: str,
    context: str,
    exc: BaseException,
    event: str,
    **fields: Any,
) -> None:
    """logger.error 記録 + 失敗時 stderr フォールバック (PR#347 B-3 / Q-8 DRY)。

    ``api_client`` / ``github_client`` の close・cache 失敗ログで共通する
    「``logger.error`` → 失敗時 ``stderr``」パターンをモジュールレベルに集約する。
    ``AsyncGitHubClient`` は ``AsyncAPIClient`` を継承しないため、メソッドではなく
    モジュール関数として共有する (PR#347 Q-8: インライン重複による修正漏れを防ぐ)。

    ロガー自体が致命例外 (``MemoryError`` / ``RecursionError``) を投げた場合は
    fail-fast で再 raise し、それ以外のロガー例外は握りつぶした ``exc`` の型名を
    ``stderr`` へ再露出させて監視可能性を保つ。

    Args:
        logger: structlog ロガー。
        source: stderr メッセージのソース識別子 (例 ``"api_client"``)。
        context: 失敗箇所の短い識別子 (例 ``"aclose"`` / ``"etag_cache"``)。
        exc: 既に握りつぶされている元例外 (型名のみ stderr 出力, PII 非含)。
        event: ``logger.error`` へ渡すイベント名。
        **fields: ``logger.error`` へ渡す構造化フィールド。

    Raises:
        MemoryError: ``logger`` が ``MemoryError`` を投げた場合に再 raise（fail-fast）。
        RecursionError: ``logger`` が ``RecursionError`` を投げた場合に再 raise（fail-fast）。
    """
    try:
        logger.error(event, **fields)
    except (MemoryError, RecursionError):  # fmt: skip
        # 致命例外は握りつぶさず再raise（fail-fast）。両者は Exception 派生のため、
        # 下の except Exception より先に明示的に先取りする
        # （sentry_scrub_primitives._safe_log_warning / _close_async_client と同一方針）。
        raise
    except Exception:  # noqa: BLE001
        # ロガー例外が握りつぶした exc を再露出させない保険。
        try:
            print(
                f"[{source}] {context} logger failed: {type(exc).__name__}",
                file=sys.stderr,
                flush=True,
            )
        except Exception:  # noqa: BLE001, S110
            pass
