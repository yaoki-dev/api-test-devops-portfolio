"""JSONPlaceholder Posts リソースの統合テスト（実 API 呼び出し）

実際の JSONPlaceholder API にネットワーク経由でアクセスし、Post リソースに対する
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
        with SyncJSONPlaceholderClient() as client:
            client.get_post(1)
    except (APIConnectionError, APITimeoutError, APIRetryError) as exc:
        pytest.skip(
            "JSONPlaceholder への接続に失敗したため 404 契約検証を skip します"
            f"（ネットワーク障害が原因であり 404 契約バグではありません）: {exc}"
        )

    # Phase 2: 契約検証 — APIRetryError 含む全例外がテスト失敗として CI に報告される
    with SyncJSONPlaceholderClient() as client:
        with pytest.raises(APIHTTPError) as exc_info:
            client.get_post(999999)
        assert exc_info.value.status_code == 404


async def test_async_create_post_response_parses_into_post_model() -> None:
    """create_post() のレスポンスが Post モデルへ正しく解釈される

    実 API のレスポンス形状が変わり Post モデルの検証が通らなくなった場合に落ちる。
    id=101 は JSONPlaceholder が新規作成時に必ず返す固定値（永続化しないため）。
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


async def test_async_update_post_returns_sent_fields_as_dict() -> None:
    """update_post() が送信内容を反映したレスポンスをそのまま返す

    Post モデルではなく生の dict を検証する理由: JSONPlaceholder の PUT は
    「送信したフィールド + id」だけを返し userId を省くため、Post の必須項目を
    満たさない。update_post() が dict を返す設計はこの実 API 仕様に由来する。
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


async def test_async_delete_post_completes_without_exception() -> None:
    """delete_post() が実 API に対して例外なく完了する

    削除結果を検証しない理由: JSONPlaceholder は DELETE を永続化せず、応答本文も
    空である。ここで守れる契約は「2xx が返り例外に化けない」ことだけであり、
    それ以上を assert すると実 API の仕様ではなくテストの願望を検証してしまう。
    """
    async with AsyncJSONPlaceholderClient() as client:
        await client.delete_post(post_id=1)


async def test_async_post_crud_sequence_reuses_one_client() -> None:
    """Create → Read → Update → Delete を単一クライアントで通し、各段が例外なく完了する

    守っている契約は「1つの ``AsyncClient`` インスタンスで4メソッドを連続実行しても
    ライフサイクル管理が壊れない」ことのみ。``_close_async_client`` の後始末が早すぎる、
    ``self`` に状態が残る、といった実装の劣化を検知する。

    サーバー側の状態遷移は検証**できない**。JSONPlaceholder は Create/Update/Delete を
    永続化せず（POST は常に ``id=101`` を返す）、Read は作成物ではなく既存データ
    （id=1-100）を取得する。4ステップは実質的に独立したステートレス呼び出しである。

    接続（TCP）の再利用は ``httpx`` の transport pool の責務であり、ここでは検証しない。
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


async def test_async_get_nonexistent_post_raises_404() -> None:
    """存在しない投稿の GET が APIHTTPError(status_code=404) を送出する
    （二相分離: 到達性確認→契約検証）

    二相構成:
      Phase 1 (到達性確認): 既存リソース /posts/1 へ疎通し、接続障害は skip
      Phase 2 (契約検証):   /posts/999999 で APIHTTPError(status_code=404) を検証。
                            APIRetryError 含む全例外がテスト失敗として CI に報告される。

    設計意図: Phase 1/2 を分離することで、pytest.raises(APIHTTPError) が APIRetryError
    を捕捉せず外側の except に伝播する問題（skip に化けて CI がバグを見逃す）を防止する。

    GET を使う理由: JSONPlaceholder の ``PUT /posts/{id}`` は存在しない id に対して
    500 を返す（実測）。5xx はリトライ対象のため APIRetryError となり、404 契約を
    検証できない。GET は 404 を返し、4xx は即失敗するのでリトライも発生しない。

    基底の APIClientError ではなく APIHTTPError を期待する理由: APIClientError は
    APIConnectionError / APITimeoutError / APIRetryError も捕捉するため、ネットワーク
    障害でもテストが緑になり、404 契約の破壊を検知できない。
    """
    # Phase 1: 到達性確認 — 接続障害時は skip（404 契約バグではない）
    try:
        async with AsyncJSONPlaceholderClient() as client:
            await client.get_post(1)
    except (APIConnectionError, APITimeoutError, APIRetryError) as exc:
        pytest.skip(
            "JSONPlaceholder への接続に失敗したため 404 契約検証を skip します"
            f"（ネットワーク障害が原因であり 404 契約バグではありません）: {exc}"
        )

    # Phase 2: 契約検証 — APIRetryError 含む全例外がテスト失敗として CI に報告される
    async with AsyncJSONPlaceholderClient() as client:
        with pytest.raises(APIHTTPError) as exc_info:
            await client.get_post(999999)
        assert exc_info.value.status_code == 404
