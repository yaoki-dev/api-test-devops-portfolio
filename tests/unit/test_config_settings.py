import logging
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from config.settings import (
    APIConfig,
    Environment,
    LogConfig,
    LogLevel,
    SecurityConfig,
    SentryConfig,
    Settings,
    TestConfig,
    get_settings,
    reload_settings,
)

# Module-level marker: All tests in this file are unit tests
pytestmark = pytest.mark.unit


class TestAPIConfigBoundaryValues:
    """APIConfig数値フィールドの境界値テスト（P1-Critical）

    Pydantic Fieldのge/le制約を検証:
    - timeout: ge=1.0, le=300.0
    - retry_count: ge=0, le=10
    - retry_delay: ge=0.1, le=60.0
    """

    @pytest.mark.parametrize(
        ("field", "value", "should_pass"),
        [
            # timeout: ge=1.0, le=300.0
            pytest.param("timeout", 0.9, False, id="timeout_below_min"),
            pytest.param("timeout", 1.0, True, id="timeout_at_min"),
            pytest.param("timeout", 300.0, True, id="timeout_at_max"),
            pytest.param("timeout", 300.1, False, id="timeout_above_max"),
            # retry_count: ge=0, le=10
            pytest.param("retry_count", -1, False, id="retry_count_below_min"),
            pytest.param("retry_count", 0, True, id="retry_count_at_min"),
            pytest.param("retry_count", 10, True, id="retry_count_at_max"),
            pytest.param("retry_count", 11, False, id="retry_count_above_max"),
            # retry_delay: ge=0.1, le=60.0
            pytest.param("retry_delay", 0.09, False, id="retry_delay_below_min"),
            pytest.param("retry_delay", 0.1, True, id="retry_delay_at_min"),
            pytest.param("retry_delay", 60.0, True, id="retry_delay_at_max"),
            pytest.param("retry_delay", 60.1, False, id="retry_delay_above_max"),
        ],
    )
    def test_numeric_field_boundaries(
        self, field: str, value: int | float, should_pass: bool
    ) -> None:
        """数値フィールドの境界値検証

        Note:
            動的kwargs展開のため type: ignore を使用。
            parametrizedテストの設計上、静的型チェックの限界。
        """
        if should_pass:
            config = APIConfig(**{field: value})  # type: ignore[arg-type]
            assert getattr(config, field) == value
        else:
            with pytest.raises(ValidationError):
                APIConfig(**{field: value})  # type: ignore[arg-type]


class TestAPIConfigValidation:
    """APIConfig.validate_base_url のテスト (lines 73-77)"""

    def test_base_url_without_scheme_raises_error(self):
        """スキーム(http/https)なしのURLでエラー発生"""
        with pytest.raises(ValidationError) as exc_info:
            APIConfig(base_url="example.com")
        assert "Base URL must start with http:// or https://" in str(exc_info.value)

    def test_base_url_with_ftp_scheme_raises_error(self):
        """ftp://スキームでエラー発生"""
        with pytest.raises(ValidationError) as exc_info:
            APIConfig(base_url="ftp://example.com")
        assert "Base URL must start with http:// or https://" in str(exc_info.value)

    def test_base_url_with_trailing_slash_removed(self):
        """末尾のスラッシュが削除される (line 76-77)"""
        config = APIConfig(base_url="https://example.com/")
        assert config.base_url == "https://example.com"
        assert not config.base_url.endswith("/")

    def test_base_url_with_multiple_trailing_slashes_removed(self):
        """複数の末尾スラッシュが削除される"""
        config = APIConfig(base_url="https://example.com///")
        assert config.base_url == "https://example.com"

    def test_base_url_http_scheme_valid(self):
        """http://スキームが有効（SSRF対応: 許可ドメインを使用）"""
        config = APIConfig(base_url="http://httpbin.org")
        assert config.base_url == "http://httpbin.org"

    @pytest.mark.smoke
    def test_base_url_https_scheme_valid(self):
        """https://スキームが有効"""
        config = APIConfig(base_url="https://api.example.com")
        assert config.base_url == "https://api.example.com"


class TestLogConfigValidation:
    """LogConfig.validate_log_file のテスト (lines 105-109)"""

    def test_log_file_none_handling(self):
        """file=None の場合の処理 (line 105)"""
        config = LogConfig(file=None)
        assert config.file is None

    def test_log_file_directory_creation(self, tmp_path: Path) -> None:
        """存在しないディレクトリが自動作成される (lines 106-108)"""
        log_file = tmp_path / "logs" / "subdir" / "app.log"
        assert not log_file.parent.exists()

        _ = LogConfig(file=str(log_file))  # noqa: F841 - ディレクトリ作成の副作用をテスト

        # ディレクトリが作成されたことを確認
        assert log_file.parent.exists()
        assert log_file.parent.is_dir()

    def test_log_file_existing_directory(self, tmp_path: Path) -> None:
        """既存ディレクトリの場合もエラーなし"""
        log_dir = tmp_path / "existing_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "app.log"

        config = LogConfig(file=str(log_file))
        assert config.file == str(log_file)

    def test_log_file_deep_nested_directory_creation(self, tmp_path: Path) -> None:
        """深くネストされたディレクトリの作成"""
        log_file = tmp_path / "a" / "b" / "c" / "d" / "app.log"
        _ = LogConfig(file=str(log_file))  # noqa: F841 - ディレクトリ作成の副作用をテスト
        assert log_file.parent.exists()


class TestSettingsEnvironmentValidation:
    """Settings.validate_environment のテスト (lines 192-194)"""

    @pytest.mark.parametrize(
        ("env_input", "expected", "needs_secret"),
        [
            pytest.param("PRODUCTION", Environment.PRODUCTION, True, id="uppercase"),
            pytest.param("DeVeLoPmEnT", Environment.DEVELOPMENT, False, id="mixed_case"),
            pytest.param(Environment.TESTING, Environment.TESTING, False, id="enum_direct"),
            pytest.param("staging", Environment.STAGING, False, id="lowercase"),
        ],
    )
    def test_environment_validation(
        self, env_input: str | Environment, expected: Environment, needs_secret: bool
    ) -> None:
        """環境設定バリデーション: 文字列→小文字変換、Enum直接指定

        Note:
            Pydantic field_validatorが実行時に文字列→Enum変換を行うため、
            str | Environment を受け入れる。静的型チェックとの差異あり。
        """
        if needs_secret:
            settings = Settings(
                environment=env_input,  # type: ignore[arg-type]
                security=SecurityConfig(api_key=SecretStr("test-key")),  # noqa: S106
            )
        else:
            settings = Settings(environment=env_input)  # type: ignore[arg-type]
        assert settings.environment == expected


class TestSettingsEnvironmentMethods:
    """Settings環境判定メソッドのテスト (lines 198, 202, 206, 210)"""

    def test_is_development_true(self):
        """is_development() がTrueを返す (line 198)"""
        settings = Settings(environment=Environment.DEVELOPMENT)
        assert settings.is_development() is True

    def test_is_testing_true(self):
        """is_testing() がTrueを返す (line 202)"""
        settings = Settings(environment=Environment.TESTING)
        assert settings.is_testing() is True

    def test_is_production_true(self):
        """is_production() がTrueを返す (line 206)"""
        # 本番環境ではシークレットが必須
        settings = Settings(
            environment=Environment.PRODUCTION,
            security=SecurityConfig(api_key=SecretStr("test-key")),  # noqa: S106
        )
        assert settings.is_production() is True

    @pytest.mark.parametrize(
        ("log_level", "expected"),
        [
            pytest.param(LogLevel.DEBUG, logging.DEBUG, id="debug"),
            pytest.param(LogLevel.INFO, logging.INFO, id="info"),
            pytest.param(LogLevel.WARNING, logging.WARNING, id="warning"),
            pytest.param(LogLevel.ERROR, logging.ERROR, id="error"),
            pytest.param(LogLevel.CRITICAL, logging.CRITICAL, id="critical"),
        ],
    )
    def test_get_log_level_mapping(self, log_level: LogLevel, expected: int) -> None:
        """get_log_level() がLogLevel Enumを正しくlogging定数にマッピング"""
        settings = Settings()
        settings.log.level = log_level
        assert settings.get_log_level() == expected


class TestProductionSecretValidation:
    """本番環境でのシークレット検証テスト"""

    def test_production_without_secrets_raises_error(self):
        """本番環境でシークレット未設定時にエラー"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(environment=Environment.PRODUCTION)
        assert "SECURITY__API_KEY or SECURITY__JWT_SECRET" in str(exc_info.value)

    def test_production_with_api_key_valid(self):
        """本番環境でapi_key設定時は有効"""
        settings = Settings(
            environment=Environment.PRODUCTION,
            security=SecurityConfig(api_key=SecretStr("test-key")),  # noqa: S106
        )
        assert settings.is_production() is True

    def test_production_with_jwt_secret_valid(self):
        """本番環境でjwt_secret設定時は有効"""
        settings = Settings(
            environment=Environment.PRODUCTION,
            security=SecurityConfig(jwt_secret=SecretStr("test-secret")),  # noqa: S106
        )
        assert settings.is_production() is True

    def test_development_without_secrets_valid(self):
        """開発環境ではシークレット不要"""
        settings = Settings(environment=Environment.DEVELOPMENT)
        assert settings.is_development() is True


class TestSettingsSecretMasking:
    """Settings.to_dict() のシークレットマスキングテスト (lines 214-225)"""

    def test_to_dict_with_secret_masking_enabled(self):
        """exclude_secrets=True でシークレットがマスクされる (lines 217-223)"""
        settings = Settings()
        # テスト専用ダミー値（本番では使用されない）
        settings.security.api_key = SecretStr("test-api-key-12345")  # noqa: S105
        settings.security.jwt_secret = SecretStr("test-jwt-secret-67890")  # noqa: S105

        result = settings.to_dict(exclude_secrets=True)

        assert result["security"]["api_key"] == "***MASKED***"
        assert result["security"]["jwt_secret"] == "***MASKED***"  # noqa: S105 - テスト用マスク文字列

    def test_to_dict_with_secret_masking_disabled(self):
        """exclude_secrets=False でシークレットがそのまま出力される (line 216)"""
        settings = Settings()
        # テスト専用ダミー値（本番では使用されない）
        settings.security.api_key = SecretStr("test-api-key-12345")  # noqa: S105
        settings.security.jwt_secret = SecretStr("test-jwt-secret-67890")  # noqa: S105

        result = settings.to_dict(exclude_secrets=False)

        # SecretStrの値は.get_secret_value()で取得できるが、model_dump()では文字列として出力される
        # Pydanticの動作により、SecretStrは文字列として出力される
        assert "api_key" in result["security"]
        assert "jwt_secret" in result["security"]

    def test_to_dict_model_dump_called(self):
        """model_dump() が呼び出される (line 215)"""
        settings = Settings()
        result = settings.to_dict()

        # 基本的な構造が辞書として存在することを確認
        assert isinstance(result, dict)
        assert "environment" in result
        assert "api" in result
        assert "log" in result
        assert "test" in result
        assert "security" in result

    def test_to_dict_api_key_none_not_masked(self):
        """api_keyがNoneの場合はマスク処理がスキップされる (line 220)"""
        settings = Settings()
        settings.security.api_key = None

        result = settings.to_dict(exclude_secrets=True)

        # Noneの場合はマスクされない（line 220のif条件）
        assert result["security"]["api_key"] is None

    def test_to_dict_jwt_secret_none_not_masked(self):
        """jwt_secretがNoneの場合はマスク処理がスキップされる (line 222)"""
        settings = Settings()
        settings.security.jwt_secret = None

        result = settings.to_dict(exclude_secrets=True)

        assert result["security"]["jwt_secret"] is None

    def test_to_dict_sentry_dsn_masked(self):
        """Sentry DSN設定時にマスクされる (lines 385-389)"""
        from pydantic import SecretStr

        settings = Settings()
        settings.sentry = SentryConfig(
            dsn=SecretStr("https://abc123@o456.ingest.sentry.io/789")  # noqa: S106
        )

        result = settings.to_dict(exclude_secrets=True)

        assert result["sentry"]["dsn"] == "***MASKED***"

    def test_to_dict_sentry_dsn_empty_also_masked(self):
        """空DSNもマスクされる（model_dump後は文字列として扱われる）"""
        settings = Settings()
        # デフォルトは空SecretStr、model_dump()後は'**********'文字列

        result = settings.to_dict(exclude_secrets=True)

        # model_dump()後のSecretStrは文字列として扱われ、マスクされる
        assert result["sentry"]["dsn"] == "***MASKED***"

    def test_sentry_config_default_factory(self):
        """SentryConfigがdefault_factoryで作成される"""
        settings = Settings()

        assert isinstance(settings.sentry, SentryConfig)
        assert settings.sentry.enabled is False
        assert settings.sentry.traces_sample_rate == 0.1


class TestSettingsSingleton:
    """シングルトンパターンのテスト (lines 239-248)"""

    @pytest.fixture(autouse=True)
    def reset_singleton(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """各テスト前にシングルトンをリセット（DRY改善）"""
        import config.settings

        monkeypatch.setattr(config.settings, "_settings", None)

    def test_get_settings_creates_instance_first_time(self) -> None:
        """get_settings() が初回呼び出しで新インスタンスを作成 (lines 239-241)"""
        settings1 = get_settings()
        assert settings1 is not None
        assert isinstance(settings1, Settings)

    def test_get_settings_returns_same_instance(self) -> None:
        """get_settings() が2回目以降は同じインスタンスを返す"""
        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_reload_settings_creates_new_instance(self) -> None:
        """reload_settings() が新しいインスタンスを作成 (lines 247-248)"""
        settings1 = get_settings()
        settings2 = reload_settings()

        # 新しいインスタンスが作成される
        assert settings1 is not settings2
        assert isinstance(settings2, Settings)

    def test_reload_settings_updates_global_variable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """reload_settings() がグローバル変数を更新 (line 247)"""
        # 最初のインスタンス作成
        settings1 = get_settings()
        _ = settings1.project_name  # noqa: F841 - 元の値を確認（後で検証に使用）

        # 環境変数を変更してreload
        monkeypatch.setenv("PROJECT_NAME", "New Project Name")
        settings2 = reload_settings()

        # 新しいインスタンスが環境変数を読み込んでいることを確認
        # ※ただし、Pydanticは初期化時に環境変数を読むため、
        # 実際には新しいSettingsインスタンスが作成されていることを確認
        assert settings2 is not settings1

        # get_settings()が新しいインスタンスを返すことを確認
        settings3 = get_settings()
        assert settings3 is settings2


class TestNestedConfigDefaults:
    """ネスト設定のデフォルトファクトリーテスト"""

    @pytest.mark.parametrize(
        ("attr", "expected_type"),
        [
            pytest.param("api", APIConfig, id="api_config"),
            pytest.param("log", LogConfig, id="log_config"),
            pytest.param("test", TestConfig, id="test_config"),
            pytest.param("security", SecurityConfig, id="security_config"),
        ],
    )
    def test_nested_config_type(self, attr: str, expected_type: type) -> None:
        """各サブ設定がdefault_factoryで正しい型として初期化される"""
        settings = Settings()
        assert isinstance(getattr(settings, attr), expected_type)


class TestEnvironmentVariableLoading:
    """環境変数からの設定読み込みテスト"""

    def test_nested_environment_variable_loading(self, monkeypatch):
        """ネスト記法（API__BASE_URL）での環境変数読み込み"""
        monkeypatch.setenv("API__BASE_URL", "https://test-api.example.com")
        monkeypatch.delattr("config.settings._settings", raising=False)

        settings = reload_settings()
        assert settings.api.base_url == "https://test-api.example.com"

    def test_case_insensitive_environment_variables(self, monkeypatch):
        """大小文字を区別しない環境変数読み込み (case_sensitive=False)"""
        monkeypatch.setenv("project_name", "Test Project")
        monkeypatch.delattr("config.settings._settings", raising=False)

        settings = reload_settings()
        assert settings.project_name == "Test Project"

    def test_debug_mode_from_environment(self, monkeypatch):
        """DEBUG環境変数からのdebugモード設定"""
        monkeypatch.setenv("DEBUG", "false")
        monkeypatch.delattr("config.settings._settings", raising=False)

        settings = reload_settings()
        assert settings.debug is False
