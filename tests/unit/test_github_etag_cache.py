"""github_etag_cache モジュールの独立ユニットテスト。"""

from unittest.mock import Mock, patch

import httpx
import pytest
from structlog.testing import capture_logs

from utils.github_error_handler import GitHubAPIError
from utils.github_etag_cache import _ETAG_PATTERN, GitHubETagCache

pytestmark = pytest.mark.unit


def _make_cache(max_cache_entries: int = 256) -> GitHubETagCache:
    return GitHubETagCache(max_cache_entries, logger=Mock())


def test_prepare_headers_with_etag() -> None:
    cache = _make_cache()
    cache._etag_cache["/repos/test"] = "etag-abc"
    assert cache._prepare_headers("/repos/test") == {"If-None-Match": "etag-abc"}


def test_prepare_headers_without_etag() -> None:
    assert _make_cache()._prepare_headers("/repos/test") == {}


def test_handle_304_response_cache_hit() -> None:
    cache = _make_cache()
    cached = {"id": 1, "login": "user"}
    cache._data_cache["/user"] = cached
    assert cache._handle_304_response("/user") == cached


def test_handle_304_response_cache_miss_logs_and_omits_query_params() -> None:
    cache = _make_cache()
    cache_key = "/users/octocat/repos?per_page=30&sort=updated"
    cache._etag_cache[cache_key] = "etag-value"
    with (
        patch.object(cache, "logger") as logger,
        pytest.raises(GitHubAPIError, match="Cache inconsistency") as exc_info,
    ):
        cache._handle_304_response(cache_key)
    assert "?" not in str(exc_info.value)
    logger.error.assert_called_once()
    assert logger.error.call_args.kwargs["endpoint"] == "/users/octocat/repos"


def test_update_etag_cache_with_and_without_etag() -> None:
    cache = _make_cache()
    cache._update_etag_cache(
        "/repos/test", httpx.Response(200, headers={"ETag": '"abc123"'}), {"id": 1}
    )
    assert cache._etag_cache["/repos/test"] == '"abc123"'
    assert cache._data_cache["/repos/test"] == {"id": 1}
    cache._update_etag_cache("/repos/test", httpx.Response(200), {"id": 2})
    assert "/repos/test" not in cache._etag_cache
    assert "/repos/test" not in cache._data_cache


def test_update_etag_cache_evicts_oldest_and_refreshes_existing() -> None:
    cache = _make_cache(max_cache_entries=2)
    for key, etag, payload in [
        ("/first", '"etag-1"', {"id": 1}),
        ("/second", '"etag-2"', {"id": 2}),
        ("/first", '"etag-1b"', {"id": 10}),
        ("/third", '"etag-3"', {"id": 3}),
    ]:
        cache._update_etag_cache(key, httpx.Response(200, headers={"ETag": etag}), payload)
    assert list(cache._etag_cache) == ["/first", "/third"]
    assert cache._etag_cache["/first"] == '"etag-1b"'


def test_update_etag_cache_enforces_limit_before_insert_with_reserve() -> None:
    cache = _make_cache(max_cache_entries=2)
    for index in range(2):
        cache._etag_cache[f"/old-{index}"] = f"etag-{index}"
        cache._data_cache[f"/old-{index}"] = {"id": index}
    captured: dict[str, object] = {}
    original = cache._enforce_cache_limit

    def spy(reserve: int = 0) -> None:
        captured["reserve"] = reserve
        captured["new_key_present_at_call"] = "/new" in cache._etag_cache
        original(reserve)

    with patch.object(cache, "_enforce_cache_limit", side_effect=spy):
        cache._update_etag_cache("/new", httpx.Response(200, headers={"ETag": '"new"'}), {"id": 3})
    assert captured == {"reserve": 1, "new_key_present_at_call": False}
    assert list(cache._etag_cache) == ["/old-1", "/new"]


def test_enforce_cache_limit_invariant_violation_clears_both_caches() -> None:
    cache = _make_cache(max_cache_entries=2)
    cache._etag_cache["/first"] = "etag-1"
    cache._data_cache["/first"] = {"id": 1}
    cache._data_cache["/orphan"] = {"id": 99}
    with patch.object(cache, "logger") as logger:
        cache._enforce_cache_limit()
    assert cache._etag_cache == {}
    assert cache._data_cache == {}
    logger.error.assert_called_once()
    assert logger.error.call_args.kwargs["data_only_keys"] == ["/orphan"]


def test_enforce_cache_limit_detects_same_length_key_divergence() -> None:
    cache = _make_cache(max_cache_entries=4)
    cache._etag_cache["/a"] = "etag-a"
    cache._etag_cache["/b"] = "etag-b"
    cache._data_cache["/a"] = {"id": 1}
    cache._data_cache["/c"] = {"id": 3}

    with patch.object(cache, "logger") as logger:
        cache._enforce_cache_limit()

    assert cache._etag_cache == {}
    assert cache._data_cache == {}
    logger.error.assert_called_once_with(
        "cache_invariant_violation",
        etag_cache_size=2,
        data_cache_size=2,
        etag_only_keys=["/b"],
        data_only_keys=["/c"],
        etag_only_keys_truncated=False,
        data_only_keys_truncated=False,
        action="cleared_both_caches",
    )


def test_enforce_cache_limit_strips_query_strings_and_truncates_flags() -> None:
    cache = _make_cache(max_cache_entries=10)
    for index in range(6):
        cache._etag_cache[f"/etag-only-{index}?token=secret"] = f"etag-{index}"
    cache._data_cache["/data-only?token=secret"] = {"id": 1}
    with patch.object(cache, "logger") as logger:
        cache._enforce_cache_limit()
    kwargs = logger.error.call_args.kwargs
    assert kwargs["etag_only_keys"] == [f"/etag-only-{i}" for i in range(5)]
    assert kwargs["etag_only_keys_truncated"] is True
    assert kwargs["data_only_keys"] == ["/data-only"]


@pytest.mark.parametrize(
    ("etag", "accepted"),
    [
        ('"opaque"', True),
        ('W/"weak"', True),
        ('""', True),
        ('"a\\b"', True),
        ("no-quotes", False),
        ('w/"lowercase"', False),
        ('"a\tb"', False),
        ('"\x7f"', False),
    ],
)
def test_etag_pattern_acceptance(etag: str, accepted: bool) -> None:
    assert (_ETAG_PATTERN.match(etag) is not None) is accepted


def test_update_etag_cache_invalid_etag_evicts_stale_even_if_logger_raises() -> None:
    cache = _make_cache()
    cache._etag_cache["/repos/test"] = '"stale"'
    cache._data_cache["/repos/test"] = {"id": 1}
    with patch.object(cache, "logger") as logger:
        logger.warning.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError, match="boom"):
            cache._update_etag_cache(
                "/repos/test", httpx.Response(200, headers={"ETag": "bad"}), {"id": 2}
            )
    assert "/repos/test" not in cache._etag_cache
    assert "/repos/test" not in cache._data_cache


def test_update_etag_cache_etag_removed_evicts_even_if_logger_raises() -> None:
    cache = _make_cache()
    cache._etag_cache["/repos/test"] = '"stale"'
    cache._data_cache["/repos/test"] = {"id": 1}
    with patch.object(cache, "logger") as logger:
        logger.info.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError, match="boom"):
            cache._update_etag_cache("/repos/test", httpx.Response(200), {"id": 2})
    assert "/repos/test" not in cache._etag_cache
    assert "/repos/test" not in cache._data_cache


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        (None, "/users/octocat"),
        ({}, "/users/octocat"),
        ({"sort": "updated", "per_page": "30"}, "/users/octocat?per_page=30&sort=updated"),
        ({"q": "hello world"}, "/users/octocat?q=hello%20world"),
        ({"q": "a&b=c"}, "/users/octocat?q=a%26b%3Dc"),
        (
            {"クエリ": "こんにちは"},
            "/users/octocat?%E3%82%AF%E3%82%A8%E3%83%AA=%E3%81%93%E3%82%93%E3%81%AB%E3%81%A1%E3%81%AF",
        ),
    ],
)
def test_cache_key(params: dict[str, str] | None, expected: str) -> None:
    assert GitHubETagCache._cache_key("/users/octocat", params) == expected


def test_cache_key_params_are_sorted_and_ints_match_strings() -> None:
    assert GitHubETagCache._cache_key("/repos", {"b": "2", "a": "1"}) == "/repos?a=1&b=2"
    assert GitHubETagCache._cache_key("/repos", {"per_page": 30}) == GitHubETagCache._cache_key(
        "/repos", {"per_page": "30"}
    )


def test_cache_key_errors_are_pii_safe() -> None:
    class NonEncodable:
        def __str__(self) -> str:
            raise UnicodeEncodeError("ascii", "秘密", 0, 1, "not encodable")

    with (
        capture_logs() as logs,
        pytest.raises(GitHubAPIError, match="UnicodeEncodeError") as exc_info,
    ):
        GitHubETagCache._cache_key("/repos", {"secret_param": NonEncodable()})
    assert exc_info.value.__cause__ is None
    assert logs[0]["event"] == "cache_key_build_failed"
    assert logs[0]["error_type"] == "UnicodeEncodeError"
    assert "secret_param" not in str(logs[0])
    assert "秘密" not in str(logs[0])
