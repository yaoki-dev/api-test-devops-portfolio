"""アプリケーション設定管理

学習目標:
- Pydantic Settingsを使った環境設定管理
- 環境ごとの設定分離パターン
- 設定値のバリデーション
- セキュリティベストプラクティス
"""

import ipaddress
import logging
import os
import socket
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# =============================================================================
# SSRF Prevention Configuration
# =============================================================================


def _get_allowed_domains() -> set[str]:
    """環境変数またはデフォルト値から許可ドメインリストを取得

    環境変数 ALLOWED_DOMAINS: カンマ区切りのドメインリスト
    例: ALLOWED_DOMAINS=api.example.com,api.test.com
    """
    env_domains = os.environ.get("ALLOWED_DOMAINS", "")
    if env_domains:
        return set(d.strip() for d in env_domains.split(",") if d.strip())

    # デフォルト: 本番用 + テスト用ドメイン
    return {
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


# 許可されたドメインリスト（環境変数で上書き可能）
ALLOWED_DOMAINS: set[str] = _get_allowed_domains()

# 危険なプライベートIPレンジ
PRIVATE_IP_RANGES: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),  # loopback
    ipaddress.ip_network("169.254.0.0/16"),  # link-local (AWS metadata)
    ipaddress.ip_network("::1/128"),  # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),  # IPv6 private
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
]


def _check_ip_private(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """IPアドレスがプライベートかチェック（IPv4-mapped IPv6対応）

    Security:
        IPv4-mapped IPv6（::ffff:x.x.x.x）を使ったSSRFバイパス攻撃を防止。
        例: ::ffff:192.168.1.1 は実質的に192.168.1.1と同じ。
    """
    # IPv4-mapped IPv6アドレスの検出と変換
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        # ::ffff:192.168.1.1 → 192.168.1.1 として評価
        ip = ip.ipv4_mapped

    return any(ip in network for network in PRIVATE_IP_RANGES)


@lru_cache(maxsize=256)
def _resolve_hostname(hostname: str) -> str | None:
    """ホスト名をDNS解決してIPアドレス文字列を返す（結果をキャッシュ）

    Args:
        hostname: 解決対象のホスト名

    Returns:
        解決されたIPアドレス文字列。失敗時はNone。

    Note:
        キャッシュサイズ256の根拠:
        - 本プロジェクトの許可ドメイン数は最大10程度
        - テスト中のユニークホスト名は約20-30種類
        - 256は実用上十分な余裕を持たせた値（メモリ消費は無視できる程度）
        - Python標準のlru_cacheデフォルト(128)の2倍で、
          将来的なドメイン追加にも対応

    Security:
        キャッシュポイズニングリスク評価:
        - プロセス内キャッシュのため、外部からの直接改ざんは不可能
        - DNS応答自体が汚染されている場合のリスクはキャッシュ有無に関わらず同一
          （初回解決時点で汚染されたIPが返る）
        - プロセス再起動でキャッシュはクリアされる
        - 長時間稼働サービスでは定期的なcache_clear()を検討
    """
    try:
        return socket.gethostbyname(hostname)
    except OSError:
        return None


def is_private_ip(hostname: str) -> bool:
    """ホスト名がプライベートIPまたはローカルアドレスかチェック

    Args:
        hostname: チェック対象のホスト名またはIPアドレス

    Returns:
        True: プライベート/ローカルIP, False: パブリックIP

    Security:
        - IPv4-mapped IPv6（::ffff:x.x.x.x）もプライベートIPとして検出
        - DNS解決失敗時はFail-Closed（ブロック）
        - DNS解決結果はLRUキャッシュ（256エントリ）で高速化

    """
    try:
        # IPアドレス形式の場合（DNS解決不要）
        ip = ipaddress.ip_address(hostname)
        return _check_ip_private(ip)
    except ValueError:
        # ホスト名の場合、DNS解決を試みる（キャッシュ付き）
        resolved = _resolve_hostname(hostname)
        if resolved is None:
            # DNS解決失敗は安全側に倒す（ブロック = Fail-Closed）
            # セキュリティ: SSRF攻撃防止のため、不明なホストはプライベートIPと見なす
            return True
        try:
            ip = ipaddress.ip_address(resolved)
            return _check_ip_private(ip)
        except ValueError:
            return True


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
    user_agent: str = Field(default="API-Test-Portfolio/0.1.0", description="User-Agentヘッダー")

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """ベースURLのバリデーション（SSRF Prevention対応）

        Security:
            - プライベートIP/ループバックアドレスをブロック
            - 許可されたドメインのみ許可（ALLOWED_DOMAINS）
            - AWS metadata endpoint (169.254.169.254) をブロック
        """
        if not v.startswith(("http://", "https://")):
            raise ValueError("Base URL must start with http:// or https://")

        # URLパース
        parsed = urlparse(v)
        hostname = parsed.hostname

        if not hostname:
            raise ValueError("Invalid URL: hostname not found")

        # SSRF Prevention: プライベートIPチェック
        if is_private_ip(hostname):
            raise ValueError(
                f"SSRF Prevention: Private/loopback IP addresses are not allowed: {hostname}",
            )

        # SSRF Prevention: 許可ドメインチェック
        if hostname not in ALLOWED_DOMAINS:
            raise ValueError(
                f"SSRF Prevention: Domain not in allowlist: {hostname}. "
                f"Allowed: {', '.join(sorted(ALLOWED_DOMAINS))}",
            )

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
        default=5.0,
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
    debug: bool = Field(default=True, description="デバッグモードの有効化")
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
                raise ValueError(f"environment の値が無効です: {v!r}。有効な値: {valid}") from None
        # NOTE: mode="before" のためPydantic型強制前に実行され、int/None等も到達可能。
        # Pydanticがmode="after"なら非str型は型強制段階で排除されるが、
        # mode="before"では生の値を受け取るため、この分岐は防御的コードとして機能する。
        raise ValueError(
            f"environment には str または Environment を指定してください。"
            f"受け取った型: {type(v).__name__!r}, 値: {v!r}"
        )

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """本番・ステージング環境でのシークレット存在チェック

        Security:
            本番環境（ENVIRONMENT=production）およびステージング（ENVIRONMENT=staging）では、
            api_keyまたはjwt_secretの少なくとも一方が必須。
            未設定の場合はValueErrorを発生させ、サイレント失敗を防止。
            ステージングは本番と同等のインフラ・データを扱うため同一ポリシーを適用。

        Note:
            開発/テスト環境ではシークレットなしで動作可能。

        """
        if self.environment in {Environment.PRODUCTION, Environment.STAGING}:
            if self.security.api_key is None and self.security.jwt_secret is None:
                raise ValueError(
                    f"{self.environment.value.capitalize()} environment requires at least one of: "
                    "SECURITY__API_KEY or SECURITY__JWT_SECRET",
                )
        return self

    @model_validator(mode="after")
    def validate_production_https(self) -> "Settings":
        """本番・ステージング環境でのHTTPS強制

        Security:
            本番（ENVIRONMENT=production）およびステージング（ENVIRONMENT=staging）では、
            HTTPS接続を強制し平文HTTP通信を禁止。
            OWASP A02: Cryptographic Failures対策。
            ステージングは本番と同等のインフラ・データを扱うため同一ポリシーを適用。

        Note:
            開発/テスト環境ではHTTP接続を許可（ローカル開発用）。
        """
        if self.environment in {Environment.PRODUCTION, Environment.STAGING}:
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
settings = get_settings()

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
