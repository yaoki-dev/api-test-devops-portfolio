"""utils/logger.py のユニットテスト"""

import logging
from unittest.mock import MagicMock, patch

import pytest
import structlog
from structlog.testing import capture_logs

from config.settings import LogFormat
from utils.logger import get_logger

pytestmark = pytest.mark.unit


class TestGetLogger:
    def test_get_logger_returns_bound_logger(self) -> None:
        logger = get_logger(__name__)

        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")
        assert hasattr(logger, "debug")

    def test_get_logger_with_name(self) -> None:
        logger = get_logger("test.module.name")

        assert logger is not None

    def test_get_logger_without_name(self) -> None:
        logger = get_logger()

        assert logger is not None
        assert hasattr(logger, "info")


class TestStructlogConfiguration:
    def test_structlog_is_configured_after_get_logger(self) -> None:
        # 事前にリセット（テスト間の独立性確保）
        structlog.reset_defaults()

        # get_logger呼び出し前は未設定（reset後）
        # Note: reset_defaults()後でもis_configured()はTrueを返す場合がある
        # そのため、get_logger呼び出し後の状態のみ確認

        logger = get_logger(__name__)

        assert structlog.is_configured()
        assert logger is not None

    def test_lazy_initialization_only_once(self) -> None:
        structlog.reset_defaults()

        with patch("structlog.configure", wraps=structlog.configure) as mock_configure:
            logger1 = get_logger("module1")
            logger2 = get_logger("module2")
            logger3 = get_logger("module3")

        assert logger1 is not None
        assert logger2 is not None
        assert logger3 is not None
        mock_configure.assert_called_once()


class TestLogOutput:
    def test_structured_log_captures_event(self) -> None:
        with capture_logs() as captured:
            logger = structlog.get_logger()
            logger.info("test_event", user_id=123, action="login")

        assert len(captured) == 1
        assert captured[0]["event"] == "test_event"
        assert captured[0]["user_id"] == 123
        assert captured[0]["action"] == "login"

    def test_log_levels_filtering(self) -> None:
        """ログレベルフィルタリングが機能することを確認

        capture_logs() はプロセッサ連鎖をバイパスするが、レベルフィルタは
        wrapper_class（make_filtering_bound_logger）側で適用されるため維持される。
        よってフィルタ結果は現行グローバル設定の最小レベルに依存する。
        ここでは INFO を明示設定して、環境変数 LOG__LEVEL に依存しない
        決定的なテストにする（設定は finally で復元）。
        """
        original_config = structlog.get_config()
        structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.INFO))
        try:
            with capture_logs() as captured:
                logger = structlog.get_logger()
                logger.debug("debug_message")
                logger.info("info_message")
                logger.warning("warning_message")
                logger.error("error_message")

            events = [log["event"] for log in captured]
            assert "info_message" in events
            assert "warning_message" in events
            assert "error_message" in events
            assert "debug_message" not in events
        finally:
            structlog.configure(**original_config)


class TestLogFormat:
    @patch("utils.logger.get_settings")
    def test_console_format_configuration(self, mock_get_settings: MagicMock) -> None:
        mock_settings = mock_get_settings.return_value
        mock_settings.log.format = LogFormat.CONSOLE
        mock_settings.get_log_level.return_value = logging.INFO

        structlog.reset_defaults()

        logger = get_logger("test_console")

        assert logger is not None
        assert structlog.is_configured()

    @patch("utils.logger.get_settings")
    def test_json_format_configuration(self, mock_get_settings: MagicMock) -> None:
        mock_settings = mock_get_settings.return_value
        mock_settings.log.format = LogFormat.JSON
        mock_settings.get_log_level.return_value = logging.INFO

        structlog.reset_defaults()

        logger = get_logger("test_json")

        assert logger is not None
        assert structlog.is_configured()


class TestLoggerIntegration:
    def test_logger_works_with_api_client_pattern(self) -> None:
        logger = get_logger(__name__)

        with capture_logs() as captured:
            logger.info("api_client_initialized", base_url="https://example.com")
            logger.warning("server_error", status_code=503, method="GET", endpoint="/users")
            logger.error("all_retries_failed", method="GET", endpoint="/users")

        assert len(captured) >= 3

        events = [log["event"] for log in captured]
        assert "api_client_initialized" in events
        assert "server_error" in events
        assert "all_retries_failed" in events

    def test_logger_works_with_github_client_pattern(self) -> None:
        logger = get_logger(__name__)

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

        rate_limit_log = captured[0]
        assert rate_limit_log["remaining"] == 5

        retry_log = captured[1]
        assert retry_log["attempt"] == 2
        assert retry_log["status_code"] == 503
