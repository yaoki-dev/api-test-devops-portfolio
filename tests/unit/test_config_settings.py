import logging
from pathlib import Path
from typing import Any

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
    _validate_base_url_with_allowed_domains,
    get_settings,
    reload_settings,
)
from config.settings import (
    TestConfig as SettingsTestConfig,
)

# Module-level marker: All tests in this file are unit tests
pytestmark = pytest.mark.unit


class TestAPIConfigBaseUrlDependencyInjection:
    def test_validate_base_url_accepts_injected_allowed_domain(self) -> None:
        result = _validate_base_url_with_allowed_domains(
            "https://example.com/",
            frozenset({"example.com"}),
        )

        assert result == "https://example.com"

    def test_validate_base_url_rejects_domain_missing_from_injected_allowlist(self) -> None:
        with pytest.raises(ValueError, match="Domain not in allowlist"):
            _validate_base_url_with_allowed_domains(
                "https://evil.com",
                frozenset({"example.com"}),
            )

    def test_validate_base_url_rejects_missing_hostname(self) -> None:
        with pytest.raises(ValueError, match="Invalid URL: hostname not found"):
            _validate_base_url_with_allowed_domains(
                "https://",
                frozenset({"example.com"}),
            )

    def test_validate_base_url_allowlist_log_includes_operator_guidance(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="config.settings"):
            with pytest.raises(ValueError, match="Domain not in allowlist"):
                _validate_base_url_with_allowed_domains(
                    "https://evil.com",
                    frozenset({"example.com"}),
                )

        assert any(
            "Check ALLOWED_DOMAINS setting" in record.getMessage()
            and record.levelno == logging.WARNING
            for record in caplog.records
        )

    def test_validate_base_url_logs_warning_for_domain_not_in_allowlist(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="config.settings"):
            with pytest.raises(ValueError, match="Domain not in allowlist"):
                _validate_base_url_with_allowed_domains(
                    "https://evil.com", frozenset({"example.com"})
                )
        assert any(
            "SSRF Prevention: Domain not in allowlist" in record.getMessage()
            and record.levelno == logging.WARNING
            for record in caplog.records
        )


class TestAPIConfigBoundaryValues:
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
        self,
        field: str,
        value: float,
        should_pass: bool,
    ) -> None:
        if should_pass:
            config = APIConfig(**{field: value})  # type: ignore[arg-type]
            assert getattr(config, field) == value
        else:
            with pytest.raises(ValidationError):
                APIConfig(**{field: value})  # type: ignore[arg-type]


class TestAPIConfigValidation:
    def test_base_url_without_scheme_raises_error(self):
        with pytest.raises(ValidationError) as exc_info:
            APIConfig(base_url="example.com")
        assert "Base URL must start with http:// or https://" in str(exc_info.value)

    def test_base_url_with_ftp_scheme_raises_error(self):
        with pytest.raises(ValidationError) as exc_info:
            APIConfig(base_url="ftp://example.com")
        assert "Base URL must start with http:// or https://" in str(exc_info.value)

    def test_base_url_with_trailing_slash_removed(self):
        config = APIConfig(base_url="https://example.com/")
        assert config.base_url == "https://example.com"
        assert not config.base_url.endswith("/")

    def test_base_url_with_multiple_trailing_slashes_removed(self):
        config = APIConfig(base_url="https://example.com///")
        assert config.base_url == "https://example.com"

    def test_base_url_http_scheme_valid(self):
        config = APIConfig(base_url="http://httpbin.org")
        assert config.base_url == "http://httpbin.org"

    def test_base_url_https_scheme_valid(self):
        config = APIConfig(base_url="https://api.github.com")
        assert config.base_url == "https://api.github.com"


class TestLogConfigValidation:
    def test_log_file_none_handling(self):
        config = LogConfig(file=None)
        assert config.file is None

    def test_log_file_directory_creation(self, tmp_path: Path) -> None:
        log_file = tmp_path / "logs" / "subdir" / "app.log"
        assert not log_file.parent.exists()

        _ = LogConfig(file=str(log_file))

        # ディレクトリが作成されたことを確認
        assert log_file.parent.exists()
        assert log_file.parent.is_dir()

    def test_log_file_existing_directory(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "existing_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "app.log"

        config = LogConfig(file=str(log_file))
        assert config.file == str(log_file)

    def test_log_file_deep_nested_directory_creation(self, tmp_path: Path) -> None:
        log_file = tmp_path / "a" / "b" / "c" / "d" / "app.log"
        _ = LogConfig(file=str(log_file))
        assert log_file.parent.exists()


class TestSettingsEnvironmentValidation:
    @pytest.mark.parametrize(
        ("env_input", "expected", "needs_secret"),
        [
            pytest.param("PRODUCTION", Environment.PRODUCTION, True, id="uppercase"),
            pytest.param("DeVeLoPmEnT", Environment.DEVELOPMENT, False, id="mixed_case"),
            pytest.param(Environment.TESTING, Environment.TESTING, False, id="enum_direct"),
            pytest.param("staging", Environment.STAGING, True, id="lowercase"),
        ],
    )
    def test_environment_validation(
        self,
        env_input: str | Environment,
        expected: Environment,
        needs_secret: bool,
    ) -> None:
        """Pydanticのstr→Enum実行時変換により、静的型との差異を許容する契約を検証する。"""
        if needs_secret:
            settings = Settings(
                environment=env_input,  # type: ignore[arg-type]
                security=SecurityConfig(api_key=SecretStr("test-key")),
                api=APIConfig(base_url="https://jsonplaceholder.typicode.com"),  # https:// 必須
            )
        else:
            settings = Settings(environment=env_input)  # type: ignore[arg-type]
        assert settings.environment == expected

    @pytest.mark.parametrize(
        "env_input",
        [
            pytest.param("production ", id="trailing_space"),
            pytest.param(" development", id="leading_space"),
            pytest.param("  staging  ", id="both_spaces"),
        ],
    )
    def test_environment_validation_strips_whitespace(self, env_input: str) -> None:
        stripped = env_input.strip().lower()
        expected = Environment(stripped)
        needs_secret = expected in {Environment.PRODUCTION, Environment.STAGING}
        if needs_secret:
            settings = Settings(
                environment=env_input,  # type: ignore[arg-type]
                security=SecurityConfig(api_key=SecretStr("test-key")),
                api=APIConfig(base_url="https://jsonplaceholder.typicode.com"),
            )
        else:
            settings = Settings(environment=env_input)  # type: ignore[arg-type]
        assert settings.environment == expected

    @pytest.mark.parametrize(
        "empty_input",
        [
            pytest.param("", id="empty_string"),
            pytest.param("  ", id="whitespace_only"),
            pytest.param("\t", id="tab_only"),
        ],
    )
    def test_environment_validation_empty_raises(self, empty_input: str) -> None:
        with pytest.raises(ValidationError):
            Settings(environment=empty_input)  # type: ignore[arg-type]

    def test_environment_validation_invalid_string_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Settings(environment="producton")  # type: ignore[arg-type]
        # エラーメッセージに有効値リストが含まれることを検証（契約の明示的保護）
        # Pydantic非依存: validate_environment のカスタムメッセージを .errors() で検証
        assert any("Valid values" in str(e["msg"]) for e in exc_info.value.errors())

    def test_environment_validation_invalid_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            Settings(environment=123)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "short_form",
        [
            pytest.param("dev", id="short_dev_raises"),
            pytest.param("test", id="short_test_raises"),
            pytest.param("stg", id="short_stg_raises"),
            pytest.param("prod", id="short_prod_raises"),
        ],
    )
    def test_environment_validation_short_forms_raise(self, short_form: str) -> None:
        """.env.example/docker-compose.ymlで明示された「短縮形不可」契約を、直接Settingsをinstantiateして保護する。"""
        with pytest.raises(ValidationError):
            Settings(environment=short_form)  # type: ignore[arg-type]


class TestSettingsEnvironmentMethods:
    def test_is_development_true(self):
        settings = Settings(environment=Environment.DEVELOPMENT)
        assert settings.is_development() is True

    def test_is_testing_true(self):
        settings = Settings(environment=Environment.TESTING)
        assert settings.is_testing() is True

    def test_is_production_true(self):
        # 本番環境ではシークレットが必須
        settings = Settings(
            environment=Environment.PRODUCTION,
            security=SecurityConfig(api_key=SecretStr("test-key")),
        )
        assert settings.is_production() is True

    @pytest.mark.parametrize(
        ("env", "expected"),
        [
            pytest.param(Environment.STAGING, True, id="staging"),
            pytest.param(Environment.PRODUCTION, False, id="production"),
            pytest.param(Environment.DEVELOPMENT, False, id="development"),
            pytest.param(Environment.TESTING, False, id="testing"),
        ],
    )
    def test_is_staging(self, env: Environment, expected: bool) -> None:
        kwargs: dict[str, Any] = {"environment": env}
        if env in {Environment.PRODUCTION, Environment.STAGING}:
            kwargs["security"] = SecurityConfig(api_key=SecretStr("test-key"))
        settings = Settings(**kwargs)
        assert settings.is_staging() is expected

    @pytest.mark.parametrize(
        ("env", "expected"),
        [
            pytest.param(Environment.PRODUCTION, True, id="production"),
            pytest.param(Environment.STAGING, True, id="staging"),
            pytest.param(Environment.DEVELOPMENT, False, id="development"),
            pytest.param(Environment.TESTING, False, id="testing"),
        ],
    )
    def test_is_production_like(self, env: Environment, expected: bool) -> None:
        kwargs: dict[str, Any] = {"environment": env}
        if env in {Environment.PRODUCTION, Environment.STAGING}:
            kwargs["security"] = SecurityConfig(api_key=SecretStr("test-key"))
        settings = Settings(**kwargs)
        assert settings.is_production_like() is expected

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
        settings = Settings()
        settings.log.level = log_level
        assert settings.get_log_level() == expected


class TestProductionSecretValidation:
    def test_production_without_secrets_raises_error(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(environment=Environment.PRODUCTION)
        assert "SECURITY__API_KEY or SECURITY__JWT_SECRET" in str(exc_info.value)

    def test_production_with_api_key_valid(self):
        settings = Settings(
            environment=Environment.PRODUCTION,
            security=SecurityConfig(api_key=SecretStr("test-key")),
        )
        assert settings.is_production() is True

    def test_production_with_jwt_secret_valid(self):
        settings = Settings(
            environment=Environment.PRODUCTION,
            security=SecurityConfig(jwt_secret=SecretStr("test-secret")),
        )
        assert settings.is_production() is True

    def test_development_without_secrets_valid(self):
        settings = Settings(environment=Environment.DEVELOPMENT)
        assert settings.is_development() is True

    def test_staging_without_secrets_raises_error(self):
        """TestProductionSecretValidationクラスだがSTAGINGも本番同等のシークレット必須ポリシーを検証する。"""
        with pytest.raises(ValidationError, match="SECURITY__API_KEY or SECURITY__JWT_SECRET"):
            Settings(
                environment=Environment.STAGING,
                api=APIConfig(base_url="https://jsonplaceholder.typicode.com"),
            )

    def test_staging_with_api_key_valid(self):
        settings = Settings(
            environment=Environment.STAGING,
            security=SecurityConfig(api_key=SecretStr("test-key")),
            api=APIConfig(base_url="https://jsonplaceholder.typicode.com"),
        )
        assert settings.environment == Environment.STAGING

    def test_staging_with_jwt_secret_valid(self):
        settings = Settings(
            environment=Environment.STAGING,
            security=SecurityConfig(jwt_secret=SecretStr("test-secret")),
            # validate_production_https のためHTTPS必須
            api=APIConfig(base_url="https://jsonplaceholder.typicode.com"),
        )
        assert settings.environment == Environment.STAGING


class TestProductionHTTPSValidation:
    def test_production_http_raises_error(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                environment=Environment.PRODUCTION,
                security=SecurityConfig(api_key=SecretStr("test-key")),
                api=APIConfig(base_url="http://jsonplaceholder.typicode.com"),
            )
        assert "requires HTTPS" in str(exc_info.value)

    def test_production_https_valid(self):
        settings = Settings(
            environment=Environment.PRODUCTION,
            security=SecurityConfig(api_key=SecretStr("test-key")),
            api=APIConfig(base_url="https://jsonplaceholder.typicode.com"),
        )
        assert settings.api.base_url == "https://jsonplaceholder.typicode.com"

    def test_staging_http_raises_error(self):
        """ステージング環境のHTTPS強制をOWASP A02（暗号化の失敗）対策として検証する。"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                environment=Environment.STAGING,
                security=SecurityConfig(api_key=SecretStr("test-key")),
                api=APIConfig(base_url="http://jsonplaceholder.typicode.com"),
            )
        assert "requires HTTPS" in str(exc_info.value)

    def test_staging_https_valid(self):
        settings = Settings(
            environment=Environment.STAGING,
            security=SecurityConfig(api_key=SecretStr("test-key")),
            api=APIConfig(base_url="https://jsonplaceholder.typicode.com"),
        )
        assert settings.api.base_url == "https://jsonplaceholder.typicode.com"

    def test_development_http_valid(self):
        settings = Settings(
            environment=Environment.DEVELOPMENT,
            api=APIConfig(base_url="http://jsonplaceholder.typicode.com"),
        )
        assert settings.api.base_url == "http://jsonplaceholder.typicode.com"


class TestSettingsSecretMasking:
    def test_to_dict_with_secret_masking_enabled(self):
        settings = Settings()
        # テスト専用ダミー値（本番では使用されない）
        settings.security.api_key = SecretStr("test-api-key-12345")
        settings.security.jwt_secret = SecretStr("test-jwt-secret-67890")

        result = settings.to_dict(exclude_secrets=True)

        assert result["security"]["api_key"] == "***MASKED***"
        assert result["security"]["jwt_secret"] == "***MASKED***"  # noqa: S105 - テスト用マスク文字列

    def test_to_dict_with_secret_masking_disabled(self):
        settings = Settings()
        # テスト専用ダミー値（本番では使用されない）
        settings.security.api_key = SecretStr("test-api-key-12345")
        settings.security.jwt_secret = SecretStr("test-jwt-secret-67890")

        result = settings.to_dict(exclude_secrets=False)

        # SecretStrの値は.get_secret_value()で取得できるが、model_dump()では文字列として出力される
        # Pydanticの動作により、SecretStrは文字列として出力される
        assert "api_key" in result["security"]
        assert "jwt_secret" in result["security"]

    def test_to_dict_model_dump_called(self):
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
        settings = Settings()
        settings.security.api_key = None

        result = settings.to_dict(exclude_secrets=True)

        # Noneの場合はマスクされない（line 220のif条件）
        assert result["security"]["api_key"] is None

    def test_to_dict_jwt_secret_none_not_masked(self):
        settings = Settings()
        settings.security.jwt_secret = None

        result = settings.to_dict(exclude_secrets=True)

        assert result["security"]["jwt_secret"] is None

    def test_to_dict_sentry_dsn_masked(self):
        from pydantic import SecretStr

        settings = Settings()
        settings.sentry = SentryConfig(
            dsn=SecretStr("https://abc123@o456.ingest.sentry.io/789"),
        )

        result = settings.to_dict(exclude_secrets=True)

        assert result["sentry"]["dsn"] == "***MASKED***"

    def test_to_dict_sentry_dsn_empty_also_masked(self):
        """空のSecretStrもmodel_dump後は文字列化されマスク対象になる仕様を検証する。"""
        settings = Settings()
        # デフォルトは空SecretStr、model_dump()後は'**********'文字列

        result = settings.to_dict(exclude_secrets=True)

        # model_dump()後のSecretStrは文字列として扱われ、マスクされる
        assert result["sentry"]["dsn"] == "***MASKED***"

    def test_sentry_config_default_factory(self):
        settings = Settings()

        assert isinstance(settings.sentry, SentryConfig)
        assert settings.sentry.enabled is False
        assert settings.sentry.traces_sample_rate == 0.1


class TestSettingsSingleton:
    """シングルトン状態のリークを防ぐため、autouse fixtureでリセットし再生成契約を検証する。"""

    @pytest.fixture(autouse=True)
    def reset_singleton(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """各テスト前にシングルトンをリセット（DRY改善）"""
        import config.settings

        monkeypatch.setattr(config.settings, "_settings", None)

    def test_get_settings_creates_instance_first_time(self) -> None:
        settings1 = get_settings()
        assert settings1 is not None
        assert isinstance(settings1, Settings)

    def test_get_settings_returns_same_instance(self) -> None:
        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_reload_settings_creates_new_instance(self) -> None:
        settings1 = get_settings()
        settings2 = reload_settings()

        # 新しいインスタンスが作成される
        assert settings1 is not settings2
        assert isinstance(settings2, Settings)

    def test_reload_settings_updates_global_variable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 最初のインスタンス作成
        settings1 = get_settings()
        _ = settings1.project_name

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
    @pytest.mark.parametrize(
        ("attr", "expected_type"),
        [
            pytest.param("api", APIConfig, id="api_config"),
            pytest.param("log", LogConfig, id="log_config"),
            pytest.param("test", SettingsTestConfig, id="test_config"),
            pytest.param("security", SecurityConfig, id="security_config"),
        ],
    )
    def test_nested_config_type(self, attr: str, expected_type: type) -> None:
        settings = Settings()
        assert isinstance(getattr(settings, attr), expected_type)


class TestTestConfigDefaults:
    @pytest.mark.parametrize(
        ("attr", "expected"),
        [
            pytest.param("external_api_enabled", True, id="external_api_enabled_true"),
            pytest.param("performance_test_enabled", False, id="performance_test_enabled_false"),
            pytest.param("security_test_enabled", False, id="security_test_enabled_false"),
            pytest.param("test_data_cleanup", True, id="test_data_cleanup_true"),
        ],
    )
    def test_test_config_boolean_defaults(self, attr: str, expected: bool) -> None:
        config = SettingsTestConfig()
        assert getattr(config, attr) is expected


class TestEnvironmentVariableLoading:
    def test_nested_environment_variable_loading(self, monkeypatch):
        monkeypatch.setenv("API__BASE_URL", "https://httpbin.org")
        import config.settings

        monkeypatch.setattr(config.settings, "_settings", None)

        settings = reload_settings()
        assert settings.api.base_url == "https://httpbin.org"

    def test_case_insensitive_environment_variables(self, monkeypatch):
        monkeypatch.setenv("project_name", "Test Project")
        import config.settings

        monkeypatch.setattr(config.settings, "_settings", None)

        settings = reload_settings()
        assert settings.project_name == "Test Project"

    def test_debug_mode_from_environment(self, monkeypatch):
        monkeypatch.setenv("DEBUG", "false")
        import config.settings

        monkeypatch.setattr(config.settings, "_settings", None)

        settings = reload_settings()
        assert settings.debug is False


class TestSSRFPrevention:
    """OWASP API7:2023対策として、base_urlを許可ドメインのallowlistだけで制限する契約を検証する。"""

    @pytest.mark.parametrize(
        ("malicious_url", "description"),
        [
            pytest.param(
                "http://169.254.169.254/latest/meta-data/",
                "AWS metadata endpoint",
                id="aws_metadata",
            ),
            pytest.param(
                "http://localhost:8080/admin",
                "Loopback localhost",
                id="localhost",
            ),
            pytest.param(
                "http://127.0.0.1:8080/admin",
                "Loopback 127.0.0.1",
                id="loopback_ip",
            ),
            pytest.param(
                "http://192.168.1.1/router",
                "Private IP 192.168.x.x",
                id="private_192_168",
            ),
            pytest.param(
                "http://10.0.0.1/internal",
                "Private IP 10.x.x.x",
                id="private_10",
            ),
            pytest.param(
                "http://172.16.0.1/internal",
                "Private IP 172.16.x.x",
                id="private_172_16",
            ),
            # userinfo はホストではない。allowlist 判定が netloc に退行すると通ってしまう
            pytest.param(
                "https://jsonplaceholder.typicode.com@169.254.169.254/latest/meta-data/",
                "Userinfo authority confusion to metadata endpoint",
                id="userinfo_authority_confusion",
            ),
        ],
    )
    def test_ssrf_unallowlisted_hosts_rejected(self, malicious_url: str, description: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            APIConfig(base_url=malicious_url)

        error_message = str(exc_info.value)
        assert "SSRF Prevention" in error_message, (
            f"Expected SSRF Prevention error for {description}"
        )

    @pytest.mark.parametrize(
        ("unauthorized_url", "domain"),
        [
            pytest.param(
                "https://evil-site.com/api",
                "evil-site.com",
                id="unauthorized_external",
            ),
            pytest.param(
                "https://attacker.io/proxy",
                "attacker.io",
                id="attacker_domain",
            ),
            pytest.param(
                "https://internal.corp.local/api",
                "internal.corp.local",
                id="corp_internal",
            ),
            # 末尾ドット FQDN は DNS 上は同一だが、allowlist は完全一致のため拒否される
            pytest.param(
                "https://jsonplaceholder.typicode.com./posts",
                "jsonplaceholder.typicode.com.",
                id="trailing_dot_fqdn",
            ),
        ],
    )
    def test_ssrf_domain_allowlist_enforced(self, unauthorized_url: str, domain: str) -> None:
        """このvalidatorはallowlist判定のみでDNS解決やprivate-IP判定を行わない契約を検証する。"""
        with pytest.raises(ValidationError) as exc_info:
            APIConfig(base_url=unauthorized_url)

        error_message = str(exc_info.value)
        # allowlist 外のホストは "SSRF Prevention: Domain not in allowlist" でブロックされる
        assert "Domain not in allowlist" in error_message or "SSRF Prevention" in error_message, (
            f"Expected SSRF Prevention error for {domain}"
        )

    @pytest.mark.parametrize(
        "allowed_domain",
        [
            pytest.param("https://jsonplaceholder.typicode.com", id="jsonplaceholder"),
            pytest.param("https://api.github.com", id="github_api"),
            pytest.param("https://httpbin.org", id="httpbin"),
            # allowlist の次元はホスト名のみ
            # port を検証次元に加える退行を検出する。
            pytest.param(
                "https://jsonplaceholder.typicode.com:8443",
                id="allowed_host_non_default_port",
            ),
        ],
    )
    def test_allowed_domains_accepted(self, allowed_domain: str) -> None:
        config = APIConfig(base_url=allowed_domain)
        assert config.base_url == allowed_domain.rstrip("/")

    def test_validate_base_url_ssrf_block_logs_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="config.settings"):
            with pytest.raises(ValidationError):
                APIConfig(base_url="https://evil.attacker.com/api")

        assert any("SSRF Prevention" in record.message for record in caplog.records), (
            "SSRF防止ブロック時にwarningログが出力されるべき"
        )


# ── Boundary value + ALLOWED_DOMAINS tests ──


class TestTestConfigBoundaryValues:
    @pytest.mark.parametrize(
        ("value", "expected_valid"),
        [
            pytest.param(0.09, False, id="slow_test_threshold_below_min"),
            pytest.param(0.1, True, id="slow_test_threshold_at_min"),
            pytest.param(3.0, True, id="slow_test_threshold_default"),
        ],
    )
    def test_slow_test_threshold_boundary(self, value: float, expected_valid: bool) -> None:
        if expected_valid:
            config = SettingsTestConfig(slow_test_threshold=value)
            assert config.slow_test_threshold == value
        else:
            with pytest.raises(ValidationError):
                SettingsTestConfig(slow_test_threshold=value)

    @pytest.mark.parametrize(
        ("value", "expected_valid"),
        [
            pytest.param(0, False, id="max_concurrent_below_min"),
            pytest.param(1, True, id="max_concurrent_at_min"),
            pytest.param(50, True, id="max_concurrent_at_max"),
            pytest.param(51, False, id="max_concurrent_above_max"),
        ],
    )
    def test_max_concurrent_requests_boundary(self, value: int, expected_valid: bool) -> None:
        if expected_valid:
            config = SettingsTestConfig(max_concurrent_requests=value)
            assert config.max_concurrent_requests == value
        else:
            with pytest.raises(ValidationError):
                SettingsTestConfig(max_concurrent_requests=value)


class TestAllowedDomainsEnvOverride:
    """ALLOWED_DOMAINSはmodule import時に一度だけ確定するため、起動後のmonkeypatch.setenvが
    validate_base_url()に反映されない制約を検証する。"""

    def test_allowed_domains_env_override(self, monkeypatch):
        from config.settings import _get_allowed_domains

        monkeypatch.setenv("ALLOWED_DOMAINS", "custom.example.com,api.custom.com")
        result = _get_allowed_domains()
        assert isinstance(result, frozenset)
        assert result == frozenset({"custom.example.com", "api.custom.com"})

    def test_allowed_domains_env_empty_returns_default(self, monkeypatch):
        from config.settings import _get_allowed_domains

        monkeypatch.delenv("ALLOWED_DOMAINS", raising=False)
        result = _get_allowed_domains()
        assert isinstance(result, frozenset)
        # マジックナンバー len(result) >= 7 を避け、必須デフォルトドメインの subset を検証する。
        assert {
            "jsonplaceholder.typicode.com",
            "api.github.com",
            "httpbin.org",
        }.issubset(result)

    @pytest.mark.parametrize(
        "value",
        [
            pytest.param("", id="empty_string"),
            pytest.param("  ", id="whitespace_only"),
            pytest.param(",", id="comma_only"),
            pytest.param(" , ", id="blank_entries_only"),
        ],
    )
    def test_allowed_domains_blank_env_entries_return_empty_set(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        """空白のみのALLOWED_DOMAINSはdeny-all（空セット）として扱われるfail-safe仕様を検証する。"""
        from config.settings import _get_allowed_domains

        monkeypatch.setenv("ALLOWED_DOMAINS", value)
        result = _get_allowed_domains()
        assert result == frozenset()

    def test_allowed_domains_override_does_not_affect_validate_base_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ALLOWED_DOMAINSのimport時確定という制約を、setenv後もValidationErrorが出ることで保護する。"""
        # custom.example.com を ALLOWED_DOMAINS に追加しても、
        # モジュールは既に評価済みのため反映されない
        monkeypatch.setenv("ALLOWED_DOMAINS", "custom.example.com")
        # validate_base_url() は ALLOWED_DOMAINS 既存値 (import時確定) を参照するため
        # custom.example.com は許可ドメインに含まれず ValidationError になる
        with pytest.raises(ValidationError):
            APIConfig(base_url="https://custom.example.com")
