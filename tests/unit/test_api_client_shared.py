"""Shared tests for module-level utility functions in api_client.py (non-async-specific).

These tests verify exception hierarchy, _safe_parse_json(), and _map_request_error()
which are module-level utility functions independent of AsyncAPIClient/SyncAPIClient.

Consolidated from test_async_client_error_handling.py and
test_sync_client_error_handling.py to eliminate duplication.

テストケース一覧（15件）:
    - Exception (3件): hierarchy, http_error_status_preservation, retry_error_message
    - JSON Parsing (3件): invalid_json, json_error_init, json_error_without_response
    - Request Error Mapping (5件): too_many_redirects, invalid_url, timeout,
      connect_error, network_error
    - Classify Error (4件): non_retryable_logs_error, non_retryable_async_prefix,
      retryable_logs_warning, retryable_timeout
"""

import json
from unittest.mock import Mock

import httpx
import pytest

from utils.api_client import (
    APIClientError,
    APIConnectionError,
    APIHTTPError,
    APIJSONDecodeError,
    APIRetryError,
    APITimeoutError,
    _classify_error,
    _map_request_error,
    _safe_parse_json,
)

# Module-level marker: All tests in this file are unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Exception Tests（例外クラスの検証）
# =============================================================================


def test_exception_hierarchy() -> None:
    """例外クラスの継承関係確認"""
    assert issubclass(APIConnectionError, APIClientError)
    assert issubclass(APITimeoutError, APIClientError)
    assert issubclass(APIHTTPError, APIClientError)
    assert issubclass(APIRetryError, APIClientError)
    assert issubclass(APIJSONDecodeError, APIClientError)
    assert issubclass(APIClientError, Exception)


def test_http_error_status_preservation() -> None:
    """APIHTTPError がステータスコードを保持することを確認"""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 404

    error = APIHTTPError("Not Found", status_code=404, response=mock_response)

    assert error.status_code == 404
    assert error.response == mock_response
    assert str(error) == "Not Found"


def test_retry_error_message() -> None:
    """APIRetryError のメッセージ確認"""
    error = APIRetryError("Max retries exceeded")
    assert str(error) == "Max retries exceeded"


# =============================================================================
# JSON Parsing Tests（_safe_parse_json の検証）
# =============================================================================


def test_safe_parse_json_invalid_json() -> None:
    """不正なJSONでAPIJSONDecodeErrorが発生（エラーパス）"""
    mock_response = Mock(spec=httpx.Response)
    mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "doc", 0)

    with pytest.raises(APIJSONDecodeError) as exc_info:
        _safe_parse_json(mock_response)

    assert "Failed to parse JSON" in str(exc_info.value)
    assert exc_info.value.response == mock_response


def test_api_json_decode_error_init() -> None:
    """APIJSONDecodeErrorのコンストラクタテスト"""
    mock_response = Mock(spec=httpx.Response)
    error = APIJSONDecodeError("Parse error", response=mock_response)

    assert str(error) == "Parse error"
    assert error.response == mock_response


def test_api_json_decode_error_without_response() -> None:
    """APIJSONDecodeError: responseなしでも動作"""
    error = APIJSONDecodeError("Parse error")

    assert str(error) == "Parse error"
    assert error.response is None


# =============================================================================
# Request Error Mapping Tests（_map_request_error の検証）
# =============================================================================


def test_map_request_error_too_many_redirects() -> None:
    """TooManyRedirectsで非リトライエラー発生"""
    error = httpx.TooManyRedirects("Max redirects exceeded")

    with pytest.raises(APIClientError) as exc_info:
        _map_request_error(error)

    assert "Non-retryable" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, httpx.TooManyRedirects)


def test_map_request_error_invalid_url() -> None:
    """InvalidURLで非リトライエラー発生"""
    error = httpx.InvalidURL("Invalid URL format")

    with pytest.raises(APIClientError) as exc_info:
        _map_request_error(error)

    assert "Non-retryable" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, httpx.InvalidURL)


def test_map_request_error_timeout() -> None:
    """TimeoutExceptionでAPITimeoutError返却"""
    error = httpx.TimeoutException("Request timed out")
    result = _map_request_error(error)

    assert isinstance(result, APITimeoutError)
    assert "timeout" in str(result).lower()
    assert result.__cause__ is error


def test_map_request_error_connect_error() -> None:
    """ConnectErrorでAPIConnectionError返却"""
    error = httpx.ConnectError("Connection refused")
    result = _map_request_error(error)

    assert isinstance(result, APIConnectionError)
    assert "connection" in str(result).lower()
    assert result.__cause__ is error


def test_map_request_error_network_error() -> None:
    """NetworkError（else分岐）でAPIConnectionError返却"""
    error = httpx.NetworkError("Network unreachable")
    result = _map_request_error(error)

    assert isinstance(result, APIConnectionError)
    assert "network" in str(result).lower()
    assert result.__cause__ is error


# =============================================================================
# Classify Error Tests（_classify_error の検証）
# =============================================================================


def test_classify_error_non_retryable_logs_error() -> None:
    """TooManyRedirects時にlogger.errorが呼ばれる"""
    error = httpx.TooManyRedirects("Max redirects")
    mock_logger = Mock()

    with pytest.raises(APIClientError):
        _classify_error(error, mock_logger, is_async=False, method="GET", endpoint="/test")

    mock_logger.error.assert_called_once()
    call_kwargs = mock_logger.error.call_args
    assert call_kwargs[0][0] == "request_error_non_retryable"
    assert call_kwargs[1]["error_type"] == "TooManyRedirects"


def test_classify_error_non_retryable_async_prefix() -> None:
    """async呼び出し時にログイベント名にasync_プレフィックスが付く"""
    error = httpx.InvalidURL("Bad URL")
    mock_logger = Mock()

    with pytest.raises(APIClientError):
        _classify_error(error, mock_logger, is_async=True, method="GET", endpoint="/test")

    mock_logger.error.assert_called_once()
    call_kwargs = mock_logger.error.call_args
    assert call_kwargs[0][0] == "async_request_error_non_retryable"


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


def test_classify_error_retryable_timeout() -> None:
    """TimeoutException時にAPITimeoutErrorが返される"""
    error = httpx.TimeoutException("Timed out")
    mock_logger = Mock()

    result = _classify_error(error, mock_logger, is_async=True, method="GET", endpoint="/slow")

    assert isinstance(result, APITimeoutError)
    assert result.__cause__ is error
    mock_logger.warning.assert_called_once()
    call_kwargs = mock_logger.warning.call_args
    assert call_kwargs[0][0] == "async_request_error"
