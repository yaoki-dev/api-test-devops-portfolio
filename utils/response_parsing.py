"""JSON response parsing helpers for API clients."""

import json
from collections.abc import Callable
from functools import cache
from typing import Any, cast

import httpx
from pydantic import BaseModel, TypeAdapter, ValidationError

from utils.exceptions import APIJSONDecodeError


def safe_parse_json(response: httpx.Response) -> Any:
    """レスポンスJSONを安全にパース

    Args:
        response: HTTPレスポンスオブジェクト

    Returns:
        パースされたJSONデータ

    Raises:
        APIJSONDecodeError: JSONパース失敗時

    Notes:
        ``json.JSONDecodeError`` の ``str(e)`` にはパース位置情報（行番号・
        文字位置）が含まれるが、httpx例外と異なりホスト名・プロキシ設定等の
        機密情報は含まれない。デバッグに有用な診断情報を保持するため
        ``str(e)`` をそのまま使用する。
        また、``APIJSONDecodeError.response`` に元の ``httpx.Response``
        オブジェクトを保持するが、レスポンスボディには機密データが含まれる
        可能性があるためログには出力しない。デバッグ時は呼び出し元で
        ``e.response`` を通じてアクセス可能。

    """
    try:
        return cast(Any, response.json())
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        # httpx は不正な UTF-8 ボディに対し JSONDecodeError ではなく
        # UnicodeDecodeError を送出するため、両方を捕捉する。
        raise APIJSONDecodeError(
            f"Failed to parse JSON response: {e}",
            response=response,
        ) from e


def _format_validation_error(e: ValidationError) -> str:
    details = "; ".join(
        f"{'.'.join(map(str, err.get('loc', ()))) or '<root>'}: "
        f"{err.get('msg', 'validation error')} ({err.get('type', 'unknown')})"
        for err in e.errors(include_input=False)[:3]
    )
    more = e.error_count() - 3
    suffix = f"; ... +{more} more" if more > 0 else ""
    return f"{e.error_count()} validation error(s): {details}{suffix}"


@cache
def _build_list_adapter(model_type: type[BaseModel]) -> TypeAdapter[list[Any]]:
    """``list[model_type]`` の ``TypeAdapter`` をモデル型ごとに1度だけ構築する。

    Notes:
        ``TypeAdapter`` の生成は pydantic-core スキーマ構築を伴うため、公式は
        モジュールレベルで1度だけ生成する形を推奨している。``model_type`` は
        実行時引数でモジュール変数にできないので、型をキーにしたキャッシュへ
        一般化した。モデル型は有界（動的生成経路なし）で無制限キャッシュは安全。

        ``functools.cache`` は戻り値の型パラメータだけでなく引数の型検査も消す
        ため、この関数へ直接渡した不正な型は mypy を素通りし pydantic 内部の
        例外になる。必ず型を再表明する ``_list_adapter`` 経由で呼ぶこと。

    """
    return TypeAdapter(list[model_type])  # type: ignore[valid-type]


def _list_adapter[M: BaseModel](model_type: type[M]) -> TypeAdapter[list[M]]:
    """キャッシュ済みの ``TypeAdapter`` を、モデル型を保った形で返す。

    Notes:
        ``@cache`` を直接ジェネリック関数へ付けると戻り値が
        ``TypeAdapter[list[Any]]`` へ退化し、``type[M: BaseModel]`` の引数制約
        まで失われる（非モデル型を渡しても mypy が検出できない）。キャッシュ層を
        分離しこの薄い層で型を再表明することで、呼び出し側は ``list[M]`` として
        静的に検証される。

    """
    return _build_list_adapter(model_type)


def validate_parsed_model[M: BaseModel](
    data: object,
    model_type: type[M],
    *,
    error_factory: Callable[[str], Exception],
) -> M:
    """パース済みデータをPydanticモデルへ検証して変換する。"""
    try:
        return model_type.model_validate(data)
    except ValidationError as e:
        raise error_factory(
            f"Invalid {model_type.__name__} response schema: {_format_validation_error(e)}"
        ) from None


def validate_parsed_model_list[M: BaseModel](
    data: object,
    model_type: type[M],
    *,
    error_factory: Callable[[str], Exception],
) -> list[M]:
    """パース済み配列をPydanticモデル配列へ検証して変換する。"""
    try:
        # TypeAdapter(list[model]) を使うと ValidationError の loc に
        # 失敗要素の index が自動付与される。
        return _list_adapter(model_type).validate_python(data)
    except ValidationError as e:
        raise error_factory(
            f"Invalid {model_type.__name__} response schema: {_format_validation_error(e)}"
        ) from None


def parse_response_model[ResponseModelT: BaseModel](
    response: httpx.Response, model_type: type[ResponseModelT]
) -> ResponseModelT:
    """レスポンスJSONをPydanticモデルへ検証して変換する。"""
    data = safe_parse_json(response)
    if not isinstance(data, dict):
        raise APIJSONDecodeError(
            f"Expected object JSON for {model_type.__name__}, got {type(data).__name__}",
            response=response,
        )
    try:
        return model_type.model_validate(data)
    except ValidationError as e:
        raise APIJSONDecodeError(
            f"Invalid {model_type.__name__} response schema: {_format_validation_error(e)}",
            response=response,
        ) from e


def parse_response_model_list[ResponseModelT: BaseModel](
    response: httpx.Response, model_type: type[ResponseModelT]
) -> list[ResponseModelT]:
    """レスポンスJSON配列をPydanticモデル配列へ検証して変換する。"""
    data = safe_parse_json(response)
    if not isinstance(data, list):
        raise APIJSONDecodeError(
            f"Expected array JSON for {model_type.__name__}, got {type(data).__name__}",
            response=response,
        )
    try:
        # TypeAdapter(list[model]) を使うと ValidationError の loc に
        # 失敗要素の index が自動付与される（例: loc=("0", "user_id")）。
        # _format_validation_error が loc を "." 結合するため "0.user_id: ..."
        # のように、配列内のどの要素が失敗したか診断可能になる。
        return _list_adapter(model_type).validate_python(data)
    except ValidationError as e:
        raise APIJSONDecodeError(
            f"Invalid {model_type.__name__} response schema: {_format_validation_error(e)}",
            response=response,
        ) from e
