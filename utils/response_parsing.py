"""JSON response parsing helpers for API clients."""

import json
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
        # NOTE: model_type は実行時には具象クラスだが、mypy は変数を型添字
        #   list[...] に使えない（valid-type）。実行時の正しさはテストで担保済みのため
        #   この行に限り type: ignore を付与する（Pydantic + mypy の既知の制約）。
        return TypeAdapter(list[model_type]).validate_python(data)  # type: ignore[valid-type]
    except ValidationError as e:
        raise APIJSONDecodeError(
            f"Invalid {model_type.__name__} response schema: {_format_validation_error(e)}",
            response=response,
        ) from e
