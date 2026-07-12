"""github_error_handler モジュールの独立ユニットテスト。

GW1 で抽出された純粋関数（redact_body_preview）、例外クラス
（SanitizedJSONDecodeError, GitHubAPIError 他）、ハンドラ関数の振る舞いを
facade 非依存で検証する。
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from utils.github_error_handler import (
    GitHubAPIError,
    GitHubServerError,
    NotFoundError,
    RateLimitError,
    SanitizedJSONDecodeError,
    _handle_5xx_response,
    _handle_403_response,
    _handle_http_status_error,
    _parse_json_response,
    redact_body_preview,
)

pytestmark = pytest.mark.unit


# =============================================================================
# redact_body_preview — PII 抑制関数
# =============================================================================


def test_redact_body_preview_different_inputs_produce_different_hashes() -> None:
    """異なる入力は異なるハッシュを返す。"""
    assert redact_body_preview("body A") != redact_body_preview("body B")


def test_redact_body_preview_handles_unicode() -> None:
    """非 ASCII 文字を含む入力でもエラーなくハッシュを返す。"""
    result = redact_body_preview("日本語のエラーメッセージ")
    assert result.startswith("[redacted:")


def test_redact_body_preview_handles_special_chars() -> None:
    """特殊文字（改行、タブ、null）を含む文字列も処理できる。"""
    body = "line1\nline2\tindented\x00null"
    result = redact_body_preview(body)
    assert result.startswith("[redacted:")


def test_redact_body_preview_never_returns_original_body() -> None:
    """元のボディ内容が結果に含まれない（PII 漏洩防止）。"""
    secret = "ghp_secret_token_12345"  # noqa: S105 — test fixture, not a real secret
    result = redact_body_preview(secret)
    assert "ghp_secret" not in result


# =============================================================================
# SanitizedJSONDecodeError — PII 安全な JSON エラー
# =============================================================================


def test_sanitized_json_decode_error_str_with_multiline_msg() -> None:
    """複雑な msg も正しく文字列化される。"""
    cause = SanitizedJSONDecodeError("json.JSONDecodeError", "Expecting ',' delimiter", 42, 3, 5)
    result = str(cause)
    assert result.startswith("json.JSONDecodeError:")
    assert "pos=42" in result
    assert "lineno=3" in result
    assert "colno=5" in result


def test_sanitized_json_decode_error_is_exception_subclass() -> None:
    """SanitizedJSONDecodeError は Exception のサブクラス。"""
    assert issubclass(SanitizedJSONDecodeError, Exception)


# =============================================================================
# 例外階層
# =============================================================================


def test_rate_limit_error_inherits_from_github_api_error() -> None:
    """RateLimitError は GitHubAPIError のサブクラス。"""
    assert issubclass(RateLimitError, GitHubAPIError)


def test_not_found_error_inherits_from_github_api_error() -> None:
    """NotFoundError は GitHubAPIError のサブクラス。"""
    assert issubclass(NotFoundError, GitHubAPIError)


def test_github_server_error_inherits_from_github_api_error() -> None:
    """GitHubServerError は GitHubAPIError のサブクラス。"""
    assert issubclass(GitHubServerError, GitHubAPIError)


def test_rate_limit_error_has_reset_time() -> None:
    """RateLimitError は reset_time 属性を持つ。"""
    err = RateLimitError(1700000000)
    assert err.reset_time == 1700000000


def test_rate_limit_error_str_includes_iso_timestamp() -> None:
    """RateLimitError の文字列表現に ISO 8601 形式の reset 時刻が含まれる。"""
    from datetime import UTC, datetime

    reset_time = 1700000000
    err = RateLimitError(reset_time)
    expected_iso = datetime.fromtimestamp(reset_time, tz=UTC).isoformat()
    assert expected_iso in str(err)


# =============================================================================
# _handle_403_response — 403 レート制限判別
# =============================================================================


def _make_response(status_code: int, headers: dict | None = None) -> httpx.Response:
    """httpx.Response の簡易ファクトリ。"""
    return httpx.Response(
        status_code=status_code,
        headers=headers or {},
        request=httpx.Request("GET", "https://api.github.com/test"),
    )


def test_handle_403_raises_rate_limit_error_when_remaining_is_zero() -> None:
    """rate_remaining=0 の 403 は RateLimitError を送出する。"""
    response = _make_response(403)
    with pytest.raises(RateLimitError) as exc_info:
        _handle_403_response(
            response=response,
            rate_remaining=0,
            reset_time=1700000000,
            logger=MagicMock(),
        )
    assert exc_info.value.reset_time == 1700000000


def test_handle_403_raises_github_api_error_when_remaining_is_negative() -> None:
    """rate_remaining<0（フォールバック値）の 403 は GitHubAPIError。
    == 0 のみが RateLimitError、負数は通常の 403 扱い。"""
    response = _make_response(403)
    with pytest.raises(GitHubAPIError):
        _handle_403_response(
            response=response,
            rate_remaining=-1,
            reset_time=1700000000,
            logger=MagicMock(),
        )


def test_handle_403_raises_rate_limit_when_remaining_none_header_zero() -> None:
    """rate_remaining=None でレスポンスヘッダーが 0 の場合も RateLimitError。"""
    response = _make_response(
        403,
        headers={
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": "1700000000",
        },
    )
    with pytest.raises(RateLimitError) as exc_info:
        _handle_403_response(
            response=response,
            rate_remaining=None,
            logger=MagicMock(),
        )
    assert exc_info.value.reset_time == 1700000000


def test_handle_403_raises_github_api_error_when_remaining_positive() -> None:
    """rate_remaining > 0 の 403 は通常の GitHubAPIError。"""
    response = _make_response(403)
    with pytest.raises(GitHubAPIError) as exc_info:
        _handle_403_response(
            response=response,
            rate_remaining=100,
            logger=MagicMock(),
        )
    assert "Access forbidden" in str(exc_info.value)


# =============================================================================
# _handle_5xx_response — 5xx リトライ制御（非同期）
# =============================================================================


@pytest.mark.asyncio
async def test_handle_5xx_sleeps_unless_final_attempt() -> None:
    """最終試行でなければログ出力し sleep する。"""
    response = _make_response(503)
    logger = MagicMock()

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await _handle_5xx_response(
            response=response,
            attempt=1,
            endpoint="/test",
            method="GET",
            max_retries=3,
            logger=logger,
        )

    logger.warning.assert_called_once()
    mock_sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_5xx_raises_github_server_error_on_final_attempt() -> None:
    """最終試行では GitHubServerError を送出し sleep しない。"""
    response = _make_response(502)
    logger = MagicMock()

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with pytest.raises(GitHubServerError) as exc_info:
            await _handle_5xx_response(
                response=response,
                attempt=2,
                endpoint="/repos",
                method="POST",
                max_retries=3,
                logger=logger,
            )

    assert "502" in str(exc_info.value)
    logger.error.assert_called_once()
    mock_sleep.assert_not_awaited()


# =============================================================================
# _parse_json_response — JSON パース + PII 安全なエラー（同期）
# =============================================================================


def test_parse_json_response_returns_parsed_dict() -> None:
    """有効な JSON body から dict を返す。"""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = {"key": "value"}

    result = _parse_json_response(
        response=mock_response,
        endpoint="/test",
        logger=MagicMock(),
    )
    assert result == {"key": "value"}


def test_parse_json_response_returns_parsed_list() -> None:
    """有効な JSON body から list を返す。"""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = [{"key": "value"}]

    result = _parse_json_response(
        response=mock_response,
        endpoint="/test",
        logger=MagicMock(),
    )
    assert result == [{"key": "value"}]


def test_parse_json_response_raises_github_api_error_on_invalid_json() -> None:
    """不正な JSON body は GitHubAPIError（cause=SanitizedJSONDecodeError）を送出。"""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "not json", 0)

    with pytest.raises(GitHubAPIError) as exc_info:
        _parse_json_response(
            response=mock_response,
            endpoint="/test",
            logger=MagicMock(),
        )

    assert "Invalid JSON response" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, SanitizedJSONDecodeError)
    assert "not json" not in str(exc_info.value.__cause__)


def test_parse_json_response_logs_on_decode_error() -> None:
    """JSON デコード失敗時に logger.error を呼ぶ。"""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "bad", 0)
    logger = MagicMock()

    with pytest.raises(GitHubAPIError):
        _parse_json_response(
            response=mock_response,
            endpoint="/users",
            logger=logger,
        )

    logger.error.assert_called_once()
    assert logger.error.call_args.kwargs["endpoint"] == "/users"


# =============================================================================
# _handle_http_status_error — HTTP エラー → 例外階層マッピング
# =============================================================================


def test_handle_http_status_error_raises_not_found_for_404() -> None:
    """404 は NotFoundError を送出する。"""
    response = _make_response(404)
    with pytest.raises(NotFoundError) as exc_info:
        _handle_http_status_error(
            response=response,
            endpoint="/repos/nonexistent",
            method="GET",
            logger=MagicMock(),
        )
    assert exc_info.value.__cause__ is None


def test_handle_http_status_error_raises_rate_limit_for_429() -> None:
    """429 は RateLimitError を送出する（セカンダリレート制限）。"""
    response = _make_response(
        429,
        headers={
            "X-RateLimit-Reset": "1700000000",
        },
    )
    with pytest.raises(RateLimitError) as exc_info:
        _handle_http_status_error(
            response=response,
            endpoint="/test",
            method="GET",
            logger=MagicMock(),
        )
    assert exc_info.value.reset_time == 1700000000


def test_handle_http_status_error_raises_generic_for_401() -> None:
    """401 は GitHubAPIError を送出する。"""
    response = _make_response(401)
    with pytest.raises(GitHubAPIError) as exc_info:
        _handle_http_status_error(
            response=response,
            endpoint="/user",
            method="GET",
            logger=MagicMock(),
        )
    assert "401" in str(exc_info.value)


def test_handle_http_status_error_raises_generic_for_422() -> None:
    """422 は GitHubAPIError を送出する。"""
    response = _make_response(422)
    with pytest.raises(GitHubAPIError) as exc_info:
        _handle_http_status_error(
            response=response,
            endpoint="/repos",
            method="POST",
            logger=MagicMock(),
        )
    assert "422" in str(exc_info.value)


def test_handle_http_status_error_all_use_from_none() -> None:
    """全ての例外送出で __cause__ は None（PII 漏洩防止）。"""
    with pytest.raises(NotFoundError) as exc_info:
        _handle_http_status_error(
            response=_make_response(404),
            endpoint="/t",
            method="GET",
            logger=MagicMock(),
        )
    assert exc_info.value.__cause__ is None

    with pytest.raises(GitHubAPIError) as exc_info2:
        _handle_http_status_error(
            response=_make_response(401),
            endpoint="/t",
            method="GET",
            logger=MagicMock(),
        )
    assert exc_info2.value.__cause__ is None
