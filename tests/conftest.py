"""
pytest共通設定とフィクスチャ定義

学習目標:
- pytest fixture設計パターンの理解
- テストデータ管理の効率化
- モックとスタブの活用方法
- テスト環境分離の実現
"""

import json
import time
from collections.abc import AsyncGenerator, Callable, Generator
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, TypedDict
from unittest.mock import AsyncMock, Mock, PropertyMock

import httpx
import pytest
import pytest_asyncio
from httpx import Response
from structlog.typing import FilteringBoundLogger

from utils.api_client import AsyncAPIClient
from utils.logger import get_logger

# =============================================================================
# 型定義（TypedDict）
# =============================================================================


class TodoResponse(TypedDict):
    """TODOレスポンスの型定義"""

    userId: int
    id: int
    title: str
    completed: bool


class ApiConfig(TypedDict):
    """API設定の型定義"""

    base_url: str
    timeout: int
    retry_count: int
    retry_delay: float


class LogConfig(TypedDict):
    """ログ設定の型定義"""

    level: str
    format: str


class TestSettings(TypedDict):
    """テスト設定の型定義"""

    slow_test_threshold: float
    max_concurrent_requests: int


class TestConfigDict(TypedDict):
    """テスト設定全体の型定義"""

    api: ApiConfig
    log: LogConfig
    test: TestSettings


# =============================================================================
# 定数定義
# =============================================================================

# ディレクトリベース自動適用マーカー（フォルダ名 = マーカー名の1:1マッピング）
# Note: Path.partsで厳密マッチ、"first match wins"で最初のマッチのみ適用
# MappingProxyType: ランタイム不変性を保証（dictへの追加/変更を防止）
AUTO_APPLY_MARKERS: Final[MappingProxyType[str, str]] = MappingProxyType(
    {
        "unit": "単体テスト",
        "integration": "統合テスト",
        "e2e": "E2Eテスト",
        "performance": "パフォーマンステスト",
    }
)

# 手動適用マーカー（@pytest.mark.xxx で明示的に付与）
MANUAL_MARKERS: Final[dict[str, str]] = {
    "slow": "実行時間の長いテスト",
    "external": "外部API依存テスト",
    "smoke": "基本機能テスト”,
    "regression":"回帰テスト"
}

# 自動適用対象のマーカー名タプル（AUTO_APPLY_MARKERSから派生）
AUTO_APPLY_MARKER_NAMES: Final[tuple[str, ...]] = tuple(AUTO_APPLY_MARKERS.keys())

# テスト設定デフォルト値（Magic number/string排除）
DEFAULT_TEST_BASE_URL: Final[str] = "https://jsonplaceholder.typicode.com"
DEFAULT_TIMEOUT: Final[int] = 10
DEFAULT_RETRY_COUNT: Final[int] = 1
DEFAULT_RETRY_DELAY: Final[float] = 0.5
SLOW_TEST_THRESHOLD_SECONDS: Final[float] = 5.0
MAX_CONCURRENT_REQUESTS: Final[int] = 5
TEST_USER_AGENT: Final[str] = "API-Test-Portfolio/0.1.0"


# =============================================================================
# Timer クラス（モジュールレベル定義）
# =============================================================================


class Timer:
    """パフォーマンス計測用タイマークラス

    使用例:
        timer = Timer()
        timer.start()
        # 処理実行
        timer.stop()
        print(f"Elapsed: {timer.elapsed:.3f}s")
        timer.assert_faster_than(1.0, "処理が遅すぎます")

    Warning:
        このクラスはスレッドセーフではありません。
        pytest-xdist等の並列実行環境では、各ワーカーで独立したインスタンスを
        使用してください。共有状態での使用は信頼性のない結果を招きます。
    """

    def __init__(self) -> None:
        self.start_time: float | None = None
        self.end_time: float | None = None

    def start(self) -> None:
        """計測開始"""
        self.start_time = time.perf_counter()

    def stop(self) -> None:
        """計測終了"""
        self.end_time = time.perf_counter()

    @property
    def elapsed(self) -> float:
        """経過時間（秒）を取得

        Returns:
            経過時間（秒）

        Raises:
            ValueError: start/stopが呼ばれていない場合
        """
        # ローカル変数への代入でmypyの型narrowingを確実に機能させる
        start = self.start_time
        end = self.end_time
        if start is None or end is None:
            raise ValueError("Timer not properly started/stopped")
        return end - start

    def assert_faster_than(self, threshold: float, message: str = "") -> None:
        """指定閾値より速いことを検証

        Args:
            threshold: 閾値（秒）
            message: 失敗時の追加メッセージ

        Raises:
            pytest.fail: 閾値を超えた場合
        """
        if self.elapsed > threshold:
            pytest.fail(
                f"Performance test failed: {self.elapsed:.3f}s > {threshold:.3f}s. {message}"
            )


# =============================================================================
# Pytest設定
# =============================================================================


def pytest_configure(config: pytest.Config) -> None:
    """pytest実行時の共通設定

    Args:
        config: pytest設定オブジェクト

    Note:
        structlogはutils.logger.get_logger()で取得するため、
        ここでは標準loggingのルートロガー設定のみ行う（pytest内部用）
    """
    # structlogロガー初期化（テスト用）
    # Note: get_logger()初回呼び出し時に設定が自動適用される
    logger = get_logger("pytest")
    logger.debug("pytest_configure started")  # M3: パス情報を削除

    # テストマーカーの登録（自動適用 + 手動適用を結合）
    all_markers = dict(AUTO_APPLY_MARKERS) | MANUAL_MARKERS
    for marker_name, description in all_markers.items():
        config.addinivalue_line("markers", f"{marker_name}: {description}")


# =============================================================================
# ディレクトリベースマーカー自動適用
# =============================================================================


def _get_sort_key(item: pytest.Item) -> tuple[bool, bool, str]:
    """ソートキー生成（マーカー走査を1回に最適化）

    Args:
        item: pytestテストアイテム

    Returns:
        (slow判定, external判定, テスト名) のタプル
        Trueは後ろにソートされるため、slowテストが最後に実行される
    """
    marker_names = {mark.name for mark in item.iter_markers()}
    return (
        "slow" in marker_names,
        "external" in marker_names,
        item.name,
    )


def _apply_directory_markers(items: list[pytest.Item]) -> None:
    """ディレクトリベースのマーカー自動適用（Path.parts使用）

    Args:
        items: 収集されたテストアイテムのリスト

    Note:
        Path.partsでパス要素をタプル化し、厳密な境界チェックを実現
        例: ('tests', 'unit', 'test_foo.py') → "unit" in parts = True
        例: ('tests', 'unittest', 'test_foo.py') → "unit" in parts = False

        動作: "first match wins" - 最初にマッチしたマーカーのみ適用
        AUTO_APPLY_MARKER_NAMESの定義順でチェック（フォルダ名=マーカー名）
    """
    for item in items:
        path_parts = item.path.parts
        for marker_name in AUTO_APPLY_MARKER_NAMES:
            if marker_name in path_parts:
                item.add_marker(getattr(pytest.mark, marker_name))
                break  # first match wins


def _sort_by_execution_priority(items: list[pytest.Item]) -> None:
    """テスト実行順序の最適化（高速テスト優先）

    Args:
        items: 収集されたテストアイテムのリスト（in-placeソート）
    """
    items.sort(key=_get_sort_key)


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """テストコレクション後処理（SRP準拠）

    Args:
        config: pytest設定オブジェクト
        items: 収集されたテストアイテムのリスト
    """
    _apply_directory_markers(items)
    _sort_by_execution_priority(items)


# =============================================================================
# 基本フィクスチャ
# =============================================================================


# Note: event_loop fixtureは削除済み
# pytest-asyncio 0.23+では asyncio_mode = "auto" で自動管理されるため不要


@pytest.fixture(scope="session")
def test_config() -> TestConfigDict:
    """テスト用設定データ（読み取り専用として扱うこと）

    Returns:
        TestConfigDict: API/ログ/テスト設定を含む辞書

    Warning:
        このフィクスチャはsessionスコープです。
        返却された辞書を変更しないでください。
        変更は後続の全テストに影響し、テスト汚染を引き起こします。
    """
    return {
        "api": {
            "base_url": DEFAULT_TEST_BASE_URL,
            "timeout": DEFAULT_TIMEOUT,
            "retry_count": DEFAULT_RETRY_COUNT,
            "retry_delay": DEFAULT_RETRY_DELAY,
        },
        "log": {"level": "DEBUG", "format": "console"},
        "test": {
            "slow_test_threshold": SLOW_TEST_THRESHOLD_SECONDS,
            "max_concurrent_requests": MAX_CONCURRENT_REQUESTS,
        },
    }


@pytest.fixture
def logger() -> FilteringBoundLogger:
    """テスト用structlogロガー

    Returns:
        FilteringBoundLogger: structlogのフィルタリング対応BoundLogger
    """
    return get_logger("test")


# =============================================================================
# API関連フィクスチャ
# =============================================================================


@pytest_asyncio.fixture
async def async_client(
    test_config: TestConfigDict,
) -> AsyncGenerator[AsyncAPIClient, None]:
    """非同期HTTPクライアント"""
    async with AsyncAPIClient(
        base_url=test_config["api"]["base_url"],
        timeout=test_config["api"]["timeout"],
        headers={"User-Agent": TEST_USER_AGENT},
    ) as client:
        yield client


@pytest.fixture
def mock_httpx_async_client() -> Mock:
    """モック化されたHTTPX非同期クライアント

    Returns:
        Mock: httpx.AsyncClientのspec付きMock。
            get/post/put/delete/patchメソッドはAsyncMock。

    Note:
        Sync版テストには mock_httpx_sync_client を使用してください。
    """
    mock_client = Mock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock()
    mock_client.post = AsyncMock()
    mock_client.put = AsyncMock()
    mock_client.delete = AsyncMock()
    mock_client.patch = AsyncMock()
    return mock_client


@pytest.fixture
def mock_httpx_sync_client() -> Mock:
    """モック化されたHTTPX同期クライアント

    Returns:
        Mock: httpx.Clientのspec付きMock。
            requestメソッドは_make_request_with_retry()から呼ばれる。
            get/post/put/delete/patchメソッドは通常Mock（非AsyncMock）。

    Note:
        既存mock_httpx_async_clientはspec=httpx.AsyncClientのため、
        Sync版テストにはこちらを使用する。
    """
    mock_client = Mock(spec=httpx.Client)
    mock_client.request = Mock()  # _make_request_with_retry()が使用
    mock_client.get = Mock()
    mock_client.post = Mock()
    mock_client.put = Mock()
    mock_client.delete = Mock()
    mock_client.patch = Mock()
    return mock_client


@pytest.fixture
def sample_api_response() -> TodoResponse:
    """JSONPlaceholder APIのサンプルレスポンス

    Returns:
        TodoResponse: TODOレスポンスのサンプルデータ
    """
    return {"userId": 1, "id": 1, "title": "delectus aut autem", "completed": False}


@pytest.fixture
def mock_successful_response(sample_api_response: TodoResponse) -> Mock:
    """成功時のモックレスポンス

    Args:
        sample_api_response: サンプルTODOデータ

    Returns:
        Mock: status_code=200のhttpx.Response Mock
    """
    mock_response = Mock(spec=Response)
    mock_response.status_code = 200
    mock_response.json.return_value = sample_api_response
    mock_response.text = json.dumps(sample_api_response)
    mock_response.headers = {"content-type": "application/json"}
    mock_response.raise_for_status.return_value = None
    return mock_response


@pytest.fixture
def mock_error_response() -> Mock:
    """エラー時のモックレスポンス

    Returns:
        Mock: status_code=404のhttpx.Response Mock。
            raise_for_statusはHTTPStatusErrorを発生。
    """
    mock_response = Mock(spec=Response)
    mock_response.status_code = 404
    mock_response.json.return_value = {"error": "Not Found"}
    mock_response.text = '{"error": "Not Found"}'
    mock_response.headers = {"content-type": "application/json"}
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404 Not Found", request=Mock(), response=mock_response
    )
    return mock_response


def create_mock_response(
    status_code: int,
    *,
    json_data: dict[str, Any] | None = None,
    text: str | None = None,
    is_client_error: bool | None = None,
    is_server_error: bool | None = None,
    raise_for_status_error: bool = True,
) -> Mock:
    """Mock httpx.Response を生成するファクトリ関数.

    PropertyMock を使用して is_client_error/is_server_error プロパティを
    正しくモック化。従来の属性設定では Mock オブジェクトが返される問題を解決。

    Args:
        status_code: HTTPステータスコード
        json_data: レスポンスJSONデータ（デフォルト: {"status": "ok"}）
        text: レスポンステキスト（Noneの場合はjson_dataから自動生成）
        is_client_error: 4xxエラーかどうか（Noneの場合はstatus_codeから自動判定）
        is_server_error: 5xxエラーかどうか（Noneの場合はstatus_codeから自動判定）
        raise_for_status_error: 4xx/5xx時にraise_for_statusでHTTPStatusErrorを発生させるか
            （デフォルト: True）

    Returns:
        設定済みMock httpx.Response

    Example:
        >>> mock_404 = create_mock_response(404)
        >>> mock_404.status_code
        404
        >>> mock_404.is_client_error
        True
        >>> mock_404.is_server_error
        False

        >>> mock_500 = create_mock_response(500, json_data={"error": "Internal"})
        >>> mock_500.is_server_error
        True

        # raise_for_status の動作確認
        >>> mock_404 = create_mock_response(404)
        >>> mock_404.raise_for_status()  # raises HTTPStatusError

        >>> mock_200 = create_mock_response(200)
        >>> mock_200.raise_for_status()  # returns None (no error)

    Note:
        - PropertyMock により httpx.Response.is_client_error プロパティの動作を再現
        - 依存分離: httpx パッケージへの依存を最小化（単体テストの原則）
        - バージョン耐性: httpx の内部実装変更に影響されない
        - raise_for_status_error=False で明示的にエラー発生を抑制可能
    """
    response = Mock(spec=httpx.Response)
    response.status_code = status_code

    # JSONデータ設定
    if json_data is None:
        json_data = {"status": "ok"}
    response.json.return_value = json_data

    # テキスト設定
    if text is None:
        text = json.dumps(json_data)
    response.text = text

    # ヘッダー設定
    response.headers = {"content-type": "application/json"}

    # 自動判定（明示的指定がない場合）
    if is_client_error is None:
        is_client_error = 400 <= status_code < 500
    if is_server_error is None:
        is_server_error = 500 <= status_code < 600

    # PropertyMock でプロパティを正しく設定
    # Note: type(response) を使うことでインスタンスではなくクラスに設定
    type(response).is_client_error = PropertyMock(return_value=is_client_error)
    type(response).is_server_error = PropertyMock(return_value=is_server_error)

    # raise_for_status のモック設定
    if raise_for_status_error and status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"{status_code} Error",
            request=Mock(spec=httpx.Request),
            response=response,
        )
    else:
        response.raise_for_status.return_value = None

    return response


@pytest.fixture
def mock_response_factory() -> Callable[..., Mock]:
    """Mock httpx.Response ファクトリフィクスチャ

    Returns:
        Callable: create_mock_response 関数

    Example:
        def test_example(mock_response_factory):
            mock_404 = mock_response_factory(404)
            mock_500 = mock_response_factory(500, json_data={"error": "Server Error"})
    """
    return create_mock_response


# =============================================================================
# テストデータフィクスチャ
# =============================================================================


@pytest.fixture
def todo_data_factory() -> Callable[..., TodoResponse]:
    """TODOテストデータファクトリー

    Returns:
        Callable: TODOデータを生成する関数
    """

    def create_todo(
        user_id: int = 1,
        todo_id: int = 1,
        title: str = "Test TODO",
        completed: bool = False,
    ) -> TodoResponse:
        return {
            "userId": user_id,
            "id": todo_id,
            "title": title,
            "completed": completed,
        }

    return create_todo


@pytest.fixture
def user_data_factory() -> Callable[..., dict[str, Any]]:
    """ユーザーテストデータファクトリー

    Returns:
        Callable: ユーザーデータを生成する関数
    """

    def create_user(
        user_id: int = 1,
        name: str = "Test User",
        username: str = "testuser",
        email: str = "test@example.com",
    ) -> dict[str, Any]:
        return {
            "id": user_id,
            "name": name,
            "username": username,
            "email": email,
            "address": {
                "street": "Test Street",
                "suite": "Apt. 1",
                "city": "Test City",
                "zipcode": "12345-6789",
                "geo": {"lat": "0.0000", "lng": "0.0000"},
            },
            "phone": "1-770-736-8031 x56442",
            "website": "testuser.org",
            "company": {
                "name": "Test Company",
                "catchPhrase": "Test catchphrase",
                "bs": "test business",
            },
        }

    return create_user


@pytest.fixture
def post_data_factory() -> Callable[..., dict[str, Any]]:
    """投稿テストデータファクトリー

    Returns:
        Callable: 投稿データを生成する関数
    """

    def create_post(
        user_id: int = 1,
        post_id: int = 1,
        title: str = "Test Post",
        body: str = "Test post body content",
    ) -> dict[str, Any]:
        return {"userId": user_id, "id": post_id, "title": title, "body": body}

    return create_post


# =============================================================================
# パフォーマンステスト用フィクスチャ
# =============================================================================


@pytest.fixture
def performance_timer() -> Timer:
    """パフォーマンス計測用タイマー

    Returns:
        Timer: パフォーマンス計測用タイマーインスタンス

    Warning:
        Timerクラスはスレッドセーフではありません。
        pytest-xdist並列実行時は各ワーカーで独立したインスタンスが
        使用されますが、共有状態での使用は避けてください。
    """
    return Timer()


# =============================================================================
# エラーハンドリング用フィクスチャ
# =============================================================================


@pytest.fixture
def error_scenarios() -> dict[str, Exception]:
    """各種エラーシナリオ

    Returns:
        dict: エラー種別名をキーとした例外オブジェクトの辞書
    """
    return {
        "timeout": httpx.TimeoutException("Request timed out"),
        "connection_error": httpx.ConnectError("Connection failed"),
        "http_error": httpx.HTTPStatusError(
            "500 Internal Server Error", request=Mock(), response=Mock(status_code=500)
        ),
        "json_decode_error": json.JSONDecodeError("Invalid JSON", "doc", 0),
    }


# =============================================================================
# セキュリティテスト用フィクスチャ
# =============================================================================


@pytest.fixture
def security_payloads() -> dict[str, list[str]]:
    """セキュリティテスト用のペイロード（ASVS Level 1 V5.3準拠）

    Returns:
        dict: 攻撃種別名をキーとしたペイロードリストの辞書

    Note:
        このフィクスチャはASVS Level 1のV5.3（入力検証）要件に対応。
        - sql_injection: V5.3.4
        - xss: V5.3.3
        - command_injection: V5.3.8
        - path_traversal: V5.3.8
    """
    return {
        "sql_injection": [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'--",
        ],
        "xss": [
            "<script>alert('xss')</script>",
            "javascript:alert(1)",
            "<img src=x onerror=alert(1)>",
        ],
        "command_injection": [
            "; ls -la",
            "| cat /etc/passwd",
            "&& whoami",
        ],
        "path_traversal": [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\drivers\\etc\\hosts",
            "....//....//....//etc/passwd",
        ],
    }


# =============================================================================
# 統合テスト用フィクスチャ
# =============================================================================


@pytest.fixture  # scope="function"(default) - テスト分離保証
def integration_test_data() -> dict[str, list[dict[str, Any]]]:
    """統合テスト用データセット

    各テストに独立したデータインスタンスを提供します。

    Note:
        scope="function"(デフォルト)を使用。可変データ(list/dict)の
        module scope共有はテスト間汚染リスクがあるため回避。

    Returns:
        dict: 以下の構造を持つテストデータ辞書

            - "todos": list[dict] - 15個のTODOオブジェクト
                * userId (int): 1-3
                * id (int): 1-5 (per userId)
                * title (str): "TODO {id}"形式
                * completed (bool): id % 2 == 0 の場合 True
            - "users": list[dict] - 3個のユーザーオブジェクト
                * id (int): 1-3
                * name (str): "User {id}"形式
                * username (str): "user{id}"形式
                * email (str): "user{id}@example.com"形式
    """
    return {
        "todos": [
            {"userId": i, "id": j, "title": f"TODO {j}", "completed": j % 2 == 0}
            for i in range(1, 4)
            for j in range(1, 6)
        ],
        "users": [
            {
                "id": i,
                "name": f"User {i}",
                "username": f"user{i}",
                "email": f"user{i}@example.com",
            }
            for i in range(1, 4)
        ],
    }


# =============================================================================
# クリーンアップフィクスチャ
# =============================================================================


@pytest.fixture(autouse=True)
def cleanup_test_files() -> Generator[None, None, None]:
    """テスト後のファイルクリーンアップ

    Yields:
        None: テスト実行を許可

    Note:
        autouse=Trueにより全テストで自動実行
    """
    yield

    # テンポラリファイルの削除
    temp_files = Path().glob("test_*.tmp")
    for temp_file in temp_files:
        temp_file.unlink(missing_ok=True)


# =============================================================================
# 学習ポイント:
#
# 1. フィクスチャスコープの使い分け:
#    - session: テスト実行全体で1回のみ
#    - module: モジュール単位で1回
#    - function: テスト関数ごと（デフォルト）
#
# 2. ファクトリーパターン:
#    - 動的なテストデータ生成
#    - パラメータ化による柔軟性
#
# 3. モック活用:
#    - 外部依存の排除
#    - テスト実行速度向上
#    - エラーシナリオの再現
#
# 4. 非同期テストサポート:
#    - AsyncClient の適切な管理
#    - イベントループの共有
#
# 5. 自動クリーンアップ:
#    - autouse=True による自動実行
#    - テスト環境の清潔性維持
#
# 6. structlog統合:
#    - プロジェクト標準のstructlogを使用
#    - FilteringBoundLoggerによる型安全なログ
#
# 7. 型安全性:
#    - TypedDictによる構造化データの型定義
#    - MappingProxyTypeによるランタイム不変性
#    - Final定数によるAPI安定性の明示
# =============================================================================
