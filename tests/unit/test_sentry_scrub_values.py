"""値スクラブ（values）のテスト

_scrub_sensitive_data とURL / クエリ文字列 / パスパラメータのスクラブをカバー。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

import utils.sentry_scrub_events as sentry_events
import utils.sentry_scrub_primitives as sentry_primitives
import utils.sentry_scrub_values as sentry_values
from utils.sentry_scrub_values import (
    MAX_SCRUB_DEPTH,
    _scrub_query_string,
    _scrub_sensitive_data,
    _scrub_url,
)

pytestmark = pytest.mark.unit


class TestScrubSensitiveData:
    """機密データスクラブのテスト"""

    def test_scrub_password_field(self) -> None:
        data = {"password": "dummy", "display_name": "user"}
        result = _scrub_sensitive_data(data)
        assert result["password"] == "[REDACTED]"  # noqa: S105
        assert result["display_name"] == "user"

    def test_scrub_nested_dict(self) -> None:
        data = {"user": {"api_key": "key123", "email": "user@example.com"}}
        result = _scrub_sensitive_data(data)
        assert result["user"]["api_key"] == "[REDACTED]"
        assert result["user"]["email"] == "[REDACTED]"  # email はPII（GDPR対応）でスクラブ対象

    def test_scrub_list_of_dicts(self) -> None:
        data = {
            "headers": [
                {"Authorization": "Bearer token123"},
                {"Content-Type": "application/json"},
            ],
        }
        result = _scrub_sensitive_data(data)
        assert result["headers"][0]["Authorization"] == "[REDACTED]"
        assert result["headers"][1]["Content-Type"] == "application/json"

    def test_scrub_nested_list(self) -> None:
        data = {"items": [[{"x-auth-token": "tok"}, {"name": "public"}]]}
        result = _scrub_sensitive_data(data)
        assert result["items"][0][0]["x-auth-token"] == "[REDACTED]"  # noqa: S105
        assert result["items"][0][1]["name"] == "public"

    def test_scrub_case_insensitive(self) -> None:
        data = {"PASSWORD": "secret", "Api_Key": "key", "TOKEN": "tok"}
        result = _scrub_sensitive_data(data)
        assert result["PASSWORD"] == "[REDACTED]"  # noqa: S105
        assert result["Api_Key"] == "[REDACTED]"
        assert result["TOKEN"] == "[REDACTED]"  # noqa: S105

    @pytest.mark.parametrize(
        "input_data,expected",
        [
            (None, None),
            ([], []),
            ("string", "string"),
            (123, 123),
            (True, True),
        ],
    )
    def test_scrub_non_dict_passthrough(self, input_data: Any, expected: Any) -> None:
        assert _scrub_sensitive_data(input_data) == expected

    def test_scrub_non_dict_triggers_fail_open_warning(self) -> None:
        """非dict入力時にfail-open警告がログ出力され、データはそのまま返る。"""
        with patch.object(sentry_primitives._logger, "warning") as mock_warning:
            result = _scrub_sensitive_data("not_a_dict")
        assert result == "not_a_dict"
        mock_warning.assert_called_once()
        call_kwargs = mock_warning.call_args[1]
        assert call_kwargs["actual_type"] == "str"
        assert call_kwargs["action"] == "return_as_is"

    def test_scrub_empty_dict(self) -> None:
        assert _scrub_sensitive_data({}) == {}

    def test_scrub_deeply_nested(self) -> None:
        data = {"level1": {"level2": {"level3": {"secret": "deep_secret", "public": "visible"}}}}
        result = _scrub_sensitive_data(data)
        assert result["level1"]["level2"]["level3"]["secret"] == "[REDACTED]"  # noqa: S105
        assert result["level1"]["level2"]["level3"]["public"] == "visible"

    def test_scrub_preserves_original(self) -> None:
        original = {"password": "dummy"}
        _scrub_sensitive_data(original)
        assert original["password"] == "dummy"  # noqa: S105

    def test_scrub_max_depth_exceeded(self) -> None:
        # MAX_SCRUB_DEPTH階層のネストを作成
        """再帰制限を超えると[MAX_DEPTH_EXCEEDED]を返す（循環参照対策）"""
        deep_data: dict[str, Any] = {"safe_key": "value"}
        current = deep_data
        for i in range(MAX_SCRUB_DEPTH + 2):
            current["nested"] = {"level": i}
            current = current["nested"]

        result = _scrub_sensitive_data(deep_data)

        # 深い階層は[MAX_DEPTH_EXCEEDED]になる
        nested = result
        for _ in range(MAX_SCRUB_DEPTH):
            nested = nested.get("nested", nested)
        assert nested == "[MAX_DEPTH_EXCEEDED]"

    def test_scrub_max_depth_constant(self) -> None:
        assert MAX_SCRUB_DEPTH == 10
        assert isinstance(MAX_SCRUB_DEPTH, int)


class TestScrubQueryStringAndUrl:
    """query string / URL スクラブのテスト"""

    def test_scrub_query_string_preserves_duplicate_params(self) -> None:
        result = _scrub_query_string("token=a&safe=1&token=b&empty=")
        assert result == "token=%5BREDACTED%5D&safe=1&token=%5BREDACTED%5D&empty="

    def test_scrub_request_query_string_accepts_bytes(self) -> None:
        result = sentry_values._scrub_request_query_string(b"token=a&safe=1")
        assert result == "token=%5BREDACTED%5D&safe=1"

    def test_scrub_url_removes_userinfo_and_fragment(self) -> None:
        url = "https://user:pass@example.com/path?x-access-token=tok&safe=1#frag"
        result = _scrub_url(url)
        assert result == "https://example.com/path?x-access-token=%5BREDACTED%5D&safe=1"

    def test_scrub_url_preserves_non_sensitive_query_params(self) -> None:
        url = "https://example.com/path?page=2&sort=asc"
        assert _scrub_url(url) == url

    def test_scrub_url_path_params_sensitive_key_scrubbed(self) -> None:
        """path param の機密キー値は query と一貫してスクラブされる (B-1 Option A)。

        session_id は _is_sensitive_key で True となるため [REDACTED] に置換される。
        非機密キー (sort=asc) は保持される。fragment は除去される。
        """
        result = _scrub_url("https://example.com/path;session_id=secret?sort=asc#frag")
        assert "session_id=secret" not in result
        assert "session_id=[REDACTED]" in result
        assert "sort=asc" in result
        assert "#" not in result

    def test_scrub_url_redacts_email_in_path(self) -> None:
        result = _scrub_url("https://example.com/users/user@example.com/profile?sort=asc")
        assert "user@example.com" not in result
        assert "[REDACTED]" in result
        assert "sort=asc" in result  # query は保持

    def test_scrub_url_redacts_email_in_path_params(self) -> None:
        result = _scrub_url("https://example.com/activate;email=user@example.com?sort=asc")
        assert "user@example.com" not in result
        assert "[REDACTED]" in result
        assert "sort=asc" in result  # query は保持

    def test_scrub_url_handles_ipv6_and_invalid_port(self) -> None:
        """IPv6と不正ポートでも例外を出さず処理する"""
        assert _scrub_url("http://user@[::1]:8080/path?token=a#frag") == (
            "http://[::1]:8080/path?token=%5BREDACTED%5D"
        )
        assert _scrub_url("http://example.com:bad/path?token=a#frag") == (
            "http://example.com/path?token=%5BREDACTED%5D"
        )

    def test_scrub_url_handles_no_hostname(self) -> None:
        """hostname=None (空ホストのURL) で netloc='' が返ること。

        urlparse("http:///path?token=abc").hostname is None になるURL を渡した際、
        _scrub_url 内 L251 の `if hostname is None: netloc = ""` 分岐を通過する。
        query の機密値はスクラブされ、scheme:// と path は保持されること。
        """
        result = _scrub_url("http:///path?token=abc")
        # hostname=None 分岐 → netloc="" → "http:///path?..." の形式で返る
        assert result == "http:///path?token=%5BREDACTED%5D"
        # abc (token値) はスクラブ済み
        assert "abc" not in result

    def test_scrub_url_fragment_only_is_removed(self) -> None:
        """fragment-only URL の fragment が除去される（PII 漏洩防止）。"""
        result = _scrub_url("https://example.com/path#secret-fragment")
        assert "#" not in result
        assert result == "https://example.com/path"


class TestScrubSentryFieldExceptionAsList:
    """#1 blocker: exception フィールドが list 形式でも PII がスクラブされることを検証する。

    Sentry 標準形は dict だが custom before_send 等で list 形態が生じうる。dict 要素は
    exception 専用スクラブで values[*].value REDACTION と stackframe vars scrub を適用し、
    非 dict 要素は汎用 _scrub_list_item で再帰スクラブする
    (dispatch 全分岐で素通しゼロ・defense-in-depth 一貫性)。
    """

    def test_exception_as_list_redacts_value_and_scrubs_frame_vars(self) -> None:
        event_dict: dict[str, Any] = {
            "exception": [
                {
                    "type": "ValueError",
                    "value": "password=hunter2 in message",
                    "stacktrace": {"frames": [{"vars": {"api_key": "sk-secret"}}]},
                }
            ]
        }
        sentry_events._scrub_sentry_field(event_dict, "exception")

        item = event_dict["exception"][0]
        assert item["value"] == "[REDACTED]"  # 例外メッセージ全体を redact
        assert item["type"] == "ValueError"  # type は観測性のため保持
        assert item["stacktrace"]["frames"][0]["vars"]["api_key"] == "[REDACTED]"

    def test_exception_as_list_scalar_item_preserved(self) -> None:
        """list 内の scalar 要素は _scrub_list_item 経由でも原形保持し、クラッシュしない。

        scalar(str/int)はキーコンテキストを持たないため _scrub_list_item は
        redact せず原形を返す(キーベース scrub の仕様限界)。素通しではなく
        汎用スクラバを通過した結果の不変であることを担保する。
        """
        event_dict: dict[str, Any] = {"exception": ["not-a-dict", 42]}
        sentry_events._scrub_sentry_field(event_dict, "exception")

        assert event_dict["exception"] == ["not-a-dict", 42]

    def test_exception_as_list_nested_container_item_is_scrubbed(self) -> None:
        """list 内の非 dict コンテナ(list/tuple)に内包された機密キーも再帰スクラブされる。

        codex adversarial review 指摘の defense-in-depth 穴を塞ぐ: 旧実装は非 dict 要素を
        素通し(原形保持)していたため、custom before_send が exception を
        list[list[dict]] 形態で生成した場合に内側の PII が漏洩しえた。
        _scrub_list_item への委譲により、tags/spans 等の他 list 分岐と同様に
        ネスト機密キーを redact する。
        """
        event_dict: dict[str, Any] = {
            "exception": [["context", {"password": "hunter2"}]],  # noqa: S106
        }
        sentry_events._scrub_sentry_field(event_dict, "exception")

        nested = event_dict["exception"][0]
        assert nested[0] == "context"  # 非機密 scalar は保持
        assert nested[1]["password"] == "[REDACTED]"  # noqa: S105  # ネスト機密キーは redact


class TestScrubUrlPathParams:
    """RFC 2396 path params のPII/secretスクラブ回帰テスト"""

    def test_percent_encoded_sensitive_key_is_redacted(self) -> None:
        url = "https://example.com/path;%73ession_id=secret"

        result = _scrub_url(url)

        assert result == "https://example.com/path;%73ession_id=[REDACTED]"
        assert "secret" not in result

    def test_email_pii_in_key_position_is_redacted(self) -> None:
        """key=value の key 側に email PII があっても漏らさない。"""
        url = "https://example.com/path;contact@example.com=true"

        result = _scrub_url(url)

        assert result == "https://example.com/path;[REDACTED]=true"
        assert "contact@example.com" not in result

    def test_empty_key_redacts_value(self) -> None:
        """空キーは機密性を判定できないため値を conservative に隠す。"""
        url = "https://example.com/path;=password123"

        result = _scrub_url(url)

        assert result == "https://example.com/path;=[REDACTED]"
        assert "password123" not in result

    def test_no_equals_path_param_preserves_non_pii_segment(self) -> None:
        """値なし matrix param は PII でなければそのまま保持する。"""
        assert _scrub_url("https://example.com/path;jsessionid") == (
            "https://example.com/path;jsessionid"
        )

    def test_no_equals_path_param_redacts_email_pii_segment(self) -> None:
        """値なし matrix param 全体に email PII があれば除去する。"""
        result = _scrub_url("https://example.com/path;contact@example.com")

        assert result == "https://example.com/path;[REDACTED]"
        assert "contact@example.com" not in result


def test_scrub_url_handles_ipv6_without_port() -> None:
    """IPv6 アドレス（ポートなし）を含む URL でも例外を出さず token をスクラブする (#12-Q-10)。"""
    url = "http://[::1]/path?token=abc"
    result = _scrub_url(url)
    assert "[::1]" in result  # netloc 保持
    assert "abc" not in result  # token 値スクラブ済み
