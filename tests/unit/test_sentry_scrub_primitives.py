"""スクラブ基盤（primitives）のテスト

機密キー判定（SENSITIVE_KEYS / _is_sensitive_key）とログ基盤ヘルパー
（_safe_log_warning）をカバー。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

import utils.sentry_init as sentry_module
from utils.sentry_init import (
    SENSITIVE_KEYS,
    _is_sensitive_key,
    _scrub_sensitive_data,
)

pytestmark = pytest.mark.unit


class TestSensitiveKeysCompleteness:
    """SENSITIVE_KEYSの網羅性テスト"""

    def test_sensitive_keys_is_frozenset(self) -> None:
        assert isinstance(SENSITIVE_KEYS, frozenset)

    def test_sensitive_keys_count(self) -> None:
        """機密キーが44個定義されていることを検証するセンチネルテスト

        Note:
        件数のハードコードは意図的であり、SENSITIVE_KEYS への意図しない
        キーの追加・削除を検知するセンチネルとして機能する。
        キーを追加・削除する場合は、このテストの件数も更新する。
        """
        assert len(SENSITIVE_KEYS) == 44  # SENSITIVE_KEYS 変更時はここの数値も更新

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
            "username",
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
            # 複合語バリアント (単語境界検出のfalse negative補完)
            "authtoken",
            "usertoken",
            "userpassword",
        ],
    )
    def test_expected_keys_present(self, key: str) -> None:
        assert key in SENSITIVE_KEYS

    def test_sensitive_key_match_uses_word_boundaries_with_hyphen_normalization(self) -> None:
        """機密キー判定は単語境界一致 + ハイフン/アンダースコア正規化

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
        """composite key (接頭辞/接尾辞付き) の PII regression 回帰防止テスト

        `_is_sensitive_key` を完全一致(exact)に変更した際に、
        複合キーが漏洩したリグレッションを防止。
        安全な判定ロジック（部分一致等）が変更され、脆弱性が再発しないことを担保するゲートテスト"""
        result = _scrub_sensitive_data({composite_key: "leak-me"})
        assert result[composite_key] == "[REDACTED]", (
            f"composite key '{composite_key}' must be redacted to prevent PII regression"
        )

    @pytest.mark.parametrize(
        "known_false_negative",
        [
            "foopassword",
            "mypassword",
            "oldpassword",
            "ssnumber",
            "cvvcode",
        ],
    )
    def test_sensitive_key_false_negatives_documented(self, known_false_negative: str) -> None:
        """単語境界設計の既知 false negative を契約化する。

        substring 一致へ戻すと `prototype` / `photo_url` 等の false positive が再発するため、
        連結語の頻出パターンは SENSITIVE_KEYS へ明示追加する方針を維持する。
        """
        assert _is_sensitive_key(known_false_negative) is False

    @pytest.mark.parametrize(
        ("key", "expected"),
        [
            # True positives: 短縮語そのもの → True
            ("otp", True),
            ("mfa", True),
            ("totp", True),
            # prefix/suffix 非対称設計の契約化
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
        "key",
        [
            "username",
            "user_name",
            "get_username",
            "username_hash",
            "display_username",
        ],
    )
    def test_username_variants_over_redacted(self, key: str) -> None:
        """username を含むキーは意図的に over-redact される。

        `user_id` (False) と異なり、`username` は SENSITIVE_KEYS に含まれるため、
        派生キー (get_username / username_hash / display_username 等) も True になる。
        セキュリティ観点では過剰 redact は漏洩より低リスクであり、この意図的な
        over-redact 挙動を契約テストとして固定する（実挙動を empirical に確認済み）。
        """
        assert _is_sensitive_key(key) is True

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
        camelCase PII バイパス修正の回帰テスト
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
        r"""数字プレフィックス/サフィックスを単語境界として扱う回帰テスト

        `_SENSITIVE_KEY_PATTERN` の数字境界を拡張。
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
            ("SECRET", True),  # secret compact = secret
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
        全大文字 PII バイパス修正の回帰テスト
        """
        assert _is_sensitive_key(key) is expected


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

    def test_stderr_fallback_exception_is_fully_suppressed(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """logger.warning 失敗かつ stderr (print) も失敗する二重障害パスで例外が伝播しない。"""
        with (
            patch.object(sentry_module._logger, "warning", side_effect=RuntimeError("log fail")),
            patch("builtins.print", side_effect=OSError("stderr closed")),
        ):
            sentry_module._safe_log_warning("test_event")  # 例外伝播しないことを確認
        assert capsys.readouterr().err == ""


class TestIsSensitiveKeyPatternContract:
    """_SENSITIVE_KEY_PATTERN / _is_sensitive_key の仕様契約テスト (#13-GC-2)"""

    def test_is_sensitive_key_token_standalone_not_matched_by_pattern(self) -> None:
        # compact fallback により True — パターン非一致だが compact 一致
        """ "token" 単独は _SENSITIVE_KEY_PATTERN の suffix lookahead で非一致。
        ただし _COMPACT_SENSITIVE_KEYS の完全一致 fallback で True になる（設計意図）。
        """
        assert _is_sensitive_key("token") is True

    def test_is_sensitive_key_access_token_matched(self) -> None:
        assert _is_sensitive_key("access_token") is True

    @pytest.mark.parametrize("key", ["authtoken", "usertoken", "userpassword"])
    def test_is_sensitive_key_registered_compound_variants_matched(self, key: str) -> None:
        """SENSITIVE_KEYS に明示登録した複合語バリアントは redact される (#4)。

        単語境界パターンの suffix lookahead では捕捉できない複合語を補完するため、
        頻出バリアントを SENSITIVE_KEYS に直接登録している。compact fallback
        （アンダースコア除去後の完全一致）で True になる契約を固定する。
        """
        assert _is_sensitive_key(key) is True

    @pytest.mark.parametrize(
        "key",
        ["myusertoken", "prefixauthtoken", "xusertoken", "xuserpassword"],
    )
    def test_is_sensitive_key_arbitrary_prefixed_keys_not_over_redacted(self, key: str) -> None:
        """任意の prefix を付けた非ヘッダーキーは過剰 redact しない（false positive 防止）。

        compact fallback は substring ではなく完全一致のため、`myusertoken` 等の
        セパレータなし複合語は SENSITIVE_KEYS に一致せず保持される。
        （注: `x-user-token` のようにハイフン/アンダースコア区切りで `token` 語を含む形式は
        単語境界マッチで redact される。ここで検証するのは区切りなしの任意複合語のみ。）
        これにより `_is_sensitive_key` が無関係なキーを巻き込んで過剰 redact する退行を検出する。
        """
        assert _is_sensitive_key(key) is False

    @pytest.mark.parametrize(
        "key",
        ["x-auth-token", "X-Auth-Token", "x-access-token", "x-csrf-token", "x-refresh-token"],
    )
    def test_is_sensitive_key_http_auth_header_variants_matched(self, key: str) -> None:
        """実在する `X-*` 認証系 HTTP ヘッダーは大小・ハイフン正規化後に redact される。

        SENSITIVE_KEYS には標準 HTTP 認証ヘッダーのみ登録する方針。これらが
        正規化（lower 化 + ハイフン→アンダースコア）後に確実に一致する契約を固定する。
        """
        assert _is_sensitive_key(key) is True
