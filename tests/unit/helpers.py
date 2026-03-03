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
    paramsがNoneの場合はparams={}を使用する。
    params={}はcontains lookupのため空集合はすべての集合のサブセットとなり、
    クエリパラメータの有無にかかわらず任意のリクエストにマッチする点に注意。
    クエリパラメータなしのリクエストのみに限定するには params__eq={} が必要だが、
    現在のユースケース（単一ルート登録）では実質的な問題はない。

    Args:
        url: モック対象のURL
        params: クエリパラメータ（Noneの場合はparams={}を使用 - 任意リクエストにマッチ）
        json_data: レスポンスとして返すJSONデータ

    Returns:
        respx.Route: call_count等の検証に使用可能なルートオブジェクト
    """
    if params is not None:
        return respx.get(url, params=params).respond(json=json_data)
    return respx.get(url, params={}).respond(json=json_data)
