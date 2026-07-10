"""Async base client tests for utils.jsonplaceholder_base_async."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
import respx
from structlog.testing import capture_logs

from tests.constants import BASE_URL, INVALID_BASE_URLS
from utils.exceptions import (
    APIClientError,
    APIConnectionError,
    APIHTTPError,
    APIRetryError,
    APITimeoutError,
)
from utils.jsonplaceholder_base_async import AsyncAPIClient

pytestmark = pytest.mark.unit


@respx.mock
@patch("utils.jsonplaceholder_base_async.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_timeout_retry_then_success(mock_backoff: Mock) -> None:
    """
    タイムアウトエラー後のリトライで最終的に成功するテスト

    検証項目：
    - タイムアウトエラー発生時にリトライが行われること（2回連続タイムアウト）
    - リトライ回数が設定値（retry_count=3）に基づくこと
      （初回+最大3回リトライ=最大4回実行、本テストは3回目で成功）
    - リトライ後に成功した場合のレスポンスが正しく返却されること

    Note: test_async_client_error_handling.py の test_async_timeout_then_success（1回タイムアウト）
          と対をなすテスト。こちらは「2回連続タイムアウト → 3回目で成功」を検証する。
          @patch(exponential_backoff_with_jitter)でリトライ待機を0秒化しCI時間短縮。
          respxトランスポートモックにより実際のhttpxコードパスを通じて検証する。
    """
    # respxルート: 最初の2回はタイムアウト、3回目で成功
    # retry_count=3 の場合: 初回(1) + 最大リトライ(3) = 最大4リクエスト。
    # 本テストは3回目で成功するためリスト要素は3個（TimeoutException 2個 + Response 1個）。
    # 注意: side_effect 要素数はリクエスト総数（初回+リトライ数）と一致させること。
    # 不一致はStopIteration→RuntimeErrorになる。
    route = respx.get(f"{BASE_URL}/users/1")
    route.side_effect = [
        httpx.TimeoutException("Timeout 1"),
        httpx.TimeoutException("Timeout 2"),
        httpx.Response(200, json={"id": 1, "name": "Test User"}),
    ]

    async with AsyncAPIClient(retry_count=3) as client:
        result = await client.get("/users/1")

    # リトライ動作検証: 3回目で成功（call_countで決定論的に検証）
    assert route.call_count == 3
    assert mock_backoff.call_count == 2  # 3回試行 = 2回待機（初回は待機なし）

    # レスポンス検証: get()はhttpx.Responseを返す
    assert result.status_code == 200
    json_data = result.json()
    assert json_data["id"] == 1
    assert json_data["name"] == "Test User"


@respx.mock
@patch("utils.jsonplaceholder_base_async.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_performance_and_timeout(mock_backoff: Mock) -> None:
    """
    非同期処理のパフォーマンス・タイムアウト・リソース管理テスト

    検証項目：
    - リクエストタイムアウト時のリトライ動作
    - 全リトライ失敗後のAPIRetryError発生
    - リトライ回数がretry_countに基づくこと（route.call_countで決定論的に検証）

    Note: タイムアウト時、実装はリトライ後にAPIRetryErrorを発生させる。
          TimeoutExceptionは内部でキャッチされる。
          @patch(exponential_backoff_with_jitter)でリトライ待機を0秒化しCI時間短縮。
          respxトランスポートモックにより実際のhttpxコードパスを通じて検証する。
    """
    retry_count = 1  # retry_count=1: 初回 + 1回リトライ = 2回のリクエスト

    # respxルート: 全リクエストでタイムアウト（retry_count+1 回）
    route = respx.get(f"{BASE_URL}/users/1")
    route.side_effect = [httpx.TimeoutException("Request timeout") for _ in range(retry_count + 1)]

    # タイムアウト動作テスト（全リトライ後にAPIRetryError）
    async with AsyncAPIClient(timeout=1.0, retry_count=retry_count) as client:
        with pytest.raises(APIRetryError) as exc_info:
            await client.get("/users/1")

    # エラーメッセージ検証
    assert "failed after" in str(exc_info.value).lower()

    # リトライ動作確認: route.call_count で決定論的に検証（respxトランスポートモック使用）
    assert route.call_count == retry_count + 1  # 初回 + retry_count回リトライ
    assert mock_backoff.call_count == retry_count  # リトライ1回 = バックオフ1回


async def test_async_context_manager_cleanup_on_success():
    """
    正常終了時のコンテキストマネージャーリソースクリーンアップテスト

    検証項目：
    - async with ブロック正常終了時に aclose() が呼び出されること

    Note: aclose()呼び出し検証はhttpxクライアントの内部動作に依存するためpatchを使用。
    """
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance

        async with AsyncAPIClient():
            pass  # 何もしない

        # aclose() が呼び出されることを確認
        mock_client_instance.aclose.assert_called_once()


async def test_async_context_manager_cleanup_on_exception():
    """
    例外発生時でもコンテキストマネージャーがクリーンアップするテスト

    検証項目：
    - 例外発生時でも aclose() が呼び出されること（リソースリークなし）

    Note: aclose()呼び出し検証はhttpxクライアントの内部動作に依存するためpatchを使用。
          RuntimeError は httpx.RequestError のサブクラスではないため、リトライを通らず
          そのまま伝播する。基底クラス Exception より具体的な型を使用することで
          テストバグの誤検知を防ぐ。
    """
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance

        test_error = RuntimeError("Test error")
        mock_client_instance.request.side_effect = test_error

        with pytest.raises(RuntimeError) as exc_info:
            async with AsyncAPIClient() as client:
                await client.get("/users/1")

        assert str(exc_info.value) == "Test error"
        # 例外発生時でもaclose()が呼び出されることを確認（クリーンアップ保証）
        mock_client_instance.aclose.assert_called_once()


@pytest.mark.parametrize(
    "close_exc,expected_type,expected_module",
    [
        (httpx.CloseError("close-failed"), "CloseError", "httpx"),
        (OSError("connection reset"), "OSError", "builtins"),
    ],
)
async def test_async_api_client_aexit_aclose_exception_is_suppressed_with_warning(
    close_exc: httpx.CloseError | OSError,
    expected_type: str,
    expected_module: str,
) -> None:
    """__aexit__ で aclose() が例外を投げても警告ログのみ出力する"""
    client = AsyncAPIClient()

    with (
        patch.object(client._client, "aclose", new=AsyncMock(side_effect=close_exc)),
        capture_logs() as log_output,
    ):
        await client.__aexit__(None, None, None)

    warning_logs = [
        log for log in log_output if log.get("event") == "async_api_client_aclose_failed"
    ]
    assert len(warning_logs) == 1
    assert warning_logs[0]["error_type"] == expected_type
    assert warning_logs[0]["error_module"] == expected_module
    assert client._client is None


async def test_async_api_client_aexit_body_exception_not_overridden_by_close_exception() -> None:
    """__aexit__ で本体例外発生中に aclose() も例外を出すケース。

    body 例外 (exc_val) が close 例外で上書きされないこと
    (warning log only, no re-raise) を end-to-end で検証する。設計意図:
    ``async with`` body 例外 + aclose 例外の両発生時、原因情報 (body 例外) を
    優先伝播させて debuggability を維持する (CWE-755 例外マスク回避)。
    """
    client = AsyncAPIClient()

    with (
        patch.object(
            client._client,
            "aclose",
            new=AsyncMock(side_effect=httpx.CloseError("close-failed")),
        ),
        pytest.raises(ValueError, match="body-error"),
        capture_logs() as log_output,
    ):
        async with client:
            raise ValueError("body-error")

    # close 例外は warning log のみ。body 例外は ValueError として外側に伝播。
    warning_logs = [
        log for log in log_output if log.get("event") == "async_api_client_aclose_failed"
    ]
    assert len(warning_logs) == 1
    assert warning_logs[0]["error_type"] == "CloseError"
    assert warning_logs[0]["error_module"] == "httpx"


async def test_aexit_unexpected_exception_reraises_when_no_body_exception() -> None:
    """__aexit__ で body 例外なし + 予期しない close 例外 → close_exc を re-raise する。

    github_client.py L698 のテストを api_client 用に移植

    body 例外がない状態（exc_type is None）では、aclose() の予期しない例外は
    実装バグとして呼び出し元に伝播させる。
    error ログ（has_body_exception=False, exc_info=True）が記録されてから re-raise。
    """
    client = AsyncAPIClient()

    with (
        patch.object(
            client._client,
            "aclose",
            new=AsyncMock(side_effect=RuntimeError("close-failed")),
        ),
        pytest.raises(RuntimeError, match="close-failed"),
        capture_logs() as log_output,
    ):
        await client.__aexit__(None, None, None)

    unexpected_event = "async_api_client_aclose_unexpected_error"
    error_logs = [log for log in log_output if log.get("event") == unexpected_event]
    assert len(error_logs) == 1
    assert error_logs[0]["error_type"] == "RuntimeError"
    assert error_logs[0]["error_module"] == "builtins"
    assert error_logs[0]["has_body_exception"] is False
    # exc_info=True によりスタックトレースが記録される
    assert error_logs[0].get("exc_info") is True
    # 予期しない例外では warning ログは出ない
    failed_event = "async_api_client_aclose_failed"
    warning_logs = [log for log in log_output if log.get("event") == failed_event]
    assert len(warning_logs) == 0


async def test_aexit_unexpected_exception_suppressed_when_body_exception() -> None:
    """__aexit__ で body 例外あり + 予期しない close 例外 → re-raise しない（body 例外優先）。

    github_client.py L728 のテストを api_client 用に移植

    body 例外がある状態（exc_type is not None）では close_exc を re-raise せず、
    body 例外を優先伝播させて debuggability を維持する（CWE-755 例外マスク回避）。
    RuntimeError は予期しない例外ブランチ → error ログ + has_body_exception=True。
    """
    client = AsyncAPIClient()

    with (
        patch.object(
            client._client,
            "aclose",
            new=AsyncMock(side_effect=RuntimeError("close-failed")),
        ),
        pytest.raises(ValueError, match="body-error"),
        capture_logs() as log_output,
    ):
        async with client:
            raise ValueError("body-error")

    # close 例外は re-raise しない。body 例外は ValueError として外側に伝播。
    unexpected_event = "async_api_client_aclose_unexpected_error"
    error_logs = [log for log in log_output if log.get("event") == unexpected_event]
    assert len(error_logs) == 1
    assert error_logs[0]["error_type"] == "RuntimeError"
    assert error_logs[0]["error_module"] == "builtins"
    assert error_logs[0]["has_body_exception"] is True
    # exc_info=True によりスタックトレースが記録される
    assert error_logs[0].get("exc_info") is True
    # warning ログは出ない
    failed_event = "async_api_client_aclose_failed"
    warning_logs = [log for log in log_output if log.get("event") == failed_event]
    assert len(warning_logs) == 0


async def test_aclose_logger_info_failure_propagates_without_misclassification() -> None:
    """aclose() 単独呼び出し: logger.info 失敗が close 失敗として誤分類されないことを検証。

    close 処理は __aexit__ と共通化されるが、logger 例外はそのまま caller に
    propagate し、aclose_unexpected_error には記録されない (Codex Q-1 recommendation: both paths)。
    """
    client = AsyncAPIClient()

    with (
        patch.object(client._client, "aclose", new=AsyncMock()),
        patch.object(client.logger, "info", side_effect=RuntimeError("logger-failed")),
        patch.object(client.logger, "error") as mock_error,
        pytest.raises(RuntimeError, match="logger-failed"),
    ):
        await client.aclose()

    mock_error.assert_not_called()


@pytest.mark.parametrize(
    ("close_exc", "expected_type", "expected_module"),
    [
        (httpx.CloseError("close-failed"), "CloseError", "httpx"),
        (OSError("close-failed"), "OSError", "builtins"),
    ],
)
async def test_aclose_exception_is_suppressed_with_warning(
    close_exc: httpx.CloseError | OSError,
    expected_type: str,
    expected_module: str,
) -> None:
    """aclose() 単独呼び出しでも close 例外は warning のみで抑止する。"""
    client = AsyncAPIClient()

    with (
        patch.object(client._client, "aclose", new=AsyncMock(side_effect=close_exc)),
        capture_logs() as log_output,
    ):
        await client.aclose()

    warning_logs = [
        log for log in log_output if log.get("event") == "async_api_client_aclose_failed"
    ]
    assert len(warning_logs) == 1
    assert warning_logs[0]["error_type"] == expected_type
    assert warning_logs[0]["error_module"] == expected_module
    closed_logs = [log for log in log_output if log.get("event") == "async_api_client_closed"]
    assert len(closed_logs) == 0


async def test_aclose_normal_close_logs_info() -> None:
    """aclose() 単独呼び出し時に async_api_client_closed の info ログが1回出力される。"""
    client = AsyncAPIClient()

    with (
        patch.object(client._client, "aclose", new=AsyncMock()),
        capture_logs() as log_output,
    ):
        await client.aclose()

    closed_logs = [log for log in log_output if log.get("event") == "async_api_client_closed"]
    assert len(closed_logs) == 1
    assert closed_logs[0]["log_level"] == "info"


async def test_aclose_unexpected_exception_suppressed_with_warning() -> None:
    """aclose() 単独呼び出しで予期しない例外 (RuntimeError) は warning ログのみで抑止される。

    既存の ``test_aclose_exception_is_suppressed_with_warning`` は CloseError/OSError で
    第1 except 分岐 (async_api_client_aclose_failed) をヒットするのに対し、本テストは
    ``except Exception`` 第2分岐 (suppress_unexpected=True パス /
    async_api_client_aclose_unexpected_error_suppressed) を明示的にカバーする回帰防止テスト。
    aclose() は finally ブロック等での安全な呼び出しを保証するため、実装バグ起因の
    予期しない例外も re-raise せず握りつぶす設計。
    """
    client = AsyncAPIClient()

    with (
        patch.object(
            client._client,
            "aclose",
            new=AsyncMock(side_effect=RuntimeError("unexpected-boom")),
        ),
        capture_logs() as log_output,
    ):
        await client.aclose()  # 例外が伝播しないこと（伝播すればこのテストは失敗する）

    suppressed_logs = [
        log
        for log in log_output
        if log.get("event") == "async_api_client_aclose_unexpected_error_suppressed"
    ]
    assert len(suppressed_logs) == 1
    assert suppressed_logs[0]["error_type"] == "RuntimeError"
    assert suppressed_logs[0]["error_module"] == "builtins"
    # aclose 失敗のため else 節 (closed ログ) は未到達
    closed_logs = [log for log in log_output if log.get("event") == "async_api_client_closed"]
    assert len(closed_logs) == 0
    # suppress 経路でも状態一貫性のため _client が None になること（壊れたクライアント再利用防止）
    assert client._client is None


@pytest.mark.parametrize(
    "fatal_exc",
    [MemoryError("OOM"), RecursionError("maximum recursion depth exceeded")],
)
async def test_aclose_fatal_exception_propagates_not_suppressed(
    fatal_exc: MemoryError | RecursionError,
) -> None:
    """aclose() 単独呼出 (suppress_unexpected=True 経路) でも MemoryError /
    RecursionError は握りつぶさず fail-fast で伝播する。

    両者は ``Exception`` 派生 (MemoryError は ``Exception`` 直系、RecursionError は
    ``RuntimeError`` 派生) のため ``except Exception`` に捕捉されうるが、専用 except 句で
    先取りし即時 re-raise する設計 (github_client / sentry_init と同一方針)。
    ``test_aclose_unexpected_exception_suppressed_with_warning`` (RuntimeError は
    suppress) と対になり、「fatal のみ選択的に伝播」する不変条件を固定する回帰防止テスト。
    """
    client = AsyncAPIClient()

    with (
        patch.object(client._client, "aclose", new=AsyncMock(side_effect=fatal_exc)),
        pytest.raises(type(fatal_exc)),
        capture_logs() as log_output,
    ):
        await client.aclose()  # 専用 except 句で即時 re-raise されること

    # 専用句が except Exception より先に re-raise するため suppress ログは出ない
    suppressed_logs = [
        log
        for log in log_output
        if log.get("event") == "async_api_client_aclose_unexpected_error_suppressed"
    ]
    assert len(suppressed_logs) == 0
    # aclose 失敗のため closed ログも未到達
    closed_logs = [log for log in log_output if log.get("event") == "async_api_client_closed"]
    assert len(closed_logs) == 0


async def test_aexit_logger_info_failure_not_misclassified_as_close_failure() -> None:
    """__aexit__: _client.aclose() 成功後に logger.info が例外を投げても
    aclose_unexpected_error として誤分類されないことを検証 (Codex Q-1 regression)。

    else 節に logger.info を分離したため、logger 例外は try-except 外から propagate し、
    close 失敗 (aclose_unexpected_error) として記録されない。
    """
    client = AsyncAPIClient()

    with (
        patch.object(client._client, "aclose", new=AsyncMock()),
        patch.object(client.logger, "info", side_effect=RuntimeError("logger-failed")),
        patch.object(client.logger, "error") as mock_error,
        pytest.raises(RuntimeError, match="logger-failed"),
    ):
        await client.__aexit__(None, None, None)

    # close 失敗として誤分類されていない = error ログ（unexpected_error）未呼び出し
    mock_error.assert_not_called()


@pytest.mark.slow  # slowマーカー（通常実行では除外可能）
@respx.mock
async def test_async_performance_benchmark():
    """
    非同期APIクライアントの並行処理パターン検証（100並行リクエスト）

    NOTE: respxはネットワークI/Oをバイパスするため、実行時間の計測は意味がない。
    このテストは100並行リクエストが正しく処理されることを検証する。

    注意：このテストは時間がかかるため、slowマーカーを付与
    実行時は pytest -m slow で個別実行を推奨
    """
    # 各ユーザーエンドポイントをrespxでモック化（1〜100）
    routes = [
        respx.get(f"{BASE_URL}/users/{i}").respond(json={"id": i, "name": "Test"})
        for i in range(1, 101)
    ]

    async with AsyncAPIClient() as client:
        # 100回の並行リクエスト実行
        tasks = [client.get(f"/users/{i}") for i in range(1, 101)]
        results = await asyncio.gather(*tasks)

    # 全100リクエストが成功したことを検証
    assert len(results) == 100
    # 全ルートが各1回ずつ呼ばれたことを確認（並行実行の証明）
    assert all(r.call_count == 1 for r in routes)


@respx.mock
async def test_http_put_method():
    """
    AsyncAPIClient.put()メソッドの基本動作検証

    検証項目：
    - PUTリクエストが正しく送信される
    - JSONデータが正確に送信される
    - レスポンスが正常に返却される
    - HTTPメソッドが"PUT"である
    """
    endpoint = "/posts/1"
    update_data = {"id": 1, "title": "Updated Title", "body": "Updated Content", "userId": 1}

    # PUTレスポンスをモック化
    respx.put(f"{BASE_URL}{endpoint}").respond(status_code=200, json=update_data)

    # テスト実行
    async with AsyncAPIClient() as client:
        response = await client.put(endpoint, json=update_data)

    # 結果検証
    assert response.status_code == 200
    json_data = response.json()
    assert json_data == update_data
    assert json_data["title"] == "Updated Title"


@respx.mock
async def test_http_delete_method():
    """
    AsyncAPIClient.delete()メソッドの基本動作検証

    検証項目：
    - DELETEリクエストが正しく送信される
    - 204 No Content または 200 OK が返却される
    - エンドポイントが正確に構築される
    """
    endpoint = "/posts/1"

    # DELETEレスポンスをモック化（204 No Content）
    respx.delete(f"{BASE_URL}{endpoint}").respond(status_code=204)

    # テスト実行
    async with AsyncAPIClient() as client:
        response = await client.delete(endpoint)

    # 結果検証
    assert response.status_code == 204


@respx.mock
async def test_http_patch_method():
    """
    AsyncAPIClient.patch()メソッドの基本動作検証

    検証項目：
    - PATCHリクエストが正しく送信される
    - 部分更新データが正確に送信される
    - レスポンスが正常に返却される
    - HTTPメソッドが"PATCH"である
    """
    endpoint = "/posts/1"
    partial_data = {"title": "Partially Updated Title"}
    full_response = {
        "id": 1,
        "title": "Partially Updated Title",
        "body": "Original Content",
        "userId": 1,
    }

    # PATCHレスポンスをモック化
    respx.patch(f"{BASE_URL}{endpoint}").respond(status_code=200, json=full_response)

    # テスト実行
    async with AsyncAPIClient() as client:
        response = await client.patch(endpoint, json=partial_data)

    # 結果検証
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["title"] == "Partially Updated Title"
    assert json_data["body"] == "Original Content"  # 未更新フィールドは保持


@respx.mock
async def test_http_put_with_error():
    """
    AsyncAPIClient.put()の404エラーケーステスト

    検証項目：
    - 存在しないリソースへのPUTで404エラー
    - APIHTTPErrorが正しく発生する
    - エラーステータスコードが404である
    """
    endpoint = "/posts/999999"
    update_data = {"title": "Non-existent Post"}

    # 404レスポンスをモック化
    respx.put(f"{BASE_URL}{endpoint}").respond(status_code=404)

    # テスト実行
    async with AsyncAPIClient() as client:
        with pytest.raises(APIHTTPError) as exc_info:
            await client.put(endpoint, json=update_data)

        # エラー詳細検証
        assert exc_info.value.status_code == 404


async def test_async_client_timeout_zero_not_overridden() -> None:
    """timeout=0.0がデフォルト設定値に上書きされないことを確認（r2850768833回帰テスト）

    httpxでは timeout=0.0 は即座にタイムアウト（TimeoutException発生）する設定値。
    falsyな値として `or` パターンで設定値に上書きされてはならない。

    AsyncAPIClientは非同期コンテキストマネージャーのため async with で使用するが、
    timeout属性は __init__ で設定されるため、エントリー直後に検証可能。
    """
    async with AsyncAPIClient(timeout=0.0) as client:
        assert client.timeout == 0.0, (
            "timeout=0.0 はhttpxで有効な設定値（即座にタイムアウト）のため"
            "デフォルト設定値に上書きされてはならない"
        )


@pytest.mark.parametrize(
    "base_url",
    INVALID_BASE_URLS,
    ids=["empty", "whitespace", "tab", "newline"],
)
def test_async_client_base_url_validation_raises_value_error(base_url: str) -> None:
    """base_url が空・空白・タブ・改行の場合、初期化時に ValueError が発生する

    Security Rationale:
        空文字列: httpx.AsyncClient に渡ると実行時に InvalidURL が発生し原因特定が困難。
        初期化時の早期検証で設定ミスを即座に検出する。

        空白バイパス: bool("   ") == True のため `if not self.base_url` を通過する。
        str.strip() による追加検証が必要。

        タブ・改行: URL設定時の見えない制御文字バイパスを防ぐ。
    """
    with pytest.raises(ValueError, match="base_url が空です"):
        AsyncAPIClient(base_url=base_url)


async def test_async_client_falsy_values_not_overridden() -> None:
    """falsy値(0, 0.0)がデフォルト設定値に上書きされないことを検証

    退行防止（r2850768833回帰テスト）:
    修正前の `x or default` パターンでは retry_count=0 や
    timeout=0.0 がFalsyと判定され設定値で上書きされていた。
    `x if x is not None else default` への修正が正しく動作することを保証する。
    """
    async with AsyncAPIClient(
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
@patch("utils.jsonplaceholder_base_async.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_retry_on_server_error_then_success(mock_backoff: Mock) -> None:
    """サーバーエラー後に成功するケース（5xxはリトライ対象）"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.Response(500),  # 初回: 失敗
        httpx.Response(500),  # リトライ1回目: 失敗
        httpx.Response(200, json={"id": 1, "title": "test"}),  # リトライ2回目: 成功
        # Note: retry_count=3（最大4回呼び出し可能）だが、
        # 2回目のリトライで成功するためリストは3要素で十分
    ]

    async with AsyncAPIClient(retry_count=3) as client:
        response = await client.get("/posts/1")

    assert route.call_count == 3
    assert response.status_code == 200
    # バックオフが2回呼ばれることを確認（attempt 0, 1で失敗→backoff、attempt 2で成功）
    assert mock_backoff.call_count == 2


@respx.mock
@patch("utils.jsonplaceholder_base_async.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_retry_exhausted(mock_backoff: Mock) -> None:
    """リトライ上限でAPIRetryErrorが発生することを確認（5xxのみリトライ）"""
    retry_count = 2
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [httpx.Response(500)] * (retry_count + 1)  # 初回 + リトライ数

    async with AsyncAPIClient(retry_count=retry_count) as client:
        with pytest.raises(APIRetryError) as exc_info:
            await client.get("/posts/1")

    # リトライ回数+1回（初回+リトライ{retry_count}回={retry_count + 1}回）実行されたことを確認
    assert route.call_count == retry_count + 1
    assert f"Async request failed after {retry_count + 1} attempts" in str(exc_info.value)
    # バックオフがretry_count回呼ばれることを確認（最後の試行ではバックオフなし）
    assert mock_backoff.call_count == retry_count


@respx.mock
@patch("utils.jsonplaceholder_base_async.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_4xx_error_no_retry(mock_backoff: Mock) -> None:
    """4xxクライアントエラーはリトライせず即座にAPIHTTPErrorを発生"""
    route = respx.get(f"{BASE_URL}/posts/999")
    route.side_effect = [
        httpx.Response(404),
    ]

    async with AsyncAPIClient(retry_count=3) as client:
        with pytest.raises(APIHTTPError) as exc_info:
            await client.get("/posts/999")

    # 4xxエラーはリトライしない（1回のみ実行）
    assert route.call_count == 1
    assert exc_info.value.status_code == 404
    # 4xxは即raise、バックオフに到達しないことを確認
    assert mock_backoff.call_count == 0


@respx.mock
@patch("utils.jsonplaceholder_base_async.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_timeout_error_retry(mock_backoff: Mock) -> None:
    """タイムアウト時にAPIRetryErrorが発生することを確認"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.TimeoutException("Request timed out"),
        httpx.TimeoutException("Request timed out"),
    ]

    async with AsyncAPIClient(retry_count=1) as client:
        with pytest.raises(APIRetryError) as exc_info:
            await client.get("/posts/1")

    # リトライが実行されることを確認（初回+リトライ1回=2回）
    assert route.call_count == 2
    assert isinstance(exc_info.value.__cause__, APITimeoutError)
    # バックオフが1回呼ばれることを確認（最後の試行ではバックオフなし）
    assert mock_backoff.call_count == 1


@respx.mock
@patch("utils.jsonplaceholder_base_async.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_timeout_then_success(mock_backoff: Mock) -> None:
    """タイムアウト後に成功するケース"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.TimeoutException("Timeout 1"),
        httpx.Response(200, json={"id": 1}),
    ]

    async with AsyncAPIClient(retry_count=2) as client:
        response = await client.get("/posts/1")

    assert route.call_count == 2
    assert response.status_code == 200
    # バックオフが1回呼ばれることを確認（attempt 0で失敗→backoff、attempt 1で成功）
    assert mock_backoff.call_count == 1


@respx.mock
@patch("utils.jsonplaceholder_base_async.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_connection_error_retry(mock_backoff: Mock) -> None:
    """接続エラー時にAPIRetryErrorが発生することを確認"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.ConnectError("Connection refused"),
        httpx.ConnectError("Connection refused"),
    ]

    async with AsyncAPIClient(retry_count=1) as client:
        with pytest.raises(APIRetryError) as exc_info:
            await client.get("/posts/1")

    assert route.call_count == 2
    assert isinstance(exc_info.value.__cause__, APIConnectionError)
    # バックオフが1回呼ばれることを確認（最後の試行ではバックオフなし）
    assert mock_backoff.call_count == 1


@respx.mock
@patch("utils.jsonplaceholder_base_async.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_connection_then_success(mock_backoff: Mock) -> None:
    """接続エラー後に成功するケース"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.ConnectError("Connection 1"),
        httpx.ConnectError("Connection 2"),
        httpx.Response(200, json={"id": 1}),
    ]

    async with AsyncAPIClient(retry_count=3) as client:
        response = await client.get("/posts/1")

    assert route.call_count == 3
    assert response.status_code == 200
    # バックオフが2回呼ばれることを確認（attempt 0, 1で失敗→backoff、attempt 2で成功）
    assert mock_backoff.call_count == 2


@respx.mock
@patch("utils.jsonplaceholder_base_async.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_mixed_errors_then_success(mock_backoff: Mock) -> None:
    """タイムアウト→サーバーエラー→成功のシナリオ"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.TimeoutException("Timeout"),
        httpx.Response(503),
        httpx.Response(200, json={"id": 1}),
    ]

    async with AsyncAPIClient(retry_count=3) as client:
        response = await client.get("/posts/1")

    assert route.call_count == 3
    assert response.status_code == 200
    # バックオフが2回呼ばれることを確認（attempt 0, 1で失敗→backoff、attempt 2で成功）
    assert mock_backoff.call_count == 2


@respx.mock
@patch("utils.jsonplaceholder_base_async.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_mixed_errors_exhaust_retries(mock_backoff: Mock) -> None:
    """複数のエラータイプでリトライ上限に達するケース"""
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.TimeoutException("Timeout"),
        httpx.ConnectError("Connection failed"),
        httpx.Response(500),
    ]

    async with AsyncAPIClient(retry_count=2) as client:
        with pytest.raises(APIRetryError) as exc_info:
            await client.get("/posts/1")

    assert route.call_count == 3
    # 最後のエラー（500 Server Error）が__causeとして記録されていることを確認
    assert isinstance(exc_info.value.__cause__, APIHTTPError)
    # バックオフが2回呼ばれることを確認（最後の試行ではバックオフなし）
    assert mock_backoff.call_count == 2


@respx.mock
@patch("utils.jsonplaceholder_base_async.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_post_with_retry(mock_backoff: Mock) -> None:
    """POSTリクエストのリトライ動作確認（5xxはリトライ対象）"""
    route = respx.post(f"{BASE_URL}/posts")
    route.side_effect = [
        httpx.Response(502),
        httpx.Response(201, json={"id": 101, "title": "created"}),
    ]

    async with AsyncAPIClient(retry_count=2) as client:
        response = await client.post(
            "/posts",
            json={"title": "test", "body": "content", "userId": 1},
        )

    assert route.call_count == 2
    assert response.status_code == 201
    # バックオフが1回呼ばれることを確認（attempt 0で502失敗→backoff、attempt 1で成功）
    assert mock_backoff.call_count == 1


@respx.mock
@patch("utils.jsonplaceholder_base_async.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_put_4xx_no_retry(mock_backoff: Mock) -> None:
    """PUTリクエストで4xxエラーはリトライせず即座にAPIHTTPErrorを発生"""
    route = respx.put(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.Response(400),
    ]

    async with AsyncAPIClient(retry_count=3) as client:
        with pytest.raises(APIHTTPError) as exc_info:
            await client.put("/posts/1", json={"title": "updated"})

    # 4xxエラーはリトライしない（1回のみ実行）
    assert route.call_count == 1
    assert exc_info.value.status_code == 400
    # 4xxは即raise、バックオフに到達しないことを確認
    assert mock_backoff.call_count == 0


@respx.mock
@patch("utils.jsonplaceholder_base_async.exponential_backoff_with_jitter", return_value=0.0)
async def test_async_delete_with_retry(mock_backoff: Mock) -> None:
    """DELETEリクエストのリトライ動作確認"""
    route = respx.delete(f"{BASE_URL}/posts/1")
    route.side_effect = [
        httpx.TimeoutException("Timeout"),
        httpx.Response(200),
    ]

    async with AsyncAPIClient(retry_count=2) as client:
        response = await client.delete("/posts/1")

    assert route.call_count == 2
    assert response.status_code == 200
    # バックオフが1回呼ばれることを確認（attempt 0でTimeout失敗→backoff、attempt 1で成功）
    assert mock_backoff.call_count == 1


@pytest.mark.parametrize(
    "exc",
    [
        httpx.TooManyRedirects("Max redirects exceeded"),
        httpx.InvalidURL("Invalid URL format"),
    ],
)
@respx.mock
async def test_async_non_retryable_error_logs_before_raise(
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
            async with AsyncAPIClient(retry_count=0) as client:
                await client.get("/posts/1")

    # ERRORレベルのログが出力されていることを検証（ログバイパスが修正済み）
    error_logs = [
        log
        for log in log_output
        if log.get("log_level") == "error" and log.get("event") == "request_error_non_retryable"  # noqa: E501
    ]
    assert len(error_logs) == 1, f"Expected 1 error log, got: {log_output}"
    assert error_logs[0]["method"] == "GET"
    assert error_logs[0]["endpoint"] == "/posts/1"
    assert "error" not in error_logs[0]  # security: 認証情報漏洩防止
    assert "error_type" in error_logs[0]  # error_type フィールドの存在確認
    assert error_logs[0]["is_async"] is True  # AsyncAPIClient 呼び出しの確認


@respx.mock
async def test_async_non_retryable_error_skips_retry() -> None:
    """retry_count>=1設定時でも非リトライエラーはリトライループを即 raise で脱出する

    TooManyRedirects/InvalidURL は即 raise のため、
    retry_count を増やしても1回のみの試行で APIClientError が発生する。
    """
    route = respx.get(f"{BASE_URL}/posts/1")
    route.side_effect = httpx.TooManyRedirects("Max redirects exceeded")

    with pytest.raises(APIClientError, match="Non-retryable request error"):
        async with AsyncAPIClient(retry_count=2) as client:
            await client.get("/posts/1")

    # リトライされていないことを確認
    assert route.call_count == 1, "非リトライエラーは1回のみ試行される"


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

    従来は None.request アクセスで AttributeError になっていたが、
    use-after-close を明示的な RuntimeError として通知する（github_client.py L878 と同一パターン）。
    """
    client = AsyncAPIClient(base_url="https://test.com")
    # close 後の状態をシミュレート（_client を None に強制設定）
    client._client = None
    with pytest.raises(RuntimeError, match="Client not initialized"):
        await client._make_request_with_retry("GET", "/test")


async def test_async_client_headers_empty_dict_preserves_defaults(mock_base_url: str) -> None:
    """AsyncAPIClient: headers={} でデフォルトヘッダーが保持される

    `if headers is not None:` の設計を保証するテスト。
    空辞書を渡しても update({}) は no-op なので、デフォルトヘッダーは変わらない。
    """
    async with AsyncAPIClient(base_url=mock_base_url, headers={}) as client:
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
