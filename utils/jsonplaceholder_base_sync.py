"""Base synchronous JSONPlaceholder HTTP client."""

import time
from types import TracebackType
from typing import Any, Self

import httpx

from config.settings import settings
from utils.exceptions import APIClientError, APIHTTPError, APIRetryError
from utils.http_helpers import classify_error, resolve_client_config
from utils.logger import get_logger


def _legacy_backoff(*, attempt: int, base_delay: float, jitter_percent: float) -> float:
    """Route through api_client shim so W2a keeps legacy monkeypatch contracts."""
    from utils import api_client

    return api_client.exponential_backoff_with_jitter(
        attempt=attempt,
        base_delay=base_delay,
        jitter_percent=jitter_percent,
    )


class SyncAPIClient:
    """基本的な同期HTTPクライアント"""

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

        # HTTPクライアントの初期化
        # close() 後に None を代入するため Optional 宣言
        # （AsyncAPIClient._client と対称, PR#347 CQ-6）。
        self._client: httpx.Client | None = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self.default_headers,
            limits=httpx.Limits(max_connections=settings.api.max_connections),
        )

        self.logger.info("api_client_initialized", base_url=self.base_url)

    def __enter__(self) -> Self:
        """コンテキストマネージャーのエントリー"""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """コンテキストマネージャーの終了処理"""
        self.close()

    def close(self) -> None:
        """クライアントのクローズ

        ``AsyncAPIClient`` / ``AsyncGitHubClient.__aexit__`` と同様に、close 後は
        ``self._client = None`` を設定してダブルクローズを防止する（PR#347 CQ-6）。
        truthy チェックではなく ``is not None`` で他箇所の規約と統一する。

        ``self._client.close()`` が例外（``httpx.CloseError`` / ``OSError`` 等）を投げても、
        ``finally`` 節で ``self._client = None`` を必ず設定する。これにより ``_request`` 冒頭の
        use-after-close ガード（``_client is None`` 判定）の前提が保たれ、close 失敗後に壊れた
        クライアントへリクエストが発行される状態不整合を防ぐ。``AsyncAPIClient._close_async_client``
        が全 except 経路で ``_client=None`` を設定するのと対称（PR#347 review）。例外は従来通り
        呼び出し元へ伝播させる（``finally`` は抑制しない）。``api_client_closed`` info ログは
        close 成功時のみ出力する（``finally`` の外に置くため、例外時はスキップされる）。
        """
        if self._client is not None:
            try:
                self._client.close()
            finally:
                self._client = None
            self.logger.info("api_client_closed")

    def _make_request_with_retry(self, method: str, endpoint: str, **kwargs: Any) -> httpx.Response:
        """リトライ機能付きHTTPリクエスト実行

        Args:
            method: HTTPメソッド
            endpoint: APIエンドポイント
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
            TooManyRedirects/InvalidURL は _map_request_error() 内で即 raise されるため、
            APIRetryError ではなく APIClientError として呼び出し元に届く。
            呼び出し元は APIClientError で捕捉すること。

        """
        # close 後の use-after-close を明示エラー化（AsyncAPIClient._request と同一パターン）。
        # 型注釈 _client: httpx.Client | None に対する None 絞り込みも兼ねる（PR#347 CQ-6）。
        if self._client is None:
            raise RuntimeError("Client not initialized or already closed.")

        last_exception: APIClientError | None = None

        for attempt in range(self.retry_count + 1):
            # HTTPリクエスト実行（ネットワーク層）
            try:
                # structlogでログ出力（DRY原則: 重複ログ削除）
                if attempt > 0:
                    self.logger.warning(
                        "request_retry",
                        attempt=attempt + 1,
                        max_attempts=self.retry_count + 1,
                        method=method,
                        endpoint=endpoint,
                    )
                else:
                    self.logger.debug("request_start", method=method, endpoint=endpoint)

                # HTTPリクエスト実行
                response = self._client.request(method, endpoint, **kwargs)
            except (httpx.RequestError, httpx.InvalidURL) as e:
                # 全ネットワーク層エラーをキャッチ（TimeoutException, ConnectError, etc.）
                # TooManyRedirects/InvalidURL は classify_error → _map_request_error 内で即 raise
                last_exception = classify_error(
                    e,
                    self.logger,
                    is_async=False,
                    method=method,
                    endpoint=endpoint,
                )
            else:
                # ネットワーク成功時のみHTTPステータス処理
                try:
                    response.raise_for_status()
                    self.logger.debug(
                        "request_success",
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
            if attempt < self.retry_count:
                delay = _legacy_backoff(
                    attempt=attempt,
                    base_delay=self.retry_delay,
                    jitter_percent=0.3,
                )
                self.logger.debug(
                    "retry_backoff",
                    delay_seconds=round(delay, 2),
                    attempt=attempt + 1,
                    strategy="exponential_backoff_with_jitter",
                )
                time.sleep(delay)

        # すべてのリトライが失敗
        self.logger.error("all_retries_failed", method=method, endpoint=endpoint)
        raise APIRetryError(
            f"Request failed after {self.retry_count + 1} attempts",
        ) from last_exception

    def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """GETリクエスト実行"""
        return self._make_request_with_retry("GET", endpoint, params=params, headers=headers)

    def post(
        self,
        endpoint: str,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """POSTリクエスト実行"""
        return self._make_request_with_retry(
            "POST",
            endpoint,
            json=json,
            data=data,
            headers=headers,
        )

    def put(
        self,
        endpoint: str,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """PUTリクエスト実行"""
        return self._make_request_with_retry("PUT", endpoint, json=json, data=data, headers=headers)

    def delete(self, endpoint: str, headers: dict[str, str] | None = None) -> httpx.Response:
        """DELETEリクエスト実行"""
        return self._make_request_with_retry("DELETE", endpoint, headers=headers)

    def patch(
        self,
        endpoint: str,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """PATCHリクエスト実行"""
        return self._make_request_with_retry(
            "PATCH",
            endpoint,
            json=json,
            data=data,
            headers=headers,
        )
