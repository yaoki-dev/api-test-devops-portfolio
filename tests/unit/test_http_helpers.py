"""HTTP helper tests for utils.http_helpers."""

from unittest.mock import Mock, patch

import httpx
import pytest

from tests.constants import INVALID_BASE_URLS
from utils.exceptions import (
    APIClientError,
    APIConnectionError,
    APITimeoutError,
)
from utils.http_helpers import (
    classify_error as _classify_error,
)
from utils.http_helpers import (
    log_error_with_stderr_fallback as _log_error_with_stderr_fallback,
)
from utils.http_helpers import (
    map_request_error as _map_request_error,
)
from utils.http_helpers import (
    resolve_client_config as _resolve_client_config,
)
from utils.http_helpers import (
    validate_optional_int as _validate_optional_int,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "value,name,min_value",
    [
        (None, "limit", 0),
        (None, "user_id", 1),
    ],
    ids=["limit_none", "user_id_none"],
)
def test_validate_optional_int_none_value_skips_validation(
    value: int | None, name: str, min_value: int
) -> None:
    """value=None の場合、min_valueに関わらず例外が発生しないこと（早期スキップ）"""
    _validate_optional_int(value, name, min_value)


@pytest.mark.parametrize(
    "value,name,min_value",
    [
        (0, "limit", 0),
        (1, "user_id", 1),
    ],
    ids=["limit_boundary_zero", "user_id_boundary_one"],
)
def test_validate_optional_int_boundary_value_equal_to_min_passes(
    value: int, name: str, min_value: int
) -> None:
    """value == min_value の境界値では例外が発生しないこと（`<` 比較の検証）"""
    _validate_optional_int(value, name, min_value)


@pytest.mark.parametrize(
    "value,name,min_value",
    [
        (-1, "limit", 0),
        (0, "user_id", 1),
        (-100, "user_id", 1),
    ],
    ids=["limit_negative", "user_id_zero", "user_id_very_negative"],
)
def test_validate_optional_int_below_min_raises_value_error(
    value: int, name: str, min_value: int
) -> None:
    """value < min_value の場合、期待メッセージでValueErrorが発生すること"""
    with pytest.raises(ValueError, match=f"{name} must be >= {min_value}"):
        _validate_optional_int(value, name, min_value)


def test_map_request_error_too_many_redirects() -> None:
    """TooManyRedirectsで非リトライエラー発生"""
    error = httpx.TooManyRedirects("Max redirects exceeded")

    with pytest.raises(APIClientError) as exc_info:
        _map_request_error(error)

    assert "Non-retryable" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, httpx.TooManyRedirects)
    # セキュリティ: str(e) が含まれないこと（機密情報漏洩防止）
    assert "Max redirects exceeded" not in str(exc_info.value)
    assert "TooManyRedirects" in str(exc_info.value)  # type(e).__name__ が含まれること


def test_map_request_error_invalid_url() -> None:
    """InvalidURLで非リトライエラー発生"""
    error = httpx.InvalidURL("Invalid URL format")

    with pytest.raises(APIClientError) as exc_info:
        _map_request_error(error)

    assert "Non-retryable" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, httpx.InvalidURL)
    # セキュリティ: str(e) が含まれないこと（機密情報漏洩防止）
    assert "Invalid URL format" not in str(exc_info.value)
    assert "InvalidURL" in str(exc_info.value)  # type(e).__name__ が含まれること


def test_map_request_error_timeout() -> None:
    """TimeoutExceptionでAPITimeoutError返却"""
    error = httpx.TimeoutException("Request timed out at https://internal.corp/api")
    result = _map_request_error(error)

    assert isinstance(result, APITimeoutError)
    assert "timeout" in str(result).lower()
    assert result.__cause__ is error
    # セキュリティ: str(e) が含まれないこと（機密情報漏洩防止）
    assert "internal.corp" not in str(result)
    assert "TimeoutException" in str(result)  # type(e).__name__ が含まれること


def test_map_request_error_connect_error() -> None:
    """ConnectErrorでAPIConnectionError返却"""
    error = httpx.ConnectError("Connection refused to internal-proxy.corp.example.com")
    result = _map_request_error(error)

    assert isinstance(result, APIConnectionError)
    assert "connection" in str(result).lower()
    assert result.__cause__ is error
    # セキュリティ: str(e)（ホスト名等の機密情報）が含まれないこと
    assert "internal-proxy.corp.example.com" not in str(result)
    assert "ConnectError" in str(result)  # type(e).__name__ が含まれること


def test_map_request_error_network_error() -> None:
    """NetworkError（else分岐）でAPIConnectionError返却"""
    error = httpx.NetworkError("Network unreachable via proxy.internal.example.com")
    result = _map_request_error(error)

    assert isinstance(result, APIConnectionError)
    assert "network" in str(result).lower()
    assert result.__cause__ is error
    # セキュリティ: str(e) が含まれないこと（機密情報漏洩防止）
    assert "proxy.internal.example.com" not in str(result)
    assert "NetworkError" in str(result)  # type(e).__name__ が含まれること


def test_classify_error_non_retryable_logs_error() -> None:
    """TooManyRedirects時にlogger.errorが呼ばれる"""
    error = httpx.TooManyRedirects("Max redirects")
    mock_logger = Mock()

    with pytest.raises(APIClientError) as exc_info:
        _classify_error(error, mock_logger, is_async=False, method="GET", endpoint="/test")

    mock_logger.error.assert_called_once()
    call_kwargs = mock_logger.error.call_args
    assert call_kwargs[0][0] == "request_error_non_retryable"
    assert call_kwargs[1]["is_async"] is False
    assert call_kwargs[1]["error_type"] == "TooManyRedirects"
    assert call_kwargs[1]["method"] == "GET"
    assert call_kwargs[1]["endpoint"] == "/test"
    assert "error" not in call_kwargs[1]
    assert isinstance(exc_info.value.__cause__, httpx.TooManyRedirects)
    mock_logger.warning.assert_not_called()


def test_classify_error_non_retryable_async_field() -> None:
    """async呼び出し時にis_asyncフィールドがTrueになる（静的イベント名 + 構造化フィールド）"""
    error = httpx.InvalidURL("Bad URL")
    mock_logger = Mock()

    with pytest.raises(APIClientError) as exc_info:
        _classify_error(error, mock_logger, is_async=True, method="GET", endpoint="/test")

    mock_logger.error.assert_called_once()
    call_kwargs = mock_logger.error.call_args
    assert call_kwargs[0][0] == "request_error_non_retryable"
    assert call_kwargs[1]["is_async"] is True
    assert "error" not in call_kwargs[1]
    assert isinstance(exc_info.value.__cause__, httpx.InvalidURL)
    mock_logger.warning.assert_not_called()


def test_classify_error_retryable_logs_warning() -> None:
    """ConnectError時にlogger.warningが呼ばれる"""
    error = httpx.ConnectError("Connection refused")
    mock_logger = Mock()

    result = _classify_error(error, mock_logger, is_async=False, method="POST", endpoint="/api")

    assert isinstance(result, APIConnectionError)
    assert result.__cause__ is error
    mock_logger.warning.assert_called_once()
    call_kwargs = mock_logger.warning.call_args
    assert call_kwargs[0][0] == "request_error"
    assert call_kwargs[1]["error_type"] == "ConnectError"
    assert call_kwargs[1]["method"] == "POST"
    assert call_kwargs[1]["endpoint"] == "/api"
    assert "error" not in call_kwargs[1]


def test_classify_error_retryable_timeout() -> None:
    """TimeoutException時にAPITimeoutErrorが返される"""
    error = httpx.TimeoutException("Timed out")
    mock_logger = Mock()

    result = _classify_error(error, mock_logger, is_async=True, method="GET", endpoint="/slow")

    assert isinstance(result, APITimeoutError)
    assert result.__cause__ is error
    mock_logger.warning.assert_called_once()
    call_kwargs = mock_logger.warning.call_args
    assert call_kwargs[0][0] == "request_error"
    assert call_kwargs[1]["is_async"] is True
    assert "error" not in call_kwargs[1]


def test_classify_error_retryable_network_error() -> None:
    """ReadError（NetworkErrorサブクラス）時にAPIConnectionErrorが返される（else分岐）"""
    error = httpx.ReadError("Read failed")
    mock_logger = Mock()

    result = _classify_error(error, mock_logger, is_async=False, method="GET", endpoint="/test")

    assert isinstance(result, APIConnectionError)
    assert result.__cause__ is error
    mock_logger.warning.assert_called_once()
    call_kwargs = mock_logger.warning.call_args
    assert call_kwargs[0][0] == "request_error"
    assert call_kwargs[1]["error_type"] == "ReadError"
    assert "error" not in call_kwargs[1]


class MockAPISettings:
    """settings フォールバック検証用の手書き fake（本物の APIConfig は使えない）。

        Note: base_url の "settings.example.com" は ALLOWED_DOMAINS allowlist 外のため、
    `APIConfig(base_url=...)` は SSRF Prevention バリデータで ValidationError を送出する。
        この専用ホストは settings 由来の値であることの目印として assert されている。
    """

    def __init__(self) -> None:
        self.base_url = "https://settings.example.com"
        self.timeout = 30.0
        self.retry_count = 3
        self.retry_delay = 1.0
        self.user_agent = "test-agent/1.0"


class MockSettings:
    def __init__(self) -> None:
        self.api = MockAPISettings()


@pytest.fixture()
def mock_settings() -> MockSettings:
    return MockSettings()


def test_resolve_client_config_base_url_none_uses_settings(mock_settings: MockSettings) -> None:
    """base_url=None の場合 settings.api.base_url が使われる"""
    with patch("utils.http_helpers.settings", mock_settings):
        base_url, _, _, _, _ = _resolve_client_config(None, None, None, None, None)
    assert base_url == "https://settings.example.com"


@pytest.mark.parametrize("invalid_base_url", INVALID_BASE_URLS)
def test_resolve_client_config_invalid_base_url_raises(
    mock_settings: MockSettings,
    invalid_base_url: str,
) -> None:
    """空白のみの base_url で ValueError が発生"""
    with patch("utils.http_helpers.settings", mock_settings):
        with pytest.raises(ValueError, match="base_url が空です"):
            _resolve_client_config(invalid_base_url, None, None, None, None)


def test_resolve_client_config_none_timeout_uses_settings(mock_settings: MockSettings) -> None:
    """timeout=None の場合 settings.api.timeout が使われる"""
    with patch("utils.http_helpers.settings", mock_settings):
        _, timeout, _, _, _ = _resolve_client_config("https://example.com", None, None, None, None)
    assert timeout == 30.0


def test_resolve_client_config_none_retry_count_uses_settings(mock_settings: MockSettings) -> None:
    """retry_count=None の場合 settings.api.retry_count が使われる"""
    with patch("utils.http_helpers.settings", mock_settings):
        _, _, retry_count, _, _ = _resolve_client_config(
            "https://example.com", 10.0, None, 2.0, None
        )
    assert retry_count == 3


def test_resolve_client_config_none_retry_delay_uses_settings(mock_settings: MockSettings) -> None:
    """retry_delay=None の場合 settings.api.retry_delay が使われる"""
    with patch("utils.http_helpers.settings", mock_settings):
        _, _, _, retry_delay, _ = _resolve_client_config("https://example.com", 10.0, 5, None, None)
    assert retry_delay == 1.0


def test_resolve_client_config_headers_none_returns_defaults_only(
    mock_settings: MockSettings,
) -> None:
    """headers=None の場合デフォルトヘッダーのみ返される"""
    with patch("utils.http_helpers.settings", mock_settings):
        _, _, _, _, headers = _resolve_client_config("https://example.com", None, None, None, None)
    assert set(headers.keys()) == {"User-Agent", "Accept", "Content-Type"}


def test_resolve_client_config_headers_empty_dict_triggers_update(
    mock_settings: MockSettings,
) -> None:
    """headers={} (空dict) の場合も update() が呼ばれデフォルトヘッダーが含まれる

    `if headers is not None:` の明示的Noneチェックにより、
    空dictはNoneと異なる扱いになることを検証する。
    """
    with patch("utils.http_helpers.settings", mock_settings):
        _, _, _, _, headers = _resolve_client_config("https://example.com", None, None, None, {})
    assert set(headers.keys()) == {"User-Agent", "Accept", "Content-Type"}


def test_resolve_client_config_headers_merged_with_defaults(mock_settings: MockSettings) -> None:
    """カスタムヘッダーがデフォルトヘッダーとマージされる"""
    with patch("utils.http_helpers.settings", mock_settings):
        _, _, _, _, headers = _resolve_client_config(
            "https://example.com", None, None, None, {"X-Custom": "value"}
        )
    assert headers["X-Custom"] == "value"
    assert "User-Agent" in headers


def test_resolve_client_config_custom_headers_override_defaults(
    mock_settings: MockSettings,
) -> None:
    """カスタムヘッダーがデフォルトヘッダーを上書きできる"""
    with patch("utils.http_helpers.settings", mock_settings):
        _, _, _, _, headers = _resolve_client_config(
            "https://example.com", None, None, None, {"User-Agent": "custom-agent"}
        )
    assert headers["User-Agent"] == "custom-agent"


def test_resolve_client_config_zero_timeout_not_overridden(mock_settings: MockSettings) -> None:
    """timeout=0.0 は settings へフォールバックしない（is not None チェックの検証）

    `if timeout:` に誤変更された場合、0.0 が falsy のため settings.api.timeout(30.0)
    で上書きされてしまうバグを検出する。
    """
    with patch("utils.http_helpers.settings", mock_settings):
        _, timeout, _, _, _ = _resolve_client_config("https://example.com", 0.0, None, None, None)
    assert timeout == 0.0


def test_resolve_client_config_zero_retry_count_not_overridden(mock_settings: MockSettings) -> None:
    """retry_count=0 は settings へフォールバックしない（is not None チェックの検証）

    `if retry_count:` に誤変更された場合、0 が falsy のため settings.api.retry_count(3)
    で上書きされてしまうバグを検出する。
    """
    with patch("utils.http_helpers.settings", mock_settings):
        _, _, retry_count, _, _ = _resolve_client_config("https://example.com", None, 0, None, None)
    assert retry_count == 0


def test_resolve_client_config_zero_retry_delay_not_overridden(mock_settings: MockSettings) -> None:
    """retry_delay=0.0 は settings へフォールバックしない（is not None チェックの検証）

    `if retry_delay:` に誤変更された場合、0.0 が falsy のため settings.api.retry_delay(1.0)
    で上書きされてしまうバグを検出する。
    """
    with patch("utils.http_helpers.settings", mock_settings):
        _, _, _, retry_delay, _ = _resolve_client_config(
            "https://example.com", None, None, 0.0, None
        )
    assert retry_delay == 0.0


class TestLogErrorWithStderrFallback:
    """_log_error_with_stderr_fallback の stderr フォールバック分岐。

    close・cache 失敗ログで共通する「logger.error → 失敗時 stderr」パターンを
    保証する。MemoryError/RecursionError は fail-fast 再 raise、それ以外の logger
    例外は握りつぶした exc の「型名のみ」を stderr へ再露出する設計を検証する。
    """

    def test_generic_logger_exception_falls_back_to_stderr(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """logger.error が一般例外を投げた場合、exc の型名のみ stderr へ出力する。

        握りつぶした元例外の str()・logger 例外の str() のいずれも stderr へ
        漏らさない（型名のみ）ことで PII 漏洩を防ぐ設計を保証する。
        """
        mock_logger = Mock()
        mock_logger.error.side_effect = RuntimeError("logger backend down")
        # 元例外の str() に PII を模した値を入れ、漏れないことを検証する
        suppressed_exc = ValueError("user-email=secret@example.com")

        _log_error_with_stderr_fallback(
            mock_logger,
            "api_client",
            "aclose",
            suppressed_exc,
            "aclose_failed",
            endpoint="/test",
        )

        captured = capsys.readouterr()
        assert captured.err.strip() == "[api_client] aclose logger failed: ValueError"
        # PII（元例外の str）も logger 例外の str も stderr に含まれない
        assert "secret@example.com" not in captured.err
        assert "logger backend down" not in captured.err
        # フォールバック前に logger.error が event/fields 付きで1回呼ばれている
        mock_logger.error.assert_called_once_with("aclose_failed", endpoint="/test")

    def test_successful_logging_emits_no_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        """logger.error が成功した場合、stderr へ何も出力しない（主経路の回帰保護）。

        DRY 集約後に最も多用される正常系。logger.error が event/fields 付きで
        1回だけ呼ばれ、stderr フォールバックを通らないことを保証する。
        """
        mock_logger = Mock()

        _log_error_with_stderr_fallback(
            mock_logger,
            "api_client",
            "aclose",
            ValueError("orig"),
            "aclose_failed",
            endpoint="/test",
        )

        mock_logger.error.assert_called_once_with("aclose_failed", endpoint="/test")
        assert capsys.readouterr().err == ""

    @pytest.mark.parametrize("fatal_exc", [MemoryError, RecursionError])
    def test_fatal_logger_exception_propagates(
        self, fatal_exc: type[BaseException], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """logger.error が MemoryError/RecursionError を投げた場合は再 raise する。

        致命例外は except 句の評価順序で先取りされ、stderr 握りつぶしの対象外
        （sync/async fail-fast 対称性）
        """
        mock_logger = Mock()
        mock_logger.error.side_effect = fatal_exc()

        with pytest.raises(fatal_exc):
            _log_error_with_stderr_fallback(
                mock_logger,
                "api_client",
                "aclose",
                ValueError("orig"),
                "aclose_failed",
            )

        # fail-fast 経路では stderr フォールバックを通らない
        assert capsys.readouterr().err == ""
