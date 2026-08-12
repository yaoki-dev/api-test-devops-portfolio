"""utils/logger.py のユニットテスト"""

from unittest.mock import MagicMock, patch

import pytest

from tests.unit.helpers import _make_fake_validation_error
from utils.logger import _safe_error_summary, _sentry_debug_detail, _sentry_processor

pytestmark = pytest.mark.unit


class TestSentryProcessor:
    """警告状態fixtureでthrottle経路を分離

    Note: setenv/delenv を使用する場合、ここでは cache_clear() は不要。"""

    # ダミーのWrappedLoggerとmethod_name（未使用だが引数として必要）
    _dummy_logger = None
    _dummy_method = "error"

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

        _FakeValidationError = _make_fake_validation_error(  # noqa: N806
            TypeError("unexpected keyword argument 'include_input'")
        )
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
        """errors(include_input=False) が失敗した場合は details sanitized に落ちる

        SENTRY_DEBUG 有効時は `_safe_error_summary` 失敗を [SENTRY_WARN] で型名のみ通知
        (運用時の完全サイレント化を回避しつつ str(e) は出力しない)。
        """

        _FakeValidationError = _make_fake_validation_error(  # noqa: N806
            RuntimeError("inner-runtime-leak-marker")
        )
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
        # 内側 RuntimeError の str(e) (= "inner-runtime-leak-marker") は漏洩しない
        assert "inner-runtime-leak-marker" not in captured.err
        # SENTRY_DEBUG 有効時は型名のみの診断メッセージが出力される
        assert "[SENTRY_WARN] _safe_error_summary failed: RuntimeError" in captured.err

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

    def test_invalid_exc_info_tuple_warning_emitted(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_sdk = MagicMock()
        mock_sdk.get_client.return_value.is_active.return_value = True
        mock_scope = MagicMock()
        mock_sdk.new_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
        mock_sdk.new_scope.return_value.__exit__ = MagicMock(return_value=False)

        event_dict = {
            "level": "error",
            "event": "invalid exc_info tuple",
            "exc_info": (ValueError, ValueError("tuple error")),
        }

        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        captured = capsys.readouterr()
        assert (
            captured.err == "[SENTRY_WARN] invalid exc_info type for capture_exception: tuple; "
            "falling back to capture_message\n"
        )


@pytest.mark.unit
class TestSafeErrorSummary:
    def test_real_validation_error_returns_sanitized_count(self) -> None:
        from pydantic import BaseModel, ValidationError

        class _Payload(BaseModel):
            url: str

        with pytest.raises(ValidationError) as exc_info:
            _Payload(url=123)  # type: ignore[arg-type]

        summary = _safe_error_summary(exc_info.value)

        assert summary == "1 validation error(s)"
        assert "123" not in summary

    def test_safe_error_summary_failure_warns_without_sentry_debug(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """errors() 失敗 warning は SENTRY_DEBUG なしでも型名のみ出力される"""
        monkeypatch.delenv("SENTRY_DEBUG", raising=False)

        _FakeValidationError = _make_fake_validation_error(  # noqa: N806
            RuntimeError("inner-runtime-leak-marker")
        )

        summary = _safe_error_summary(_FakeValidationError())

        assert summary == "_FakeValidationError (details sanitized)"
        captured = capsys.readouterr()
        assert captured.err == "[SENTRY_WARN] _safe_error_summary failed: RuntimeError\n"
        assert "inner-runtime-leak-marker" not in captured.err

    def test_sentry_debug_detail_returns_empty_when_debug_disabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """SENTRY_DEBUG 無効時は詳細文字列を返さない"""

        monkeypatch.delenv("SENTRY_DEBUG", raising=False)

        assert _sentry_debug_detail(RuntimeError("secret")) == ""

    @pytest.mark.parametrize(
        ("message", "expected"),
        [
            ("x" * 100, ": " + ("x" * 100)),
            ("y" * 101, ": " + ("y" * 100)),
        ],
    )
    def test_sentry_debug_detail_truncates_at_100_chars(
        self,
        monkeypatch: pytest.MonkeyPatch,
        message: str,
        expected: str,
    ) -> None:
        """SENTRY_DEBUG 有効時は詳細を 100 文字まで返す"""

        monkeypatch.setenv("SENTRY_DEBUG", "true")

        assert _sentry_debug_detail(RuntimeError(message)) == expected

    def test_memory_error_from_errors_method_reraises(self) -> None:
        """errors() が MemoryError を発生させた場合は再発生する"""
        _FakeValidationError = _make_fake_validation_error(  # noqa: N806
            MemoryError("OOM in errors()")
        )
        with pytest.raises(MemoryError):
            _safe_error_summary(_FakeValidationError())

    def test_recursion_error_from_errors_method_reraises(self) -> None:
        """errors() が RecursionError を発生させた場合は再発生する"""
        _FakeValidationError = _make_fake_validation_error(  # noqa: N806
            RecursionError("recursion in errors()")
        )
        with pytest.raises(RecursionError):
            _safe_error_summary(_FakeValidationError())


@pytest.mark.unit
class TestSentryProcessorPIIIntegration:
    _dummy_logger = MagicMock()
    _dummy_method = "error"

    def test_sensitive_keys_in_event_dict_are_redacted_by_before_send(self) -> None:
        """logger.error(password=X) → set_extra → _before_send で機密値が REDACTED されること"""
        from utils.sentry_scrub_events import _before_send

        # _sentry_processor が scope.set_extra に渡したキー/値を採取する
        captured_extra: dict[str, object] = {}

        mock_scope = MagicMock()
        mock_scope.set_extra.side_effect = lambda k, v: captured_extra.update({k: v})
        mock_sdk = MagicMock()
        mock_sdk.get_client.return_value.is_active.return_value = True
        mock_sdk.new_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
        mock_sdk.new_scope.return_value.__exit__ = MagicMock(return_value=False)

        # structlog の bind 経由で機密キーが event_dict に含まれるシナリオを再現
        event_dict = {
            "level": "error",
            "event": "auth failed",
            "password": "supersecret",
            "api_key": "ak-12345",
            "user_id": 42,  # 非機密キーは保持される
        }

        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        # set_extra に機密キーが渡されている (この段階では未除去)
        assert captured_extra["password"] == "supersecret"  # noqa: S105
        assert captured_extra["api_key"] == "ak-12345"
        assert captured_extra["user_id"] == 42

        # 以下が _before_send 適用後の event 構造を模擬する
        synthetic_event: dict[str, object] = {"extra": dict(captured_extra)}
        scrubbed = _before_send(synthetic_event, {})  # type: ignore[arg-type]

        # 機密キー (password / api_key) は [REDACTED] に置換される
        assert scrubbed is not None
        scrubbed_extra = scrubbed["extra"]
        assert isinstance(scrubbed_extra, dict)
        assert scrubbed_extra["password"] == "[REDACTED]"  # noqa: S105
        assert scrubbed_extra["api_key"] == "[REDACTED]"
        # 非機密キーは保持される (false-positive 抑止)
        assert scrubbed_extra["user_id"] == 42
