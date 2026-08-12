"""外部API疎通と設定ロードを確認する最小 smoke tests"""

from collections.abc import Generator

import pytest

from config.settings import Settings, get_settings
from utils.jsonplaceholder_base_sync import SyncAPIClient


@pytest.fixture(scope="class")
def api_client() -> Generator[SyncAPIClient]:
    """TCP接続を共有し、smoke test の外部API疎通コストを抑える。"""
    with SyncAPIClient() as client:
        yield client


@pytest.mark.smoke
class TestSmoke:
    def test_api_request_succeeds(self, api_client: SyncAPIClient) -> None:
        """#81 の回帰防止として、JSONPlaceholder への最小疎通を確認する。"""
        response = api_client.get("/posts/1")
        assert response.status_code == 200


@pytest.mark.smoke
def test_settings_load_succeeds() -> None:
    """networkなしで Pydantic 検証と .env 読込の生存確認を行う。"""
    settings = get_settings()
    assert isinstance(settings, Settings)
