"""github_error_handler モジュールの独立ユニットテスト。

GW1 で抽出された純粋関数（redact_body_preview）、例外クラス
（SanitizedJSONDecodeError, GitHubAPIError 他）、ハンドラ関数の振る舞いを
facade 非依存で検証する。
"""

import json
import re
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


def test_redact_body_preview_different_inputs_produce_different_hashes() -> None:
    assert redact_body_preview("body A") != redact_body_preview("body B")


def test_redact_body_preview_handles_unicode() -> None:
    result = redact_body_preview("日本語のエラーメッセージ")
    assert result.startswith("[redacted:")


def test_redact_body_preview_handles_special_chars() -> None:
    body = "line1\nline2\tindented\x00null"
    result = redact_body_preview(body)
    assert result.startswith("[redacted:")


def test_redact_body_preview_never_returns_original_body() -> None:
    """元のボディ内容が結果に含まれない（PII 漏洩防止）。"""
    external_message = "ghp_external_message_token_12345"  # noqa: S105 — test fixture, not a real external_message
    result = redact_body_preview(external_message)
    assert "ghp_external_message" not in result


def test_redact_body_preview_returns_fixed_hash_format_for_empty_body() -> None:
    """空 body でも固定長 SHA256 fingerprint 形式を返す。"""
    result = redact_body_preview("")
    assert result == "[redacted:e3b0c44298fc1c14]"
    assert re.fullmatch(r"\[redacted:[0-9a-f]{16}\]", result)


def test_redact_body_preview_is_deterministic() -> None:
    body = "A" * 200
    assert redact_body_preview(body) == redact_body_preview(body)


def test_sanitized_json_decode_error_str_with_multiline_msg() -> None:
    cause = SanitizedJSONDecodeError("json.JSONDecodeError", "Expecting ',' delimiter", 42, 3, 5)
    result = str(cause)
    assert result.startswith("json.JSONDecodeError:")
    assert "pos=42" in result
    assert "lineno=3" in result
    assert "colno=5" in result


def test_sanitized_json_decode_error_is_exception_subclass() -> None:
    assert issubclass(SanitizedJSONDecodeError, Exception)


def test_rate_limit_error_inherits_from_github_api_error() -> None:
    assert issubclass(RateLimitError, GitHubAPIError)


def test_not_found_error_inherits_from_github_api_error() -> None:
    assert issubclass(NotFoundError, GitHubAPIError)


def test_github_server_error_inherits_from_github_api_error() -> None:
    assert issubclass(GitHubServerError, GitHubAPIError)


def test_rate_limit_error_has_reset_time() -> None:
    err = RateLimitError(1700000000)
    assert err.reset_time == 1700000000


def test_rate_limit_error_str_includes_iso_timestamp() -> None:
    from datetime import UTC, datetime

    reset_time = 1700000000
    err = RateLimitError(reset_time)
    expected_iso = datetime.fromtimestamp(reset_time, tz=UTC).isoformat()
    assert expected_iso in str(err)


def test_rate_limit_error_overflow_falls_back_to_unix_timestamp() -> None:
    """極端な reset_time は unix:{reset_time} 形式へフォールバックする。"""
    extreme_reset_time = 2**63
    err = RateLimitError(extreme_reset_time)
    assert err.reset_time == extreme_reset_time
    assert f"unix:{extreme_reset_time}" in str(err)


@pytest.mark.parametrize(
    "reset_time",
    [
        pytest.param(-1, id="negative_one"),
        pytest.param(-100, id="negative_hundred"),
        pytest.param(0, id="zero_boundary"),
    ],
)
def test_rate_limit_error_non_positive_reset_time_is_unknown(reset_time: int) -> None:
    """0以下のreset_timeをunknownへフォールバックする例外契約を検証する。"""
    err = RateLimitError(reset_time)
    assert err.reset_time == reset_time
    assert "unknown" in str(err)


def _make_response(status_code: int, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        headers=headers or {},
        request=httpx.Request("GET", "https://api.github.com/test"),
    )


def test_handle_403_raises_rate_limit_error_when_remaining_is_zero() -> None:
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
    response = _make_response(403)
    with pytest.raises(GitHubAPIError) as exc_info:
        _handle_403_response(
            response=response,
            rate_remaining=100,
            logger=MagicMock(),
        )
    assert "Access forbidden" in str(exc_info.value)


def test_handle_403_redacts_external_message() -> None:
    """外部メッセージが例外やログに露出せず、PII漏洩を防止することを検証する。"""
    external_message = "token=ghp_sensitive private-repo=user/restricted"
    response = httpx.Response(
        403,
        json={"message": external_message},
        request=httpx.Request("GET", "https://api.github.com/test"),
    )
    logger = MagicMock()

    with pytest.raises(GitHubAPIError) as exc_info:
        _handle_403_response(
            response=response,
            rate_remaining=100,
            logger=logger,
        )

    assert str(exc_info.value) == "Access forbidden"
    assert external_message not in str(exc_info.value)
    logger.warning.assert_called_once_with(
        "github_403_forbidden",
        message_preview=redact_body_preview(external_message),
    )
    assert external_message not in repr(logger.warning.call_args)


async def test_handle_5xx_sleeps_unless_final_attempt() -> None:
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


async def test_handle_5xx_raises_github_server_error_on_final_attempt() -> None:
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


def test_parse_json_response_returns_parsed_dict() -> None:
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = {"key": "value"}

    result = _parse_json_response(
        response=mock_response,
        endpoint="/test",
        logger=MagicMock(),
    )
    assert result == {"key": "value"}


def test_parse_json_response_returns_parsed_list() -> None:
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = [{"key": "value"}]

    result = _parse_json_response(
        response=mock_response,
        endpoint="/test",
        logger=MagicMock(),
    )
    assert result == [{"key": "value"}]


def test_parse_json_response_raises_github_api_error_on_invalid_json() -> None:
    """生のJSONDecodeErrorを漏らさず、SanitizedJSONDecodeErrorをcauseに保持する例外契約を検証する。"""
    logger = MagicMock()
    response = httpx.Response(
        200, content=b"not-valid-json", headers={"Content-Type": "application/json"}
    )

    with pytest.raises(GitHubAPIError) as exc_info:
        _parse_json_response(
            response=response,
            endpoint="/test",
            logger=logger,
        )

    assert "Invalid JSON response" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, SanitizedJSONDecodeError)
    assert not isinstance(exc_info.value.__cause__, json.JSONDecodeError)
    assert b"not-valid-json" not in repr(exc_info.value.__cause__).encode()
    # raise が except 節の外にあることを固定する。中に戻すと __context__ に
    # 生の json.JSONDecodeError（.doc に未リダクションの body を保持）が残る。
    assert exc_info.value.__context__ is None
    logger.error.assert_called_once()
    assert logger.error.call_args.kwargs["endpoint"] == "/test"


def test_parse_json_response_malformed_utf8_keeps_body_out_of_cause() -> None:
    """不正 UTF-8 body でも生の UnicodeDecodeError を漏らさず body を cause から締め出す。

    httpx の response.json() は bytes を直接デコードするため、不正 UTF-8 では
    JSONDecodeError ではなく UnicodeDecodeError が飛ぶ（両者に継承関係はない）。
    UnicodeDecodeError.object は JSONDecodeError.doc と同様に生 body を保持するため、
    捕捉しないと Sentry へ body が届き SanitizedJSONDecodeError を設けた意味がなくなる。
    行・列の概念を持たない型なので lineno/colno は -1（該当なし）で写す。
    """
    logger = MagicMock()
    response = httpx.Response(200, content=b'{"token": "ghp_secret_leaked_value" \xff}')

    with pytest.raises(GitHubAPIError) as exc_info:
        _parse_json_response(
            response=response,
            endpoint="/test",
            logger=logger,
        )

    assert "Invalid JSON response" in str(exc_info.value)
    cause = exc_info.value.__cause__
    assert isinstance(cause, SanitizedJSONDecodeError)
    assert not isinstance(cause, UnicodeDecodeError)
    assert b"ghp_secret_leaked_value" not in repr(cause).encode()
    assert cause.error_type == "builtins.UnicodeDecodeError"
    assert (cause.lineno, cause.colno) == (-1, -1)
    assert exc_info.value.__context__ is None
    assert logger.error.call_args.kwargs["error_type"] == "UnicodeDecodeError"


def test_parse_json_response_logs_on_decode_error() -> None:
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


def test_handle_http_status_error_raises_not_found_for_404() -> None:
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


def test_handle_403_response_no_json_log() -> None:
    response = httpx.Response(
        403,
        headers={"X-RateLimit-Remaining": "50", "X-RateLimit-Reset": "0"},
        content=b"not json",
    )
    logger = MagicMock()
    with pytest.raises(GitHubAPIError) as exc_info:
        _handle_403_response(response, logger=logger)
    logger.warning.assert_called_once()
    assert logger.warning.call_args.args[0] == "failed_to_parse_error_message"
    assert logger.warning.call_args.kwargs["status_code"] == 403
    assert logger.warning.call_args.kwargs["error_type"] == "JSONDecodeError"
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None


def test_handle_403_response_malformed_utf8_body_stays_forbidden() -> None:
    """不正 UTF-8 の secondary rate limit body は素通りせず Forbidden へ落ちる。

    httpx は不正 UTF-8 に対し UnicodeDecodeError を送出する（JSONDecodeError ではない）。
    捕捉しないと 403 整形が例外で抜け、呼び出し側が GitHubAPIError ではなく生の
    UnicodeDecodeError を受け取る（.object が body を保持したまま）。
    body をデコードできない以上 secondary 判定は不能なので、message 抽出不能の他ケースと
    同じく Forbidden に倒すのが正しい。RateLimitError に昇格しないことを固定する。
    """
    response = httpx.Response(
        403,
        headers={"X-RateLimit-Remaining": "50", "X-RateLimit-Reset": "0"},
        content=b'{"message": "You have exceeded a secondary rate limit \xff"}',
    )
    logger = MagicMock()
    with pytest.raises(GitHubAPIError) as exc_info:
        _handle_403_response(response, logger=logger)
    assert not isinstance(exc_info.value, RateLimitError)
    logger.warning.assert_called_once()
    assert logger.warning.call_args.args[0] == "failed_to_parse_error_message"
    assert logger.warning.call_args.kwargs["status_code"] == 403
    assert logger.warning.call_args.kwargs["error_type"] == "UnicodeDecodeError"
    # UnicodeDecodeError.start（不正バイト位置）が error_pos へ写ることを固定する。
    assert logger.warning.call_args.kwargs["error_pos"] == 54
    assert "error_lineno" not in logger.warning.call_args.kwargs
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None


def test_handle_403_response_empty_body_logs_no_warning() -> None:
    """空 body は「パース失敗」ではなく「message なし」として warning なしで扱う。

    body を持たない 429 が同じ抽出関数を通るようになったため、空 body を
    パース失敗として警告すると常態がノイズになる。この意図的な挙動変更を固定する
    （test_handle_403_response_no_json_log の非空・不正 JSON とは別経路）。
    """
    response = httpx.Response(
        403,
        headers={"X-RateLimit-Remaining": "50", "X-RateLimit-Reset": "0"},
        content=b"",
    )
    logger = MagicMock()
    with pytest.raises(GitHubAPIError) as exc_info:
        _handle_403_response(response, logger=logger)
    logger.warning.assert_not_called()
    assert not isinstance(exc_info.value, RateLimitError)


def test_handle_http_status_error_429_parse_failure_logs_status_code_429() -> None:
    """パース失敗 warning は 429 由来なら status_code=429 を載せる。

    このイベントは 403 と 429 の両経路から発火するため、status_code だけが由来の判別材料になる。
    403 側のテスト (test_handle_403_response_no_json_log) は status_code を 403 に
    固定実装しても通ってしまい、フィールドの存在意義そのものを検証できない。
    """
    response = httpx.Response(
        429,
        headers={"X-RateLimit-Remaining": "50", "X-RateLimit-Reset": "1700000000"},
        content=b"not json",
    )
    logger = MagicMock()
    with pytest.raises(RateLimitError):
        _handle_http_status_error(
            response=response,
            endpoint="/test",
            method="GET",
            logger=logger,
        )
    logger.warning.assert_called_once()
    assert logger.warning.call_args.args[0] == "failed_to_parse_error_message"
    assert logger.warning.call_args.kwargs["status_code"] == 429


_EXHAUSTED_PRIMARY_WITH_BOTH_HEADERS = {
    "X-RateLimit-Remaining": "0",
    "X-RateLimit-Reset": "1700000000",
    "Retry-After": "45",
}


def test_handle_403_exhausted_primary_keeps_retry_after_and_reset() -> None:
    """primary 枯渇の 403 でも Retry-After と Reset の両方を例外に保持する。

    GitHub docs は「Retry-After 経過まで再試行しない」と「remaining == 0 なら reset まで
    再試行しない」を独立条件として課すため、片方を破棄すると消費者が
    max(now + retry_after, reset_time) を計算できない。remaining == 0 では body を
    読まないため、非 JSON body でも warning が出ないことも同時に固定する。
    """
    response = httpx.Response(
        403,
        headers=_EXHAUSTED_PRIMARY_WITH_BOTH_HEADERS,
        content=b"not json",
    )
    logger = MagicMock()
    with pytest.raises(RateLimitError) as exc_info:
        _handle_403_response(response, logger=logger)
    assert exc_info.value.retry_after == 45
    assert exc_info.value.reset_time == 1700000000
    logger.warning.assert_not_called()


def test_handle_http_status_error_429_exhausted_primary_keeps_retry_after_and_reset() -> None:
    """primary 枯渇の 429 は 403 と同じ判定規則で両ヘッダーを保持する。

    403 側 (test_handle_403_exhausted_primary_keeps_retry_after_and_reset) と同一ヘッダーで
    同一の (retry_after, reset_time) になることを固定し、経路間の非対称の再発を防ぐ。
    remaining == 0 で body を読まないため、非 JSON body でも warning は出ない。
    """
    response = httpx.Response(
        429,
        headers=_EXHAUSTED_PRIMARY_WITH_BOTH_HEADERS,
        content=b"not json",
    )
    logger = MagicMock()
    with pytest.raises(RateLimitError) as exc_info:
        _handle_http_status_error(
            response=response,
            endpoint="/test",
            method="GET",
            logger=logger,
        )
    assert exc_info.value.retry_after == 45
    assert exc_info.value.reset_time == 1700000000
    logger.warning.assert_not_called()


def test_handle_403_with_retry_after_but_no_rate_limit_signal_stays_forbidden() -> None:
    """remaining != 0 かつ非 secondary の 403 は Retry-After が付いていても Forbidden のまま。

    rate limit 判定に Retry-After の有無を使うと、WAF 等が Retry-After を付けた
    通常の Forbidden を RateLimitError に誤分類する。判定材料は remaining と
    message 文言のみであることを固定する。
    """
    response = httpx.Response(
        403,
        headers={"X-RateLimit-Remaining": "50", "Retry-After": "45"},
        json={"message": "Forbidden by policy"},
    )
    logger = MagicMock()
    with pytest.raises(GitHubAPIError, match="^Access forbidden$") as exc_info:
        _handle_403_response(response, logger=logger)
    assert not isinstance(exc_info.value, RateLimitError)


def test_handle_403_exhausted_primary_without_retry_after_defers_to_reset() -> None:
    """Retry-After 欠落の primary 枯渇 403 は retry_after=None で reset 待ちに委ねる。"""
    response = httpx.Response(
        403,
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1700000000"},
    )
    logger = MagicMock()
    with pytest.raises(RateLimitError) as exc_info:
        _handle_403_response(response, logger=logger)
    assert exc_info.value.retry_after is None
    assert exc_info.value.reset_time == 1700000000


def test_handle_403_exhausted_primary_without_reset_keeps_retry_after() -> None:
    """Reset 欠落の primary 枯渇 403 でも Retry-After は破棄せず保持する（429 側と対称）。"""
    response = httpx.Response(
        403,
        headers={"X-RateLimit-Remaining": "0", "Retry-After": "45"},
    )
    logger = MagicMock()
    with pytest.raises(RateLimitError) as exc_info:
        _handle_403_response(response, logger=logger)
    assert exc_info.value.retry_after == 45
    assert exc_info.value.reset_time == 0


def test_handle_http_status_error_429_exhausted_primary_without_reset_keeps_retry_after() -> None:
    """Reset 欠落の primary 枯渇 429 でも Retry-After は破棄せず保持する。

    reset_time は欠落フォールバックの 0（= 不明）になるため、Retry-After まで捨てると
    消費者が待機時間を一切算出できなくなる。
    """
    response = httpx.Response(
        429,
        headers={"X-RateLimit-Remaining": "0", "Retry-After": "45"},
    )
    logger = MagicMock()
    with pytest.raises(RateLimitError) as exc_info:
        _handle_http_status_error(
            response=response,
            endpoint="/test",
            method="GET",
            logger=logger,
        )
    assert exc_info.value.retry_after == 45
    assert exc_info.value.reset_time == 0


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"message": 999}, id="message-is-not-str"),
        pytest.param([{"message": "listed"}], id="body-is-not-dict"),
    ],
)
def test_handle_403_response_skips_preview_for_unexpected_body_shapes(body: object) -> None:
    """message が str でない / body が dict でない 403 は message_preview を出さずに送出する。

    isinstance ガードを外すと raw_message[:200] が TypeError になるため、
    GitHubAPIError 以外が漏れないことを分岐ごとに固定する。
    """
    logger = MagicMock()
    response = httpx.Response(403, json=body)

    with pytest.raises(GitHubAPIError, match="^Access forbidden$") as exc_info:
        _handle_403_response(response, rate_remaining=50, logger=logger)

    logger.warning.assert_not_called()
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None


def test_handle_403_response_truncates_message_to_200_chars() -> None:
    logger = MagicMock()
    response = httpx.Response(403, json={"message": "z" * 201})
    with pytest.raises(GitHubAPIError, match="^Access forbidden$"):
        _handle_403_response(response, rate_remaining=50, logger=logger)
    assert logger.warning.call_args.kwargs["message_preview"] == redact_body_preview("z" * 200)


def test_handle_403_response_no_truncation_at_boundary() -> None:
    logger = MagicMock()
    exact_message = "z" * 200
    response = httpx.Response(403, json={"message": exact_message})
    with pytest.raises(GitHubAPIError, match="^Access forbidden$"):
        _handle_403_response(response, rate_remaining=50, logger=logger)
    assert logger.warning.call_args.kwargs["message_preview"] == redact_body_preview(exact_message)


def test_handle_http_status_error_uses_debug_for_other_4xx() -> None:
    response = httpx.Response(400, request=httpx.Request("GET", "https://api.github.com/test"))
    logger = MagicMock()
    with pytest.raises(GitHubAPIError, match=r"^HTTP 400 error$") as exc_info:
        _handle_http_status_error(response, "/test", "GET", logger=logger)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    logger.debug.assert_called_once_with(
        "http_status_error",
        status_code=400,
        endpoint="/test",
        method="GET",
        body_preview=redact_body_preview(""),
    )
    logger.warning.assert_not_called()


def test_handle_http_status_error_uses_warning_for_401() -> None:
    response = httpx.Response(401, request=httpx.Request("GET", "https://api.github.com/test"))
    logger = MagicMock()
    with pytest.raises(GitHubAPIError, match=r"^HTTP 401 error$") as exc_info:
        _handle_http_status_error(response, "/test", "GET", logger=logger)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    logger.warning.assert_called_once_with(
        "http_status_error",
        status_code=401,
        endpoint="/test",
        method="GET",
        body_preview=redact_body_preview(""),
    )
    logger.debug.assert_not_called()


def test_handle_http_status_error_warning_truncates_body_preview_for_401() -> None:
    response = httpx.Response(
        401,
        content=b"A" * 201,
        request=httpx.Request("GET", "https://api.github.com/test"),
    )
    logger = MagicMock()
    with pytest.raises(GitHubAPIError, match=r"^HTTP 401 error$"):
        _handle_http_status_error(response, "/test", "GET", logger=logger)
    assert logger.warning.call_args.kwargs["body_preview"] == redact_body_preview("A" * 200)


def test_handle_http_status_error_with_5xx_raises_github_api_error() -> None:
    response = httpx.Response(503, request=httpx.Request("GET", "https://api.github.com/test"))
    with pytest.raises(GitHubAPIError, match=r"^HTTP 503 error$"):
        _handle_http_status_error(response, "/test", "GET", logger=MagicMock())


def test_parse_json_response_unexpected_parse_error_propagates() -> None:
    response = MagicMock(spec=httpx.Response)
    response.json.side_effect = RuntimeError("parser exploded")
    with pytest.raises(RuntimeError, match="parser exploded"):
        _parse_json_response(response, "/test", logger=MagicMock())


@pytest.mark.parametrize(
    ("body", "expected_preview_source"),
    [
        pytest.param("x" * 201, "x" * 200, id="ascii_truncation"),
        pytest.param("x" * 200, "x" * 200, id="ascii_boundary"),
        pytest.param("あ" * 201, "あ" * 200, id="multibyte_truncation"),
    ],
)
def test_handle_http_status_error_body_preview_truncation(
    body: str, expected_preview_source: str
) -> None:
    response = httpx.Response(
        400, text=body, request=httpx.Request("GET", "https://api.github.com/test")
    )
    logger = MagicMock()
    with pytest.raises(GitHubAPIError):
        _handle_http_status_error(response, "/test", "GET", logger=logger)
    expected = response.content[:200].decode(response.encoding or "utf-8", errors="replace")
    assert logger.debug.call_args.kwargs["body_preview"] == redact_body_preview(expected)


def test_handle_http_status_error_with_invalid_bytes() -> None:
    response = httpx.Response(
        400,
        content=b"\xff\xfe invalid bytes \x80\x81",
        request=httpx.Request("GET", "https://api.github.com/test"),
    )
    with pytest.raises(GitHubAPIError, match=r"^HTTP 400 error$"):
        _handle_http_status_error(response, "/test", "GET", logger=MagicMock())


def test_handle_http_status_error_cause_excludes_response_body() -> None:
    sensitive_body = "token=SUPER_SECRET_API_KEY_12345"  # noqa: S105
    response = httpx.Response(
        422, request=httpx.Request("GET", "https://api.github.com/repos/test"), text=sensitive_body
    )
    logger = MagicMock()
    with pytest.raises(GitHubAPIError) as exc_info:
        _handle_http_status_error(response, "/repos/test", "GET", logger=logger)
    body_preview_logged = logger.debug.call_args.kwargs["body_preview"]
    assert body_preview_logged.startswith("[redacted:")
    assert sensitive_body not in body_preview_logged
    assert sensitive_body not in str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
