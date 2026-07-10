"""Response parsing tests for utils.response_parsing."""

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


class DummyModel(BaseModel):
    """テスト用のシンプルなPydanticモデル"""

    id: int = Field(..., ge=1)
    name: str


def test_parse_response_model_success(mock_response_factory: MockResponseFactory) -> None:
    """_parse_response_model: 正常系（dict -> model）"""
    mock_response = mock_response_factory({"id": 1, "name": "test"})

    result = _parse_response_model(mock_response, DummyModel)

    assert isinstance(result, DummyModel)
    assert result.id == 1
    assert result.name == "test"


def test_parse_response_model_invalid_type(mock_response_factory: MockResponseFactory) -> None:
    """_parse_response_model: 異常系（配列が返ってきた場合）"""
    mock_response = mock_response_factory([{"id": 1, "name": "test"}])

    with pytest.raises(APIJSONDecodeError, match="Expected object JSON for DummyModel, got list"):
        _parse_response_model(mock_response, DummyModel)


def test_parse_response_model_validation_error(mock_response_factory: MockResponseFactory) -> None:
    """_parse_response_model: 異常系（バリデーションエラー）"""
    mock_response = mock_response_factory({"id": 0, "name": "test"})  # id < 1

    with pytest.raises(APIJSONDecodeError, match="Invalid DummyModel response schema"):
        _parse_response_model(mock_response, DummyModel)


def test_parse_response_model_list_success(mock_response_factory: MockResponseFactory) -> None:
    """_parse_response_model_list: 正常系（list -> list[model]）"""
    mock_response = mock_response_factory([{"id": 1, "name": "test1"}, {"id": 2, "name": "test2"}])

    result = _parse_response_model_list(mock_response, DummyModel)

    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(item, DummyModel) for item in result)
    assert result[0].id == 1
    assert result[1].name == "test2"


def test_parse_response_model_list_invalid_type(mock_response_factory: MockResponseFactory) -> None:
    """_parse_response_model_list: 異常系（オブジェクトが返ってきた場合）"""
    mock_response = mock_response_factory({"id": 1, "name": "test"})

    with pytest.raises(APIJSONDecodeError, match="Expected array JSON for DummyModel, got dict"):
        _parse_response_model_list(mock_response, DummyModel)


def test_parse_response_model_list_validation_error(
    mock_response_factory: MockResponseFactory,
) -> None:
    """_parse_response_model_list: 異常系（要素にバリデーションエラーがある場合）

    エラーメッセージに失敗要素の index（loc 先頭）が含まれ、配列内の
    どの要素が原因か診断できることを検証する（TypeAdapter による index 付与）。
    """
    mock_response = mock_response_factory([{"id": 1, "name": "test1"}, {"id": -1, "name": "test2"}])

    with pytest.raises(APIJSONDecodeError, match="Invalid DummyModel response schema") as exc_info:
        _parse_response_model_list(mock_response, DummyModel)

    # index=1（2番目の要素）が失敗したことが loc 先頭に表れる
    assert "1.id" in str(exc_info.value)


def test_safe_parse_json_invalid_json(
    mock_response_factory: MockResponseFactory,
) -> None:
    """不正なJSONでAPIJSONDecodeErrorが発生（エラーパス）"""
    mock_response = mock_response_factory()
    mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "doc", 0)

    with pytest.raises(APIJSONDecodeError) as exc_info:
        _safe_parse_json(mock_response)

    assert "Failed to parse JSON" in str(exc_info.value)
    assert "Invalid JSON" in str(exc_info.value)  # str(e) の診断情報を保持
    assert exc_info.value.response == mock_response
