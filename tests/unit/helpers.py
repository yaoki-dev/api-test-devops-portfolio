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

    前提条件:
        必ず @respx.mock デコレータまたは with respx.mock: ブロック内から
        呼び出すこと。コンテキスト外から呼び出した場合、RuntimeError が発生する。

    Args:
        url: モック対象のURL
        params: クエリパラメータ（Noneの場合はparams__eq={}を使用 - クエリパラメータなしのみマッチ）
        json_data: レスポンスとして返すJSONデータ

    Returns:
        respx.Route: call_count等の検証に使用可能なルートオブジェクト

    Raises:
        RuntimeError: @respx.mock コンテキスト外から呼び出した場合
    """
    if params is not None:
        return respx.get(url, params=params).respond(json=json_data)
    return respx.get(url, params__eq={}).respond(json=json_data)
