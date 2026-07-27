"""イベント整形ヘルパー（event helpers）のテスト

_scrub_exception_field のスクラブと fail-open 分岐、_scrub_exception_frame /
_scrub_exception_stacktrace の fail-open 分岐、_scrub_exception_value_item の
bytes 値スクラブ、内部タグ（_has_internal_tag）と extras（_set_internal_extras）
の補助関数をカバー。

_scrub_exception_value_item の直接テスト（scalar の fail-open 警告を含む）は
test_sentry_scrub_events.py 側にある。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import utils.sentry_scrub_events as sentry_events
import utils.sentry_scrub_primitives as sentry_primitives
from utils.sentry_scrub_events import (
    _scrub_exception_field,
    _scrub_exception_value_item,
)

pytestmark = pytest.mark.unit


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

        with patch.object(sentry_primitives._logger, "warning") as mock_warning:
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

        with patch("utils.sentry_scrub_events._safe_log_warning") as mock_warn:
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
        tags = {sentry_events._INTERNAL_TAG_KEY: sentry_events._INTERNAL_TAG_VALUE}
        assert sentry_events._has_internal_tag(tags) is True

    def test_list_form_with_internal_tag_returns_true(self) -> None:
        tags = [
            ("env", "prod"),
            (sentry_events._INTERNAL_TAG_KEY, sentry_events._INTERNAL_TAG_VALUE),
        ]
        assert sentry_events._has_internal_tag(tags) is True

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
            {sentry_events._INTERNAL_TAG_KEY: "wrong_value"},  # dict 形式 + value mismatch
            [("env", "prod"), ("other_key", "other_value")],  # list 形式だが内部 tag 不在
            [(sentry_events._INTERNAL_TAG_KEY, "wrong_value")],  # list 形式 + value mismatch
            [("not-a-tuple-with-2-elements",)],  # list 内 malformed item
        ],
    )
    def test_fall_through_returns_false(self, non_match_value: Any) -> None:
        """dict / list 以外、または内部 tag 不在の場合は常に False を返す。

        defensive fall-through branch を gate 化することで、helper の
        unintended True 返却 (recursion guard 誤発火 → 通常 event の
        scrub スキップ = PII 漏洩経路) を回帰防止する。
        """
        assert sentry_events._has_internal_tag(non_match_value) is False


class TestScrubExceptionFailOpenBranches:
    """_scrub_exception_frame / _scrub_exception_stacktrace の fail-open 警告分岐の直接テスト

    これらの分岐 (frame 非 dict / frame_vars 非 dict・None / frames 非 list・None) は
    従来 _before_send 経由の統合テストでしか到達せず、PII 漏洩防止に関わる重要パスのため
    直接ユニットテストで個別に検証する。
    """

    def test_frame_not_dict_returns_input_and_warns_high_risk(self) -> None:
        """frame が dict でない場合: 入力を破壊せず返し、HIGH リスク警告を出す (fail-open)。"""
        with patch.object(sentry_events, "_safe_log_warning") as mock_warn:
            result = sentry_events._scrub_exception_frame("not-a-frame")

        assert result == "not-a-frame"
        mock_warn.assert_called_once()
        assert mock_warn.call_args.args[0] == "sentry_exception_frame_unexpected_type"
        assert mock_warn.call_args.kwargs.get("pii_leak_risk") == "HIGH"

    def test_frame_vars_unexpected_type_skips_scrub_and_warns(self) -> None:
        """frame['vars'] が dict/None 以外: vars を素通しし警告を出す (scrub スキップ)。"""
        frame = {"function": "handler", "vars": "not-a-dict"}
        with patch.object(sentry_events, "_safe_log_warning") as mock_warn:
            result = sentry_events._scrub_exception_frame(frame)

        assert result["vars"] == "not-a-dict"
        mock_warn.assert_called_once()
        assert mock_warn.call_args.args[0] == "sentry_exception_frame_vars_unexpected_type"

    def test_frame_vars_none_no_warning(self) -> None:
        """frame['vars'] が None (正常: vars 欠如): 警告を出さず frame を返す (誤検知防止)。"""
        frame = {"function": "handler"}
        with patch.object(sentry_events, "_safe_log_warning") as mock_warn:
            result = sentry_events._scrub_exception_frame(frame)

        assert result == {"function": "handler"}
        mock_warn.assert_not_called()

    def test_frame_vars_dict_is_scrubbed(self) -> None:
        frame = {"vars": {"password": "secret", "user_input": "safe_value"}}
        result = sentry_events._scrub_exception_frame(frame)

        assert result["vars"]["password"] == "[REDACTED]"  # noqa: S105
        assert result["vars"]["user_input"] == "safe_value"

    def test_frame_source_context_is_removed_and_vars_are_scrubbed(self) -> None:
        frame = {
            "pre_context": ["API_KEY = 'secret'"],
            "context_line": "raise RuntimeError(password)",
            "post_context": ["logger.info(user_email)"],
            "vars": {"password": "secret", "user_input": "safe_value"},
        }

        result = sentry_events._scrub_exception_frame(frame)

        assert "pre_context" not in result
        assert "context_line" not in result
        assert "post_context" not in result
        assert result["vars"]["password"] == "[REDACTED]"  # noqa: S105
        assert result["vars"]["user_input"] == "safe_value"

    def test_frames_unexpected_type_returns_input_and_warns(self) -> None:
        """stacktrace['frames'] が list/None 以外: stacktrace を素通しし警告を出す (fail-open)。"""
        stacktrace = {"frames": "not-a-list"}
        with patch.object(sentry_events, "_safe_log_warning") as mock_warn:
            result = sentry_events._scrub_exception_stacktrace(stacktrace)

        assert result == {"frames": "not-a-list"}
        mock_warn.assert_called_once()
        assert mock_warn.call_args.args[0] == "sentry_exception_frames_unexpected_type"

    def test_frames_none_no_warning(self) -> None:
        stacktrace = {"registers": {"rax": "0x0"}}
        with patch.object(sentry_events, "_safe_log_warning") as mock_warn:
            result = sentry_events._scrub_exception_stacktrace(stacktrace)

        assert result == {"registers": {"rax": "0x0"}}
        mock_warn.assert_not_called()


def test_internal_tag_value_is_valid_hex() -> None:
    import re

    from utils.sentry_scrub_events import _INTERNAL_TAG_VALUE

    assert re.fullmatch(r"[0-9a-f]{32}", _INTERNAL_TAG_VALUE) is not None
    assert len(_INTERNAL_TAG_VALUE) <= 200  # Sentry SDK tag value 上限 200文字以内


def test_exception_value_item_redacts_dict_bytes_value() -> None:
    result = _scrub_exception_value_item({"value": b"password=secret"})

    assert result == {"value": "[REDACTED]"}


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
            sentry_events._set_internal_extras(mock_scope, {"user_email": "x@example.com"})

        # 拒否時は部分書き込みが起きない（原子性）
        mock_scope.set_extra.assert_not_called()

    def test_mixed_unauthorized_key_raises_before_partial_write(self) -> None:
        """許可キー混在時も未許可キーがあれば scope へ一切書き込まない。"""
        mock_scope = MagicMock()

        with pytest.raises(
            ValueError,
            match=r"Unauthorized key in internal event extra: 'user_email'",
        ):
            sentry_events._set_internal_extras(
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

        sentry_events._set_internal_extras(
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
        sentry_events._set_internal_extras(mock_scope, {})
        mock_scope.set_extra.assert_not_called()
