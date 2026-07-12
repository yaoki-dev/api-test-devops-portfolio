"""github_rate_limit モジュールの独立ユニットテスト。

GW1 で抽出された純粋関数（_parse_rate_limit_header, _check_rate_limit_warning）と
公開定数（RATE_LIMIT_WARNING_THRESHOLD）の振る舞いを facade 非依存で検証する。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from utils.github_rate_limit import (
    RATE_LIMIT_WARNING_THRESHOLD,
    _check_rate_limit_warning,
    _log_and_sleep_for_retry,
    _parse_rate_limit_header,
)

pytestmark = pytest.mark.unit


# =============================================================================
# RATE_LIMIT_WARNING_THRESHOLD — 公開定数
# =============================================================================


def test_rate_limit_warning_threshold_is_ten() -> None:
    """公開定数 RATE_LIMIT_WARNING_THRESHOLD は 10 に固定されている。"""
    assert RATE_LIMIT_WARNING_THRESHOLD == 10
    assert isinstance(RATE_LIMIT_WARNING_THRESHOLD, int)


# =============================================================================
# _parse_rate_limit_header — 純粋関数
# =============================================================================


def test_parse_rate_limit_header_returns_int_from_header() -> None:
    """有効な整数値文字列がヘッダーに存在する場合、int を返す。"""
    headers = httpx.Headers({"x-ratelimit-remaining": "42"})
    result = _parse_rate_limit_header(
        headers, "x-ratelimit-remaining", default=100, logger=MagicMock()
    )
    assert result == 42


def test_parse_rate_limit_header_returns_zero() -> None:
    """ヘッダー値が "0" の場合、0 を返す。"""
    headers = httpx.Headers({"x-ratelimit-remaining": "0"})
    result = _parse_rate_limit_header(
        headers, "x-ratelimit-remaining", default=100, logger=MagicMock()
    )
    assert result == 0


def test_parse_rate_limit_header_returns_negative() -> None:
    """ヘッダー値が負数の場合、そのまま負数 int を返す。"""
    headers = httpx.Headers({"x-ratelimit-remaining": "-1"})
    result = _parse_rate_limit_header(
        headers, "x-ratelimit-remaining", default=100, logger=MagicMock()
    )
    assert result == -1


def test_parse_rate_limit_header_returns_large_value() -> None:
    """ヘッダー値が大きな数値の場合、そのまま int を返す。"""
    headers = httpx.Headers({"x-ratelimit-remaining": "5000"})
    result = _parse_rate_limit_header(
        headers, "x-ratelimit-remaining", default=100, logger=MagicMock()
    )
    assert result == 5000


def test_parse_rate_limit_header_returns_default_when_header_missing() -> None:
    """ヘッダー名が存在しない場合、default 値を返す。"""
    headers = httpx.Headers({})
    logger = MagicMock()
    result = _parse_rate_limit_header(headers, "x-ratelimit-remaining", default=100, logger=logger)
    assert result == 100
    logger.warning.assert_not_called()


def test_parse_rate_limit_header_returns_default_when_header_is_empty_string() -> None:
    """ヘッダー値が空文字列の場合、default を返し warning をログ出力する。"""
    headers = httpx.Headers({"x-ratelimit-remaining": ""})
    logger = MagicMock()
    result = _parse_rate_limit_header(headers, "x-ratelimit-remaining", default=100, logger=logger)
    assert result == 100
    logger.warning.assert_called_once()
    call_args = logger.warning.call_args
    assert call_args.kwargs["header"] == "x-ratelimit-remaining"


def test_parse_rate_limit_header_returns_default_when_header_is_non_numeric() -> None:
    """ヘッダー値が非数値文字列の場合、default を返し warning をログ出力する。"""
    headers = httpx.Headers({"x-ratelimit-remaining": "abc"})
    logger = MagicMock()
    result = _parse_rate_limit_header(headers, "x-ratelimit-remaining", default=100, logger=logger)
    assert result == 100
    logger.warning.assert_called_once()
    call_args = logger.warning.call_args
    assert call_args.kwargs["header"] == "x-ratelimit-remaining"


def test_parse_rate_limit_header_returns_default_when_header_is_float_string() -> None:
    """ヘッダー値が浮動小数点数文字列の場合、default を返す（int 変換失敗）。"""
    headers = httpx.Headers({"x-ratelimit-remaining": "3.14"})
    logger = MagicMock()
    result = _parse_rate_limit_header(headers, "x-ratelimit-remaining", default=100, logger=logger)
    assert result == 100
    logger.warning.assert_called_once()


def test_parse_rate_limit_header_truncates_value_in_warning() -> None:
    """warning ログ内の value は repr 先頭 100 文字に切り詰められる。"""
    long_value = "x" * 200
    headers = httpx.Headers({"x-ratelimit-remaining": long_value})
    logger = MagicMock()
    _parse_rate_limit_header(headers, "x-ratelimit-remaining", default=100, logger=logger)
    call_args = logger.warning.call_args
    assert len(call_args.kwargs["value"]) <= 100


# =============================================================================
# _check_rate_limit_warning — レート制限警告判定
# =============================================================================


def test_check_rate_limit_warning_returns_none_when_above_threshold() -> None:
    """remaining が閾値以上の場合、None を返す（警告不要）。"""
    headers = httpx.Headers({})
    result = _check_rate_limit_warning(headers, remaining=50, logger=MagicMock())
    assert result is None


def test_check_rate_limit_warning_returns_none_when_at_threshold() -> None:
    """remaining が閾値と等しい場合、None を返す（警告不要）。"""
    headers = httpx.Headers({})
    result = _check_rate_limit_warning(
        headers, remaining=RATE_LIMIT_WARNING_THRESHOLD, logger=MagicMock()
    )
    assert result is None


def test_check_rate_limit_warning_returns_reset_time_when_below_threshold() -> None:
    """remaining が閾値未満の場合、reset_time を返し warning をログ出力する。"""
    headers = httpx.Headers(
        {
            "x-ratelimit-reset": "1700000000",
        }
    )
    logger = MagicMock()
    result = _check_rate_limit_warning(headers, remaining=5, logger=logger)
    assert result == 1700000000
    logger.warning.assert_called_once()
    call_args = logger.warning.call_args
    assert call_args.kwargs["remaining"] == 5


def test_check_rate_limit_warning_returns_zero_reset_time() -> None:
    """reset ヘッダー値が "0" の場合、epoch=0 の isoformat 文字列をログ出力する。"""
    headers = httpx.Headers({"x-ratelimit-reset": "0"})
    logger = MagicMock()
    result = _check_rate_limit_warning(headers, remaining=3, logger=logger)
    assert result == 0
    logger.warning.assert_called_once()
    # epoch=0 は datetime.fromtimestamp(0, tz=UTC) → "1970-01-01T00:00:00+00:00"
    assert "1970-01-01" in logger.warning.call_args.kwargs["reset_time"]


def test_check_rate_limit_warning_handles_overflow_error() -> None:
    """datetime.fromtimestamp が OverflowError を送出する巨大な reset 値の場合、
    "unix:" プレフィックス付きの数値文字列で fallback する。"""
    # 2^63 超 で OverflowError を誘発
    huge_timestamp = 2**63 + 1
    headers = httpx.Headers(
        {
            "x-ratelimit-reset": str(huge_timestamp),
        }
    )
    logger = MagicMock()
    result = _check_rate_limit_warning(headers, remaining=2, logger=logger)
    assert result == huge_timestamp
    logger.warning.assert_called_once()
    reset_str = logger.warning.call_args.kwargs["reset_time"]
    assert reset_str == f"unix:{huge_timestamp}"


def test_check_rate_limit_warning_handles_negative_reset_time() -> None:
    """負の reset 値を受け取った場合でも、datetime.fromtimestamp で処理して reset_time を返す。"""
    headers = httpx.Headers(
        {
            "x-ratelimit-reset": "-1",
        }
    )
    logger = MagicMock()
    result = _check_rate_limit_warning(headers, remaining=2, logger=logger)
    # 負値は OverflowError にならず fromtimestamp が処理する（1969-12-31 相当）
    assert result == -1
    logger.warning.assert_called_once()


def test_check_rate_limit_warning_uses_default_when_reset_header_missing() -> None:
    """x-ratelimit-reset ヘッダーが存在しない場合、_RATE_LIMIT_RESET_FALLBACK (0) を使用する。"""
    headers = httpx.Headers({})
    logger = MagicMock()
    result = _check_rate_limit_warning(headers, remaining=1, logger=logger)
    assert result == 0
    logger.warning.assert_called_once()


# =============================================================================
# _log_and_sleep_for_retry — リトライ制御（非同期）
# =============================================================================


async def test_log_and_sleep_for_retry_sleeps_unless_final_attempt() -> None:
    """最終試行でなければ警告をログ出力し sleep する。"""
    error = httpx.TimeoutException("timeout")
    logger = MagicMock()

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await _log_and_sleep_for_retry(
            attempt=1,
            max_retries=3,
            method="GET",
            endpoint="/test",
            error=error,
            logger=logger,
            event="github_retry_timeout",
            error_context="connection_timeout",
        )

    logger.warning.assert_called_once()
    mock_sleep.assert_awaited_once()


async def test_log_and_sleep_for_retry_does_not_sleep_on_final_attempt() -> None:
    """最終試行では sleep せず、error をログ出力する。"""
    error = httpx.NetworkError("connection refused")
    logger = MagicMock()

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await _log_and_sleep_for_retry(
            attempt=2,
            max_retries=3,
            method="POST",
            endpoint="/repos",
            error=error,
            logger=logger,
            event="github_retry_network",
            error_context="connection_refused_retry",
        )

    logger.error.assert_called_once()
    mock_sleep.assert_not_awaited()


async def test_log_and_sleep_for_retry_includes_event_and_error_context() -> None:
    """ログ出力に event 名と error_context が含まれる。"""
    error = httpx.RemoteProtocolError("protocol error")
    logger = MagicMock()

    with patch("utils.github_rate_limit.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await _log_and_sleep_for_retry(
            attempt=0,
            max_retries=3,
            method="GET",
            endpoint="/users",
            error=error,
            logger=logger,
            event="github_retry_remote",
            error_context="remote_protocol_error",
        )

    mock_sleep.assert_awaited_once()
    call_args = logger.warning.call_args
    assert call_args.args[0] == "github_retry_remote"
    assert call_args.kwargs["error_context"] == "remote_protocol_error"
    assert call_args.kwargs["endpoint"] == "/users"
    assert call_args.kwargs["method"] == "GET"
