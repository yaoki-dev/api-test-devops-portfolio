"""Sentryイベント整形（events）のテスト

_before_send を中心としたイベント整形・例外スクラブ・再帰ガードをカバー。
"""

from __future__ import annotations

import sys
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from sentry_sdk.types import Event

import utils.sentry_init as sentry_module
from utils.sentry_init import (
    _SCRUBBED_EVENT_FIELDS,
    MAX_SCRUB_DEPTH,
    _before_send,
    _scrub_exception_field,
    _scrub_exception_value_item,
)

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


class TestScrubExceptionField:
    """Sentry exception フィールドの fail-open 分岐を検証する。"""

    def test_non_dict_frame_logs_warning_and_passes_through(self) -> None:
        """非 dict frame は fail-open しつつ、無音にせず warning を残す。"""
        exception_value = {
            "values": [
                {
                    "stacktrace": {
                        "frames": [
                            "raw-frame",
                            {"vars": {"password": "secret", "safe": "ok"}},
                        ],
                    },
                },
            ],
        }

        with patch.object(sentry_module._logger, "warning") as mock_warning:
            result = _scrub_exception_field(exception_value)

        frames = result["values"][0]["stacktrace"]["frames"]
        assert frames[0] == "raw-frame"
        assert frames[1]["vars"] == {"password": "[REDACTED]", "safe": "ok"}

        mock_warning.assert_called_once()
        call_kwargs = mock_warning.call_args[1]
        assert call_kwargs["actual_type"] == "str"
        assert call_kwargs["action"] == "skip_frame_scrub"

    def test_scrubs_exception_value_string(self) -> None:
        exception_value = {
            "values": [
                {
                    "value": "DatabaseError: Connection to postgres://user:password@host/db failed",
                },
            ],
        }

        result = _scrub_exception_field(exception_value)

        assert result["values"][0]["value"] == "[REDACTED]"

    def test_scrub_exception_field_with_dict_values(self) -> None:
        """values が dict 型の場合も _scrub_sensitive_data でkey-based scrubされる。

        list-path と異なり value フィールドの明示的 [REDACTED] 置換は行わない。
        _scrub_sensitive_data のキーベース判定に依存する（dict構造では value が
        キー名として直接出現しないため）。
        """
        exception_value = {
            "values": {
                "error_1": {"value": "safe_data", "token": "secret_123"},
                "error_2": {"value": "also_safe", "password": "pw_leak"},
            },
        }

        result = _scrub_exception_field(exception_value)

        # 機密キーは [REDACTED] に置換される
        assert result["values"]["error_1"]["token"] == "[REDACTED]"  # noqa: S105
        assert result["values"]["error_2"]["password"] == "[REDACTED]"  # noqa: S105
        # 非機密キー・非機密値はそのまま保持
        assert result["values"]["error_1"]["value"] == "safe_data"
        assert result["values"]["error_2"]["value"] == "also_safe"
        # 元の exception_value は変更されない
        assert exception_value["values"]["error_1"]["token"] == "secret_123"  # noqa: S105

    def test_scrub_exception_field_with_empty_dict_values(self) -> None:
        exception_value: dict[str, Any] = {"values": {}}

        result = _scrub_exception_field(exception_value)

        assert result == {"values": {}}

    def test_scrub_exception_field_without_values_key_no_warning(self) -> None:
        """ "values" キー未存在は Sentry 仕様上の有効構造のため WARNING を出さない。

        Sentry exception interface は values を必須としない
        (getsentry/sentry interfaces/exception.py: get_path(data, "values",
        default=[]) で空リスト扱い)。誤検知 WARNING を抑制しつつ、他キーは
        ベストエフォートで機密スクラブを継続することを検証する。
        """
        exception_value: dict[str, Any] = {"type": "ValueError", "token": "secret_xyz"}  # noqa: S106

        with patch("utils.sentry_init._safe_log_warning") as mock_warn:
            result = _scrub_exception_field(exception_value)

        # "values" キー未存在は正常構造のため WARNING は出力されない
        mock_warn.assert_not_called()
        # 機密キーはベストエフォートでスクラブされる
        assert result["token"] == "[REDACTED]"  # noqa: S105
        # 非機密キーは保持される
        assert result["type"] == "ValueError"
        # 元の exception_value は変更されない
        assert exception_value["token"] == "secret_xyz"  # noqa: S105


class TestHasInternalTag:
    """_has_internal_tag ヘルパーの defensive branch coverage テスト

    helper の全 branch (dict / list / fall-through) を直接 unit test 化し、
    `_before_send` 経由の間接検証では gate 化できない defensive branch
    (None / str / int / 空 dict / 空 list / value mismatch) の robustness を
    回帰防止する。
    """

    def test_dict_form_with_internal_tag_returns_true(self) -> None:
        tags = {sentry_module._INTERNAL_TAG_KEY: sentry_module._INTERNAL_TAG_VALUE}
        assert sentry_module._has_internal_tag(tags) is True

    def test_list_form_with_internal_tag_returns_true(self) -> None:
        tags = [
            ("env", "prod"),
            (sentry_module._INTERNAL_TAG_KEY, sentry_module._INTERNAL_TAG_VALUE),
        ]
        assert sentry_module._has_internal_tag(tags) is True

    @pytest.mark.parametrize(
        "non_match_value",
        [
            None,
            "string-tags",
            42,
            0,
            False,
            {},  # 空 dict
            [],  # 空 list
            {"other_key": "other_value"},  # dict 形式だが内部 key 不在
            {sentry_module._INTERNAL_TAG_KEY: "wrong_value"},  # dict 形式 + value mismatch
            [("env", "prod"), ("other_key", "other_value")],  # list 形式だが内部 tag 不在
            [(sentry_module._INTERNAL_TAG_KEY, "wrong_value")],  # list 形式 + value mismatch
            [("not-a-tuple-with-2-elements",)],  # list 内 malformed item
        ],
    )
    def test_fall_through_returns_false(self, non_match_value: Any) -> None:
        """dict / list 以外、または内部 tag 不在の場合は常に False を返す。

        defensive fall-through branch を gate 化することで、helper の
        unintended True 返却 (recursion guard 誤発火 → 通常 event の
        scrub スキップ = PII 漏洩経路) を回帰防止する。
        """
        assert sentry_module._has_internal_tag(non_match_value) is False


class TestScrubExceptionFailOpenBranches:
    """_scrub_exception_frame / _scrub_exception_stacktrace の fail-open 警告分岐の直接テスト

    これらの分岐 (frame 非 dict / frame_vars 非 dict・None / frames 非 list・None) は
    従来 _before_send 経由の統合テストでしか到達せず、PII 漏洩防止に関わる重要パスのため
    直接ユニットテストで個別に検証する。
    """

    def test_frame_not_dict_returns_input_and_warns_high_risk(self) -> None:
        """frame が dict でない場合: 入力を破壊せず返し、HIGH リスク警告を出す (fail-open)。"""
        with patch.object(sentry_module, "_safe_log_warning") as mock_warn:
            result = sentry_module._scrub_exception_frame("not-a-frame")

        assert result == "not-a-frame"
        mock_warn.assert_called_once()
        assert mock_warn.call_args.args[0] == "sentry_exception_frame_unexpected_type"
        assert mock_warn.call_args.kwargs.get("pii_leak_risk") == "HIGH"

    def test_frame_vars_unexpected_type_skips_scrub_and_warns(self) -> None:
        """frame['vars'] が dict/None 以外: vars を素通しし警告を出す (scrub スキップ)。"""
        frame = {"function": "handler", "vars": "not-a-dict"}
        with patch.object(sentry_module, "_safe_log_warning") as mock_warn:
            result = sentry_module._scrub_exception_frame(frame)

        assert result["vars"] == "not-a-dict"
        mock_warn.assert_called_once()
        assert mock_warn.call_args.args[0] == "sentry_exception_frame_vars_unexpected_type"

    def test_frame_vars_none_no_warning(self) -> None:
        """frame['vars'] が None (正常: vars 欠如): 警告を出さず frame を返す (誤検知防止)。"""
        frame = {"function": "handler"}
        with patch.object(sentry_module, "_safe_log_warning") as mock_warn:
            result = sentry_module._scrub_exception_frame(frame)

        assert result == {"function": "handler"}
        mock_warn.assert_not_called()

    def test_frame_vars_dict_is_scrubbed(self) -> None:
        frame = {"vars": {"password": "secret", "user_input": "safe_value"}}
        result = sentry_module._scrub_exception_frame(frame)

        assert result["vars"]["password"] == "[REDACTED]"  # noqa: S105
        assert result["vars"]["user_input"] == "safe_value"

    def test_frame_source_context_is_removed_and_vars_are_scrubbed(self) -> None:
        frame = {
            "pre_context": ["API_KEY = 'secret'"],
            "context_line": "raise RuntimeError(password)",
            "post_context": ["logger.info(user_email)"],
            "vars": {"password": "secret", "user_input": "safe_value"},
        }

        result = sentry_module._scrub_exception_frame(frame)

        assert "pre_context" not in result
        assert "context_line" not in result
        assert "post_context" not in result
        assert result["vars"]["password"] == "[REDACTED]"  # noqa: S105
        assert result["vars"]["user_input"] == "safe_value"

    def test_frames_unexpected_type_returns_input_and_warns(self) -> None:
        """stacktrace['frames'] が list/None 以外: stacktrace を素通しし警告を出す (fail-open)。"""
        stacktrace = {"frames": "not-a-list"}
        with patch.object(sentry_module, "_safe_log_warning") as mock_warn:
            result = sentry_module._scrub_exception_stacktrace(stacktrace)

        assert result == {"frames": "not-a-list"}
        mock_warn.assert_called_once()
        assert mock_warn.call_args.args[0] == "sentry_exception_frames_unexpected_type"

    def test_frames_none_no_warning(self) -> None:
        stacktrace = {"registers": {"rax": "0x0"}}
        with patch.object(sentry_module, "_safe_log_warning") as mock_warn:
            result = sentry_module._scrub_exception_stacktrace(stacktrace)

        assert result == {"registers": {"rax": "0x0"}}
        mock_warn.assert_not_called()


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

        with patch.object(sentry_module._logger, "warning") as mock_warning:
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
                sentry_module,
                "_scrub_sensitive_data",
                side_effect=[{"Authorization": "[REDACTED]"}, RuntimeError("boom")],
            ),
            patch.object(sentry_module, "_emit_scrub_failure_to_sentry") as mock_emit,
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
                sentry_module,
                "_scrub_exception_field",
                side_effect=RuntimeError("exception-scrub-boom"),
            ),
            patch.object(sentry_module, "_emit_scrub_failure_to_sentry") as mock_emit,
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
            patch.object(sentry_module, "_scrub_url", side_effect=RuntimeError("url-scrub-boom")),
            patch.object(sentry_module, "_emit_scrub_failure_to_sentry") as mock_emit,
            patch.object(sentry_module, "_logger") as mock_logger,
            patch.object(sentry_module, "_safe_log_warning") as mock_warning,
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
            patch.object(sentry_module, "_scrub_url", side_effect=RuntimeError("boom")),
            patch.object(sentry_module, "_emit_scrub_failure_to_sentry") as mock_emit,
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
            patch.object(sentry_module, "_scrub_url", side_effect=RuntimeError("url-scrub-boom")),
            patch.object(
                sentry_module,
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
            patch.object(sentry_module, "_scrub_url", side_effect=RuntimeError("url-scrub-boom")),
            patch.object(sentry_module, "_emit_scrub_failure_to_sentry") as mock_emit,
            patch.object(sentry_module, "_logger") as mock_logger,
            patch.object(sentry_module, "_safe_log_warning") as mock_warning,
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
            patch.object(sentry_module, "_scrub_sensitive_data", side_effect=MemoryError()),
            patch.object(sentry_module, "_emit_scrub_failure_to_sentry") as mock_emit,
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
            patch.object(sentry_module, "_scrub_sentry_field", side_effect=RecursionError()),
            patch.object(sentry_module, "_emit_scrub_failure_to_sentry") as mock_emit,
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

        with patch.object(sentry_module._logger, "warning") as mock_warning:
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
                    sentry_module._INTERNAL_TAG_KEY: sentry_module._INTERNAL_TAG_VALUE,
                },
                "request": {"headers": {"Authorization": "Bearer SECRET"}},
            },
        )

        with patch.object(sentry_module, "_scrub_sensitive_data") as mock_scrub:
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
                        sentry_module._INTERNAL_TAG_KEY,
                        sentry_module._INTERNAL_TAG_VALUE,
                    ),
                ],
                "request": {"headers": {"Authorization": "Bearer SECRET"}},
            },
        )

        with patch.object(sentry_module, "_scrub_sensitive_data") as mock_scrub:
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
            sentry_module._emit_scrub_failure_to_sentry(RuntimeError("scrub-boom"))

        mock_scope.set_tag.assert_any_call(
            sentry_module._INTERNAL_TAG_KEY,
            sentry_module._INTERNAL_TAG_VALUE,
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
            sentry_module._emit_scrub_failure_to_sentry(
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
            sentry_module._emit_scrub_failure_to_sentry(ValueError("orig-error"))

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
            sentry_module._emit_scrub_failure_to_sentry(KeyError("missing"))
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
                sentry_module._emit_scrub_failure_to_sentry(ValueError("orig"))

    def test_emit_scrub_failure_reraises_memory_error_fail_fast(self) -> None:
        """内部 SDK 呼び出しが MemoryError を投げた場合 fail-fast で再 raise する。"""
        mock_sdk = MagicMock()
        mock_sdk.new_scope = MagicMock(side_effect=MemoryError())
        with patch.dict(sys.modules, {"sentry_sdk": mock_sdk}):
            with pytest.raises(MemoryError):
                sentry_module._emit_scrub_failure_to_sentry(ValueError("orig"))

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
        result = sentry_module._scrub_list_item({"token": "secret"}, MAX_SCRUB_DEPTH)
        assert result == "[MAX_DEPTH_EXCEEDED]"

    def test_scrub_tags_item_respects_max_depth(self) -> None:
        """_scrub_tags_item も MAX_SCRUB_DEPTH 到達時に "[MAX_DEPTH_EXCEEDED]" を返す"""
        result = sentry_module._scrub_tags_item(("token", "secret"), _depth=MAX_SCRUB_DEPTH)
        assert result == "[MAX_DEPTH_EXCEEDED]"

    def test_scrub_sentry_field_non_dict_logs_warning(self) -> None:
        """非dict型フィールドは空dict置換 + logger.warning を常時出力."""
        event = cast(Event, {"extra": "not-a-dict"})

        with patch.object(sentry_module._logger, "warning") as mock_warning:
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

        with patch.object(sentry_module._logger, "warning") as mock_warning:
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

        with patch.object(sentry_module._logger, "warning") as mock_warning:
            result = _before_send(event, {})

        assert result is not None
        assert result["extra"] == {}
        call_kwargs = mock_warning.call_args[1]
        assert call_kwargs["event_id"] == "evt-123"

    def test_before_send_request_non_dict_replaced_with_empty_dict_and_logs_warning(self) -> None:
        """request が非dict型の場合、空dictに置換し event_id 付きで警告する。"""
        event = cast(Event, {"event_id": "evt-456", "request": "raw-request"})

        with patch.object(sentry_module._logger, "warning") as mock_warning:
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
            sentry_module._logger,
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
        with patch.object(sentry_module, "_safe_log_warning") as mock_warning:
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
        result = sentry_module._scrub_tags_item(nested)
        assert result[0] == ("password", "[REDACTED]")
        assert result[1] == ("safe", "ok")
        assert result[2] == ("token", "[REDACTED]")

    def test_scrub_tags_item_nonsensitive_value_nested_dict_scrubbed(self) -> None:
        tag = ("user_metadata", {"password": "secret", "safe": "ok"})
        result = sentry_module._scrub_tags_item(tag)
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
        result = sentry_module._scrub_tags_item(tag)
        assert result[0] == "user_metadata"
        # value の2要素リストはタグペアと誤認されず保持される
        assert result[1] == ["email", "user@example.com"]

    def test_scrub_tags_item_nonsensitive_value_nested_tuples_scrubbed(self) -> None:
        """非機密タグペアの value 内のネスト tuple の機密キーが redact される。

        _scrub_list_item 経由で tuple の tag pair 判定が継承されるため、
        ネストされた機密キーも適切にスクラブされる。
        """
        tag = ("meta", [("password", "s1"), ("token", "s2"), ("safe", "ok")])
        result = sentry_module._scrub_tags_item(tag)
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

        result = sentry_module._scrub_exception_value_item(value_item)

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

        result = sentry_module._scrub_exception_value_item(value_item)

        assert type(result) is container_type
        assert result[0]["user_id"] == 42
        assert result[0]["name"] == "Alice"

    def test_scrub_exception_value_item_scalar_logs_warning(self) -> None:
        """_scrub_exception_value_item: 非 container 型は警告後に fail-open する。"""
        value_item = 42

        with patch.object(sentry_module, "_safe_log_warning") as mock_warning:
            result = sentry_module._scrub_exception_value_item(value_item)

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

        result = sentry_module._scrub_exception_value_item(value_item)

        assert result["token"] == "[REDACTED]"  # noqa: S105  # カスタム機密キーは redact
        assert result["type"] == "ValueError"  # type は観測性のため保持（S-1 方針）
        assert result["value"] == "[REDACTED]"  # value は無条件 redact
        assert result["safe"] == "keep_this"  # 非機密キーは保持


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
                    sentry_module._INTERNAL_TAG_KEY: sentry_module._INTERNAL_TAG_VALUE,
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


class TestSentryProcessorBeforeSendChain:
    """logger._sentry_processor → sentry_init._before_send PII フィルター連鎖テスト

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


def test_internal_tag_value_is_valid_hex() -> None:
    import re

    from utils.sentry_init import _INTERNAL_TAG_VALUE

    assert re.fullmatch(r"[0-9a-f]{32}", _INTERNAL_TAG_VALUE) is not None
    assert len(_INTERNAL_TAG_VALUE) <= 200  # Sentry SDK tag value 上限 200文字以内


def test_exception_value_item_redacts_dict_bytes_value() -> None:
    result = _scrub_exception_value_item({"value": b"password=secret"})

    assert result == {"value": "[REDACTED]"}


class TestScrubSpanItem:
    """_scrub_span_item の直接単体テスト（T-2）。

    _before_send 経由の間接テストではカバーされないエッジケースを
    直接呼び出しで検証する。
    """

    def test_non_dict_input_list_delegates_to_scrub_list_item(self) -> None:
        """(a) 非dict入力（list）は _scrub_list_item に委譲される。

        平坦な文字列リストは機密キーコンテキストを持たないためそのまま保持される。
        """
        result = sentry_module._scrub_span_item(["foo", "bar"], _depth=0)
        assert result == ["foo", "bar"]

    def test_non_dict_scalar_delegates_to_scrub_list_item(self) -> None:
        result = sentry_module._scrub_span_item("plain-string", _depth=0)
        assert result == "plain-string"

    def test_max_depth_exceeded_returns_sentinel(self) -> None:
        """(b) _depth >= MAX_SCRUB_DEPTH のとき "[MAX_DEPTH_EXCEEDED]" を返す。"""
        result = sentry_module._scrub_span_item(
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
        result = sentry_module._scrub_span_item(item, _depth=0)

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
        result = sentry_module._scrub_span_item(item, _depth=0)

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
        result = sentry_module._scrub_span_item(item, _depth=0)

        result_description = result["description"]
        assert result_description.startswith("GET ")
        assert "foo@example.com" not in result_description
        assert "[REDACTED]" in result_description
        assert "/profile" in result_description


class TestSetInternalExtras:
    """_set_internal_extras の許可リスト強制。

    内部タグ付きイベントは _before_send の scrub をバイパスして Sentry に到達するため、
    extra に書けるキーを _INTERNAL_EVENT_EXTRA_KEYS で固定し、PII を含み得るキーの
    混入を fail-fast で拒否する多層防御 (CWE-312) を検証する。
    """

    def test_unauthorized_key_raises_value_error(self) -> None:
        """許可リスト外キーは ValueError で拒否され、scope へ一切書き込まない。"""
        mock_scope = MagicMock()

        with pytest.raises(
            ValueError,
            match=r"Unauthorized key in internal event extra: 'user_email'",
        ):
            sentry_module._set_internal_extras(mock_scope, {"user_email": "x@example.com"})

        # 拒否時は部分書き込みが起きない（原子性）
        mock_scope.set_extra.assert_not_called()

    def test_mixed_unauthorized_key_raises_before_partial_write(self) -> None:
        """許可キー混在時も未許可キーがあれば scope へ一切書き込まない。"""
        mock_scope = MagicMock()

        with pytest.raises(
            ValueError,
            match=r"Unauthorized key in internal event extra: 'user_email'",
        ):
            sentry_module._set_internal_extras(
                mock_scope,
                {"error_type": "ValueError", "user_email": "x@example.com"},
            )

        mock_scope.set_extra.assert_not_called()

    def test_authorized_keys_are_delegated_to_scope(self) -> None:
        """許可リスト内キーは全て scope.set_extra へ委譲される。

        実呼び出し元 _emit_scrub_failure_to_sentry は 4 キー全てを使うため、
        いずれかの転送が欠落するリグレッションを検出できるよう全キーを検証する。
        """
        mock_scope = MagicMock()

        sentry_module._set_internal_extras(
            mock_scope,
            {
                "error_type": "ValueError",
                "error_module": "builtins",
                "action": "scrub_failed",
                "event_id": "evt-1",
            },
        )

        mock_scope.set_extra.assert_any_call("error_type", "ValueError")
        mock_scope.set_extra.assert_any_call("error_module", "builtins")
        mock_scope.set_extra.assert_any_call("action", "scrub_failed")
        mock_scope.set_extra.assert_any_call("event_id", "evt-1")
        # 許可キーのみが委譲され、余分な書き込みがない
        assert mock_scope.set_extra.call_count == 4

    def test_empty_dict_is_accepted(self) -> None:
        mock_scope = MagicMock()
        sentry_module._set_internal_extras(mock_scope, {})
        mock_scope.set_extra.assert_not_called()
