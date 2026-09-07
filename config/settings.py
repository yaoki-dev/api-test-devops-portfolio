"""アプリケーション設定管理"""

import logging
import os
from enum import StrEnum
from pathlib import Path
from typing import Any, Self
from urllib.parse import urlparse

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# NOTE: utils/logger.py は config.settings に依存するため structlog は使用不可（循環インポート回避）
_logger = logging.getLogger(__name__)

# =============================================================================
# SSRF Prevention Configuration
# =============================================================================


def _get_allowed_domains() -> frozenset[str]:
    """環境変数またはデフォルト値から許可ドメインリストを取得

    環境変数 ALLOWED_DOMAINS: カンマ区切りのドメインリスト
    例: ALLOWED_DOMAINS=api.example.com,api.test.com
    空白のみの値は空集合を返す（deny-all）。
    """
    if "ALLOWED_DOMAINS" in os.environ:
        env_domains = os.environ["ALLOWED_DOMAINS"]
        # 余分な空白は除去する。空文字列・空白のみなら空集合になり、deny-all を維持する。
        domains = frozenset(d.strip() for d in env_domains.split(",") if d.strip())
        if not domains:
            # deny-all (全ドメイン拒否) は設定ミスの可能性が高いため起動時に警告する。
            # 空の許可リストは全 validate_base_url() を失敗させるため、サイレントな
            # 許可リスト空化 (例: .env の `ALLOWED_DOMAINS=`) を早期検出可能にする。
            _logger.warning(
                "ALLOWED_DOMAINS が空のため全ドメインを拒否します (deny-all)。"
                " SSRF 許可リストが意図せず空になっていないか確認してください。 raw value=%r",
                env_domains[:200],
            )
        return domains

    # デフォルト: 本番用 + テスト用ドメイン
    return frozenset(
        {
            # 本番用
            "jsonplaceholder.typicode.com",
            "api.github.com",
            "httpbin.org",
            # テスト用（example.com は RFC 2606 で予約済み）
            "example.com",
            "api.example.com",
            "test.example.com",
            "test-api.example.com",
        }
    )


# 許可されたドメインリスト（環境変数で上書き可能）
# NOTE: モジュール読み込み時に確定する。起動後の環境変数変更（monkeypatch等）は
# 再起動するまで validate_base_url() に反映されない。validate_base_url() は
# モジュール変数 ALLOWED_DOMAINS を直接参照するため、テストで動的に変更する場合は
# config.settings.ALLOWED_DOMAINS を monkeypatch するか、モジュールインポート前に
# 環境変数を設定すること。_get_allowed_domains() を呼ぶだけでは戻り値が
# ALLOWED_DOMAINS に再代入されず validate_base_url() の動作は変わらない。
# ALLOWED_DOMAINS は module-level で評価されるため、settings インスタンス生成タイミングではなく
# import 前の環境変数設定が必要。
ALLOWED_DOMAINS: frozenset[str] = _get_allowed_domains()


def _validate_base_url_with_allowed_domains(v: str, allowed_domains: frozenset[str]) -> str:
    """base_url 検証を切り出す。

    許可ドメインを注入できるようにして、Settings の全体初期化に依存しない
    直接テストを可能にする。
    """
    if not v.startswith(("http://", "https://")):
        raise ValueError("Base URL must start with http:// or https://")

    # URLパース
    parsed = urlparse(v)
    hostname = parsed.hostname

    if not hostname:
        raise ValueError("Invalid URL: hostname not found")

    # SSRF Prevention: 許可ドメインチェック
    if hostname not in allowed_domains:
        _logger.warning(
            "SSRF Prevention: Domain not in allowlist: %r. Allowed domains count: %d. "
            "Check ALLOWED_DOMAINS setting.",
            hostname[:200],
            len(allowed_domains),
        )
        raise ValueError("SSRF Prevention: Domain not in allowlist.")

    return v.rstrip("/")


# =============================================================================
# 環境定義
# =============================================================================


class Environment(StrEnum):
    """実行環境の定義"""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    """ログレベルの定義"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(StrEnum):
    """ログフォーマットの定義"""

    CONSOLE = "console"
    JSON = "json"


# =============================================================================
# API設定モデル
# =============================================================================


class APIConfig(BaseModel):
    """API関連の設定"""

    base_url: str = Field(
        default="https://jsonplaceholder.typicode.com",
        description="APIのベースURL",
    )
    timeout: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description="リクエストタイムアウト（秒）",
    )
    retry_count: int = Field(default=3, ge=0, le=10, description="リトライ回数")
    retry_delay: float = Field(default=1.0, ge=0.1, le=60.0, description="リトライ間隔（秒）")
    max_connections: int = Field(default=10, ge=1, le=100, description="最大同時接続数")
    user_agent: str = Field(
        default="api-test-devops-portfolio/0.1.0", description="User-Agentヘッダー"
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """ベースURLのバリデーション（SSRF Prevention対応）

        Security:
            - スキームは http:// または https:// のみ許可
            - 許可ドメインのみ許可（ALLOWED_DOMAINS allowlist）
            - allowlist 外のホストはすべてブロック

        Note:
            設定バリデータは allowlist-only の純粋関数（I/Oなし）として保つ。
            DNS 解決や private-IP 判定は構成読み込み時に実行しない
            （TOCTOU/DNS-rebinding 回避 + テスト決定性の確保）。
            SSRF 対策の境界は許可ドメイン制限であり、egress 層の
            private-IP guard は現時点では未実装。
        """
        return _validate_base_url_with_allowed_domains(v, ALLOWED_DOMAINS)


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
        default=5,
        ge=1,
        le=100,
        description="ローテーションするログファイル数",
    )
    console_output: bool = Field(default=True, description="コンソール出力の有効化")

    @field_validator("file")
    @classmethod
    def validate_log_file(cls, v: str | None) -> str | None:
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
        default=3.0,
        ge=0.1,
        description="スローテストの判定閾値（秒）",
    )
    max_concurrent_requests: int = Field(
        default=5,
        ge=1,
        le=50,
        description="並行テストでの最大リクエスト数",
    )
    external_api_enabled: bool = Field(default=True, description="外部APIテストの有効化")
    performance_test_enabled: bool = Field(
        default=False,
        description="パフォーマンステストの有効化",
    )
    security_test_enabled: bool = Field(default=False, description="セキュリティテストの有効化")
    test_data_cleanup: bool = Field(default=True, description="テスト後のデータクリーンアップ")


# =============================================================================
# セキュリティ設定モデル
# =============================================================================


class SecurityConfig(BaseModel):
    """セキュリティ関連の設定"""

    api_key: SecretStr | None = Field(default=None, description="API認証キー")
    jwt_secret: SecretStr | None = Field(
        default=None,
        description="JWT署名用シークレット",
    )
    allowed_hosts: list[str] = Field(
        default=["localhost", "127.0.0.1"],
        description="許可するホスト一覧",
    )
    rate_limit_requests: int = Field(default=100, ge=1, description="レート制限：リクエスト数")
    rate_limit_window: int = Field(
        default=3600,  # 1時間
        ge=60,
        description="レート制限：時間窓（秒）",
    )
    enable_cors: bool = Field(default=False, description="CORS有効化")


class SentryConfig(BaseModel):
    """Sentry関連の設定"""

    dsn: SecretStr = Field(default=SecretStr(""), description="Sentry DSN")
    enabled: bool = Field(default=False, description="Sentry有効化")
    environment: str | None = Field(
        default=None,
        description="環境名（未設定時はsettings.environmentを使用）",
    )
    traces_sample_rate: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="トレースサンプリングレート",
    )
    profiles_sample_rate: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="プロファイリングサンプリングレート",
    )
    send_default_pii: bool = Field(default=False, description="PII送信の有効化")


# =============================================================================
# メイン設定クラス
# =============================================================================


# 本番相当環境セット（production + staging）
# validate_production_secrets / validate_production_https / is_production_like で共有
_PRODUCTION_LIKE_ENVIRONMENTS: frozenset[Environment] = frozenset(
    {
        Environment.PRODUCTION,
        Environment.STAGING,
    }
)


class Settings(BaseSettings):
    """アプリケーション設定の統合管理"""

    # テスト用フォーマット問題：shorter line
    model_config = SettingsConfigDict(
        # 環境変数の設定
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",  # API__BASE_URL のようなネスト記法
        case_sensitive=False,
        extra="ignore",  # 不明な設定値は無視
    )

    # 基本設定
    environment: Environment = Field(default=Environment.DEVELOPMENT, description="実行環境")
    debug: bool = Field(default=False, description="デバッグモードの有効化")
    project_name: str = Field(default="API Test Portfolio", description="プロジェクト名")
    version: str = Field(default="0.1.0", description="アプリケーションバージョン")

    # 各種設定
    api: APIConfig = Field(default_factory=APIConfig)
    log: LogConfig = Field(default_factory=LogConfig)
    test: TestConfig = Field(default_factory=TestConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    sentry: SentryConfig = Field(default_factory=SentryConfig)

    @field_validator("environment", mode="before")
    @classmethod
    def validate_environment(cls, v: str | Environment) -> Environment:
        """環境設定のバリデーション

        Note:
            StrEnumはstrを継承するため isinstance(v, str) はEnumインスタンスにもTrueを返す。
            Enumインスタンスを先に判定し、strは正規化（strip + lower）してから
            Environmentコンストラクタで変換する。これにより末尾スペースやタイポを
            早期検出し、わかりやすいエラーメッセージを提供できる。

        Raises:
            ValueError: 無効な環境名（タイポ・末尾スペース含む）またはstr/Environment以外の型
        """
        # StrEnumはstrを継承するため、Enumインスタンスを先に判定して早期リターン
        if isinstance(v, Environment):
            return v
        if isinstance(v, str):
            normalized = v.strip().lower()
            try:
                return Environment(normalized)
            except ValueError:
                valid = [e.value for e in Environment]
                # from None: PydanticがValidationErrorでラップするため
                # 元のValueErrorチェーンを隠してエラーメッセージをクリーンに保つ
                raise ValueError(
                    f"Invalid environment value: {v!r}. Valid values: {valid}"
                ) from None
        # NOTE: mode="before" のためPydantic型強制前に実行され、int/None等も到達可能。
        # Pydanticがmode="after"なら非str型は型強制段階で排除されるが、
        # mode="before"では生の値を受け取るため、この分岐は防御的コードとして機能する。
        raise ValueError(
            f"environment must be a str or Environment. "
            f"Received type: {type(v).__name__!r}, value: {v!r}"
        )

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Self:
        """本番・ステージング環境でのシークレット存在チェック

        Security:
            本番環境（ENVIRONMENT=production）およびステージング（ENVIRONMENT=staging）では、
            api_keyまたはjwt_secretの少なくとも一方が必須。
            未設定の場合はValueErrorを発生させ、サイレント失敗を防止。
            ステージングは本番と同等のインフラ・データを扱うため同一ポリシーを適用。

        Note:
            開発/テスト環境ではシークレットなしで動作可能。

        """
        if self.environment in _PRODUCTION_LIKE_ENVIRONMENTS:
            if self.security.api_key is None and self.security.jwt_secret is None:
                raise ValueError(
                    f"{self.environment.value.capitalize()} environment requires at least one of: "
                    "SECURITY__API_KEY or SECURITY__JWT_SECRET",
                )
        return self

    @model_validator(mode="after")
    def validate_production_https(self) -> Self:
        """本番・ステージング環境でのHTTPS強制

        Security:
            本番（ENVIRONMENT=production）およびステージング（ENVIRONMENT=staging）では、
            HTTPS接続を強制し平文HTTP通信を禁止。
            OWASP A02: Cryptographic Failures対策。
            ステージングは本番と同等のインフラ・データを扱うため同一ポリシーを適用。

        Note:
            開発/テスト環境ではHTTP接続を許可（ローカル開発用）。
        """
        if self.environment in _PRODUCTION_LIKE_ENVIRONMENTS:
            if not self.api.base_url.startswith("https://"):
                raise ValueError(
                    f"{self.environment.value.capitalize()} environment requires HTTPS. "
                    "Set API__BASE_URL to an https:// URL.",
                )
        return self

    def is_development(self) -> bool:
        """開発環境判定"""
        return self.environment == Environment.DEVELOPMENT

    def is_testing(self) -> bool:
        """テスト環境判定"""
        return self.environment == Environment.TESTING

    def is_production(self) -> bool:
        """本番環境判定"""
        return self.environment == Environment.PRODUCTION

    def is_staging(self) -> bool:
        """ステージング環境判定"""
        return self.environment == Environment.STAGING

    def is_production_like(self) -> bool:
        """本番相当環境判定（production + staging）"""
        return self.environment in _PRODUCTION_LIKE_ENVIRONMENTS

    def get_log_level(self) -> int:
        """ログレベルの取得（logging/structlog共通）

        structlogはloggingモジュールのログレベル定数を使用するため、
        標準loggingの定数をそのまま返す。

        Returns:
            int: logging.DEBUG (10), INFO (20), WARNING (30), ERROR (40), CRITICAL (50)

        Example:
            >>> import structlog
            >>> structlog.configure(
            ...     wrapper_class=structlog.make_filtering_bound_logger(settings.get_log_level())
            ... )

        """
        # LogLevel Enum → logging定数への明示的マッピング（型安全）
        level_map: dict[LogLevel, int] = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL,
        }
        return level_map[self.log.level]

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

            # Sentry DSNをマスク（空文字列も含めてマスク）
            if "sentry" in data:
                sentry = data["sentry"]
                if "dsn" in sentry:
                    sentry["dsn"] = "***MASKED***"

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
# モジュールインポート時に ValidationError が発生すると ImportError として連鎖し
# 根本原因（環境変数のタイポ等）が隠蔽される。logging で根本原因を明示する。
try:
    settings = get_settings()
except Exception as e:  # noqa: BLE001  # ValidationError含む全設定エラーを捕捉（SystemExit等のBaseException除外済み）
    _logger.critical(
        "設定の初期化に失敗しました (type=%s)。環境変数を確認してください: %s",
        type(e).__name__,
        e,
    )
    raise
