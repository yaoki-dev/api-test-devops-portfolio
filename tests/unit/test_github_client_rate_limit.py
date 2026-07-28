"""GitHub API非同期クライアントのrate-limit統合テスト

AsyncGitHubClient 経由で primary / secondary rate limit の判別、RateLimitError への変換、
reset / retry-after ヘッダーの解釈と不正値のフォールバック、警告ログの出力回数を検証する。
純粋関数単体の検証は tests/unit/test_github_rate_limit.py が担当する。
"""

from datetime import UTC, datetime
from unittest.mock import ANY, patch

import httpx
import pytest
import respx
from structlog.testing import capture_logs

from utils.github_client import AsyncGitHubClient
from utils.github_error_handler import GitHubAPIError, RateLimitError
from utils.github_rate_limit import SECONDARY_RATE_LIMIT_FALLBACK_RETRY_AFTER

pytestmark = pytest.mark.unit

GITHUB_API_BASE_URL = "https://api.github.com"

# octokit issue #566 が記録した実レスポンスの body message。
# secondary rate limit はヘッダーでは primary と区別できないため、この文言が唯一の判定材料になる。
SECONDARY_RATE_LIMIT_MESSAGE = (
    "You have exceeded a secondary rate limit. Please wait a few minutes before you try again."
)


@respx.mock
async def test_rate_limit_exceeded():
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=403,
        headers={
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": "1640000000",
        },
    )

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.reset_time == 1640000000
    assert "Rate limit exceeded" in str(exc_info.value)
    assert route.call_count == 1


@respx.mock
async def test_rate_limit_warning_log():
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=200,
        json={"login": "octocat"},
        headers={
            "X-RateLimit-Remaining": "5",  # < 10 → 警告ログトリガー
            "X-RateLimit-Reset": "1640000000",
        },
    )

    async with AsyncGitHubClient() as client:
        with patch.object(client.logger, "warning") as mock_warning:
            await client.get_user("octocat")

            # 警告ログ呼び出し確認（引数順序変更に強い形式）
            mock_warning.assert_called_once_with(
                "rate_limit_low",
                remaining=5,
                reset_time=ANY,
            )

    assert route.call_count == 1


@respx.mock
async def test_403_non_rate_limit():
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [
        httpx.Response(
            403,
            json={"message": "Repository access blocked"},
            headers={"X-RateLimit-Remaining": "50"},
        ),
        httpx.Response(
            403,
            json={"message": "Repository access blocked"},
            headers={"X-RateLimit-Remaining": "50"},
        ),
    ]

    async with AsyncGitHubClient() as client:
        with pytest.raises(GitHubAPIError, match="Access forbidden"):
            await client.get_user("octocat")

        with pytest.raises(GitHubAPIError, match="Access forbidden") as exc_info:
            await client.get_user("octocat")
        assert not isinstance(exc_info.value, RateLimitError)


@respx.mock
async def test_invalid_rate_limit_header_remaining():
    """不正なレート制限ヘッダーで外部例外を出さず、安全なフォールバックへ進む。"""
    respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=200,
        json={"login": "octocat"},
        headers={"X-RateLimit-Remaining": "N/A"},
    )

    with capture_logs() as log_output:
        async with AsyncGitHubClient() as client:
            result = await client.get_user("octocat")

    assert result["login"] == "octocat"
    warning_logs = [log for log in log_output if log.get("event") == "invalid_rate_limit_header"]
    assert len(warning_logs) == 1
    assert warning_logs[0]["log_level"] == "warning"
    assert warning_logs[0]["header"] == "X-RateLimit-Remaining"
    assert warning_logs[0]["value"] == repr("N/A")


@respx.mock
async def test_invalid_rate_limit_header_403():
    """403経路でも不正ヘッダーを再解析せず、warning後に安全なAPIエラーへ落とす。"""
    respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=403,
        json={"message": "Forbidden"},
        headers={"X-RateLimit-Remaining": "invalid"},
    )

    with capture_logs() as log_output:
        async with AsyncGitHubClient() as client:
            with pytest.raises(GitHubAPIError):
                await client.get_user("octocat")

    warning_logs = [log for log in log_output if log.get("event") == "invalid_rate_limit_header"]
    assert len(warning_logs) == 1
    for log_entry in warning_logs:
        assert log_entry["log_level"] == "warning"
        assert log_entry["header"] == "X-RateLimit-Remaining"
        assert log_entry["value"] == repr("invalid")


@respx.mock
async def test_invalid_rate_limit_header_429_secondary_logs_warning_once():
    """429の secondary 判定でも X-RateLimit-Remaining を二重パースしない。

    403 は _handle_403_response にパース済みの値を渡して重複を避けており
    (test_invalid_rate_limit_header_403)、429 も同じ不変条件「1レスポンスにつき warning 1件」
    を満たす必要がある。secondary 判定を後付けした際、この注入を忘れると warning が 2 件になる。
    """
    respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=429,
        json={"message": SECONDARY_RATE_LIMIT_MESSAGE},
        headers={"X-RateLimit-Remaining": "invalid"},
    )

    with capture_logs() as log_output:
        async with AsyncGitHubClient() as client:
            with pytest.raises(RateLimitError) as exc_info:
                await client.get_user("octocat")

    warning_logs = [log for log in log_output if log.get("event") == "invalid_rate_limit_header"]
    assert len(warning_logs) == 1
    assert warning_logs[0]["header"] == "X-RateLimit-Remaining"
    # 不正値は fallback (0以外) に倒れるため primary 枯渇とは判定されず、既定60秒が載る。
    assert exc_info.value.retry_after == SECONDARY_RATE_LIMIT_FALLBACK_RETRY_AFTER


@respx.mock
async def test_invalid_rate_limit_reset_header_low_remaining():
    """レート制限ヘッダーの一部が壊れても、警告と処理継続を両立する。"""
    respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=200,
        json={"login": "octocat"},
        headers={
            "X-RateLimit-Remaining": "5",
            "X-RateLimit-Reset": "not-a-timestamp",
        },
    )

    with capture_logs() as log_output:
        async with AsyncGitHubClient() as client:
            result = await client.get_user("octocat")

    assert result["login"] == "octocat"

    # invalid_rate_limit_header warning（X-RateLimit-Reset不正値）
    invalid_header_logs = [
        log for log in log_output if log.get("event") == "invalid_rate_limit_header"
    ]
    assert len(invalid_header_logs) == 1
    assert invalid_header_logs[0]["log_level"] == "warning"
    assert invalid_header_logs[0]["header"] == "X-RateLimit-Reset"
    assert invalid_header_logs[0]["value"] == repr("not-a-timestamp")

    # rate_limit_low warning（remaining=5 < 10）
    rate_limit_low_logs = [log for log in log_output if log.get("event") == "rate_limit_low"]
    assert len(rate_limit_low_logs) == 1
    assert rate_limit_low_logs[0]["log_level"] == "warning"
    assert rate_limit_low_logs[0]["remaining"] == 5
    # フォールバック: reset_time=0 → epoch（1970-01-01T00:00:00+00:00）
    expected_reset_time = datetime(1970, 1, 1, 0, 0, tzinfo=UTC).isoformat()
    assert rate_limit_low_logs[0]["reset_time"] == expected_reset_time


@respx.mock
async def test_invalid_rate_limit_reset_header_rate_limit_exceeded():
    """remaining=0ではreset解析失敗後もRateLimitErrorによる待機制御を維持する。"""
    respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=403,
        json={"message": "Forbidden"},
        headers={
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": "broken",
        },
    )

    with capture_logs() as log_output:
        async with AsyncGitHubClient() as client:
            with pytest.raises(RateLimitError):
                await client.get_user("octocat")

    # invalid_rate_limit_header warningは共通パスで1件のみ（resetヘッダー二重パース回避）
    invalid_header_logs = [
        log for log in log_output if log.get("event") == "invalid_rate_limit_header"
    ]
    assert len(invalid_header_logs) == 1
    for log_entry in invalid_header_logs:
        assert log_entry["log_level"] == "warning"
        assert log_entry["header"] == "X-RateLimit-Reset"
        assert log_entry["value"] == repr("broken")

    # rate_limit_low warningが1件（remaining=0 < 10）
    rate_limit_low_logs = [log for log in log_output if log.get("event") == "rate_limit_low"]
    assert len(rate_limit_low_logs) == 1
    assert rate_limit_low_logs[0]["log_level"] == "warning"
    assert rate_limit_low_logs[0]["remaining"] == 0
    # フォールバック: reset_time=0 → epoch（1970-01-01T00:00:00+00:00）
    expected_reset_time = datetime(1970, 1, 1, 0, 0, tzinfo=UTC).isoformat()
    assert rate_limit_low_logs[0]["reset_time"] == expected_reset_time


@respx.mock
async def test_429_response_raises_rate_limit_error() -> None:
    """secondary の message を含まない 429 では retry_after が None のままになる。

    429 は primary / secondary の両方で返る。両者を区別しないと secondary 向けの
    60秒フォールバックが primary にも適用され、reset まで待つ仕様に反する待機時間を
    呼び出し側へ渡す。
    """
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        429,
        headers={"X-RateLimit-Reset": "1700000000"},
    )

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.reset_time == 1700000000
    assert exc_info.value.retry_after is None
    assert route.call_count == 1


@respx.mock
async def test_httpx_status_error_429_defensive_path() -> None:
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        429,
        headers={"X-RateLimit-Reset": "1640000000"},
    )

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.__context__ is None  # active exception context 外 raise による PII 防止
    assert exc_info.value.reset_time == 1640000000
    assert "Rate limit exceeded" in str(exc_info.value)
    assert route.call_count == 1


@respx.mock
async def test_429_response_missing_reset_header_falls_back_to_zero() -> None:
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(429)

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.reset_time == 0
    assert "unknown" in str(exc_info.value)  # else分岐のメッセージ内容を保護
    assert route.call_count == 1


@respx.mock
async def test_httpx_status_error_429_missing_reset_header_falls_back_to_zero() -> None:
    request = httpx.Request("GET", f"{GITHUB_API_BASE_URL}/users/octocat")
    response_429 = httpx.Response(429, request=request)
    error_429 = httpx.HTTPStatusError(
        "429 Too Many Requests", request=request, response=response_429
    )

    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [error_429]

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.reset_time == 0
    assert "unknown" in str(exc_info.value)  # else分岐のメッセージ内容を保護
    assert route.call_count == 1


@respx.mock
async def test_httpx_status_error_429_secondary_rate_limit_sets_retry_after() -> None:
    """防御的パスの429でも secondary を検出し retry_after を載せる。

    通常パスの429とは別関数（_handle_http_status_error）が処理するため、
    片方だけ実装・修正しても気付けない。両経路を独立に固定する。
    """
    request = httpx.Request("GET", f"{GITHUB_API_BASE_URL}/users/octocat")
    response_429 = httpx.Response(
        429,
        request=request,
        headers={"Retry-After": "45"},
        json={"message": SECONDARY_RATE_LIMIT_MESSAGE},
    )
    error_429 = httpx.HTTPStatusError(
        "429 Too Many Requests", request=request, response=response_429
    )

    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [error_429]

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.retry_after == 45
    assert route.call_count == 1


@respx.mock
async def test_httpx_status_error_429_secondary_falls_back_to_default_retry_after() -> None:
    request = httpx.Request("GET", f"{GITHUB_API_BASE_URL}/users/octocat")
    response_429 = httpx.Response(
        429,
        request=request,
        headers={"X-RateLimit-Remaining": "25"},
        json={"message": SECONDARY_RATE_LIMIT_MESSAGE},
    )
    error_429 = httpx.HTTPStatusError(
        "429 Too Many Requests", request=request, response=response_429
    )

    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [error_429]

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.retry_after == SECONDARY_RATE_LIMIT_FALLBACK_RETRY_AFTER
    assert route.call_count == 1


@respx.mock
async def test_httpx_status_error_429_secondary_with_exhausted_primary_defers_to_reset() -> None:
    """防御的パス(429)でも remaining=0 の secondary で既定60秒へ倒さない。

    通常パスと防御的パスは別関数が待機秒数を決めるため、片方だけ修正しても気付けない。
    実際この組み合わせは、通常パス側を直した時点では防御的パス側が未固定のままだった。
    """
    request = httpx.Request("GET", f"{GITHUB_API_BASE_URL}/users/octocat")
    response_429 = httpx.Response(
        429,
        request=request,
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1700000000"},
        json={"message": SECONDARY_RATE_LIMIT_MESSAGE},
    )
    error_429 = httpx.HTTPStatusError(
        "429 Too Many Requests", request=request, response=response_429
    )

    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [error_429]

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.retry_after is None
    assert exc_info.value.reset_time == 1700000000
    assert route.call_count == 1


@respx.mock
async def test_httpx_status_error_429_secondary_invalid_remaining_logs_warning_once() -> None:
    """防御的パスの429でも不正 remaining は warning 1件で既定60秒へ倒す。

    通常パス側の同名不変条件は test_invalid_rate_limit_header_429_secondary_logs_warning_once
    が固定しているが、防御的パスは _handle_http_status_error が独立に remaining を解決するため
    別テストが要る。この分岐が 403 側のように remaining を先読みして
    _resolve_rate_limit_retry_after への注入を忘れると warning が 2 件になる。
    """
    request = httpx.Request("GET", f"{GITHUB_API_BASE_URL}/users/octocat")
    response_429 = httpx.Response(
        429,
        request=request,
        headers={"X-RateLimit-Remaining": "invalid"},
        json={"message": SECONDARY_RATE_LIMIT_MESSAGE},
    )
    error_429 = httpx.HTTPStatusError(
        "429 Too Many Requests", request=request, response=response_429
    )

    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [error_429]

    with capture_logs() as log_output:
        async with AsyncGitHubClient() as client:
            with pytest.raises(RateLimitError) as exc_info:
                await client.get_user("octocat")

    warning_logs = [log for log in log_output if log.get("event") == "invalid_rate_limit_header"]
    assert len(warning_logs) == 1
    assert warning_logs[0]["header"] == "X-RateLimit-Remaining"
    # 不正値は fallback (0以外) に倒れるため primary 枯渇とは判定されず、既定60秒が載る。
    assert exc_info.value.retry_after == SECONDARY_RATE_LIMIT_FALLBACK_RETRY_AFTER
    assert route.call_count == 1


@respx.mock
async def test_403_secondary_rate_limit_falls_back_to_default_retry_after() -> None:
    """secondary rate limit は remaining != 0 かつ Retry-After 欠損でも RateLimitError にする。

    primary 超過と違い remaining は 0 にならず Retry-After も付かないことがあるため、
    ヘッダーだけでは通常の 403 Forbidden と区別できない。ヘッダー値は octokit issue #566 が
    記録した実レスポンス（remaining=25 / Retry-After なし）をそのまま再現している。
    """
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        403,
        headers={
            "X-RateLimit-Limit": "30",
            "X-RateLimit-Remaining": "25",
            "X-RateLimit-Reset": "1675318655",
        },
        json={"message": SECONDARY_RATE_LIMIT_MESSAGE},
    )

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.retry_after == SECONDARY_RATE_LIMIT_FALLBACK_RETRY_AFTER
    assert route.call_count == 1


@respx.mock
async def test_403_secondary_rate_limit_uses_retry_after_header() -> None:
    """GitHub指定のRetry-Afterを既定値より優先し、実際の待機時間を尊重する。"""
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        403,
        headers={"X-RateLimit-Remaining": "25", "Retry-After": "30"},
        json={"message": SECONDARY_RATE_LIMIT_MESSAGE},
    )

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.retry_after == 30
    assert route.call_count == 1


@respx.mock
async def test_403_secondary_rate_limit_http_date_retry_after_falls_back() -> None:
    """RFC 9110 は Retry-After に HTTP-date も許すため、秒数パース失敗を許容値として扱う。"""
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        403,
        headers={
            "X-RateLimit-Remaining": "25",
            "Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT",
        },
        json={"message": SECONDARY_RATE_LIMIT_MESSAGE},
    )

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.retry_after == SECONDARY_RATE_LIMIT_FALLBACK_RETRY_AFTER
    assert route.call_count == 1


@respx.mock
async def test_403_secondary_rate_limit_non_positive_retry_after_falls_back() -> None:
    """非正の Retry-After は待機時間として無意味なため既定へ倒す。

    HTTP-date のテストは int() が失敗して既定へ倒れるのに対し、こちらは int() が成功した上で
    値が非正になる経路を通る。行き先は同じ既定だが到達経路が異なるため両方を固定する。
    """
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        403,
        headers={"X-RateLimit-Remaining": "25", "Retry-After": "0"},
        json={"message": SECONDARY_RATE_LIMIT_MESSAGE},
    )

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.retry_after == SECONDARY_RATE_LIMIT_FALLBACK_RETRY_AFTER
    assert route.call_count == 1


@respx.mock
async def test_403_non_json_body_is_not_detected_as_secondary_rate_limit() -> None:
    """body が JSON でない 403（プロキシの HTML エラー等）で誤検出も例外送出もしない。"""
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        403,
        headers={"X-RateLimit-Remaining": "25"},
        content=b"<html>secondary rate limit</html>",
    )

    async with AsyncGitHubClient() as client:
        with pytest.raises(GitHubAPIError) as exc_info:
            await client.get_user("octocat")

    assert not isinstance(exc_info.value, RateLimitError)
    assert route.call_count == 1


@respx.mock
async def test_429_secondary_rate_limit_uses_retry_after_header() -> None:
    """通常経路でもGitHub指定のRetry-Afterを既定値より優先する。"""
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        429,
        headers={"X-RateLimit-Remaining": "25", "Retry-After": "45"},
        json={"message": SECONDARY_RATE_LIMIT_MESSAGE},
    )

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.retry_after == 45
    assert route.call_count == 1


@respx.mock
async def test_429_secondary_rate_limit_falls_back_to_default_retry_after() -> None:
    """通常パス(429)で Retry-After 欠損・remaining!=0 なら既定60秒へ倒す。

    既定60秒は 403 経路にもテストがあるが、429 通常パスの配線は別関数なので独立に固定する。
    """
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        429,
        headers={"X-RateLimit-Remaining": "25"},
        json={"message": SECONDARY_RATE_LIMIT_MESSAGE},
    )

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.retry_after == SECONDARY_RATE_LIMIT_FALLBACK_RETRY_AFTER
    assert route.call_count == 1


@respx.mock
async def test_429_secondary_rate_limit_with_exhausted_primary_defers_to_reset() -> None:
    """primary quota 枯渇中(remaining=0)の secondary で既定60秒へ倒さない。

    GitHub docs の待機時間の優先順位は Retry-After → remaining == 0 なら reset → 最低1分。
    ここで60秒を返すと quota 枯渇のまま再送させ、docs が警告する BAN を招く。

    retry_after is None は「secondary と判定されなかった」場合にも成立するため、本テスト単体
    では検出が働いたことまでは示せない（それは Retry-After 系のテストが担う）。ここで固定する
    のは remaining == 0 のとき 60 を返さないことに限る。
    """
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        429,
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1700000000"},
        json={"message": SECONDARY_RATE_LIMIT_MESSAGE},
    )

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.retry_after is None
    assert exc_info.value.reset_time == 1700000000
    assert route.call_count == 1


@respx.mock
async def test_httpx_status_error_403_defensive_path_uses_rate_limit_headers() -> None:
    """通常経路と防御的経路のRateLimitError判定を一致させ、経路差の回帰を防ぐ。"""
    request = httpx.Request("GET", f"{GITHUB_API_BASE_URL}/users/octocat")
    response_403 = httpx.Response(
        403,
        headers={
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": "1700000000",
        },
        request=request,
    )
    error_403 = httpx.HTTPStatusError("403 Forbidden", request=request, response=response_403)

    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [error_403]

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.reset_time == 1700000000
    assert exc_info.value.__context__ is None
    assert route.call_count == 1


@respx.mock
async def test_check_rate_limit_warning_overflow_reset_time() -> None:
    """巨大なreset値のログ変換に失敗しても、レート制限処理を継続する。"""
    # 2**63 はほとんどのプラットフォームで datetime.fromtimestamp が
    # OverflowError または OSError を送出する値
    overflow_reset: int = 2**63

    respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=200,
        json={"login": "octocat"},
        headers={
            "X-RateLimit-Remaining": "5",  # < 10 → _check_rate_limit_warning 実行
            "X-RateLimit-Reset": str(overflow_reset),
        },
    )

    with capture_logs() as log_output:
        async with AsyncGitHubClient() as client:
            result = await client.get_user("octocat")

    assert result["login"] == "octocat"

    rate_limit_low_logs = [log for log in log_output if log.get("event") == "rate_limit_low"]
    assert len(rate_limit_low_logs) == 1
    assert rate_limit_low_logs[0]["log_level"] == "warning"
    assert rate_limit_low_logs[0]["remaining"] == 5

    assert rate_limit_low_logs[0]["reset_time"] == f"unix:{overflow_reset}"


@respx.mock
async def test_429_uses_warning_reset_time_from_rate_limit_check() -> None:
    """429 応答受信時に _check_rate_limit_warning が返した warning_reset_time を
    RateLimitError の reset_time として使用することを検証する。

    フロー:
    1. X-RateLimit-Remaining=5（閾値未満）→ _check_rate_limit_warning が reset_time を返す
    2. 429 応答 → warning_reset_time が非 None なので X-RateLimit-Reset の再パースを省略
    3. RateLimitError(reset_time) が発生
    """
    expected_reset_time = 1700000999
    respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        429,
        headers={
            "X-RateLimit-Remaining": "5",  # < 10 → _check_rate_limit_warning が実行される
            "X-RateLimit-Reset": str(expected_reset_time),
        },
    )

    async with AsyncGitHubClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_user("octocat")

    assert exc_info.value.reset_time == expected_reset_time
    assert exc_info.value.__cause__ is None  # from None で PII 漏洩防止
