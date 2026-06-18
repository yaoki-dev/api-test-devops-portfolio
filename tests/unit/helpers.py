"""
テストユーティリティヘルパー

respxを使ったHTTPモックテストの共通ヘルパー関数群。
主にsyncテスト（test_sync_client.py）およびasyncテスト（test_async_client.py）で利用。
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
        呼び出すこと。コンテキスト外でもルート登録自体は成功するが、
        モックは機能しない。モックされていないリクエストが発行された場合、
        respxは AllMockedAssertionError を発生させる。

    Args:
        url: モック対象のURL
        params: クエリパラメータ（Noneの場合はparams__eq={}を使用 - クエリパラメータなしのみマッチ）
        json_data: レスポンスとして返すJSONデータ

    Returns:
        respx.Route: call_count等の検証に使用可能なルートオブジェクト

    Raises:
        なし（この関数自体は例外を発生させない）
    """
    if params is not None:
        return respx.get(url, params=params).respond(json=json_data)
    return respx.get(url, params__eq={}).respond(json=json_data)


def assert_warning_log_count(log_output: list, event_name: str, expected_count: int) -> None:
    """警告ログの発生回数を検証するヘルパー関数

    structlog の capture_logs() が収集したログエントリから、
    指定したイベント名の警告ログが期待回数発生していることを検証する。

    Args:
        log_output: capture_logs() が収集したログエントリのリスト
        event_name: 検証対象のイベント名
        expected_count: 期待する警告ログの発生回数
    """
    warning_events = [log["event"] for log in log_output if log.get("log_level") == "warning"]
    assert warning_events.count(event_name) == expected_count, (
        f"Expected {expected_count} '{event_name}' warnings, got: {warning_events}"
    )


def make_mock_user(uid: int, **overrides: Any) -> dict[str, Any]:
    """テスト用ユーザーデータのモック生成ファクトリ

    DRY原則に基づき、テストコード間でのモックデータ重複を排除する。
    デフォルトで完全なユーザー構造を生成し、**overridesで特定フィールドを上書き可能。

    Args:
        uid: ユーザーID
        **overrides: 上書きするフィールド名と値

    Returns:
        dict[str, Any]: 生成されたユーザーデータ辞書
    """
    user = {
        "id": uid,
        "name": f"User {uid}",
        "username": f"user{uid}",
        "email": f"user{uid}@example.com",
        "address": {
            "street": f"Street {uid}",
            "suite": f"Suite {uid}",
            "city": f"City {uid}",
            "zipcode": f"1000{uid}",
            "geo": {"lat": "0.0000", "lng": "0.0000"},
        },
        "phone": f"123-456-000{uid}",
        "website": f"https://user{uid}.example.com",
        "company": {
            "name": f"Company {uid}",
            "catchPhrase": f"Phrase {uid}",
            "bs": f"bs {uid}",
        },
    }
    user.update(overrides)
    return user
