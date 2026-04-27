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

from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr
from sentry_sdk.types import Event

from utils.sentry_init import (
    MAX_SCRUB_DEPTH,
    SENSITIVE_KEYS,
    _before_send,
    _scrub_sensitive_data,
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
        """31種類の機密キーが定義されている（body_preview追加後）"""
        assert len(SENSITIVE_KEYS) == 31

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
            "database_url",
            "ssn",
            "credit_card",
            "cvv",
            "card_number",
            # HTTPレスポンスプレビュー
            "body_preview",
        ],
    )
    def test_expected_keys_present(self, key: str) -> None:
        """期待される機密キーが含まれている"""
        assert key in SENSITIVE_KEYS


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

    def test_returns_event(self) -> None:
        """イベントオブジェクトを返す（Noneではない）"""
        event = cast(Event, {"message": "test"})
        result_dict = self._call_before_send(event)
        assert result_dict["message"] == "test"


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
        SDKがBadDsn例外を投げると、except節でキャッチされ警告出力。
        非本番環境のみ（本番環境ではRuntimeError発生）。
        """
        # SENTRY_DEBUGを再読み込み（モジュールレベル変数）
        import utils.sentry_init as sentry_module

        sentry_module.SENTRY_DEBUG = True

        mock_settings.return_value.sentry.enabled = True
        mock_settings.return_value.sentry.dsn = SecretStr("invalid-dsn")
        mock_settings.return_value.is_production_like.return_value = False  # 非本番環境 (#39)

        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = init_sentry()

            assert result is False
            assert len(w) == 1
            # DSN検証はSDKに委任（BadDsn例外 → 警告出力）
            assert "Sentry initialization failed" in str(w[0].message)
            assert w[0].category is UserWarning

        # クリーンアップ
        sentry_module.SENTRY_DEBUG = False

    @patch("utils.sentry_init.get_settings")
    def test_invalid_dsn_no_warning_without_debug(self, mock_settings: MagicMock) -> None:
        """無効なDSNでSENTRY_DEBUG=falseの場合は警告なし（非本番環境）"""
        import utils.sentry_init as sentry_module

        sentry_module.SENTRY_DEBUG = False

        mock_settings.return_value.sentry.enabled = True
        mock_settings.return_value.sentry.dsn = SecretStr("invalid-dsn")
        mock_settings.return_value.is_production_like.return_value = False  # 非本番環境 (#39)

        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = init_sentry()

            assert result is False
            assert len(w) == 0  # 警告なし


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
        """SDK例外時にSENTRY_DEBUG=trueなら警告が出る（非本番環境）"""
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

        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = init_sentry()

            assert result is False
            assert len(w) == 1
            assert "Sentry initialization failed" in str(w[0].message)
            assert "ConnectionError" in str(w[0].message)

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
