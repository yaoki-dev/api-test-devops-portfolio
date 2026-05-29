"""Sentry SDK初期化モジュールのテスト

utils/sentry_init.py の単体テスト。
機密データスクラブ、DSN検証、初期化ロジックをカバー。

テストカテゴリ:
    - 初期化系: init_sentry()の正常/異常系
    - スクラブ系: _scrub_sensitive_data()の再帰処理
    - 状態管理: グローバルフラグの整合性
    - before_send: イベント前処理フック
"""

from __future__ import annotations

import sys
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr
from sentry_sdk.types import Event

import utils.sentry_init as sentry_module
from utils.sentry_init import (
    _SCRUBBED_EVENT_FIELDS,
    MAX_SCRUB_DEPTH,
    SENSITIVE_KEYS,
    _before_send,
    _is_sensitive_key,
    _scrub_exception_field,
    _scrub_query_string,
    _scrub_sensitive_data,
    _scrub_url,
    init_sentry,
    is_sentry_initialized,
    reset_sentry_state,
)

# Module-level marker: All tests in this file are unit tests
pytestmark = pytest.mark.unit


class TestScrubSensitiveData:
    """機密データスクラブのテスト"""

    def test_scrub_password_field(self) -> None:
        """パスワードフィールドがREDACTEDされる"""
        data = {"password": "dummy", "username": "user"}
        result = _scrub_sensitive_data(data)
        assert result["password"] == "[REDACTED]"  # noqa: S105
        assert result["username"] == "user"

    def test_scrub_nested_dict(self) -> None:
        """ネストされた辞書内の機密データもスクラブ"""
        data = {"user": {"api_key": "key123", "email": "user@example.com"}}
        result = _scrub_sensitive_data(data)
        assert result["user"]["api_key"] == "[REDACTED]"
        assert result["user"]["email"] == "[REDACTED]"  # email はPII（GDPR対応）でスクラブ対象

    def test_scrub_list_of_dicts(self) -> None:
        """リスト内辞書の機密データもスクラブ"""
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
        """リスト内のネストしたlistも再帰的にスクラブされる"""
        data = {"items": [[{"x-auth-token": "tok"}, {"name": "public"}]]}
        result = _scrub_sensitive_data(data)
        assert result["items"][0][0]["x-auth-token"] == "[REDACTED]"  # noqa: S105
        assert result["items"][0][1]["name"] == "public"

    def test_scrub_case_insensitive(self) -> None:
        """キー名は大文字小文字を区別しない"""
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
        """非辞書データはそのまま返す"""
        assert _scrub_sensitive_data(input_data) == expected

    def test_scrub_non_dict_triggers_fail_open_warning(self) -> None:
        """非dict入力時にfail-open警告がログ出力され、データはそのまま返る。"""
        with patch.object(sentry_module._logger, "warning") as mock_warning:
            result = _scrub_sensitive_data("not_a_dict")
        assert result == "not_a_dict"
        mock_warning.assert_called_once()
        call_kwargs = mock_warning.call_args[1]
        assert call_kwargs["actual_type"] == "str"
        assert call_kwargs["action"] == "return_as_is"

    def test_scrub_empty_dict(self) -> None:
        """空辞書は空辞書を返す"""
        assert _scrub_sensitive_data({}) == {}

    def test_scrub_deeply_nested(self) -> None:
        """3階層ネストでもスクラブされる"""
        data = {"level1": {"level2": {"level3": {"secret": "deep_secret", "public": "visible"}}}}
        result = _scrub_sensitive_data(data)
        assert result["level1"]["level2"]["level3"]["secret"] == "[REDACTED]"  # noqa: S105
        assert result["level1"]["level2"]["level3"]["public"] == "visible"

    def test_scrub_preserves_original(self) -> None:
        """元データは変更されない（イミュータビリティ）"""
        original = {"password": "dummy"}
        _scrub_sensitive_data(original)
        assert original["password"] == "dummy"  # noqa: S105

    def test_scrub_max_depth_exceeded(self) -> None:
        """再帰制限を超えると[MAX_DEPTH_EXCEEDED]を返す（循環参照対策）"""
        # MAX_SCRUB_DEPTH階層のネストを作成
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
        """MAX_SCRUB_DEPTHが適切な値に設定されている"""
        assert MAX_SCRUB_DEPTH == 10
        assert isinstance(MAX_SCRUB_DEPTH, int)


class TestSensitiveKeysCompleteness:
    """SENSITIVE_KEYSの網羅性テスト"""

    def test_sensitive_keys_is_frozenset(self) -> None:
        """SENSITIVE_KEYSはfrozenset（不変）"""
        assert isinstance(SENSITIVE_KEYS, frozenset)

    def test_sensitive_keys_count(self) -> None:
        """40 sensitive keys defined (sentinel test).

        The hardcoded count is intentional: it serves as a sentinel to detect
        unintended additions/removals to SENSITIVE_KEYS. When adding keys,
        update the count in this test as well.
        """
        assert len(SENSITIVE_KEYS) == 43  # SENSITIVE_KEYS 変更時はここの数値も更新

    @pytest.mark.parametrize(
        "key",
        [
            # 認証系（基本）
            "password",
            "token",
            "secret",
            "api_key",
            "dsn",
            "authorization",
            "cookie",
            "session",
            "credential",
            # 認証系（拡張）
            "bearer",
            "jwt",
            "access_token",
            "refresh_token",
            "private_key",
            "client_secret",
            "x-api-key",
            "auth_token",
            "passwd",
            # 暗号化
            "encryption_key",
            "cipher_key",
            # OAuth
            "oauth_token",
            # 二要素認証
            "otp",
            "mfa",
            "totp",
            # 個人情報
            "email",
            "ip_address",
            "database_url",
            "ssn",
            "credit_card",
            "cvv",
            "card_number",
            # HTTPレスポンスプレビュー
            "body_preview",
            "access_key",
            "proxy-authorization",
            "set-cookie",
            "x-auth-token",
            "x-csrf-token",
            "csrf_token",
            "x-refresh-token",
            "x-access-token",
        ],
    )
    def test_expected_keys_present(self, key: str) -> None:
        """期待される機密キーが含まれている"""
        assert key in SENSITIVE_KEYS

    def test_sensitive_key_match_uses_word_boundaries_with_hyphen_normalization(self) -> None:
        """機密キー判定は単語境界一致 + ハイフン/アンダースコア正規化。

        composite key (接頭辞/接尾辞付き)、ハイフン variant、case 違いの全てを redact する。
        SENSITIVE_KEYS に含まれない word や unrelated substring は redact しない。
        """
        result = _scrub_sensitive_data(
            {
                # 完全一致
                "access_token": "secret-a",
                # composite (接尾辞)
                "access_token_suffix": "secret-b",
                # composite (接頭辞)
                "user_password": "secret-c",
                # ハイフン variant
                "X-Auth-Token": "secret-d",
                # case 違い
                "EMAIL_ADDRESS": "user@example.com",
                # session 系 composite
                "session_id": "sess-123",
                # 非機密
                "name": "public",
                "items_count": 42,
                "photo_url": "https://example.com/avatar.png",
                "prototype": "v2",
                "option": "safe",
            }
        )
        assert result["access_token"] == "[REDACTED]"  # noqa: S105
        assert result["access_token_suffix"] == "[REDACTED]"  # noqa: S105
        assert result["user_password"] == "[REDACTED]"  # noqa: S105
        assert result["X-Auth-Token"] == "[REDACTED]"  # noqa: S105
        assert result["EMAIL_ADDRESS"] == "[REDACTED]"
        assert result["session_id"] == "[REDACTED]"
        # 非機密キーは保持
        assert result["name"] == "public"
        assert result["items_count"] == 42
        assert result["photo_url"] == "https://example.com/avatar.png"
        assert result["prototype"] == "v2"
        assert result["option"] == "safe"

    @pytest.mark.parametrize(
        "composite_key",
        [
            # PR#347 review で発見された PII regression 対象 composite key
            "user_password",
            "db_password",
            "password_hash",
            "customer_email",
            "email_address",
            "session_id",
            "user_session",
            "auth_token_v2",
            "legacy_jwt",
            "customer_jwt",
            "bearer_token",
            "request_api_key",
            "internal_secret",
            "x-auth-token",
            "X_API_KEY",
            "cookie_value",
        ],
    )
    def test_composite_keys_are_redacted(self, composite_key: str) -> None:
        """composite key (接頭辞/接尾辞付き) の PII regression 回帰防止テスト。

        PR#347 で _is_sensitive_key が substring → exact 一致へ変更され、
        composite key が漏洩する regression が発生した。本テストはその逆方向の
        変更を再導入しないための gate。
        """
        result = _scrub_sensitive_data({composite_key: "leak-me"})
        assert result[composite_key] == "[REDACTED]", (
            f"composite key '{composite_key}' must be redacted to prevent PII regression"
        )

    @pytest.mark.parametrize(
        ("key", "expected"),
        [
            # True positives: 短縮語そのもの → True
            ("otp", True),
            ("mfa", True),
            ("totp", True),
            # PR#347 review Q-2: prefix/suffix 非対称設計の契約化
            # `token` 単独は _SENSITIVE_KEY_PATTERN (prefix `(?:^|[_\d])`,
            # suffix `(?=[^a-z]|$)`) では match しないが、_COMPACT_SENSITIVE_KEYS
            # (utils/sentry_init.py:210-212) のアンダースコア除去後完全一致 fallback で
            # True 判定される。設計意図契約化。
            ("token", True),
            # True positives: アンダースコア境界で区切られた複合キー → True
            ("otp_count", True),  # noqa: S105
            ("mfa_setup", True),
            ("totp_secret", True),  # "totp" + "secret" 両方 hit
            ("user_otp", True),
            ("otp_secret", True),
            # False positives: 短縮語を含むだけの非機密キー → False
            ("photo_url", False),
            ("prototype", False),
            ("option", False),
            ("comfort_level", False),
            ("message", False),
            ("version", False),
            # 関係ないキー → False
            ("user_id", False),
            ("created_at", False),
        ],
    )
    def test_is_sensitive_key_short_word_behaviors(self, key: str, expected: bool) -> None:
        """短縮語は単語境界で区切られた場合のみ機密キーとして扱う。

        otp/mfa/totp 等の短縮語は SENSITIVE_KEYS に含まれるため単体では True。
        これらを接頭辞/接尾辞とする複合キー (otp_count / user_otp 等) も
        アンダースコア境界で区切られている場合は True になる。
        """
        assert _is_sensitive_key(key) is expected

    @pytest.mark.parametrize(
        ("key", "expected"),
        [
            # camelCase 機密キー → True（snake_case 正規化後にパターン一致）
            ("accessToken", True),
            ("apiKey", True),
            ("emailAddress", True),
            ("refreshToken", True),
            ("clientSecret", True),
            # Dotted keys from nested config/log fields are normalized like snake_case.
            ("config.password", True),
            ("user.email", True),
            ("auth.token", True),
            # camelCase 非機密キー → False
            ("photoUrl", False),
            ("itemCount", False),
        ],
    )
    def test_is_sensitive_key_camelcase_normalization(self, key: str, expected: bool) -> None:
        """camelCase キーは snake_case に正規化してから機密判定する。

        accessToken → access_token → token 境界で True。
        apiKey → api_key → api_key 完全一致で True。
        PR#347 review fix #1: camelCase PII バイパス修正の回帰テスト。
        """
        assert _is_sensitive_key(key) is expected

    @pytest.mark.parametrize(
        ("key", "expected"),
        [
            # True positives: 数字サフィックス付き機密キー（境界条件 \d）→ True
            ("password2", True),
            ("api_key2", True),
            ("token2", True),
            ("password1", True),
            ("secret9", True),
            ("authorization2", True),
            # True positives: 数字プレフィックス/中間数字を左境界として扱う
            ("v2token", True),
            ("2secret", True),
            ("3password", True),
            ("api_key1token", True),
            # False positives: 機密語にハイフン/アンダースコアの先頭境界がなく
            # `_NORMALIZED_SENSITIVE_KEYS` にも一致しない連結文字列 → False
            ("notasecretkey", False),  # 先頭境界 `^|_` 不成立
            ("prototype", False),
            ("photo_url", False),
            ("v2prototype", False),
            ("release2photo_url", False),
            # 既存挙動の維持確認: 数字なし + アンダースコア境界
            ("password_2", True),  # _ 区切りで境界成立
            ("api_key_2", True),
            # ハイフン区切り + 数字境界: api-key-v2 → api_key_v2 → True
            ("api-key-v2", True),
        ],
    )
    def test_is_sensitive_key_digit_boundary(self, key: str, expected: bool) -> None:
        r"""数字プレフィックス/サフィックスを単語境界として扱う回帰テスト。

        PR#347 review fix #2/#1: `_SENSITIVE_KEY_PATTERN` の数字境界を拡張。
        これにより `password2` / `api_key2` / `v2token` 等の連番命名規約でも
        redact が確実に発火する。

        Note: 現パターンは数字後に文字が続く `token1value` 等も True
        判定する（数字単独で境界成立のため）。これは defense-in-depth の安全側挙動
        として許容するが、`prototype` / `photo_url` 等の過剰検出は引き続き防ぐ。
        """
        assert _is_sensitive_key(key) is expected

    @pytest.mark.parametrize(
        ("key", "expected"),
        [
            # True positives: 全大文字命名（ACRONYM 分割不可 → compact fallback）→ True
            ("APIKEY", True),  # api_key compact = apikey
            ("ACCESSTOKEN", True),  # access_token compact = accesstoken
            ("PASSWORD", True),  # password compact = password
            ("SECRET", True),  # secret compact = secret (PR#347 fallback)
            # True positives: 既存 ACRONYM 分割が正常動作するケース → True
            ("APIKey", True),  # → api_key (ACRONYM_Word 分割)
            ("JSONWebToken", True),  # → json_web_token
            # False positives: 全大文字非機密キー → False
            ("PHOTOURL", False),  # compact photourl ≠ any sensitive compact
            ("PROTOTYPE", False),  # compact prototype ≠ any sensitive compact
            ("ITEMCOUNT", False),  # compact itemcount ≠ any sensitive compact
        ],
    )
    def test_is_sensitive_key_allcaps_normalization(self, key: str, expected: bool) -> None:
        """全大文字命名は compact fallback で機密判定する。

        ACRONYM regex `([A-Z]+)([A-Z][a-z])` は末尾が小文字で終わらない
        全大文字命名（APIKEY, ACCESSTOKEN 等）を分割できない。
        compact fallback（アンダースコア除去後の完全一致）がこれを補完する。
        `PHOTOURL` は compact `photourl` が `url` と完全一致しないため False 維持
        （substring 一致 ≠ 完全一致）。
        PR#347 review fix: 全大文字 PII バイパス修正の回帰テスト。
        """
        assert _is_sensitive_key(key) is expected


class TestScrubbedEventFieldsCompleteness:
    """_SCRUBBED_EVENT_FIELDSの網羅性テスト"""

    def test_scrubbed_event_fields_match_expected_contract(self) -> None:
        """スクラブ対象フィールドが過不足なく定義されている。"""
        assert isinstance(_SCRUBBED_EVENT_FIELDS, frozenset)
        assert _SCRUBBED_EVENT_FIELDS == frozenset(
            {
                "extra",
                "user",
                "contexts",
                "tags",
                "breadcrumbs",
                "exception",
            }
        )


class TestScrubQueryStringAndUrl:
    """query string / URL スクラブのテスト"""

    def test_scrub_query_string_preserves_duplicate_params(self) -> None:
        """重複クエリパラメータを落とさずスクラブする"""
        result = _scrub_query_string("token=a&safe=1&token=b&empty=")
        assert result == "token=%5BREDACTED%5D&safe=1&token=%5BREDACTED%5D&empty="

    def test_scrub_request_query_string_accepts_bytes(self) -> None:
        """request.query_string が bytes でもスクラブする"""
        result = sentry_module._scrub_request_query_string(b"token=a&safe=1")
        assert result == "token=%5BREDACTED%5D&safe=1"

    def test_scrub_url_removes_userinfo_and_fragment(self) -> None:
        """URLのuserinfo/fragmentを除去しqueryをスクラブする"""
        url = "https://user:pass@example.com/path?x-access-token=tok&safe=1#frag"
        result = _scrub_url(url)
        assert result == "https://example.com/path?x-access-token=%5BREDACTED%5D&safe=1"

    def test_scrub_url_preserves_non_sensitive_query_params(self) -> None:
        """非機密 query は変更せず、通常URLの正常系を保持する。"""
        url = "https://example.com/path?page=2&sort=asc"
        assert _scrub_url(url) == url

    def test_scrub_url_path_params_pass_through(self) -> None:
        """RFC 2396 パスパラメータ (`;key=value`) は query string ではない。
        scrub せずそのまま通過する (#7)。"""
        result = _scrub_url("https://example.com/path;session_id=secret?sort=asc#frag")
        assert result == "https://example.com/path;session_id=secret?sort=asc"

    def test_scrub_url_redacts_email_in_path(self) -> None:
        """URL パスセグメント内のメールアドレスを [REDACTED] に置換する (#16)。"""
        result = _scrub_url("https://example.com/users/user@example.com/profile?sort=asc")
        assert "user@example.com" not in result
        assert "[REDACTED]" in result
        assert "sort=asc" in result  # query は保持

    def test_scrub_url_redacts_email_in_path_params(self) -> None:
        """RFC 2396 パスパラメータ内のメールアドレスも [REDACTED] に置換する (#16)。"""
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
        """exception.values[*].value はメッセージ文字列ごと redaction する。"""
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
        """values が空 dict でも例外なく処理される。"""
        exception_value: dict[str, Any] = {"values": {}}

        result = _scrub_exception_field(exception_value)

        assert result == {"values": {}}


class TestHasInternalTag:
    """_has_internal_tag ヘルパーの defensive branch coverage テスト。

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
        """リクエストヘッダーがスクラブされる"""
        event = cast(Event, {"request": {"headers": {"Cookie": "session=abc123"}}})
        result_dict = self._call_before_send(event)
        assert result_dict["request"]["headers"]["Cookie"] == "[REDACTED]"

    def test_scrub_request_cookies_and_env(self) -> None:
        """request.cookies / request.env もスクラブされる。"""
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
        """リクエストボディがスクラブされる"""
        event = cast(Event, {"request": {"data": {"password": "secret", "username": "user"}}})
        result_dict = self._call_before_send(event)
        assert result_dict["request"]["data"]["password"] == "[REDACTED]"  # noqa: S105
        assert result_dict["request"]["data"]["username"] == "user"

    def test_scrub_extra_data(self) -> None:
        """extraデータがスクラブされる"""
        event = cast(Event, {"extra": {"token": "secret_token"}})
        result_dict = self._call_before_send(event)
        assert result_dict["extra"]["token"] == "[REDACTED]"  # noqa: S105

    def test_scrub_extra_body_preview(self) -> None:
        """extra.body_preview がスクラブされる"""
        event = cast(Event, {"extra": {"body_preview": "password=secret"}})
        result_dict = self._call_before_send(event)
        assert result_dict["extra"]["body_preview"] == "[REDACTED]"  # noqa: S105

    def test_scrub_tags(self) -> None:
        """タグがスクラブされる"""
        event = cast(Event, {"tags": {"api_key": "key123"}})
        result_dict = self._call_before_send(event)
        assert result_dict["tags"]["api_key"] == "[REDACTED]"

    def test_scrub_breadcrumbs(self) -> None:
        """breadcrumbs内の機密データがスクラブされる"""
        event = cast(Event, {"breadcrumbs": {"values": [{"data": {"set-cookie": "a=b"}}]}})
        result_dict = self._call_before_send(event)
        assert result_dict["breadcrumbs"]["values"][0]["data"]["set-cookie"] == "[REDACTED]"

    def test_scrub_breadcrumbs_list_form(self) -> None:
        """list[dict] 形式 breadcrumbs 内の機密データもスクラブされる"""
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
        """tags が list[list[str, str]] 形式 (JSON roundtrip) でも機密キーが redact される"""
        event = cast(Event, {"tags": [["api_token", "abc"], ["safe", "ok"]]})
        result_dict = self._call_before_send(event)
        scrubbed = list(result_dict["tags"])
        assert (scrubbed[0][0], scrubbed[0][1]) == ("api_token", "[REDACTED]")
        assert (scrubbed[1][0], scrubbed[1][1]) == ("safe", "ok")

    def test_scrub_tags_dict_form_defense_in_depth(self) -> None:
        """tags が非標準 list[dict] 形式でも defense-in-depth で機密キーが redact される

        Sentry SDK 標準仕様外だが custom before_send hook 等で生じうるため
        PII 漏洩を防ぐ目的で dict 要素も再帰スクラブする (PR #347 review iter2)。
        """
        event = cast(Event, {"tags": [{"authorization": "Bearer X", "label": "public"}]})
        result_dict = self._call_before_send(event)
        tag_dict = result_dict["tags"][0]
        assert tag_dict["authorization"] == "[REDACTED]"
        assert tag_dict["label"] == "public"

    def test_scrub_tags_non_sensitive_preserved(self) -> None:
        """tags 内の非機密ペア (key が SENSITIVE_KEYS に該当しない) は redact されない"""
        event = cast(Event, {"tags": [("environment", "production"), ("version", "1.0.0")]})
        result_dict = self._call_before_send(event)
        scrubbed = list(result_dict["tags"])
        assert (scrubbed[0][0], scrubbed[0][1]) == ("environment", "production")
        assert (scrubbed[1][0], scrubbed[1][1]) == ("version", "1.0.0")

    def test_scrub_breadcrumbs_2_element_list_not_overscrubbed(self) -> None:
        """breadcrumbs 内の非PII 2要素 list ([label, value]) が誤って tag-pair 扱いされない

        PR #347 review KP-003 / T3 対応の regression test。
        旧コードでは list[2]+str[0] heuristic が breadcrumbs まで適用され、
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
        """request.query_stringの重複キーを保持してスクラブする"""
        event = cast(Event, {"request": {"query_string": "token=a&safe=1&token=b"}})
        result_dict = self._call_before_send(event)
        assert (
            result_dict["request"]["query_string"]
            == "token=%5BREDACTED%5D&safe=1&token=%5BREDACTED%5D"
        )

    def test_scrub_request_query_string_accepts_bytes(self) -> None:
        """request.query_string が bytes でも機密値をスクラブする"""
        event = cast(Event, {"request": {"query_string": b"token=a&safe=1"}})
        result_dict = self._call_before_send(event)
        assert result_dict["request"]["query_string"] == "token=%5BREDACTED%5D&safe=1"

    def test_scrub_request_url_removes_userinfo_and_fragment(self) -> None:
        """request.urlのuserinfo/fragmentを除去する"""
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
        """exception フィールドのスクラブ失敗でもイベントをdropして内部通知する。"""
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
        """_scrub_url が例外を発生させた場合も fail-closed でイベントをdropする。"""
        event = cast(Event, {"request": {"url": "https://example.com/path?token=abc"}})

        with (
            patch.object(sentry_module, "_scrub_url", side_effect=RuntimeError("url-scrub-boom")),
            patch.object(sentry_module, "_emit_scrub_failure_to_sentry") as mock_emit,
            patch.object(sentry_module, "_safe_log_warning") as mock_warning,
        ):
            result = _before_send(event, {})

        assert result is None
        mock_warning.assert_called_once_with(
            "sentry_before_send_drop_event",
            error_type="RuntimeError",
            error_module="builtins",
        )
        mock_emit.assert_called_once()

    def test_before_send_drops_event_on_memory_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """MemoryError は fail-closed で event を drop し None を返す (PR#347 review #6)。

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
        """RecursionError は fail-closed で event を drop し None を返す (PR#347 review #6)。

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
        """_emit_scrub_failure_to_sentry は _INTERNAL_TAG を付与して capture_message を呼ぶ"""
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

    def test_returns_event(self) -> None:
        """イベントオブジェクトを返す（Noneではない）"""
        event = cast(Event, {"message": "test"})
        result_dict = self._call_before_send(event)
        assert result_dict["message"] == "test"

    def test_before_send_user_non_dict_replaced_with_empty_dict(self) -> None:
        """user が非 dict (str等) の場合、空dictに置換される."""
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
        """list 内の (key, value) ペア形式でない要素はそのまま保持される。"""
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

    def test_scrub_sentry_field_non_dict_logs_warning(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """非dict型フィールドは空dict置換 + logger.warning を常時出力."""
        # _scrub_sentry_field は SENTRY_DEBUG に関わらず logger.warning を出力する
        monkeypatch.setattr(sentry_module, "SENTRY_DEBUG", True)
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

    def test_scrub_sentry_field_non_dict_logs_warning_regardless_of_debug(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SENTRY_DEBUG=False時も logger.warning は常時出力（本番監視対応）."""
        monkeypatch.setattr(sentry_module, "SENTRY_DEBUG", False)
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

        PR#347 review #1: 旧実装は完全 silent (`except Exception: pass`) だったが、
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
        """exception.values[*].stacktrace.frames[*].vars 内の機密変数がスクラブされる。"""
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
        result = _before_send(event, {})
        assert result is not None, "fail-open: 異常構造でもイベントdropしない"
        result_dict = cast(dict[str, Any], result)
        assert result_dict["exception"]["values"] == "not_a_list", (
            "元の値が保持されている（破壊的置換なし）"
        )

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
        # 非 dict 要素はそのまま保持（fail-open）
        assert values[1] == "not_a_dict"
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
        """_scrub_tags_item の nested list 分岐 (3要素以上) で機密キーが redact される。"""
        nested = [("password", "secret"), ("safe", "ok"), ("token", "abc")]
        result = sentry_module._scrub_tags_item(nested)
        assert result[0] == ("password", "[REDACTED]")
        assert result[1] == ("safe", "ok")
        assert result[2] == ("token", "[REDACTED]")

    def test_scrub_tags_item_nonsensitive_value_nested_dict_scrubbed(self) -> None:
        """非機密タグペアの value が dict の場合、内部の機密キーが redact される。"""
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


class TestInitSentry:
    """Sentry初期化のテスト"""

    def setup_method(self) -> None:
        """各テスト前に状態リセット"""
        reset_sentry_state()

    def teardown_method(self) -> None:
        """各テスト後に状態リセット"""
        reset_sentry_state()

    @patch("utils.sentry_init.get_settings")
    def test_init_when_disabled(self, mock_settings: MagicMock) -> None:
        """enabled=Falseの場合はFalseを返す"""
        mock_settings.return_value.sentry.enabled = False
        assert init_sentry() is False

    @patch("utils.sentry_init.get_settings")
    def test_init_with_empty_dsn(self, mock_settings: MagicMock) -> None:
        """空DSNの場合はFalseを返す"""
        mock_settings.return_value.sentry.enabled = True
        mock_settings.return_value.sentry.dsn = SecretStr("")
        assert init_sentry() is False

    @patch("utils.sentry_init.get_settings")
    def test_init_with_invalid_dsn_format(self, mock_settings: MagicMock) -> None:
        """無効なDSN形式の場合、非本番環境ではFalseを返す"""
        mock_settings.return_value.sentry.enabled = True
        mock_settings.return_value.sentry.dsn = SecretStr("invalid-dsn")
        mock_settings.return_value.is_production_like.return_value = False  # 非本番環境 (#39)
        assert init_sentry() is False

    @patch("utils.sentry_init.get_settings")
    @patch("sentry_sdk.init")
    def test_init_with_valid_dsn(self, mock_sdk_init: MagicMock, mock_settings: MagicMock) -> None:
        """有効なDSNで初期化成功"""
        mock_settings.return_value.sentry.enabled = True
        mock_settings.return_value.sentry.dsn = SecretStr(
            "https://abc123@o456.ingest.us.sentry.io/789",
        )
        mock_settings.return_value.sentry.environment = "testing"
        mock_settings.return_value.sentry.traces_sample_rate = 0.1
        mock_settings.return_value.sentry.profiles_sample_rate = 0.1
        mock_settings.return_value.sentry.send_default_pii = False
        mock_settings.return_value.environment.value = "testing"

        result = init_sentry()

        assert result is True
        mock_sdk_init.assert_called_once()

    @patch("utils.sentry_init.get_settings")
    @patch("sentry_sdk.init")
    def test_double_init_prevented(
        self,
        mock_sdk_init: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """二重初期化は防止される"""
        mock_settings.return_value.sentry.enabled = True
        mock_settings.return_value.sentry.dsn = SecretStr(
            "https://abc123@o456.ingest.us.sentry.io/789",
        )
        mock_settings.return_value.sentry.environment = "testing"
        mock_settings.return_value.sentry.traces_sample_rate = 0.1
        mock_settings.return_value.sentry.profiles_sample_rate = 0.1
        mock_settings.return_value.sentry.send_default_pii = False
        mock_settings.return_value.environment.value = "testing"

        # 1回目の初期化
        assert init_sentry() is True
        # 2回目の初期化（既に初期化済み）
        assert init_sentry() is True

        # sentry_sdk.initは1回のみ呼ばれる
        assert mock_sdk_init.call_count == 1


class TestSentryState:
    """Sentry状態管理のテスト"""

    def setup_method(self) -> None:
        """各テスト前に状態リセット"""
        reset_sentry_state()

    def teardown_method(self) -> None:
        """各テスト後に状態リセット"""
        reset_sentry_state()

    def test_is_initialized_default_false(self) -> None:
        """デフォルトでは未初期化"""
        assert is_sentry_initialized() is False

    def test_reset_state_works(self) -> None:
        """状態リセットが機能する"""
        # 状態を手動で変更（通常は非推奨だが、テスト用）
        import utils.sentry_init as sentry_module

        sentry_module._sentry_initialized = True
        assert is_sentry_initialized() is True

        reset_sentry_state()
        assert is_sentry_initialized() is False

    @patch("utils.sentry_init.get_settings")
    @patch("sentry_sdk.init")
    def test_state_persists_after_init(
        self,
        mock_sdk_init: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """初期化後は状態が維持される"""
        mock_settings.return_value.sentry.enabled = True
        mock_settings.return_value.sentry.dsn = SecretStr(
            "https://abc123@o456.ingest.us.sentry.io/789",
        )
        mock_settings.return_value.sentry.environment = "testing"
        mock_settings.return_value.sentry.traces_sample_rate = 0.1
        mock_settings.return_value.sentry.profiles_sample_rate = 0.1
        mock_settings.return_value.sentry.send_default_pii = False
        mock_settings.return_value.environment.value = "testing"

        init_sentry()
        assert is_sentry_initialized() is True


class TestSentryDebugMode:
    """デバッグモード（SENTRY_DEBUG）のテスト"""

    def setup_method(self) -> None:
        """各テスト前に状態リセット"""
        reset_sentry_state()

    def teardown_method(self) -> None:
        """各テスト後に状態リセット"""
        reset_sentry_state()

    @patch.dict("os.environ", {"SENTRY_DEBUG": "true"})
    @patch("utils.sentry_init.get_settings")
    def test_invalid_dsn_warning_with_debug(self, mock_settings: MagicMock) -> None:
        """無効なDSNでSENTRY_DEBUG=trueの場合はSDK例外の警告が出る

        Note: DSN_PATTERN削除後、DSN検証はSDKに委任。
        SDKがBadDsn例外を投げると、except節でキャッチされ _logger.warning を出力。
        非本番環境のみ（本番環境ではRuntimeError発生）。
        warnings.warn → _logger.warning に変更（filterwarnings('error') 環境での DSN 漏洩防止）
        """
        # SENTRY_DEBUGを再読み込み（モジュールレベル変数）
        import utils.sentry_init as sentry_module

        sentry_module.SENTRY_DEBUG = True

        mock_settings.return_value.sentry.enabled = True
        mock_settings.return_value.sentry.dsn = SecretStr("invalid-dsn")
        mock_settings.return_value.is_production_like.return_value = False  # 非本番環境 (#39)

        with patch.object(sentry_module._logger, "warning") as mock_warn:
            result = init_sentry()

            assert result is False
            mock_warn.assert_called_once()
            call_kwargs = mock_warn.call_args
            # DSN検証はSDKに委任（BadDsn例外 → _logger.warning 出力）
            assert call_kwargs[0][0] == "sentry_init_failed"
            # BadDsn は sentry_sdk.utils に定義されている
            assert call_kwargs[1]["error_module"] == "sentry_sdk.utils"
            assert call_kwargs[1]["error_type"] == "BadDsn"

        # クリーンアップ
        sentry_module.SENTRY_DEBUG = False

    @patch("utils.sentry_init.get_settings")
    def test_invalid_dsn_no_warning_without_debug(self, mock_settings: MagicMock) -> None:
        """Invalid DSN always triggers _logger.warning regardless of SENTRY_DEBUG"""
        import utils.sentry_init as sentry_module

        sentry_module.SENTRY_DEBUG = False

        mock_settings.return_value.sentry.enabled = True
        mock_settings.return_value.sentry.dsn = SecretStr("invalid-dsn")
        mock_settings.return_value.is_production_like.return_value = False

        with patch.object(sentry_module._logger, "warning") as mock_warn:
            result = init_sentry()

            assert result is False
            mock_warn.assert_called_once_with(
                "sentry_init_failed",
                error_type="BadDsn",
                error_module="sentry_sdk.utils",
            )


class TestSdkExceptionHandling:
    """SDK例外ハンドリングのテスト（C-04）"""

    def setup_method(self) -> None:
        """各テスト前に状態リセット"""
        reset_sentry_state()

    def teardown_method(self) -> None:
        """各テスト後に状態リセット"""
        reset_sentry_state()

    @patch("utils.sentry_init.get_settings")
    @patch("sentry_sdk.init", side_effect=RuntimeError("SDK init failed"))
    def test_sdk_init_exception_returns_false(
        self,
        mock_sdk_init: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """sentry_sdk.init()が例外を投げた場合、非本番環境ではFalseを返す"""
        mock_settings.return_value.sentry.enabled = True
        mock_settings.return_value.sentry.dsn = SecretStr(
            "https://abc123@o456.ingest.us.sentry.io/789",
        )
        mock_settings.return_value.sentry.environment = "testing"
        mock_settings.return_value.sentry.traces_sample_rate = 0.1
        mock_settings.return_value.sentry.profiles_sample_rate = 0.1
        mock_settings.return_value.sentry.send_default_pii = False
        mock_settings.return_value.environment.value = "testing"
        mock_settings.return_value.is_production_like.return_value = False  # 非本番環境 (#39)

        result = init_sentry()

        assert result is False
        assert is_sentry_initialized() is False
        mock_sdk_init.assert_called_once()

    @patch("utils.sentry_init.get_settings")
    @patch("sentry_sdk.init", side_effect=ValueError("Invalid configuration"))
    def test_sdk_init_value_error_returns_false(
        self,
        mock_sdk_init: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """sentry_sdk.init()がValueErrorを投げた場合、非本番環境ではFalseを返す"""
        mock_settings.return_value.sentry.enabled = True
        mock_settings.return_value.sentry.dsn = SecretStr(
            "https://abc123@o456.ingest.us.sentry.io/789",
        )
        mock_settings.return_value.sentry.environment = "testing"
        mock_settings.return_value.sentry.traces_sample_rate = 0.1
        mock_settings.return_value.sentry.profiles_sample_rate = 0.1
        mock_settings.return_value.sentry.send_default_pii = False
        mock_settings.return_value.environment.value = "testing"
        mock_settings.return_value.is_production_like.return_value = False  # 非本番環境 (#39)

        result = init_sentry()

        assert result is False
        assert is_sentry_initialized() is False

    @patch.dict("os.environ", {"SENTRY_DEBUG": "true"})
    @patch("utils.sentry_init.get_settings")
    @patch("sentry_sdk.init", side_effect=ConnectionError("Network error"))
    def test_sdk_init_exception_warning_with_debug(
        self,
        mock_sdk_init: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """SDK例外時にSENTRY_DEBUG=trueなら _logger.warning が出る（非本番環境）
        warnings.warn → _logger.warning に変更（filterwarnings('error') 環境での DSN 漏洩防止）
        """
        import utils.sentry_init as sentry_module

        sentry_module.SENTRY_DEBUG = True

        mock_settings.return_value.sentry.enabled = True
        mock_settings.return_value.sentry.dsn = SecretStr(
            "https://abc123@o456.ingest.us.sentry.io/789",
        )
        mock_settings.return_value.sentry.environment = "testing"
        mock_settings.return_value.sentry.traces_sample_rate = 0.1
        mock_settings.return_value.sentry.profiles_sample_rate = 0.1
        mock_settings.return_value.sentry.send_default_pii = False
        mock_settings.return_value.environment.value = "testing"
        mock_settings.return_value.is_production_like.return_value = False  # 非本番環境 (#39)

        with patch.object(sentry_module._logger, "warning") as mock_warn:
            result = init_sentry()

            assert result is False
            mock_warn.assert_called_once()
            call_kwargs = mock_warn.call_args
            # error_type に例外クラス名が含まれる（DSN 値は含まない）
            assert call_kwargs[0][0] == "sentry_init_failed"
            assert call_kwargs[1]["error_type"] == "ConnectionError"
            assert call_kwargs[1]["error_module"] == "builtins"

        sentry_module.SENTRY_DEBUG = False

    @patch("utils.sentry_init.get_settings")
    @patch("sentry_sdk.init", side_effect=ValueError("Invalid configuration"))
    def test_sdk_init_exception_raises_in_production(
        self,
        mock_sdk_init: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """本番環境でSDK例外が発生した場合はRuntimeErrorを発生させる

        Security Rationale:
            本番環境でSentry初期化失敗を黙って無視すると、
            エラー監視が機能しない状態で運用が続行される。
            Fail-Fast原則により、明示的に失敗させる。
        """
        mock_settings.return_value.sentry.enabled = True
        mock_settings.return_value.sentry.dsn = SecretStr(
            "https://abc123@o456.ingest.us.sentry.io/789",
        )
        mock_settings.return_value.sentry.environment = "production"
        mock_settings.return_value.sentry.traces_sample_rate = 0.1
        mock_settings.return_value.sentry.profiles_sample_rate = 0.1
        mock_settings.return_value.sentry.send_default_pii = False
        mock_settings.return_value.environment.value = "production"
        mock_settings.return_value.is_production_like.return_value = True  # 本番環境 (#39)

        with pytest.raises(RuntimeError) as exc_info:
            init_sentry()

        assert "Sentry initialization failed in production" in str(exc_info.value)
        assert "ValueError" in str(exc_info.value)
        assert is_sentry_initialized() is False

    @patch("utils.sentry_init.get_settings")
    @patch("sentry_sdk.init", side_effect=RuntimeError("SDK init failed"))
    def test_init_sentry_logger_failure_falls_back_to_stderr(
        self,
        mock_sdk_init: MagicMock,
        mock_settings: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """非本番環境でSDK初期化失敗後、_logger.warning自体が例外を出した場合にstderrへフォールバックする"""
        # 非本番環境・有効なDSN設定で except Exception 経路に誘導
        mock_settings.return_value.sentry.enabled = True
        mock_settings.return_value.sentry.dsn = SecretStr(
            "https://abc123@o456.ingest.us.sentry.io/789",
        )
        mock_settings.return_value.sentry.environment = "testing"
        mock_settings.return_value.sentry.traces_sample_rate = 0.1
        mock_settings.return_value.sentry.profiles_sample_rate = 0.1
        mock_settings.return_value.sentry.send_default_pii = False
        mock_settings.return_value.environment.value = "testing"
        mock_settings.return_value.is_production_like.return_value = False  # 非本番環境

        import utils.sentry_init as sentry_module

        # _logger.warning が例外を出すことでstderrフォールバック経路を強制
        with patch.object(
            sentry_module._logger,
            "warning",
            side_effect=RuntimeError("logger broken"),
        ):
            result = init_sentry()

        assert result is False
        captured = capsys.readouterr()
        assert "[SENTRY_WARN]" in captured.err
        assert "sentry_init_failed" in captured.err
        assert "original_error_type=RuntimeError" in captured.err
        assert "original_error_module=builtins" in captured.err
        assert "logger_error_type=RuntimeError" in captured.err

    @patch("utils.sentry_init.get_settings")
    def test_import_error_raises_in_production(self, mock_settings: MagicMock) -> None:
        """本番環境でsentry-sdk未インストールの場合はRuntimeErrorを発生させる

        Security Rationale:
            本番環境でSentry SDKがインストールされていないと、
            エラー監視が完全に無効化される。依存関係漏れの早期検出のため、
            Fail-Fast原則により明示的に失敗させる。
        """
        mock_settings.return_value.sentry.enabled = True
        mock_settings.return_value.sentry.dsn = SecretStr(
            "https://abc123@o456.ingest.us.sentry.io/789",
        )
        mock_settings.return_value.sentry.environment = "production"
        mock_settings.return_value.is_production_like.return_value = True  # 本番環境 (#39)

        # sentry_sdkのimportをモックしてImportErrorを発生させる
        import builtins

        original_import = builtins.__import__

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "sentry_sdk":
                raise ImportError("No module named 'sentry_sdk'")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            with pytest.raises(RuntimeError) as exc_info:
                init_sentry()

        assert "Sentry SDK not installed in production" in str(exc_info.value)
        assert "Add 'sentry-sdk' to dependencies" in str(exc_info.value)
        assert is_sentry_initialized() is False

    @patch("utils.sentry_init.get_settings")
    def test_import_error_returns_false_in_dev(self, mock_settings: MagicMock) -> None:
        """開発環境でsentry-sdk未インストールの場合はFalseを返す"""
        mock_settings.return_value.sentry.enabled = True
        mock_settings.return_value.sentry.dsn = SecretStr(
            "https://abc123@o456.ingest.us.sentry.io/789",
        )
        mock_settings.return_value.sentry.environment = "development"
        mock_settings.return_value.is_production_like.return_value = False  # 開発環境 (#39)

        # sentry_sdkのimportをモックしてImportErrorを発生させる
        import builtins

        original_import = builtins.__import__

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "sentry_sdk":
                raise ImportError("No module named 'sentry_sdk'")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            result = init_sentry()

        assert result is False
        assert is_sentry_initialized() is False

    @patch("utils.sentry_init.get_settings")
    def test_import_error_logger_failure_falls_back_with_original_error(
        self,
        mock_settings: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """ImportError 経路の stderr fallback に元例外型を含める。"""
        mock_settings.return_value.sentry.enabled = True
        mock_settings.return_value.sentry.dsn = SecretStr(
            "https://abc123@o456.ingest.us.sentry.io/789",
        )
        mock_settings.return_value.sentry.environment = "development"
        mock_settings.return_value.is_production_like.return_value = False

        import builtins

        original_import = builtins.__import__

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "sentry_sdk":
                raise ImportError("No module named 'sentry_sdk'")
            return original_import(name, *args, **kwargs)

        with (
            patch.object(builtins, "__import__", side_effect=mock_import),
            patch.object(
                sentry_module._logger,
                "warning",
                side_effect=RuntimeError("logger broken"),
            ),
        ):
            result = init_sentry()

        assert result is False
        captured = capsys.readouterr()
        assert "sentry_sdk_not_installed" in captured.err
        assert "original_error_type=ImportError" in captured.err
        assert "original_error_module=builtins" in captured.err
        assert "logger_error_type=RuntimeError" in captured.err


class TestSentryProcessorBeforeSendChain:
    """logger._sentry_processor → sentry_init._before_send PII フィルター連鎖テスト

    _sentry_processor は scope.set_extra() で extra フィールドを設定し、
    Sentry SDK は _before_send フックを介してイベントを送信する。
    このクラスは extra 経由の PII が _before_send で正しく除去されることを検証する。
    """

    def test_sensitive_extra_keys_are_redacted(self) -> None:
        """email/password 等の機密フィールドが [REDACTED] に置換される"""
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
        """機密キー以外の extra フィールドはそのまま保持される"""
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
        """複数の機密キーが同時に存在する場合、全て [REDACTED] になる"""
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
        """user/contexts 内の機密フィールドも _before_send で除去される"""
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
    """_INTERNAL_TAG_VALUE が secrets.token_hex(16) で生成された有効な32文字 hex か検証（PR#347）"""
    import re

    from utils.sentry_init import _INTERNAL_TAG_VALUE

    assert re.fullmatch(r"[0-9a-f]{32}", _INTERNAL_TAG_VALUE) is not None
    assert len(_INTERNAL_TAG_VALUE) <= 200  # Sentry SDK tag value 上限 200文字以内


class TestSafeLogWarning:
    """_safe_log_warning のエラーハンドリングテスト (#11-B-5 / #13-TC-2 / #14)"""

    def test_recursion_error_is_reraised(self) -> None:
        """RecursionError は fail-fast で再 raise される。"""
        with patch.object(sentry_module._logger, "warning", side_effect=RecursionError()):
            with pytest.raises(RecursionError):
                sentry_module._safe_log_warning("test_event")

    def test_memory_error_is_reraised(self) -> None:
        """MemoryError は fail-fast で再 raise される。"""
        with patch.object(sentry_module._logger, "warning", side_effect=MemoryError()):
            with pytest.raises(MemoryError):
                sentry_module._safe_log_warning("test_event")

    def test_regular_exception_is_suppressed_with_stderr_fallback(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """RuntimeError 等の通常例外は抑止され、stderr にフォールバック出力される。"""
        with patch.object(sentry_module._logger, "warning", side_effect=RuntimeError("log fail")):
            # raise されない（fail-open）
            sentry_module._safe_log_warning("test_event")
        captured = capsys.readouterr()
        assert "_safe_log_warning failed" in captured.err
        assert "RuntimeError" in captured.err


class TestScrubUrlIpv6:
    """_scrub_url IPv6 関連テスト (#12-Q-10)"""

    def test_scrub_url_handles_ipv6_without_port(self) -> None:
        """IPv6 アドレス（ポートなし）を含む URL でも例外を出さず token をスクラブする。"""
        url = "http://[::1]/path?token=abc"
        result = _scrub_url(url)
        assert "[::1]" in result  # netloc 保持
        assert "abc" not in result  # token 値スクラブ済み


class TestIsSensitiveKeyPatternContract:
    """_SENSITIVE_KEY_PATTERN / _is_sensitive_key の仕様契約テスト (#13-GC-2)"""

    def test_is_sensitive_key_token_standalone_not_matched_by_pattern(self) -> None:
        """ "token" 単独は _SENSITIVE_KEY_PATTERN の suffix lookahead で非一致。
        ただし _COMPACT_SENSITIVE_KEYS の完全一致 fallback で True になる（設計意図）。
        """
        # compact fallback により True — パターン非一致だが compact 一致
        assert _is_sensitive_key("token") is True

    def test_is_sensitive_key_access_token_matched(self) -> None:
        """ "access_token" は _SENSITIVE_KEY_PATTERN の単語境界で一致する。"""
        assert _is_sensitive_key("access_token") is True
