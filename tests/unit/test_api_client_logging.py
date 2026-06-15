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
    テスト中のみ DEBUG へ再構成して capture し、
    終了後に元の structlog 設定へ復元する。
    実API不要・決定論的（respx で HTTP 層を差し替え）。
    """
    mock_get_route(f"{BASE_URL}/posts/1", None, {"id": 1})

    # structlog のグローバル設定をテスト用に DEBUG へ再構成し、終了時は
    # reset_defaults() で builtin デフォルトへリセットする（get_config 復元は
    # ミュータブル参照共有で不完全になりうるため。structlog 公式推奨のクリーンアップ）。
    # reset 後は他テストの get_logger() 呼び出しで production 設定が遅延再構成される。
    try:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
            cache_logger_on_first_use=False,
        )
        with structlog.testing.capture_logs() as logs:
            with SyncAPIClient() as client:
                client.get("/posts/1")
    finally:
        structlog.reset_defaults()

    events = [entry["event"] for entry in logs]
    assert "request_start" in events, (
        f"request_start ログエントリが見つかりません。記録されたイベント: {events}\n"
        "hint: structlog の wrapper_class 再構成が SyncAPIClient の"
        "ロガーに適用されているか確認してください"
    )

    success = next(
        (entry for entry in logs if entry["event"] == "request_success"),
        None,
    )
    assert success is not None, (
        f"request_success ログエントリが見つかりません。記録されたイベント: {events}"
    )
    assert success["endpoint"] == "/posts/1"
    assert success["status_code"] == 200
