"""Shared API client exceptions and fatal-exception policy."""

import asyncio

import httpx

# 同期文脈の fatal 例外。asyncio のタスクキャンセルを持たないため CancelledError を含まない。
SYNC_FATAL_EXCEPTIONS: tuple[type[BaseException], ...] = (
    KeyboardInterrupt,
    SystemExit,
    MemoryError,
    RecursionError,
)

# 非同期文脈の fatal 例外。SYNC に graceful-shutdown シグナルの CancelledError を加えたもの。
# httpx 例外（NetworkError, RemoteProtocolError 等）をここに追加してはならない。
# github_client.py の _request では except 句の順序で先行キャッチしており、
# この定数に httpx 例外を追加すると NetworkError のリトライが壊れる。
ASYNC_FATAL_EXCEPTIONS: tuple[type[BaseException], ...] = (
    *SYNC_FATAL_EXCEPTIONS,
    asyncio.CancelledError,
)


class APIClientError(Exception):
    """APIクライアント基底例外"""


class APIConnectionError(APIClientError):
    """API接続エラー"""


class APITimeoutError(APIClientError):
    """APIタイムアウトエラー"""


class APIHTTPError(APIClientError):
    """HTTPステータスエラー"""

    def __init__(self, message: str, status_code: int, response: httpx.Response | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class APIRetryError(APIClientError):
    """リトライ上限エラー"""


class APIJSONDecodeError(APIClientError):
    """JSONパース＋スキーマ検証エラー"""

    def __init__(self, message: str, response: httpx.Response | None = None):
        super().__init__(message)
        self.response = response
