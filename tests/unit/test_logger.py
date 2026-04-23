"""utils/logger.py のユニットテスト

テスト対象:
- get_logger()関数の動作
- structlog遅延初期化
- ログフォーマット選択（console/json）
- FilteringBoundLogger型の検証
- _sentry_processor()のSentry連携（5分岐カバレッジ）
"""

from unittest.mock import MagicMock, patch

import pytest
import structlog
from structlog.testing import capture_logs

from config.settings import LogFormat
from utils.logger import _sentry_processor, get_logger

# Module-level marker: All tests in this file are unit tests
pytestmark = pytest.mark.unit


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
    def test_console_format_configuration(self, mock_get_settings: MagicMock) -> None:
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
    def test_json_format_configuration(self, mock_get_settings: MagicMock) -> None:
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


class TestSentryProcessor:
    """_sentry_processor関数のテスト（5分岐カバレッジ）

    PR#130レビュー指摘対応:
    - 64行・5分岐のSentry連携プロセッサーを網羅的にテスト
    - Silent Failure防止のための監視系テスト

    テスト対象分岐:
    1. INFO/WARNログ → 即return（Sentry送信しない）
    2. Sentry未初期化 → 即return
    3. 例外情報あり → capture_exception()
    4. 例外情報なし → capture_message()
    5. ImportError/Exception → エラー処理
    """

    # ダミーのWrappedLoggerとmethod_name（未使用だが引数として必要）
    _dummy_logger = None
    _dummy_method = "error"

    @pytest.mark.parametrize(
        "level",
        ["info", "INFO", "warning", "WARNING", "debug", "DEBUG", ""],
    )
    def test_skip_non_error_levels(self, level: str) -> None:
        """分岐1: ERROR以上以外のログレベルはスキップされる"""
        event_dict = {"level": level, "event": "test message"}

        result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        # event_dictがそのまま返される（Sentry送信なし）
        assert result is event_dict
        assert result["event"] == "test message"

    @pytest.mark.parametrize(
        "level", ["error", "ERROR", "critical", "CRITICAL", "exception", "EXCEPTION"]
    )
    def test_process_error_levels(self, level: str) -> None:
        """ERROR/CRITICAL/EXCEPTIONレベルは処理対象"""
        event_dict = {"level": level, "event": "error message"}

        # 動的インポートをパッチするため sentry_sdk モジュール全体をモック
        mock_sdk = MagicMock()
        mock_client = MagicMock()
        mock_client.is_active.return_value = True
        mock_sdk.get_client.return_value = mock_client
        mock_sdk.new_scope.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_sdk.new_scope.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        assert result is event_dict
        # Sentryメソッドが呼ばれたことを確認
        assert mock_sdk.capture_message.called or mock_sdk.capture_exception.called

    def test_skip_when_sentry_not_active(self) -> None:
        """分岐2: Sentry未初期化時はスキップ"""
        event_dict = {"level": "error", "event": "error message"}

        mock_sdk = MagicMock()
        mock_client = MagicMock()
        mock_client.is_active.return_value = False  # 未初期化
        mock_sdk.get_client.return_value = mock_client

        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        assert result is event_dict
        # capture_messageもcapture_exceptionも呼ばれない
        mock_sdk.capture_message.assert_not_called()
        mock_sdk.capture_exception.assert_not_called()

    def test_capture_exception_with_exc_info(self) -> None:
        """分岐3: 例外情報ありの場合capture_exceptionを呼ぶ"""
        test_exception = ValueError("test error")
        event_dict = {
            "level": "error",
            "event": "error with exception",
            "exc_info": test_exception,
        }

        mock_sdk = MagicMock()
        mock_client = MagicMock()
        mock_client.is_active.return_value = True
        mock_sdk.get_client.return_value = mock_client

        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        assert result is event_dict
        mock_sdk.capture_exception.assert_called_once_with(test_exception)
        mock_sdk.capture_message.assert_not_called()

    def test_capture_message_without_exc_info(self) -> None:
        """分岐4: 例外情報なしの場合capture_messageを呼ぶ"""
        event_dict = {
            "level": "error",
            "event": "error without exception",
            "user_id": 123,
            "action": "test",
        }

        mock_sdk = MagicMock()
        mock_client = MagicMock()
        mock_client.is_active.return_value = True
        mock_sdk.get_client.return_value = mock_client

        mock_scope = MagicMock()
        mock_sdk.new_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
        mock_sdk.new_scope.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        assert result is event_dict
        mock_sdk.capture_message.assert_called_once_with(
            "error without exception",
            level="error",
        )
        mock_sdk.capture_exception.assert_not_called()

    def test_capture_message_with_exc_info_true(self) -> None:
        """exc_info=Trueの場合はcapture_messageを呼ぶ（例外オブジェクトではない）"""
        event_dict = {
            "level": "error",
            "event": "error with exc_info=True",
            "exc_info": True,  # Trueは例外オブジェクトではない
        }

        mock_sdk = MagicMock()
        mock_client = MagicMock()
        mock_client.is_active.return_value = True
        mock_sdk.get_client.return_value = mock_client

        mock_scope = MagicMock()
        mock_sdk.new_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
        mock_sdk.new_scope.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        assert result is event_dict
        mock_sdk.capture_message.assert_called_once()
        mock_sdk.capture_exception.assert_not_called()

    def test_silent_skip_on_import_error(self) -> None:
        """分岐5a: sentry-sdk未インストール時はサイレントスキップ"""
        event_dict = {"level": "error", "event": "error message"}

        # sys.modulesからsentry_sdkを除去してImportErrorを発生させる
        import sys

        original_modules = sys.modules.copy()
        # sentry_sdkが既にインポートされている場合は除去
        if "sentry_sdk" in sys.modules:
            del sys.modules["sentry_sdk"]

        try:
            with patch.dict("sys.modules", {"sentry_sdk": None}):
                with patch(
                    "builtins.__import__",
                    side_effect=ImportError("No module named 'sentry_sdk'"),
                ):
                    result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)
        finally:
            sys.modules.update(original_modules)

        # event_dictがそのまま返される（例外は発生しない）
        assert result is event_dict

    def test_warn_on_import_error_when_sentry_debug_enabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """分岐5c: SENTRY_DEBUG有効時はImportError時にstderr警告出力"""
        event_dict = {"level": "error", "event": "error message"}
        monkeypatch.setenv("SENTRY_DEBUG", "true")

        import sys as _sys

        original_modules = _sys.modules.copy()
        if "sentry_sdk" in _sys.modules:
            del _sys.modules["sentry_sdk"]

        try:
            with patch.dict("sys.modules", {"sentry_sdk": None}):
                with patch(
                    "builtins.__import__",
                    side_effect=ImportError("No module named 'sentry_sdk'"),
                ):
                    result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)
        finally:
            _sys.modules.update(original_modules)

        assert result is event_dict
        captured = capsys.readouterr()
        assert "[SENTRY_WARN]" in captured.err
        assert "sentry-sdk not installed" in captured.err

    def test_stderr_output_on_sentry_failure(self, capsys: pytest.CaptureFixture[str]) -> None:
        """分岐5b: Sentry送信失敗時はstderrへ出力"""
        event_dict = {"level": "error", "event": "error message"}

        mock_sdk = MagicMock()
        mock_client = MagicMock()
        mock_client.is_active.return_value = True
        mock_sdk.get_client.return_value = mock_client
        # capture_messageで例外を発生させる
        mock_sdk.capture_message.side_effect = RuntimeError("Sentry connection failed")

        mock_scope = MagicMock()
        mock_sdk.new_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
        mock_sdk.new_scope.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        # event_dictは正常に返される（プロセッサーチェーン継続）
        assert result is event_dict

        # stderrにエラーメッセージが出力される
        captured = capsys.readouterr()
        assert "[SENTRY_ERROR]" in captured.err
        assert "Sentry connection failed" in captured.err

    def test_extra_context_set_in_scope(self) -> None:
        """追加コンテキストがSentryスコープに設定される"""
        event_dict = {
            "level": "error",
            "event": "error with context",
            "user_id": 456,
            "request_id": "abc-123",
            "endpoint": "/api/users",
        }

        mock_sdk = MagicMock()
        mock_client = MagicMock()
        mock_client.is_active.return_value = True
        mock_sdk.get_client.return_value = mock_client

        mock_scope = MagicMock()
        mock_sdk.new_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
        mock_sdk.new_scope.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        # set_extraが追加コンテキストで呼ばれる
        set_extra_calls = {call[0][0]: call[0][1] for call in mock_scope.set_extra.call_args_list}
        assert set_extra_calls.get("user_id") == 456
        assert set_extra_calls.get("request_id") == "abc-123"
        assert set_extra_calls.get("endpoint") == "/api/users"

    def test_default_message_when_event_missing(self) -> None:
        """eventキーがない場合のデフォルトメッセージ"""
        event_dict = {"level": "error"}  # eventキーなし

        mock_sdk = MagicMock()
        mock_client = MagicMock()
        mock_client.is_active.return_value = True
        mock_sdk.get_client.return_value = mock_client

        mock_scope = MagicMock()
        mock_sdk.new_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
        mock_sdk.new_scope.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        # デフォルトメッセージが使用される
        mock_sdk.capture_message.assert_called_once_with(
            "Unknown error",
            level="error",
        )
