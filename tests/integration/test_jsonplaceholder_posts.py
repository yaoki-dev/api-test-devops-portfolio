"""JSONPlaceholder Posts リソースの外部結合テスト

実JSONPlaceholder API にアクセスし、Post リソースに対する
CRUD と 404 契約を検証する。``settings.test.external_api_enabled`` が False の場合は
モジュール単位で skip される。

JSONPlaceholder の仕様上の注意:
  - Create/Update/Delete は永続化されない。POST は常に ``id=101`` を返す。
  - ``PUT /posts/{id}`` は存在しない id に対して 404 ではなく 500 を返す。
"""

import pytest

from config.settings import settings
from models.responses import Post
from utils.exceptions import (
    APIConnectionError,
    APIHTTPError,
    APIRetryError,
    APITimeoutError,
)
from utils.jsonplaceholder_client_async import AsyncJSONPlaceholderClient
from utils.jsonplaceholder_client_sync import SyncJSONPlaceholderClient

SKIP_INTEGRATION = not settings.test.external_api_enabled
SKIP_REASON = "settings.test.external_api_enabled is False - skipping external API tests"

pytestmark = [pytest.mark.integration, pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_REASON)]


def test_sync_get_nonexistent_post_raises_404() -> None:
    # 到達性確認 — 接続障害時は skip（404 契約バグではない）
    try:
        with SyncJSONPlaceholderClient() as client:
            client.get_post(1)
    except (APIConnectionError, APITimeoutError, APIRetryError) as exc:
        pytest.skip(
            "JSONPlaceholder への接続に失敗したため 404 契約検証を skip します"
            f"（ネットワーク障害が原因であり 404 契約バグではありません）: {exc}"
        )

    # 契約検証 — APIRetryError 含む全例外がテスト失敗として CI に報告される
    with SyncJSONPlaceholderClient() as client:
        with pytest.raises(APIHTTPError) as exc_info:
            client.get_post(999999)
        assert exc_info.value.status_code == 404


async def test_async_create_post_response_parses_into_post_model() -> None:
    async with AsyncJSONPlaceholderClient() as client:
        post = await client.create_post(
            title="Integration Test Post",
            body="This is a test post from integration tests",
            user_id=1,
        )

        assert isinstance(post, Post)
        assert post.title == "Integration Test Post"
        assert post.body == "This is a test post from integration tests"
        assert post.user_id == 1

        # JSONPlaceholder API の仕様: 新規作成時は id=101 が返る
        assert post.id == 101


async def test_async_update_post_returns_sent_fields_as_dict() -> None:
    # JSONPlaceholderのPUTはuserIdを返さないため、Postモデルではなくdictで検証する
    async with AsyncJSONPlaceholderClient() as client:
        # 既存投稿を更新（id=1 は常に存在する）
        updated = await client.update_post(
            post_id=1,
            title="Updated Title via Integration Test",
            body="Updated body content",
        )

        assert updated["id"] == 1
        assert updated["title"] == "Updated Title via Integration Test"
        assert updated["body"] == "Updated body content"


async def test_async_delete_post_completes_without_exception() -> None:
    # DELETEは永続化されず応答も空のため、例外が発生しないことのみを検証する
    async with AsyncJSONPlaceholderClient() as client:
        await client.delete_post(post_id=1)


async def test_async_post_crud_sequence_reuses_one_client() -> None:
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

        # 投稿一覧取得
        # JSONPlaceholder API の仕様: 新規作成データは永続化されないため、
        # 既存データ（id=1-100）を取得して確認
        posts = await client.get_posts(limit=10)
        assert len(posts) > 0
        assert isinstance(posts, list)

        # Update - 既存投稿を更新（id=1）
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


async def test_async_get_nonexistent_post_raises_404() -> None:
    # 到達性確認 — 接続障害時は skip（404 契約バグではない）
    try:
        async with AsyncJSONPlaceholderClient() as client:
            await client.get_post(1)
    except (APIConnectionError, APITimeoutError, APIRetryError) as exc:
        pytest.skip(
            "JSONPlaceholder への接続に失敗したため 404 契約検証を skip します"
            f"（ネットワーク障害が原因であり 404 契約バグではありません）: {exc}"
        )

    # 契約検証 — APIRetryError 含む全例外がテスト失敗として CI に報告される
    async with AsyncJSONPlaceholderClient() as client:
        with pytest.raises(APIHTTPError) as exc_info:
            await client.get_post(999999)
        assert exc_info.value.status_code == 404
