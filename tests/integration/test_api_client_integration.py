"""JSONPlaceholder API (SyncAPIClient) 統合テスト
JSONPlaceholder の実APIに対し、SyncAPIClient の公開例外契約の検証
"""

import pytest

from utils.api_client import (
    APIConnectionError,
    APIHTTPError,
    APIRetryError,
    APITimeoutError,
    SyncAPIClient,
)

# Module-level marker: 全テストを統合テストとして毎 PR CI で実行する。
# external は付与しない（JSONPlaceholder は基準 API で、既存 integration 群と整合させるため。
# external は GitHub API 等の認証・レート制限を伴う依存に限定）。
pytestmark = pytest.mark.integration


def test_api_404_raises_http_error() -> None:
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
        with SyncAPIClient() as client:
            client.get("/posts/1")
    except (APIConnectionError, APITimeoutError, APIRetryError) as exc:
        pytest.skip(
            "JSONPlaceholder への接続に失敗したため 404 契約検証を skip します"
            f"（ネットワーク障害が原因であり 404 契約バグではありません）: {exc}"
        )

    # Phase 2: 契約検証 — APIRetryError 含む全例外がテスト失敗として CI に報告される
    with SyncAPIClient() as client:
        with pytest.raises(APIHTTPError) as exc_info:
            client.get("/posts/999999")
        assert exc_info.value.status_code == 404
