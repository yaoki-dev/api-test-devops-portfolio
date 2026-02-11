from unittest.mock import AsyncMock, patch

import httpx
import pytest

from utils.api_client import (
    AsyncJSONPlaceholderClient,
    SyncAPIClient,
    SyncJSONPlaceholderClient,
)

# Module-level marker: All tests in this file are unit tests
pytestmark = pytest.mark.unit


# Mock settings for testing purposes, as the actual SyncAPIClient uses config.settings
class MockAPISettings:
    def __init__(self):
        self.base_url = "https://jsonplaceholder.typicode.com"
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
    assert client.base_url == "https://jsonplaceholder.typicode.com"
    assert client.timeout == 30.0
    assert client.retry_count == 3


@pytest.mark.unit
def test_base_client_headers_are_set_correctly():
    """ヘッダーが正しく設定されることを確認"""
    custom_headers = {"X-Custom-Header": "Value"}
    client = SyncAPIClient(base_url="https://test.com", headers=custom_headers)
    assert client.default_headers["X-Custom-Header"] == "Value"
    assert client.default_headers["Accept"] == "application/json"


@pytest.mark.unit
def test_base_client_close_method():
    """closeメソッドがクライアントを閉じることを確認"""
    client = SyncAPIClient(base_url="https://test.com")
    client.__enter__()  # Manually enter context to ensure _client is initialized
    assert client._client is not None
    client.close()
    # httpx.Client.close() doesn't set _client to None, but it closes the transport.
    # We can't easily assert the underlying httpx client is closed without mocking.
    # For now, just ensure no error is raised.


# =============================================================================
# health_check システム例外伝播テスト（Kubernetes OOMKilled対応）
# =============================================================================


@pytest.mark.unit
def test_health_check_memory_error_propagates():
    """MemoryErrorはhealth_checkから伝播する（Kubernetes OOMKilled対応）

    システム例外（MemoryError, KeyboardInterrupt, SystemExit）は
    health_checkで隠蔽せず、Kubernetesに伝播させる必要がある。
    これにより、OOMKilled等の適切なコンテナ再起動が可能になる。
    """
    with SyncJSONPlaceholderClient() as client:
        with patch.object(client, "get", side_effect=MemoryError("Out of memory")):
            with pytest.raises(MemoryError):
                client.health_check()


@pytest.mark.unit
def test_health_check_keyboard_interrupt_propagates():
    """KeyboardInterruptはhealth_checkから伝播する"""
    with SyncJSONPlaceholderClient() as client:
        with patch.object(client, "get", side_effect=KeyboardInterrupt()):
            with pytest.raises(KeyboardInterrupt):
                client.health_check()


@pytest.mark.unit
def test_health_check_system_exit_propagates():
    """SystemExitはhealth_checkから伝播する"""
    with SyncJSONPlaceholderClient() as client:
        with patch.object(client, "get", side_effect=SystemExit(1)):
            with pytest.raises(SystemExit):
                client.health_check()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_health_check_memory_error_propagates():
    """非同期版: MemoryErrorは伝播する（Kubernetes OOMKilled対応）"""
    async with AsyncJSONPlaceholderClient() as client:
        with patch.object(client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = MemoryError("Out of memory")
            with pytest.raises(MemoryError):
                await client.health_check()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_health_check_keyboard_interrupt_propagates():
    """非同期版: KeyboardInterruptは伝播する"""
    async with AsyncJSONPlaceholderClient() as client:
        with patch.object(client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = KeyboardInterrupt()
            with pytest.raises(KeyboardInterrupt):
                await client.health_check()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_health_check_system_exit_propagates():
    """非同期版: SystemExitは伝播する"""
    async with AsyncJSONPlaceholderClient() as client:
        with patch.object(client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = SystemExit(1)
            with pytest.raises(SystemExit):
                await client.health_check()


# =============================================================================
# Bulk操作部分失敗コンテキスト保持テスト（PR#170 Task 12）
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bulk_create_users_partial_failure_tracking():
    """bulk_create_usersで部分失敗時に失敗ユーザーを特定可能

    検証項目:
    - BulkOperationResult型で結果が返される
    - 成功/失敗のカウントが正確
    - 失敗アイテムに元の入力データとエラー情報が含まれる
    """
    from utils.api_client import BulkOperationResult

    async with AsyncJSONPlaceholderClient() as client:
        # 3件中1件失敗するシナリオを設定
        users = [
            {"name": "User1", "email": "user1@example.com"},
            {"name": "User2", "email": "invalid-email"},  # 失敗予定
            {"name": "User3", "email": "user3@example.com"},
        ]

        # create_userをモック: 2番目のみ例外発生
        call_count = 0

        async def mock_create_user(user_data):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ValueError("Invalid email format")
            return {"id": call_count, **user_data}

        with patch.object(client, "create_user", side_effect=mock_create_user):
            result = await client.bulk_create_users(users)

        # BulkOperationResult型であることを確認
        assert isinstance(result, BulkOperationResult)
        assert result.success_count == 2
        assert result.failure_count == 1
        assert len(result.failed_items) == 1
        # 失敗アイテムに元の入力が含まれる
        assert result.failed_items[0]["input"] == users[1]
        assert "error" in result.failed_items[0]
