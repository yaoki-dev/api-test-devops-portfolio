"""
アプリケーション設定管理

学習目標:
- Pydantic Settingsを使った環境設定管理
- 環境ごとの設定分離パターン
- 設定値のバリデーション
- セキュリティベストプラクティス
"""

import logging
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, SecretStr, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# =============================================================================
# 環境定義
# =============================================================================


class Environment(str, Enum):
    """実行環境の定義"""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """ログレベルの定義"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(str, Enum):
    """ログフォーマットの定義"""

    CONSOLE = "console"
    JSON = "json"


# =============================================================================
# API設定モデル
# =============================================================================


class APIConfig(BaseModel):
    """API関連の設定"""

    base_url: str = Field(
        default="https://jsonplaceholder.typicode.com", description="APIのベースURL"
    )
    timeout: float = Field(
        default=30.0, ge=1.0, le=300.0, description="リクエストタイムアウト（秒）"
    )
    retry_count: int = Field(default=3, ge=0, le=10, description="リトライ回数")
    retry_delay: float = Field(
        default=1.0, ge=0.1, le=60.0, description="リトライ間隔（秒）"
    )
    max_connections: int = Field(default=10, ge=1, le=100, description="最大同時接続数")
    user_agent: str = Field(
        default="API-Test-Portfolio/0.1.0", description="User-Agentヘッダー"
    )

    @validator("base_url")
    def validate_base_url(cls, v):  # noqa: N805
        """ベースURLのバリデーション"""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Base URL must start with http:// or https://")
        if v.endswith("/"):
            v = v.rstrip("/")
        return v


# =============================================================================
# ログ設定モデル
# =============================================================================


class LogConfig(BaseModel):
    """ログ関連の設定"""

    level: LogLevel = Field(default=LogLevel.INFO, description="ログレベル")
    format: LogFormat = Field(default=LogFormat.JSON, description="ログフォーマット")
    file: str | None = Field(default=None, description="ログファイルのパス")
    max_size: int = Field(
        default=10 * 1024 * 1024,  # 10MB
        ge=1024,
        description="ログファイルの最大サイズ（バイト）",
    )
    backup_count: int = Field(
        default=5, ge=1, le=100, description="ローテーションするログファイル数"
    )
    console_output: bool = Field(default=True, description="コンソール出力の有効化")

    @validator("file")
    def validate_log_file(cls, v):  # noqa: N805
        """ログファイルパスのバリデーション"""
        if v is not None:
            log_path = Path(v)
            # ディレクトリが存在しない場合は作成
            log_path.parent.mkdir(parents=True, exist_ok=True)
        return v


# =============================================================================
# テスト設定モデル
# =============================================================================


class TestConfig(BaseModel):
    """テスト関連の設定"""

    slow_test_threshold: float = Field(
        default=5.0, ge=0.1, description="スローテストの判定閾値（秒）"
    )
    max_concurrent_requests: int = Field(
        default=5, ge=1, le=50, description="並行テストでの最大リクエスト数"
    )
    external_api_enabled: bool = Field(
        default=True, description="外部APIテストの有効化"
    )
    performance_test_enabled: bool = Field(
        default=False, description="パフォーマンステストの有効化"
    )
    security_test_enabled: bool = Field(
        default=False, description="セキュリティテストの有効化"
    )
    test_data_cleanup: bool = Field(
        default=True, description="テスト後のデータクリーンアップ"
    )


# =============================================================================
# セキュリティ設定モデル
# =============================================================================


class SecurityConfig(BaseModel):
    """セキュリティ関連の設定"""

    api_key: SecretStr | None = Field(default=None, description="API認証キー")
    jwt_secret: SecretStr | None = Field(  # noqa: S105
        default=None, description="JWT署名用シークレット"
    )
    allowed_hosts: list[str] = Field(
        default=["localhost", "127.0.0.1"], description="許可するホスト一覧"
    )
    rate_limit_requests: int = Field(
        default=100, ge=1, description="レート制限：リクエスト数"
    )
    rate_limit_window: int = Field(
        default=3600,  # 1時間
        ge=60,
        description="レート制限：時間窓（秒）",
    )
    enable_cors: bool = Field(default=False, description="CORS有効化")


# =============================================================================
# メイン設定クラス
# =============================================================================


class Settings(BaseSettings):
    """アプリケーション設定の統合管理"""

    model_config = SettingsConfigDict(
        # 環境変数の設定
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",  # API__BASE_URL のようなネスト記法
        case_sensitive=False,
        extra="ignore",  # 不明な設定値は無視
    )

    # 基本設定
    environment: Environment = Field(
        default=Environment.DEVELOPMENT, description="実行環境"
    )
    debug: bool = Field(default=True, description="デバッグモードの有効化")
    project_name: str = Field(
        default="API Test Portfolio", description="プロジェクト名"
    )
    version: str = Field(default="0.1.0", description="アプリケーションバージョン")

    # 各種設定
    api: APIConfig = Field(default_factory=APIConfig)
    log: LogConfig = Field(default_factory=LogConfig)
    test: TestConfig = Field(default_factory=TestConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    @validator("environment", pre=True)
    def validate_environment(cls, v):  # noqa: N805
        """環境設定のバリデーション"""
        if isinstance(v, str):
            v = v.lower()
        return v

    def is_development(self) -> bool:
        """開発環境判定"""
        return self.environment == Environment.DEVELOPMENT

    def is_testing(self) -> bool:
        """テスト環境判定"""
        return self.environment == Environment.TESTING

    def is_production(self) -> bool:
        """本番環境判定"""
        return self.environment == Environment.PRODUCTION

    def get_log_level(self) -> int:
        """ログレベルの取得（loggingモジュール用）"""
        return getattr(logging, self.log.level.value)

    def to_dict(self, exclude_secrets: bool = True) -> dict[str, Any]:
        """設定を辞書形式で出力"""
        data = self.model_dump()

        if exclude_secrets:
            # シークレット値をマスク
            if "security" in data:
                security = data["security"]
                if security.get("api_key"):
                    security["api_key"] = "***MASKED***"
                if security.get("jwt_secret"):
                    security["jwt_secret"] = "***MASKED***"  # noqa: S105

        return data


# =============================================================================
# グローバル設定インスタンス
# =============================================================================

# シングルトンパターンで設定を管理
_settings: Settings | None = None


def get_settings() -> Settings:
    """設定インスタンスの取得（シングルトン）"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """設定の再読み込み（主にテスト用）"""
    global _settings
    _settings = Settings()
    return _settings


# 便利なエイリアス
settings = get_settings()


# =============================================================================
# 環境別設定の例
# =============================================================================


def get_development_settings() -> dict[str, Any]:
    """開発環境用設定の例"""
    return {
        "ENVIRONMENT": "development",
        "DEBUG": "true",
        "LOG__LEVEL": "DEBUG",
        "LOG__FORMAT": "console",
        "API__TIMEOUT": "30",
        "TEST__EXTERNAL_API_ENABLED": "true",
    }


def get_testing_settings() -> dict[str, Any]:
    """テスト環境用設定の例"""
    return {
        "ENVIRONMENT": "testing",
        "DEBUG": "false",
        "LOG__LEVEL": "DEBUG",
        "LOG__FORMAT": "console",
        "API__TIMEOUT": "10",
        "API__RETRY_COUNT": "1",
        "TEST__EXTERNAL_API_ENABLED": "false",
        "TEST__PERFORMANCE_TEST_ENABLED": "false",
    }


def get_production_settings() -> dict[str, Any]:
    """本番環境用設定の例"""
    return {
        "ENVIRONMENT": "production",
        "DEBUG": "false",
        "LOG__LEVEL": "INFO",
        "LOG__FORMAT": "json",
        "LOG__FILE": "/var/log/app/api-test.log",
        "API__TIMEOUT": "60",
        "API__RETRY_COUNT": "3",
        "SECURITY__RATE_LIMIT_REQUESTS": "1000",
    }


# =============================================================================
# 学習ポイント:
#
# 1. Pydantic Settings活用:
#    - 型安全な設定管理
#    - 環境変数の自動読み込み
#    - バリデーション機能
#
# 2. 設定の階層化:
#    - 機能別の設定グループ化
#    - ネストした設定構造
#    - ドット記法での環境変数設定
#
# 3. セキュリティ考慮:
#    - SecretStr による機密情報の保護
#    - 設定出力時のマスキング
#    - 環境別のセキュリティレベル
#
# 4. 柔軟性と拡張性:
#    - Enum による選択肢制限
#    - バリデータによるカスタム検証
#    - 環境判定メソッド
#
# 5. 実用性:
#    - シングルトンパターン
#    - 設定の再読み込み機能
#    - 辞書変換機能
# =============================================================================
