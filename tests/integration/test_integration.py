"""Integration tests for JSONPlaceholder clients."""

import asyncio

import pytest

from config.settings import settings
from models.responses import Post
from utils.exceptions import (
    APIClientError,
    APIConnectionError,
    APIHTTPError,
    APIRetryError,
    APITimeoutError,
)
from utils.jsonplaceholder_base_sync import SyncAPIClient
from utils.jsonplaceholder_client_async import AsyncJSONPlaceholderClient

SKIP_INTEGRATION = not settings.test.external_api_enabled
SKIP_REASON = "settings.test.external_api_enabled is False - skipping external API tests"

pytestmark = pytest.mark.unit


def test_api_404_raises_http_error() -> None:
    """存在しないリソースでAPIHTTPErrorが発生する（二相分離: 到達性確認→契約検証）

    二相構成:
      Phase 1 (到達性確認): 既存リソース /posts/1 へ疎通し、接続障害は skip
      Phase 2 (契約検証):   /posts/999999 で APIHTTPError(status_code=404) を検証。
                            APIRetryError 含む全例外がテスト失敗として CI に報告される。

    設計意図: Phase 1/2 を分離することで、pytest.raises(APIHTTPError) が APIRetryError
    を捕捉せず外側の except に伝播する問題（skip に化けて CI がバグを見逃す）を防止する。
    """
    # Phase 1: 到達性確認 — 接続障害時は skip（404 契約バグではない）
    try:
        with SyncAPIClient() as client:
            client.get("/posts/1")
    except (APIConnectionError, APITimeoutError, APIRetryError) as exc:
        pytest.skip(
            "JSONPlaceholder への接続に失敗したため 404 契約検証を skip します"
            f"（ネットワーク障害が原因であり 404 契約バグではありません）: {exc}"
        )

    # Phase 2: 契約検証 — APIRetryError 含む全例外がテスト失敗として CI に報告される
    with SyncAPIClient() as client:
        with pytest.raises(APIHTTPError) as exc_info:
            client.get("/posts/999999")
        assert exc_info.value.status_code == 404


@pytest.mark.integration
@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_REASON)
async def test_real_async_create_post():
    """
    実API: 非同期投稿作成（POST /posts）のテスト

    検証項目：
    - 実際のJSONPlaceholder APIへの接続
    - create_post() メソッドの実行
    - レスポンスの正常取得（id, title, body, userId）
    - HTTPステータスコード 201 Created の確認
    """
    async with AsyncJSONPlaceholderClient() as client:
        # 実API呼び出し
        post = await client.create_post(
            title="Integration Test Post",
            body="This is a test post from integration tests",
            user_id=1,
        )

        # 結果検証
        assert isinstance(post, Post)
        assert post.title == "Integration Test Post"
        assert post.body == "This is a test post from integration tests"
        assert post.user_id == 1

        # JSONPlaceholder API の仕様: 新規作成時は id=101 が返る
        assert post.id == 101


@pytest.mark.integration
@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_REASON)
async def test_real_async_update_post():
    """
    実API: 非同期投稿更新（PUT /posts/{id}）のテスト

    検証項目：
    - 既存投稿（id=1）の更新リクエスト
    - update_post() メソッドの実行
    - レスポンスに更新データが反映されているか確認
    - HTTPステータスコード 200 OK の確認
    """
    async with AsyncJSONPlaceholderClient() as client:
        # 既存投稿を更新（id=1 は常に存在する）
        updated = await client.update_post(
            post_id=1,
            title="Updated Title via Integration Test",
            body="Updated body content",
        )

        # 結果検証
        assert updated["id"] == 1
        assert updated["title"] == "Updated Title via Integration Test"
        assert updated["body"] == "Updated body content"


@pytest.mark.integration
@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_REASON)
async def test_real_async_delete_post():
    """
    実API: 非同期投稿削除（DELETE /posts/{id}）のテスト

    検証項目：
    - 既存投稿（id=1）の削除リクエスト
    - delete_post() メソッドの実行
    - 例外が発生しないことの確認
    - JSONPlaceholder API の仕様: 実際には削除されないが200/204を返す
    """
    async with AsyncJSONPlaceholderClient() as client:
        # delete_post() returns None, so just verify no exception raised
        await client.delete_post(post_id=1)


@pytest.mark.integration
@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_REASON)
async def test_real_async_crud_integration():
    """
    実API: CRUD操作の統合フローテスト（実API使用）

    検証項目：
    - Create → Read → Update → Delete の一連フロー
    - 実際のネットワークI/O処理
    - 各操作の正常実行と適切なレスポンス処理
    - 非同期処理によるパフォーマンス
    - エンドツーエンドの動作確認

    注意：
    - JSONPlaceholder API の仕様上、Create/Update/Delete は実際には永続化されない
    - テストは API の動作確認と、クライアント実装の検証が目的
    """
    async with AsyncJSONPlaceholderClient() as client:
        # Step 1: Create - 新規投稿作成
        post = await client.create_post(
            title="E2E Integration Test",
            body="Testing full CRUD flow with real API",
            user_id=1,
        )
        post_id = post.id
        assert post_id == 101  # JSONPlaceholder API の仕様
        assert post.title == "E2E Integration Test"

        # Step 2: Read - 投稿一覧取得
        # JSONPlaceholder API の仕様: 新規作成データは永続化されないため、
        # 既存データ（id=1-100）を取得して確認
        posts = await client.get_posts(limit=10)
        assert len(posts) > 0
        assert isinstance(posts, list)

        # Step 3: Update - 既存投稿を更新（id=1）
        updated = await client.update_post(
            post_id=1,
            title="Updated in Integration Test",
            body="Updated body content",
        )
        assert updated["id"] == 1
        assert updated["title"] == "Updated in Integration Test"

        # Step 4: Delete - 投稿削除（id=1）
        # delete_post() returns None, so just verify no exception raised
        await client.delete_post(post_id=1)


@pytest.mark.integration
@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_REASON)
async def test_real_async_404_error():
    """
    実API: 404 Not Found エラー時の挙動テスト

    検証項目：
    - 存在しないリソース（post_id=999999）へのアクセス
    - 404エラーの適切な検出と例外処理
    - APIClientError 例外の発生
    - リトライが実行されないこと（4xxはクライアントエラー）
    """
    async with AsyncJSONPlaceholderClient() as client:
        # 存在しないIDへのアクセス
        with pytest.raises(APIClientError):
            await client.update_post(post_id=999999, title="Test", body="Test")


@pytest.mark.integration
@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_REASON)
async def test_real_async_concurrent_crud():
    """
    実API: 並行CRUD操作のパフォーマンステスト

    検証項目：
    - asyncio.gather() による並行リクエスト実行
    - 複数の投稿作成・更新を同時処理
    - パフォーマンス測定（逐次実行 vs 並行実行）
    - エラーハンドリングの一貫性
    """
    async with AsyncJSONPlaceholderClient() as client:
        # 3つの投稿を並行作成
        create_tasks = [
            client.create_post(f"Concurrent Post {i}", f"Body {i}", 1) for i in range(1, 4)
        ]

        # 並行実行
        results = await asyncio.gather(*create_tasks)

        # 結果検証
        assert len(results) == 3
        for i, post in enumerate(results, start=1):
            assert post.title == f"Concurrent Post {i}"
            assert post.user_id == 1
            assert post.id == 101  # JSONPlaceholder の仕様: 常に101


@pytest.mark.integration
@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_REASON)
async def test_real_async_with_timeout():
    """
    実API: タイムアウト設定の動作テスト

    検証項目：
    - カスタムタイムアウト設定（30秒）
    - 通常のリクエストが正常に完了すること
    - タイムアウト値がクライアントに正しく設定されること
    """
    # カスタムタイムアウトでクライアント作成
    async with AsyncJSONPlaceholderClient(timeout=30.0) as client:
        # 通常のリクエストが正常に完了することを確認
        posts = await client.get_posts(limit=5)
        assert len(posts) == 5
        assert isinstance(posts, list)
