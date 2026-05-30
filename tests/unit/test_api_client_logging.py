"""SyncAPIClient ログ出力テスト (Issue #83)

API呼び出し時に構造化ログ（structlog）が出力されることを検証する。
スモーク（最小生存確認）の責務を超えるため test_smoke.py から移設し、
実APIに依存しないようモックレスポンス（respx）で決定論化した。
"""

import logging

import pytest
import respx
import structlog

from tests.constants import BASE_URL
from tests.unit.helpers import mock_get_route
from utils.api_client import SyncAPIClient

pytestmark = pytest.mark.unit


@respx.mock
def test_get_produces_structured_logs() -> None:
    """#83: GET呼び出しで request_start / request_success ログが出力される

    検証: モックレスポンスに対して GET を実行し、structlog が
    リクエスト開始・成功イベントを endpoint 付きで記録すること。

    request_start / request_success は DEBUG レベルで出力されるため、
    既定の filtering level（INFO）では破棄される。テスト中のみ DEBUG へ
    再構成して capture し、終了後に元の structlog 設定へ復元する。
    実API不要・決定論的（respx で HTTP 層を差し替え）。
    """
    mock_get_route(f"{BASE_URL}/posts/1", None, {"id": 1})

    original_config = structlog.get_config()
    try:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
            cache_logger_on_first_use=False,
        )
        with structlog.testing.capture_logs() as logs:
            with SyncAPIClient() as client:
                response = client.get("/posts/1")
    finally:
        structlog.configure(**original_config)

    assert response.status_code == 200

    events = [entry["event"] for entry in logs]
    assert "request_start" in events
    assert "request_success" in events

    success = next(entry for entry in logs if entry["event"] == "request_success")
    assert success["endpoint"] == "/posts/1"
    assert success["status_code"] == 200
