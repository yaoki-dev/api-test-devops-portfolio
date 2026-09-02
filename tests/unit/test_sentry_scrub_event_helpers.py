"""イベント整形ヘルパー（event helpers）のテスト

_scrub_exception_field のスクラブと fail-open 分岐、_scrub_exception_frame /
_scrub_exception_stacktrace の fail-open 分岐、_scrub_exception_value_item の
bytes 値スクラブ、内部タグ（_has_internal_tag）と extras（_set_internal_extras）
の補助関数をカバー。

_scrub_exception_value_item の直接テスト（scalar の fail-open 警告を含む）は
test_sentry_scrub_events.py 側にある。
"""

from __future__ import annotations

from collections import namedtuple
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from sentry_sdk.types import Event

import utils.sentry_scrub_events as sentry_events
from utils.sentry_scrub_events import (
    _mask_freetext_pii,
    _scrub_event_message_fields,
    _scrub_exception_field,
    _scrub_exception_value_item,
    _scrub_exception_value_item_extra_keys,
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

        with patch.object(sentry_events, "_safe_log_warning") as mock_warning:
            result = _scrub_exception_field(exception_value)

        frames = result["values"][0]["stacktrace"]["frames"]
        assert frames[0] == "raw-frame"
        assert frames[1]["vars"] == {"password": "[REDACTED]", "safe": "ok"}

        mock_warning.assert_called_once()
        assert mock_warning.call_args.args[0] == "sentry_exception_frame_unexpected_type"
        call_kwargs = mock_warning.call_args.kwargs
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


@pytest.mark.parametrize(
    "structured_value",
    [
        pytest.param({"password": "hunter2"}, id="dict"),
        pytest.param(["token=abc123"], id="list"),
        pytest.param(("token=abc123",), id="tuple"),
    ],
)
def test_exception_value_item_redacts_structured_value(structured_value: Any) -> None:
    """非文字列の value も REDACT する。

    _scrub_exception_value_item_extra_keys が "value" を明示スキップするため、
    ここで REDACT しないと構造化された value はどこからもスクラブされず素通りする。
    custom before_send hook / SDK 拡張が構造化 value を渡す経路を想定した多層防御。
    """
    result = _scrub_exception_value_item({"type": "ValueError", "value": structured_value})

    assert result == {"type": "ValueError", "value": "[REDACTED]"}


def test_exception_value_item_keeps_numeric_value() -> None:
    """int/float/bool は PII 非含のため素通しする（非 dict value_item の扱いと対称）。"""
    assert _scrub_exception_value_item({"value": 42}) == {"value": 42}


def test_exception_value_item_namedtuple_does_not_raise() -> None:
    """namedtuple を再構築しようとすると TypeError になるため plain tuple へ落とす。

    `type(value_item)(generator)` は namedtuple の位置引数シグネチャと衝突する。
    ここで例外が漏れると before_send がイベントごと落とし観測性を失う。
    """
    params = namedtuple("Params", ["a", "b"])("a@b.com", 42)  # noqa: PYI024

    result = _scrub_exception_value_item(params)

    # 素の str は redact されない（_scrub_list_item のキー文脈方針）。
    # ここで固定するのは plain tuple へ落ちて例外にならないこと。
    assert result == ("a@b.com", 42)
    assert type(result) is tuple


def test_exception_value_item_extra_keys_namedtuple_does_not_raise() -> None:
    """extra key 側の並び再構築も namedtuple で落ちない。"""
    scrubbed_value: dict[str, Any] = {
        "type": "ValueError",
        "custom": namedtuple("Params", ["a", "b"])("a@b.com", 42),  # noqa: PYI024
    }

    _scrub_exception_value_item_extra_keys(scrubbed_value)

    assert scrubbed_value["custom"] == ("a@b.com", 42)
    assert type(scrubbed_value["custom"]) is tuple


def test_exception_value_item_extra_keys_keeps_list_type() -> None:
    """list は list のまま返し、tuple 化しない（並び型を保つ既存契約）。"""
    scrubbed_value: dict[str, Any] = {"type": "ValueError", "custom": [{"password": "hunter2"}]}

    _scrub_exception_value_item_extra_keys(scrubbed_value)

    assert scrubbed_value["custom"] == [{"password": "[REDACTED]"}]


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


class TestMaskFreetextPII:
    """message / logentry 向け選択的マスクの境界を検証する。"""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            pytest.param(
                "login failed for alice@example.com password=hunter2",
                "login failed for [REDACTED] password=[REDACTED]",
                id="email_and_assignment",
            ),
            pytest.param("token: abc123, status=ok", "token: [REDACTED], status=ok", id="colon"),
            pytest.param(
                "api_key='sk live 123' user=bob",
                "api_key=[REDACTED] user=bob",
                id="quoted_value_with_spaces",
            ),
            pytest.param(
                "Authorization: Bearer secret status=500",
                "Authorization: [REDACTED] status=500",
                id="authorization_bearer_keeps_following_assignment",
            ),
            pytest.param(
                "proxy-authorization=Basic abc123",
                "proxy-authorization=[REDACTED]",
                id="proxy_authorization_case_insensitive",
            ),
            pytest.param(
                '{"Authorization": "Digest username=alice, realm=example"}',
                '{"Authorization": [REDACTED]}',
                id="quoted_authorization_digest",
            ),
            pytest.param(
                "password hunter2 token＝abc123 cfg[secret]=xyz",
                "password [REDACTED] token＝[REDACTED] cfg[secret]=[REDACTED]",
                id="space_fullwidth_and_bracket_assignments",
            ),
            pytest.param(
                "パスワード: hunter2 メールアドレス: alice@example.com",
                "パスワード: [REDACTED] メールアドレス: [REDACTED]",
                id="japanese_sensitive_labels",
            ),
            pytest.param(
                "request eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.s3cr3t",
                "request [REDACTED]",
                id="bare_jwt",
            ),
            pytest.param(
                "card 4111 1111 1111 1111 phone +81 90 1234 5678",
                "card [REDACTED] phone [REDACTED]",
                id="bare_card_and_international_phone",
            ),
        ],
    )
    def test_sensitive_parts_are_masked(self, text: str, expected: str) -> None:
        assert _mask_freetext_pii(text) == expected

    @pytest.mark.parametrize(
        "text",
        [
            pytest.param("retry=3 attempt=2", id="non_sensitive_keys"),
            pytest.param("timeout after 30s (retry=1)", id="parenthesized"),
        ],
    )
    def test_non_sensitive_text_is_preserved(self, text: str) -> None:
        """機密キー名を持たない代入は潰さない。issue タイトルの識別性を保つため。"""
        assert _mask_freetext_pii(text) == text

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            pytest.param(
                "token=abc123&status=ok&retry=3",
                "token=[REDACTED]&status=ok&retry=3",
                id="query_string_keeps_following_params",
            ),
            pytest.param(
                'body={"password": "hunter2"}',
                'body={"password": [REDACTED]}',
                id="json_nested_in_non_sensitive_key",
            ),
            pytest.param(
                '{"password": "hunter2", "email": "a@b.co"}',
                '{"password": [REDACTED], "email": [REDACTED]}',
                id="bare_json_quoted_keys",
            ),
            pytest.param("token=a]b", "token=[REDACTED]", id="value_containing_bracket"),
        ],
    )
    def test_structured_text_is_masked_without_collateral_loss(
        self, text: str, expected: str
    ) -> None:
        """構造化文字列の境界。マスクが過小（漏洩）にも過大（情報喪失）にもならないこと。

        いずれも実装当初の正規表現では失敗した。``&`` 区切りで後続パラメータを
        巻き込み、JSON は外側の非機密キーが内側を食い潰し、``]`` を含む値は
        途中で切れて残りが漏れた。
        """
        assert _mask_freetext_pii(text) == expected

    @pytest.mark.parametrize(
        "text",
        [
            pytest.param("password=[REDACTED] realpw=x", id="already_redacted"),
            pytest.param('{"password": "hunter2"}', id="json"),
            pytest.param("token=abc&status=ok", id="query_string"),
        ],
    )
    def test_masking_is_idempotent(self, text: str) -> None:
        """二重適用で出力が壊れないこと。before_send は再入しうるため。"""
        once = _mask_freetext_pii(text)

        assert _mask_freetext_pii(once) == once

    def test_authorization_masking_is_idempotent(self) -> None:
        text = "Authorization: Bearer secret"
        once = _mask_freetext_pii(text)
        assert once == "Authorization: [REDACTED]"
        assert _mask_freetext_pii(once) == once

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            pytest.param(
                "Authorization: Bearer YWJjZA==",
                "Authorization: [REDACTED]",
                id="base64_padding_at_end",
            ),
            pytest.param(
                "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.s3cr3t",
                "Authorization: [REDACTED]",
                id="dotted_jwt",
            ),
            pytest.param(
                "Authorization: Bearer YWJjZA==\nstatus=500",
                "Authorization: [REDACTED]\nstatus=500",
                id="lf_termination_preserves_context",
            ),
            pytest.param(
                "Authorization: Bearer YWJjZA==\r\nstatus=500",
                "Authorization: [REDACTED]\r\nstatus=500",
                id="crlf_termination_preserves_context",
            ),
        ],
    )
    def test_authorization_masks_padded_tokens_and_line_terminators(
        self, text: str, expected: str
    ) -> None:
        """認証値のpaddingと改行終端を含めてcredentialを残さない。"""
        assert _mask_freetext_pii(text) == expected


class TestScrubEventMessageFields:
    """message / logentry を専用経路でスクラブすることを検証する。"""

    def test_message_and_logentry_are_masked(self) -> None:
        event = {
            "message": "x token=abc",
            "logentry": {
                "formatted": "login failed for alice@example.com password=hunter2",
                "message": "login failed for %s",
                "params": ["alice@example.com", 42],
            },
        }

        _scrub_event_message_fields(event)

        assert event["message"] == "x token=[REDACTED]"
        assert event["logentry"] == {
            "formatted": "login failed for [REDACTED] password=[REDACTED]",
            "message": "login failed for %s",
            "params": ["[REDACTED]", 42],
        }

    def test_before_send_masks_authorization_in_message(self) -> None:
        event = cast(
            Event,
            {"message": "request failed Authorization: Bearer secret-xyz"},
        )

        result = sentry_events._before_send(event, {})

        assert result is not None
        assert result["message"] == "request failed Authorization: [REDACTED]"
        assert "secret-xyz" not in str(result)

    @pytest.mark.parametrize("line_ending", ["\n", "\r\n"])
    def test_before_send_masks_padded_authorization_before_next_line(
        self, line_ending: str
    ) -> None:
        event = cast(
            Event,
            {"message": (f"request failed Authorization: Bearer YWJjZA=={line_ending}status=500")},
        )

        result = sentry_events._before_send(event, {})

        assert result is not None
        assert result["message"] == (
            f"request failed Authorization: [REDACTED]{line_ending}status=500"
        )
        assert "YWJjZA==" not in str(result)

    def test_bare_param_value_is_redacted(self) -> None:
        """LoggingIntegration の実イベント形状。params の裸の値も潰れること。

        formatted だけを塞いでも params にオリジナルが残る経路があり、
        自由文字列マスクでは ``"hunter2"`` のようなキー文脈を持たない値を捕まえられない。
        """
        event: dict[str, Any] = {
            "logentry": {
                "message": "auth failed for %s password=%s",
                "formatted": "auth failed for alice@example.com password=hunter2",
                "params": ["alice@example.com", "hunter2"],
            }
        }

        _scrub_event_message_fields(event)

        assert event["logentry"]["params"] == ["[REDACTED]", "[REDACTED]"]
        assert "hunter2" not in event["logentry"]["formatted"]

    def test_breadcrumb_messages_are_masked(self) -> None:
        """breadcrumbs[*].message も塞ぐこと。

        キー名 ``message`` は機密キー集合に無く ``_SCRUBBED_EVENT_FIELDS`` 経由の
        キー名ベーススクラブを素通りする。LoggingIntegration は INFO 以上を
        breadcrumb 化するため、logentry と同じ形の PII がここにも流れ込む。
        """
        event: dict[str, Any] = {
            "breadcrumbs": {
                "values": [
                    {"message": "retrying for bob@example.com token=abc123", "level": "warning"},
                    {"level": "info"},
                    "not-a-dict",
                ]
            }
        }

        _scrub_event_message_fields(event)

        values = event["breadcrumbs"]["values"]
        assert values[0] == {
            "message": "retrying for [REDACTED] token=[REDACTED]",
            "level": "warning",
        }
        assert values[1] == {"level": "info"}
        assert values[2] == "not-a-dict"

    def test_non_string_params_are_kept(self) -> None:
        """非 str は残す。配列の形と型がデバッグの手掛かりになるため。"""
        event: dict[str, Any] = {"logentry": {"params": ["secret", 42, True, None]}}

        _scrub_event_message_fields(event)

        assert event["logentry"]["params"] == ["[REDACTED]", 42, True, None]

    def test_dict_params_go_through_key_based_scrub(self) -> None:
        event: dict[str, Any] = {"logentry": {"params": {"password": "hunter2", "safe": "ok"}}}

        _scrub_event_message_fields(event)

        assert event["logentry"]["params"] == {"password": "[REDACTED]", "safe": "ok"}

    def test_dict_inside_params_list_goes_through_key_based_scrub(self) -> None:
        """params 直下の dict と同じ扱いを、list に入れ子になった dict にも適用する。

        キー文脈がある要素はキーベース scrub、無い素の str は位置ベースで潰す、
        という二重ポリシーを入れ子でも維持することを固定する。
        """
        event: dict[str, Any] = {
            "logentry": {"params": [{"password": "hunter2", "safe": "ok"}, "alice@example.com"]}
        }

        _scrub_event_message_fields(event)

        assert event["logentry"]["params"] == [
            {"password": "[REDACTED]", "safe": "ok"},
            "[REDACTED]",
        ]

    def test_bytes_params_are_redacted(self) -> None:
        """bytes も PII を含みうるため str と同じく潰す。

        ``_scrub_exception_value_item`` が bytes を REDACT する方針と対称にする。
        """
        event: dict[str, Any] = {"logentry": {"params": [b"password=hunter2", 42]}}

        _scrub_event_message_fields(event)

        assert event["logentry"]["params"] == ["[REDACTED]", 42]

    def test_nested_list_params_are_scrubbed(self) -> None:
        event: dict[str, Any] = {"logentry": {"params": [["alice@example.com", "hunter2"], 42]}}

        _scrub_event_message_fields(event)

        assert event["logentry"]["params"] == [["[REDACTED]", "[REDACTED]"], 42]

    def test_dict_inside_params_tuple_is_scrubbed(self) -> None:
        event: dict[str, Any] = {"logentry": {"params": ({"token": "sk-live-XYZ"},)}}

        _scrub_event_message_fields(event)

        assert event["logentry"]["params"] == ({"token": "[REDACTED]"},)

    def test_namedtuple_params_do_not_raise(self) -> None:
        """namedtuple を再構築しようとすると TypeError になるため plain tuple へ落とす。

        `type(params)(generator)` は namedtuple の位置引数シグネチャと衝突する。
        """
        params = namedtuple("Params", ["a", "b"])("secret", 42)  # noqa: PYI024
        event: dict[str, Any] = {"logentry": {"params": params}}

        _scrub_event_message_fields(event)

        assert event["logentry"]["params"] == ("[REDACTED]", 42)

    def test_circular_params_hit_depth_guard(self) -> None:
        """循環参照でも RecursionError にならず深度ガードで打ち切る。"""
        circular: list[Any] = []
        circular.append(circular)
        event: dict[str, Any] = {"logentry": {"params": circular}}

        _scrub_event_message_fields(event)

        flattened = repr(event["logentry"]["params"])
        assert "[MAX_DEPTH_EXCEEDED]" in flattened

    @pytest.mark.parametrize(
        ("transaction", "expected"),
        [
            pytest.param(
                "GET /users?token=abc123",
                # _scrub_url は結果を URL エンコードして返すため [] は %5B%5D になる。
                # spans[*].description と同一の既存挙動。
                "GET /users?token=%5BREDACTED%5D",
                id="query_string_pii_removed_method_kept",
            ),
            pytest.param(
                "GET /users/alice@example.com/details",
                "GET /users/[REDACTED]/details",
                id="path_pii_removed",
            ),
            pytest.param(
                "GET /users/1234/details",
                "GET /users/<digits>/details",
                id="numeric_path_identifier_removed",
            ),
            pytest.param(
                "GET /jobs/550e8400-e29b-41d4-a716-446655440000",
                "GET /jobs/<uuid>",
                id="uuid_path_identifier_removed",
            ),
            pytest.param(
                "GET /users/1234;token=secret",
                "GET /users/<digits>;token=[REDACTED]",
                id="path_parameter_and_identifier_removed",
            ),
            pytest.param("GET /users", "GET /users", id="clean_transaction_untouched"),
            pytest.param("celery.task.sync", "celery.task.sync", id="non_url_name_untouched"),
        ],
    )
    def test_transaction_name_is_scrubbed(self, transaction: str, expected: str) -> None:
        """transaction 名の PII を落とし、メソッドと経路の可読性は保つこと。

        Sentry 公式が「raw URL がそのまま transaction 名になり PII を運ぶ」箇所として
        明示している。SDK の URL パラメータ化はルーティング設定次第で失敗しうる。
        """
        event: dict[str, Any] = {"transaction": transaction}

        _scrub_event_message_fields(event)

        assert event["transaction"] == expected

    def test_non_string_transaction_is_left_alone(self) -> None:
        """str 以外は触らない。壊すと transaction イベントごと失うため。"""
        event: dict[str, Any] = {"transaction": None}

        _scrub_event_message_fields(event)

        assert event["transaction"] is None

    def test_non_dict_logentry_is_dropped_fail_closed(self) -> None:
        """dict 以外の logentry はスクラブ不能なため空 dict へ倒す。"""
        event: dict[str, Any] = {"logentry": "raw-string"}

        with patch.object(sentry_events, "_safe_log_warning") as mock_warning:
            _scrub_event_message_fields(event)

        assert event["logentry"] == {}
        mock_warning.assert_called_once()

    def test_before_send_masks_message_end_to_end(self) -> None:
        """_before_send 経由でも message / logentry がマスクされる。"""
        event = cast(
            "Any",
            {
                "message": "login failed for alice@example.com password=hunter2",
                "logentry": {"formatted": "login failed for alice@example.com password=hunter2"},
            },
        )

        result = sentry_events._before_send(event, {})

        assert result is not None
        assert result["message"] == "login failed for [REDACTED] password=[REDACTED]"
        assert result["logentry"]["formatted"] == "login failed for [REDACTED] password=[REDACTED]"
