"""utils.response_parsing のJSON変換エラー契約テスト"""

import json
from typing import Protocol
from unittest.mock import Mock

import httpx
import pytest
from pydantic import BaseModel, Field, ValidationError

from models.responses import GitHubRepo, GitHubUser
from utils.exceptions import (
    APIJSONDecodeError,
)
from utils.response_parsing import (
    _build_list_adapter,
    _list_adapter,
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
from utils.response_parsing import (
    safe_parse_json_object as _safe_parse_json_object,
)
from utils.response_parsing import (
    validate_parsed_model as _validate_parsed_model,
)
from utils.response_parsing import (
    validate_parsed_model_list as _validate_parsed_model_list,
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


def test_validate_parsed_model_success_and_ignores_future_fields() -> None:
    result = _validate_parsed_model(
        {"login": "octocat", "id": 1, "future_field": "ignored"},
        GitHubUser,
        error_factory=ValueError,
    )

    assert result.login == "octocat"
    assert result.id == 1
    assert not hasattr(result, "future_field")


def test_validate_parsed_model_list_success() -> None:
    result = _validate_parsed_model_list(
        [
            {"name": "repo-a", "id": 1, "full_name": "octocat/repo-a"},
            {"name": "repo-b", "id": 2, "full_name": "octocat/repo-b"},
        ],
        GitHubRepo,
        error_factory=ValueError,
    )

    assert [repo.name for repo in result] == ["repo-a", "repo-b"]
    assert all(isinstance(repo, GitHubRepo) for repo in result)


def test_list_adapter_is_cached_per_model_type() -> None:
    """TypeAdapter の再構築を防ぐキャッシュが、モデル型ごとに正しく分離されることを検証する。

    キャッシュが壊れると呼び出しごとに pydantic-core スキーマが再構築され、
    型を跨いで共有されると誤ったモデルで検証してしまう。
    """
    assert _list_adapter(GitHubRepo) is _list_adapter(GitHubRepo)
    # mypy は両辺の宣言型が別なので比較が自明と判定するが、ここで確かめたいのは
    # 「キャッシュが実行時に型ごとのオブジェクトを返す」という宣言型の裏付けそのもの。
    assert _list_adapter(GitHubRepo) is not _list_adapter(GitHubUser)  # type: ignore[comparison-overlap]

    # identity だけでは「キャッシュされた adapter が正しいモデルで検証するか」を
    # 保証できないため、型ごとの検証挙動まで確認する。
    repos = _list_adapter(GitHubRepo).validate_python(
        [{"name": "repo-a", "id": 1, "full_name": "octocat/repo-a"}]
    )
    assert isinstance(repos[0], GitHubRepo)

    users = _list_adapter(GitHubUser).validate_python([{"login": "octocat", "id": 1}])
    assert isinstance(users[0], GitHubUser)

    # GitHubUser の payload を GitHubRepo の adapter へ通すと失敗する
    # （= キャッシュが型を跨いで共有されていない）
    with pytest.raises(ValidationError):
        _list_adapter(GitHubRepo).validate_python([{"login": "octocat", "id": 1}])

    # @cache をジェネリックな _list_adapter 側へ戻すと戻り値と引数制約が Any へ
    # 退化するが、退化版も mypy を通るため型検査では検出できない。キャッシュが
    # どちらの層にあるかを構造的に固定して、この無音な後退を防ぐ。
    # 型保持の手段を別機構（overload 等）へ変える場合はこの assert も更新する。
    assert not hasattr(_list_adapter, "cache_info")
    assert hasattr(_build_list_adapter, "cache_info")


def test_validate_parsed_model_rejects_strict_type_drift() -> None:
    with pytest.raises(ValueError, match="Invalid GitHubUser response schema"):
        _validate_parsed_model(
            {"login": "octocat", "id": "8"},
            GitHubUser,
            error_factory=ValueError,
        )


def test_validate_parsed_model_rejects_missing_required_field() -> None:
    with pytest.raises(ValueError, match="Invalid GitHubUser response schema"):
        _validate_parsed_model({"id": 1}, GitHubUser, error_factory=ValueError)


def test_validate_parsed_model_list_rejects_non_list() -> None:
    with pytest.raises(ValueError, match="Invalid GitHubRepo response schema"):
        _validate_parsed_model_list(
            {"name": "repo", "id": 1, "full_name": "octocat/repo"},
            GitHubRepo,
            error_factory=ValueError,
        )


def test_validate_parsed_model_uses_error_factory() -> None:
    def error_factory(message: str) -> Exception:
        return RuntimeError(f"wrapped: {message}")

    with pytest.raises(RuntimeError, match="wrapped: Invalid GitHubUser"):
        _validate_parsed_model({"id": 1}, GitHubUser, error_factory=error_factory)


def test_validate_parsed_model_error_is_private_and_chainless() -> None:
    with pytest.raises(ValueError) as exc_info:
        _validate_parsed_model(
            {"login": 123, "id": "secret-id"},
            GitHubUser,
            error_factory=ValueError,
        )

    message = str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True
    assert "123" not in message
    assert "secret-id" not in message


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


@pytest.mark.parametrize(
    ("payload", "expected_type_name"),
    [
        ([{"id": 1}], "list"),
        ("plain string", "str"),
        (42, "int"),
        (True, "bool"),
    ],
)
def test_safe_parse_json_object_rejects_non_object(
    mock_response_factory: MockResponseFactory,
    payload: object,
    expected_type_name: str,
) -> None:
    """トップレベルが JSON オブジェクトでない場合に APIJSONDecodeError を送出する。

    RFC 7159 上 JSON のトップレベルは配列・スカラーも取り得るため、``dict`` を
    返す契約のメソッドは境界で検証しないと呼び出し側で素の ``TypeError`` が漏れる。
    """
    mock_response = mock_response_factory(payload)

    with pytest.raises(APIJSONDecodeError) as exc_info:
        _safe_parse_json_object(mock_response)

    assert "Expected object JSON response" in str(exc_info.value)
    assert expected_type_name in str(exc_info.value)
    assert exc_info.value.response == mock_response


def test_safe_parse_json_object_rejects_null(
    mock_response_factory: MockResponseFactory,
) -> None:
    """``null`` ボディは fixture の payload 省略と区別して個別に検証する。"""
    mock_response = mock_response_factory()
    mock_response.json.return_value = None

    with pytest.raises(APIJSONDecodeError) as exc_info:
        _safe_parse_json_object(mock_response)

    assert "NoneType" in str(exc_info.value)


def test_safe_parse_json_object_returns_dict(
    mock_response_factory: MockResponseFactory,
) -> None:
    payload = {"id": 1, "title": "t"}
    mock_response = mock_response_factory(payload)

    assert _safe_parse_json_object(mock_response) == payload
