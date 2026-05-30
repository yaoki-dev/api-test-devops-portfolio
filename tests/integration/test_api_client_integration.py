"""JSONPlaceholder API (SyncAPIClient) 統合テスト — 公開例外契約の検証 (Issue #82)

JSONPlaceholder の実APIに対し、SyncAPIClient の公開例外契約を検証する。
スモーク（最小生存確認）の責務を超えるため、test_smoke.py から移設した。

- 404レスポンス → APIHTTPError（status_code=404）が送出される公開契約
"""

import pytest

from utils.api_client import APIHTTPError, SyncAPIClient

# Module-level marker: このファイルの全テストは統合テスト
pytestmark = pytest.mark.integration


def test_api_404_raises_http_error() -> None:
    """#82: 存在しないリソースでAPIHTTPErrorが発生する

    検証: 404レスポンスで APIHTTPError が status_code=404 で送出される
    （公開例外契約のブラックボックス検証）。
    """
    with SyncAPIClient() as client:
        with pytest.raises(APIHTTPError) as exc_info:
            client.get("/posts/999999")
    assert exc_info.value.status_code == 404
