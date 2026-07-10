"""Exception hierarchy tests for utils.exceptions."""

from collections.abc import Callable
from unittest.mock import Mock

import httpx
import pytest

from utils.exceptions import (
    APIClientError,
    APIConnectionError,
    APIHTTPError,
    APIJSONDecodeError,
    APIRetryError,
    APITimeoutError,
)

pytestmark = pytest.mark.unit


MockResponseFactory = Callable[[object | None], Mock]


@pytest.fixture()
def mock_response_factory() -> MockResponseFactory:
    """テスト用 Mock(spec=httpx.Response) を生成する factory fixture

    テスト間で mock 生成ロジックを集約し、httpx.Response 仕様変更時の
    修正を1箇所に限定する。

    Returns:
        payload（省略可）を受け取り、json.return_value を設定した
        Mock(spec=httpx.Response) を返す callable
    """

    def _factory(payload: object | None = None) -> Mock:
        response = Mock(spec=httpx.Response)
        if payload is not None:
            response.json.return_value = payload
        return response

    return _factory


def test_exception_hierarchy() -> None:
    """例外クラスの継承関係確認"""
    assert issubclass(APIConnectionError, APIClientError)
    assert issubclass(APITimeoutError, APIClientError)
    assert issubclass(APIHTTPError, APIClientError)
    assert issubclass(APIRetryError, APIClientError)
    assert issubclass(APIJSONDecodeError, APIClientError)
    assert issubclass(APIClientError, Exception)


def test_http_error_status_preservation(
    mock_response_factory: MockResponseFactory,
) -> None:
    """APIHTTPError がステータスコードを保持することを確認"""
    mock_response = mock_response_factory()
    mock_response.status_code = 404

    error = APIHTTPError("Not Found", status_code=404, response=mock_response)

    assert error.status_code == 404
    assert error.response == mock_response
    assert str(error) == "Not Found"


def test_retry_error_message() -> None:
    """APIRetryError のメッセージ確認"""
    error = APIRetryError("Max retries exceeded")
    assert str(error) == "Max retries exceeded"


def test_api_json_decode_error_init(mock_response_factory: MockResponseFactory) -> None:
    """APIJSONDecodeErrorのコンストラクタテスト"""
    mock_response = mock_response_factory()
    error = APIJSONDecodeError("Parse error", response=mock_response)

    assert str(error) == "Parse error"
    assert error.response == mock_response


def test_api_json_decode_error_without_response() -> None:
    """APIJSONDecodeError: responseなしでも動作"""
    error = APIJSONDecodeError("Parse error")

    assert str(error) == "Parse error"
    assert error.response is None
