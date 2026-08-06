"""GitHub API非同期クライアントのライフサイクル管理テスト

async context manager（__aenter__ / __aexit__）と aclose() によるリソース解放、
close 時例外の抑制・再送出・本体例外との優先順位、aclose() の冪等性、
クローズ時のログ出力、context manager 未使用時の request の振る舞いをカバーする。
"""

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from structlog.testing import capture_logs

from utils.github_client import AsyncGitHubClient

pytestmark = pytest.mark.unit


async def test_context_manager_initialization() -> None:
    client = AsyncGitHubClient()
    managed_client: httpx.AsyncClient | None = None
    assert client._client is None

    async with client as ctx_client:
        assert ctx_client is client
        assert ctx_client._client is not None
        assert isinstance(ctx_client._client, httpx.AsyncClient)
        managed_client = ctx_client._client

    assert managed_client is not None
    assert managed_client.is_closed


async def test_aenter_caps_connection_pool() -> None:
    """__aenter__ が接続プール上限を明示的に httpx へ渡すことを固定する。

    未指定だと httpx 既定の max_connections=100 が効くが、これは GitHub が強制する
    同時100リクエスト上限と偶然一致し、プール飽和と API 拒否が同時に起きてマージンが
    ゼロになる。この暗黙の一致へ戻る回帰を防ぐ。
    """
    target = "utils.github_client.httpx.AsyncClient"
    with patch(target, return_value=AsyncMock()) as async_client_cls:
        async with AsyncGitHubClient():
            pass
        assert async_client_cls.call_args.kwargs["limits"].max_connections == 10

        async with AsyncGitHubClient(max_connections=3):
            pass
        assert async_client_cls.call_args.kwargs["limits"].max_connections == 3


@pytest.mark.parametrize("invalid", [0, -1, 101])
async def test_init_rejects_out_of_range_max_connections(invalid: int) -> None:
    """max_connections を 1..100 に制限する（settings.api.max_connections と同一契約）。

    下限: 0 以下ではプールが接続を確保できず全リクエストが PoolTimeout になる。
    上限: 100 は GitHub の同時リクエスト制限そのもので、超えても API 側で拒否される。
    どちらも即座の ValueError で呼び出し側の設定ミスを表面化させる。
    """
    with pytest.raises(ValueError, match="max_connections must be between 1 and 100"):
        AsyncGitHubClient(max_connections=invalid)


@pytest.mark.parametrize("valid", [1, 100])
async def test_init_accepts_max_connections_boundaries(valid: int) -> None:
    """境界値 1 / 100 は許容する（off-by-one で有効値を弾かないことの固定）。"""
    assert AsyncGitHubClient(max_connections=valid).max_connections == valid


@pytest.mark.parametrize(
    ("close_exception", "expected_type", "expected_module"),
    [
        (OSError("connection reset"), "OSError", "builtins"),
        (httpx.CloseError("close failed"), "CloseError", "httpx"),
    ],
)
async def test_aexit_aclose_known_exception_is_suppressed_with_warning(
    close_exception: Exception, expected_type: str, expected_module: str
) -> None:
    """既知のクローズ時例外をwarningへ記録して抑制する。"""
    client = AsyncGitHubClient()
    client._client = AsyncMock()
    client._client.aclose = AsyncMock(side_effect=close_exception)

    with capture_logs() as log_output:
        await client.__aexit__(None, None, None)

    known_event = "async_github_client_aclose_failed"
    warning_logs = [log for log in log_output if log.get("event") == known_event]
    assert len(warning_logs) == 1
    assert warning_logs[0]["error_type"] == expected_type
    # third-party 例外起点モジュール識別のため error_module を併用
    assert warning_logs[0]["error_module"] == expected_module
    assert client._client is None
    # 既知例外では error ログは出ない
    unexpected_event = "async_github_client_aclose_unexpected_error"
    error_logs = [log for log in log_output if log.get("event") == unexpected_event]
    assert len(error_logs) == 0
    # else節スキップ検証。aclose() 例外時は __aexit__ の
    # else 節 (utils/github_client.py L291-292) が実行されず "async_github_client_closed"
    # info ログは出力されない設計意図 (test_aexit_normal_close_logs_infoの対照)
    closed_logs = [log for log in log_output if log.get("event") == "async_github_client_closed"]
    assert len(closed_logs) == 0


async def test_aexit_aclose_unexpected_exception_reraises_when_no_body_exception() -> None:
    """__aexit__ で body 例外なし + 予期しない close 例外 → close_exc を re-raise する。
    body 例外がない状態（exc_type is None）では、aclose() の予期しない例外は
    実装バグとして呼び出し元に伝播させる。
    error ログ（has_body_exception=False, exc_info=True）が記録されてから re-raise。
    """
    client = AsyncGitHubClient()
    client._client = AsyncMock()
    client._client.aclose = AsyncMock(side_effect=RuntimeError("close-failed"))

    with pytest.raises(RuntimeError, match="close-failed"), capture_logs() as log_output:
        await client.__aexit__(None, None, None)

    unexpected_event = "async_github_client_aclose_unexpected_error"
    error_logs = [log for log in log_output if log.get("event") == unexpected_event]
    assert len(error_logs) == 1
    assert error_logs[0]["error_type"] == "RuntimeError"
    # third-party 例外起点モジュール識別のため error_module を併用
    assert error_logs[0]["error_module"] == "builtins"
    assert error_logs[0]["has_body_exception"] is False
    # exc_info=True によりスタックトレースが記録される
    assert error_logs[0].get("exc_info") is True
    known_event = "async_github_client_aclose_failed"
    warning_logs = [log for log in log_output if log.get("event") == known_event]
    assert len(warning_logs) == 0
    # else節スキップ検証。aclose() 例外時は __aexit__ の
    # else 節 (utils/github_client.py L291-292) が実行されず "async_github_client_closed"
    # info ログは出力されない設計意図 (test_aexit_normal_close_logs_infoの対照)
    closed_logs = [log for log in log_output if log.get("event") == "async_github_client_closed"]
    assert len(closed_logs) == 0


async def test_aclose_standalone_success_sets_client_none() -> None:
    """__aexit__を経由しないfinally経路のクローズ契約を固定する。"""
    client = AsyncGitHubClient()
    client._client = AsyncMock()

    with capture_logs() as log_output:
        await client.aclose()

    # 全経路規約: 正常クローズ後は _client=None（ダブル aclose 防止）
    assert client._client is None
    closed_logs = [log for log in log_output if log.get("event") == "async_github_client_closed"]
    assert len(closed_logs) == 1


async def test_aclose_standalone_known_close_error_warns_and_sets_none() -> None:
    client = AsyncGitHubClient()
    client._client = AsyncMock()
    client._client.aclose = AsyncMock(side_effect=httpx.CloseError("known-close"))

    with capture_logs() as log_output:
        await client.aclose()  # CloseError は warning 化され伝播しない

    assert client._client is None
    warning_logs = [
        log for log in log_output if log.get("event") == "async_github_client_aclose_failed"
    ]
    assert len(warning_logs) == 1
    assert warning_logs[0]["error_type"] == "CloseError"


async def test_aclose_standalone_fatal_reraises_and_sets_none() -> None:
    client = AsyncGitHubClient()
    client._client = AsyncMock()
    client._client.aclose = AsyncMock(side_effect=asyncio.CancelledError())

    with pytest.raises(asyncio.CancelledError):
        await client.aclose()

    # 致命例外でも CloseError/else 節と対称に _client=None を設定する
    assert client._client is None


async def test_aclose_standalone_unexpected_is_suppressed() -> None:
    """standalone aclose() で予期しない例外 → 抑制（re-raise しない）・error ログ・_client=None。

    __aexit__ は body 例外なし時に re-raise するが、standalone aclose は伝播中の
    例外を上書きしないよう常に抑制する（AsyncAPIClient.aclose と対称)
    """
    client = AsyncGitHubClient()
    client._client = AsyncMock()
    client._client.aclose = AsyncMock(side_effect=RuntimeError("unexpected-close"))

    with capture_logs() as log_output:
        await client.aclose()  # 抑制されるため例外は伝播しない

    assert client._client is None
    error_logs = [
        log
        for log in log_output
        if log.get("event") == "async_github_client_aclose_unexpected_error"
    ]
    assert len(error_logs) == 1
    assert error_logs[0]["error_type"] == "RuntimeError"
    assert error_logs[0]["action"] == "suppressed_standalone_aclose"


async def test_aclose_standalone_idempotent_when_client_none() -> None:
    client = AsyncGitHubClient()
    client._client = None

    with capture_logs() as log_output:
        await client.aclose()

    assert client._client is None
    assert log_output == []


async def test_aexit_body_exception_not_overridden_by_close_exception() -> None:
    """body例外とaclose例外の併発時に原因情報を失わないため、close例外をre-raiseせず
    body例外を優先伝播させることを検証する（CWE-755例外マスク回避）。"""
    client = AsyncGitHubClient()
    # __aenter__ が生成するクライアント自体を差し替える。ブロック内で _client を代入すると
    # __aenter__ が生成した実クライアントが閉じられないまま破棄される。
    mock_async_client = AsyncMock()
    mock_async_client.aclose = AsyncMock(side_effect=RuntimeError("close-failed"))

    with (
        patch("utils.github_client.httpx.AsyncClient", return_value=mock_async_client),
        pytest.raises(ValueError, match="body-error"),
        capture_logs() as log_output,
    ):
        async with client:
            raise ValueError("body-error")

    # close 例外は re-raise しない。body 例外は ValueError として外側に伝播
    # RuntimeError は予期しない例外 → error ログ (has_body_exception=True)
    unexpected_event = "async_github_client_aclose_unexpected_error"
    error_logs = [log for log in log_output if log.get("event") == unexpected_event]
    assert len(error_logs) == 1
    assert error_logs[0]["error_type"] == "RuntimeError"
    assert error_logs[0]["error_module"] == "builtins"
    assert error_logs[0]["has_body_exception"] is True
    # exc_info=True によりスタックトレースが記録される
    assert error_logs[0].get("exc_info") is True
    known_event = "async_github_client_aclose_failed"
    warning_logs = [log for log in log_output if log.get("event") == known_event]
    assert len(warning_logs) == 0
    # else節スキップ検証。body+close 二重例外時も
    # else 節 (utils/github_client.py L291-292) は実行されず "async_github_client_closed"
    # info ログは出力されない (test_aexit_normal_close_logs_infoの対照)。
    closed_logs = [log for log in log_output if log.get("event") == "async_github_client_closed"]
    assert len(closed_logs) == 0


@pytest.mark.parametrize(
    "fatal_exc",
    [MemoryError("OOM"), RecursionError("maximum recursion depth exceeded")],
)
async def test_aexit_fatal_close_exception_propagates_even_with_body_exception(
    fatal_exc: MemoryError | RecursionError,
) -> None:
    """fatal例外（MemoryError/RecursionError）はexcept Exceptionの抑制に捕捉されうるため、
    専用except句で先取りしbody例外併発時もfail-fastで伝播させる
    （api_client._close_async_client/sentry_initと同一方針の回帰防止）。"""
    client = AsyncGitHubClient()
    # __aenter__ が生成するクライアント自体を差し替える（実クライアントの取り残しを防ぐ）。
    mock_async_client = AsyncMock()
    mock_async_client.aclose = AsyncMock(side_effect=fatal_exc)

    with (
        patch("utils.github_client.httpx.AsyncClient", return_value=mock_async_client),
        pytest.raises(type(fatal_exc)),
        capture_logs() as log_output,
    ):
        async with client:
            raise ValueError("body-error")

    # 専用 except 句が except Exception より先に re-raise するため、
    # unexpected_error（error ログ）も known-exception warning も記録されない。
    unexpected_event = "async_github_client_aclose_unexpected_error"
    error_logs = [log for log in log_output if log.get("event") == unexpected_event]
    assert len(error_logs) == 0
    known_event = "async_github_client_aclose_failed"
    warning_logs = [log for log in log_output if log.get("event") == known_event]
    assert len(warning_logs) == 0
    # aclose 失敗のため else 節（closed ログ）は未到達。
    closed_logs = [log for log in log_output if log.get("event") == "async_github_client_closed"]
    assert len(closed_logs) == 0


async def test_request_without_context_manager() -> None:
    client = AsyncGitHubClient()
    # async withを使わずに直接_requestを呼ぶ
    with pytest.raises(RuntimeError) as exc_info:
        await client._request("GET", "/users/octocat")

    assert "Client not initialized" in str(exc_info.value)
    assert "async with" in str(exc_info.value)


async def test_aexit_normal_close_logs_info() -> None:
    """__aexit__ 正常クローズ時に "async_github_client_closed" の info ログが1回出力される

    aclose() が例外なく完了した場合（else 節）に structlog の info ログが記録されることを
    capture_logs で検証する。
    """
    with capture_logs() as log_output:
        async with AsyncGitHubClient():
            pass

    closed_logs = [log for log in log_output if log.get("event") == "async_github_client_closed"]
    assert len(closed_logs) == 1
    assert closed_logs[0]["log_level"] == "info"
