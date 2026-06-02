"""JSONPlaceholder API (SyncAPIClient) 統合テスト — 公開例外契約の検証 (Issue #82)

JSONPlaceholder の実APIに対し、SyncAPIClient の公開例外契約を検証する。
スモーク（最小生存確認）の責務を超えるため、test_smoke.py から移設した。

- 404レスポンス → APIHTTPError（status_code=404）が送出される公開契約
"""

import pytest

from utils.api_client import (
    APIConnectionError,
    APIHTTPError,
    APIRetryError,
    APITimeoutError,
    SyncAPIClient,
)

# Module-level marker: このファイルの全テストは統合テスト。external は付与しない
# （毎 PR CI で実行する）。
# 理由: JSONPlaceholder は本プロジェクトのテスト用基準 API であり、
# tests/integration/test_basic.py 等が同 API への 404 検証を plain integration として
# 既に毎 PR 実行している。ここに external を付けると既存 integration 群と非対称になるため
# 整合を優先する。external は GitHub API 等（認証・レート制限を伴う依存）に限定する。
pytestmark = pytest.mark.integration


def test_api_404_raises_http_error() -> None:
    """#82: 存在しないリソースでAPIHTTPErrorが発生する

    検証: 404レスポンスで APIHTTPError が status_code=404 で送出される
    （公開例外契約のブラックボックス検証）。

    実ネットワーク依存のため、接続障害・タイムアウト時は契約検証不能として
    skip し、CI のフラキー失敗（404 契約バグではなくインフラ起因の失敗）を防ぐ。
    """
    try:
        with SyncAPIClient() as client:
            with pytest.raises(APIHTTPError) as exc_info:
                client.get("/posts/999999")
        assert exc_info.value.status_code == 404
    except (APIConnectionError, APITimeoutError, APIRetryError) as exc:
        pytest.skip(
            "JSONPlaceholder への接続に失敗したため 404 契約検証を skip します"
            f"（ネットワーク障害が原因であり 404 契約バグではありません）: {exc}"
        )
