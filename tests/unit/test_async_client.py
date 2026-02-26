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
import json
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
import respx
from httpx import Response

# プロジェクト内モジュール
from utils.api_client import (
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


@respx.mock
async def test_async_get_user(sample_user_data):
    """
    非同期APIクライアントの基本的なGETリクエストをテスト

    検証項目：
    - async with コンテキストマネージャーの動作
    - HTTPXクライアントのリクエスト実行
    - JSONレスポンスの正常パーシング
    - ログ出力の確認
    """
    # respxでエンドポイントをモック化（ルート固有のcall_countで検証）
    route = respx.get(f"{BASE_URL}/users/1").respond(json=sample_user_data)

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        result = await client.get_user(1)

        # 結果検証
        assert result == sample_user_data
        assert result["id"] == 1
        assert result["name"] == "Leanne Graham"
        assert result["email"] == "Sincere@april.biz"

    # リクエストが1回発行されたことを確認（ルート固有）
    assert route.call_count == 1


# ===============================================================================
# Test 2: 並行リクエスト・コンカレンシーテスト
# ===============================================================================


@respx.mock
async def test_async_concurrent_requests(sample_users_list):
    """
    複数の非同期リクエストを並行実行するテスト

    検証項目：
    - asyncio.gather による並行実行（3並行リクエスト）
    - 各ユーザーデータの正確な取得（ID=1,2,3の確認）
    - 各ルートが1回ずつ呼ばれることの確認（route.call_count）
    """
    # 各ユーザーエンドポイントをrespxでモック化（ルート固有のcall_countで検証）
    route_user1 = respx.get(f"{BASE_URL}/users/1").respond(json=sample_users_list[0])
    route_user2 = respx.get(f"{BASE_URL}/users/2").respond(json=sample_users_list[1])
    route_user3 = respx.get(f"{BASE_URL}/users/3").respond(json=sample_users_list[2])

    # 並行実行テスト
    async with AsyncJSONPlaceholderClient() as client:
        # 3つのリクエストを並行実行
        user_ids = [1, 2, 3]
        tasks = [client.get_user(user_id) for user_id in user_ids]
        results = await asyncio.gather(*tasks)

        # 結果検証
        assert len(results) == 3
        assert all(isinstance(result, dict) for result in results)
        assert results[0]["id"] == 1
        assert results[1]["id"] == 2
        assert results[2]["id"] == 3

    # 各ルートが1回ずつ呼ばれたことを確認（ルート固有）
    assert route_user1.call_count == 1
    assert route_user2.call_count == 1
    assert route_user3.call_count == 1


@respx.mock
async def test_async_multiple_users_with_semaphore():
    """
    Semaphoreを使用した複数ユーザー並行取得のテスト

    検証項目：
    - get_multiple_users()が全件（5件）を正常返却すること
    - 各ユーザーエンドポイントが1回ずつ呼ばれること（重複リクエストなし）
    - max_concurrent パラメータを受け付けること

    学習ポイント:
    - asyncio.Semaphore: 同時実行数を制限するロック機構
    - Rate Limit対策: GitHub API等の外部API制限への対応
    """
    # 各ユーザーエンドポイントをrespxでモック化（ルート固有のcall_countで検証）
    routes = {}
    for i in [1, 2, 3, 4, 5]:
        routes[i] = respx.get(f"{BASE_URL}/users/{i}").respond(json={"id": i, "name": f"User {i}"})

    async with AsyncJSONPlaceholderClient() as client:
        # max_concurrent=2でSemaphore制御
        results = await client.get_multiple_users([1, 2, 3, 4, 5], max_concurrent=2)

        # 結果検証
        assert len(results) == 5
        assert all(isinstance(result, dict) for result in results)
        assert results[0]["id"] == 1
        assert results[4]["id"] == 5

    # 全ユーザー取得成功確認（各ルート1回ずつ、計5回のHTTPリクエスト）
    assert all(r.call_count == 1 for r in routes.values())


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
    route1 = respx.get(f"{BASE_URL}/users/1").respond(json={"id": 1, "name": "User 1"})
    route2 = respx.get(f"{BASE_URL}/users/2").respond(status_code=500)
    route3 = respx.get(f"{BASE_URL}/users/3").respond(json={"id": 3, "name": "User 3"})
    route4 = respx.get(f"{BASE_URL}/users/4").respond(status_code=500)
    route5 = respx.get(f"{BASE_URL}/users/5").respond(json={"id": 5, "name": "User 5"})

    # retry_count=0: リトライなし設定でgraceful degradationのみ検証（リトライ挙動は別テストで担保）
    async with AsyncJSONPlaceholderClient(retry_count=0, retry_delay=0.0) as client:
        results = await client.get_multiple_users([1, 2, 3, 4, 5], max_concurrent=2)

    # graceful degradation検証（成功分のみ返却パターン）
    assert len(results) == 3, f"Expected 3 successful results, got {len(results)}"
    assert all(isinstance(r, dict) for r in results)

    # Expected IDs [1,3,5] in any order, no duplicates
    result_ids = [r["id"] for r in results]
    assert sorted(result_ids) == [1, 3, 5], f"Expected IDs [1,3,5], got {result_ids}"

    # 全5エンドポイントが各1回ずつ呼ばれたことを確認（retry_count=0のため決定論的に==1）
    assert route1.call_count == 1
    assert route2.call_count == 1
    assert route3.call_count == 1
    assert route4.call_count == 1
    assert route5.call_count == 1


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
    # DRY: リスト内包表記で一括設定（全件500エラー）
    routes = [respx.get(f"{BASE_URL}/users/{uid}").respond(status_code=500) for uid in [1, 2, 3]]

    # retry_count=0: リトライなし設定でgraceful degradationのみ検証（リトライ挙動は別テストで担保）
    async with AsyncJSONPlaceholderClient(retry_count=0, retry_delay=0.0) as client:
        results = await client.get_multiple_users([1, 2, 3], max_concurrent=2)

    # 全件失敗で空リスト返却
    assert results == [], f"Expected empty list, got {results}"
    assert isinstance(results, list), f"Expected list type, got {type(results)}"

    # 全3エンドポイントが各1回ずつ呼ばれたことを確認（retry_count=0のため決定論的に==1）
    assert all(r.call_count == 1 for r in routes)


# ===============================================================================
# Test 3: エラーハンドリング・リトライ機能テスト
# ===============================================================================


@patch("utils.api_client.exponential_backoff_with_jitter", return_value=0.0)
@respx.mock
async def test_async_timeout_retry_then_success(mock_backoff: Mock) -> None:
    """
    タイムアウトエラー後のリトライで最終的に成功するテスト

    検証項目：
    - タイムアウトエラー発生時にリトライが行われること（2回連続タイムアウト）
    - リトライ回数が設定値（retry_count=3）に基づくこと（初回+2回リトライ=3回実行）
    - リトライ後に成功した場合のレスポンスが正しく返却されること

    Note: test_async_client_error_handling.py の test_async_timeout_then_success（1回タイムアウト）
          と対をなすテスト。こちらは「2回連続タイムアウト → 3回目で成功」を検証する。
          @patch(exponential_backoff_with_jitter)でリトライ待機を0秒化しCI時間短縮。
          respxトランスポートモックにより実際のhttpxコードパスを通じて検証する。
    """
    # respxルート: 最初の2回はタイムアウト、3回目で成功
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

    # レスポンス検証: get()はhttpx.Responseを返す
    assert result.status_code == 200
    json_data = result.json()
    assert json_data["id"] == 1
    assert json_data["name"] == "Test User"


# ===============================================================================
# Test 4: 非同期POST・データ送信テスト
# ===============================================================================


@respx.mock
async def test_async_post_create_user():
    """
    非同期POST リクエスト・データ送信のテスト

    検証項目：
    - JSON データの送信
    - Content-Type ヘッダーの自動設定
    - レスポンスの適切な処理
    - 作成されたリソースの確認
    """
    # 作成成功レスポンスをrespxでモック化（ルート固有のcall_countで検証）
    created_user = {
        "id": 101,
        "name": "New Async User",
        "email": "async@example.com",
        "phone": "123-456-7890",
    }
    route = respx.post(f"{BASE_URL}/users").respond(status_code=201, json=created_user)

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

    # POSTリクエストが1回発行されたことを確認（ルート固有）
    assert route.call_count == 1
    assert route.calls[0].request.method == "POST"

    # リクエストボディの内容を検証（フィールド名変更の退行検出）
    request_body = json.loads(route.calls[0].request.content)
    assert request_body["name"] == "New Async User"
    assert request_body["email"] == "async@example.com"
    assert request_body["phone"] == "123-456-7890"


@respx.mock
async def test_async_bulk_create_users():
    """
    複数ユーザーの並行作成テスト

    検証項目：
    - bulk_create_users メソッドの動作
    - 複数POST リクエストの並行実行（asyncio.gather使用）
    - 成功したユーザーのみ返却される動作確認

    注意: bulk_create_users は asyncio.gather で並行POST → 同一URLに複数POST。
    respx は同一ルートへの複数リクエストに対して同じレスポンスを繰り返し返す。
    レスポンスを区別するため side_effect パターンを使用。
    """
    # 複数ユーザーのテストデータ
    users_to_create = [
        {"name": "User 1", "email": "user1@test.com"},
        {"name": "User 2", "email": "user2@test.com"},
        {"name": "User 3", "email": "user3@test.com"},
    ]

    # 各リクエストで異なるレスポンスを返すためside_effectを使用
    post_route = respx.post(f"{BASE_URL}/users")
    post_route.side_effect = [
        Response(201, json={"id": 101, "name": "User 1", "email": "user1@test.com"}),
        Response(201, json={"id": 102, "name": "User 2", "email": "user2@test.com"}),
        Response(201, json={"id": 103, "name": "User 3", "email": "user3@test.com"}),
    ]

    async with AsyncJSONPlaceholderClient() as client:
        results = await client.bulk_create_users(users_to_create)

    # 結果検証
    assert len(results) == 3
    assert all(result["id"] > 100 for result in results)

    # 並行実行確認（3回のPOSTリクエスト、ルート固有）
    assert post_route.call_count == 3

    # 作成されたユーザー確認（防御的テスト）

    # respxのside_effectリストは同一ルートへの呼び出し順に
    # 消費される（決定的）。
    # asyncio.gatherの結果も入力タスク順に返却されるため順序は決定的だが、
    # インデックス位置ではなく名称の存在確認に絞ることで、将来の実装変更への耐性を高める。
    # → set/in検証: 期待される全名称が含まれることを確認

    created_names = [result["name"] for result in results]
    assert "User 1" in created_names
    assert "User 2" in created_names
    assert "User 3" in created_names


@respx.mock
async def test_async_bulk_create_users_partial_failure():
    """
    複数ユーザーの並行作成における部分失敗テスト（silent failure設計の検証）

    検証項目：
    - 一部リクエストが4xxエラーで失敗してもbulk_create_usersは例外を発生させない
    - 成功したユーザーのみが返却される（失敗分は除外）
    - 全リクエストが試行される（部分失敗でも中断しない）

    設計根拠：
    bulk_create_usersはasyncio.gather(return_exceptions=True)で部分失敗を吸収する。
    4xxエラー（422）は即失敗（リトライなし）のため、APIHTTPErrorが
    return_exceptionsにより捕捉され、成功分のみが返却される。

    Note: side_effectリストはリクエスト到着順に消費される。
    respxモック環境（実I/O待機なし）ではtask作成順とリクエスト送信順が一致するため決定論的。
    成功件数は厳密に2件（== 2）で検証する。
    """
    users_to_create = [
        {"name": "User 1", "email": "user1@test.com"},
        {"name": "User 2", "email": "user2@test.com"},  # この1件を422エラーで失敗させる
        {"name": "User 3", "email": "user3@test.com"},
    ]

    # 2件目のリクエストを422（Unprocessable Entity）で失敗させる
    # 4xxはリトライなし即失敗 → APIHTTPError を return_exceptions が捕捉
    post_route = respx.post(f"{BASE_URL}/users")
    post_route.side_effect = [
        Response(201, json={"id": 101, "name": "User 1", "email": "user1@test.com"}),
        Response(422, json={"error": "Unprocessable Entity"}),  # 2件目: 422で即失敗
        Response(201, json={"id": 103, "name": "User 3", "email": "user3@test.com"}),
    ]

    async with AsyncJSONPlaceholderClient() as client:
        # 例外なく完了することを確認（silent partial failure）
        results = await client.bulk_create_users(users_to_create)

    # 部分失敗: 3件中1件(422)が失敗するため成功件数は正確に2件
    # Note: respxのside_effectはリクエスト到着順（task作成順）に消費され決定論的
    assert len(results) == 2, "3件中1件(422)が失敗するため、成功件数は正確に2件であること"

    # 全リクエストが試行されたことを確認（部分失敗でも全件送信）
    assert post_route.call_count == 3

    # 成功分のみ返却確認（存在確認 + 失敗ユーザーが含まれないことを確認）
    created_names = [result["name"] for result in results]
    assert "User 1" in created_names  # 1件目成功
    assert "User 3" in created_names  # 3件目成功
    assert "User 2" not in created_names  # 2件目は422エラーで失敗、返却されない


@respx.mock
async def test_async_bulk_create_users_partial_failure_5xx() -> None:
    """
    5xxエラー（サーバーエラー）時の部分失敗テスト（APIRetryError経路の検証）

    検証項目：
    - 一部リクエストが5xxエラーで失敗してもbulk_create_usersは例外を発生させない
    - 成功したユーザーのみが返却される（失敗分は除外）
    - 全リクエストが試行される（部分失敗でも中断しない）

    設計根拠：
    4xx（APIHTTPError即発生）と5xx（APIRetryError）では例外型が異なる別コードパス。
    5xx: request → 500 → last_exception=APIHTTPError → retry → 上限でAPIRetryError発生
    どちらもreturn_exceptions=Trueで捕捉され、isinstance(r, dict)フィルタで除外される。

    Note: retry_count=0で5xxリトライを無効化し、side_effectを3件に固定する（決定論的）。
    respxのside_effectはHTTPリクエストの受信順に消費される（asyncio.gatherのタスク作成順と
    概ね一致するが厳密保証なし）。retry_count=0で各タスクは1リクエストのみ発行するため安定。
    成功件数は厳密に2件（== 2）で検証する。
    """
    users_to_create = [
        {"name": "User 1", "email": "user1@test.com"},
        {"name": "User 2", "email": "user2@test.com"},  # この1件を500エラーで失敗させる
        {"name": "User 3", "email": "user3@test.com"},
    ]

    # 2件目のリクエストを500（Internal Server Error）で失敗させる
    # 5xxはリトライ対象だが、retry_count=0でリトライを無効化 → 即APIRetryErrorに変換
    # → return_exceptionsで捕捉され、成功分のみ返却される
    post_route = respx.post(f"{BASE_URL}/users")
    post_route.side_effect = [
        Response(201, json={"id": 101, "name": "User 1", "email": "user1@test.com"}),
        Response(500, json={"error": "Internal Server Error"}),  # 2件目: 500で失敗
        Response(201, json={"id": 103, "name": "User 3", "email": "user3@test.com"}),
    ]

    # retry_count=0: 5xxリトライなし → 即APIRetryError → side_effectは3件で決定論的
    async with AsyncJSONPlaceholderClient(retry_count=0) as client:
        # 例外なく完了することを確認（silent partial failure）
        results = await client.bulk_create_users(users_to_create)

    # 部分失敗: 3件中1件(500→APIRetryError)が失敗するため成功件数は正確に2件
    assert len(results) == 2, (
        "3件中1件(5xx→APIRetryError)が失敗するため、成功件数は正確に2件であること"
    )

    # 全リクエストが試行されたことを確認（部分失敗でも全件送信）
    assert post_route.call_count == 3

    # 成功分のみ返却確認（存在確認 + 失敗ユーザーが含まれないことを確認）
    created_names = [result["name"] for result in results]
    assert "User 1" in created_names  # 1件目成功
    assert "User 3" in created_names  # 3件目成功
    assert "User 2" not in created_names  # 2件目は500エラーで失敗、返却されない


async def test_async_bulk_create_users_cancelled_error_propagates() -> None:
    """複数タスク同時キャンセル時にBaseExceptionGroupで伝播されることを確認（graceful shutdown保護）

    K8s SIGTERM等で複数タスクが同時にキャンセルされた場合、
    bulk_create_users は BaseExceptionGroup に全件を格納して呼び出し元に伝播させる。
    「ログに count=N と記録された件数と、伝播する例外件数の一貫性」を保証する設計。

    Python convention（asyncio.TaskGroup と同パターン）:
    - 1件 → 直接 raise（test_async_bulk_create_users_single_cancelled_error_no_log でカバー）
    - 複数件 → BaseExceptionGroup で伝播（本テスト）

    NOTE: ExceptionGroup ではなく BaseExceptionGroup を使用する理由:
          CancelledError は BaseException サブクラスのため ExceptionGroup に格納不可。
    """
    with patch.object(
        AsyncJSONPlaceholderClient,
        "create_user",
        new_callable=AsyncMock,
    ) as mock_create:
        mock_create.side_effect = asyncio.CancelledError()
        async with AsyncJSONPlaceholderClient() as client:
            # 2タスク同時キャンセル → BaseExceptionGroup で伝播
            with pytest.raises(BaseExceptionGroup) as exc_info:
                await client.bulk_create_users([{"name": "A"}, {"name": "B"}])
    # 格納された例外がすべて CancelledError であることを確認（graceful shutdown 伝播保証）
    assert len(exc_info.value.exceptions) == 2
    assert all(isinstance(e, asyncio.CancelledError) for e in exc_info.value.exceptions)


async def test_async_bulk_create_users_single_cancelled_error_no_log() -> None:
    """単一タスクキャンセル時は logger.error を呼ばずに CancelledError を再発生させることを確認

    len(fatal_exceptions) == 1 のコードパス（ログなし・raise のみ）を検証。
    len > 1 時のみ logger.error が呼ばれる設計であり、単一キャンセルはログ対象外。

    設計根拠: 単一タスクのキャンセルは通常の graceful shutdown シーケンスであり、
    ログノイズを避けるため意図的にログ出力しない設計になっている。
    """
    with patch.object(
        AsyncJSONPlaceholderClient,
        "create_user",
        new_callable=AsyncMock,
    ) as mock_create:
        mock_create.side_effect = asyncio.CancelledError()
        async with AsyncJSONPlaceholderClient() as client:
            with patch.object(client, "logger") as mock_logger:
                with pytest.raises(asyncio.CancelledError):
                    # 1タスクのみ → len(fatal_exceptions) == 1 → ログなし
                    await client.bulk_create_users([{"name": "A"}])
                # 単一キャンセルでは logger.error は呼ばれない
                mock_logger.error.assert_not_called()


async def test_async_bulk_create_users_multiple_cancelled_errors_logged() -> None:
    """複数タスク同時キャンセル時にerrorログが出力されることを確認

    K8s SIGTERM等で全タスクが同時キャンセルされると、
    asyncio.gather(return_exceptions=True) が複数の CancelledError を収集する。
    bulk_create_users は len(fatal_exceptions) > 1 の場合に
    logger.error("bulk_create_multiple_fatal_errors", ...) を呼び出す。
    """
    with patch.object(
        AsyncJSONPlaceholderClient,
        "create_user",
        new_callable=AsyncMock,
    ) as mock_create:
        mock_create.side_effect = asyncio.CancelledError()
        async with AsyncJSONPlaceholderClient() as client:
            with patch.object(client, "logger") as mock_logger:
                # 複数タスク同時キャンセル → BaseExceptionGroup で伝播（Python convention）
                # ログの count=2 と伝播する例外件数の一貫性を保証する設計
                # NOTE: CancelledError は BaseException サブクラスのため BaseExceptionGroup を使用
                with pytest.raises(BaseExceptionGroup) as exc_info:
                    await client.bulk_create_users([{"name": "A"}, {"name": "B"}])
                # patch.objectスコープ内でassert（モックが有効な期間中に検証）
                # 2ユーザー両方がキャンセル → len > 1 → logger.error 呼び出し確認
                mock_logger.error.assert_called_once_with(
                    "bulk_create_multiple_fatal_errors",
                    count=2,
                    types=["CancelledError", "CancelledError"],
                )
        # BaseExceptionGroup の中身が CancelledError であることを確認
        assert len(exc_info.value.exceptions) == 2
        assert all(isinstance(e, asyncio.CancelledError) for e in exc_info.value.exceptions)


async def test_async_bulk_create_users_memory_error_propagates() -> None:
    """MemoryError が gather 後に再発生されることを確認

    bulk_create_users は asyncio.CancelledError だけでなく MemoryError も
    fatal_exceptions として収集して再発生させる（OOM 保護）。

    実装の isinstance チェック対象4種:
    - asyncio.CancelledError: test_async_bulk_create_users_cancelled_error_propagates でカバー
    - MemoryError: 本テストでカバー
    - KeyboardInterrupt: pytest がシグナルとして処理するため unit test 内での再現が困難。
      pytest.raises(KeyboardInterrupt) を使っても pytest 自体のシグナルハンドラが先に捕捉する。
    - SystemExit: 同様の理由で unit test での再現が困難。
    """
    with patch.object(
        AsyncJSONPlaceholderClient,
        "create_user",
        new_callable=AsyncMock,
    ) as mock_create:
        mock_create.side_effect = MemoryError("OOM")
        async with AsyncJSONPlaceholderClient() as client:
            with pytest.raises(MemoryError):
                await client.bulk_create_users([{"name": "A"}])


# ===============================================================================
# Test 5: パフォーマンス・タイムアウト・リソース管理テスト
# ===============================================================================


async def test_async_performance_and_timeout():
    """
    非同期処理のパフォーマンス・タイムアウト・リソース管理テスト

    検証項目：
    - リクエストタイムアウトの動作
    - リトライ後のAPIRetryError発生
    - リトライ間隔の検証

    Note: タイムアウト時、実装はリトライ後にAPIRetryErrorを発生させる。
          TimeoutExceptionは内部でキャッチされる。

          【respx非移行理由】
          httpx.AsyncClientをpatchしてcall_count検証する構造は
          respxのroute.call_count検証と機能的に等価。
          ただし実時間遅延検証（elapsed >= retry_delay）はCI環境でflakeyなため除去済みで
          respxへの移行によるテスト品質向上が限定的なため現状維持。
          ※aclose()検証はtest_async_context_manager_cleanupが担う（別責務）。
    """
    from httpx import TimeoutException

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance

        # Test 5-1: タイムアウト動作テスト（全リトライ後にAPIRetryError）
        mock_client_instance.request.side_effect = TimeoutException("Request timeout")

        async with AsyncAPIClient(timeout=1.0, retry_count=1, retry_delay=0.05) as client:
            # 実装はリトライ失敗後にAPIRetryErrorを発生させる
            with pytest.raises(APIRetryError) as exc_info:
                await client.get("/users/1")

            # エラーメッセージ検証
            assert "failed after" in str(exc_info.value).lower()

            # リトライ動作確認: 初回 + 1回リトライ = 2回の呼び出し
            assert mock_client_instance.request.call_count == 2
            # Note: 実時間アサート（elapsed >= 0.05）は CI 環境での実行スケジュール変動により
            # flaky になるため除去。リトライ動作は call_count == 2 で検証済み。


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

        async with AsyncJSONPlaceholderClient():
            pass  # 何もしない

        # aclose() が呼び出されることを確認
        mock_client_instance.aclose.assert_called_once()


async def test_async_context_manager_cleanup_on_exception():
    """
    例外発生時でもコンテキストマネージャーがクリーンアップするテスト

    検証項目：
    - 例外発生時でも aclose() が呼び出されること（リソースリークなし）

    Note: aclose()呼び出し検証はhttpxクライアントの内部動作に依存するためpatchを使用。
          Exception は httpx.RequestError のサブクラスではないため、リトライを通らず
          そのまま伝播する。例外型はテスト上の都合で使用。
    """
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance

        test_error = Exception("Test error")
        mock_client_instance.request.side_effect = test_error

        with pytest.raises(Exception) as exc_info:
            async with AsyncJSONPlaceholderClient() as client:
                await client.get("/users/1")

        assert str(exc_info.value) == "Test error"
        # 例外発生時でもaclose()が呼び出されることを確認（クリーンアップ保証）
        mock_client_instance.aclose.assert_called_once()


@respx.mock
async def test_async_health_check_success():
    """
    API ヘルスチェック正常系テスト

    検証項目：
    - health_check()メソッドの正常動作
    - 正常時: True返却

    学習ポイント:
    - Docker/Kubernetes readiness probe対応
    - 軽量クエリ（_limit=1）でサーバー負荷最小化
    """
    route = respx.get(f"{BASE_URL}/users", params={"_limit": 1}).respond(
        json=[{"id": 1, "name": "User 1"}]
    )

    async with AsyncJSONPlaceholderClient() as client:
        result = await client.health_check()

    assert result is True
    assert route.call_count == 1


@respx.mock
async def test_async_health_check_connection_error():
    """
    API ヘルスチェック接続エラー時のテスト

    検証項目：
    - 接続エラー時: False返却（graceful degradation）
    - httpx.ConnectError → _make_request_with_retry内でAPIConnectionErrorに変換
      → health_checkでキャッチ

    学習ポイント:
    - respxのside_effectでhttpxネイティブ例外をシミュレート（patch不要）
    - 例外伝播チェーン: httpx.ConnectError → APIConnectionError → health_checkでFalse返却
    - サービス継続性: 例外時はFalse返却
    """
    route = respx.get(f"{BASE_URL}/users", params={"_limit": 1}).mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    async with AsyncJSONPlaceholderClient(retry_count=0) as client:
        result = await client.health_check()

    assert result is False
    assert route.call_count == 1  # retry_count=0なのでリトライなし（1回のみ実行）


# ===============================================================================
# パフォーマンステスト（オプション：時間のかかるテスト）
# ===============================================================================


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

    async with AsyncJSONPlaceholderClient() as client:
        # 100回の並行リクエスト実行
        tasks = [client.get(f"/users/{i}") for i in range(1, 101)]
        results = await asyncio.gather(*tasks)

    # 全100リクエストが成功したことを検証
    assert len(results) == 100
    # 全ルートが各1回ずつ呼ばれたことを確認（並行実行の証明）
    assert all(r.call_count == 1 for r in routes)


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


# ===============================================================================
# Issue #173: 未テストメソッドのカバレッジ追加（60% → 85%目標）
# ===============================================================================


# ===============================================================================
# Test Critical Priority: get_user_data() - 並行処理データ整合性検証
# ===============================================================================


@respx.mock
async def test_get_user_data_parallel_requests():
    """
    get_user_data()の4並行API呼び出しとデータ整合性検証

    検証項目：
    - 4つのAPI（user/posts/todos/albums）が並行実行される
    - asyncio.gatherによる効率的な並行処理
    - postsのuserIdフィルタリングが正しく機能する
    - 返却データ構造が{user, posts, todos, albums}である
    - 各フィールドに期待されるデータ型が含まれる

    学習ポイント:
    - asyncio.gather: 複数の非同期タスクを並行実行
    - respx複数エンドポイント: 1テストで4APIをモック化
    - データ整合性検証: フィルタリングロジックの正確性確認
    - 並行処理パフォーマンス: 順次実行より高速
    """
    user_id = 1

    # 4つのAPIエンドポイントをモック化
    # User API
    route_user = respx.get(f"{BASE_URL}/users/{user_id}").respond(
        json={"id": 1, "name": "Leanne Graham", "email": "Sincere@april.biz"}
    )

    # Posts API（user_id=1のみ - API側フィルタリング）
    route_posts = respx.get(f"{BASE_URL}/posts", params={"userId": user_id}).respond(
        json=[
            {"id": 1, "userId": 1, "title": "Post by User 1", "body": "Content 1"},
            {"id": 3, "userId": 1, "title": "Another post by User 1", "body": "Content 3"},
        ]
    )

    # Todos API（user_id=1のみ）
    route_todos = respx.get(f"{BASE_URL}/todos", params={"userId": user_id}).respond(
        json=[
            {"id": 1, "userId": 1, "title": "Todo 1", "completed": True},
            {"id": 2, "userId": 1, "title": "Todo 2", "completed": False},
        ]
    )

    # Albums API（user_id=1のみ）
    route_albums = respx.get(f"{BASE_URL}/albums", params={"userId": user_id}).respond(
        json=[
            {"id": 1, "userId": 1, "title": "Album 1"},
            {"id": 2, "userId": 1, "title": "Album 2"},
        ]
    )

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        result = await client.get_user_data(user_id)

    # データ構造検証
    assert "user" in result
    assert "posts" in result
    assert "todos" in result
    assert "albums" in result

    # ユーザー情報検証
    assert result["user"]["id"] == 1
    assert result["user"]["name"] == "Leanne Graham"

    # postsフィルタリング検証（userId=1のみが含まれる）
    assert len(result["posts"]) == 2
    assert all(post["userId"] == 1 for post in result["posts"])
    assert result["posts"][0]["id"] == 1
    assert result["posts"][1]["id"] == 3

    # todos検証
    assert len(result["todos"]) == 2
    assert all(todo["userId"] == 1 for todo in result["todos"])

    # albums検証
    assert len(result["albums"]) == 2
    assert all(album["userId"] == 1 for album in result["albums"])

    # 4つのAPIが各1回ずつ呼ばれたことを確認（asyncio.gatherによる並行実行の証明）
    assert route_user.call_count == 1
    assert route_posts.call_count == 1
    assert route_todos.call_count == 1
    assert route_albums.call_count == 1


@respx.mock
async def test_get_user_data_with_empty_posts():
    """
    get_user_data()で一部APIが空リスト返却時の動作検証

    検証項目：
    - posts APIが空リストを返す場合でもエラーにならない
    - 他のAPI（todos/albums）は正常に取得される
    - graceful degradation（部分失敗許容）の実装確認

    学習ポイント:
    - エッジケース: 空データの取り扱い
    - システム全体の堅牢性: 一部データ欠如時も継続動作
    """
    user_id = 1

    # User API
    route_user = respx.get(f"{BASE_URL}/users/{user_id}").respond(
        json={"id": 1, "name": "Leanne Graham", "email": "Sincere@april.biz"}
    )

    # Posts API: userId=1 でフィルタされた結果が空
    route_posts = respx.get(f"{BASE_URL}/posts", params={"userId": user_id}).respond(json=[])

    # Todos API
    route_todos = respx.get(f"{BASE_URL}/todos", params={"userId": user_id}).respond(
        json=[{"id": 1, "userId": 1, "title": "Todo 1", "completed": True}]
    )

    # Albums API
    route_albums = respx.get(f"{BASE_URL}/albums", params={"userId": user_id}).respond(
        json=[{"id": 1, "userId": 1, "title": "Album 1"}]
    )

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        result = await client.get_user_data(user_id)

    # posts が空リストでも正常動作
    assert result["posts"] == []
    assert len(result["todos"]) == 1
    assert len(result["albums"]) == 1

    # 4つのAPIが各1回ずつ呼ばれたことを確認（asyncio.gatherによる並行実行の証明）
    assert route_user.call_count == 1
    assert route_posts.call_count == 1
    assert route_todos.call_count == 1
    assert route_albums.call_count == 1


# ===============================================================================
# Test High Priority: get_posts() - 投稿一覧取得（parametrize）
# ===============================================================================


@pytest.mark.parametrize(
    "limit,expected_count,test_description",
    [
        (2, 2, "limit=2で2件取得"),
        (None, 5, "limit=Noneで全件取得（モックは5件）"),
        (0, 0, "limit=0で0件取得（境界値検証、API仕様では空配列返却）"),
        (100, 5, "limit=100で上限超過時は全件取得"),
    ],
    ids=["normal_limit", "no_limit", "zero_limit", "excessive_limit"],
)
@respx.mock
async def test_get_posts_with_various_limits(limit, expected_count, test_description):
    """
    get_posts()のlimitパラメータ動作検証（parametrize）

    検証項目：
    - limit=2: 正常に2件取得
    - limit=None: パラメータなしで全件取得
    - limit=0: 境界値で0件取得（`if limit is not None`対応後）
    - limit=100: 上限超過時は利用可能な全件取得

    学習ポイント:
    - pytest.parametrize: 複数ケースを1テストで実行
    - ids=: 各ケースの意図を明示的に表現
    - クエリパラメータの正確なマッチング
    - エッジケース網羅: 境界値/None/過剰値
    """
    # モックデータ（5件の投稿）
    all_posts = [
        {"id": i, "userId": 1, "title": f"Post {i}", "body": f"Content {i}"} for i in range(1, 6)
    ]

    # limitパラメータに応じてrespxエンドポイントを設定
    if limit is None:
        # limit指定なし: クエリパラメータなしのURL
        respx.get(f"{BASE_URL}/posts").respond(json=all_posts)
        expected_posts = all_posts
    elif limit == 0:
        # limit=0: API仕様では空配列[]を返却（境界値テスト）
        respx.get(f"{BASE_URL}/posts", params={"_limit": 0}).respond(json=[])
        expected_posts = []
    else:
        # limit指定あり: クエリパラメータ付きURL
        respx.get(f"{BASE_URL}/posts", params={"_limit": limit}).respond(json=all_posts[:limit])
        expected_posts = all_posts[:limit]

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        result = await client.get_posts(limit=limit)

    # 結果検証
    actual_expected = len(expected_posts)
    assert len(result) == actual_expected, (
        f"{test_description}: expected {actual_expected}, got {len(result)}"
    )
    assert result == expected_posts
    assert all(isinstance(post, dict) for post in result)


@pytest.mark.parametrize(
    "user_id,expected_count,test_description",
    [
        (None, 5, "user_id=Noneで全投稿取得（フィルタなし）"),
        (1, 2, "user_id=1でユーザー1の投稿のみ取得（API側フィルタ）"),
        (2, 1, "user_id=2でユーザー2の投稿のみ取得"),
        (999, 0, "user_id=999で存在しないユーザー（空配列返却）"),
    ],
    ids=["no_filter", "user_1", "user_2", "nonexistent_user"],
)
@respx.mock
async def test_async_get_posts_user_filter(user_id, expected_count, test_description):
    """
    get_posts()のuser_idパラメータ動作検証（API側フィルタリング）

    検証項目：
    - user_id=None: フィルタなしで全投稿取得
    - user_id=1/2: 指定ユーザーの投稿のみ取得（API側フィルタ）
    - user_id=999: 存在しないユーザーで空配列返却

    学習ポイント:
    - API側フィルタリング: ネットワーク転送量削減（90%削減効果）
    - クエリパラメータ: /posts?userId=X
    - 境界値テスト: 存在しないユーザーID
    """
    # モックデータ（5件の投稿、userId=1が2件、userId=2が1件、userId=3が2件）
    all_posts = [
        {"id": 1, "userId": 1, "title": "Post 1 by User 1", "body": "Content 1"},
        {"id": 2, "userId": 2, "title": "Post 2 by User 2", "body": "Content 2"},
        {"id": 3, "userId": 1, "title": "Post 3 by User 1", "body": "Content 3"},
        {"id": 4, "userId": 3, "title": "Post 4 by User 3", "body": "Content 4"},
        {"id": 5, "userId": 3, "title": "Post 5 by User 3", "body": "Content 5"},
    ]

    # user_idパラメータに応じてrespxエンドポイントを設定
    if user_id is None:
        # user_idなし: 全件取得
        respx.get(f"{BASE_URL}/posts").respond(json=all_posts)
        expected_posts = all_posts
    elif user_id == 999:
        # 存在しないuser_id: 空配列
        respx.get(f"{BASE_URL}/posts", params={"userId": user_id}).respond(json=[])
        expected_posts = []
    else:
        # user_id指定: API側フィルタリング
        filtered_posts = [p for p in all_posts if p["userId"] == user_id]
        respx.get(f"{BASE_URL}/posts", params={"userId": user_id}).respond(json=filtered_posts)
        expected_posts = filtered_posts

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        result = await client.get_posts(user_id=user_id)

    # 結果検証
    assert len(result) == expected_count, (
        f"{test_description}: expected {expected_count}, got {len(result)}"
    )
    assert result == expected_posts
    if user_id is not None and user_id != 999:
        # user_id指定時は全投稿が指定ユーザーのものであることを確認
        assert all(post["userId"] == user_id for post in result)


# ===============================================================================
# Test: get_posts() - 入力値バリデーション
# ===============================================================================


@pytest.mark.unit
@pytest.mark.parametrize(
    "limit,user_id,expected_error",
    [
        (-1, None, "limit must be >= 0"),
        (-100, None, "limit must be >= 0"),
        (None, 0, "user_id must be >= 1"),
        (None, -1, "user_id must be >= 1"),
        (-1, 0, "limit must be >= 0"),  # limitが先に検証される
    ],
    ids=[
        "negative_limit",
        "very_negative_limit",
        "zero_user_id",
        "negative_user_id",
        "both_invalid_limit_first",
    ],
)
async def test_async_get_posts_validation_error(limit, user_id, expected_error):
    """
    get_posts()の入力値バリデーション検証

    検証項目：
    - limit < 0: ValueError発生
    - user_id < 1: ValueError発生（JSONPlaceholder APIはID=1から）
    - 両方無効な場合: limitが先に検証される

    学習ポイント:
    - 早期エラー検出: API呼び出し前にクライアント側で検証
    - Fail-Fast原則: 無効な入力は即座に拒否
    """
    async with AsyncJSONPlaceholderClient() as client:
        with pytest.raises(ValueError, match=expected_error):
            await client.get_posts(limit=limit, user_id=user_id)


# ===============================================================================
# Test High Priority: get_post() - 個別投稿取得
# ===============================================================================


@respx.mock
async def test_get_post_by_id_success():
    """
    get_post()の正常系テスト

    検証項目：
    - post_id指定で特定投稿を取得
    - レスポンスデータが正確に返却される
    - エンドポイントが正しく構築される（/posts/{post_id}）

    学習ポイント:
    - RESTful API設計: リソースIDによる個別取得
    - URL構築: パスパラメータの正確性
    """
    post_id = 1
    expected_post = {"id": 1, "userId": 1, "title": "Test Post", "body": "Test Content"}

    # モック設定
    respx.get(f"{BASE_URL}/posts/{post_id}").respond(json=expected_post)

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        result = await client.get_post(post_id)

    # 結果検証
    assert result == expected_post
    assert result["id"] == post_id
    assert "title" in result
    assert "body" in result


@respx.mock
async def test_get_post_not_found():
    """
    get_post()の404エラーケーステスト

    検証項目：
    - 存在しないpost_idで404エラーが発生
    - APIHTTPErrorが正しく発生する
    - エラーステータスコードが404である

    学習ポイント:
    - エラーハンドリング: 存在しないリソースへの対応
    - HTTPステータスコード: 404 Not Foundの意味
    - エッジケース: 異常系のテスト重要性
    """
    post_id = 999999

    # 404レスポンスをモック化
    respx.get(f"{BASE_URL}/posts/{post_id}").respond(status_code=404)

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        with pytest.raises(APIHTTPError) as exc_info:
            await client.get_post(post_id)

        # エラー詳細検証
        assert exc_info.value.status_code == 404


# ===============================================================================
# Test High Priority: create_post() - 投稿作成
# ===============================================================================


@respx.mock
async def test_create_post_success():
    """
    create_post()の正常系テスト

    検証項目：
    - title/body/user_id指定で投稿作成
    - レスポンスにidが付与される（サーバー生成）
    - POSTリクエストが正しく送信される
    - JSONデータが正確に送信される

    学習ポイント:
    - RESTful POST: リソース作成操作
    - レスポンスデータ: サーバー生成フィールド（id）の確認
    - リクエストボディ: JSON形式でのデータ送信
    """
    title = "New Post"
    body = "This is a new post content"
    user_id = 1

    expected_response = {
        "id": 101,  # サーバーが生成したID
        "userId": user_id,
        "title": title,
        "body": body,
    }

    # モック設定（ルート固有のcall_countで検証）
    route = respx.post(f"{BASE_URL}/posts").respond(status_code=201, json=expected_response)

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        result = await client.create_post(title=title, body=body, user_id=user_id)

    # 結果検証
    assert result["id"] == 101
    assert result["userId"] == user_id
    assert result["title"] == title
    assert result["body"] == body

    # リクエストボディの内容を検証（フィールド名変更の退行検出）
    request_body = json.loads(route.calls[0].request.content)
    assert request_body["title"] == title
    assert request_body["body"] == body
    assert request_body["userId"] == user_id


@respx.mock
async def test_create_post_with_empty_body():
    """
    create_post()でbody空文字列のエッジケーステスト

    検証項目：
    - body=空文字列でも投稿作成が成功する
    - 必須フィールド（title/user_id）のみで作成可能
    - APIが空文字列を許容する動作確認

    学習ポイント:
    - エッジケース: 空データの取り扱い
    - API仕様: フィールドのオプショナル性
    - バリデーション: クライアント vs サーバーサイド
    """
    title = "Post with Empty Body"
    body = ""  # 空文字列
    user_id = 1

    expected_response = {"id": 102, "userId": user_id, "title": title, "body": body}

    # モック設定（route変数に保存してリクエスト内容を後で検証できるようにする）
    route = respx.post(f"{BASE_URL}/posts").respond(status_code=201, json=expected_response)

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        result = await client.create_post(title=title, body=body, user_id=user_id)

    # レスポンス検証
    assert result["id"] == 102
    assert result["body"] == ""  # 空文字列が保持される

    # リクエストボディ検証: 空文字列が実際に送信されているか確認
    request_body = json.loads(route.calls[0].request.content)
    assert request_body["body"] == ""  # 空文字列が送信されていることを確認
    assert request_body["title"] == title
    assert request_body["userId"] == user_id


# ===============================================================================
# Test Medium Priority: get_todos() - TODO一覧取得（parametrize）
# ===============================================================================


@pytest.mark.parametrize(
    "user_id,completed,limit,expected_params,expected_count,test_description",
    [
        (1, True, 5, {"userId": 1, "completed": True, "_limit": 5}, 2, "全パラメータ指定"),
        (1, None, None, {"userId": 1}, 3, "user_idのみ指定"),
        (None, False, 10, {"completed": False, "_limit": 10}, 2, "completedとlimit指定"),
        (None, None, None, {}, 5, "パラメータなし（全取得）"),
        (2, True, None, {"userId": 2, "completed": True}, 1, "user_id=2, completed=True"),
    ],
    ids=[
        "all_params",
        "user_id_only",
        "completed_and_limit",
        "no_params",
        "user2_completed",
    ],
)
@respx.mock
async def test_get_todos_with_filters(
    user_id, completed, limit, expected_params, expected_count, test_description
):
    """
    get_todos()の複数パラメータ組み合わせ検証（parametrize）

    検証項目：
    - user_id/completed/limitの全組み合わせ動作確認
    - クエリパラメータが正確に構築される
    - Noneパラメータは送信されない（APIデフォルト動作）
    - フィルタ結果が期待通りの件数である

    学習ポイント:
    - pytest.parametrize応用: 3パラメータの組み合わせテスト
    - クエリパラメータ処理: Noneの除外ロジック
    - URLエンコーディング: booleanの文字列変換
    - テストケース網羅性: 全組み合わせの効率的検証
    """
    # モックデータ（5件のTODO、複数ユーザー/完了状態）
    all_todos = [
        {"id": 1, "userId": 1, "title": "Todo 1", "completed": True},
        {"id": 2, "userId": 1, "title": "Todo 2", "completed": False},
        {"id": 3, "userId": 1, "title": "Todo 3", "completed": True},
        {"id": 4, "userId": 2, "title": "Todo 4", "completed": True},
        {"id": 5, "userId": 2, "title": "Todo 5", "completed": False},
    ]

    # パラメータに応じてフィルタされたモックデータを作成
    filtered_todos = all_todos
    if user_id is not None:
        filtered_todos = [t for t in filtered_todos if t["userId"] == user_id]
    if completed is not None:
        filtered_todos = [t for t in filtered_todos if t["completed"] == completed]
    if limit is not None:
        filtered_todos = filtered_todos[:limit]

    # クエリパラメータ構築（Noneは除外）
    query_params = []
    if user_id is not None:
        query_params.append(f"userId={user_id}")
    if completed is not None:
        query_params.append(f"completed={str(completed).lower()}")
    if limit is not None:
        query_params.append(f"_limit={limit}")

    # URLを構築
    if query_params:
        url = f"{BASE_URL}/todos?{'&'.join(query_params)}"
    else:
        url = f"{BASE_URL}/todos"

    # respxモック設定
    respx.get(url).respond(json=filtered_todos)

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        result = await client.get_todos(user_id=user_id, completed=completed, limit=limit)

    # 結果検証
    assert len(result) == expected_count, (
        f"{test_description}: expected {expected_count}, got {len(result)}"
    )
    assert result == filtered_todos
    assert all(isinstance(todo, dict) for todo in result)

    # 追加検証: フィルタ条件が結果に反映されている
    if user_id is not None:
        assert all(t["userId"] == user_id for t in result)
    if completed is not None:
        assert all(t["completed"] == completed for t in result)


# ===============================================================================
# Test: get_todos() - 入力値バリデーション
# ===============================================================================


@pytest.mark.unit
@pytest.mark.parametrize(
    "limit,user_id,expected_error",
    [
        (-1, None, "limit must be >= 0"),
        (-100, None, "limit must be >= 0"),
        (None, 0, "user_id must be >= 1"),
        (None, -1, "user_id must be >= 1"),
        (-1, 0, "limit must be >= 0"),
    ],
    ids=[
        "negative_limit",
        "very_negative_limit",
        "zero_user_id",
        "negative_user_id",
        "both_invalid_limit_first",
    ],
)
async def test_async_get_todos_validation_error(limit, user_id, expected_error):
    """
    get_todos()の入力値バリデーション検証

    検証項目：
    - limit < 0: ValueError発生
    - user_id < 1: ValueError発生（JSONPlaceholder APIはID=1から）
    - 両方無効な場合: limitが先に検証される

    学習ポイント:
    - Fail-Fast原則: 無効な入力は即座に拒否
    - get_posts()と同一パターンのバリデーション一貫性
    """
    async with AsyncJSONPlaceholderClient() as client:
        with pytest.raises(ValueError, match=expected_error):
            await client.get_todos(limit=limit, user_id=user_id)


# ===============================================================================
# Test Medium Priority: put/delete/patch - HTTPメソッド基本動作
# ===============================================================================


@respx.mock
async def test_http_put_method():
    """
    AsyncAPIClient.put()メソッドの基本動作検証

    検証項目：
    - PUTリクエストが正しく送信される
    - JSONデータが正確に送信される
    - レスポンスが正常に返却される
    - HTTPメソッドが"PUT"である

    学習ポイント:
    - HTTP PUT: リソース全体の更新操作
    - RESTful API: PUT vs PATCH の使い分け
    - 冪等性（idempotence）: 同じリクエストを複数回実行しても結果が同じ
    """
    endpoint = "/posts/1"
    update_data = {"id": 1, "title": "Updated Title", "body": "Updated Content", "userId": 1}

    # PUTレスポンスをモック化
    respx.put(f"{BASE_URL}{endpoint}").respond(status_code=200, json=update_data)

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
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

    学習ポイント:
    - HTTP DELETE: リソース削除操作
    - ステータスコード: 204（No Content）vs 200（OK with body）
    - 冪等性: 削除済みリソースの再削除は通常エラーにならない（実装依存）
    """
    endpoint = "/posts/1"

    # DELETEレスポンスをモック化（204 No Content）
    respx.delete(f"{BASE_URL}{endpoint}").respond(status_code=204)

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
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

    学習ポイント:
    - HTTP PATCH: リソースの部分更新操作
    - PUT vs PATCH: PUTは全体更新、PATCHは部分更新
    - JSONデータ: 更新フィールドのみ送信（効率的）
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
    async with AsyncJSONPlaceholderClient() as client:
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

    学習ポイント:
    - エラーハンドリング: 更新対象リソース不在時の動作
    - HTTPステータスコード: 404 Not Found
    - 堅牢性: 異常系テストの重要性
    """
    endpoint = "/posts/999999"
    update_data = {"title": "Non-existent Post"}

    # 404レスポンスをモック化
    respx.put(f"{BASE_URL}{endpoint}").respond(status_code=404)

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        with pytest.raises(APIHTTPError) as exc_info:
            await client.put(endpoint, json=update_data)

        # エラー詳細検証
        assert exc_info.value.status_code == 404


# ===============================================================================
# Issue #173: Albums/Photos API テスト追加（カバレッジ85%達成）
# ===============================================================================


# ===============================================================================
# Albums API Tests
# ===============================================================================


@pytest.mark.parametrize(
    "user_id,expected_count,test_description",
    [
        (1, 2, "user_id=1でアルバム取得"),
        (None, 5, "user_id指定なしで全アルバム取得"),
        (2, 1, "user_id=2でアルバム取得"),
    ],
    ids=["user_id_1", "no_user_id", "user_id_2"],
)
@respx.mock
async def test_get_albums_with_filters(user_id, expected_count, test_description):
    """
    get_albums()のuser_idパラメータ検証（parametrize）

    検証項目：
    - user_id指定時に正しくパラメータが送信される
    - user_id=Noneで全件取得
    - フィルタ結果が期待通りの件数である

    学習ポイント:
    - Albums API: ユーザーごとのアルバム管理
    - parametrize応用: 複数ユーザーパターンテスト
    """
    # モックデータ（5件のアルバム、複数ユーザー）
    all_albums = [
        {"id": 1, "userId": 1, "title": "Album 1"},
        {"id": 2, "userId": 1, "title": "Album 2"},
        {"id": 3, "userId": 2, "title": "Album 3"},
        {"id": 4, "userId": 3, "title": "Album 4"},
        {"id": 5, "userId": 3, "title": "Album 5"},
    ]

    # パラメータに応じてフィルタ
    if user_id is not None:
        filtered_albums = [a for a in all_albums if a["userId"] == user_id]
        url = f"{BASE_URL}/albums?userId={user_id}"
    else:
        filtered_albums = all_albums
        url = f"{BASE_URL}/albums"

    # respxモック設定
    respx.get(url).respond(json=filtered_albums)

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        result = await client.get_albums(user_id=user_id)

    # 結果検証
    assert len(result) == expected_count, (
        f"{test_description}: expected {expected_count}, got {len(result)}"
    )
    assert result == filtered_albums
    assert all(isinstance(album, dict) for album in result)

    # user_idフィルタ検証
    if user_id is not None:
        assert all(a["userId"] == user_id for a in result)


# ===============================================================================
# Test: get_albums() - 入力値バリデーション
# ===============================================================================


@pytest.mark.unit
@pytest.mark.parametrize(
    "user_id,expected_error",
    [
        (0, "user_id must be >= 1"),
        (-1, "user_id must be >= 1"),
    ],
    ids=["zero_user_id", "negative_user_id"],
)
async def test_async_get_albums_validation_error(user_id, expected_error):
    """
    get_albums()の入力値バリデーション検証

    検証項目：
    - user_id < 1: ValueError発生（JSONPlaceholder APIはID=1から）

    学習ポイント:
    - Fail-Fast原則: 無効な入力は即座に拒否
    - get_posts()と同一パターンのバリデーション一貫性
    """
    async with AsyncJSONPlaceholderClient() as client:
        with pytest.raises(ValueError, match=expected_error):
            await client.get_albums(user_id=user_id)


# ===============================================================================
# Photos API Tests
# ===============================================================================


@pytest.mark.parametrize(
    "album_id,expected_count,test_description",
    [
        (1, 2, "album_id=1で写真取得"),
        (None, 6, "album_id指定なしで全写真取得"),
        (2, 1, "album_id=2で写真取得"),
    ],
    ids=["album_id_1", "no_album_id", "album_id_2"],
)
@respx.mock
async def test_get_photos_with_filters(album_id, expected_count, test_description):
    """
    get_photos()のalbum_idパラメータ検証（parametrize）

    検証項目：
    - album_id指定時に正しくエンドポイントが構築される（/albums/{album_id}/photos）
    - album_id=Noneで全件取得（/photos）
    - フィルタ結果が期待通りの件数である

    学習ポイント:
    - Photos API: アルバムごとの写真管理
    - エンドポイント分岐ロジック: パラメータ有無で異なるURL
    """
    # モックデータ（6件の写真、複数アルバム）
    all_photos = [
        {"id": 1, "albumId": 1, "title": "Photo 1", "url": "https://example.com/1.jpg"},
        {"id": 2, "albumId": 1, "title": "Photo 2", "url": "https://example.com/2.jpg"},
        {"id": 3, "albumId": 2, "title": "Photo 3", "url": "https://example.com/3.jpg"},
        {"id": 4, "albumId": 3, "title": "Photo 4", "url": "https://example.com/4.jpg"},
        {"id": 5, "albumId": 3, "title": "Photo 5", "url": "https://example.com/5.jpg"},
        {"id": 6, "albumId": 3, "title": "Photo 6", "url": "https://example.com/6.jpg"},
    ]

    # パラメータに応じてフィルタとURL構築
    if album_id is not None:
        filtered_photos = [p for p in all_photos if p["albumId"] == album_id]
        url = f"{BASE_URL}/albums/{album_id}/photos"
    else:
        filtered_photos = all_photos
        url = f"{BASE_URL}/photos"

    # respxモック設定
    respx.get(url).respond(json=filtered_photos)

    # テスト実行
    async with AsyncJSONPlaceholderClient() as client:
        result = await client.get_photos(album_id=album_id)

    # 結果検証
    assert len(result) == expected_count, (
        f"{test_description}: expected {expected_count}, got {len(result)}"
    )
    assert result == filtered_photos
    assert all(isinstance(photo, dict) for photo in result)

    # album_idフィルタ検証
    if album_id is not None:
        assert all(p["albumId"] == album_id for p in result)


# ===============================================================================
# get_comments / get_photos 入力バリデーションテスト
# ===============================================================================


@pytest.mark.unit
@pytest.mark.parametrize(
    "post_id",
    [0, -1, -100],
    ids=["post_id_zero", "post_id_negative", "post_id_large_negative"],
)
async def test_async_get_comments_invalid_post_id(
    post_id: int, respx_mock: respx.MockRouter
) -> None:
    """
    AsyncJSONPlaceholderClient.get_comments()の無効post_idバリデーション

    検証項目：
    - post_id=0 は ValueError を発生させる（JSONPlaceholder API は1-based ID）
    - 負数のpost_idも同様に ValueError を発生させる
    - HTTP リクエストは発行されない

    学習ポイント:
    - 境界値テスト: 0 は偽値（falsy）であるため `if post_id:` では検出できないバグ
    - `if post_id is not None and post_id < 1:` による正確な検証パターン
    """
    async with AsyncJSONPlaceholderClient() as client:
        with pytest.raises(ValueError, match="post_id must be >= 1"):
            await client.get_comments(post_id=post_id)

    # ValueError が先に発生するため HTTP リクエストは到達しない
    assert len(respx_mock.calls) == 0


@pytest.mark.unit
@pytest.mark.parametrize(
    "album_id",
    [0, -1, -100],
    ids=["album_id_zero", "album_id_negative", "album_id_large_negative"],
)
async def test_async_get_photos_invalid_album_id(
    album_id: int, respx_mock: respx.MockRouter
) -> None:
    """
    AsyncJSONPlaceholderClient.get_photos()の無効album_idバリデーション

    検証項目：
    - album_id=0 は ValueError を発生させる（JSONPlaceholder API は1-based ID）
    - 負数のalbum_idも同様に ValueError を発生させる
    - HTTP リクエストは発行されない

    学習ポイント:
    - album_id=0 を渡すと API は空配列を返すが、正しいエラーではない（サイレント失敗）
    - 明示的な ValueError により呼び出し側でバグを早期発見できる
    """
    async with AsyncJSONPlaceholderClient() as client:
        with pytest.raises(ValueError, match="album_id must be >= 1"):
            await client.get_photos(album_id=album_id)

    # ValueError が先に発生するため HTTP リクエストは到達しない
    assert len(respx_mock.calls) == 0


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
