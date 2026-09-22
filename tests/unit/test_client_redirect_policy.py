"""HTTP クライアント 3 種のリダイレクト非追従契約テスト

SSRF 境界は ``config/settings.py`` の base_url allowlist 単層である（ADR-0007）。
リダイレクト追従が有効になると、allowlist を通った base_url から 3xx 経由で
allowlist 外ホストへ到達できるため、3 クライアントすべてが ``follow_redirects=False``
で構築されることを実効値で固定する。httpx の既定値と同値なので明示引数を外しても通る
（実害なし）。止めるのは ``follow_redirects=True`` へ変える回帰（``requests`` 流儀）である。
"""

import httpx
import pytest
import respx

from tests.constants import BASE_URL
from utils.exceptions import APIHTTPError, APIRetryError
from utils.github_client import AsyncGitHubClient
from utils.jsonplaceholder_base_async import AsyncAPIClient
from utils.jsonplaceholder_base_sync import SyncAPIClient

pytestmark = pytest.mark.unit


def test_sync_api_client_does_not_follow_redirects() -> None:
    with SyncAPIClient(base_url=BASE_URL) as client:
        assert isinstance(client._client, httpx.Client)
        assert client._client.follow_redirects is False


async def test_async_api_client_does_not_follow_redirects() -> None:
    async with AsyncAPIClient(base_url=BASE_URL) as client:
        assert isinstance(client._client, httpx.AsyncClient)
        assert client._client.follow_redirects is False


async def test_github_client_does_not_follow_redirects() -> None:
    async with AsyncGitHubClient() as client:
        assert isinstance(client._client, httpx.AsyncClient)
        assert client._client.follow_redirects is False


@respx.mock
@pytest.mark.parametrize("status_code", [301, 302, 307, 308])
def test_sync_api_client_raises_on_redirect_instead_of_following(status_code: int) -> None:
    """3xx は追従されず raise_for_status() で失敗する（GitHub の 301 と同じ経路）。

    httpx 0.20 以降 raise_for_status() は 2xx 以外を HTTPStatusError にする。3xx は
    is_client_error ではないため 5xx と同じ再送対象に分類され、retry_count=0 では
    APIHTTPError を原因に持つ APIRetryError で終わる。ここで固定するのは
    「Location 先へ 2 回目のリクエストが出ない」ことである。
    """
    origin = respx.get(f"{BASE_URL}/users/1").mock(
        return_value=httpx.Response(status_code, headers={"Location": "https://evil.example/"})
    )

    with (
        SyncAPIClient(base_url=BASE_URL, retry_count=0) as client,
        pytest.raises(APIRetryError) as exc,
    ):
        client.get("/users/1")

    assert isinstance(exc.value.__cause__, APIHTTPError)
    assert origin.call_count == 1
    # 追従していれば allowlist 外ホストへの 2 回目の呼び出しが respx に記録される
    assert [call.request.url.host for call in respx.calls] == [httpx.URL(BASE_URL).host]


@respx.mock
@pytest.mark.parametrize("status_code", [301, 302, 307, 308])
async def test_async_api_client_raises_on_redirect_instead_of_following(status_code: int) -> None:
    """Sync 側と同じ契約を Async 基盤でも固定する（Sync / Async parity）。"""
    origin = respx.get(f"{BASE_URL}/users/1").mock(
        return_value=httpx.Response(status_code, headers={"Location": "https://evil.example/"})
    )

    async with AsyncAPIClient(base_url=BASE_URL, retry_count=0) as client:
        with pytest.raises(APIRetryError) as exc:
            await client.get("/users/1")

    assert isinstance(exc.value.__cause__, APIHTTPError)
    assert origin.call_count == 1
    assert [call.request.url.host for call in respx.calls] == [httpx.URL(BASE_URL).host]
