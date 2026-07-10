"""JSONPlaceholder Users リソースの統合テスト（実 API 呼び出し）

実際の JSONPlaceholder API にネットワーク経由でアクセスし、User の入れ子モデルの
パースと、ユーザー起点の関連データ並行集約を検証する。
``settings.test.external_api_enabled`` が False の場合はモジュール単位で skip される。
"""

import pytest

from config.settings import settings
from models.responses import Album, Post, Todo, User
from utils.jsonplaceholder_client_async import AsyncJSONPlaceholderClient

SKIP_INTEGRATION = not settings.test.external_api_enabled
SKIP_REASON = "settings.test.external_api_enabled is False - skipping external API tests"

pytestmark = [pytest.mark.integration, pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_REASON)]


async def test_async_user_nested_models_parsed() -> None:
    """get_user() が User → Address → Geo / Company の入れ子を実 API から構築できる

    Post が 4 個のフラットなフィールドしか持たないのに対し、User は 3 段の入れ子を
    持つ最も壊れやすいモデルである。全モデルが ``extra="forbid"`` のため、実 API が
    未知のフィールドを追加した時点で ValidationError となり、ここで検知される。

    ``catch_phrase`` を検証するのは、実 API が camelCase の ``catchPhrase`` を返し、
    Pydantic の alias 解決を経由して初めて値が入るため（alias が壊れると空になる）。
    ``geo.lat`` は数値ではなく文字列（実測値: "-37.3159"）であり、モデル側も str。
    """
    async with AsyncJSONPlaceholderClient() as client:
        user = await client.get_user(1)

    assert isinstance(user, User)
    assert user.id == 1

    # Address → Geo（2段目・3段目の入れ子が構築されている）
    assert user.address.city
    assert isinstance(user.address.geo.lat, str)

    # Company（alias catchPhrase → catch_phrase の解決が効いている）
    assert user.company.catch_phrase


async def test_async_get_user_data_parallel_aggregation() -> None:
    """get_user_data() が 4 エンドポイントを並行取得し、各キーへ正しい型を割り当てる

    asyncio.TaskGroup で users / posts / todos / albums を同時に叩く。単発呼び出しでは
    通るコードが、TaskGroup 配下の結果回収で壊れるケースを実ネットワーク越しに検知する。

    件数ではなく ``user_id == 1`` を検証する理由: 件数を固定すると実 API のデータ変動で
    flaky になるうえ、``?userId=`` フィルタが壊れて全件返っても件数だけでは気付けない。
    フィルタ契約そのものを assert する方が、壊れ方に対して正確に反応する。

    ``user_id`` の検証だけでは不十分なため型も assert する。Post / Todo / Album は
    いずれも ``user_id: int`` (alias ``userId``) を持つため、TaskGroup の結果が
    キー間で取り違えられても（例: ``data["posts"]`` に todos の結果が入る）
    ``user_id`` の比較だけは通ってしまう。型の検証がその取り違えを捕捉する。
    """
    user_id = 1

    async with AsyncJSONPlaceholderClient() as client:
        data = await client.get_user_data(user_id)

    assert isinstance(data["user"], User)
    assert data["user"].id == user_id

    # 各キーが「空でない」「期待する型」「全件が該当ユーザー」の3条件を満たすこと
    assert data["posts"]
    assert all(isinstance(post, Post) for post in data["posts"])
    assert all(post.user_id == user_id for post in data["posts"])

    assert data["todos"]
    assert all(isinstance(todo, Todo) for todo in data["todos"])
    assert all(todo.user_id == user_id for todo in data["todos"])

    assert data["albums"]
    assert all(isinstance(album, Album) for album in data["albums"])
    assert all(album.user_id == user_id for album in data["albums"])
