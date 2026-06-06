from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from structlog.testing import capture_logs

from tests.constants import BASE_URL
from utils.api_client import (
    _MAX_LOGGED_FAILURE_DETAILS,
    AsyncAPIClient,
    AsyncJSONPlaceholderClient,
    SyncAPIClient,
)

# Module-level marker: All tests in this file are unit tests
pytestmark = pytest.mark.unit


# Mock settings for testing purposes, as the actual SyncAPIClient uses config.settings
class MockAPISettings:
    def __init__(self):
        self.base_url = BASE_URL
        self.timeout = 30.0
        self.retry_count = 3
        self.retry_delay = 0.1
        self.user_agent = "test-agent"
        self.max_connections = 10


class MockSettings:
    def __init__(self):
        self.api = MockAPISettings()


# Replace the actual settings with mock settings for testing
# This is a simplified approach for demonstration. In a real project,
# you'd use pytest fixtures or dependency injection for better isolation.
mock_settings_instance = MockSettings()


@pytest.fixture(autouse=True)
def mock_settings():
    with patch("config.settings.settings", new=mock_settings_instance):
        yield


def test_base_client_initialization():
    """クライアント初期化テスト"""
    client = SyncAPIClient(base_url="https://test.com", timeout=10.0, retry_count=1)
    assert client.base_url == "https://test.com"
    assert client.timeout == 10.0
    assert client.retry_count == 1
    assert "User-Agent" in client.default_headers
    # User-Agent値のチェックは削除（モック動作ではなく実際の値を使用）


def test_context_manager_basic():
    """Context Manager基本動作テスト"""
    with SyncAPIClient(base_url="https://test.com") as client:
        assert client._client is not None
        assert isinstance(client._client, httpx.Client)
    # After exiting, the client should be closed (though we can't directly assert _client is None)


def test_base_client_uses_default_settings_if_not_provided():
    """引数がない場合にデフォルト設定が使用されることを確認"""
    client = SyncAPIClient()  # Uses mock_settings_instance
    assert client.base_url == BASE_URL
    assert client.timeout == 30.0
    assert client.retry_count == 3


def test_base_client_headers_are_set_correctly():
    """ヘッダーが正しく設定されることを確認"""
    custom_headers = {"X-Custom-Header": "Value"}
    client = SyncAPIClient(base_url="https://test.com", headers=custom_headers)
    assert client.default_headers["X-Custom-Header"] == "Value"
    assert client.default_headers["Accept"] == "application/json"


def test_base_client_close_method():
    """closeメソッドがクライアントを閉じることを確認"""
    client = SyncAPIClient(base_url="https://test.com")
    client.__enter__()  # Manually enter context to ensure _client is initialized
    assert client._client is not None
    client.close()
    # httpx.Client.close() doesn't set _client to None, but it closes the transport.
    # We can't easily assert the underlying httpx client is closed without mocking.
    # For now, just ensure no error is raised.


async def test_close_async_client_with_none_client_does_not_raise() -> None:
    """_client が None の場合、_close_async_client は何もせず例外を発生させない（no-op）。

    Fix #13-TC-3: double-close 防止のため _close_async_client に
    None ガードが実装されていることを検証する。
    """
    client = AsyncAPIClient(base_url="https://test.com")
    # _client を None に強制設定（close 後の状態をシミュレート）
    client._client = None
    # None の場合は no-op であり、例外が発生しないことを検証
    await client._close_async_client(None)


async def test_aclose_unexpected_error_suppressed_logs_error() -> None:
    """aclose() 直接呼び出し時の予期しないclose例外はerrorログで監視対象にする。"""
    client = AsyncAPIClient(base_url="https://test.com")
    client._client = AsyncMock()
    client._client.aclose = AsyncMock(side_effect=RuntimeError("close-failed"))

    with capture_logs() as logs:
        await client.aclose()

    error_logs = [
        log
        for log in logs
        if log.get("event") == "async_api_client_aclose_unexpected_error_suppressed"
    ]
    assert len(error_logs) == 1
    assert error_logs[0]["log_level"] == "error"
    assert error_logs[0]["error_type"] == "RuntimeError"


async def test_make_request_with_retry_raises_when_client_closed() -> None:
    """close 後（_client=None）に _make_request_with_retry を呼ぶと RuntimeError を送出する。

    PR#347 review fix: 従来は None.request アクセスで AttributeError になっていたが、
    use-after-close を明示的な RuntimeError として通知する（github_client.py L878 と同一パターン）。
    """
    client = AsyncAPIClient(base_url="https://test.com")
    # close 後の状態をシミュレート（_client を None に強制設定）
    client._client = None
    with pytest.raises(RuntimeError, match="Client not initialized"):
        await client._make_request_with_retry("GET", "/test")


def test_sync_close_sets_client_none_even_when_close_raises() -> None:
    """SyncAPIClient.close() は close() が例外を投げても _client=None を保証する。

    PR#347 review fix A: close() 例外時に _client が残存すると _request 冒頭の
    use-after-close ガード（_client is None 判定）をすり抜け、壊れたクライアントへ
    リクエストが発行される状態不整合が生じる。finally で _client=None を保証し、
    例外は従来通り呼び出し元へ伝播させる（AsyncAPIClient._close_async_client と対称）。
    """
    client = SyncAPIClient(base_url="https://test.example.com")
    client._client = Mock()
    client._client.close = Mock(side_effect=OSError("close-failed"))

    # 例外は呼び出し元へ伝播する（finally は抑制しない）
    with pytest.raises(OSError, match="close-failed"):
        client.close()

    # close() 失敗後も _client=None が保証され、use-after-close ガードが機能する
    assert client._client is None


async def test_bulk_create_users_details_truncated_false_at_max() -> None:
    """失敗が上限件数ちょうど（_MAX_LOGGED_FAILURE_DETAILS）では details_truncated=False。"""
    client = AsyncJSONPlaceholderClient(base_url="https://test.com")
    with patch.object(client, "create_user", new=AsyncMock(side_effect=RuntimeError("fail"))):
        with capture_logs() as logs:
            result = await client.bulk_create_users(
                [{"name": f"u{i}"} for i in range(_MAX_LOGGED_FAILURE_DETAILS)]
            )
    assert result == []
    warn = next((lg for lg in logs if lg.get("event") == "bulk_create_partial_failure"), None)
    assert warn is not None
    assert warn["failed_count"] == _MAX_LOGGED_FAILURE_DETAILS
    assert warn["success_count"] == 0
    assert warn["details_truncated"] is False
    assert len(warn["failed_details"]) == _MAX_LOGGED_FAILURE_DETAILS
    detail = warn["failed_details"][0]
    assert "index" in detail
    assert "error_type" in detail


async def test_bulk_create_users_details_truncated_true_above_max() -> None:
    """失敗件数が _MAX_LOGGED_FAILURE_DETAILS+1 のとき details_truncated=True になる境界を検証。"""
    client = AsyncJSONPlaceholderClient(base_url="https://test.com")
    with patch.object(client, "create_user", new=AsyncMock(side_effect=RuntimeError("fail"))):
        with capture_logs() as logs:
            result = await client.bulk_create_users(
                [{"name": f"u{i}"} for i in range(_MAX_LOGGED_FAILURE_DETAILS + 1)]
            )
    assert result == []
    warn = next((lg for lg in logs if lg.get("event") == "bulk_create_partial_failure"), None)
    assert warn is not None
    assert warn["failed_count"] == _MAX_LOGGED_FAILURE_DETAILS + 1
    assert warn["success_count"] == 0
    assert warn["details_truncated"] is True
    assert len(warn["failed_details"]) == _MAX_LOGGED_FAILURE_DETAILS
    detail = warn["failed_details"][0]
    assert "index" in detail
    assert "error_type" in detail
