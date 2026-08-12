"""例外階層の契約テスト。"""

from typing import Protocol
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


class MockResponseFactory(Protocol):
    """payload 省略呼び出しを型に表現するための fixture 呼び出し規約。

    ``Callable[[object | None], Mock]`` は引数をちょうど1個要求し既定値を表現できないため、
    payload なしの呼び出しが mypy で ``[call-arg]`` になる。
    """

    def __call__(self, payload: object | None = None) -> Mock: ...


@pytest.fixture()
def mock_response_factory() -> MockResponseFactory:
    """mock生成を集約し、httpx.Response互換の修正点を1箇所に閉じ込める。"""

    def _factory(payload: object | None = None) -> Mock:
        response = Mock(spec=httpx.Response)
        if payload is not None:
            response.json.return_value = payload
        return response

    return _factory


def test_exception_hierarchy() -> None:
    assert issubclass(APIConnectionError, APIClientError)
    assert issubclass(APITimeoutError, APIClientError)
    assert issubclass(APIHTTPError, APIClientError)
    assert issubclass(APIRetryError, APIClientError)
    assert issubclass(APIJSONDecodeError, APIClientError)
    assert issubclass(APIClientError, Exception)


def test_http_error_status_preservation(
    mock_response_factory: MockResponseFactory,
) -> None:
    mock_response = mock_response_factory()
    mock_response.status_code = 404

    error = APIHTTPError("Not Found", status_code=404, response=mock_response)

    assert error.status_code == 404
    assert error.response == mock_response
    assert str(error) == "Not Found"


def test_retry_error_message() -> None:
    error = APIRetryError("Max retries exceeded")
    assert str(error) == "Max retries exceeded"


def test_api_json_decode_error_init(mock_response_factory: MockResponseFactory) -> None:
    mock_response = mock_response_factory()
    error = APIJSONDecodeError("Parse error", response=mock_response)

    assert str(error) == "Parse error"
    assert error.response == mock_response


def test_api_json_decode_error_without_response() -> None:
    error = APIJSONDecodeError("Parse error")

    assert str(error) == "Parse error"
    assert error.response is None
