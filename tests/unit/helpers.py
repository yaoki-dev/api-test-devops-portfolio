"""
テストユーティリティヘルパー

respxを使ったHTTPモックテストの共通ヘルパー関数群。
主にsyncテスト（test_sync_client.py）およびasyncテスト（test_async_client.py）で利用。
"""

from __future__ import annotations

from typing import Any

import respx


def mock_get_route(url: str, params: dict[str, Any] | None, json_data: Any) -> respx.Route:
    """respx GET ルートを、クエリ有無で正しいマッチ方式に分けて登録する。

    respx の params= は subset match なので、params=None は params__eq={} にして
    クエリなしリクエストだけに一致させる。@respx.mock/with respx.mock 外では
    ルート登録できてもモックが効かず、未モック通信は AllMockedAssertionError になる。
    """
    if params is not None:
        return respx.get(url, params=params).respond(json=json_data)
    return respx.get(url, params__eq={}).respond(json=json_data)


def assert_warning_log_count(log_output: list, event_name: str, expected_count: int) -> None:
    """structlog capture_logs() から指定 warning event の発生回数を検証する。"""
    warning_events = [log["event"] for log in log_output if log.get("log_level") == "warning"]
    assert warning_events.count(event_name) == expected_count, (
        f"Expected {expected_count} '{event_name}' warnings, got: {warning_events}"
    )


def make_mock_user(uid: int, **overrides: Any) -> dict[str, Any]:
    """完全な User 形状を生成し、overrides でフィールド単位の差分だけ表現する。"""
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


def make_canonical_user(
    user_id: int = 1,
    name: str = "Leanne Graham",
    username: str = "Bret",
    email: str = "Sincere@april.biz",
    website: str = "https://hildegard.org",
) -> dict[str, Any]:
    """JSONPlaceholder 実APIに近い正準 User 形状で、Pydantic 検証用の完全構造を返す。"""
    return {
        "id": user_id,
        "name": name,
        "username": username,
        "email": email,
        "address": {
            "street": "Kulas Light",
            "suite": "Apt. 556",
            "city": "Gwenborough",
            "zipcode": "92998-3874",
            "geo": {"lat": "-37.3159", "lng": "81.1496"},
        },
        "phone": "1-770-736-8031 x56442",
        "website": website,
        "company": {
            "name": "Romaguera-Crona",
            "catchPhrase": "Multi-layered client-server neural-net",
            "bs": "harness real-time e-markets",
        },
    }
