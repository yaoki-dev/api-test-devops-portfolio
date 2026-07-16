"""utils.response_parsing のJSON変換エラー契約テスト"""

import json
from collections.abc import Callable
from unittest.mock import Mock

import httpx
import pytest
from pydantic import BaseModel, Field

from utils.exceptions import (
    APIJSONDecodeError,
)
from utils.response_parsing import (
    parse_response_model as _parse_response_model,
)
from utils.response_parsing import (
    parse_response_model_list as _parse_response_model_list,
)
from utils.response_parsing import (
    safe_parse_json as _safe_parse_json,
)

pytestmark = pytest.mark.unit


MockResponseFactory = Callable[[object | None], Mock]


@pytest.fixture()
def mock_response_factory() -> MockResponseFactory:
    """httpx.Response 仕様変更時の修正点を1箇所に限定する。"""

    def _factory(payload: object | None = None) -> Mock:
        response = Mock(spec=httpx.Response)
        if payload is not None:
            response.json.return_value = payload
        return response

    return _factory


class DummyModel(BaseModel):
    id: int = Field(..., ge=1)
    name: str


def test_parse_response_model_success(mock_response_factory: MockResponseFactory) -> None:
    mock_response = mock_response_factory({"id": 1, "name": "test"})

    result = _parse_response_model(mock_response, DummyModel)

    assert isinstance(result, DummyModel)
    assert result.id == 1
    assert result.name == "test"


def test_parse_response_model_invalid_type(mock_response_factory: MockResponseFactory) -> None:
    mock_response = mock_response_factory([{"id": 1, "name": "test"}])

    with pytest.raises(APIJSONDecodeError, match="Expected object JSON for DummyModel, got list"):
        _parse_response_model(mock_response, DummyModel)


def test_parse_response_model_validation_error(mock_response_factory: MockResponseFactory) -> None:
    mock_response = mock_response_factory({"id": 0, "name": "test"})  # id < 1

    with pytest.raises(APIJSONDecodeError, match="Invalid DummyModel response schema"):
        _parse_response_model(mock_response, DummyModel)


def test_parse_response_model_list_success(mock_response_factory: MockResponseFactory) -> None:
    mock_response = mock_response_factory([{"id": 1, "name": "test1"}, {"id": 2, "name": "test2"}])

    result = _parse_response_model_list(mock_response, DummyModel)

    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(item, DummyModel) for item in result)
    assert result[0].id == 1
    assert result[1].name == "test2"


def test_parse_response_model_list_invalid_type(mock_response_factory: MockResponseFactory) -> None:
    mock_response = mock_response_factory({"id": 1, "name": "test"})

    with pytest.raises(APIJSONDecodeError, match="Expected array JSON for DummyModel, got dict"):
        _parse_response_model_list(mock_response, DummyModel)


def test_parse_response_model_list_validation_error(
    mock_response_factory: MockResponseFactory,
) -> None:
    """TypeAdapter が付与する index により、配列内の失敗要素を診断できることを固定する。"""
    mock_response = mock_response_factory([{"id": 1, "name": "test1"}, {"id": -1, "name": "test2"}])

    with pytest.raises(APIJSONDecodeError, match="Invalid DummyModel response schema") as exc_info:
        _parse_response_model_list(mock_response, DummyModel)

    # index=1（2番目の要素）が失敗したことが loc 先頭に表れる
    assert "1.id" in str(exc_info.value)


def test_safe_parse_json_invalid_json(
    mock_response_factory: MockResponseFactory,
) -> None:
    mock_response = mock_response_factory()
    mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "doc", 0)

    with pytest.raises(APIJSONDecodeError) as exc_info:
        _safe_parse_json(mock_response)

    assert "Failed to parse JSON" in str(exc_info.value)
    assert "Invalid JSON" in str(exc_info.value)  # str(e) の診断情報を保持
    assert exc_info.value.response == mock_response


def test_safe_parse_json_unicode_decode_error_converted_to_api_json_decode_error() -> None:
    """httpx 0.28.1 の不正UTF-8 UnicodeDecodeError を APIJSONDecodeError へ変換する。"""
    response = httpx.Response(200, content=b"\xff")

    with pytest.raises(APIJSONDecodeError) as exc_info:
        _safe_parse_json(response)

    assert isinstance(exc_info.value.__cause__, UnicodeDecodeError)
