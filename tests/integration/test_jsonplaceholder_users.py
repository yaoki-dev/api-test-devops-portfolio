"""JSONPlaceholder Usersリソースの外部結合テスト。

実APIへアクセスし、Userの入れ子モデルのパースと、
ユーザー起点の関連データ並行集約を検証する。
settings.test.external_api_enabled が False の場合はモジュール全体をskipする。
"""

import pytest

from config.settings import settings
from models.responses import Album, Post, Todo, User
from utils.jsonplaceholder_client_async import AsyncJSONPlaceholderClient

SKIP_INTEGRATION = not settings.test.external_api_enabled
SKIP_REASON = "settings.test.external_api_enabled is False - skipping external API tests"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.external,
    pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_REASON),
]


async def test_async_user_nested_models_parsed() -> None:
    """Alias解決の回帰を検知するため、3段の入れ子モデルを実APIで検証する。"""
    async with AsyncJSONPlaceholderClient() as client:
        user = await client.get_user(1)

    assert isinstance(user, User)
    assert user.id == 1

    assert user.address.city
    assert isinstance(user.address.geo.lat, str)

    # catchPhrase はモデル側の alias で catch_phrase に変換される。
    assert user.company.catch_phrase


async def test_async_get_user_data_parallel_aggregation() -> None:
    user_id = 1

    async with AsyncJSONPlaceholderClient() as client:
        data = await client.get_user_data(user_id)

    assert isinstance(data["user"], User)
    assert data["user"].id == user_id

    assert data["posts"]
    assert all(isinstance(post, Post) for post in data["posts"])
    assert all(post.user_id == user_id for post in data["posts"])

    assert data["todos"]
    assert all(isinstance(todo, Todo) for todo in data["todos"])
    assert all(todo.user_id == user_id for todo in data["todos"])

    assert data["albums"]
    assert all(isinstance(album, Album) for album in data["albums"])
    assert all(album.user_id == user_id for album in data["albums"])
