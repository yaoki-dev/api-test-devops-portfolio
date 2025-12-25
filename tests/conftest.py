"""
pytest共通設定とフィクスチャ定義

学習目標:
- pytest fixture設計パターンの理解
- テストデータ管理の効率化
- モックとスタブの活用方法
- テスト環境分離の実現
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
import pytest_asyncio
from httpx import Response

from config.settings import reload_settings
from utils.api_client import AsyncAPIClient

# =============================================================================
# Pytest設定
# =============================================================================


def pytest_configure(config):
    """pytest実行時の共通設定"""
    # ログ設定
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/test.log")
            if Path("logs").exists()
            else logging.StreamHandler(),
        ],
    )

    # テストマーカーの登録
    config.addinivalue_line("markers", "unit: 単体テスト")
    config.addinivalue_line("markers", "integration: 統合テスト")
    config.addinivalue_line("markers", "e2e: E2Eテスト")
    config.addinivalue_line("markers", "slow: 実行時間の長いテスト")
    config.addinivalue_line("markers", "external: 外部API依存テスト")
    config.addinivalue_line("markers", "performance: パフォーマンステスト")
    config.addinivalue_line("markers", "smoke: スモークテスト（main PR用、基本機能の動作確認）")


def pytest_collection_modifyitems(config, items):
    """テスト実行順序の最適化"""
    # 高速テストを先に実行
    items.sort(
        key=lambda item: (
            "slow" in [mark.name for mark in item.iter_markers()],
            "external" in [mark.name for mark in item.iter_markers()],
            item.name,
        )
    )


# =============================================================================
# 基本フィクスチャ
# =============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """非同期テスト用のイベントループ（セッションスコープ）"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_config() -> dict[str, Any]:
    """テスト用設定データ"""
    return {
        "api": {
            "base_url": "https://jsonplaceholder.typicode.com",
            "timeout": 10,
            "retry_count": 1,
            "retry_delay": 0.5,
        },
        "log": {"level": "DEBUG", "format": "console"},
        "test": {
            "slow_test_threshold": 5.0,  # 5秒以上で"slow"マーク推奨
            "max_concurrent_requests": 5,
        },
    }


@pytest.fixture
def logger():
    """テスト用ロガー"""
    return logging.getLogger("test")


# =============================================================================
# API関連フィクスチャ
# =============================================================================


@pytest_asyncio.fixture
async def async_client(
    test_config: dict[str, Any],
) -> AsyncGenerator[AsyncAPIClient, None]:
    """非同期HTTPクライアント（テスト用）- Phase 1統合"""
    async with AsyncAPIClient(
        base_url=test_config["api"]["base_url"],
        timeout=test_config["api"]["timeout"],
        headers={"User-Agent": "API-Test-Portfolio/0.1.0"},
    ) as client:
        yield client


@pytest.fixture
def mock_httpx_client() -> Mock:
    """モック化されたHTTPXクライアント"""
    mock_client = Mock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock()
    mock_client.post = AsyncMock()
    mock_client.put = AsyncMock()
    mock_client.delete = AsyncMock()
    mock_client.patch = AsyncMock()
    return mock_client


@pytest.fixture
def sample_api_response() -> dict[str, Any]:
    """JSONPlaceholder APIのサンプルレスポンス"""
    return {"userId": 1, "id": 1, "title": "delectus aut autem", "completed": False}


@pytest.fixture
def mock_successful_response(sample_api_response: dict[str, Any]) -> Mock:
    """成功時のモックレスポンス"""
    mock_response = Mock(spec=Response)
    mock_response.status_code = 200
    mock_response.json.return_value = sample_api_response
    mock_response.text = json.dumps(sample_api_response)
    mock_response.headers = {"content-type": "application/json"}
    mock_response.raise_for_status.return_value = None
    return mock_response


@pytest.fixture
def mock_error_response() -> Mock:
    """エラー時のモックレスポンス"""
    mock_response = Mock(spec=Response)
    mock_response.status_code = 404
    mock_response.json.return_value = {"error": "Not Found"}
    mock_response.text = '{"error": "Not Found"}'
    mock_response.headers = {"content-type": "application/json"}
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404 Not Found", request=Mock(), response=mock_response
    )
    return mock_response


# =============================================================================
# テストデータフィクスチャ
# =============================================================================


@pytest.fixture
def todo_data_factory():
    """TODOテストデータファクトリー"""

    def create_todo(
        user_id: int = 1,
        todo_id: int = 1,
        title: str = "Test TODO",
        completed: bool = False,
    ) -> dict[str, Any]:
        return {
            "userId": user_id,
            "id": todo_id,
            "title": title,
            "completed": completed,
        }

    return create_todo


@pytest.fixture
def user_data_factory():
    """ユーザーテストデータファクトリー"""

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
def post_data_factory():
    """投稿テストデータファクトリー"""

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
def performance_timer():
    """パフォーマンス計測用タイマー"""
    import time

    class Timer:
        def __init__(self):
            self.start_time: float | None = None
            self.end_time: float | None = None

        def start(self):
            self.start_time = time.perf_counter()

        def stop(self):
            self.end_time = time.perf_counter()

        @property
        def elapsed(self) -> float:
            if self.start_time is None or self.end_time is None:
                raise ValueError("Timer not properly started/stopped")
            return self.end_time - self.start_time

        def assert_faster_than(self, threshold: float, message: str = "") -> None:
            if self.elapsed > threshold:
                pytest.fail(
                    f"Performance test failed: {self.elapsed:.3f}s > {threshold:.3f}s. {message}"
                )

    return Timer()


# =============================================================================
# エラーハンドリング用フィクスチャ
# =============================================================================


@pytest.fixture
def error_scenarios():
    """各種エラーシナリオ"""
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
def security_payloads():
    """セキュリティテスト用のペイロード"""
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


@pytest.fixture(scope="module")
def integration_test_data():
    """統合テスト用の大量データセット"""
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
def cleanup_test_files():
    """テスト後のファイルクリーンアップ"""
    yield

    # テンポラリファイルの削除
    temp_files = Path().glob("test_*.tmp")
    for temp_file in temp_files:
        temp_file.unlink(missing_ok=True)


@pytest.fixture(scope="function", autouse=True)
def reset_settings():
    """
    各テスト実行前に設定をリロードしてテスト独立性を保証

    将来的な並列実行（pytest -n auto）導入時に、
    グローバルシングルトンsettingsのテスト間汚染を防止
    """
    reload_settings()
    yield
    reload_settings()


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
# =============================================================================
