"""Utilities module for API Test DevOps Portfolio.

Exports:
    SyncAPIClient: Base synchronous API client
    AsyncAPIClient: Asynchronous API client
    SyncJSONPlaceholderClient: JSONPlaceholder API client (sync)
    AsyncJSONPlaceholderClient: JSONPlaceholder API client (async)
    APIClientError: 共通API例外の基底クラス
    APIJSONDecodeError: JSON decode 失敗時の例外
"""

from .api_client import (
    APIClientError,
    APIJSONDecodeError,
    AsyncAPIClient,
    AsyncJSONPlaceholderClient,
    SyncAPIClient,
    SyncJSONPlaceholderClient,
)

__all__ = [
    "APIClientError",
    "APIJSONDecodeError",
    "AsyncAPIClient",
    "AsyncJSONPlaceholderClient",
    "SyncAPIClient",
    "SyncJSONPlaceholderClient",
]
