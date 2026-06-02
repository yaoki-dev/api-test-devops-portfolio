"""Smoke Tests (Issue #81)

真のSmoke Test: デプロイ後の最小生存確認。
- 外部API（JSONPlaceholder）への疎通確認
- 設定ロード（get_settings）の健全性確認

責務外のテスト（404例外契約検証・ログ内省）は移設済み:
- 404例外契約 → tests/integration/test_api_client_integration.py（Issue #82）
- ログ出力検証 → tests/unit/test_api_client_logging.py（Issue #83）
"""

from collections.abc import Generator

import pytest

from config.settings import Settings, get_settings
from utils.api_client import SyncAPIClient


@pytest.fixture(scope="class")
def api_client() -> Generator[SyncAPIClient]:
    """Smoke test用の共有APIクライアント（TCP接続効率化）"""
    with SyncAPIClient() as client:
        yield client


@pytest.mark.smoke
class TestSmoke:
    """Smoke Tests - 外部API（JSONPlaceholder）疎通確認"""

    def test_api_request_succeeds(self, api_client: SyncAPIClient) -> None:
        """#81: APIリクエストが成功する

        検証: JSONPlaceholder APIへのリクエスト成功 = システム疎通確認
        """
        response = api_client.get("/posts/1")
        assert response.status_code == 200


@pytest.mark.smoke
def test_settings_load_succeeds() -> None:
    """設定ロードが例外なく完了する

    検証: get_settings() が Settings インスタンスを返す = 設定系の生存確認。
    network不要・高速・決定論的（Pydantic検証/.env読込が通ること）。
    """
    settings = get_settings()
    assert isinstance(settings, Settings)
