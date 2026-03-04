"""
テストユーティリティヘルパー

respxを使ったHTTPモックテストの共通ヘルパー関数群。
sync/asyncテスト両方から利用可能。
"""

from __future__ import annotations

from typing import Any

import respx


def mock_get_route(url: str, params: dict[str, Any] | None, json_data: Any) -> respx.Route:
    """respx GETルートのparams有無対応ヘルパー

    respxのparams=はcontains match（サブセットマッチ）。
    paramsがNoneの場合はparams__eq={}を使用する（等価マッチ、クエリパラメータなしのリクエストのみにマッチ）。

    Args:
        url: モック対象のURL
        params: クエリパラメータ（Noneの場合はparams__eq={}を使用 - クエリパラメータなしのみマッチ）
        json_data: レスポンスとして返すJSONデータ

    Returns:
        respx.Route: call_count等の検証に使用可能なルートオブジェクト
    """
    if params is not None:
        return respx.get(url, params=params).respond(json=json_data)
    return respx.get(url, params__eq={}).respond(json=json_data)
