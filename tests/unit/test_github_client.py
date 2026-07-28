"""GitHub API非同期クライアントのUnit Tests"""

from unittest.mock import patch

import httpx
import pytest
import respx
from structlog.testing import capture_logs

from utils.exceptions import APIClientError
from utils.github_client import AsyncGitHubClient, validate_github_repo, validate_github_username
from utils.github_error_handler import (
    GitHubAPIError,
    NotFoundError,
    SanitizedJSONDecodeError,
    redact_body_preview,
)
from utils.github_rate_limit import (
    RATE_LIMIT_WARNING_THRESHOLD,
)

pytestmark = pytest.mark.unit
# @pytest.mark.asyncio: asyncio_mode = "auto" (pyproject.toml) のため、@pytest.mark.asyncio は不要
# pytest-asyncio が async テストを自動検出する

GITHUB_API_BASE_URL = "https://api.github.com"


def test_github_api_error_uses_shared_api_client_error() -> None:
    assert issubclass(GitHubAPIError, APIClientError)


def test_gw1_public_contract_symbols_are_promoted() -> None:
    cause = SanitizedJSONDecodeError("json.JSONDecodeError", "Expecting value", 0, 1, 1)

    assert RATE_LIMIT_WARNING_THRESHOLD == 10
    assert redact_body_preview("") == "[redacted:e3b0c44298fc1c14]"
    assert str(cause) == "json.JSONDecodeError: Expecting value pos=0, lineno=1, colno=1"


@respx.mock
async def test_get_user_success():
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=200,
        json={
            "login": "octocat",
            "name": "The Octocat",
            "public_repos": 8,
        },
        headers={"X-RateLimit-Remaining": "59"},
    )

    async with AsyncGitHubClient() as client:
        user = await client.get_user("octocat")

    assert user["login"] == "octocat"
    assert user["name"] == "The Octocat"
    assert user["public_repos"] == 8
    assert route.call_count == 1


@respx.mock
async def test_get_repos_success():
    route = respx.get(
        f"{GITHUB_API_BASE_URL}/users/octocat/repos", params={"sort": "updated", "per_page": 2}
    ).respond(
        status_code=200,
        json=[
            {"name": "Hello-World", "stargazers_count": 100},
            {"name": "Spoon-Knife", "stargazers_count": 50},
        ],
        headers={"X-RateLimit-Remaining": "58"},
    )

    async with AsyncGitHubClient() as client:
        repos = await client.get_repos("octocat", per_page=2)

    assert len(repos) == 2
    assert repos[0]["name"] == "Hello-World"
    assert repos[1]["stargazers_count"] == 50
    assert route.call_count == 1


@pytest.mark.parametrize(
    "sort",
    [
        pytest.param("stars", id="unsupported_sort"),
        pytest.param("", id="empty_sort"),
    ],
)
async def test_get_repos_rejects_invalid_sort(sort: str) -> None:
    """外部APIへ送る前にsortの許容値を検証し、無効入力を到達させない。"""
    async with AsyncGitHubClient() as client:
        with pytest.raises(ValueError, match="sort must be one of"):
            await client.get_repos("octocat", sort=sort)


@pytest.mark.parametrize(
    "per_page",
    [
        pytest.param(0, id="below_min"),
        pytest.param(101, id="above_max"),
    ],
)
async def test_get_repos_rejects_invalid_per_page(per_page: int) -> None:
    """外部APIへ送る前にper_pageの範囲を検証し、無効入力を到達させない。"""
    async with AsyncGitHubClient() as client:
        with pytest.raises(ValueError, match="per_page must be between 1 and 100"):
            await client.get_repos("octocat", per_page=per_page)


@respx.mock
async def test_get_repo_success():
    route = respx.get(f"{GITHUB_API_BASE_URL}/repos/octocat/Hello-World").respond(
        status_code=200,
        json={
            "name": "Hello-World",
            "full_name": "octocat/Hello-World",
            "stargazers_count": 100,
            "forks_count": 50,
        },
        headers={"X-RateLimit-Remaining": "57"},
    )

    async with AsyncGitHubClient() as client:
        repo = await client.get_repo("octocat", "Hello-World")

    assert repo["name"] == "Hello-World"
    assert repo["stargazers_count"] == 100
    assert route.call_count == 1


@respx.mock
async def test_get_user_not_found():
    route = respx.get(f"{GITHUB_API_BASE_URL}/users/nonexistent-user-12345").respond(
        status_code=404,
        headers={"X-RateLimit-Remaining": "60"},
    )

    async with AsyncGitHubClient() as client:
        with pytest.raises(NotFoundError) as exc_info:
            await client.get_user("nonexistent-user-12345")

    assert "Resource not found" in str(exc_info.value)
    assert "/users/nonexistent-user-12345" in str(exc_info.value)
    assert route.call_count == 1


@respx.mock
async def test_etag_cache_hit():
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
        assert user1["login"] == "octocat"

        user2 = await client.get_user("octocat")
        assert user2 == {"login": "octocat", "id": 1}

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
        json={"login": "octocat"},
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
        json={"login": "octocat"},
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

    assert result == {"login": "octocat"}
    assert route.call_count == 1
    error_logs = [log for log in logs if log.get("event") == "etag_cache_update_failed"]
    assert len(error_logs) == 1
    assert error_logs[0]["log_level"] == "error"
    assert error_logs[0]["error_type"] == "RuntimeError"
    assert error_logs[0]["method"] == "GET"
    assert error_logs[0]["endpoint"] == "/users/octocat"


@pytest.mark.parametrize(
    "username",
    [
        pytest.param("octocat", id="simple_name"),
        pytest.param("user-name", id="hyphen"),
        pytest.param("a", id="single_char"),
        pytest.param("a" * 39, id="max_length"),  # 上限（39文字）
        pytest.param("1user", id="leading_digit"),
        pytest.param("user123", id="digits_in_name"),
        pytest.param("MyUser", id="uppercase"),
    ],
)
def test_username_validation_valid(username: str) -> None:
    validate_github_username(username)


async def test_username_validation_invalid():
    """ユーザー名をURL pathへ組み込むため、Path Traversal入力を拒否する。"""
    async with AsyncGitHubClient() as client:
        # Path Traversal攻撃パターン
        with pytest.raises(ValueError, match="Invalid GitHub username"):
            await client.get_user("../../../etc/passwd")
        with pytest.raises(ValueError, match="Invalid GitHub username"):
            await client.get_user("")
        with pytest.raises(ValueError, match="Invalid GitHub username"):
            await client.get_user("a" * 40)


@respx.mock
async def test_get_user_type_guard_rejects_non_dict():
    respx.get(f"{GITHUB_API_BASE_URL}/users/octocat").respond(
        status_code=200,
        json=[{"id": 1}],
        headers={"X-RateLimit-Remaining": "50"},
    )
    async with AsyncGitHubClient() as client:
        with pytest.raises(GitHubAPIError, match="Expected dict response, got list"):
            await client.get_user("octocat")


@respx.mock
async def test_get_repos_type_guard_rejects_non_list():
    respx.get(f"{GITHUB_API_BASE_URL}/users/octocat/repos").respond(
        status_code=200,
        json={"id": 1},
        headers={"X-RateLimit-Remaining": "50"},
    )
    async with AsyncGitHubClient() as client:
        with pytest.raises(GitHubAPIError, match="Expected list response, got dict"):
            await client.get_repos("octocat")


@respx.mock
async def test_get_repo_type_guard_rejects_non_dict():
    respx.get(f"{GITHUB_API_BASE_URL}/repos/octocat/Hello-World").respond(
        status_code=200,
        json=[{"id": 1}],
        headers={"X-RateLimit-Remaining": "50"},
    )
    async with AsyncGitHubClient() as client:
        with pytest.raises(GitHubAPIError, match="Expected dict response, got list"):
            await client.get_repo("octocat", "Hello-World")


# KeyboardInterruptはpytest自体がSIGINTハンドラとして処理するためunitテストでの検証は省略
# SystemExit / MemoryError / CancelledError の3種で例外伝播パスをカバー


@pytest.mark.parametrize(
    "repo",
    [
        pytest.param("my-repo", id="hyphen"),
        pytest.param("a", id="single_char"),
        pytest.param("a" * 100, id="max_length"),  # 上限（100文字）
        pytest.param("my_repo", id="underscore"),
        pytest.param("my.repo", id="dot"),
        pytest.param(".github", id="github_special_repository"),
        pytest.param("123", id="digits_only"),
    ],
)
def test_repo_validation_valid(repo: str) -> None:
    validate_github_repo(repo)


@pytest.mark.parametrize(
    "repo",
    [
        pytest.param("../etc/passwd", id="path_traversal"),
        pytest.param("a" * 101, id="too_long"),
        pytest.param("", id="empty_string"),
        pytest.param("repo name!", id="special_chars"),
        pytest.param("repo\x00name", id="null_byte"),
        pytest.param(".", id="dot_single"),
        pytest.param("..", id="dot_double"),
    ],
)
def test_repo_validation_invalid(repo: str) -> None:
    """リポジトリ名をURL pathへ組み込むため、Path Traversalを入力境界で拒否する。"""
    with pytest.raises(ValueError, match="Invalid GitHub repository name"):
        validate_github_repo(repo)


def test_sanitized_jsondecodeerror_str_contains_no_response_body() -> None:
    """SanitizedJSONDecodeError.__str__() は型・位置情報のみで body を含まない

    現状の PII 漏洩防止は __cause__ チェーン切断（__context__=None）に依存するが、
    __str__ 出力自体が response body を構造的に保持しないことを直接検証し、
    将来のフォーマット変更による回帰を検出する。
    """
    cause = SanitizedJSONDecodeError(
        "json.JSONDecodeError",
        msg="Expecting value",
        pos=42,
        lineno=3,
        colno=7,
    )

    rendered = str(cause)
    # msg は json.JSONDecodeError.msg（静的パーサ診断文字列）で PII 非含有
    assert rendered == "json.JSONDecodeError: Expecting value pos=42, lineno=3, colno=7"
    assert cause.msg == "Expecting value"  # 破損種別識別用 msg を保持
    assert cause.pos == 42
    assert cause.lineno == 3
    assert cause.colno == 7  # 診断用 colno を保持
    # 仮にレスポンス body 由来の機密文字列があっても __str__ には現れない
    assert "password" not in rendered
    assert "token" not in rendered


def test_sanitized_jsondecodeerror_reduce_roundtrip_preserves_fields() -> None:
    """SanitizedJSONDecodeError は __reduce__ で全フィールドを復元可能

    非標準 __init__ シグネチャ（5 引数）のため __reduce__ を実装。pytest-xdist の
    worker→controller 例外転送や Sentry SDK シリアライズが依存する pickle プロトコル
    の契約（``cls(*args)`` で再構築可能）を直接検証する。pickle.loads は CWE-502 回避の
    ため使わず、__reduce__ の戻り値から手動で再構築して TypeError にならないことを保証する。
    """
    original = SanitizedJSONDecodeError(
        "json.JSONDecodeError",
        msg="Expecting value",
        pos=42,
        lineno=3,
        colno=7,
    )

    cls, args = original.__reduce__()
    restored = cls(*args)

    assert isinstance(restored, SanitizedJSONDecodeError)
    assert restored.error_type == "json.JSONDecodeError"
    assert restored.msg == "Expecting value"
    assert restored.pos == 42
    assert restored.lineno == 3
    assert restored.colno == 7
    assert str(restored) == str(original)


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
            json=[{"name": "repo-a", "pushed_at": "2025-01-01"}],
            headers={"ETag": '"updated-etag"', "X-RateLimit-Remaining": "50"},
        ),
        httpx.Response(304, headers={"X-RateLimit-Remaining": "50"}),
    ]
    created_route.respond(
        200,
        json=[{"name": "repo-b", "created_at": "2024-01-01"}],
        headers={"ETag": '"created-etag"', "X-RateLimit-Remaining": "50"},
    )

    async with AsyncGitHubClient() as client:
        repos1 = await client.get_repos("octocat", sort="updated", per_page=30)
        assert repos1[0]["name"] == "repo-a"

        repos2 = await client.get_repos("octocat", sort="created", per_page=10)
        assert repos2[0]["name"] == "repo-b"

        repos3 = await client.get_repos("octocat", sort="updated", per_page=30)
        assert repos3[0]["name"] == "repo-a"

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
            json=[{"name": "repo-updated"}],
            headers={"ETag": '"updated"', "X-RateLimit-Remaining": "50"},
        ),
        httpx.Response(304, headers={"X-RateLimit-Remaining": "50"}),
    ]
    created_route.side_effect = [
        httpx.Response(
            200,
            json=[{"name": "repo-created"}],
            headers={"ETag": '"created"', "X-RateLimit-Remaining": "50"},
        ),
    ]

    async with AsyncGitHubClient() as client:
        r1 = await client.get_repos("octocat", sort="updated", per_page=30)
        assert r1[0]["name"] == "repo-updated"

        r2 = await client.get_repos("octocat", sort="created", per_page=30)
        assert r2[0]["name"] == "repo-created"

        r3 = await client.get_repos("octocat", sort="updated", per_page=30)
        assert r3[0]["name"] == "repo-updated"

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
