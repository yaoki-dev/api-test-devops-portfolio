"""Sentryイベント整形（events）のテスト

_before_send を中心としたイベント整形・例外スクラブ・再帰ガードをカバー。

transaction / span のスクラブは test_sentry_transaction_span.py、
例外フィールド・内部タグ・extras の補助関数の直接テストは
test_sentry_scrub_event_helpers.py 側にある。
"""

from __future__ import annotations

import sys
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from sentry_sdk.types import Event

import utils.sentry_scrub_events as sentry_events
import utils.sentry_scrub_primitives as sentry_primitives
import utils.sentry_scrub_values as sentry_values
from utils.sentry_scrub_events import (
    _SCRUBBED_EVENT_FIELDS,
    _before_send,
)
from utils.sentry_scrub_values import MAX_SCRUB_DEPTH

pytestmark = pytest.mark.unit


def test_scrubbed_event_fields_match_expected_contract() -> None:
    """_SCRUBBED_EVENT_FIELDS の網羅性テスト"""
    assert isinstance(_SCRUBBED_EVENT_FIELDS, frozenset)
    assert _SCRUBBED_EVENT_FIELDS == frozenset(
        {
            "extra",
            "user",
            "contexts",
            "tags",
            "breadcrumbs",
            "spans",
            "exception",
        }
    )


class TestBeforeSend:
    """Sentry送信前フックのテスト"""

    def _call_before_send(self, event: Event) -> dict[str, Any]:
        """_before_send を呼び出し、非Noneを保証して dict として返すヘルパー。

        全テストメソッドで共通の「None検証 + キャスト」パターンを集約。
        Noneチェック漏れによる偽陽性を防ぐ。
        """
        result = _before_send(event, {})
        assert result is not None, "_before_send が None を返しました（イベントが破棄されました）"
        return cast(dict[str, Any], result)

    def test_scrub_request_headers(self) -> None:
        event = cast(Event, {"request": {"headers": {"Cookie": "session=abc123"}}})
        result_dict = self._call_before_send(event)
        assert result_dict["request"]["headers"]["Cookie"] == "[REDACTED]"

    def test_scrub_request_cookies_and_env(self) -> None:
        event = cast(
            Event,
            {
                "request": {
                    "cookies": {"session": "abc123", "theme": "dark"},
                    "env": {
                        "HTTP_AUTHORIZATION": "Bearer token",
                        "SERVER_NAME": "example.com",
                    },
                }
            },
        )
        result_dict = self._call_before_send(event)
        assert result_dict["request"]["cookies"]["session"] == "[REDACTED]"
        assert result_dict["request"]["cookies"]["theme"] == "dark"
        assert result_dict["request"]["env"]["HTTP_AUTHORIZATION"] == "[REDACTED]"
        assert result_dict["request"]["env"]["SERVER_NAME"] == "example.com"

    def test_scrub_request_data(self) -> None:
        event = cast(Event, {"request": {"data": {"password": "secret", "username": "user"}}})
        result_dict = self._call_before_send(event)
        assert result_dict["request"]["data"]["password"] == "[REDACTED]"  # noqa: S105
        assert result_dict["request"]["data"]["username"] == "[REDACTED]"

    def test_scrub_request_data_non_dict_replaced_with_redacted(self) -> None:
        """request.data が非dict/listの場合、PII素通りを防ぐため fail-closed にする。"""
        event = cast(Event, {"request": {"data": "password=secret&token=abc"}})

        with patch.object(sentry_primitives._logger, "warning") as mock_warning:
            result_dict = self._call_before_send(event)

        assert result_dict["request"]["data"] == "[REDACTED]"
        mock_warning.assert_called_once()
        assert mock_warning.call_args.args == ("sentry_request_field_type_unexpected",)
        call_kwargs = mock_warning.call_args[1]
        assert call_kwargs["actual_type"] == "str"
        assert call_kwargs["action"] == "replaced_with_redacted"

    def test_scrub_extra_data(self) -> None:
        event = cast(Event, {"extra": {"token": "secret_token"}})
        result_dict = self._call_before_send(event)
        assert result_dict["extra"]["token"] == "[REDACTED]"  # noqa: S105

    def test_scrub_extra_body_preview(self) -> None:
        event = cast(Event, {"extra": {"body_preview": "password=secret"}})
        result_dict = self._call_before_send(event)
        assert result_dict["extra"]["body_preview"] == "[REDACTED]"  # noqa: S105

    def test_scrub_tags(self) -> None:
        event = cast(Event, {"tags": {"api_key": "key123"}})
        result_dict = self._call_before_send(event)
        assert result_dict["tags"]["api_key"] == "[REDACTED]"

    def test_scrub_breadcrumbs(self) -> None:
        event = cast(Event, {"breadcrumbs": {"values": [{"data": {"set-cookie": "a=b"}}]}})
        result_dict = self._call_before_send(event)
        assert result_dict["breadcrumbs"]["values"][0]["data"]["set-cookie"] == "[REDACTED]"

    def test_scrub_breadcrumbs_list_form(self) -> None:
        event = cast(
            Event,
            {"breadcrumbs": [{"data": {"Authorization": "Bearer secret", "request_id": "req-1"}}]},
        )
        result_dict = self._call_before_send(event)
        breadcrumb = result_dict["breadcrumbs"][0]
        assert breadcrumb["data"]["Authorization"] == "[REDACTED]"
        assert breadcrumb["data"]["request_id"] == "req-1"

    def test_scrub_tags_tuple_form(self) -> None:
        """tags が list[tuple[str, str]] 形式 (Sentry SDK 標準) で機密キーが redact される"""
        event = cast(Event, {"tags": [("user_password", "secret"), ("name", "public")]})
        result_dict = self._call_before_send(event)
        # tuple は scrub 後も sequence のまま
        scrubbed = list(result_dict["tags"])
        assert (scrubbed[0][0], scrubbed[0][1]) == ("user_password", "[REDACTED]")
        assert (scrubbed[1][0], scrubbed[1][1]) == ("name", "public")

    def test_scrub_tags_list_pair_form(self) -> None:
        event = cast(Event, {"tags": [["api_token", "abc"], ["safe", "ok"]]})
        result_dict = self._call_before_send(event)
        scrubbed = list(result_dict["tags"])
        assert (scrubbed[0][0], scrubbed[0][1]) == ("api_token", "[REDACTED]")
        assert (scrubbed[1][0], scrubbed[1][1]) == ("safe", "ok")

    def test_scrub_tags_dict_form_defense_in_depth(self) -> None:
        """tags が非標準 list[dict] 形式でも defense-in-depth で機密キーが redact される

        Sentry SDK 標準仕様外だが custom before_send hook 等で生じうるため
        PII 漏洩を防ぐ目的で dict 要素も再帰スクラブする。
        """
        event = cast(Event, {"tags": [{"authorization": "Bearer X", "label": "public"}]})
        result_dict = self._call_before_send(event)
        tag_dict = result_dict["tags"][0]
        assert tag_dict["authorization"] == "[REDACTED]"
        assert tag_dict["label"] == "public"

    def test_scrub_tags_non_sensitive_preserved(self) -> None:
        event = cast(Event, {"tags": [("environment", "production"), ("version", "1.0.0")]})
        result_dict = self._call_before_send(event)
        scrubbed = list(result_dict["tags"])
        assert (scrubbed[0][0], scrubbed[0][1]) == ("environment", "production")
        assert (scrubbed[1][0], scrubbed[1][1]) == ("version", "1.0.0")

    def test_scrub_breadcrumbs_2_element_list_not_overscrubbed(self) -> None:
        """breadcrumbs 内の非PII 2要素 list ([label, value]) が誤って tag-pair 扱いされない

        regression test: 旧コードでは list[2]+str[0] heuristic が breadcrumbs まで適用され、
        非機密の表示用ペアまで [REDACTED] になっていた。
        """
        event = cast(
            Event,
            {
                "breadcrumbs": [
                    {"category": "ui", "data": [["display_label", "visible-text"]]},
                ],
            },
        )
        result_dict = self._call_before_send(event)
        # breadcrumbs[0].data は dict、その中の list は generic scrub に流れるため
        # ["display_label", "visible-text"] は tag-pair 扱いされない。
        breadcrumb_data = result_dict["breadcrumbs"][0]["data"]
        # _scrub_sensitive_data が dict を recurse、list value は要素ごと処理されるが
        # str element はそのまま preserved
        assert breadcrumb_data == [["display_label", "visible-text"]]

    def test_scrub_request_preserves_duplicate_query_params(self) -> None:
        event = cast(Event, {"request": {"query_string": "token=a&safe=1&token=b"}})
        result_dict = self._call_before_send(event)
        assert (
            result_dict["request"]["query_string"]
            == "token=%5BREDACTED%5D&safe=1&token=%5BREDACTED%5D"
        )

    def test_scrub_request_query_string_accepts_bytes(self) -> None:
        event = cast(Event, {"request": {"query_string": b"token=a&safe=1"}})
        result_dict = self._call_before_send(event)
        assert result_dict["request"]["query_string"] == "token=%5BREDACTED%5D&safe=1"

    def test_scrub_request_url_removes_userinfo_and_fragment(self) -> None:
        event = cast(
            Event,
            {"request": {"url": "https://user:pass@example.com/path?x-auth-token=tok#fragment"}},
        )
        result_dict = self._call_before_send(event)
        assert (
            result_dict["request"]["url"] == "https://example.com/path?x-auth-token=%5BREDACTED%5D"
        )

    def test_before_send_fail_closed_without_partial_request_mutation(self) -> None:
        """スクラブ例外時はNoneを返し、元requestを部分変更せず Sentry に内部通知を送る"""
        original_request = {
            "headers": {"Authorization": "Bearer token"},
            "data": {"password": "secret"},
        }
        event = cast(Event, {"request": original_request})

        with (
            patch.object(
                sentry_values,
                "_scrub_sensitive_data",
                side_effect=[{"Authorization": "[REDACTED]"}, RuntimeError("boom")],
            ),
            patch.object(sentry_events, "_emit_scrub_failure_to_sentry") as mock_emit,
        ):
            result = _before_send(event, {})

        assert result is None
        assert event["request"] is original_request
        assert original_request == {
            "headers": {"Authorization": "Bearer token"},
            "data": {"password": "secret"},
        }
        mock_emit.assert_called_once()
        passed_exc = mock_emit.call_args.args[0]
        assert isinstance(passed_exc, RuntimeError)
        assert str(passed_exc) == "boom"

    def test_before_send_fail_closed_when_scrub_exception_field_raises(self) -> None:
        event = cast(
            Event,
            {
                "exception": {
                    "values": [{"stacktrace": {"frames": [{"vars": {"password": "secret"}}]}}]
                }
            },
        )

        with (
            patch.object(
                sentry_events,
                "_scrub_exception_field",
                side_effect=RuntimeError("exception-scrub-boom"),
            ),
            patch.object(sentry_events, "_emit_scrub_failure_to_sentry") as mock_emit,
        ):
            result = _before_send(event, {})

        assert result is None
        mock_emit.assert_called_once()

    def test_before_send_fail_closed_when_scrub_url_raises(self) -> None:
        """_scrub_url が例外を発生させた場合も fail-closed でイベントをdropする。

        drop ログは _logger.error 一本化で event_id を付与する。
        _safe_log_warning はロガー障害時のフォールバック専用のため通常は呼ばれない。
        """
        event = cast(Event, {"request": {"url": "https://example.com/path?token=abc"}})

        with (
            patch.object(sentry_events, "_scrub_url", side_effect=RuntimeError("url-scrub-boom")),
            patch.object(sentry_events, "_emit_scrub_failure_to_sentry") as mock_emit,
            patch.object(sentry_events, "_logger") as mock_logger,
            patch.object(sentry_events, "_safe_log_warning") as mock_warning,
        ):
            result = _before_send(event, {})

        assert result is None
        mock_logger.error.assert_called_once_with(
            "sentry_before_send_drop_event",
            error_type="RuntimeError",
            error_module="builtins",
            event_id=None,
        )
        mock_warning.assert_not_called()
        mock_emit.assert_called_once()

    def test_before_send_passes_event_id_to_scrub_failure_notification(self) -> None:
        """scrub 失敗時に event_id を内部通知へ渡す。"""
        event = cast(
            Event,
            {
                "event_id": "evt-789",
                "request": {"url": "https://example.com/path?token=abc"},
            },
        )

        with (
            patch.object(sentry_events, "_scrub_url", side_effect=RuntimeError("boom")),
            patch.object(sentry_events, "_emit_scrub_failure_to_sentry") as mock_emit,
        ):
            result = _before_send(event, {})

        assert result is None
        mock_emit.assert_called_once()
        assert isinstance(mock_emit.call_args.args[0], RuntimeError)
        assert mock_emit.call_args.kwargs == {"event_id": "evt-789"}

    @pytest.mark.parametrize(
        "emit_error",
        [MemoryError("emit-oom"), RecursionError("emit-depth")],
    )
    def test_before_send_fail_closed_when_emit_reraises_system_error(
        self, emit_error: BaseException
    ) -> None:
        """emit がシステム異常 (MemoryError/RecursionError) を再 raise しても、SF-1 の
        呼び出し側 try/except が捕捉し event を drop (None) する。

        _emit_scrub_failure_to_sentry は内部でシステム異常を fail-fast 再 raise する設計だが、
        その再 raise は scrub ブロックの except (MemoryError, RecursionError) の外で発生するため
        SF-1 の保護が無いと return None を飛び越えて _before_send 外へ伝播し、fail-closed ドロップが
        Sentry SDK の capture_internal_exceptions 挙動依存になる。本テストは SF-1 が emit 経路の
        fail-closed を SDK 非依存で確定させることを保証する（SF-1 除去時は再 raise が伝播し失敗）。
        """
        event = cast(Event, {"request": {"url": "https://example.com/path?token=abc"}})

        with (
            patch.object(sentry_events, "_scrub_url", side_effect=RuntimeError("url-scrub-boom")),
            patch.object(
                sentry_events,
                "_emit_scrub_failure_to_sentry",
                side_effect=emit_error,
            ),
        ):
            # SF-1 が無いと emit_error がこの呼び出しで伝播する（red 条件）。
            result = _before_send(event, {})

        assert result is None

    def test_before_send_secondary_fallback_when_logger_error_raises(self) -> None:
        """scrub 失敗ログ出力中に _logger.error 自体が例外を投げた場合、二次 fallback の
        _safe_log_warning へ fall through し、event は drop (None) される。

        既存 `test_before_send_fail_closed_when_scrub_url_raises` は _logger.error 正常系
        (mock_warning.assert_not_called()) のみカバーする。本テストはロガー障害時の
        二次 fallback 分岐 (sentry_init.py) を明示的に回帰検証する。
        一次 _logger.error は event_id を付与するが、フォールバック _safe_log_warning は
        event_id を渡さない (フォールバックはロガー障害時専用)。
        """
        event = cast(Event, {"request": {"url": "https://example.com/path?token=abc"}})

        with (
            patch.object(sentry_events, "_scrub_url", side_effect=RuntimeError("url-scrub-boom")),
            patch.object(sentry_events, "_emit_scrub_failure_to_sentry") as mock_emit,
            patch.object(sentry_events, "_logger") as mock_logger,
            patch.object(sentry_events, "_safe_log_warning") as mock_warning,
        ):
            mock_logger.error.side_effect = RuntimeError("logger-error-boom")
            result = _before_send(event, {})

        assert result is None
        # 一次ログ (_logger.error) が試行されて失敗 → 二次 fallback へ遷移
        mock_logger.error.assert_called_once()
        # 二次 fallback は event_id なしで scrub_exc の型情報のみ記録
        mock_warning.assert_called_once_with(
            "sentry_before_send_drop_event",
            error_type="RuntimeError",
            error_module="builtins",
        )
        mock_emit.assert_called_once()

    def test_before_send_drops_event_on_memory_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """MemoryError は fail-closed で event を drop し None を返す。

        旧仕様 (raise) では before_send からの例外を Sentry SDK が内部 catch し
        PII 付き event をそのまま送信し続けるリスクがあるため、stderr の最小通知に
        留めて return None で安全に遮断する (CWE-391 対策)。
        """
        event = cast(Event, {"request": {"headers": {}}})
        with (
            patch.object(sentry_values, "_scrub_sensitive_data", side_effect=MemoryError()),
            patch.object(sentry_events, "_emit_scrub_failure_to_sentry") as mock_emit,
        ):
            result = _before_send(event, {})

        assert result is None
        captured = capsys.readouterr()
        assert "[SENTRY_SCRUB_FAILED]" in captured.err
        assert "before_send system error: MemoryError or RecursionError" in captured.err
        mock_emit.assert_not_called()

    def test_before_send_drops_event_on_recursion_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """RecursionError は fail-closed で event を drop し None を返す。

        詳細は test_before_send_drops_event_on_memory_error の docstring 参照。
        """
        event = cast(Event, {"extra": {"key": "value"}})
        with (
            patch.object(sentry_events, "_scrub_sentry_field", side_effect=RecursionError()),
            patch.object(sentry_events, "_emit_scrub_failure_to_sentry") as mock_emit,
        ):
            result = _before_send(event, {})

        assert result is None
        captured = capsys.readouterr()
        assert "[SENTRY_SCRUB_FAILED]" in captured.err
        assert "before_send system error: MemoryError or RecursionError" in captured.err
        mock_emit.assert_not_called()

    def test_before_send_exception_scalar_replaced_with_safe_placeholder(self) -> None:
        """scalar exception は Sentry 仕様準拠の安全な placeholder に置換する。"""
        event = cast(Event, {"event_id": "evt-exc", "exception": "raw secret token=abc"})

        with patch.object(sentry_primitives._logger, "warning") as mock_warning:
            result_dict = self._call_before_send(event)

        assert result_dict["exception"] == {
            "values": [
                {
                    "type": "ScrubbedException",
                    "value": "[REDACTED: unscrubable exception structure]",
                }
            ]
        }
        mock_warning.assert_called_once()
        assert mock_warning.call_args.kwargs["action"] == "replaced_with_safe_placeholder"
        assert mock_warning.call_args.kwargs["event_id"] == "evt-exc"

    def test_before_send_skips_scrub_for_internal_tagged_event(self) -> None:
        """再帰防止: 内部通知 tag が付与された event は scrub をスキップし通過させる。

        この挙動が無いと _emit_scrub_failure_to_sentry → capture_message → _before_send
        の経路で scrub が再実行され、例外が出続けると無限再帰となる。
        """
        event = cast(
            Event,
            {
                "tags": {
                    sentry_events._INTERNAL_TAG_KEY: sentry_events._INTERNAL_TAG_VALUE,
                },
                "request": {"headers": {"Authorization": "Bearer SECRET"}},
            },
        )

        with patch.object(sentry_events, "_scrub_sensitive_data") as mock_scrub:
            result = _before_send(event, {})

        assert result is not None
        assert result is event
        mock_scrub.assert_not_called()
        assert result["request"]["headers"]["Authorization"] == "Bearer SECRET"

    def test_before_send_skips_scrub_for_list_form_internal_tagged_event(self) -> None:
        """再帰防止: list[tuple] 形式 tags でも内部通知 tag は検出され scrub をスキップする。

        Sentry SDK 現行版は scope.set_tag 経由で dict 形式 event["tags"] を生成するが、
        SDK 仕様変更や別経路 emit で list[tuple[str, str]] 形式が渡る可能性に備える
        defense-in-depth (_has_internal_tag 参照)。
        """
        event = cast(
            Event,
            {
                "tags": [
                    ("env", "prod"),
                    (
                        sentry_events._INTERNAL_TAG_KEY,
                        sentry_events._INTERNAL_TAG_VALUE,
                    ),
                ],
                "request": {"headers": {"Authorization": "Bearer SECRET"}},
            },
        )

        with patch.object(sentry_events, "_scrub_sensitive_data") as mock_scrub:
            result = _before_send(event, {})

        assert result is not None
        assert result is event
        mock_scrub.assert_not_called()
        assert result["request"]["headers"]["Authorization"] == "Bearer SECRET"

    def test_emit_scrub_failure_to_sentry_sets_internal_tag(self) -> None:
        mock_scope = MagicMock()
        mock_scope.__enter__ = MagicMock(return_value=mock_scope)
        mock_scope.__exit__ = MagicMock(return_value=False)
        mock_sdk = MagicMock()
        mock_sdk.new_scope = MagicMock(return_value=mock_scope)

        with patch.dict(sys.modules, {"sentry_sdk": mock_sdk}):
            sentry_events._emit_scrub_failure_to_sentry(RuntimeError("scrub-boom"))

        mock_scope.set_tag.assert_any_call(
            sentry_events._INTERNAL_TAG_KEY,
            sentry_events._INTERNAL_TAG_VALUE,
        )
        mock_scope.set_level.assert_called_once_with("error")
        mock_scope.capture_message.assert_called_once_with("sentry_scrub_failed", level="error")

    def test_emit_scrub_failure_to_sentry_sets_event_id_extra(self) -> None:
        """_emit_scrub_failure_to_sentry は event_id を extra に付与する。"""
        mock_scope = MagicMock()
        mock_scope.__enter__ = MagicMock(return_value=mock_scope)
        mock_scope.__exit__ = MagicMock(return_value=False)
        mock_sdk = MagicMock()
        mock_sdk.new_scope = MagicMock(return_value=mock_scope)

        with patch.dict(sys.modules, {"sentry_sdk": mock_sdk}):
            sentry_events._emit_scrub_failure_to_sentry(
                RuntimeError("scrub-boom"),
                event_id="evt-789",
            )

        mock_scope.set_extra.assert_any_call("event_id", "evt-789")

    def test_emit_scrub_failure_falls_back_to_stderr_on_inner_exception(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """内部 Sentry 通知が更に例外を出した場合、stderr へ最終フォールバックする"""
        mock_sdk = MagicMock()
        mock_sdk.new_scope = MagicMock(side_effect=RuntimeError("sdk-broken"))

        with patch.dict(sys.modules, {"sentry_sdk": mock_sdk}):
            sentry_events._emit_scrub_failure_to_sentry(ValueError("orig-error"))

        captured = capsys.readouterr()
        assert "[SENTRY_SCRUB_FAILED]" in captured.err
        assert "inner_error_type=RuntimeError" in captured.err
        assert "original_error_type=ValueError" in captured.err

    def test_emit_scrub_failure_falls_back_to_stderr_when_sdk_not_loaded(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """sentry_sdk が未ロードの場合も stderr へフォールバックする"""
        original = sys.modules.pop("sentry_sdk", None)
        try:
            sentry_events._emit_scrub_failure_to_sentry(KeyError("missing"))
        finally:
            if original is not None:
                sys.modules["sentry_sdk"] = original

        captured = capsys.readouterr()
        assert "[SENTRY_SCRUB_FAILED]" in captured.err
        assert "sentry_sdk_not_loaded" in captured.err
        assert "error_type=KeyError" in captured.err

    def test_emit_scrub_failure_reraises_recursion_error_fail_fast(self) -> None:
        """内部 SDK 呼び出しが RecursionError を投げた場合 fail-fast で再 raise する。

        MemoryError/RecursionError は system 致命例外であり、_emit 内部の
        `except Exception` で握り潰さず即時伝播させる契約（_safe_log_warning と同一方針）。
        伝播した例外は Sentry SDK の capture_internal_exceptions が捕捉し event を破棄するため
        fail-closed（PII 非送信）は維持される。
        """
        mock_sdk = MagicMock()
        mock_sdk.new_scope = MagicMock(side_effect=RecursionError())
        with patch.dict(sys.modules, {"sentry_sdk": mock_sdk}):
            with pytest.raises(RecursionError):
                sentry_events._emit_scrub_failure_to_sentry(ValueError("orig"))

    def test_emit_scrub_failure_reraises_memory_error_fail_fast(self) -> None:
        """内部 SDK 呼び出しが MemoryError を投げた場合 fail-fast で再 raise する。"""
        mock_sdk = MagicMock()
        mock_sdk.new_scope = MagicMock(side_effect=MemoryError())
        with patch.dict(sys.modules, {"sentry_sdk": mock_sdk}):
            with pytest.raises(MemoryError):
                sentry_events._emit_scrub_failure_to_sentry(ValueError("orig"))

    def test_returns_event(self) -> None:
        event = cast(Event, {"message": "test"})
        result_dict = self._call_before_send(event)
        assert result_dict["message"] == "test"

    def test_before_send_user_non_dict_replaced_with_empty_dict(self) -> None:
        event = cast(Event, {"user": "anonymous"})
        result = _before_send(event, {})
        assert result is not None
        assert result["user"] == {}

    @pytest.mark.parametrize("field", ["extra", "contexts", "tags"])
    def test_before_send_non_dict_non_list_field_replaced_with_empty_dict(self, field: str) -> None:
        """dict/list 以外の型は空dictに置換される（PII保護の安全サイド防御）。

        _scrub_sentry_field は isinstance(value, dict) / isinstance(value, list)
        がいずれもFalseの場合に event_dict[field] = {} で空dictに置換する。
        user の非dictテストは test_before_send_user_non_dict_replaced_with_empty_dict。
        """
        non_dict_value: Any = "not-a-dict-or-list"
        event = cast(Event, {field: non_dict_value})
        result = _before_send(event, {})
        assert result is not None
        assert result[field] == {}

    def test_before_send_list_tags_redacts_sensitive_key(self) -> None:
        """Sentry SDK が tags を list[tuple[str, str]] 形式で渡した場合に
        機密キーの値が [REDACTED] に置換され、非機密ペアは保持される。
        """
        list_tags: Any = [
            ("env", "prod"),
            ("token", "SUPER_SECRET"),
            ("request_id", "req-123"),
        ]
        event = cast(Event, {"tags": list_tags})
        result = _before_send(event, {})
        assert result is not None
        assert ("env", "prod") in result["tags"]
        assert ("token", "[REDACTED]") in result["tags"]
        assert ("request_id", "req-123") in result["tags"]
        # 非機密のデバッグ情報（request_id 等）が空dict化で消失しないことを確認
        assert "SUPER_SECRET" not in str(result["tags"])

    def test_before_send_list_tags_passes_through_non_pair_items(self) -> None:
        list_value: Any = ["item1", "item2", ("safe", "value")]
        event = cast(Event, {"tags": list_value})
        result = _before_send(event, {})
        assert result is not None
        assert result["tags"] == ["item1", "item2", ("safe", "value")]

    def test_scrub_list_item_respects_max_depth(self) -> None:
        """_scrub_list_item も最大深さ上限で再帰を停止する"""
        result = sentry_events._scrub_list_item({"token": "secret"}, MAX_SCRUB_DEPTH)
        assert result == "[MAX_DEPTH_EXCEEDED]"

    def test_scrub_tags_item_respects_max_depth(self) -> None:
        """_scrub_tags_item も MAX_SCRUB_DEPTH 到達時に "[MAX_DEPTH_EXCEEDED]" を返す"""
        result = sentry_events._scrub_tags_item(("token", "secret"), _depth=MAX_SCRUB_DEPTH)
        assert result == "[MAX_DEPTH_EXCEEDED]"

    def test_scrub_sentry_field_non_dict_logs_warning(self) -> None:
        """非dict型フィールドは空dict置換 + logger.warning を常時出力."""
        event = cast(Event, {"extra": "not-a-dict"})

        with patch.object(sentry_primitives._logger, "warning") as mock_warning:
            result = _before_send(event, {})

        assert result is not None
        assert result["extra"] == {}
        mock_warning.assert_called_once()
        call_kwargs = mock_warning.call_args[1]
        assert call_kwargs["field"] == "extra"
        assert call_kwargs["actual_type"] == "str"
        assert call_kwargs["action"] == "replaced_with_empty_dict"
        assert call_kwargs["event_id"] is None

    def test_scrub_sentry_field_non_dict_contexts_logs_warning(self) -> None:
        """非dict型 contexts フィールドも空dict置換 + logger.warning を常時出力（本番監視対応）."""
        event = cast(Event, {"contexts": 123})

        with patch.object(sentry_primitives._logger, "warning") as mock_warning:
            result = _before_send(event, {})

        assert result is not None
        assert result["contexts"] == {}
        mock_warning.assert_called_once()
        call_kwargs = mock_warning.call_args[1]
        assert call_kwargs["field"] == "contexts"
        assert call_kwargs["actual_type"] == "int"
        assert call_kwargs["action"] == "replaced_with_empty_dict"
        assert call_kwargs["event_id"] is None

    def test_scrub_sentry_field_non_dict_logs_event_id(self) -> None:
        """非dict/listフィールドの警告には event_id を含める。"""
        event = cast(Event, {"event_id": "evt-123", "extra": "not-a-dict"})

        with patch.object(sentry_primitives._logger, "warning") as mock_warning:
            result = _before_send(event, {})

        assert result is not None
        assert result["extra"] == {}
        call_kwargs = mock_warning.call_args[1]
        assert call_kwargs["event_id"] == "evt-123"

    def test_before_send_request_non_dict_replaced_with_empty_dict_and_logs_warning(self) -> None:
        """request が非dict型の場合、空dictに置換し event_id 付きで警告する。"""
        event = cast(Event, {"event_id": "evt-456", "request": "raw-request"})

        with patch.object(sentry_primitives._logger, "warning") as mock_warning:
            result = _before_send(event, {})

        assert result is not None
        assert result["request"] == {}
        mock_warning.assert_called_once()
        call_kwargs = mock_warning.call_args[1]
        assert mock_warning.call_args.args == ("sentry_request_type_unexpected",)
        assert call_kwargs["actual_type"] == "str"
        assert call_kwargs["action"] == "replaced_with_empty_dict"
        assert call_kwargs["event_id"] == "evt-456"

    def test_scrub_sentry_field_logger_failure_is_suppressed(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """logger.warning 失敗時も Sentry イベントを drop せず fail-open で継続する。

        旧実装は完全 silent (`except Exception: pass`) だったが、
        ロガー側 RecursionError 等の重大障害が無音化される問題があったため、
        stderr に最低限の診断 1 行を出力する fail-open に変更。
        """
        event = cast(Event, {"extra": "not-a-dict"})

        with patch.object(
            sentry_primitives._logger,
            "warning",
            side_effect=RuntimeError("logger broken"),
        ):
            result = _before_send(event, {})

        assert result is not None
        assert result["extra"] == {}
        captured = capsys.readouterr()
        # fail-open: stderr に診断行が出るが Sentry イベントは drop されない
        assert "_safe_log_warning failed" in captured.err
        assert "error_type=RuntimeError" in captured.err

    def test_before_send_scrubs_exception_stacktrace_vars(self) -> None:
        event = cast(
            Event,
            {
                "exception": {
                    "values": [
                        {
                            "stacktrace": {
                                "frames": [
                                    {
                                        "vars": {
                                            "password": "super_secret",
                                            "api_key": "KEY123",
                                            "user_input": "safe_value",
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            },
        )
        result = _before_send(event, {})
        assert result is not None
        frame_vars = result["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"]
        assert frame_vars["password"] == "[REDACTED]"  # noqa: S105
        assert frame_vars["api_key"] == "[REDACTED]"
        assert frame_vars["user_input"] == "safe_value"

    def test_before_send_exception_fail_open_unexpected_structure(self) -> None:
        """exception フィールドの構造が未知でもイベントをdropせずfail-openする。

        values が非 list（例: str）の場合、_scrub_exception_field は
        警告を残して元データをそのまま返し、_before_send は None を返さず
        イベントを通過させる（fail-open）。
        """
        event: dict[str, Any] = {
            "exception": {
                "values": "not_a_list",  # 不正な型: list 期待だが str
            },
        }
        with patch.object(sentry_events, "_safe_log_warning") as mock_warning:
            result = _before_send(event, {})
        assert result is not None, "fail-open: 異常構造でもイベントdropしない"
        result_dict = cast(dict[str, Any], result)
        assert result_dict["exception"]["values"] == "not_a_list", (
            "元の値が保持されている（破壊的置換なし）"
        )
        # _safe_log_warning が想定 event で発火することを検証。
        # これがないと将来 _safe_log_warning 呼び出しが削除されてもテストが通過する。
        mock_warning.assert_called_once()
        assert mock_warning.call_args[0][0] == "sentry_exception_values_unexpected_type"

    def test_before_send_exception_fail_open_non_dict_value_item(self) -> None:
        """values 内に非 dict 要素があってもイベントをdropせずfail-openする。

        _scrub_exception_field は型不一致の value 要素を
        スクラブせずそのまま通過させる（fail-open）。
        正常な dict 要素は引き続きスクラブされる。
        """
        event: dict[str, Any] = {
            "exception": {
                "values": [
                    {"stacktrace": {"frames": [{"vars": {"password": "secret"}}]}},
                    "not_a_dict",  # 不正な型: dict 期待だが str
                    42,  # 不正な型: dict 期待だが int
                ],
            },
        }
        result = _before_send(event, {})
        assert result is not None, "fail-open: 異常構造でもイベントdropしない"
        result_dict = cast(dict[str, Any], result)
        values = result_dict["exception"]["values"]
        # 正常な dict 要素はスクラブされている
        assert values[0]["stacktrace"]["frames"][0]["vars"]["password"] == "[REDACTED]"  # noqa: S105
        # str は PII 含む可能性のため [REDACTED] に置換される (B-3)
        assert values[1] == "[REDACTED]"
        # int/float/bool は PII 非含のため素通し（fail-open）
        assert values[2] == 42

    def test_before_send_exception_fail_open_non_dict_stacktrace(self) -> None:
        """stacktrace が非 dict でもイベントをdropせずfail-openする。

        _scrub_exception_field は stacktrace が dict でない場合、
        警告を残して stacktrace のスクラブをスキップし、
        イベントを破壊しない（fail-open）。
        """
        event: dict[str, Any] = {
            "exception": {
                "values": [
                    {
                        "type": "ValueError",
                        "stacktrace": "not_a_dict",  # 不正な型: dict 期待だが str
                    },
                ],
            },
        }
        result = _before_send(event, {})
        assert result is not None, "fail-open: 異常構造でもイベントdropしない"
        result_dict = cast(dict[str, Any], result)
        val = result_dict["exception"]["values"][0]
        assert val["type"] == "ValueError"
        assert val["stacktrace"] == "not_a_dict", "元の stacktrace が保持されている"

    def test_before_send_exception_fail_open_non_list_frames(self) -> None:
        """frames が非 list でもイベントをdropせずfail-openする。

        _scrub_exception_field は frames が list でない場合、
        警告を残して frames のスクラブをスキップし、
        イベントを破壊しない（fail-open）。
        """
        event: dict[str, Any] = {
            "exception": {
                "values": [
                    {
                        "stacktrace": {
                            "frames": "not_a_list",  # 不正な型: list 期待だが str
                        },
                    },
                ],
            },
        }
        result = _before_send(event, {})
        assert result is not None, "fail-open: 異常構造でもイベントdropしない"
        result_dict = cast(dict[str, Any], result)
        stacktrace = result_dict["exception"]["values"][0]["stacktrace"]
        assert stacktrace["frames"] == "not_a_list", "元の frames が保持されている"

    def test_before_send_exception_fail_open_non_dict_frame(self) -> None:
        """frames 内に非 dict 要素があってもイベントをdropせずfail-openする。

        _scrub_exception_field は型不一致の frame 要素を
        スクラブせずそのまま通過させる（fail-open）。
        正常な dict frame は引き続きスクラブされる。
        """
        event: dict[str, Any] = {
            "exception": {
                "values": [
                    {
                        "stacktrace": {
                            "frames": [
                                {"vars": {"password": "secret"}},
                                "not_a_dict_frame",  # 不正な型: dict 期待だが str
                            ],
                        },
                    },
                ],
            },
        }
        result = _before_send(event, {})
        assert result is not None, "fail-open: 異常構造でもイベントdropしない"
        result_dict = cast(dict[str, Any], result)
        frames = result_dict["exception"]["values"][0]["stacktrace"]["frames"]
        assert frames[0]["vars"]["password"] == "[REDACTED]"  # noqa: S105
        assert frames[1] == "not_a_dict_frame", "非 dict frame がそのまま保持されている"

    def test_before_send_exception_fail_open_non_dict_vars(self) -> None:
        """vars が非 dict でもイベントをdropせずfail-openする。

        _scrub_exception_field は vars が dict でない場合、
        警告を残して vars のスクラブをスキップし、
        イベントを破壊しない（fail-open）。
        """
        event: dict[str, Any] = {
            "exception": {
                "values": [
                    {
                        "stacktrace": {
                            "frames": [
                                {
                                    "vars": "not_a_dict",  # 不正な型: dict 期待だが str
                                },
                            ],
                        },
                    },
                ],
            },
        }
        result = _before_send(event, {})
        assert result is not None, "fail-open: 異常構造でもイベントdropしない"
        result_dict = cast(dict[str, Any], result)
        frame = result_dict["exception"]["values"][0]["stacktrace"]["frames"][0]
        assert frame["vars"] == "not_a_dict", "元の vars が保持されている"

    def test_scrub_tags_item_nested_list_redacts_sensitive(self) -> None:
        nested = [("password", "secret"), ("safe", "ok"), ("token", "abc")]
        result = sentry_events._scrub_tags_item(nested)
        assert result[0] == ("password", "[REDACTED]")
        assert result[1] == ("safe", "ok")
        assert result[2] == ("token", "[REDACTED]")

    def test_scrub_tags_item_nonsensitive_value_nested_dict_scrubbed(self) -> None:
        tag = ("user_metadata", {"password": "secret", "safe": "ok"})
        result = sentry_events._scrub_tags_item(tag)
        # キーは保持、value 内の機密キーは redact
        assert result[0] == "user_metadata"
        assert result[1]["password"] == "[REDACTED]"  # noqa: S105
        assert result[1]["safe"] == "ok"

    def test_scrub_tags_item_nonsensitive_value_two_element_list_preserved(self) -> None:
        """非機密タグペアの value が2要素リストでもタグペアと誤認せずそのまま保持する。

        （例: ("user_metadata", ["email", "user@example.com"]) の ["email", ...] は
        tag pair ではなく単なる配列値。_scrub_list_item を使うことで過剰 redact を防ぐ）
        """
        tag = ("user_metadata", ["email", "user@example.com"])
        result = sentry_events._scrub_tags_item(tag)
        assert result[0] == "user_metadata"
        # value の2要素リストはタグペアと誤認されず保持される
        assert result[1] == ["email", "user@example.com"]

    def test_scrub_tags_item_nonsensitive_value_nested_tuples_scrubbed(self) -> None:
        """非機密タグペアの value 内のネスト tuple の機密キーが redact される。

        _scrub_list_item 経由で tuple の tag pair 判定が継承されるため、
        ネストされた機密キーも適切にスクラブされる。
        """
        tag = ("meta", [("password", "s1"), ("token", "s2"), ("safe", "ok")])
        result = sentry_events._scrub_tags_item(tag)
        assert result[0] == "meta"
        # _scrub_list_item が tuple の tag pair を判定し redact
        assert result[1][0] == ("password", "[REDACTED]")
        assert result[1][1] == ("token", "[REDACTED]")
        assert result[1][2] == ("safe", "ok")

    @pytest.mark.parametrize(
        "container_type",
        [list, tuple],
        ids=["list", "tuple"],
    )
    def test_scrub_exception_value_item_list_tuple_redacts_nested_sensitive(
        self, container_type: type
    ) -> None:
        # ネストdictに機密キー「token」と非機密キー「safe」を混在させる
        """_scrub_exception_value_item の list/tuple分岐: ネストした機密データを再帰スクラブする。

        value_item が list/tuple の場合、各要素を _scrub_list_item(_depth=0) で再帰スクラブする。
        dict要素内の機密キー値は [REDACTED] 化され、非機密値は保持される。
        (sentry_init.py L181: isinstance(value_item,(list,tuple)) 分岐)
        """
        sensitive_item = {"token": "secret_value", "safe": "keep_this"}
        value_item = container_type([sensitive_item])

        result = sentry_events._scrub_exception_value_item(value_item)

        # 戻り値は同じ型 (list → list, tuple → tuple)
        assert type(result) is container_type
        # 機密キーはスクラブされている
        assert result[0]["token"] == "[REDACTED]"  # noqa: S105
        # 非機密キーは保持されている
        assert result[0]["safe"] == "keep_this"

    @pytest.mark.parametrize(
        "container_type",
        [list, tuple],
        ids=["list", "tuple"],
    )
    def test_scrub_exception_value_item_list_tuple_preserves_non_sensitive(
        self, container_type: type
    ) -> None:
        """_scrub_exception_value_item の list/tuple分岐: 非機密値は保持される。

        機密キーを含まない dict 要素の値はそのまま保持され、
        過剰スクラブ（false positive）が発生しないことを検証する。
        """
        non_sensitive_item = {"user_id": 42, "name": "Alice"}
        value_item = container_type([non_sensitive_item])

        result = sentry_events._scrub_exception_value_item(value_item)

        assert type(result) is container_type
        assert result[0]["user_id"] == 42
        assert result[0]["name"] == "Alice"

    def test_scrub_exception_value_item_scalar_logs_warning(self) -> None:
        """_scrub_exception_value_item: 非 container 型は警告後に fail-open する。"""
        value_item = 42

        with patch.object(sentry_events, "_safe_log_warning") as mock_warning:
            result = sentry_events._scrub_exception_value_item(value_item)

        assert result == value_item
        mock_warning.assert_called_once_with(
            "sentry_exception_value_item_unexpected_type",
            actual_type="int",
            action="skip_item",
        )

    def test_scrub_exception_value_item_redacts_custom_toplevel_sensitive_key(self) -> None:
        """value/stacktrace 以外のトップレベル機密キーも redact し type は保持する。

        カスタム SDK 統合が token 等を value item 直下に付与した場合の PII 漏洩防止。
        """
        value_item = {
            "type": "ValueError",
            "value": "boom",
            "token": "secret_value",  # noqa: S106 — テスト用ダミー機密値
            "safe": "keep_this",
        }

        result = sentry_events._scrub_exception_value_item(value_item)

        assert result["token"] == "[REDACTED]"  # noqa: S105  # カスタム機密キーは redact
        assert result["type"] == "ValueError"  # type は観測性のため保持（S-1 方針）
        assert result["value"] == "[REDACTED]"  # value は無条件 redact
        assert result["safe"] == "keep_this"  # 非機密キーは保持


class TestSentryProcessorBeforeSendChain:
    """logger._sentry_processor → sentry_scrub_events._before_send PII フィルター連鎖テスト

    _sentry_processor は scope.set_extra() で extra フィールドを設定し、
    Sentry SDK は _before_send フックを介してイベントを送信する。
    このクラスは extra 経由の PII が _before_send で正しく除去されることを検証する。
    """

    def test_sensitive_extra_keys_are_redacted(self) -> None:
        event: Event = cast(
            Event,
            {
                "level": "error",
                "message": "DB error",
                "extra": {
                    "email": "user@example.com",
                    "password": "secret123",
                    "user_id": 42,
                    "request_id": "req-001",
                },
            },
        )
        result = _before_send(event, {})
        assert result is not None
        extra = cast(dict[str, Any], result["extra"])
        assert extra["email"] == "[REDACTED]"
        assert extra["password"] == "[REDACTED]"  # noqa: S105
        assert extra["user_id"] == 42
        assert extra["request_id"] == "req-001"

    def test_non_sensitive_extra_preserved(self) -> None:
        event: Event = cast(
            Event,
            {
                "level": "error",
                "message": "test",
                "extra": {"user_id": 123, "action": "login", "status_code": 500},
            },
        )
        result = _before_send(event, {})
        assert result is not None
        extra = cast(dict[str, Any], result["extra"])
        assert extra["user_id"] == 123
        assert extra["action"] == "login"
        assert extra["status_code"] == 500

    def test_multiple_sensitive_keys_all_redacted(self) -> None:
        event: Event = cast(
            Event,
            {
                "level": "error",
                "message": "auth error",
                "extra": {
                    "token": "bearer-xyz",
                    "api_key": "sk-secret",
                    "secret": "my-secret",
                    "passwd": "p@ss",
                },
            },
        )
        result = _before_send(event, {})
        assert result is not None
        extra = cast(dict[str, Any], result["extra"])
        assert extra["token"] == "[REDACTED]"  # noqa: S105
        assert extra["api_key"] == "[REDACTED]"
        assert extra["secret"] == "[REDACTED]"  # noqa: S105
        assert extra["passwd"] == "[REDACTED]"  # noqa: S105

    def test_user_and_contexts_sensitive_keys_are_redacted(self) -> None:
        event: Event = cast(
            Event,
            {
                "level": "error",
                "message": "test",
                "user": {
                    "id": "42",
                    "email": "user@example.com",
                    "ip_address": "203.0.113.10",
                },
                "contexts": {
                    "auth": {
                        "token": "secret-token",
                        "role": "admin",
                    }
                },
            },
        )

        result = _before_send(event, {})

        assert result is not None
        user = cast(dict[str, Any], result["user"])
        contexts = cast(dict[str, Any], result["contexts"])
        assert user["id"] == "42"
        assert user["email"] == "[REDACTED]"
        assert user["ip_address"] == "[REDACTED]"
        assert contexts["auth"]["token"] == "[REDACTED]"  # noqa: S105
        assert contexts["auth"]["role"] == "admin"


def test_before_send_logger_error_receives_event_id() -> None:
    """_before_send の scrub 失敗時に _logger.error へ event_id kwarg が正しく渡される検証（T-3）。

    既存テスト test_before_send_passes_event_id_to_scrub_failure_notification は
    _emit_scrub_failure_to_sentry への event_id 渡しを検証するが、
    _logger.error への event_id 渡しは未検証。本テストはその空白を埋める。

    _scrub_url を RuntimeError で差し替えて失敗を誘発し、_logger.error の
    call_args_list から "sentry_before_send_drop_event" エントリを特定して
    event_id kwarg を検証する。
    """
    event = cast(
        Event,
        {
            "event_id": "evt-logger-check-001",
            "request": {"url": "https://example.com/path?token=abc"},
        },
    )

    with (
        patch.object(sentry_events, "_scrub_url", side_effect=RuntimeError("scrub-boom")),
        patch.object(sentry_events, "_emit_scrub_failure_to_sentry"),
        patch.object(sentry_events, "_logger") as mock_logger,
    ):
        result = _before_send(event, {})

    assert result is None

    # _logger.error の呼び出しから "sentry_before_send_drop_event" エントリを特定
    drop_event_calls = [
        call
        for call in mock_logger.error.call_args_list
        if call.args and call.args[0] == "sentry_before_send_drop_event"
    ]
    assert len(drop_event_calls) == 1, (
        f"'sentry_before_send_drop_event' の _logger.error 呼び出しが1件期待されるが "
        f"{len(drop_event_calls)} 件"
    )
    assert drop_event_calls[0].kwargs.get("event_id") == "evt-logger-check-001"
