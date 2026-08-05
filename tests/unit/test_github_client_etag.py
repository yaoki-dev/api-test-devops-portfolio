"""GitHub API非同期クライアントのETagキャッシュUnit Tests"""

from unittest.mock import patch

import httpx
import pytest
import respx
from structlog.testing import capture_logs

from utils.github_client import AsyncGitHubClient

pytestmark = pytest.mark.unit

GITHUB_API_BASE_URL = "https://api.github.com"


@respx.mock
async def test_etag_cache_hit() -> None:
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat")
    route.side_effect = [
        httpx.Response(
            200,
            json={"login": "octocat", "id": 1},
            headers={"ETag": '"abc123"', "X-RateLimit-Remaining": "50"},
        ),
        httpx.Response(304, headers={"X-RateLimit-Remaining": "50"}),
    ]

    async with AsyncGitHubClient() as client:
        user1 = await client.get_user("octocat")
        assert user1.login == "octocat"

        user2 = await client.get_user("octocat")
        assert user2.login == "octocat"
        assert user2.id == 1

    assert route.call_count == 2
    # 1回目はIf-None-Match未送信、2回目は保存済みETagを送信（ETagキャッシュ保存の証跡）
    assert "if-none-match" not in route.calls[0].request.headers
    assert route.calls[1].request.headers["if-none-match"] == '"abc123"'


@pytest.mark.parametrize(
    "fatal_exc",
    [
        pytest.param(MemoryError("OOM"), id="memory_error"),
        pytest.param(RecursionError("maximum recursion depth exceeded"), id="recursion_error"),
    ],
)
@respx.mock
async def test_request_etag_cache_fatal_exception_propagates(
    fatal_exc: MemoryError | RecursionError,
) -> None:
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=200,
        json={"login": "octocat", "id": 1},
        headers={"ETag": '"etag-value"'},
    )

    async with AsyncGitHubClient() as client:
        with (
            patch.object(client._cache, "_update_etag_cache", side_effect=fatal_exc),
            pytest.raises(type(fatal_exc)),
        ):
            await client.get_user("octocat")

    assert route.call_count == 1


@respx.mock
async def test_request_etag_cache_non_fatal_exception_logs_error_and_returns_response() -> None:
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=200,
        json={"login": "octocat", "id": 1},
        headers={"ETag": '"etag-value"'},
    )

    async with AsyncGitHubClient() as client:
        with (
            patch.object(
                client._cache,
                "_update_etag_cache",
                side_effect=RuntimeError("cache failed"),
            ),
            capture_logs() as logs,
        ):
            result = await client.get_user("octocat")

    assert result.login == "octocat"
    assert route.call_count == 1
    error_logs = [log for log in logs if log.get("event") == "etag_cache_update_failed"]
    assert len(error_logs) == 1
    assert error_logs[0]["log_level"] == "error"
    assert error_logs[0]["error_type"] == "RuntimeError"
    assert error_logs[0]["method"] == "GET"
    assert error_logs[0]["endpoint"] == "/users/octocat"


@respx.mock
async def test_etag_cache_key_includes_query_params() -> None:
    """クエリ違いのレスポンス混在を防ぐため、ETagキーにsort/per_pageを含める。"""
    updated_route = respx.get(
        f"{GITHUB_API_BASE_URL}/users/octocat/repos",
        params={"sort": "updated", "per_page": "30"},
    )
    created_route = respx.get(
        f"{GITHUB_API_BASE_URL}/users/octocat/repos",
        params={"sort": "created", "per_page": "10"},
    )
    updated_route.side_effect = [
        httpx.Response(
            200,
            json=[
                {
                    "name": "repo-a",
                    "id": 1,
                    "full_name": "octocat/repo-a",
                    "pushed_at": "2025-01-01",
                }
            ],
            headers={"ETag": '"updated-etag"', "X-RateLimit-Remaining": "50"},
        ),
        httpx.Response(304, headers={"X-RateLimit-Remaining": "50"}),
    ]
    created_route.respond(
        200,
        json=[
            {
                "name": "repo-b",
                "id": 2,
                "full_name": "octocat/repo-b",
                "created_at": "2024-01-01",
            }
        ],
        headers={"ETag": '"created-etag"', "X-RateLimit-Remaining": "50"},
    )

    async with AsyncGitHubClient() as client:
        repos1 = await client.get_repos("octocat", sort="updated", per_page=30)
        assert repos1[0].name == "repo-a"

        repos2 = await client.get_repos("octocat", sort="created", per_page=10)
        assert repos2[0].name == "repo-b"

        repos3 = await client.get_repos("octocat", sort="updated", per_page=30)
        assert repos3[0].name == "repo-a"

    assert updated_route.call_count == 2  # 200 + 304
    assert created_route.call_count == 1  # 200 only
    second_request = updated_route.calls[1].request
    assert "if-none-match" in second_request.headers
    assert second_request.headers["if-none-match"] == '"updated-etag"'


@respx.mock
async def test_304_returns_correct_cached_data_per_params() -> None:
    """304時に別クエリのキャッシュを返す回帰を防ぐ。"""
    octocat_base = f"{GITHUB_API_BASE_URL}/users/octocat/repos"

    updated_route = respx.get(octocat_base, params={"sort": "updated", "per_page": "30"})
    created_route = respx.get(octocat_base, params={"sort": "created", "per_page": "30"})

    updated_route.side_effect = [
        httpx.Response(
            200,
            json=[{"name": "repo-updated", "id": 1, "full_name": "octocat/repo-updated"}],
            headers={"ETag": '"updated"', "X-RateLimit-Remaining": "50"},
        ),
        httpx.Response(304, headers={"X-RateLimit-Remaining": "50"}),
    ]
    created_route.side_effect = [
        httpx.Response(
            200,
            json=[{"name": "repo-created", "id": 2, "full_name": "octocat/repo-created"}],
            headers={"ETag": '"created"', "X-RateLimit-Remaining": "50"},
        ),
    ]

    async with AsyncGitHubClient() as client:
        r1 = await client.get_repos("octocat", sort="updated", per_page=30)
        assert r1[0].name == "repo-updated"

        r2 = await client.get_repos("octocat", sort="created", per_page=30)
        assert r2[0].name == "repo-created"

        r3 = await client.get_repos("octocat", sort="updated", per_page=30)
        assert r3[0].name == "repo-updated"

    assert updated_route.call_count == 2
    assert created_route.call_count == 1


@pytest.mark.parametrize(
    "invalid_value",
    [
        pytest.param(0, id="zero"),
        pytest.param(-1, id="negative_one"),
        pytest.param(-100, id="negative_hundred"),
    ],
)
def test_async_github_client_max_cache_entries_validation(invalid_value: int) -> None:
    with pytest.raises(ValueError, match="max_cache_entries must be >= 1"):
        AsyncGitHubClient(max_cache_entries=invalid_value)


def test_async_github_client_max_cache_entries_delegates_to_cache() -> None:
    """max_cache_entries は GitHubETagCache への委譲であり、facade 側で値を持たない。

    分割後のミラーテストは cache を直接検証するため、client -> cache の委譲の継ぎ目
    （github_client.py の property）だけがテストの死角になりうる。ここで固定する。
    """
    client = AsyncGitHubClient(max_cache_entries=7)

    assert client.max_cache_entries == 7
    assert client.max_cache_entries == client._cache.max_cache_entries
