"""
SyncAPIClient エラーハンドリングテスト

Note:
    test_async_client_error_handling.py と対称構造で設計。
    責務: リトライロジック + 例外ハンドリングの検証

    例外クラス・_safe_parse_json・_map_request_error のテストは
    test_api_client_shared.py に統合済み。

テストケース一覧（4件）:
    - Retry (2件): exponential_backoff, 4xx_no_retry
    - Timeout (1件): timeout_error_retry
    - Connection (1件): connection_error_retry
"""

from unittest.mock import Mock, patch

import httpx
import pytest
import respx

from utils.api_client import (
    APIConnectionError,
    APIHTTPError,
    APIRetryError,
    APITimeoutError,
    SyncAPIClient,
)

pytestmark = pytest.mark.unit

BASE_URL = "https://jsonplaceholder.typicode.com"

# =============================================================================
# Retry Logic Tests（条件2: エラーパス）
# =============================================================================


@patch("utils.api_client.exponential_backoff_with_jitter", return_value=0.0)
@respx.mock
def test_sync_retry_with_exponential_backoff(mock_backoff: Mock) -> None:
    """サーバーエラー後に成功するケース（5xxはリトライ対象）"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.Response(500),  # 初回: 失敗
        httpx.Response(500),  # リトライ1回目: 失敗
        httpx.Response(200, json={"id": 1}),  # リトライ2回目: 成功
        # Note: retry_count=3（最大4回呼び出し可能）だが、
        # 2回目のリトライで成功するためリストは3要素で十分
    ]

    with SyncAPIClient(retry_count=3, retry_delay=0.01) as client:
        response = client.get("/posts/1")

    assert route.call_count == 3
    assert response.status_code == 200


@respx.mock
def test_sync_4xx_error_no_retry() -> None:
    """4xxクライアントエラーはリトライせず即座にAPIHTTPErrorを発生"""
    route = respx.get(f"{BASE_URL}/posts/999")
    route.side_effect = [
        httpx.Response(404),
    ]

    with SyncAPIClient(retry_count=3) as client:
        with pytest.raises(APIHTTPError) as exc_info:
            client.get("/posts/999")

    # 4xxエラーはリトライしない（1回のみ実行）
    assert route.call_count == 1
    assert exc_info.value.status_code == 404


# =============================================================================
# Timeout Tests（条件2: エラーパス）
# =============================================================================


@patch("utils.api_client.exponential_backoff_with_jitter", return_value=0.0)
@respx.mock
def test_sync_timeout_error_retry(mock_backoff: Mock) -> None:
    """タイムアウト時にAPIRetryErrorが発生することを確認"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.TimeoutException("Request timed out"),
        httpx.TimeoutException("Request timed out"),
    ]

    with SyncAPIClient(retry_count=1, retry_delay=0.01) as client:
        with pytest.raises(APIRetryError) as exc_info:
            client.get("/posts/1")

    # リトライが実行されることを確認（初回+リトライ1回=2回）
    assert route.call_count == 2
    assert isinstance(exc_info.value.__cause__, APITimeoutError)


# =============================================================================
# Connection Tests（条件2: エラーパス）
# =============================================================================


@patch("utils.api_client.exponential_backoff_with_jitter", return_value=0.0)
@respx.mock
def test_sync_connection_error_retry(mock_backoff: Mock) -> None:
    """接続エラー時にAPIRetryErrorが発生することを確認"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.ConnectError("Connection refused"),
        httpx.ConnectError("Connection refused"),
    ]

    with SyncAPIClient(retry_count=1, retry_delay=0.01) as client:
        with pytest.raises(APIRetryError) as exc_info:
            client.get("/posts/1")

    assert route.call_count == 2
    assert isinstance(exc_info.value.__cause__, APIConnectionError)


# =============================================================================
# 学習ポイント:
#
# 1. リトライロジック実装パターン:
#    - サーバーエラー（5xx）はリトライ対象
#    - クライアントエラー（4xx）はリトライしない
#    - タイムアウト・接続エラーはリトライ対象
#    - リトライ上限でAPIRetryErrorを発生
#
# 2. エラー回復戦略:
#    - 一時的なエラーからの自動回復
#    - リトライ間隔の設定（exponential backoffも可能）
#    - 最終的なエラーハンドリング（リトライ失敗時）
#
# 3. respxパターンB（side_effect）の活用:
#    - side_effectリストで複数回の動作シミュレーション
#    - 例外とhttpx.Responseの混在が可能
#    - call_countによるリトライ回数検証
#    - 例外の適切な検証（pytest.raises）
#
# 4. 共通テスト（例外・JSON・エラーマッピング）:
#    → test_api_client_shared.py に統合済み
# =============================================================================
