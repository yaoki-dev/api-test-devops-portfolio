import logging
import socket
from collections.abc import Callable, Iterator
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
    _resolve_hostname,
    _resolve_hostname_cached,
    _validate_base_url_with_allowed_domains,
    get_settings,
    is_private_ip,
    reload_settings,
)
from config.settings import (
    TestConfig as SettingsTestConfig,
)

# Module-level marker: All tests in this file are unit tests
pytestmark = pytest.mark.unit


class TestAPIConfigBaseUrlDependencyInjection:
    """base_url検証の許可ドメイン注入テスト。"""

    def test_validate_base_url_accepts_injected_allowed_domain(self) -> None:
        """ALLOWED_DOMAINSのモンキーパッチなしで許可ドメインを注入できる。"""
        result = _validate_base_url_with_allowed_domains(
            "https://example.com/",
            frozenset({"example.com"}),
        )

        assert result == "https://example.com"

    def test_validate_base_url_rejects_domain_missing_from_injected_allowlist(self) -> None:
        """注入された許可リスト外のドメインは拒否される。"""
        with pytest.raises(ValueError, match="Domain not in allowlist"):
            _validate_base_url_with_allowed_domains(
                "https://httpbin.org",
                frozenset({"example.com"}),
            )

    def test_validate_base_url_rejects_missing_hostname(self) -> None:
        """hostname が取れない URL は拒否される。"""
        with pytest.raises(ValueError, match="Invalid URL: hostname not found"):
            _validate_base_url_with_allowed_domains(
                "https://",
                frozenset({"example.com"}),
            )

    def test_validate_base_url_blocks_private_ip_regardless_of_allowlist(self) -> None:
        """プライベートIPは許可リストに含まれていてもブロックされる。

        SSRF Prevention: DIパスの契約テスト。
        許可リストにプライベートIPが含まれていても、
        is_private_ip()による先行チェックでブロックされることを検証する。
        """
        with pytest.raises(ValueError, match="Private/loopback IP addresses are not allowed"):
            _validate_base_url_with_allowed_domains(
                "http://192.168.1.1",
                frozenset({"192.168.1.1"}),  # 許可リストに入れても無効
            )


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
        self,
        field: str,
        value: float,
        should_pass: bool,
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

    def test_base_url_https_scheme_valid(self):
        """https://スキームが有効（DNS解決可能なドメインを使用）"""
        # Note: example.com系はDNS解決失敗でFail-Closedブロック
        config = APIConfig(base_url="https://api.github.com")
        assert config.base_url == "https://api.github.com"


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

        _ = LogConfig(file=str(log_file))

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
        _ = LogConfig(file=str(log_file))
        assert log_file.parent.exists()


class TestSettingsEnvironmentValidation:
    """Settings.validate_environment のテスト (lines 192-194)"""

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
        """環境設定バリデーション: 文字列→小文字変換、Enum直接指定

        Note:
            Pydantic field_validatorが実行時に文字列→Enum変換を行うため、
            str | Environment を受け入れる。静的型チェックとの差異あり。
            本番・ステージング環境はシークレット必須かつHTTPS強制のため、
            needs_secret=Trueの場合はHTTPS URLも合わせて指定する。
        """
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
        """validate_environment: 前後スペースを除去してから正規化する"""
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
        """validate_environment: 空文字列・スペースのみ・タブのみはValidationErrorを発生させる"""
        with pytest.raises(ValidationError):
            Settings(environment=empty_input)  # type: ignore[arg-type]

    def test_environment_validation_invalid_string_raises(self) -> None:
        """validate_environment: タイポなど無効な文字列はValidationErrorを発生させる"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(environment="producton")  # type: ignore[arg-type]
        # エラーメッセージに有効値リストが含まれることを検証（契約の明示的保護）
        # Pydantic非依存: validate_environment のカスタムメッセージを .errors() で検証
        assert any("有効な値" in str(e["msg"]) for e in exc_info.value.errors())

    def test_environment_validation_invalid_type_raises(self) -> None:
        """validate_environment: str/Environment以外の型はValidationErrorを発生させる"""
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
        """validate_environment: 短縮形 (dev/test/stg/prod) は ValidationError を発生させる.

        .env.example および docker-compose.yml で「Pydantic Environment enum は
        development/testing/staging/production の 4 値のみ。短縮形は不可」と明示している。
        本テストはその契約を保護する。

        Note:
            dev/test/stg/prod は互換マッピングせず、Pydantic層で常に reject される。
            本テストは「直接 python から Settings を instantiate する」シナリオ
            (CI script, smoke test 等) を検証する。
        """
        with pytest.raises(ValidationError):
            Settings(environment=short_form)  # type: ignore[arg-type]


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
        """is_staging() がステージング環境のみTrueを返す"""
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
        """is_production_like() が本番相当環境を正しく判定"""
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
        """get_log_level() がLogLevel Enumを正しくlogging定数にマッピング"""
        settings = Settings()
        settings.log.level = log_level
        assert settings.get_log_level() == expected


class TestProductionSecretValidation:
    """本番・ステージング環境でのシークレット検証テスト"""

    def test_production_without_secrets_raises_error(self):
        """本番環境でシークレット未設定時にエラー"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(environment=Environment.PRODUCTION)
        assert "SECURITY__API_KEY or SECURITY__JWT_SECRET" in str(exc_info.value)

    def test_production_with_api_key_valid(self):
        """本番環境でapi_key設定時は有効"""
        settings = Settings(
            environment=Environment.PRODUCTION,
            security=SecurityConfig(api_key=SecretStr("test-key")),
        )
        assert settings.is_production() is True

    def test_production_with_jwt_secret_valid(self):
        """本番環境でjwt_secret設定時は有効"""
        settings = Settings(
            environment=Environment.PRODUCTION,
            security=SecurityConfig(jwt_secret=SecretStr("test-secret")),
        )
        assert settings.is_production() is True

    def test_development_without_secrets_valid(self):
        """開発環境ではシークレット不要"""
        settings = Settings(environment=Environment.DEVELOPMENT)
        assert settings.is_development() is True

    def test_staging_without_secrets_raises_error(self):
        """ステージング環境でシークレット未設定時にエラー (STAGING=本番同等ポリシー)"""
        with pytest.raises(ValidationError, match="SECURITY__API_KEY or SECURITY__JWT_SECRET"):
            Settings(
                environment=Environment.STAGING,
                api=APIConfig(base_url="https://jsonplaceholder.typicode.com"),
            )

    def test_staging_with_api_key_valid(self):
        """ステージング環境でapi_key設定時は有効"""
        settings = Settings(
            environment=Environment.STAGING,
            security=SecurityConfig(api_key=SecretStr("test-key")),
            api=APIConfig(base_url="https://jsonplaceholder.typicode.com"),
        )
        assert settings.environment == Environment.STAGING

    def test_staging_with_jwt_secret_valid(self):
        """ステージング環境でjwt_secret設定時は有効"""
        settings = Settings(
            environment=Environment.STAGING,
            security=SecurityConfig(jwt_secret=SecretStr("test-secret")),
            # validate_production_https のためHTTPS必須
            api=APIConfig(base_url="https://jsonplaceholder.typicode.com"),
        )
        assert settings.environment == Environment.STAGING


class TestProductionHTTPSValidation:
    """本番環境でのHTTPS強制テスト"""

    def test_production_http_raises_error(self):
        """本番環境でHTTP URLはエラー"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                environment=Environment.PRODUCTION,
                security=SecurityConfig(api_key=SecretStr("test-key")),
                api=APIConfig(base_url="http://jsonplaceholder.typicode.com"),
            )
        assert "requires HTTPS" in str(exc_info.value)

    def test_production_https_valid(self):
        """本番環境でHTTPS URLは有効"""
        settings = Settings(
            environment=Environment.PRODUCTION,
            security=SecurityConfig(api_key=SecretStr("test-key")),
            api=APIConfig(base_url="https://jsonplaceholder.typicode.com"),
        )
        assert settings.api.base_url == "https://jsonplaceholder.typicode.com"

    def test_staging_http_raises_error(self):
        """ステージング環境でHTTP URLはエラー (OWASP A02)"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                environment=Environment.STAGING,
                security=SecurityConfig(api_key=SecretStr("test-key")),
                api=APIConfig(base_url="http://jsonplaceholder.typicode.com"),
            )
        assert "requires HTTPS" in str(exc_info.value)

    def test_staging_https_valid(self):
        """ステージング環境でHTTPS URLは有効"""
        settings = Settings(
            environment=Environment.STAGING,
            security=SecurityConfig(api_key=SecretStr("test-key")),
            api=APIConfig(base_url="https://jsonplaceholder.typicode.com"),
        )
        assert settings.api.base_url == "https://jsonplaceholder.typicode.com"

    def test_development_http_valid(self):
        """開発環境ではHTTP URLを許可"""
        settings = Settings(
            environment=Environment.DEVELOPMENT,
            api=APIConfig(base_url="http://jsonplaceholder.typicode.com"),
        )
        assert settings.api.base_url == "http://jsonplaceholder.typicode.com"


class TestSettingsSecretMasking:
    """Settings.to_dict() のシークレットマスキングテスト (lines 214-225)"""

    def test_to_dict_with_secret_masking_enabled(self):
        """exclude_secrets=True でシークレットがマスクされる (lines 217-223)"""
        settings = Settings()
        # テスト専用ダミー値（本番では使用されない）
        settings.security.api_key = SecretStr("test-api-key-12345")
        settings.security.jwt_secret = SecretStr("test-jwt-secret-67890")

        result = settings.to_dict(exclude_secrets=True)

        assert result["security"]["api_key"] == "***MASKED***"
        assert result["security"]["jwt_secret"] == "***MASKED***"  # noqa: S105 - テスト用マスク文字列

    def test_to_dict_with_secret_masking_disabled(self):
        """exclude_secrets=False でシークレットがそのまま出力される (line 216)"""
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
            dsn=SecretStr("https://abc123@o456.ingest.sentry.io/789"),
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
    """ネスト設定のデフォルトファクトリーテスト"""

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
        """各サブ設定がdefault_factoryで正しい型として初期化される"""
        settings = Settings()
        assert isinstance(getattr(settings, attr), expected_type)


class TestTestConfigDefaults:
    """TestConfig のデフォルト値テスト"""

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
        """TestConfig の bool デフォルトが退行しないことを保護する"""
        config = SettingsTestConfig()
        assert getattr(config, attr) is expected


class TestEnvironmentVariableLoading:
    """環境変数からの設定読み込みテスト"""

    def test_nested_environment_variable_loading(self, monkeypatch):
        """ネスト記法（API__BASE_URL）での環境変数読み込み"""
        # Note: DNS解決可能なドメインを使用（example.com系はFail-Closedでブロック）
        monkeypatch.setenv("API__BASE_URL", "https://httpbin.org")
        import config.settings

        monkeypatch.setattr(config.settings, "_settings", None)

        settings = reload_settings()
        assert settings.api.base_url == "https://httpbin.org"

    def test_case_insensitive_environment_variables(self, monkeypatch):
        """大小文字を区別しない環境変数読み込み (case_sensitive=False)"""
        monkeypatch.setenv("project_name", "Test Project")
        import config.settings

        monkeypatch.setattr(config.settings, "_settings", None)

        settings = reload_settings()
        assert settings.project_name == "Test Project"

    def test_debug_mode_from_environment(self, monkeypatch):
        """DEBUG環境変数からのdebugモード設定"""
        monkeypatch.setenv("DEBUG", "false")
        import config.settings

        monkeypatch.setattr(config.settings, "_settings", None)

        settings = reload_settings()
        assert settings.debug is False


class DNSCacheClearMixin:
    """DNS解決キャッシュクリアの共通fixture

    TestSSRFPrevention と TestResolveHostname で共有する。
    autouse=True により各テスト前後にキャッシュをクリアし、テスト間の干渉を防止。
    """

    @pytest.fixture(autouse=True)
    def clear_dns_cache(self) -> Iterator[None]:
        """各テスト前後にDNS解決キャッシュをクリアする"""
        _resolve_hostname_cached.cache_clear()
        yield
        _resolve_hostname_cached.cache_clear()


class TestSSRFPrevention(DNSCacheClearMixin):
    """SSRF攻撃防止のセキュリティテスト

    OWASP API Security Top 10 - API7:2023 Server Side Request Forgery (SSRF)
    - プライベートIP/ループバックアドレスのブロック
    - 許可ドメインリストによるアクセス制御
    - DNS解決失敗時のフェイルクローズド動作
    """

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
        ],
    )
    def test_ssrf_private_ip_blocked(self, malicious_url: str, description: str) -> None:
        """SSRF Prevention: プライベート/ループバックIPをブロック

        Security Rationale:
            内部ネットワークへのアクセスを防止し、
            AWSメタデータ、ルーター設定、内部サービスへの
            不正アクセスを防ぐ。
        """
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
        ],
    )
    def test_ssrf_domain_allowlist_enforced(self, unauthorized_url: str, domain: str) -> None:
        """SSRF Prevention: 許可ドメインリスト外のドメインをブロック

        Security Rationale:
            許可されたドメイン（jsonplaceholder.typicode.com、
            api.github.com等）のみアクセス可能とし、
            任意のURLへのアクセスを防止。

        Note:
            .local ドメインなどDNS解決に失敗するドメインは、
            Fail-Closed動作により「Private/loopback IP」エラーとなる。
            どちらのエラーでもSSRF攻撃は防止される。
        """
        with pytest.raises(ValidationError) as exc_info:
            APIConfig(base_url=unauthorized_url)

        error_message = str(exc_info.value)
        # SSRFは以下いずれかのエラーでブロック:
        # 1. Domain not in allowlist (resolvable but unauthorized)
        # 2. Private/loopback IP (DNS failure → fail-closed)
        assert "Domain not in allowlist" in error_message or "SSRF Prevention" in error_message, (
            f"Expected SSRF Prevention error for {domain}"
        )

    @pytest.mark.parametrize(
        ("ip_address", "expected_private"),
        [
            # プライベートIPレンジ（True = ブロック）
            pytest.param("127.0.0.1", True, id="loopback"),
            pytest.param("10.0.0.1", True, id="private_10"),
            pytest.param("172.16.0.1", True, id="private_172_16"),
            pytest.param("192.168.1.1", True, id="private_192_168"),
            pytest.param("169.254.169.254", True, id="link_local_aws"),
            # パブリックIP（False = 許可候補、ただしドメインリスト確認が必要）
            pytest.param("8.8.8.8", False, id="google_dns"),
            pytest.param("1.1.1.1", False, id="cloudflare_dns"),
        ],
    )
    def test_is_private_ip_detection(self, ip_address: str, expected_private: bool) -> None:
        """is_private_ip()がプライベートIPを正しく検出

        Security Rationale:
            RFC 1918（プライベートIP）、RFC 3927（リンクローカル）、
            RFC 5735（ループバック）を正しく識別し、
            内部ネットワークへのSSRF攻撃を防止。
        """
        result = is_private_ip(ip_address)
        assert result == expected_private, (
            f"Expected is_private_ip({ip_address}) == {expected_private}"
        )

    def test_is_private_ip_dns_failure_returns_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DNS解決失敗時はTrueを返す（Fail-Closed動作）

        Security Rationale (CRITICAL):
            DNS解決が失敗した場合、攻撃者が制御する
            DNSサーバーを介したSSRF攻撃を防ぐため、
            安全側に倒す（ブロック）。

            Fail-Open（False返却）は、以下の攻撃を許容してしまう:
            - DNS rebinding attack
            - Malicious DNS server による内部IP解決
        """
        import socket

        # DNS解決を常に失敗させる
        def mock_gethostbyname(hostname: str) -> str:
            raise OSError("DNS resolution failed")

        monkeypatch.setattr(socket, "gethostbyname", mock_gethostbyname)

        # 不明なホストはプライベートIPとして扱う（Fail-Closed）
        result = is_private_ip("unknown-host.test")
        assert result is True, "DNS failure should return True (Fail-Closed)"

    def test_is_private_ip_invalid_dns_response_returns_true(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """DNS解決結果が不正なIPアドレス形式の場合、Fail-Closedでブロック（True）を返す

        Security:
            異常なDNS応答（IPアドレス形式でない文字列）に対するSSRF防止の最終砦。
            _logger.warning()でセキュリティ証跡を記録することも検証する。
        """
        monkeypatch.setattr(socket, "gethostbyname", lambda _: "not-an-ip-address")

        with caplog.at_level(logging.WARNING, logger="config.settings"):
            result = is_private_ip("malicious.example.com")

        assert result is True, "不正なDNS応答はブロック扱い（Fail-Closed）"
        assert any("不正なIPアドレス形式" in record.message for record in caplog.records), (
            "セキュリティ証跡としてwarningログが出力されること"
        )

    @pytest.mark.parametrize(
        "allowed_domain",
        [
            # 実際にDNS解決可能なドメインのみテスト
            # example.com系は予約済みドメインで解決失敗 → Fail-Closedでブロック
            pytest.param("https://jsonplaceholder.typicode.com", id="jsonplaceholder"),
            pytest.param("https://api.github.com", id="github_api"),
            pytest.param("https://httpbin.org", id="httpbin"),
        ],
    )
    def test_allowed_domains_accepted(self, allowed_domain: str) -> None:
        """許可ドメインリスト内のドメインは受け入れられる

        Note:
            これらはテスト用・デモ用に許可されたドメイン。
            本番環境では環境変数ALLOWED_DOMAINSで制限可能。

            example.com系ドメインはRFC 2606で予約済みだが、
            DNS解決に失敗するためFail-Closed動作でブロックされる。
            設定ファイル内でexample.comを許可していても、
            実際のリクエスト時はDNS解決できないためブロックされる。
        """
        config = APIConfig(base_url=allowed_domain)
        assert config.base_url == allowed_domain.rstrip("/")

    @pytest.mark.parametrize(
        ("ipv6_address", "expected_private"),
        [
            # IPv6ループバック
            pytest.param("::1", True, id="ipv6_loopback"),
            # IPv6ユニークローカル（RFC 4193）
            pytest.param("fc00::1", True, id="ipv6_unique_local_fc00"),
            pytest.param("fd00::1", True, id="ipv6_unique_local_fd00"),
            # IPv6リンクローカル（RFC 4291）
            pytest.param("fe80::1", True, id="ipv6_link_local"),
            # IPv4-mapped IPv6（バイパス攻撃対策）
            pytest.param("::ffff:192.168.1.1", True, id="ipv4_mapped_private"),
            pytest.param("::ffff:127.0.0.1", True, id="ipv4_mapped_loopback"),
            # パブリックIPv6（False = 許可候補）
            pytest.param("2001:4860:4860::8888", False, id="google_dns_ipv6"),
        ],
    )
    def test_is_private_ip_ipv6_detection(self, ipv6_address: str, expected_private: bool) -> None:
        """IPv6プライベートIPの検出

        Security Rationale:
            IPv4-mapped IPv6（::ffff:x.x.x.x）を使ったSSRFバイパス攻撃を防止。
            例: ::ffff:192.168.1.1 は実質的に192.168.1.1と同じ。
        """
        result = is_private_ip(ipv6_address)
        assert result == expected_private, (
            f"Expected is_private_ip({ipv6_address}) == {expected_private}"
        )

    @pytest.mark.parametrize(
        ("boundary_ip", "expected_private", "description"),
        [
            # 10.0.0.0/8 境界
            pytest.param("10.0.0.0", True, "10.x.x.x range start", id="private_10_start"),
            pytest.param("10.255.255.255", True, "10.x.x.x range end", id="private_10_end"),
            pytest.param("9.255.255.255", False, "just below 10.x.x.x", id="below_private_10"),
            pytest.param("11.0.0.0", False, "just above 10.x.x.x", id="above_private_10"),
            # 172.16.0.0/12 境界
            pytest.param("172.16.0.0", True, "172.16-31 start", id="private_172_start"),
            pytest.param("172.31.255.255", True, "172.16-31 end", id="private_172_end"),
            pytest.param("172.15.255.255", False, "just below 172.16", id="below_private_172"),
            pytest.param("172.32.0.0", False, "just above 172.31", id="above_private_172"),
            # 192.168.0.0/16 境界
            pytest.param("192.168.0.0", True, "192.168 start", id="private_192_start"),
            pytest.param("192.168.255.255", True, "192.168 end", id="private_192_end"),
            pytest.param("192.167.255.255", False, "just below 192.168", id="below_private_192"),
            pytest.param("192.169.0.0", False, "just above 192.168", id="above_private_192"),
            # 127.0.0.0/8 境界（ループバック）
            pytest.param("127.0.0.1", True, "standard loopback", id="loopback_standard"),
            pytest.param("127.255.255.255", True, "loopback end", id="loopback_end"),
        ],
    )
    def test_is_private_ip_boundary_values(
        self,
        boundary_ip: str,
        expected_private: bool,
        description: str,
    ) -> None:
        """プライベートIP範囲の境界値テスト

        Security Rationale:
            境界付近のIPアドレスで正しくプライベート/パブリックを
            判定できることを確認し、Off-by-oneエラーを防止。
        """
        result = is_private_ip(boundary_ip)
        assert result == expected_private, (
            f"Boundary test failed for {description}: "
            f"is_private_ip({boundary_ip}) should be {expected_private}"
        )

    def test_validate_base_url_ssrf_block_logs_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """SSRF Prevention: 許可ドメイン外のURLブロック時にwarningログを出力する

        Security Rationale:
            SSRF防止ブロックは重要なセキュリティイベントであるため、
            warningレベルのログで監査証跡を残す。
        """
        with caplog.at_level(logging.WARNING, logger="config.settings"):
            with pytest.raises(ValidationError):
                APIConfig(base_url="https://evil.attacker.com/api")

        assert any("SSRF Prevention" in record.message for record in caplog.records), (
            "SSRF防止ブロック時にwarningログが出力されるべき"
        )


class TestResolveHostname(DNSCacheClearMixin):
    """_resolve_hostname/_resolve_hostname_cached関数のDNS解決テスト

    Security Rationale:
        DNS解決結果のキャッシュ動作とエラーハンドリングを検証し、
        ネットワーク障害時の安全なフォールバック（None返却）を保証する。

    Design Note:
        _resolve_hostname: ラッパー関数。失敗時にNoneを返す公開インターフェース。
        _resolve_hostname_cached: LRUキャッシュ付き内部関数。成功時のみキャッシュ。
    """

    def test_resolve_hostname_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DNS解決成功時に正しいIPアドレス文字列を返す"""
        monkeypatch.setattr(socket, "gethostbyname", lambda _: "93.184.216.34")

        result = _resolve_hostname("example.com")

        assert result == "93.184.216.34"

    def test_resolve_hostname_failure_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DNS解決失敗（OSError）時にNoneを返す（キャッシュされないこと含む）

        設計保証: lru_cacheは例外をキャッシュしないため、一時的なDNS障害後に
        再試行が可能であることを call_count == 2 で明示的に検証する。
        これにより「成功のみキャッシュ」設計の回帰防止テストとなる。
        """
        call_count = 0

        def raise_os_error(hostname: str) -> str:
            nonlocal call_count
            call_count += 1
            raise OSError(f"Name resolution failed: {hostname}")

        monkeypatch.setattr(socket, "gethostbyname", raise_os_error)

        result1 = _resolve_hostname("nonexistent.invalid")
        result2 = _resolve_hostname("nonexistent.invalid")

        assert result1 is None
        assert result2 is None
        # 重要: 失敗がキャッシュされていないことを検証（2回とも gethostbyname が呼ばれる）
        # もし失敗をキャッシュする実装に退行した場合、call_count == 1 になりこのテストで検出できる
        assert call_count == 2, (
            f"DNS failure should NOT be cached by lru_cache. "
            f"gethostbyname should be called twice, but was called {call_count} time(s)."
        )

    def test_resolve_hostname_cache_hit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """2回目の呼び出しでキャッシュヒット（socket.gethostbynameが1回しか呼ばれない）"""
        call_count = 0

        def counting_resolver(hostname: str) -> str:
            nonlocal call_count
            call_count += 1
            return "10.0.0.1"

        monkeypatch.setattr(socket, "gethostbyname", counting_resolver)

        result1 = _resolve_hostname("cached.example.com")
        result2 = _resolve_hostname("cached.example.com")

        assert result1 == "10.0.0.1"
        assert result2 == "10.0.0.1"
        assert call_count == 1, (
            f"gethostbyname should be called once due to cache, but was called {call_count} times"
        )

    def test_resolve_hostname_cache_clear(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """cache_clear()後に再度DNS解決が実行される"""
        call_count = 0

        def counting_resolver(hostname: str) -> str:
            nonlocal call_count
            call_count += 1
            return "10.0.0.2"

        monkeypatch.setattr(socket, "gethostbyname", counting_resolver)

        _resolve_hostname("cleared.example.com")
        assert call_count == 1

        _resolve_hostname_cached.cache_clear()
        _resolve_hostname("cleared.example.com")
        assert call_count == 2, (
            f"gethostbyname should be called again after cache_clear(), "
            f"but total calls were {call_count}"
        )

    @pytest.mark.parametrize(
        "exc_factory",
        [
            lambda: UnicodeDecodeError("utf-8", b"\xff\xfe", 0, 1, "invalid byte"),
            lambda: UnicodeEncodeError(
                "ascii", "ÿþ.attacker.example", 0, 1, "ordinal not in range(128)"
            ),
            lambda: TypeError("embedded null byte"),
            lambda: OverflowError("host name is too long"),
        ],
        ids=["UnicodeDecodeError", "UnicodeEncodeError", "TypeError", "OverflowError"],
    )
    def test_resolve_hostname_security_exception_logs_warning(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
        exc_factory: Callable[[], Exception],
    ) -> None:
        """SSRF攻撃的ホスト名による例外発生時にSSRF証跡ログが出力される

        Security Rationale:
            UnicodeDecodeError/UnicodeEncodeError/TypeError/OverflowErrorは攻撃的な入力パターン（SSRF試行）を
            示すため、セキュリティインシデントの事後調査に必要なwarningレベルログを出力する。
            一時的なDNS障害（OSError）とはログレベルで明確に区別する。
        """

        def raise_exc(hostname: str) -> str:
            raise exc_factory()

        monkeypatch.setattr(socket, "gethostbyname", raise_exc)

        with caplog.at_level(logging.WARNING, logger="config.settings"):
            result = _resolve_hostname("invalid")

        assert result is None
        assert "SSRF試行の可能性" in caplog.text

    @pytest.mark.parametrize(
        ("exc_factory", "expected_log_message"),
        [
            pytest.param(
                lambda: socket.gaierror("Name resolution failed"),
                "DNS解決失敗",
                id="gaierror",
            ),
            pytest.param(
                lambda: socket.herror("Host resolution failed"),
                "DNS解決失敗",
                id="herror",
            ),
            pytest.param(
                lambda: OSError("Network error"),
                "予期しないネットワークエラー",
                id="os_error",
            ),
        ],
    )
    def test_resolve_hostname_network_exception_logs_warning(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
        exc_factory: Callable[[], Exception],
        expected_log_message: str,
    ) -> None:
        """ネットワーク関連例外時にwarningレベルでログが出力されNoneを返す

        Design Rationale:
            socket.gaierror/herror（DNS解決失敗）と汎用OSError（ネットワーク障害）は
            いずれもNone返却+warningログ出力だが、ログメッセージで区別する。
            各例外型を個別ケースとしてテストし、将来のリファクタリングで
            except節から誤って除外されないことを保証する（退行防止）。
        """

        def raise_exc(hostname: str) -> str:
            raise exc_factory()

        monkeypatch.setattr(socket, "gethostbyname", raise_exc)

        with caplog.at_level(logging.WARNING, logger="config.settings"):
            result = _resolve_hostname("nonexistent.invalid")

        assert result is None
        assert expected_log_message in caplog.text


# ── Boundary value + ALLOWED_DOMAINS tests ──


class TestTestConfigBoundaryValues:
    """TestConfig 数値フィールドの境界値テスト.

    SettingsTestConfig フィールド検証:
    - slow_test_threshold: ge=0.1 (float)
    - max_concurrent_requests: ge=1, le=50 (int)
    """

    @pytest.mark.parametrize(
        ("value", "expected_valid"),
        [
            pytest.param(0.09, False, id="slow_test_threshold_below_min"),
            pytest.param(0.1, True, id="slow_test_threshold_at_min"),
            pytest.param(5.0, True, id="slow_test_threshold_default"),
        ],
    )
    def test_slow_test_threshold_boundary(self, value: float, expected_valid: bool) -> None:
        """slow_test_threshold: ge=0.1 境界値検証"""
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
        """max_concurrent_requests: ge=1, le=50 境界値検証"""
        if expected_valid:
            config = SettingsTestConfig(max_concurrent_requests=value)
            assert config.max_concurrent_requests == value
        else:
            with pytest.raises(ValidationError):
                SettingsTestConfig(max_concurrent_requests=value)


class TestAllowedDomainsEnvOverride:
    """ALLOWED_DOMAINS 環境変数 override テスト.

    _get_allowed_domains() は環境変数 ALLOWED_DOMAINS を参照し、
    カンマ区切りで許可ドメインを上書き可能。

    重要な制約 (開発者向け注意):
        モジュールレベル変数 ALLOWED_DOMAINS (config/settings.py L59)
        は module import 時に _get_allowed_domains() の戻り値で確定する。
        validate_base_url() は ALLOWED_DOMAINS 変数を参照するため、
        起動後 (= import 後) の monkeypatch.setenv による環境変数変更は
        validate_base_url() の挙動に反映されない。

        テストで動的に変更する場合は以下のいずれかを使う:
        1. _get_allowed_domains() を直接呼ぶ (本クラスの既存テスト方式)
        2. importlib.reload(config.settings) でモジュール再読み込み
        3. モジュールインポート前に環境変数を設定 (pytest-env 等)

        本制約の保護テストは test_allowed_domains_override_does_not_affect_validate_base_url
        を参照。
    """

    def test_allowed_domains_env_override(self, monkeypatch):
        """環境変数 ALLOWED_DOMAINS で許可ドメインを上書き"""
        from config.settings import _get_allowed_domains

        monkeypatch.setenv("ALLOWED_DOMAINS", "custom.example.com,api.custom.com")
        result = _get_allowed_domains()
        assert isinstance(result, frozenset)
        assert result == frozenset({"custom.example.com", "api.custom.com"})

    def test_allowed_domains_env_empty_returns_default(self, monkeypatch):
        """環境変数未設定時はデフォルトドメインを返す"""
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
        """空白・空要素のみの ALLOWED_DOMAINS は deny-all (空セット) を返す"""
        from config.settings import _get_allowed_domains

        monkeypatch.setenv("ALLOWED_DOMAINS", value)
        result = _get_allowed_domains()
        assert result == frozenset()

    def test_allowed_domains_override_does_not_affect_validate_base_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ALLOWED_DOMAINS 動的変更は validate_base_url() に反映されない契約を保護する.

        config.settings.ALLOWED_DOMAINS は module-level で _get_allowed_domains() の戻り値で
        確定する (module import 時に1度のみ評価)。validate_base_url() は ALLOWED_DOMAINS を
        参照するため、起動後の monkeypatch.setenv("ALLOWED_DOMAINS", ...) は反映されない。

        本テストは「monkeypatch で custom ドメインを追加しても、APIConfig(base_url=) の
        バリデーションで ValidationError が出る」ことを確認し、この重要な制約を退行から保護する。
        """
        # custom.example.com を ALLOWED_DOMAINS に追加しても、
        # モジュールは既に評価済みのため反映されない
        monkeypatch.setenv("ALLOWED_DOMAINS", "custom.example.com")
        # validate_base_url() は ALLOWED_DOMAINS 既存値 (import時確定) を参照するため
        # custom.example.com は許可ドメインに含まれず ValidationError になる
        with pytest.raises(ValidationError):
            APIConfig(base_url="https://custom.example.com")
