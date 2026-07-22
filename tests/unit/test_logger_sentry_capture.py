"""utils/logger.py のユニットテスト"""

import sys
from unittest.mock import MagicMock, patch

import pytest

from tests.unit.helpers import _make_fake_validation_error
from utils.logger import _sentry_processor

pytestmark = pytest.mark.unit


class TestSentryProcessor:
    """警告状態fixtureでthrottle経路を分離

    Note: setenv/delenv を使用する場合、ここでは cache_clear() は不要。"""

    # ダミーのWrappedLoggerとmethod_name（未使用だが引数として必要）
    _dummy_logger = None
    _dummy_method = "error"

    def test_capture_exception_with_exc_info(self) -> None:
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
        """exc_info=True かつ active な except ブロック内の場合は exc_info tuple を渡す。

        structlog.dev.set_exc_info processor は logger.exception() 呼び出し時に
        event_dict["exc_info"] = True をセットするのみで Tuple 化しない。
        TOCTOU 排除のため sys.exc_info() を new_scope() 入場前に snapshot 取得し、
        capture_exception に tuple として渡す。
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
        # capture_exception には sys.exc_info() の snapshot tuple が渡される
        mock_scope.capture_exception.assert_called_once()
        call_args = mock_scope.capture_exception.call_args
        passed_exc = call_args.args[0]
        assert isinstance(passed_exc, tuple)
        assert len(passed_exc) == 3
        assert passed_exc[0] is ValueError
        assert isinstance(passed_exc[1], ValueError)
        assert passed_exc[2] is not None
        mock_scope.capture_message.assert_not_called()
        mock_sdk.capture_exception.assert_not_called()

    def test_capture_message_fallback_when_exc_info_true_outside_except(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """exc_info=True だが active な except ブロック外の場合は capture_message へ fallback。

        logger.exception() を except ブロック外で誤用した場合、sys.exc_info()[1] が None
        になるため capture_exception(None) は空イベントを送信してしまう。
        このケースでは capture_message にフォールバックしログメッセージを Sentry に保持する。
        [SENTRY_WARN] が stderr に出力されることも検証する（throttle 保護あり）。
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
        captured = capsys.readouterr()
        assert "[SENTRY_WARN] logger.exception() called outside except block" in captured.err
        assert "falling back to capture_message" in captured.err

    def test_extra_context_set_in_scope(self) -> None:
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

        set_extra_calls = {call[0][0]: call[0][1] for call in mock_scope.set_extra.call_args_list}
        assert set_extra_calls.get("user_id") == 456
        assert set_extra_calls.get("request_id") == "abc-123"
        assert set_extra_calls.get("endpoint") == "/api/users"

    def test_set_extra_per_key_skip_on_serialization_failure(self) -> None:
        """broken __repr__ を持つ user-data の per-key skip 検証

        scope.set_extra() が AttributeError/TypeError を raise した場合に
        該当キーのみスキップして他キーは正常送信される設計を保護する
        (リグレッション検出: ループ内 except を全件 abort に変更してしまう改修への防御)。
        """
        event_dict = {
            "level": "error",
            "event": "broken __repr__ test",
            "broken_obj": "broken_value_marker",
            "user_id": 789,
            "request_id": "req-xyz",
        }

        mock_sdk = MagicMock()
        mock_client = MagicMock()
        mock_client.is_active.return_value = True
        mock_sdk.get_client.return_value = mock_client

        mock_scope = MagicMock()
        mock_sdk.new_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
        mock_sdk.new_scope.return_value.__exit__ = MagicMock(return_value=False)

        captured: dict[str, object] = {}

        def fake_set_extra(key: str, value: object) -> None:
            # broken_obj キーのみ TypeError を raise (Pydantic broken __repr__ 模擬)
            if key == "broken_obj":
                raise TypeError("simulated serialization failure on broken_obj")
            captured[key] = value

        mock_scope.set_extra.side_effect = fake_set_extra

        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        assert "broken_obj" not in captured
        assert captured.get("user_id") == 789
        assert captured.get("request_id") == "req-xyz"
        mock_scope.capture_message.assert_called_once()

    def test_capture_exception_invalid_type_falls_back_to_capture_message(self) -> None:
        """exc_info に BaseException/tuple 以外の不正型が入った場合の fallback 検証

        isinstance guard により capture_exception の TypeError 経路を回避し
        capture_message へ降格して Sentry 通知を保証する設計を保護する
        ([SENTRY_BUG] throttle 経由で永続silent化する failure mode を防止)。
        """
        event_dict = {
            "level": "error",
            "event": "invalid exc_info type",
            # 不正型 (str: BaseException でも tuple でもない truthy 値)
            "exc_info": "not_an_exception_instance",
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

        mock_scope.capture_exception.assert_not_called()
        mock_scope.capture_message.assert_called_once_with(
            "invalid exc_info type",
            level="error",
        )

    def test_capture_exception_invalid_tuple_falls_back_to_capture_message(self) -> None:
        """不正なexc_info tupleはSDKのTypeErrorを避けてメッセージ送信へ降格する。"""
        event_dict = {
            "level": "error",
            "event": "invalid exc_info tuple",
            "exc_info": (ValueError, ValueError("tuple error")),
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

        mock_scope.capture_exception.assert_not_called()
        mock_scope.capture_message.assert_called_once_with(
            "invalid exc_info tuple",
            level="error",
        )

    def test_default_message_when_event_missing(self) -> None:
        event_dict = {"level": "error"}

        mock_sdk = MagicMock()
        mock_client = MagicMock()
        mock_client.is_active.return_value = True
        mock_sdk.get_client.return_value = mock_client

        mock_scope = MagicMock()
        mock_sdk.new_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
        mock_sdk.new_scope.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        mock_scope.capture_message.assert_called_once_with(
            "Unknown error",
            level="error",
        )

    def test_skip_when_sentry_not_active(self) -> None:
        event_dict = {"level": "error", "event": "error message"}

        mock_sdk = MagicMock()
        mock_client = MagicMock()
        mock_client.is_active.return_value = False
        mock_sdk.get_client.return_value = mock_client

        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        assert result is event_dict
        # is_active=False のため new_scope() への入場自体が発生しないことを検証
        # (scope.set_extra/capture_* に到達する可能性そのものを排除)
        mock_sdk.new_scope.assert_not_called()
        mock_sdk.capture_message.assert_not_called()
        mock_sdk.capture_exception.assert_not_called()

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
                result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        assert result is event_dict
        # settings 失敗時の固有メッセージを検証 (リグレッション検出力保証)
        captured = capsys.readouterr()
        assert "[SENTRY_WARN] settings load failed" in captured.err
        assert "RuntimeError" in captured.err
        assert "sentry-sdk not installed" in captured.err

    def test_settings_failure_emits_in_non_prod_due_to_safe_fallback(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """settings_error 発生時は is_prod=True 安全フォールバックにより警告出力

        `_emit_import_error_warnings` 内で `get_settings()` が例外を発生させた場合、
        `is_prod = True` にフォールバックする (本番可能性を排除できないため)。
        この設計により非prod + SENTRY_DEBUG 未設定でも settings_error 経由で
        `should_emit_warnings = True` となり、settings_msg / sdk_msg 両方が
        stderr に emit される (settings_error 発生 path の不変条件)。
        """
        event_dict = {"level": "error", "event": "error message"}
        monkeypatch.delenv("SENTRY_DEBUG", raising=False)

        from utils import logger as logger_module

        with patch.dict("sys.modules", {"sentry_sdk": None}):
            with patch.object(
                logger_module,
                "get_settings",
                side_effect=RuntimeError("Settings validation failed"),
            ):
                result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        assert result is event_dict
        captured = capsys.readouterr()
        # is_prod=True フォールバックで settings_msg / sdk_msg ともに出力
        assert "[SENTRY_WARN] settings load failed" in captured.err
        assert "sentry-sdk not installed" in captured.err
        # settings_detail は _safe_error_summary 経由で input 値除外
        assert "Settings validation failed" not in captured.err

    def test_stderr_output_on_sentry_failure(
        self,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Sentry送信失敗は、debug無効時に詳細を漏らさずstderrへ通知する。"""
        # SENTRY_DEBUG が外部環境に残っている場合「詳細が出力されない」検証が偽陰性化する。
        # 対称テスト test_stderr_output_on_sentry_failure_in_debug 側は setenv 明示なので
        # こちらも明示的に削除して環境非依存にする。
        monkeypatch.delenv("SENTRY_DEBUG", raising=False)

        event_dict = {"level": "error", "event": "error message"}

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
        assert "Sentry connection failed" not in captured.err

    def test_stderr_output_on_sentry_failure_in_debug(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Sentry debug有効時だけ送信失敗の詳細をstderrへ出す。"""
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

    def test_sentry_bug_attribute_error_debug_disabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """分岐: AttributeError発生時は[SENTRY_BUG]をstderrへ出力 (SENTRY_DEBUG無効で詳細なし)"""
        monkeypatch.delenv("SENTRY_DEBUG", raising=False)

        mock_sdk = MagicMock()
        mock_sdk.get_client.return_value.is_active.return_value = True
        mock_sdk.new_scope.side_effect = AttributeError("mock SDK attribute mismatch")

        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            result = _sentry_processor(
                self._dummy_logger, self._dummy_method, {"level": "error", "event": "test"}
            )

        assert result is not None
        captured = capsys.readouterr()
        assert "[SENTRY_BUG]" in captured.err
        assert "AttributeError" in captured.err
        assert "mock SDK attribute mismatch" not in captured.err

    def test_sentry_bug_attribute_error_debug_enabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """分岐: SENTRY_DEBUG有効時は[SENTRY_BUG]に詳細を含める"""
        monkeypatch.setenv("SENTRY_DEBUG", "true")

        mock_sdk = MagicMock()
        mock_sdk.get_client.return_value.is_active.return_value = True
        mock_sdk.new_scope.side_effect = AttributeError("mock SDK attribute mismatch")

        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            result = _sentry_processor(
                self._dummy_logger, self._dummy_method, {"level": "error", "event": "test"}
            )

        assert result is not None
        captured = capsys.readouterr()
        assert "[SENTRY_BUG]" in captured.err
        assert "AttributeError" in captured.err
        assert "mock SDK attribute mismatch" in captured.err

    def test_sentry_bug_type_error_debug_disabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """分岐: TypeError発生時も[SENTRY_BUG]をstderrへ出力 (AttributeErrorと同ハンドラ)"""
        monkeypatch.delenv("SENTRY_DEBUG", raising=False)

        mock_sdk = MagicMock()
        mock_sdk.get_client.return_value.is_active.return_value = True
        mock_sdk.new_scope.side_effect = TypeError("SDK type mismatch")

        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            result = _sentry_processor(
                self._dummy_logger, self._dummy_method, {"level": "error", "event": "test"}
            )

        assert result is not None
        captured = capsys.readouterr()
        assert "[SENTRY_BUG]" in captured.err
        assert "TypeError" in captured.err
        assert "SDK type mismatch" not in captured.err

    def test_generic_exception_from_emit_warnings_caught(
        self, reset_sentry_warning_state: None, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """_emit_import_error_warnings自体がMemoryError/RecursionError以外の例外を投げた場合に握り潰してSENTRY_WARNを出力する"""
        from utils import logger as logger_module

        event_dict = {"level": "error", "event": "test"}
        with patch.dict("sys.modules", {"sentry_sdk": None}):
            with patch.object(
                logger_module,
                "_emit_import_error_warnings",
                side_effect=ValueError("unexpected warning failure"),
            ):
                result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)
        captured = capsys.readouterr()
        assert "[SENTRY_WARN] Failed to emit import warning: ValueError" in captured.err
        assert result == event_dict

    @pytest.mark.parametrize(
        "level",
        ["info", "INFO", "warning", "WARNING", "debug", "DEBUG", ""],
    )
    def test_skip_non_error_levels(self, level: str) -> None:
        event_dict = {"level": level, "event": "test message"}

        result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        assert result is event_dict
        assert result["event"] == "test message"

    @pytest.mark.parametrize(
        ("level", "expected_sentry_level"),
        [
            ("error", "error"),
            ("ERROR", "error"),
            ("critical", "critical"),
            ("CRITICAL", "critical"),
            ("exception", "error"),  # _SENTRY_LEVEL_MAP で "error" に正規化
            ("EXCEPTION", "error"),
        ],
    )
    def test_process_error_levels(self, level: str, expected_sentry_level: str) -> None:
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
        # 両経路ともscope内で呼び、bind済みコンテキストを送る。
        assert mock_scope.capture_message.called or mock_scope.capture_exception.called

        # _SENTRY_LEVEL_MAP の正規化が capture_message(level=...) に反映されることを検証。
        # exc_info なしのため capture_message ルートに入る (capture_exception は呼ばれない)。
        # "exception" level も "error" に正規化されること、大文字小文字を吸収すること
        # の両方をリグレッション検出対象に含める。
        mock_scope.capture_message.assert_called_once()
        _, kwargs = mock_scope.capture_message.call_args
        assert kwargs.get("level") == expected_sentry_level

    def test_system_exception_reraises_not_swallowed(self) -> None:
        """MemoryErrorを汎用例外処理で握り潰さず、KubernetesのOOM検知へ伝播させる。"""
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

    def test_memory_error_from_emit_warnings_propagates(self) -> None:
        """_emit_import_error_warnings内でMemoryErrorが発生した場合、_sentry_processorから伝播する"""
        from utils import logger as logger_module

        # 前提条件の明示: throttle マーカーが未昇格であることを保証
        # (autouse fixture の挙動が将来変わった場合のサイレント偽陽性を防ぐ)
        assert "sdk" not in logger_module._sentry_warnings_emitted

        _FakeValidationError = _make_fake_validation_error(  # noqa: N806
            MemoryError("OOM during warning emission")
        )
        event_dict = {"level": "error", "event": "test"}
        with patch.dict("sys.modules", {"sentry_sdk": None}):
            with patch.object(
                logger_module,
                "get_settings",
                side_effect=_FakeValidationError("settings failed"),
            ):
                with pytest.raises(MemoryError):
                    _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

    def test_recursion_error_from_emit_warnings_propagates(self) -> None:
        """_emit_import_error_warnings内でRecursionErrorが発生した場合、_sentry_processorから伝播する"""
        from utils import logger as logger_module

        # 前提条件の明示: throttle マーカーが未昇格であることを保証
        assert "sdk" not in logger_module._sentry_warnings_emitted

        _FakeValidationError = _make_fake_validation_error(  # noqa: N806
            RecursionError("infinite recursion in errors()")
        )
        event_dict = {"level": "error", "event": "test"}
        with patch.dict("sys.modules", {"sentry_sdk": None}):
            with patch.object(
                logger_module,
                "get_settings",
                side_effect=_FakeValidationError("settings failed"),
            ):
                with pytest.raises(RecursionError):
                    _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)
