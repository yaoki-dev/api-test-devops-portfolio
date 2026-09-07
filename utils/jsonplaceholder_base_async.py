"""JSONPlaceholder 非同期HTTP基底クライアント"""

import asyncio
from types import TracebackType
from typing import Any, Self

import httpx

from config.settings import settings
from utils.exceptions import APIClientError, APIHTTPError, APIRetryError
from utils.http_helpers import (
    classify_error,
    log_error_with_stderr_fallback,
    resolve_client_config,
    resolve_retry_policy,
    retry_suppression_suffix,
)
from utils.logger import get_logger
from utils.retry import exponential_backoff_with_jitter


class AsyncAPIClient:
    _client: httpx.AsyncClient | None  # aclose() 後に None を代入するため明示宣言

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        retry_count: int | None = None,
        retry_delay: float | None = None,
        headers: dict[str, str] | None = None,
    ):
        """Args:
        base_url: APIのベースURL（設定から自動取得可能）
        timeout: リクエストタイムアウト（秒）
        retry_count: リトライ回数
        retry_delay: リトライ間隔（秒）
        headers: 追加HTTPヘッダー

        Raises:
            ValueError: base_urlが空文字列またはホワイトスペース
                （スペース・タブ・改行等）のみの文字列の場合

        """
        # 設定解決・バリデーション（Sync/Async共通ロジック）
        # NOTE: retry_count=0, retry_delay=0.0, timeout=0.0 は有効な設定値のため is not None で判定
        # timeout=0.0: 即座にタイムアウト（無効化は timeout=None）
        (
            self.base_url,
            self.timeout,
            self.retry_count,
            self.retry_delay,
            self.default_headers,
        ) = resolve_client_config(base_url, timeout, retry_count, retry_delay, headers)

        # ロガーの初期化（structlog統合）
        self.logger = get_logger(__name__)

        # HTTPクライアントの初期化（非同期）
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self.default_headers,
            limits=httpx.Limits(max_connections=settings.api.max_connections),
        )

        self.logger.info("async_api_client_initialized", base_url=self.base_url)

    async def __aenter__(self) -> Self:
        """非同期コンテキストマネージャーのエントリー"""
        return self

    def _log_aclose_error_with_fallback(
        self, event: str, close_exc: BaseException, **fields: Any
    ) -> None:
        """aclose エラーを記録し、失敗時は stderr へフォールバック (PR#347 B-3 / Q-8)。

        モジュールレベル ``log_error_with_stderr_fallback`` への薄いラッパー。
        ``github_client`` とロジック (logger.error → 失敗時 stderr) を共有し、
        インライン重複による修正漏れを防ぐ (PR#347 Q-8 DRY)。
        """
        log_error_with_stderr_fallback(
            self.logger, "api_client", "aclose", close_exc, event, **fields
        )

    async def _close_async_client(
        self,
        body_exc_type: type[BaseException] | None,
        *,
        suppress_unexpected: bool = False,
    ) -> None:
        """``__aexit__`` と ``aclose()`` で共有する close 処理.

        Args:
            body_exc_type: ``__aexit__`` 経路では context manager の body 内で発生した
                例外型を渡す (例外無しなら ``None``)。``aclose()`` 直接呼び出し経路では
                常に ``None`` を渡す。``aclose()`` 失敗時に予期しない close 例外
                (``Exception`` 派生) を捕捉した際、body 例外の上書き防止のため
                ``has_body_exception = body_exc_type is not None`` を判定材料として
                利用する。``None`` の場合のみ実装バグとして bare ``raise`` で再送出する。
            suppress_unexpected: ``True`` の場合、予期しない close 例外を error ログ
                のみ記録して握りつぶす (re-raise しない)。``aclose()`` 直接呼び出し経路
                で ``True`` を渡すことで finally ブロック等での安全な呼び出しを保証する。
                ``__aexit__`` 経路では ``False`` (デフォルト) のまま ``has_body_exception``
                ロジックによる従来の re-raise 判定を維持する。
        """
        if self._client is not None:
            try:
                await self._client.aclose()
            except (httpx.CloseError, OSError) as close_exc:
                # 既知のクローズ時例外 — 警告のみ（body 例外を上書きしない）
                self._client = None
                self.logger.warning(
                    "async_api_client_aclose_failed",
                    error_type=type(close_exc).__name__,
                    error_module=type(close_exc).__module__,
                )
            except (MemoryError, RecursionError):  # fmt: skip
                # MemoryError/RecursionError も Exception 派生のため、再raise しないと
                # 下流の except Exception に捕捉されサイレント隠蔽される
                # （github_client / sentry_init と同一方針）。
                # 致命的エラーとして必ず再raise（fail-fast）。
                # ASYNC_FATAL_EXCEPTIONS は流用しない（close 文脈で asyncio.CancelledError
                # は捕捉対象外＝BaseException 直系で素通りさせるのが正しいため）。
                raise
            except Exception as close_exc:  # noqa: BLE001
                # 予期しない例外（AttributeError, RuntimeError, ValueError, TypeError 等の
                # 実装バグ可能性）を捕捉。以下は本句より先に処理済み / 境界外:
                #   - RecursionError / MemoryError: 上の専用句で先取り捕捉し
                #     即時 re-raise（fail-fast）。
                #   - KeyboardInterrupt / SystemExit / asyncio.CancelledError は
                #     BaseException 直系で `except Exception` の境界外。
                #     ユーザー停止/プロセス終了/cancellation を妨げない。
                has_body_exception = body_exc_type is not None
                if suppress_unexpected:
                    # aclose() 直接呼び出し経路: finally ブロック等での安全な呼び出しを保証するため
                    # 予期しない例外を握りつぶし、error ログで本番監視対象にする。
                    # suppress_unexpected=True は has_body_exception より優先して評価する。
                    # suppress 経路でも状態一貫性のため None セット。
                    # aclose 失敗後の壊れたクライアント再利用を防止
                    # （github_client __aexit__ L356 / 成功時 else 節と同一方針）。
                    self._client = None
                    self._log_aclose_error_with_fallback(
                        "async_api_client_aclose_unexpected_error_suppressed",
                        close_exc,
                        error_type=type(close_exc).__name__,
                        error_module=type(close_exc).__module__,
                        exc_info=True,  # スタックトレースをログに残す
                    )
                else:
                    # __aexit__ 経路（context manager）: 従来の has_body_exception ロジックを維持。
                    # PR#347 review SF-2: close_exc が body 例外を上書きしないため
                    # __context__ チェーンは切断される。代わりに body 例外の型名を
                    # 同一ログイベント内に記録し、close 失敗と body 例外の対応関係を
                    # 追跡可能にする (PII 非含: __qualname__ はクラス名のみ)。
                    self._log_aclose_error_with_fallback(
                        "async_api_client_aclose_unexpected_error",
                        close_exc,
                        error_type=type(close_exc).__name__,
                        error_module=type(close_exc).__module__,
                        has_body_exception=has_body_exception,
                        action=(
                            "suppressed_due_to_body_exception"
                            if has_body_exception
                            else "re_raised"
                        ),
                        body_exception_type=(
                            body_exc_type.__qualname__ if body_exc_type is not None else None
                        ),
                        exc_info=True,  # スタックトレースをログに残す
                    )
                    # body 例外がない場合のみ実装バグとして re-raise。
                    # body 例外がある場合は本質的原因の上書きを防ぐため raise しない。
                    # bare ``raise`` で active exception の traceback を完全保持
                    # （``raise close_exc`` への回帰防止: 余分な frame を追加せず Python idiom）。
                    if not has_body_exception:
                        raise
            else:
                # aclose() 成功時のみ closed ログを出す。logger.info を try 内に置くと
                # logger 自体の例外が aclose 失敗として誤検知されるため else 節に分離。
                # github_client.py / Sync close() と同一パターン (PR#347 Q-1 Codex fix)。
                self._client = None  # double-close 防止（_client 型は | None 宣言済み）
                self.logger.info("async_api_client_closed")

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """非同期コンテキストマネージャーの終了処理"""
        await self._close_async_client(exc_type)

    async def aclose(self) -> None:
        """クライアントのクローズ

        async with パターンと aclose() 単独呼び出しの両経路で
        ``async_api_client_closed`` ログを出力し、Sync (``SyncAPIClient.close()``)
        との observability 対称性を保つ (PR#347 review Q-1)。

        Note: 直接呼び出し時 (async context manager 経由でない場合)、予期しない close 例外は
        error ログ記録の上で抑制される (re-raise しない)。これにより finally ブロックでの
        安全な呼び出しを保証し、アプリクラッシュリスクを回避する。
        async with 経由では body 例外保護ロジック (has_body_exception) が適用され、
        body 例外がない場合のみ close 例外を re-raise する従来の挙動を維持する。
        """
        await self._close_async_client(None, suppress_unexpected=True)

    async def _make_request_with_retry(
        self,
        method: str,
        endpoint: str,
        *,
        retry_non_idempotent: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        """リトライ機能付き非同期HTTPリクエスト実行

        Args:
            method: HTTPメソッド
            endpoint: APIエンドポイント
            retry_non_idempotent: 非冪等メソッドの再送を明示的に許可するか
            **kwargs: httpxに渡す追加パラメータ

        Returns:
            httpx.Response: APIレスポンス

        Raises:
            APIConnectionError: 接続エラー
            APITimeoutError: タイムアウトエラー
            APIHTTPError: HTTPステータスエラー
            APIRetryError: リトライ上限エラー
            APIClientError: 非リトライエラー（TooManyRedirects / InvalidURL）

        Note:
            - TooManyRedirects/InvalidURL は map_request_error() 内で即 raise されるため、
            APIRetryError ではなく APIClientError として呼び出し元に届く。
            呼び出し元は APIClientError で捕捉すること。

            - 5xx / ネットワークエラーは、冪等メソッドでは設定回数までリトライする。
            POST/PATCH/PUT 等の非冪等メソッドは既定で 1 回だけ実行し、サーバー側の
            重複排除契約がある場合に限り ``retry_non_idempotent=True`` で再送を許可する。

        """
        # close 後の use-after-close を明示エラー化（github_client.py L878 と同一パターン）。
        # 型注釈 _client: AsyncClient | None に対する None 絞り込みも兼ねる。
        if self._client is None:
            raise RuntimeError("Client not initialized. Use 'async with' context.")

        retry_policy = resolve_retry_policy(
            method,
            self.retry_count,
            retry_non_idempotent=retry_non_idempotent,
        )
        last_exception: APIClientError | None = None

        for attempt in range(retry_policy.max_attempts):
            # 非同期HTTPリクエスト実行（ネットワーク層）
            try:
                # structlogでログ出力（DRY原則: 重複ログ削除）
                if attempt > 0:
                    self.logger.warning(
                        "async_request_retry",
                        attempt=attempt + 1,
                        max_attempts=retry_policy.max_attempts,
                        method=method,
                        endpoint=endpoint,
                    )
                else:
                    self.logger.debug("async_request_start", method=method, endpoint=endpoint)

                # 非同期HTTPリクエスト実行
                response = await self._client.request(method, endpoint, **kwargs)
            except (httpx.RequestError, httpx.InvalidURL) as e:
                # 全ネットワーク層エラーをキャッチ（TimeoutException, ConnectError, etc.）
                # TooManyRedirects/InvalidURL は classify_error → map_request_error 内で即 raise
                last_exception = classify_error(
                    e,
                    self.logger,
                    is_async=True,
                    method=method,
                    endpoint=endpoint,
                )
            else:
                # ネットワーク成功時のみHTTPステータス処理
                try:
                    response.raise_for_status()
                    self.logger.debug(
                        "async_request_success",
                        method=method,
                        endpoint=endpoint,
                        status_code=response.status_code,
                    )
                    return response
                except httpx.HTTPStatusError as e:
                    # 4xxエラーはリトライしない（クライアントエラー）
                    if e.response.is_client_error:
                        self.logger.error(
                            "client_error",
                            status_code=e.response.status_code,
                            method=method,
                            endpoint=endpoint,
                        )
                        raise APIHTTPError(
                            f"HTTP {e.response.status_code} Client Error",
                            e.response.status_code,
                            e.response,
                        ) from e

                    # 5xxエラーはリトライ対象
                    self.logger.warning(
                        "server_error",
                        status_code=e.response.status_code,
                        method=method,
                        endpoint=endpoint,
                    )
                    last_exception = APIHTTPError(
                        f"HTTP {e.response.status_code} Server Error",
                        e.response.status_code,
                        e.response,
                    )

            # 最後の試行でなければ指数バックオフ + 30%ジッターで待機
            if attempt + 1 < retry_policy.max_attempts:
                delay = exponential_backoff_with_jitter(
                    attempt=attempt,
                    base_delay=self.retry_delay,
                    jitter_percent=0.3,
                )
                self.logger.debug(
                    "async_retry_backoff",
                    delay_seconds=round(delay, 2),
                    attempt=attempt + 1,
                    strategy="exponential_backoff_with_jitter",
                )
                await asyncio.sleep(delay)

        # すべてのリトライが失敗
        self.logger.error(
            "async_all_retries_failed",
            method=method,
            endpoint=endpoint,
            attempts=retry_policy.max_attempts,
            suppressed_reason=retry_policy.suppressed_reason,
        )
        message = (
            f"Async request failed after {retry_policy.max_attempts} attempts"
            f"{retry_suppression_suffix(retry_policy, method)}"
        )
        raise APIRetryError(
            message,
            attempts=retry_policy.max_attempts,
            suppressed_reason=retry_policy.suppressed_reason,
        ) from last_exception

    async def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """非同期GETリクエスト実行"""
        return await self._make_request_with_retry("GET", endpoint, params=params, headers=headers)

    async def post(
        self,
        endpoint: str,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        *,
        retry_non_idempotent: bool = False,
    ) -> httpx.Response:
        """非同期POSTリクエスト実行。

        ``retry_non_idempotent`` は、冪等キーまたはサーバー側の重複排除契約が
        ある場合だけ有効化する。
        """
        return await self._make_request_with_retry(
            "POST",
            endpoint,
            json=json,
            data=data,
            headers=headers,
            retry_non_idempotent=retry_non_idempotent,
        )

    async def put(
        self,
        endpoint: str,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        *,
        retry_non_idempotent: bool = False,
    ) -> httpx.Response:
        """非同期PUTリクエスト実行。

        ``retry_non_idempotent`` は、サーバー実装がPUTの冪等性を保証せず、
        かつ重複排除契約がある場合だけ有効化する。
        """
        return await self._make_request_with_retry(
            "PUT",
            endpoint,
            json=json,
            data=data,
            headers=headers,
            retry_non_idempotent=retry_non_idempotent,
        )

    async def delete(self, endpoint: str, headers: dict[str, str] | None = None) -> httpx.Response:
        """非同期DELETEリクエスト実行"""
        return await self._make_request_with_retry("DELETE", endpoint, headers=headers)

    async def patch(
        self,
        endpoint: str,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        *,
        retry_non_idempotent: bool = False,
    ) -> httpx.Response:
        """非同期PATCHリクエスト実行。

        ``retry_non_idempotent`` は、冪等キーまたはサーバー側の重複排除契約が
        ある場合だけ有効化する。
        """
        return await self._make_request_with_retry(
            "PATCH",
            endpoint,
            json=json,
            data=data,
            headers=headers,
            retry_non_idempotent=retry_non_idempotent,
        )
