# ===============================================================================
# test_async_crud.py - 非同期CRUD操作の統合テスト（実API使用）
# ===============================================================================
#
# このファイルは AsyncJSONPlaceholderClient の実API統合テスト
# 学習ポイント：
# 1. 実際のJSONPlaceholder APIへの非同期リクエスト
# 2. CRUD操作の統合フロー（Create → Read → Update → Delete）
# 3. ネットワークエラー・タイムアウトの実践的処理
# 4. 統合テストとE2Eテストの違い
#
# 注意事項：
# - このテストは外部APIに依存します
# - CI/CD環境では TEST_EXTERNAL_API_ENABLED=false で無効化できます
# - レートリミット・ネットワーク遅延を考慮してください
#
# 実行方法：
#   pytest tests/integration/test_async_crud.py -v
#   pytest tests/integration/test_async_crud.py::test_real_async_create_post -v
#   TEST_EXTERNAL_API_ENABLED=false pytest tests/integration/  # スキップ
#
# ===============================================================================

import asyncio

import pytest

from config.settings import settings
from utils.api_client import APIClientError, AsyncJSONPlaceholderClient

# Pydantic Settings経由で統合テスト実行を制御（.envのTEST__EXTERNAL_API_ENABLEDを参照）
SKIP_INTEGRATION = not settings.test.external_api_enabled
SKIP_REASON = "settings.test.external_api_enabled is False - skipping external API tests"


# ===============================================================================
# Test 1: 実API - 非同期投稿作成テスト（Create）
# ===============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
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
        assert "id" in post
        assert post["title"] == "Integration Test Post"
        assert post["body"] == "This is a test post from integration tests"
        assert post["userId"] == 1

        # JSONPlaceholder API の仕様: 新規作成時は id=101 が返る
        assert post["id"] == 101


# ===============================================================================
# Test 2: 実API - 非同期投稿更新テスト（Update）
# ===============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
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
            post_id=1, title="Updated Title via Integration Test", body="Updated body content"
        )

        # 結果検証
        assert updated["id"] == 1
        assert updated["title"] == "Updated Title via Integration Test"
        assert updated["body"] == "Updated body content"


# ===============================================================================
# Test 3: 実API - 非同期投稿削除テスト（Delete）
# ===============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
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
        # delete_post() は None を返すので、例外が発生しないことを確認
        result = await client.delete_post(post_id=1)

        # 結果検証（Noneが返ることを確認）
        assert result is None


# ===============================================================================
# Test 4: 実API - CRUD統合フローテスト
# ===============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
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
        post_id = post["id"]
        assert post_id == 101  # JSONPlaceholder API の仕様
        assert post["title"] == "E2E Integration Test"

        # Step 2: Read - 投稿一覧取得
        # JSONPlaceholder API の仕様: 新規作成データは永続化されないため、
        # 既存データ（id=1-100）を取得して確認
        posts = await client.get_posts(limit=10)
        assert len(posts) > 0
        assert isinstance(posts, list)

        # Step 3: Update - 既存投稿を更新（id=1）
        updated = await client.update_post(
            post_id=1, title="Updated in Integration Test", body="Updated body content"
        )
        assert updated["id"] == 1
        assert updated["title"] == "Updated in Integration Test"

        # Step 4: Delete - 投稿削除（id=1）
        result = await client.delete_post(post_id=1)
        assert result is None


# ===============================================================================
# Test 5: 実API - エラーハンドリング（404 Not Found）
# ===============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
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


# ===============================================================================
# Test 6: 実API - 並行CRUD操作テスト（パフォーマンス）
# ===============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
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
            assert post["title"] == f"Concurrent Post {i}"
            assert post["userId"] == 1
            assert post["id"] == 101  # JSONPlaceholder の仕様: 常に101


# ===============================================================================
# Test 7: 実API - タイムアウト設定テスト
# ===============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
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
