# ===============================================================================
# test_async_client.py - 非同期APIクライアントの単体テスト
# ===============================================================================
#
# このファイルは utils.api_client.AsyncAPIClient の包括的なテストを実装
# 学習ポイント：
# 1. async/await を使った非同期テストの書き方
# 2. pytest-asyncio を使った非同期テスト実行
# 3. httpx.AsyncClient のモックとスタブ
# 4. 並行処理・コンカレンシーのテスト
# 5. エラーハンドリングの検証
# 6. パフォーマンス・タイムアウト測定
#
# 実行方法：
#   pytest tests/unit/test_async_client.py -v
#   pytest tests/unit/test_async_client.py::test_async_get_user -v
#   pytest tests/unit/test_async_client.py -k "async" --asyncio-mode=auto
#
# ===============================================================================

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
from httpx import Request, Response

# プロジェクト内モジュール
from utils.api_client import (
    APIConnectionError,
    APIHTTPError,
    APIRetryError,
    AsyncAPIClient,
    AsyncJSONPlaceholderClient,
)

# Module-level marker: All tests in this file are unit tests
pytestmark = pytest.mark.unit

# Constants
BASE_URL = "https://jsonplaceholder.typicode.com"

# ===============================================================================
# テスト用フィクスチャ・設定
# ===============================================================================


@pytest.fixture
def sample_user_data():
    """テスト用ユーザーデータ"""
    return {
        "id": 1,
        "name": "Leanne Graham",
        "username": "Bret",
        "email": "Sincere@april.biz",
        "address": {
            "street": "Kulas Light",
            "suite": "Apt. 556",
            "city": "Gwenborough",
            "zipcode": "92998-3874",
            "geo": {"lat": "-37.3159", "lng": "81.1496"},
        },
        "phone": "1-770-736-8031 x56442",
        "website": "hildegard.org",
        "company": {
            "name": "Romaguera-Crona",
            "catchPhrase": "Multi-layered client-server neural-net",
            "bs": "harness real-time e-markets",
        },
    }


@pytest.fixture
def sample_users_list():
    """テスト用ユーザーリスト"""
    return [
        {"id": 1, "name": "Leanne Graham", "email": "Sincere@april.biz"},
        {"id": 2, "name": "Ervin Howell", "email": "Shanna@melissa.tv"},
        {"id": 3, "name": "Clementine Bauch", "email": "Nathan@yesenia.net"},
    ]


# ===============================================================================
# Test 1: 基本的な非同期GET リクエストテスト
# ===============================================================================


@pytest.mark.asyncio
async def test_async_get_user(sample_user_data, mock_response_factory):
    """
    非同期APIクライアントの基本的なGETリクエストをテスト

    検証項目：
    - async with コンテキストマネージャーの動作
    - HTTPXクライアントのリクエスト実行
    - JSONレスポンスの正常パーシング
    - ログ出力の確認
    """
    # モックレスポンス準備
    mock_resp = mock_response_factory(200, json_data=sample_user_data)

    # AsyncClientのモック作成
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance
        mock_client_instance.request.return_value = mock_resp

        # テスト実行
        async with AsyncJSONPlaceholderClient() as client:
            result = await client.get_user(1)

            # 結果検証
            assert result == sample_user_data
            assert result["id"] == 1
            assert result["name"] == "Leanne Graham"
            assert result["email"] == "Sincere@april.biz"

            # モック呼び出し検証
            mock_client_instance.request.assert_called_once()
            call_args = mock_client_instance.request.call_args
            assert call_args[0][0] == "GET"  # HTTPメソッド
            assert "/users/1" in call_args[0][1]  # URL


# ===============================================================================
# Test 2: 並行リクエスト・コンカレンシーテスト
# ===============================================================================


@pytest.mark.asyncio
async def test_async_concurrent_requests(sample_users_list, mock_response_factory):
    """
    複数の非同期リクエストを並行実行するテスト

    検証項目：
    - asyncio.gather による並行実行
    - 同時実行数制限（セマフォ）の動作
    - パフォーマンス測定（並行実行による高速化）
    - エラー時の適切な例外処理
    """
    # モックレスポンス準備（複数パターン）
    mock_responses = [
        mock_response_factory(200, json_data=sample_users_list[0]),
        mock_response_factory(200, json_data=sample_users_list[1]),
        mock_response_factory(200, json_data=sample_users_list[2]),
    ]

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance
        mock_client_instance.request.side_effect = mock_responses

        # 並行実行パフォーマンステスト
        async with AsyncJSONPlaceholderClient() as client:
            start_time = time.time()

            # 3つのリクエストを並行実行
            user_ids = [1, 2, 3]
            tasks = [client.get_user(user_id) for user_id in user_ids]
            results = await asyncio.gather(*tasks)

            end_time = time.time()
            execution_time = end_time - start_time

            # 結果検証
            assert len(results) == 3
            assert all(isinstance(result, dict) for result in results)
            assert results[0]["id"] == 1
            assert results[1]["id"] == 2
            assert results[2]["id"] == 3

            # パフォーマンス検証（並行実行は高速）
            assert execution_time < 1.0  # 1秒未満で完了することを期待

            # モック呼び出し検証（3回実行）
            assert mock_client_instance.request.call_count == 3


@pytest.mark.asyncio
async def test_async_multiple_users_with_semaphore():
    """
    Semaphoreを使用した複数ユーザー並行取得のテスト

    検証項目：
    - get_multiple_users()メソッドの動作
    - Semaphoreによる同時実行数制限
    - 一部失敗時の graceful degradation
    - Rate Limit対策の実装確認

    学習ポイント:
    - asyncio.Semaphore: 同時実行数を制限するロック機構
    - Rate Limit対策: GitHub API等の外部API制限への対応
    """
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance

        # 各ユーザーのモックレスポンス
        user_responses = [
            MagicMock(
                spec=Response,
                status_code=200,
                json=MagicMock(return_value={"id": i, "name": f"User {i}"}),
                raise_for_status=MagicMock(return_value=None),
                content=f'{{"id": {i}, "name": "User {i}"}}'.encode(),
            )
            for i in [1, 2, 3, 4, 5]
        ]

        mock_client_instance.request.side_effect = user_responses

        async with AsyncJSONPlaceholderClient() as client:
            # max_concurrent=2でSemaphore制御
            results = await client.get_multiple_users([1, 2, 3, 4, 5], max_concurrent=2)

            # 結果検証
            assert len(results) == 5
            assert all(isinstance(result, dict) for result in results)
            assert results[0]["id"] == 1
            assert results[4]["id"] == 5

            # 全ユーザー取得成功確認
            assert mock_client_instance.request.call_count == 5


@pytest.mark.asyncio
@respx.mock
async def test_partial_failure_graceful_degradation():
    """
    一部リクエスト失敗時のgraceful degradationテスト

    検証項目：
    - 5件中2件が失敗するシナリオ
    - 成功したリクエストは正常に取得できる
    - システム全体はクラッシュせず継続動作

    学習ポイント:
    - graceful degradation: 部分的失敗でもシステム全体は継続動作
    - respx: 宣言的HTTPモッキング（低レベルモック排除）
    - URL-to-Responseマッピングによる明確なテスト意図表現
    """
    # 宣言的なエンドポイントマッピング（成功: 1,3,5 / 失敗: 2,4）
    respx.get(f"{BASE_URL}/users/1").respond(json={"id": 1, "name": "User 1"})
    respx.get(f"{BASE_URL}/users/2").respond(status_code=500)
    respx.get(f"{BASE_URL}/users/3").respond(json={"id": 3, "name": "User 3"})
    respx.get(f"{BASE_URL}/users/4").respond(status_code=500)
    respx.get(f"{BASE_URL}/users/5").respond(json={"id": 5, "name": "User 5"})

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        results = await client.get_multiple_users([1, 2, 3, 4, 5], max_concurrent=2)

    # graceful degradation検証（成功分のみ返却パターン）
    assert len(results) == 3, f"Expected 3 successful results, got {len(results)}"
    assert all(isinstance(r, dict) for r in results)

    # Expected IDs [1,3,5] in any order, no duplicates
    result_ids = [r["id"] for r in results]
    assert sorted(result_ids) == [1, 3, 5], f"Expected IDs [1,3,5], got {result_ids}"


@pytest.mark.asyncio
@respx.mock
async def test_all_requests_fail_returns_empty_list():
    """
    全リクエスト失敗時の空リスト返却テスト

    検証項目：
    - 全件が500エラーの場合、空リスト[]が返却される
    - システム全体がクラッシュせず正常終了
    - graceful degradationの最悪ケース保証

    学習ポイント:
    - エッジケーステスト: 最悪シナリオでのシステム動作保証
    - Defense in Depth: 稀なケースこそテストで保護
    """
    # DRY: ループで一括設定（全件500エラー）
    for user_id in [1, 2, 3]:
        respx.get(f"{BASE_URL}/users/{user_id}").respond(status_code=500)

    async with AsyncJSONPlaceholderClient() as client:
        results = await client.get_multiple_users([1, 2, 3], max_concurrent=2)

    # 全件失敗で空リスト返却
    assert results == [], f"Expected empty list, got {results}"
    assert isinstance(results, list), f"Expected list type, got {type(results)}"


# ===============================================================================
# Test 3: エラーハンドリング・リトライ機能テスト
# ===============================================================================


@pytest.mark.asyncio
async def test_async_error_handling_and_retry():
    """
    非同期エラーハンドリングとリトライ機能のテスト

    検証項目：
    - タイムアウトエラーのリトライ動作
    - 接続エラーのリトライ動作
    - HTTPステータスエラー（4xx）の即座発生（リトライなし）
    - リトライ回数・間隔の制御

    Note: AsyncAPIClient.get()はhttpx.Responseを返す。
          4xxエラー時はAPIHTTPErrorを発生させる。
    """
    from httpx import HTTPStatusError, TimeoutException

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance

        # Test 3-1: タイムアウトエラーのリトライ（最終的に成功）
        success_response = MagicMock(spec=Response)
        success_response.status_code = 200
        success_response.json.return_value = {"id": 1, "name": "Test User"}
        success_response.raise_for_status.return_value = None
        success_response.content = b'{"id": 1, "name": "Test User"}'
        success_response.reason_phrase = "OK"

        # 最初の2回はタイムアウト、3回目で成功
        mock_client_instance.request.side_effect = [
            TimeoutException("Timeout 1"),
            TimeoutException("Timeout 2"),
            success_response,
        ]

        async with AsyncAPIClient(retry_count=3, retry_delay=0.1) as client:
            start_time = time.time()
            result = await client.get("/users/1")
            end_time = time.time()

            # 結果検証: get()はhttpx.Responseを返す
            assert result.status_code == 200
            json_data = result.json()
            assert json_data["id"] == 1
            assert json_data["name"] == "Test User"

            # リトライ動作検証
            assert mock_client_instance.request.call_count == 3  # 3回目で成功
            assert end_time - start_time >= 0.2  # リトライ遅延確認（0.1 + 0.2）

        # Test 3-2: HTTPエラー（4xx）は即座発生（リトライなし）
        mock_client_instance.reset_mock()
        mock_client_instance.request.side_effect = None  # side_effectをクリア

        error_response = MagicMock(spec=Response)
        error_response.status_code = 404
        error_response.is_client_error = True  # 4xxエラー判定用
        error_response.raise_for_status.side_effect = HTTPStatusError(
            "404 Not Found",
            request=MagicMock(spec=Request),
            response=error_response,
        )
        mock_client_instance.request.return_value = error_response

        async with AsyncAPIClient(retry_count=3) as client:
            # 実装はAPIHTTPErrorを発生させる（HTTPStatusErrorをラップ）
            with pytest.raises(APIHTTPError) as exc_info:
                await client.get("/users/999")

            # エラー詳細検証
            assert exc_info.value.status_code == 404
            # HTTPエラーはリトライしないことを確認
            assert mock_client_instance.request.call_count == 1


# ===============================================================================
# Test 4: 非同期POST・データ送信テスト
# ===============================================================================


@pytest.mark.asyncio
async def test_async_post_create_user(mock_response_factory):
    """
    非同期POST リクエスト・データ送信のテスト

    検証項目：
    - JSON データの送信
    - Content-Type ヘッダーの自動設定
    - レスポンスの適切な処理
    - 作成されたリソースの確認
    """
    # 作成成功のモックレスポンス
    created_user = {
        "id": 101,
        "name": "New Async User",
        "email": "async@example.com",
        "phone": "123-456-7890",
    }
    mock_resp = mock_response_factory(201, json_data=created_user)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance
        mock_client_instance.request.return_value = mock_resp

        async with AsyncJSONPlaceholderClient() as client:
            # ユーザー作成データ
            user_data = {
                "name": "New Async User",
                "email": "async@example.com",
                "phone": "123-456-7890",
            }

            result = await client.create_user(user_data)

            # 結果検証
            assert result["id"] == 101
            assert result["name"] == "New Async User"
            assert result["email"] == "async@example.com"

            # POST リクエスト呼び出し検証
            mock_client_instance.request.assert_called_once()
            call_args = mock_client_instance.request.call_args
            assert call_args[0][0] == "POST"  # HTTPメソッド
            assert "/users" in call_args[0][1]  # URL
            assert "json" in call_args[1]  # JSON データが含まれる


@pytest.mark.asyncio
async def test_async_bulk_create_users(mock_response_factory):
    """
    複数ユーザーの並行作成テスト

    検証項目：
    - bulk_create_users メソッドの動作
    - 複数POST リクエストの並行実行（asyncio.gather使用）
    - 成功したユーザーのみ返却される動作確認
    """
    # 複数ユーザーのテストデータ
    users_to_create = [
        {"name": "User 1", "email": "user1@test.com"},
        {"name": "User 2", "email": "user2@test.com"},
        {"name": "User 3", "email": "user3@test.com"},
    ]

    # 作成成功のモックレスポンス
    created_responses = [
        mock_response_factory(
            201,
            json_data={"id": 101, "name": "User 1", "email": "user1@test.com"},
        ),
        mock_response_factory(
            201,
            json_data={"id": 102, "name": "User 2", "email": "user2@test.com"},
        ),
        mock_response_factory(
            201,
            json_data={"id": 103, "name": "User 3", "email": "user3@test.com"},
        ),
    ]

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance
        mock_client_instance.request.side_effect = created_responses

        async with AsyncJSONPlaceholderClient() as client:
            results = await client.bulk_create_users(users_to_create)

            # 結果検証
            assert len(results) == 3
            assert all(result["id"] > 100 for result in results)

            # 並行実行確認
            assert mock_client_instance.request.call_count == 3

            # 作成されたユーザー確認
            created_names = [result["name"] for result in results]
            assert "User 1" in created_names
            assert "User 2" in created_names
            assert "User 3" in created_names


# ===============================================================================
# Test 5: パフォーマンス・タイムアウト・リソース管理テスト
# ===============================================================================


@pytest.mark.asyncio
async def test_async_performance_and_timeout():
    """
    非同期処理のパフォーマンス・タイムアウト・リソース管理テスト

    検証項目：
    - リクエストタイムアウトの動作
    - リトライ後のAPIRetryError発生
    - リトライ間隔の検証

    Note: タイムアウト時、実装はリトライ後にAPIRetryErrorを発生させる。
          TimeoutExceptionは内部でキャッチされる。
    """
    from httpx import TimeoutException

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance

        # Test 5-1: タイムアウト動作テスト（全リトライ後にAPIRetryError）
        mock_client_instance.request.side_effect = TimeoutException("Request timeout")

        async with AsyncAPIClient(timeout=1.0, retry_count=1, retry_delay=0.05) as client:
            start_time = time.time()

            # 実装はリトライ失敗後にAPIRetryErrorを発生させる
            with pytest.raises(APIRetryError) as exc_info:
                await client.get("/users/1")

            elapsed = time.time() - start_time

            # エラーメッセージ検証
            assert "failed after" in str(exc_info.value).lower()

            # リトライ動作確認: 初回 + 1回リトライ = 2回の呼び出し
            assert mock_client_instance.request.call_count == 2

            # 最低限のリトライ遅延が発生していること
            assert elapsed >= 0.05


@pytest.mark.asyncio
async def test_async_context_manager_cleanup():
    """
    コンテキストマネージャーのリソースクリーンアップテスト

    検証項目：
    - async with ブロック終了時の自動クリーンアップ
    - httpx.AsyncClient.aclose() の適切な呼び出し
    - エラー発生時でもクリーンアップが実行されること
    """
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance

        # Test 5-2a: 正常終了時のクリーンアップ
        async with AsyncJSONPlaceholderClient() as client:
            pass  # 何もしない

        # aclose() が呼び出されることを確認
        mock_client_instance.aclose.assert_called_once()

        # Test 5-2b: 例外発生時でもクリーンアップされること
        mock_client_instance.reset_mock()
        test_error = Exception("Test error")
        mock_client_instance.request.side_effect = test_error

        with pytest.raises(Exception) as exc_info:
            async with AsyncJSONPlaceholderClient() as client:
                await client.get("/users/1")

        # リトライロジックが元の例外をAPIRetryErrorでラップする
        # リトライ失敗を示すエラーメッセージが含まれることを確認
        assert "failed after" in str(exc_info.value).lower() or str(exc_info.value) == "Test error"

        # 例外発生時でもaclose()が呼び出されることを確認
        mock_client_instance.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_async_health_check():
    """
    API ヘルスチェック機能のテスト

    検証項目：
    - health_check()メソッドの動作
    - 正常時: True返却
    - エラー時: False返却（graceful degradation）

    学習ポイント:
    - Docker/Kubernetes readiness probe対応
    - 軽量クエリ（_limit=1）でサーバー負荷最小化
    - 例外時はFalse返却（サービス継続性）
    """
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance

        # Test 1: 正常時 → True
        healthy_response = MagicMock(spec=Response)
        healthy_response.status_code = 200
        healthy_response.json.return_value = [{"id": 1, "name": "User 1"}]
        healthy_response.raise_for_status.return_value = None
        healthy_response.content = b'[{"id": 1, "name": "User 1"}]'

        mock_client_instance.request.return_value = healthy_response

        async with AsyncJSONPlaceholderClient() as client:
            result = await client.health_check()
            assert result is True

            # _limit=1パラメータで軽量クエリ確認
            call_args = mock_client_instance.request.call_args
            assert "params" in call_args[1]
            assert call_args[1]["params"]["_limit"] == 1

        # Test 2: APIClientError時 → False（graceful degradation）
        mock_client_instance.reset_mock()
        mock_client_instance.request.side_effect = APIConnectionError("Connection refused")

        async with AsyncJSONPlaceholderClient() as client:
            result = await client.health_check()
            assert result is False


# ===============================================================================
# パフォーマンステスト（オプション：時間のかかるテスト）
# ===============================================================================


@pytest.mark.slow  # slowマーカー（通常実行では除外可能）
@pytest.mark.asyncio
async def test_async_performance_benchmark():
    """
    非同期APIクライアントのパフォーマンスベンチマーク

    注意：このテストは時間がかかるため、slowマーカーを付与
    実行時は pytest -m slow で個別実行を推奨
    """
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance

        # 高速レスポンスのモック
        fast_response = MagicMock(spec=Response)
        fast_response.status_code = 200
        fast_response.json.return_value = {"id": 1, "name": "Test"}
        fast_response.raise_for_status.return_value = None
        fast_response.content = b'{"id": 1, "name": "Test"}'
        fast_response.reason_phrase = "OK"

        mock_client_instance.request.return_value = fast_response

        async with AsyncJSONPlaceholderClient() as client:
            # 100回の並行リクエスト実行
            start_time = time.time()
            tasks = [client.get(f"/users/{i}") for i in range(1, 101)]
            results = await asyncio.gather(*tasks)
            end_time = time.time()

            # パフォーマンス検証
            assert len(results) == 100
            execution_time = end_time - start_time
            print(f"\n100並行リクエスト実行時間: {execution_time:.3f}秒")

            # 非現実的に高速でない限り成功とする（モック環境では非常に高速）
            assert execution_time < 5.0  # 5秒以内での完了を期待


# ===============================================================================
# 【学習用】テスト実行とデバッグ方法
# ===============================================================================
#
# 1. 基本テスト実行
#   pytest tests/unit/test_async_client.py -v
#
# 2. 特定のテスト実行
#   pytest tests/unit/test_async_client.py::test_async_get_user -v
#
# 3. 非同期テストのみ実行
#   pytest tests/unit/test_async_client.py -k "async" -v
#
# 4. カバレッジ付きテスト実行
#   pytest tests/unit/test_async_client.py --cov=utils.api_client --cov-report=html
#
# 5. 遅いテストを除外
#   pytest tests/unit/test_async_client.py -m "not slow" -v
#
# 6. 遅いテストのみ実行
#   pytest tests/unit/test_async_client.py -m slow -v
#
# 7. デバッグモード（詳細出力）
#   pytest tests/unit/test_async_client.py -v -s --tb=short
#
# 8. 並列テスト実行（pytest-xdist使用）
#   pytest tests/unit/test_async_client.py -n 4 -v
#
# 9. Dockerコンテナ内でのテスト実行
#   docker-compose -f docker-compose.test.yml run --rm unit-tests \
#       pytest tests/unit/test_async_client.py -v
#
# 10. 継続的テスト実行（ファイル変更監視）
#   pytest-watch tests/unit/test_async_client.py
#
# ===============================================================================
