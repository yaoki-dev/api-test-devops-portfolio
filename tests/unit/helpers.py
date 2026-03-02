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

    respxのparams=はsubset match（指定キーが存在し値が一致すれば通過）。
    paramsがNoneの場合はパラメータなしのURLとしてモック。

    Args:
        url: モック対象のURL
        params: クエリパラメータ（Noneの場合はパラメータなしでマッチ）
        json_data: レスポンスとして返すJSONデータ

    Returns:
        respx.Route: call_count等の検証に使用可能なルートオブジェクト
    """
    if params is not None:
        return respx.get(url, params=params).respond(json=json_data)
    return respx.get(url).respond(json=json_data)
