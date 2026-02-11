"""
SyncAPIClient 基本機能テスト

Note:
    test_async_client.py と対称構造で設計。
    責務: 基本CRUD操作 + Edge Cases + DevOps

テストケース一覧（9件）:
    - Basic Operations (4件): GET, POST, PUT, DELETE
    - Edge Cases (4件): context_manager, empty_response, malformed_json, boundary
    - DevOps (1件): health_check
"""

import sys
from unittest.mock import Mock

import httpx
import pytest

from tests.conftest import create_mock_response
from utils.api_client import SyncAPIClient, SyncJSONPlaceholderClient

# =============================================================================
# Basic Operations (4件)
# =============================================================================


def test_sync_get_user(mock_httpx_sync_client: Mock) -> None:
    """GETリクエスト検証"""
    mock_response = create_mock_response(200, json_data={"id": 1, "name": "Test User"})
    mock_response.raise_for_status.return_value = None
    mock_httpx_sync_client.request.return_value = mock_response

    with SyncAPIClient() as client:
        client._client = mock_httpx_sync_client
        response = client.get("/users/1")

        assert response.status_code == 200
        assert response.json()["id"] == 1
        mock_httpx_sync_client.request.assert_called_once()


def test_sync_post_create_user(mock_httpx_sync_client: Mock) -> None:
    """POSTリクエスト検証"""
    mock_response = create_mock_response(
        201,
        json_data={"id": 101, "name": "New User", "email": "new@example.com"},
    )
    mock_response.raise_for_status.return_value = None
    mock_httpx_sync_client.request.return_value = mock_response

    with SyncAPIClient() as client:
        client._client = mock_httpx_sync_client
        response = client.post("/users", json={"name": "New User", "email": "new@example.com"})

        assert response.status_code == 201
        assert response.json()["id"] == 101


def test_sync_put_update_user(mock_httpx_sync_client: Mock) -> None:
    """PUTリクエスト検証"""
    mock_response = create_mock_response(200, json_data={"id": 1, "name": "Updated"})
    mock_response.raise_for_status.return_value = None
    mock_httpx_sync_client.request.return_value = mock_response

    with SyncAPIClient() as client:
        client._client = mock_httpx_sync_client
        response = client.put("/users/1", json={"name": "Updated"})

        assert response.status_code == 200
        assert response.json()["name"] == "Updated"


def test_sync_delete_user(mock_httpx_sync_client: Mock) -> None:
    """DELETEリクエスト検証（httpx.Response返却を検証）"""
    mock_response = create_mock_response(204, json_data={})
    mock_response.raise_for_status.return_value = None
    mock_httpx_sync_client.request.return_value = mock_response

    with SyncAPIClient() as client:
        client._client = mock_httpx_sync_client
        response = client.delete("/users/1")

        assert response.status_code == 204


# =============================================================================
# Edge Cases (4件)
# Note: 例外クラス階層テストは test_sync_client_error_handling.py に集約（SRP準拠）
# =============================================================================


def test_sync_context_manager_cleanup(mock_httpx_sync_client: Mock) -> None:
    """with文コンテキストマネージャーのクリーンアップ検証"""
    mock_httpx_sync_client.close = Mock()

    with SyncAPIClient() as client:
        client._client = mock_httpx_sync_client
        # コンテキスト内でクライアントが使用可能
        assert client._client is not None

    # with文を抜けた後、closeが呼ばれることを検証
    # Note: SyncAPIClient.__exit__でself._client.close()が呼ばれる
    mock_httpx_sync_client.close.assert_called_once()


def test_sync_empty_response_handling(mock_httpx_sync_client: Mock) -> None:
    """空レスポンス（{}）の安全処理検証"""
    mock_response = create_mock_response(200, json_data={})
    mock_response.raise_for_status.return_value = None
    mock_httpx_sync_client.request.return_value = mock_response

    with SyncAPIClient() as client:
        client._client = mock_httpx_sync_client
        response = client.get("/empty")

        assert response.json() == {}


def test_sync_malformed_json_handling(mock_httpx_sync_client: Mock) -> None:
    """不正JSON時の例外処理検証"""
    mock_response = create_mock_response(200, json_data={})
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_response.raise_for_status.return_value = None
    mock_httpx_sync_client.request.return_value = mock_response

    with SyncAPIClient() as client:
        client._client = mock_httpx_sync_client
        response = client.get("/malformed")

        with pytest.raises(ValueError, match="Invalid JSON"):
            response.json()


@pytest.mark.parametrize("user_id", [0, -1, sys.maxsize], ids=["zero", "negative", "max_int"])
def test_sync_boundary_user_id(mock_httpx_sync_client: Mock, user_id: int) -> None:
    """境界値テスト: user_id=0, -1, MAX_INT（parametrize化）"""
    mock_response = create_mock_response(200, json_data={"id": user_id})
    mock_response.raise_for_status.return_value = None
    mock_httpx_sync_client.request.return_value = mock_response

    with SyncAPIClient() as client:
        client._client = mock_httpx_sync_client
        response = client.get(f"/users/{user_id}")

        assert response.json()["id"] == user_id


# =============================================================================
# DevOps (1件)
# =============================================================================


def test_sync_health_check(mock_httpx_sync_client: Mock) -> None:
    """
    API ヘルスチェック機能のテスト（同期版）

    検証項目：
    - health_check()メソッドの動作
    - 正常時: True返却
    - エラー時: False返却（graceful degradation）

    学習ポイント:
    - Docker/Kubernetes readiness probe対応
    - Sync/Async両対応の統一インターフェース設計
    """
    # Test 1: 正常時 → True
    healthy_response = create_mock_response(200, json_data=[{"id": 1, "name": "User 1"}])
    healthy_response.raise_for_status.return_value = None
    mock_httpx_sync_client.request.return_value = healthy_response

    with SyncJSONPlaceholderClient() as client:
        client._client = mock_httpx_sync_client
        result = client.health_check()

        assert result is True

        # _limit=1パラメータで軽量クエリ確認
        call_args = mock_httpx_sync_client.request.call_args
        assert "params" in call_args[1]
        assert call_args[1]["params"]["_limit"] == 1

    # Test 2: ネットワークエラー時 → False（graceful degradation）
    # httpx.ConnectErrorを使用（httpx.RequestErrorのサブクラス）
    mock_httpx_sync_client.reset_mock()
    mock_httpx_sync_client.request.side_effect = httpx.ConnectError("Connection refused")

    with SyncJSONPlaceholderClient() as client:
        client._client = mock_httpx_sync_client
        result = client.health_check()

        assert result is False


# =============================================================================
# 学習ポイント:
#
# 1. Sync/Async対称構造:
#    - test_async_client.py と同一のテスト設計
#    - 責務分離（SRP）: 基本操作 vs エラーハンドリング
#
# 2. pytest.mark.parametrize:
#    - 境界値テストの効率的な実装
#    - ids引数でテスト名を明確化
#
# 3. Mock fixtureの活用:
#    - mock_httpx_sync_client: 同期クライアント用
#    - create_mock_response: レスポンスファクトリ
#
# =============================================================================
