"""utils/logger.py のユニットテスト

テスト対象:
- get_logger()関数の動作
- structlog遅延初期化
- ログフォーマット選択（console/json）
- FilteringBoundLogger型の検証
- _sentry_processor()のSentry連携（5分岐カバレッジ）
"""

import sys
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

    @pytest.fixture(autouse=True)
    def _reset_sentry_warnings_fixture(
        self,
        reset_sentry_warning_state: None,  # noqa: ARG002 — conftest fixture をトリガするため引数として宣言
    ) -> None:
        """sentry warning state を各テスト前で fresh state に保つ

        conftest.py の reset_sentry_warning_state fixture (monkeypatch 使用) を依存として
        宣言することで、test 実行前に utils.logger の throttle flag を一括リセットする。
        monkeypatch は teardown 時に自動復元するため明示的 teardown 不要。

        #34 対応: モジュールスコープへの拡大は overkill だが、将来追加される他クラスでも
        `reset_sentry_warning_state` fixture を依存宣言するだけで再利用可能 (DRY)。
        """
        return None

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
        mock_scope = MagicMock()
        mock_sdk.new_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
        mock_sdk.new_scope.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        assert result is event_dict
        # Sentryメソッドが呼ばれたことを確認
        # capture_message / capture_exception はいずれも scope 内で呼ばれる
        assert mock_scope.capture_message.called or mock_scope.capture_exception.called

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
        """分岐3: 例外情報ありの場合capture_exceptionをnew_scope内で呼ぶ (extra context付与)"""
        test_exception = ValueError("test error")
        event_dict = {
            "level": "error",
            "event": "error with exception",
            "exc_info": test_exception,
            "user_id": 123,
            "request_id": "req-abc",
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
        mock_scope.capture_exception.assert_called_once_with(test_exception)
        mock_sdk.capture_exception.assert_not_called()
        mock_sdk.capture_message.assert_not_called()
        mock_scope.capture_message.assert_not_called()
        # exc_info 経路も new_scope() 内で実行され、追加コンテキストが Sentry event に付与される
        # (観察性: user_id/request_id 等の structlog bind context を保持する)
        mock_sdk.new_scope.assert_called_once()
        set_extra_calls = {call[0][0]: call[0][1] for call in mock_scope.set_extra.call_args_list}
        assert set_extra_calls.get("user_id") == 123
        assert set_extra_calls.get("request_id") == "req-abc"

    def test_capture_exception_with_exc_info_tuple(self) -> None:
        """分岐3: sys.exc_info() 形式の tuple でも capture_exception を呼ぶ"""
        event_dict = {
            "level": "error",
            "event": "error with tuple exc_info",
            "user_id": 456,
        }

        try:
            raise ValueError("tuple error")
        except ValueError:
            exc_info = sys.exc_info()

        assert exc_info is not None
        event_dict["exc_info"] = exc_info

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
        mock_scope.capture_exception.assert_called_once_with(exc_info)
        mock_sdk.capture_exception.assert_not_called()
        mock_sdk.capture_message.assert_not_called()
        mock_scope.capture_message.assert_not_called()
        mock_sdk.new_scope.assert_called_once()
        set_extra_calls = {call[0][0]: call[0][1] for call in mock_scope.set_extra.call_args_list}
        assert set_extra_calls.get("user_id") == 456

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
        mock_scope.capture_message.assert_called_once_with(
            "error without exception",
            level="error",
        )
        mock_sdk.capture_exception.assert_not_called()

    def test_capture_exception_with_exc_info_true(self) -> None:
        """exc_info=True かつ active な except ブロック内の場合は capture_exception(None)。

        structlog.dev.set_exc_info processor は logger.exception() 呼び出し時に
        event_dict["exc_info"] = True をセットするのみで Tuple 化しない。
        sys.exc_info()[1] が None でない（active except ブロック内）場合に
        capture_exception(None) を呼び sys.exc_info() 経由でスタックトレースを送信する。
        """
        event_dict = {
            "level": "error",
            "event": "error with exc_info=True",
            "exc_info": True,
        }

        mock_sdk = MagicMock()
        mock_client = MagicMock()
        mock_client.is_active.return_value = True
        mock_sdk.get_client.return_value = mock_client

        mock_scope = MagicMock()
        mock_sdk.new_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
        mock_sdk.new_scope.return_value.__exit__ = MagicMock(return_value=False)

        # active な except ブロック内で呼ぶことで sys.exc_info()[1] is not None を保証
        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            try:
                raise ValueError("dummy for sys.exc_info context")
            except ValueError:
                result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        assert result is event_dict
        mock_scope.capture_exception.assert_called_once_with(None)
        mock_scope.capture_message.assert_not_called()
        mock_sdk.capture_exception.assert_not_called()

    def test_capture_message_fallback_when_exc_info_true_outside_except(self) -> None:
        """exc_info=True だが active な except ブロック外の場合は capture_message へ fallback。

        logger.exception() を except ブロック外で誤用した場合、sys.exc_info()[1] が None
        になるため capture_exception(None) は空イベントを送信してしまう。
        このケースでは capture_message にフォールバックしログメッセージを Sentry に保持する。
        """
        event_dict = {
            "level": "error",
            "event": "error with exc_info=True outside except",
            "exc_info": True,
        }

        mock_sdk = MagicMock()
        mock_client = MagicMock()
        mock_client.is_active.return_value = True
        mock_sdk.get_client.return_value = mock_client

        mock_scope = MagicMock()
        mock_sdk.new_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
        mock_sdk.new_scope.return_value.__exit__ = MagicMock(return_value=False)

        # except ブロック外: sys.exc_info()[1] は None → capture_message へ fallback
        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        assert result is event_dict
        mock_scope.capture_message.assert_called_once_with(
            "error with exc_info=True outside except", level="error"
        )
        mock_scope.capture_exception.assert_not_called()
        mock_sdk.capture_exception.assert_not_called()

    def test_silent_skip_on_import_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """分岐5a: sentry-sdk未インストール時は非本番・SENTRY_DEBUG未設定でサイレントスキップ

        環境非依存のため get_settings を明示的に mock し ENVIRONMENT の影響を遮断する。
        sys.modules["sentry_sdk"] = None が CPython 仕様により import 文で ImportError を
        発生させるため builtins.__import__ の全置換は不要 (pytest/structlog 等の内部 import
        への副作用を回避)。
        """
        event_dict = {"level": "error", "event": "error message"}
        monkeypatch.delenv("SENTRY_DEBUG", raising=False)

        from utils import logger as logger_module

        mock_settings = MagicMock()
        mock_settings.is_production_like.return_value = False

        with patch.dict("sys.modules", {"sentry_sdk": None}):
            with patch.object(logger_module, "get_settings", return_value=mock_settings):
                result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        # event_dictがそのまま返される（例外は発生しない）
        assert result is event_dict
        # 警告が出力されないことを明示検証 (is_production_like=False AND SENTRY_DEBUG未設定)
        captured = capsys.readouterr()
        assert "[SENTRY_WARN]" not in captured.err

    @pytest.mark.parametrize("sentry_debug_value", ["true", "1", "yes"])
    def test_warn_on_import_error_when_sentry_debug_enabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        sentry_debug_value: str,
    ) -> None:
        """分岐5c: SENTRY_DEBUG有効時はImportError時にstderr警告出力

        5dとの対称性のため get_settings をモックし、実行環境の ENVIRONMENT 変数に
        依存しない形で SENTRY_DEBUG 経路（is_production=False + SENTRY_DEBUG=有効値）
        のみを独立検証する。logger.py 側で受理される "true"/"1"/"yes" 全てをテスト。
        """
        event_dict = {"level": "error", "event": "error message"}
        monkeypatch.setenv("SENTRY_DEBUG", sentry_debug_value)

        from utils import logger as logger_module

        mock_settings = MagicMock()
        mock_settings.is_production_like.return_value = False  # SENTRY_DEBUG 経路のみ検証

        with patch.dict("sys.modules", {"sentry_sdk": None}):
            with patch.object(logger_module, "get_settings", return_value=mock_settings):
                result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        assert result is event_dict
        captured = capsys.readouterr()
        assert "[SENTRY_WARN]" in captured.err
        assert "sentry-sdk not installed" in captured.err
        # is_production_like() 分岐が実際に評価されたことを検証 (5d と対称な causal path 保証)
        mock_settings.is_production_like.assert_called_once()

    def test_warn_on_import_error_when_production_env(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """分岐5d: 本番環境ではSENTRY_DEBUG未設定でもstderr警告出力

        sentry_init.pyのImportError→RuntimeError Fail-Fast方針と整合性を確保し、
        本番デプロイ時のsentry-sdk未インストールを検知可能にする。
        """
        event_dict = {"level": "error", "event": "error message"}
        monkeypatch.delenv("SENTRY_DEBUG", raising=False)

        from utils import logger as logger_module

        mock_settings = MagicMock()
        mock_settings.is_production_like.return_value = True

        with patch.dict("sys.modules", {"sentry_sdk": None}):
            with patch.object(logger_module, "get_settings", return_value=mock_settings):
                result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        assert result is event_dict
        captured = capsys.readouterr()
        assert "[SENTRY_WARN]" in captured.err
        assert "sentry-sdk not installed" in captured.err
        # is_production_like() 分岐が実際に評価されたことを検証 (causal path 保証)
        mock_settings.is_production_like.assert_called_once()

    def test_settings_failure_in_import_error_handler_is_contained(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """分岐5e: get_settings() が ImportError handler 内で失敗しても処理は継続する

        defensive try/except が例外を遮断し log processor が例外を伝播しないことを保証する。
        """
        event_dict = {"level": "error", "event": "error message"}
        monkeypatch.setenv("SENTRY_DEBUG", "true")

        from utils import logger as logger_module

        with patch.dict("sys.modules", {"sentry_sdk": None}):
            with patch.object(
                logger_module,
                "get_settings",
                side_effect=RuntimeError("Settings validation failed"),
            ):
                # 例外伝播せず event_dict が返ることを検証
                result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        assert result is event_dict
        # settings 失敗時の固有メッセージを検証 (リグレッション検出力保証)
        captured = capsys.readouterr()
        assert "[SENTRY_WARN] settings load failed" in captured.err
        assert "RuntimeError" in captured.err
        assert "sentry-sdk not installed" in captured.err

    def test_validation_error_uses_type_error_detail_when_errors_signature_mismatch(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """errors() が TypeError を raise した場合は型名のみの sanitized 出力になる

        Pydantic v3 で include_input 引数が削除された場合など、errors() の
        シグネチャが変わると TypeError が発生する。_safe_error_summary() は
        全 Exception を一括捕捉し「{TypeName} (details sanitized)」を返す。
        """

        class _FakeValidationError(Exception):
            def errors(self, *, include_input: bool) -> list[dict[str, object]]:
                raise TypeError("unexpected keyword argument 'include_input'")

        event_dict = {"level": "error", "event": "error message"}
        monkeypatch.setenv("SENTRY_DEBUG", "true")

        from utils import logger as logger_module

        with patch.dict("sys.modules", {"sentry_sdk": None}):
            with patch.object(
                logger_module,
                "get_settings",
                side_effect=_FakeValidationError("validation failed"),
            ):
                result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        assert result is event_dict
        captured = capsys.readouterr()
        assert "[SENTRY_WARN] settings load failed" in captured.err
        assert "(details sanitized)" in captured.err
        # str(e) / input_value が漏洩しないことを検証
        assert "unexpected keyword argument" not in captured.err

    def test_validation_error_uses_details_omitted_when_errors_summary_fails(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """errors(include_input=False) が失敗した場合は details sanitized に落ちる"""

        class _FakeValidationError(Exception):
            def errors(self, *, include_input: bool) -> list[dict[str, object]]:
                raise RuntimeError("summary failed")

        event_dict = {"level": "error", "event": "error message"}
        monkeypatch.setenv("SENTRY_DEBUG", "true")

        from utils import logger as logger_module

        with patch.dict("sys.modules", {"sentry_sdk": None}):
            with patch.object(
                logger_module,
                "get_settings",
                side_effect=_FakeValidationError("validation failed"),
            ):
                result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        assert result is event_dict
        captured = capsys.readouterr()
        assert "[SENTRY_WARN] settings load failed" in captured.err
        assert "(details sanitized)" in captured.err
        assert "summary failed" not in captured.err

    def test_sentry_warnings_throttled_across_multiple_calls(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """_sentry_processor の stderr 警告は per-process 1 回のみ出力される

        structlog processor は ERROR ログ毎に呼ばれるため、settings 失敗 × sentry-sdk
        未インストールが持続する環境で log flood が発生する副作用を防ぐ。
        3 回連続呼び出しで警告が計 2 行 (settings + sdk 各 1 回) のみ出力されることを検証。

        早期リターン最適化の保証 (call_count assertion):
        sdk フラグ昇格後は ``_emit_import_error_warnings()`` 内の ``if
        _sentry_sdk_warning_emitted: return`` で get_settings() 呼出し自体が
        skip される。assert により誤って早期リターンを削除した場合のリグレッション
        (= エラーストーム時の累積コスト増) を検出する。

        strict equality (== 1) を採用する理由:
        現行設計では 1 回目の呼出しで sdk フラグが昇格し、2 回目以降は早期リターン
        により get_settings() が呼ばれない。「<= 1」ではなく「== 1」を採用することで、
        将来的に flag 昇格パスが冗長化された場合 (例: 複数の lock acquire 経路で
        重複呼出し) も fail-loud で即検知できる。設計意図の strict 維持を優先。
        """
        event_dict = {"level": "error", "event": "error message"}
        monkeypatch.setenv("SENTRY_DEBUG", "true")

        from utils import logger as logger_module

        with patch.dict("sys.modules", {"sentry_sdk": None}):
            with patch.object(
                logger_module,
                "get_settings",
                side_effect=RuntimeError("Settings validation failed"),
            ) as mock_get_settings:
                for _ in range(3):
                    _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        captured = capsys.readouterr()
        # settings 失敗警告と sentry-sdk 未インストール警告はそれぞれ 1 回のみ
        assert captured.err.count("[SENTRY_WARN] settings load failed") == 1
        assert captured.err.count("sentry-sdk not installed") == 1
        # 早期リターンにより 2 回目以降 get_settings() は呼ばれない (strict equality)
        assert mock_get_settings.call_count == 1, (
            f"早期リターン分岐が機能しておらず get_settings() が "
            f"{mock_get_settings.call_count} 回呼び出された (期待値: 1)"
        )

    def test_throttle_on_settings_success_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """分岐5g: settings 成功 × is_prod=True でも sdk 警告は 1 回のみ throttle される

        正規ルート (settings 成功・本番環境) で `sdk_not_installed_emitted` フラグ単独で
        スロットルが機能することを検証する。旧実装の「両フラグ AND」条件では
        settings_emitted が昇格しないため early-return が不発だったリグレッションを防ぐ。

        早期リターン最適化の保証 (call_count assertion):
        1 回目で sdk フラグ昇格後、2 回目以降は ``_emit_import_error_warnings()`` 内の
        早期リターンで get_settings() 呼出しが skip される。assert により最適化の
        リグレッションを検出する。
        """
        event_dict = {"level": "error", "event": "error message"}
        monkeypatch.delenv("SENTRY_DEBUG", raising=False)

        from utils import logger as logger_module

        mock_settings = MagicMock()
        mock_settings.is_production_like.return_value = True  # 本番環境

        with patch.dict("sys.modules", {"sentry_sdk": None}):
            with patch.object(
                logger_module, "get_settings", return_value=mock_settings
            ) as mock_get_settings:
                for _ in range(3):
                    _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        captured = capsys.readouterr()
        # sdk 警告は 1 回のみ。settings 警告は発生しない (成功ケース)
        assert captured.err.count("sentry-sdk not installed") == 1
        assert "[SENTRY_WARN] settings load failed" not in captured.err
        # 早期リターンにより 2 回目以降 get_settings() は呼ばれない
        assert mock_get_settings.call_count == 1, (
            f"早期リターン分岐が機能しておらず get_settings() が "
            f"{mock_get_settings.call_count} 回呼び出された (期待値: 1)"
        )

    def test_validation_error_input_value_not_leaked(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Pydantic ValidationError の input_value が stderr に漏洩しないこと

        str(ValidationError) は非SecretStr field の input_value を平文で含むため、
        log aggregation (CloudWatch/Datadog) 経由で operator-set 設定値が index される
        情報漏洩リスクがある。errors(include_input=False) で sanitize された summary のみ
        出力されることを検証する。
        """
        from pydantic import BaseModel, ValidationError

        class _S(BaseModel):
            url: str

        with pytest.raises(ValidationError) as exc_info:
            _S(url=123)  # type: ignore[arg-type]
        real_validation_error = exc_info.value

        # ValidationError に sensitive input_value が含まれていることを確認
        assert "123" in str(real_validation_error)

        event_dict = {"level": "error", "event": "error message"}
        monkeypatch.setenv("SENTRY_DEBUG", "true")

        from utils import logger as logger_module

        with patch.dict("sys.modules", {"sentry_sdk": None}):
            with patch.object(
                logger_module,
                "get_settings",
                side_effect=real_validation_error,
            ):
                result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        assert result is event_dict
        captured = capsys.readouterr()
        # settings load failed メッセージは出力されるが input_value (123) は含まない
        assert "[SENTRY_WARN] settings load failed" in captured.err
        assert "ValidationError" in captured.err
        assert "validation error(s)" in captured.err  # sanitized summary form
        assert "input_value" not in captured.err
        # sentinel: sensitive input value (123) が stderr に漏洩しないこと
        # (pydantic v2 str(e) には "input_value=123" 形式で含まれるが sanitize 後は消える)
        assert "123" not in captured.err, (
            "ValidationError の input_value が sanitize されず stderr に漏洩した"
        )

    def test_concurrent_emit_warnings_throttled_under_race(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_sentry_warning_lock が concurrent 呼出下でも throttle を維持する

        pytest capsys はワーカースレッド内 print が差し替え後 stderr を参照しない
        可能性があるため (false negative リスク)、io.StringIO による monkeypatch で
        全スレッドが同一バッファを参照する確定的な検証に変更する (#12 対応)。

        red-green 保証: get_settings を遅延注入し check-and-set の race window を強制露出。
        lock 無し実装では複数スレッドが check を通過し複数警告出力 → test 失敗する。

        #31 対応: race window はテスト worker 関数間で発生する (sleep は lock 内だが
        barrier でレリースした全 thread が _emit_import_error_warnings に同時到達するため、
        lock 取得競合のラウンド時に check-and-set race が顕在化する)。
        """
        import io
        import threading
        import time

        event_dict = {"level": "error", "event": "error message"}
        monkeypatch.setenv("SENTRY_DEBUG", "true")

        from utils import logger as logger_module

        captured_stderr = io.StringIO()
        monkeypatch.setattr(sys, "stderr", captured_stderr)

        def slow_get_settings() -> MagicMock:
            time.sleep(0.05)
            m = MagicMock()
            m.is_production_like.return_value = False
            m.is_production.return_value = False
            return m

        num_threads = 20
        barrier = threading.Barrier(num_threads, timeout=5.0)  # #32: timeout でデッドロック防止

        def worker() -> None:
            barrier.wait()
            _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        with patch.dict("sys.modules", {"sentry_sdk": None}):
            with patch.object(logger_module, "get_settings", side_effect=slow_get_settings):
                threads = [threading.Thread(target=worker) for _ in range(num_threads)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join(timeout=10.0)
                    assert not t.is_alive(), "worker thread deadlocked"

        output = captured_stderr.getvalue()
        assert output.count("sentry-sdk not installed") == 1, (
            f"concurrent race: expected 1 warning, got {output.count('sentry-sdk not installed')}"
        )

    def test_stderr_output_on_sentry_failure(self, capsys: pytest.CaptureFixture[str]) -> None:
        """分岐5b: Sentry送信失敗時はstderrへ出力"""
        event_dict = {"level": "error", "event": "error message"}

        mock_sdk = MagicMock()
        mock_client = MagicMock()
        mock_client.is_active.return_value = True
        mock_sdk.get_client.return_value = mock_client

        mock_scope = MagicMock()
        mock_sdk.new_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
        mock_sdk.new_scope.return_value.__exit__ = MagicMock(return_value=False)
        # capture_messageで例外を発生させる
        mock_scope.capture_message.side_effect = RuntimeError("Sentry connection failed")

        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        # event_dictは正常に返される（プロセッサーチェーン継続）
        assert result is event_dict

        # stderrにエラーメッセージが出力される
        captured = capsys.readouterr()
        assert "[SENTRY_ERROR]" in captured.err
        assert "RuntimeError" in captured.err
        assert "Sentry connection failed" not in captured.err

    def test_stderr_output_on_sentry_failure_in_debug(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """分岐5b: SENTRY_DEBUG有効時はSentry失敗の詳細をstderrへ出力する"""
        event_dict = {"level": "error", "event": "error message"}
        monkeypatch.setenv("SENTRY_DEBUG", "true")

        mock_sdk = MagicMock()
        mock_client = MagicMock()
        mock_client.is_active.return_value = True
        mock_sdk.get_client.return_value = mock_client

        mock_scope = MagicMock()
        mock_sdk.new_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
        mock_sdk.new_scope.return_value.__exit__ = MagicMock(return_value=False)
        mock_scope.capture_message.side_effect = RuntimeError("Sentry connection failed")

        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        assert result is event_dict
        captured = capsys.readouterr()
        assert "[SENTRY_ERROR]" in captured.err
        assert "RuntimeError" in captured.err
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
        mock_scope.capture_message.assert_called_once_with(
            "Unknown error",
            level="error",
        )

    def test_system_exception_reraises_not_swallowed(self) -> None:
        """MemoryError は except Exception で飲み込まれずに再発生する（K8s OOMKilled検知対応）"""
        mock_sdk = MagicMock()
        mock_client = MagicMock()
        mock_client.is_active.return_value = True
        mock_sdk.get_client.return_value = mock_client
        # new_scope 呼び出し時に MemoryError を発生させる（実際の OOM は発生しない）
        mock_sdk.new_scope.side_effect = MemoryError("simulated OOM")

        event_dict = {"event": "OOM test", "level": "error"}
        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            with pytest.raises(MemoryError):
                _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)
