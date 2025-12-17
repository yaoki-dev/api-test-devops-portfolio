"""
SyncAPIClient エラーハンドリングテスト

Note:
    test_async_client_error_handling.py と対称構造で設計。
    責務: リトライロジック + 例外ハンドリングの検証

テストケース一覧（7件）:
    - Exception (3件): hierarchy, http_error_status_preservation, retry_error_message
    - Retry (2件): exponential_backoff, 4xx_no_retry
    - Timeout (1件): timeout_error_retry
    - Connection (1件): connection_error_retry
"""

from unittest.mock import Mock

import httpx
import pytest

from tests.conftest import create_mock_response
from utils.api_client import (
    APIClientError,
    APIConnectionError,
    APIHTTPError,
    APIRetryError,
    APITimeoutError,
)
from utils.api_client import (
    BaseAPIClient as SyncAPIClient,  # エイリアス（Phase 1リネーム前）
)


class TestSyncClientExceptions:
    """カスタム例外クラスのテスト"""

    def test_sync_exception_hierarchy(self) -> None:
        """例外クラスの継承関係確認"""
        assert issubclass(APIConnectionError, APIClientError)
        assert issubclass(APITimeoutError, APIClientError)
        assert issubclass(APIHTTPError, APIClientError)
        assert issubclass(APIRetryError, APIClientError)
        assert issubclass(APIClientError, Exception)

    def test_sync_http_error_status_preservation(self) -> None:
        """APIHTTPError がステータスコードを保持することを確認"""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 404

        error = APIHTTPError("Not Found", status_code=404, response=mock_response)

        assert error.status_code == 404
        assert error.response == mock_response

    def test_sync_retry_error_message(self) -> None:
        """APIRetryError のメッセージ確認"""
        error = APIRetryError("Max retries exceeded")
        assert str(error) == "Max retries exceeded"


class TestSyncClientRetryLogic:
    """リトライロジックのテスト"""

    def test_sync_retry_with_exponential_backoff(self, mock_httpx_sync_client: Mock) -> None:
        """サーバーエラー後に成功するケース（5xxはリトライ対象）"""
        error_response = create_mock_response(500)
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=Mock(spec=httpx.Request),
            response=error_response,
        )

        success_response = create_mock_response(200, json_data={"id": 1})
        success_response.raise_for_status.return_value = None

        mock_httpx_sync_client.request.side_effect = [
            error_response,
            error_response,
            success_response,
        ]

        with SyncAPIClient(retry_count=3, retry_delay=0.01) as client:
            client._client = mock_httpx_sync_client
            response = client.get("/posts/1")

            assert mock_httpx_sync_client.request.call_count == 3
            assert response.status_code == 200

    def test_sync_4xx_error_no_retry(self, mock_httpx_sync_client: Mock) -> None:
        """4xxクライアントエラーはリトライせず即座にAPIHTTPErrorを発生"""
        error_response = create_mock_response(404)
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found",
            request=Mock(spec=httpx.Request),
            response=error_response,
        )

        mock_httpx_sync_client.request.return_value = error_response

        with SyncAPIClient(retry_count=3) as client:
            client._client = mock_httpx_sync_client

            with pytest.raises(APIHTTPError) as exc_info:
                client.get("/posts/999")

            # 4xxエラーはリトライしない（1回のみ実行）
            assert mock_httpx_sync_client.request.call_count == 1
            assert exc_info.value.status_code == 404


class TestSyncClientTimeoutHandling:
    """タイムアウトエラーのテスト"""

    def test_sync_timeout_error_retry(self, mock_httpx_sync_client: Mock) -> None:
        """タイムアウト時にAPIRetryErrorが発生することを確認"""
        mock_httpx_sync_client.request.side_effect = httpx.TimeoutException("Request timed out")

        with SyncAPIClient(retry_count=1, retry_delay=0.01) as client:
            client._client = mock_httpx_sync_client

            with pytest.raises(APIRetryError) as exc_info:
                client.get("/posts/1")

            # リトライが実行されることを確認
            assert mock_httpx_sync_client.request.call_count == 2
            assert isinstance(exc_info.value.__cause__, APITimeoutError)


class TestSyncClientConnectionHandling:
    """接続エラーのテスト"""

    def test_sync_connection_error_retry(self, mock_httpx_sync_client: Mock) -> None:
        """接続エラー時にAPIRetryErrorが発生することを確認"""
        mock_httpx_sync_client.request.side_effect = httpx.ConnectError("Connection refused")

        with SyncAPIClient(retry_count=1, retry_delay=0.01) as client:
            client._client = mock_httpx_sync_client

            with pytest.raises(APIRetryError) as exc_info:
                client.get("/posts/1")

            assert mock_httpx_sync_client.request.call_count == 2
            assert isinstance(exc_info.value.__cause__, APIConnectionError)


# =============================================================================
# 学習ポイント:
#
# 1. カスタム例外クラス設計:
#    - 例外の継承関係による階層的エラー処理
#    - 追加情報（ステータスコード、レスポンス）の保持
#    - エラーメッセージの意味的な分類
#
# 2. リトライロジック実装パターン:
#    - サーバーエラー（5xx）はリトライ対象
#    - クライアントエラー（4xx）はリトライしない
#    - タイムアウト・接続エラーはリトライ対象
#    - リトライ上限でAPIRetryErrorを発生
#
# 3. エラー回復戦略:
#    - 一時的なエラーからの自動回復
#    - リトライ間隔の設定（exponential backoffも可能）
#    - 最終的なエラーハンドリング（リトライ失敗時）
#
# 4. テストでのモック活用:
#    - side_effectによる複数回の動作シミュレーション
#    - call_countによるリトライ回数検証
#    - 例外の適切な検証（pytest.raises）
#
# 5. Async/Sync対称構造:
#    - test_async_client_error_handling.py と同一設計
#    - クラス構造: Exceptions, RetryLogic, Timeout, Connection
# =============================================================================
