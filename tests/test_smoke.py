"""Smoke Tests (Issues #81, #82, #83)

真のSmoke Test: 外部API（JSONPlaceholder）への疎通確認。
デプロイ後に「システムが動作している」ことを証明する。
"""

import logging
from collections.abc import Generator

import pytest

from utils.api_client import APIHTTPError, SyncAPIClient


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

    def test_api_404_raises_http_error(self, api_client: SyncAPIClient) -> None:
        """#82: 存在しないリソースでAPIHTTPErrorが発生する

        検証: 404レスポンスで適切な例外が発生
        """
        with pytest.raises(APIHTTPError) as exc_info:
            api_client.get("/posts/999999")
        assert exc_info.value.status_code == 404

    def test_api_request_produces_logs(
        self,
        api_client: SyncAPIClient,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """#83: API呼び出し時にログが出力される

        検証: リクエスト実行でAPIリクエストに関連するログが生成される
        """
        with caplog.at_level(logging.DEBUG):
            api_client.get("/posts/1")
        # API呼び出しに関連するログが存在することを検証（HTTPステータス or エンドポイント）
        assert any(
            "200" in record.message or "posts" in record.message.lower()
            for record in caplog.records
        ), "API request log not found in captured logs"
