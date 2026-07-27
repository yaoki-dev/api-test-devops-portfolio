"""transaction / span スクラブのテスト

before_send_transaction 経路のイベント整形と span 単位のスクラブ
（_scrub_span_item）をカバー。
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from sentry_sdk.types import Event

import utils.sentry_scrub_events as sentry_events
from utils.sentry_scrub_events import _before_send
from utils.sentry_scrub_values import MAX_SCRUB_DEPTH

pytestmark = pytest.mark.unit


class TestBeforeSendTransaction:
    """transaction イベント（before_send_transaction 経路）の scrub テスト

    transaction は error と異なり top-level `spans` (list[dict]) を持つ
    (Sentry transaction payload spec)。`before_send_transaction=_before_send`
    配線により error と同一 scrub 経路を通り、span 内の機密キーが REDACT される
    ことを検証する。
    """

    def _call_before_send(self, event: Event) -> dict[str, Any]:
        result = _before_send(event, {})
        assert result is not None, "_before_send が None を返しました（イベントが破棄されました）"
        return cast(dict[str, Any], result)

    def test_transaction_spans_sensitive_keys_redacted(self) -> None:
        event = cast(
            Event,
            {
                "type": "transaction",
                "transaction": "/api/users",
                "spans": [
                    {
                        "op": "http.client",
                        "description": "GET /api/token",
                        "data": {
                            "auth_token": "secret-span-a",  # noqa: S106
                            "status_code": 200,
                        },
                    },
                    {
                        "op": "db.query",
                        "data": {"password": "secret-span-b", "rows": 5},  # noqa: S106
                    },
                ],
            },
        )
        result_dict = self._call_before_send(event)
        assert result_dict["spans"][0]["data"]["auth_token"] == "[REDACTED]"  # noqa: S105
        assert result_dict["spans"][1]["data"]["password"] == "[REDACTED]"  # noqa: S105
        # 非機密のデバッグ情報は保持される
        assert result_dict["spans"][0]["data"]["status_code"] == 200
        assert result_dict["spans"][1]["data"]["rows"] == 5
        assert result_dict["spans"][0]["op"] == "http.client"

    def test_transaction_span_description_query_string_redacted(self) -> None:
        """transaction span description の query PII を REDACT する。"""
        event = cast(
            Event,
            {
                "type": "transaction",
                "spans": [
                    {
                        "op": "http.client",
                        "description": (
                            "GET https://api.example.com/users/jane@example.com"
                            "?token=secret123&safe=1#secret-fragment"
                        ),
                        "data": {},
                    }
                ],
            },
        )

        result_dict = self._call_before_send(event)

        description = result_dict["spans"][0]["description"]
        assert "secret123" not in description
        assert "jane@example.com" not in description
        assert "secret-fragment" not in description
        assert "token=%5BREDACTED%5D" in description
        assert "safe=1" in description

    def test_transaction_internal_tag_skips_scrub_no_recursion(self) -> None:
        """内部通知タグ付き transaction は scrub をスキップ通過する（再帰防止）。

        `tags` は base Event の top-level 属性であり transaction にも継承されるため
        (Sentry event payload spec)、`_has_internal_tag` が transaction-shaped event
        でも発火し、before_send_transaction 経由の無限再帰を遮断する。
        """
        event = cast(
            Event,
            {
                "type": "transaction",
                "tags": {
                    sentry_events._INTERNAL_TAG_KEY: sentry_events._INTERNAL_TAG_VALUE,
                },
                "spans": [{"op": "db", "data": {"password": "not-scrubbed"}}],  # noqa: S106
            },
        )
        result_dict = self._call_before_send(event)
        # スキップ通過のため span は scrub されず原形のまま（再帰防止ガードの証明）
        assert result_dict["spans"][0]["data"]["password"] == "not-scrubbed"  # noqa: S105

    def test_error_event_without_spans_unaffected(self) -> None:
        """spans を持たない error イベントは "spans" 追加の影響を受けない（回帰防止）。"""
        event = cast(
            Event,
            {"request": {"headers": {"Cookie": "session=abc123"}}},
        )
        result_dict = self._call_before_send(event)
        assert "spans" not in result_dict
        assert result_dict["request"]["headers"]["Cookie"] == "[REDACTED]"

    def test_transaction_request_field_scrubbed_via_transaction_path(self) -> None:
        """transaction の top-level `request` も before_send_transaction 経路で scrub される。

        WSGI/ASGI 統合では transaction イベントにも `request` (headers/query_string/url)
        が付与される (Sentry公式)。span data より auth header 等の実 PII を含みやすいため、
        新規配線した before_send_transaction=_before_send 経路で request 既存 scrub ロジック
        (L745-770) が transaction-shaped event でも発火することを経験的に検証する。
        """
        event = cast(
            Event,
            {
                "type": "transaction",
                "transaction": "/api/users",
                "request": {
                    "headers": {"Authorization": "Bearer secret-xyz"},
                    "query_string": "token=leak123&page=2",
                    "url": "https://api.example.com/users?token=leak123",
                },
                "spans": [{"op": "http", "data": {"api_key": "sk-secret"}}],  # noqa: S106
            },
        )
        result_dict = self._call_before_send(event)
        # request の auth header が REDACT される
        assert result_dict["request"]["headers"]["Authorization"] == "[REDACTED]"
        # query_string 内のトークンが scrub される（_scrub_request_query_string 経路）
        assert "leak123" not in result_dict["request"]["query_string"]
        # url のクエリトークンが scrub される（_scrub_url 経路）
        assert "leak123" not in result_dict["request"]["url"]
        # span data も同時に scrub される
        assert result_dict["spans"][0]["data"]["api_key"] == "[REDACTED]"  # noqa: S105

    def test_transaction_structurally_valid_after_scrub(self) -> None:
        """scrub 後も transaction が構造的に有効なまま（Relay の silent drop 防止）。

        `_before_send` は `contexts` / `spans` を in-place scrub するため、
        transaction 必須フィールド（`type` / `start_timestamp` /
        `contexts.trace` の `trace_id` / `span_id`）が破壊されないことを保証する。
        これらは `_is_sensitive_key` 非該当のため REDACT されず原形を保つべき。
        破壊されると Relay が transaction を無言ドロップし、性能監視が機能しなくなる。
        """
        event = cast(
            Event,
            {
                "type": "transaction",
                "transaction": "/api/users",
                "start_timestamp": 1588601261.481961,
                "timestamp": 1588601261.488901,
                "contexts": {
                    "trace": {
                        "trace_id": "1e57b752bc6e4544bbaa246cd1d05dee",
                        "span_id": "b01b9f6349558cd1",
                        "op": "http.server",
                        # 機密キーは scrub されるが trace 構造は保持される
                        "data": {"auth_token": "secret"},  # noqa: S106
                    },
                },
                "spans": [
                    {
                        "op": "db",
                        "span_id": "aaaa1111bbbb2222",
                        "trace_id": "1e57b752bc6e4544bbaa246cd1d05dee",
                        "data": {"password": "secret"},  # noqa: S106
                    }
                ],
            },
        )
        result_dict = self._call_before_send(event)
        # 必須トップレベルフィールドが保持される
        assert result_dict["type"] == "transaction"
        assert result_dict["start_timestamp"] == 1588601261.481961
        # contexts.trace の識別子が破壊されない（非機密キーは原形保持）
        trace = result_dict["contexts"]["trace"]
        assert trace["trace_id"] == "1e57b752bc6e4544bbaa246cd1d05dee"
        assert trace["span_id"] == "b01b9f6349558cd1"
        assert trace["op"] == "http.server"
        # trace.data 内の機密キーは scrub される
        assert trace["data"]["auth_token"] == "[REDACTED]"  # noqa: S105
        # spans は依然 list で識別子が保持される
        assert isinstance(result_dict["spans"], list)
        assert result_dict["spans"][0]["span_id"] == "aaaa1111bbbb2222"
        assert result_dict["spans"][0]["trace_id"] == "1e57b752bc6e4544bbaa246cd1d05dee"
        assert result_dict["spans"][0]["data"]["password"] == "[REDACTED]"  # noqa: S105


class TestScrubSpanItem:
    """_scrub_span_item の直接単体テスト（T-2）。

    _before_send 経由の間接テストではカバーされないエッジケースを
    直接呼び出しで検証する。
    """

    def test_non_dict_input_list_delegates_to_scrub_list_item(self) -> None:
        """(a) 非dict入力（list）は _scrub_list_item に委譲される。

        平坦な文字列リストは機密キーコンテキストを持たないためそのまま保持される。
        """
        result = sentry_events._scrub_span_item(["foo", "bar"], _depth=0)
        assert result == ["foo", "bar"]

    def test_non_dict_scalar_delegates_to_scrub_list_item(self) -> None:
        result = sentry_events._scrub_span_item("plain-string", _depth=0)
        assert result == "plain-string"

    def test_max_depth_exceeded_returns_sentinel(self) -> None:
        """(b) _depth >= MAX_SCRUB_DEPTH のとき "[MAX_DEPTH_EXCEEDED]" を返す。"""
        result = sentry_events._scrub_span_item(
            {"description": "GET /path"}, _depth=MAX_SCRUB_DEPTH
        )
        assert result == "[MAX_DEPTH_EXCEEDED]"

    def test_description_without_space_and_query_scrubs_whole_via_scrub_url(self) -> None:
        """(c) descriptionにスペースなし + '?' → 全体を _scrub_url で処理しmethod prefixなし。

        "https://api.example.com/users?token=x" はスペースで分割されないため
        value_to_scrub = description 全体。'?' を含むので _scrub_url 経路。
        クエリの token 値が除去され、スキームとホストは保持される。
        """
        item = {"description": "https://api.example.com/users?token=x"}
        result = sentry_events._scrub_span_item(item, _depth=0)

        result_description = result["description"]
        assert result_description.startswith("https://")
        assert "token=x" not in result_description

    def test_description_with_space_and_query_scrubs_via_scrub_url_preserves_method(self) -> None:
        """(d) description が "GET /path?token=secret" 形式 → _scrub_url 経路でmethod保持。

        スペースで分割後 method="GET", target="/path?token=secret"。
        '?' を含むので _scrub_url が呼ばれ、クエリがスクラブされる。
        "GET " プレフィックスは保持される。
        """
        item = {"description": "GET /path?token=secret"}
        result = sentry_events._scrub_span_item(item, _depth=0)

        result_description = result["description"]
        assert result_description.startswith("GET ")
        assert "secret" not in result_description

    def test_description_path_email_pii_redacted_via_path_pii_pattern(self) -> None:
        """(e) description のpath内メールPII → _PATH_PII_PATTERN で [REDACTED] 置換。

        "GET /users/foo@example.com/profile" はスペースで分割後
        target="/users/foo@example.com/profile"。'?' も '#' も含まないため
        _PATH_PII_PATTERN.sub("[REDACTED]", ...) 経路。
        メールアドレスが [REDACTED] に置換され、"GET " プレフィックスと残りのパスは保持。
        """
        item = {"description": "GET /users/foo@example.com/profile"}
        result = sentry_events._scrub_span_item(item, _depth=0)

        result_description = result["description"]
        assert result_description.startswith("GET ")
        assert "foo@example.com" not in result_description
        assert "[REDACTED]" in result_description
        assert "/profile" in result_description
