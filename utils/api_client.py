"""Backward-compatible API client facade.

The concrete JSONPlaceholder clients live in focused flat modules.
This shim stays until W3 import cutover removes legacy ``utils.api_client`` imports.
"""

from config.settings import settings as settings
from utils.exceptions import ASYNC_FATAL_EXCEPTIONS
from utils.exceptions import APIClientError as APIClientError
from utils.exceptions import APIConnectionError as APIConnectionError
from utils.exceptions import APIHTTPError as APIHTTPError
from utils.exceptions import APIJSONDecodeError as APIJSONDecodeError
from utils.exceptions import APIRetryError as APIRetryError
from utils.exceptions import APITimeoutError as APITimeoutError
from utils.http_helpers import (
    classify_error,
    log_error_with_stderr_fallback,
    map_request_error,
    resolve_client_config,
    validate_optional_int,
)
from utils.jsonplaceholder_base_async import AsyncAPIClient
from utils.jsonplaceholder_base_sync import SyncAPIClient
from utils.jsonplaceholder_client_async import (
    MAX_LOGGED_FAILURE_DETAILS,
    AsyncJSONPlaceholderClient,
    UserDataDict,
)
from utils.jsonplaceholder_client_sync import SyncJSONPlaceholderClient, create_client
from utils.response_parsing import (
    parse_response_model,
    parse_response_model_list,
    safe_parse_json,
)
from utils.retry import exponential_backoff_with_jitter as exponential_backoff_with_jitter

SYNC_FATAL_EXCEPTIONS: tuple[type[BaseException], ...] = (
    KeyboardInterrupt,
    SystemExit,
    MemoryError,
    RecursionError,
)

# Backward-compatible aliases retained until W3 import cutover.
_MAX_LOGGED_FAILURE_DETAILS = MAX_LOGGED_FAILURE_DETAILS
_validate_optional_int = validate_optional_int
_safe_parse_json = safe_parse_json
_parse_response_model = parse_response_model
_parse_response_model_list = parse_response_model_list
_map_request_error = map_request_error
_resolve_client_config = resolve_client_config
_classify_error = classify_error
_log_error_with_stderr_fallback = log_error_with_stderr_fallback

__all__ = [
    "APIClientError",
    "APIConnectionError",
    "APITimeoutError",
    "APIHTTPError",
    "APIRetryError",
    "APIJSONDecodeError",
    "ASYNC_FATAL_EXCEPTIONS",
    "SYNC_FATAL_EXCEPTIONS",
    "SyncAPIClient",
    "AsyncAPIClient",
    "SyncJSONPlaceholderClient",
    "AsyncJSONPlaceholderClient",
    "UserDataDict",
    "MAX_LOGGED_FAILURE_DETAILS",
    "_MAX_LOGGED_FAILURE_DETAILS",
    "create_client",
    "validate_optional_int",
    "safe_parse_json",
    "parse_response_model",
    "parse_response_model_list",
    "map_request_error",
    "resolve_client_config",
    "classify_error",
    "log_error_with_stderr_fallback",
    "exponential_backoff_with_jitter",
    "main",
]


def main() -> None:
    """Run the legacy JSONPlaceholder demo."""
    print("=== JSONPlaceholder API Client Demo ===")

    with create_client() as client:
        print("\n1. 投稿一覧取得（5件）:")
        posts = client.get_posts(limit=5)
        for post in posts:
            print(f"  - Post {post.id}: {post.title[:50]}...")

        print("\n2. ユーザー情報取得（ID: 1）:")
        user = client.get_user(1)
        print(f"  - Name: {user.name}")
        print(f"  - Email: {user.email}")
        print(f"  - Company: {user.company.name}")

        print("\n3. TODO取得（完了済み、3件）:")
        todos = client.get_todos(completed=True, limit=3)
        for todo in todos:
            status = "✓" if todo.completed else "✗"
            print(f"  {status} User {todo.user_id}: {todo.title}")

        print("\n4. 新規投稿作成テスト:")
        new_post = client.create_post(
            title="Test Post from API Client",
            body="This is a test post created by our API client.",
            user_id=1,
        )
        print(f"  - Created post ID: {new_post.id}")

    print("\n=== Demo completed ===")
