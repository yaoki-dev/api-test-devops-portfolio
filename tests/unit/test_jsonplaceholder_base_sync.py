"""JSONPlaceholder_base_sync モジュールの同期通信基盤テスト

Note:
 - Create/Update/Delete は永続化されない。POST は常に ``id=101`` を返す。
"""

import logging
import sys
from unittest.mock import Mock, patch

import httpx
import pytest
import respx
import structlog
from structlog.testing import capture_logs

from tests.constants import BASE_URL, INVALID_BASE_URLS
from tests.unit.helpers import mock_get_route
from utils.exceptions import (
    APIClientError,
    APIConnectionError,
    APIHTTPError,
    APIRetryError,
    APITimeoutError,
)
from utils.jsonplaceholder_base_sync import SyncAPIClient

pytestmark = pytest.mark.unit


class MockAPISettings:
    def __init__(self) -> None:
        self.base_url = BASE_URL
        self.timeout = 30.0
        self.retry_count = 3
        self.retry_delay = 0.1
        self.user_agent = "test-agent"
        self.max_connections = 10


class MockSettings:
    def __init__(self) -> None:
        self.api = MockAPISettings()


mock_settings_instance = MockSettings()


@pytest.fixture(autouse=True)
def mock_settings():
    """import済みsettingsを参照先でpatchし、実settingsへの漏れと設定リークを防ぐ。"""
    # NOTE: 各クライアントモジュールは `from config.settings import settings` により
    # 自前の `settings` バインディングを import 時に確定する。そのため
    # `config.settings.settings` を patch しても、それらのバインディングには届かず
    # テスト分離が成立しない（"patch where it is looked up" の原則）。実際に参照
    # される各モジュールの `settings` 名を patch する。
    with (
        patch("utils.http_helpers.settings", new=mock_settings_instance),
        patch("utils.jsonplaceholder_base_sync.settings", new=mock_settings_instance),
    ):
        yield


def test_base_client_initialization():
    client = SyncAPIClient(base_url="https://test.com", timeout=10.0, retry_count=1)
    assert client.base_url == "https://test.com"
    assert client.timeout == 10.0
    assert client.retry_count == 1
    assert "User-Agent" in client.default_headers


def test_context_manager_basic():
    with SyncAPIClient(base_url="https://test.com") as client:
        assert client._client is not None
        assert isinstance(client._client, httpx.Client)


def test_base_client_uses_default_settings_if_not_provided():
    client = SyncAPIClient()  # Uses mock_settings_instance
    assert client.base_url == BASE_URL
    assert client.timeout == 30.0
    assert client.retry_count == 3


def test_mock_settings_fixture_is_effective():
    """mock_settings fixture が実際に有効であることを保証する回帰テスト

    retry_delay は mock 値 0.1 と実 .env 既定値 1.0 が異なるため、パッチ標的が
    誤っている（import 済みバインディングに届かない）場合は実値 1.0 が返り、この
    アサーションが失敗する。テスト分離が実効的であることを保証する。
    """
    client = SyncAPIClient()  # 引数なし → mock_settings_instance を参照するはず
    assert client.retry_delay == 0.1  # mock 固有値（実 .env 既定は 1.0）


def test_base_client_headers_are_set_correctly():
    custom_headers = {"X-Custom-Header": "Value"}
    client = SyncAPIClient(base_url="https://test.com", headers=custom_headers)
    assert client.default_headers["X-Custom-Header"] == "Value"
    assert client.default_headers["Accept"] == "application/json"


def test_base_client_close_method():
    client = SyncAPIClient(base_url="https://test.com")
    client.__enter__()  # Manually enter context to ensure _client is initialized
    assert client._client is not None
    client.close()


def test_sync_close_sets_client_none_even_when_close_raises() -> None:
    """SyncAPIClient.close() は close() が例外を投げても _client=None を保証する。

    close() 例外時に _client が残存すると _request 冒頭の
    use-after-close ガード（_client is None 判定）をすり抜け、壊れたクライアントへ
    リクエストが発行される状態不整合が生じる。finally で _client=None を保証し、
    例外は従来通り呼び出し元へ伝播させる（非同期版の _close_async_client と対称）。
    """
    client = SyncAPIClient(base_url="https://test.example.com")
    client._client = Mock()
    client._client.close = Mock(side_effect=OSError("close-failed"))

    # 例外は呼び出し元へ伝播する（finally は抑制しない）
    with pytest.raises(OSError, match="close-failed"):
        client.close()

    # close() 失敗後も _client=None が保証され、use-after-close ガードが機能する
    assert client._client is None


@respx.mock
def test_sync_get_user() -> None:
    route = respx.get(f"{BASE_URL}/users/1").respond(json={"id": 1, "name": "Test User"})

    with SyncAPIClient() as client:
        response = client.get("/users/1")

    assert response.status_code == 200
    assert response.json()["id"] == 1
    assert route.call_count == 1  # HTTPリクエストが1回実際に発行されたことを確認


@respx.mock
def test_sync_post_create_user() -> None:
    route = respx.post(f"{BASE_URL}/users").respond(
        status_code=201,
        json={"id": 101, "name": "New User", "email": "new@example.com"},
    )

    with SyncAPIClient() as client:
        response = client.post("/users", json={"name": "New User", "email": "new@example.com"})

    assert response.status_code == 201
    assert response.json()["id"] == 101
    assert route.call_count == 1  # HTTPリクエストが1回実際に発行されたことを確認


@respx.mock
def test_sync_put_update_user() -> None:
    route = respx.put(f"{BASE_URL}/users/1").respond(json={"id": 1, "name": "Updated"})

    with SyncAPIClient() as client:
        response = client.put("/users/1", json={"name": "Updated"})

    assert response.status_code == 200
    assert response.json()["name"] == "Updated"
    assert route.call_count == 1  # HTTPリクエストが1回実際に発行されたことを確認


@respx.mock
def test_sync_delete_user() -> None:
    route = respx.delete(f"{BASE_URL}/users/1").respond(status_code=204, content=b"")

    with SyncAPIClient() as client:
        response = client.delete("/users/1")

    assert response.status_code == 204
    assert route.call_count == 1  # HTTPリクエストが1回実際に発行されたことを確認


def test_sync_context_manager_cleanup() -> None:
    """httpx.Client.close() の呼出しを with 終了時に固定するため patch で検証する。"""
    client_instance = SyncAPIClient()
    with patch.object(client_instance._client, "close") as mock_close:
        with client_instance:
            # コンテキスト内でクライアントが使用可能
            assert client_instance._client is not None

    # with文を抜けた後、SyncAPIClient.close()→httpx.Client.close()が呼ばれる
    mock_close.assert_called_once()


@respx.mock
def test_sync_empty_response_handling() -> None:
    route = respx.get(f"{BASE_URL}/empty").respond(json={})

    with SyncAPIClient() as client:
        response = client.get("/empty")

    assert response.json() == {}
    assert route.call_count == 1  # HTTPリクエストが1回実際に発行されたことを確認


@respx.mock
def test_sync_malformed_json_handling() -> None:
    route = respx.get(f"{BASE_URL}/malformed").respond(
        content=b"invalid json",
        headers={"content-type": "application/json"},
    )

    with SyncAPIClient() as client:
        response = client.get("/malformed")

    with pytest.raises(ValueError):
        response.json()
    assert route.call_count == 1  # HTTPリクエストが1回実際に発行されたことを確認


@pytest.mark.parametrize("user_id", [0, -1, sys.maxsize], ids=["zero", "negative", "max_int"])
@respx.mock
def test_sync_boundary_user_id(user_id: int) -> None:
    route = respx.get(f"{BASE_URL}/users/{user_id}").respond(json={"id": user_id})

    with SyncAPIClient() as client:
        response = client.get(f"/users/{user_id}")

    assert response.json()["id"] == user_id
    assert route.call_count == 1  # HTTPリクエストが1回実際に発行されたことを確認


def test_sync_client_timeout_zero_not_overridden() -> None:
    """timeout=0.0がデフォルト設定値に上書きされないことを確認（r2850768833回帰テスト）

    httpxでは timeout=0.0 は即座にタイムアウト（TimeoutException発生）する設定値。
    falsyな値として `or` パターンで設定値に上書きされてはならない。
    """
    client = SyncAPIClient(timeout=0.0)
    assert client.timeout == 0.0, (
        "timeout=0.0 はhttpxで有効な設定値（即座にタイムアウト）のため"
        "デフォルト設定値に上書きされてはならない"
    )


@pytest.mark.parametrize("base_url", INVALID_BASE_URLS, ids=["empty", "spaces", "tab", "newline"])
def test_sync_client_base_url_validation_raises_value_error(base_url: str) -> None:
    """base_url が空・空白・タブ・改行の場合、初期化時に ValueError が発生する

    Security Rationale:
        空文字列: httpx.Client に渡ると実行時に InvalidURL が発生し原因特定が困難。
        初期化時の早期検証で設定ミスを即座に検出する。

        空白バイパス: bool("   ") == True のため `if not self.base_url` を通過する。
        str.strip() による追加検証が必要。

        タブ・改行: URL設定時の見えない制御文字バイパスを防ぐ。
    """
    with pytest.raises(ValueError, match="base_url is empty"):
        SyncAPIClient(base_url=base_url)


def test_sync_client_falsy_values_not_overridden() -> None:
    """falsy値(0, 0.0)がデフォルト設定値に上書きされないことを検証

    退行防止（r2850768833回帰テスト）:
    修正前の `x or default` パターンでは retry_count=0 や
    timeout=0.0 がFalsyと判定され設定値で上書きされていた。
    `x if x is not None else default` への修正が正しく動作することを保証する。
    """
    with SyncAPIClient(
        base_url=BASE_URL,
        retry_count=0,
        timeout=0.0,
        retry_delay=0.0,
    ) as client:
        assert client.retry_count == 0, (
            "retry_count=0 should NOT be overridden by settings. "
            "Regression guard against `x or default` pattern."
        )
        assert client.timeout == 0.0, (
            "timeout=0.0 should NOT be overridden by settings. "
            "Regression guard against `x or default` pattern."
        )
        assert client.retry_delay == 0.0, (
            "retry_delay=0.0 should NOT be overridden by settings. "
            "Regression guard against `x or default` pattern."
        )


@respx.mock
@patch("utils.jsonplaceholder_base_sync.exponential_backoff_with_jitter", return_value=0.0)
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
    # バックオフが2回呼ばれることを確認（attempt 0,1で失敗→backoff、attempt 2で成功）
    assert mock_backoff.call_count == 2


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


@respx.mock
@patch("utils.jsonplaceholder_base_sync.exponential_backoff_with_jitter", return_value=0.0)
def test_sync_timeout_error_retry(mock_backoff: Mock) -> None:
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
    assert mock_backoff.call_count == 1  # retry_count=1 → バックオフ1回


@respx.mock
@patch("utils.jsonplaceholder_base_sync.exponential_backoff_with_jitter", return_value=0.0)
def test_sync_connection_error_retry(mock_backoff: Mock) -> None:
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
    assert mock_backoff.call_count == 1  # retry_count=1 → バックオフ1回


@respx.mock
@patch("utils.jsonplaceholder_base_sync.exponential_backoff_with_jitter", return_value=0.0)
def test_sync_retry_exhausted(mock_backoff: Mock) -> None:
    """リトライ上限でAPIRetryErrorが発生することを確認（5xxのみリトライ）"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(500),
        httpx.Response(500),
    ]

    with SyncAPIClient(retry_count=2, retry_delay=0.01) as client:
        with pytest.raises(APIRetryError) as exc_info:
            client.get("/posts/1")

    # リトライ回数+1回（初回+リトライ2回=3回）実行されたことを確認
    assert route.call_count == 3
    assert "Request failed after 3 attempts" in str(exc_info.value)
    assert exc_info.value.attempts == 3
    assert exc_info.value.suppressed_reason is None
    # バックオフはattempt 0, 1で呼ばれる（attempt 2は最後なのでなし）
    assert mock_backoff.call_count == 2


@respx.mock
@patch("utils.jsonplaceholder_base_sync.exponential_backoff_with_jitter", return_value=0.0)
def test_sync_timeout_then_success(mock_backoff: Mock) -> None:
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.TimeoutException("Timeout 1"),
        httpx.Response(200, json={"id": 1}),
    ]

    with SyncAPIClient(retry_count=2, retry_delay=0.01) as client:
        response = client.get("/posts/1")

    assert route.call_count == 2
    assert response.status_code == 200
    # バックオフはattempt 0でのみ呼ばれる（attempt 1で成功）
    assert mock_backoff.call_count == 1


@respx.mock
@patch("utils.jsonplaceholder_base_sync.exponential_backoff_with_jitter", return_value=0.0)
def test_sync_connection_then_success(mock_backoff: Mock) -> None:
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.ConnectError("Connection 1"),
        httpx.ConnectError("Connection 2"),
        httpx.Response(200, json={"id": 1}),
    ]

    with SyncAPIClient(retry_count=3, retry_delay=0.01) as client:
        response = client.get("/posts/1")

    assert route.call_count == 3
    assert response.status_code == 200
    # バックオフが2回呼ばれることを確認（attempt 0, 1で失敗→backoff、attempt 2で成功）
    assert mock_backoff.call_count == 2


@respx.mock
@patch("utils.jsonplaceholder_base_sync.exponential_backoff_with_jitter", return_value=0.0)
def test_sync_mixed_errors_then_success(mock_backoff: Mock) -> None:
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.TimeoutException("Timeout"),
        httpx.Response(503),
        httpx.Response(200, json={"id": 1}),
    ]

    with SyncAPIClient(retry_count=3, retry_delay=0.01) as client:
        response = client.get("/posts/1")

    assert route.call_count == 3
    assert response.status_code == 200
    # バックオフが2回呼ばれることを確認（attempt 0, 1で失敗→backoff、attempt 2で成功）
    assert mock_backoff.call_count == 2


@respx.mock
@patch("utils.jsonplaceholder_base_sync.exponential_backoff_with_jitter", return_value=0.0)
def test_sync_mixed_errors_exhaust_retries(mock_backoff: Mock) -> None:
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.TimeoutException("Timeout"),
        httpx.ConnectError("Connection failed"),
        httpx.Response(500),
    ]

    with SyncAPIClient(retry_count=2, retry_delay=0.01) as client:
        with pytest.raises(APIRetryError) as exc_info:
            client.get("/posts/1")

    assert route.call_count == 3
    # 最後のエラー（500 Server Error）が__causeとして記録されていることを確認
    assert isinstance(exc_info.value.__cause__, APIHTTPError)
    # バックオフが2回呼ばれることを確認（最後の試行ではバックオフなし）
    assert mock_backoff.call_count == 2


@respx.mock
@patch("utils.jsonplaceholder_base_sync.exponential_backoff_with_jitter", return_value=0.0)
def test_sync_put_4xx_no_retry(mock_backoff: Mock) -> None:
    """PUTリクエストで4xxエラーはリトライせず即座にAPIHTTPErrorを発生"""
    route = respx.put(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.Response(400),
    ]

    with SyncAPIClient(retry_count=3) as client:
        with pytest.raises(APIHTTPError) as exc_info:
            client.put("/posts/1", json={"title": "updated"})

    # 4xxエラーはリトライしない（1回のみ実行）
    assert route.call_count == 1
    assert exc_info.value.status_code == 400
    # 4xxは即raise、バックオフに到達しないことを確認
    assert mock_backoff.call_count == 0


@respx.mock
@patch("utils.jsonplaceholder_base_sync.exponential_backoff_with_jitter", return_value=0.0)
def test_sync_put_does_not_retry_by_default(mock_backoff: Mock) -> None:
    """PUTも実サーバーの非冪等実装に備え、既定では再送しない。"""
    route = respx.put(f"{BASE_URL}/posts/1")
    route.side_effect = [httpx.Response(502)]

    with SyncAPIClient(retry_count=2) as client:
        with pytest.raises(APIRetryError) as exc_info:
            client.put("/posts/1", json={"title": "updated"})

    assert route.call_count == 1
    assert exc_info.value.suppressed_reason == "non_idempotent_method"
    assert "Retry suppressed for non-idempotent PUT request." in str(exc_info.value)
    assert mock_backoff.call_count == 0


@respx.mock
@patch("utils.jsonplaceholder_base_sync.exponential_backoff_with_jitter", return_value=0.0)
def test_sync_put_retries_when_explicitly_opted_in(mock_backoff: Mock) -> None:
    route = respx.put(f"{BASE_URL}/posts/1")
    route.side_effect = [httpx.Response(502), httpx.Response(200)]

    with SyncAPIClient(retry_count=2) as client:
        response = client.put(
            "/posts/1",
            json={"title": "updated"},
            retry_non_idempotent=True,
        )

    assert route.call_count == 2
    assert response.status_code == 200
    assert mock_backoff.call_count == 1


@respx.mock
@patch("utils.jsonplaceholder_base_sync.exponential_backoff_with_jitter", return_value=0.0)
def test_sync_delete_with_retry(mock_backoff: Mock) -> None:
    route = respx.delete(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.TimeoutException("Timeout"),
        httpx.Response(200),
    ]

    with SyncAPIClient(retry_count=2, retry_delay=0.01) as client:
        response = client.delete("/posts/1")

    assert route.call_count == 2
    assert response.status_code == 200
    # バックオフが1回呼ばれることを確認（attempt 0でTimeout失敗→backoff、attempt 1で成功）
    assert mock_backoff.call_count == 1


@respx.mock
@patch("utils.jsonplaceholder_base_sync.exponential_backoff_with_jitter", return_value=0.0)
def test_sync_post_does_not_retry_by_default(mock_backoff: Mock) -> None:
    """POSTは既定で再送せず、非冪等リトライの抑止理由を公開する。"""
    route = respx.post(f"{BASE_URL}/posts")
    route.side_effect = [httpx.Response(502)]

    with SyncAPIClient(retry_count=2, retry_delay=0.01) as client:
        with pytest.raises(APIRetryError) as exc_info:
            client.post(
                "/posts",
                json={"title": "test", "body": "content", "userId": 1},
            )

    assert route.call_count == 1
    assert exc_info.value.attempts == 1
    assert exc_info.value.suppressed_reason == "non_idempotent_method"
    assert "Retry suppressed for non-idempotent POST request." in str(exc_info.value)
    assert mock_backoff.call_count == 0


@respx.mock
@patch("utils.jsonplaceholder_base_sync.exponential_backoff_with_jitter", return_value=0.0)
def test_sync_post_retries_when_explicitly_opted_in(mock_backoff: Mock) -> None:
    """POSTは明示的なオプトイン時だけ既存の再送動作を許可する。"""
    route = respx.post(f"{BASE_URL}/posts")
    route.side_effect = [
        httpx.Response(502),
        httpx.Response(201, json={"id": 101, "title": "created"}),
    ]

    with SyncAPIClient(retry_count=2, retry_delay=0.01) as client:
        response = client.post(
            "/posts",
            json={"title": "test", "body": "content", "userId": 1},
            retry_non_idempotent=True,
        )

    assert route.call_count == 2
    assert response.status_code == 201
    assert mock_backoff.call_count == 1


@respx.mock
@patch("utils.jsonplaceholder_base_sync.exponential_backoff_with_jitter", return_value=0.0)
def test_sync_patch_does_not_retry_by_default(mock_backoff: Mock) -> None:
    """PATCHも既定で再送しない。"""
    route = respx.patch(f"{BASE_URL}/todos/1")
    route.side_effect = [httpx.Response(502)]

    with SyncAPIClient(retry_count=2) as client:
        with pytest.raises(APIRetryError) as exc_info:
            client.patch("/todos/1", json={"completed": True})

    assert route.call_count == 1
    assert exc_info.value.suppressed_reason == "non_idempotent_method"
    assert mock_backoff.call_count == 0


@respx.mock
@patch("utils.jsonplaceholder_base_sync.exponential_backoff_with_jitter", return_value=0.0)
def test_sync_patch_retries_when_explicitly_opted_in(mock_backoff: Mock) -> None:
    """PATCHは明示的なオプトイン時だけ再送する。"""
    route = respx.patch(f"{BASE_URL}/todos/1")
    route.side_effect = [httpx.Response(502), httpx.Response(200)]

    with SyncAPIClient(retry_count=2) as client:
        response = client.patch(
            "/todos/1",
            json={"completed": True},
            retry_non_idempotent=True,
        )

    assert route.call_count == 2
    assert response.status_code == 200
    assert mock_backoff.call_count == 1


@pytest.mark.parametrize(
    "exc",
    [
        httpx.TooManyRedirects("Max redirects exceeded"),
        httpx.InvalidURL("Invalid URL format"),
    ],
)
@respx.mock
def test_sync_non_retryable_error_logs_before_raise(
    exc: httpx.TooManyRedirects | httpx.InvalidURL,
) -> None:
    """非リトライエラー時にlogger.errorが_map_request_error前に実行される

    _map_request_errorは非リトライエラーで即座にraiseするが、
    ログ出力はその前に実行されるため、デバッグ情報が失われない。
    非リトライエラー（TooManyRedirects/InvalidURL）はERRORレベルで記録される。
    """
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = exc

    with capture_logs() as log_output:
        with pytest.raises(APIClientError, match="Non-retryable request error"):
            with SyncAPIClient(retry_count=0) as client:
                client.get("/posts/1")

    # ERRORレベルのログが出力されていることを検証（ログバイパスが修正済み）
    error_logs = [
        log
        for log in log_output
        if log.get("log_level") == "error" and log.get("event") == "request_error_non_retryable"
    ]
    assert len(error_logs) == 1, f"Expected 1 error log, got: {log_output}"
    assert error_logs[0]["method"] == "GET"
    assert error_logs[0]["endpoint"] == "/posts/1"
    assert "error" not in error_logs[0]  # security: 認証情報漏洩防止
    assert "error_type" in error_logs[0]  # error_type フィールドの存在確認
    assert error_logs[0]["is_async"] is False  # SyncAPIClient 呼び出しの確認


@respx.mock
def test_sync_non_retryable_error_skips_retry() -> None:
    """retry_count>=1設定時でも非リトライエラーはリトライループを即 raise で脱出する

    TooManyRedirects/InvalidURL は即 raise のため、
    retry_count を増やしても1回のみの試行で APIClientError が発生する。
    """
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = httpx.TooManyRedirects("Max redirects exceeded")

    with pytest.raises(APIClientError, match="Non-retryable request error"):
        with SyncAPIClient(retry_count=2) as client:
            client.get("/posts/1")

    # リトライされていないことを確認
    assert route.call_count == 1, "非リトライエラーは1回のみ試行される"


@respx.mock
def test_get_produces_structured_logs() -> None:
    """#83: GET呼び出しで request_start / request_success ログが出力される

    検証: モックレスポンスに対して GET を実行し、structlog が
    リクエスト開始・成功イベントを endpoint 付きで記録すること。

    request_start / request_success は DEBUG レベルで出力されるため、
    テスト中のみ DEBUG へ再構成して capture し、
    終了後に元の structlog 設定へ復元する。
    実API不要・決定論的（respx で HTTP 層を差し替え）。
    """
    mock_get_route(f"{BASE_URL}/posts/1", None, {"id": 1})

    # structlog のグローバル設定をテスト用に DEBUG へ再構成し、終了時は
    # reset_defaults() で builtin デフォルトへリセットする（get_config 復元は
    # ミュータブル参照共有で不完全になりうるため。structlog 公式推奨のクリーンアップ）。
    # reset 後は他テストの get_logger() 呼び出しで production 設定が遅延再構成される。
    try:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
            cache_logger_on_first_use=False,
        )
        with structlog.testing.capture_logs() as logs:
            with SyncAPIClient() as client:
                client.get("/posts/1")
    finally:
        structlog.reset_defaults()

    events = [entry["event"] for entry in logs]
    assert "request_start" in events, (
        f"request_start ログエントリが見つかりません。記録されたイベント: {events}\n"
        "hint: structlog の wrapper_class 再構成が SyncAPIClient の"
        "ロガーに適用されているか確認してください"
    )

    success = next(
        (entry for entry in logs if entry["event"] == "request_success"),
        None,
    )
    assert success is not None, (
        f"request_success ログエントリが見つかりません。記録されたイベント: {events}"
    )
    assert success["endpoint"] == "/posts/1"
    assert success["status_code"] == 200


def test_sync_client_headers_empty_dict_preserves_defaults(mock_base_url: str) -> None:
    """SyncAPIClient: headers={} でデフォルトヘッダーが保持される

    `if headers is not None:` の設計を保証するテスト。
    空辞書を渡しても update({}) は no-op なので、デフォルトヘッダーは変わらない。
    """
    with SyncAPIClient(base_url=mock_base_url, headers={}) as client:
        # デフォルトヘッダーは3つ: User-Agent, Accept, Content-Type
        assert set(client.default_headers.keys()) == {
            "User-Agent",
            "Accept",
            "Content-Type",
        }
        # Noneではなく、正しく設定されている
        assert client.default_headers["User-Agent"]
        assert client.default_headers["Accept"] == "application/json"
        assert client.default_headers["Content-Type"] == "application/json"
