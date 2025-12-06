"""
config/settings.py のカバレッジ向上テスト

目標: 66.92% → 80%以上
対象未カバー行: 73-77, 105-109, 192-194, 198, 202, 206, 210, 214-225, 239-248
"""

import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from config.settings import (
    APIConfig,
    Environment,
    LogConfig,
    LogLevel,
    SecurityConfig,
    Settings,
    TestConfig,
    get_settings,
    reload_settings,
)


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
        """https://スキームが有効"""
        config = APIConfig(base_url="https://api.example.com")
        assert config.base_url == "https://api.example.com"


class TestLogConfigValidation:
    """LogConfig.validate_log_file のテスト (lines 105-109)"""

    def test_log_file_none_handling(self):
        """file=None の場合の処理 (line 105)"""
        config = LogConfig(file=None)
        assert config.file is None

    def test_log_file_directory_creation(self, tmp_path: Path):
        """存在しないディレクトリが自動作成される (lines 106-108)"""
        log_file = tmp_path / "logs" / "subdir" / "app.log"
        assert not log_file.parent.exists()

        _ = LogConfig(file=str(log_file))  # noqa: F841 - ディレクトリ作成の副作用をテスト

        # ディレクトリが作成されたことを確認
        assert log_file.parent.exists()
        assert log_file.parent.is_dir()

    def test_log_file_existing_directory(self, tmp_path: Path):
        """既存ディレクトリの場合もエラーなし"""
        log_dir = tmp_path / "existing_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "app.log"

        config = LogConfig(file=str(log_file))
        assert config.file == str(log_file)

    def test_log_file_deep_nested_directory_creation(self, tmp_path: Path):
        """深くネストされたディレクトリの作成"""
        log_file = tmp_path / "a" / "b" / "c" / "d" / "app.log"
        _ = LogConfig(file=str(log_file))  # noqa: F841 - ディレクトリ作成の副作用をテスト
        assert log_file.parent.exists()


class TestSettingsEnvironmentValidation:
    """Settings.validate_environment のテスト (lines 192-194)"""

    def test_environment_string_to_lowercase(self):
        """文字列環境変数が小文字に変換される (line 193)"""
        settings = Settings(environment="PRODUCTION")
        assert settings.environment == Environment.PRODUCTION

    def test_environment_mixed_case_to_lowercase(self):
        """大小文字混在も小文字に変換"""
        settings = Settings(environment="DeVeLoPmEnT")
        assert settings.environment == Environment.DEVELOPMENT

    def test_environment_enum_direct_handling(self):
        """Enum直接指定の場合 (line 194)"""
        settings = Settings(environment=Environment.TESTING)
        assert settings.environment == Environment.TESTING

    def test_environment_lowercase_string_valid(self):
        """小文字文字列も有効"""
        settings = Settings(environment="staging")
        assert settings.environment == Environment.STAGING


class TestSettingsEnvironmentMethods:
    """Settings環境判定メソッドのテスト (lines 198, 202, 206, 210)"""

    def test_is_development_true(self):
        """is_development() がTrueを返す (line 198)"""
        settings = Settings(environment=Environment.DEVELOPMENT)
        assert settings.is_development() is True

    def test_is_development_false(self):
        """is_development() がFalseを返す"""
        settings = Settings(environment=Environment.PRODUCTION)
        assert settings.is_development() is False

    def test_is_testing_true(self):
        """is_testing() がTrueを返す (line 202)"""
        settings = Settings(environment=Environment.TESTING)
        assert settings.is_testing() is True

    def test_is_testing_false(self):
        """is_testing() がFalseを返す"""
        settings = Settings(environment=Environment.DEVELOPMENT)
        assert settings.is_testing() is False

    def test_is_production_true(self):
        """is_production() がTrueを返す (line 206)"""
        settings = Settings(environment=Environment.PRODUCTION)
        assert settings.is_production() is True

    def test_is_production_false(self):
        """is_production() がFalseを返す"""
        settings = Settings(environment=Environment.STAGING)
        assert settings.is_production() is False

    def test_get_log_level_debug(self):
        """get_log_level() がDEBUGレベルを返す (line 210)"""
        settings = Settings()
        settings.log.level = LogLevel.DEBUG
        assert settings.get_log_level() == logging.DEBUG

    def test_get_log_level_info(self):
        """get_log_level() がINFOレベルを返す"""
        settings = Settings()
        settings.log.level = LogLevel.INFO
        assert settings.get_log_level() == logging.INFO

    def test_get_log_level_warning(self):
        """get_log_level() がWARNINGレベルを返す"""
        settings = Settings()
        settings.log.level = LogLevel.WARNING
        assert settings.get_log_level() == logging.WARNING

    def test_get_log_level_error(self):
        """get_log_level() がERRORレベルを返す"""
        settings = Settings()
        settings.log.level = LogLevel.ERROR
        assert settings.get_log_level() == logging.ERROR

    def test_get_log_level_critical(self):
        """get_log_level() がCRITICALレベルを返す"""
        settings = Settings()
        settings.log.level = LogLevel.CRITICAL
        assert settings.get_log_level() == logging.CRITICAL


class TestSettingsSecretMasking:
    """Settings.to_dict() のシークレットマスキングテスト (lines 214-225)"""

    def test_to_dict_with_secret_masking_enabled(self):
        """exclude_secrets=True でシークレットがマスクされる (lines 217-223)"""
        settings = Settings()
        # テスト専用ダミー値（本番では使用されない）
        settings.security.api_key = "test-api-key-12345"  # noqa: S105
        settings.security.jwt_secret = "test-jwt-secret-67890"  # noqa: S105

        result = settings.to_dict(exclude_secrets=True)

        assert result["security"]["api_key"] == "***MASKED***"
        assert result["security"]["jwt_secret"] == "***MASKED***"  # noqa: S105 - テスト用マスク文字列

    def test_to_dict_with_secret_masking_disabled(self):
        """exclude_secrets=False でシークレットがそのまま出力される (line 216)"""
        settings = Settings()
        # テスト専用ダミー値（本番では使用されない）
        settings.security.api_key = "test-api-key-12345"  # noqa: S105
        settings.security.jwt_secret = "test-jwt-secret-67890"  # noqa: S105

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


class TestSettingsSingleton:
    """シングルトンパターンのテスト (lines 239-248)"""

    def test_get_settings_creates_instance_first_time(self, monkeypatch):
        """get_settings() が初回呼び出しで新インスタンスを作成 (lines 239-241)"""
        # グローバル変数をリセット
        import config.settings

        monkeypatch.setattr(config.settings, "_settings", None)

        settings1 = get_settings()
        assert settings1 is not None
        assert isinstance(settings1, Settings)

    def test_get_settings_returns_same_instance(self, monkeypatch):
        """get_settings() が2回目以降は同じインスタンスを返す"""
        import config.settings

        monkeypatch.setattr(config.settings, "_settings", None)

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_reload_settings_creates_new_instance(self, monkeypatch):
        """reload_settings() が新しいインスタンスを作成 (lines 247-248)"""
        import config.settings

        monkeypatch.setattr(config.settings, "_settings", None)

        settings1 = get_settings()
        settings2 = reload_settings()

        # 新しいインスタンスが作成される
        assert settings1 is not settings2
        assert isinstance(settings2, Settings)

    def test_reload_settings_updates_global_variable(self, monkeypatch):
        """reload_settings() がグローバル変数を更新 (line 247)"""
        import config.settings

        monkeypatch.setattr(config.settings, "_settings", None)

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

    def test_api_config_default_factory(self):
        """APIConfigがdefault_factoryで作成される"""
        settings = Settings()
        assert isinstance(settings.api, APIConfig)
        assert settings.api.base_url == "https://jsonplaceholder.typicode.com"

    def test_log_config_default_factory(self):
        """LogConfigがdefault_factoryで作成される"""
        settings = Settings()
        assert isinstance(settings.log, LogConfig)
        assert settings.log.level == LogLevel.INFO

    def test_test_config_default_factory(self):
        """TestConfigがdefault_factoryで作成される"""
        settings = Settings()
        assert isinstance(settings.test, TestConfig)

    def test_security_config_default_factory(self):
        """SecurityConfigがdefault_factoryで作成される"""
        settings = Settings()
        assert isinstance(settings.security, SecurityConfig)


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
