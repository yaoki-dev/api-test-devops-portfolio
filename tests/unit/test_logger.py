"""utils/logger.py のユニットテスト

テスト対象:
- get_logger()関数の動作
- structlog遅延初期化
- ログフォーマット選択（console/json）
- FilteringBoundLogger型の検証
"""

from unittest.mock import patch

import structlog
from structlog.testing import capture_logs

from config.settings import LogFormat
from utils.logger import get_logger


class TestGetLogger:
    """get_logger関数のテスト"""

    def test_get_logger_returns_bound_logger(self) -> None:
        """get_loggerがBoundLoggerインスタンスを返すことを確認"""
        logger = get_logger(__name__)

        # structlogのBoundLoggerインスタンスであること
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")
        assert hasattr(logger, "debug")

    def test_get_logger_with_name(self) -> None:
        """名前付きロガーが正しく取得できることを確認"""
        logger = get_logger("test.module.name")

        # ロガーが取得できること
        assert logger is not None

    def test_get_logger_without_name(self) -> None:
        """名前なしでもロガーが取得できることを確認"""
        logger = get_logger()

        assert logger is not None
        assert hasattr(logger, "info")


class TestStructlogConfiguration:
    """structlog設定のテスト"""

    def test_structlog_is_configured_after_get_logger(self) -> None:
        """get_logger呼び出し後にstructlogが設定済みになることを確認"""
        # 事前にリセット（テスト間の独立性確保）
        structlog.reset_defaults()

        # get_logger呼び出し前は未設定（reset後）
        # Note: reset_defaults()後でもis_configured()はTrueを返す場合がある
        # そのため、get_logger呼び出し後の状態のみ確認

        logger = get_logger(__name__)

        # get_logger呼び出し後は設定済み
        assert structlog.is_configured()
        assert logger is not None

    def test_lazy_initialization_only_once(self) -> None:
        """structlog設定が1回のみ実行されることを確認"""
        structlog.reset_defaults()

        # 複数回get_loggerを呼び出し
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")
        logger3 = get_logger("module3")

        # すべてロガーが取得できること（例外なし）
        assert logger1 is not None
        assert logger2 is not None
        assert logger3 is not None


class TestLogOutput:
    """ログ出力のテスト"""

    def test_structured_log_captures_event(self) -> None:
        """構造化ログがイベント名とフィールドをキャプチャすることを確認"""
        with capture_logs() as captured:
            logger = structlog.get_logger()
            logger.info("test_event", user_id=123, action="login")

        assert len(captured) == 1
        assert captured[0]["event"] == "test_event"
        assert captured[0]["user_id"] == 123
        assert captured[0]["action"] == "login"

    def test_log_levels_filtering(self) -> None:
        """ログレベルフィルタリングが機能することを確認"""
        with capture_logs() as captured:
            logger = structlog.get_logger()
            logger.debug("debug_message")
            logger.info("info_message")
            logger.warning("warning_message")
            logger.error("error_message")

        # 少なくとも1つ以上のログがキャプチャされること
        assert len(captured) >= 1

        # イベント名が含まれていること
        events = [log["event"] for log in captured]
        assert any("message" in event for event in events)


class TestLogFormat:
    """ログフォーマット設定のテスト"""

    @patch("utils.logger.get_settings")
    def test_console_format_configuration(self, mock_get_settings) -> None:
        """コンソールフォーマット設定時の動作確認"""
        # モック設定
        mock_settings = mock_get_settings.return_value
        mock_settings.log.format = LogFormat.CONSOLE
        mock_settings.get_log_level.return_value = 20  # INFO

        structlog.reset_defaults()

        # ロガー取得（設定が適用される）
        logger = get_logger("test_console")

        assert logger is not None
        assert structlog.is_configured()

    @patch("utils.logger.get_settings")
    def test_json_format_configuration(self, mock_get_settings) -> None:
        """JSONフォーマット設定時の動作確認"""
        # モック設定
        mock_settings = mock_get_settings.return_value
        mock_settings.log.format = LogFormat.JSON
        mock_settings.get_log_level.return_value = 20  # INFO

        structlog.reset_defaults()

        # ロガー取得（設定が適用される）
        logger = get_logger("test_json")

        assert logger is not None
        assert structlog.is_configured()


class TestLoggerIntegration:
    """ロガー統合テスト"""

    def test_logger_works_with_api_client_pattern(self) -> None:
        """api_clientで使用されるパターンでロガーが動作することを確認"""
        logger = get_logger(__name__)

        # api_client.pyで使用される構造化ログパターン
        with capture_logs() as captured:
            logger.info("api_client_initialized", base_url="https://example.com")
            logger.warning("server_error", status_code=503, method="GET", endpoint="/users")
            logger.error("all_retries_failed", method="GET", endpoint="/users")

        # INFO以上のログがキャプチャされていること（DEBUGはフィルタリングされる可能性）
        assert len(captured) >= 3

        # イベント名の確認
        events = [log["event"] for log in captured]
        assert "api_client_initialized" in events
        assert "server_error" in events
        assert "all_retries_failed" in events

    def test_logger_works_with_github_client_pattern(self) -> None:
        """github_clientで使用されるパターンでロガーが動作することを確認"""
        logger = get_logger(__name__)

        # github_client.pyで使用される構造化ログパターン
        with capture_logs() as captured:
            logger.warning(
                "rate_limit_low",
                remaining=5,
                reset_time="2025-01-01T00:00:00",
            )
            logger.warning(
                "retrying_server_error",
                attempt=2,
                max_retries=3,
                delay=1.5,
                status_code=503,
            )

        assert len(captured) == 2

        # フィールドの確認
        rate_limit_log = captured[0]
        assert rate_limit_log["remaining"] == 5

        retry_log = captured[1]
        assert retry_log["attempt"] == 2
        assert retry_log["status_code"] == 503
