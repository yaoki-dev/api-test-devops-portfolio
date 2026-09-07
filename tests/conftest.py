"""
pytest共通設定とフィクスチャ定義
"""

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from config.settings import reload_settings


def pytest_configure(config: pytest.Config) -> None:
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
    config.addinivalue_line("markers", "performance: パフォーマンステスト")
    config.addinivalue_line("markers", "slow: 実行時間の長いテスト")
    config.addinivalue_line("markers", "external: 外部API依存テスト")
    config.addinivalue_line("markers", "smoke: スモークテスト（main PR用、基本機能の動作確認）")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """テスト実行順序の最適化"""

    # 高速テストを先に実行
    def _sort_key(item: pytest.Item) -> tuple[bool, bool, str]:
        return (
            item.get_closest_marker("slow") is not None,
            item.get_closest_marker("external") is not None,
            item.name,
        )

    items.sort(key=_sort_key)


@pytest.fixture(autouse=True)
def disable_sentry_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """テスト中のエラーがSentry本番ダッシュボードへ誤送信されるリスクを排除する。"""
    monkeypatch.setenv("SENTRY__ENABLED", "false")


@pytest.fixture(scope="session", autouse=True)
def isolate_proxy_env() -> Iterator[None]:
    """httpx クライアント生成をアンビエントなプロキシ設定から隔離する。

    NO_PROXY に IPv6 CIDR が入ると httpx が InvalidURL を送出するため
    (encode/httpx#3221)、大文字/小文字の両方を除去する。
    session スコープで class/module client fixture より先に剥離し、
    function scope の monkeypatch ではなく直接 MonkeyPatch を undo する。
    """
    mp = pytest.MonkeyPatch()
    for var in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
    ):
        mp.delenv(var, raising=False)
    yield
    mp.undo()


@pytest.fixture
def logger() -> logging.Logger:
    """テスト用ロガー"""
    return logging.getLogger("test")


@pytest.fixture
def mock_base_url() -> str:
    """unit テスト用ダミーURL（外部通信なし）"""
    return "https://test.local"


@pytest.fixture(autouse=True)
def cleanup_test_files() -> Iterator[None]:
    """テスト後のファイルクリーンアップ"""
    yield

    # テンポラリファイルの削除
    temp_files = Path().glob("test_*.tmp")
    for temp_file in temp_files:
        temp_file.unlink(missing_ok=True)


@pytest.fixture(scope="function", autouse=True)
def reset_settings() -> Iterator[None]:
    """settings singleton のテスト間汚染を防ぐ。"""
    reload_settings()
    yield


@pytest.fixture(autouse=True)
def reset_sentry_warning_state(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Sentry warning throttle/cache の module state をテスト前後で隔離する。

    `_sentry_warning_lock` は差し替えるとモジュール内の他参照と整合しないため残す。
    monkeypatch 復元と cache なしの debug flag により teardown の cache_clear は不要。
    同一プロセス内の逐次テスト汚染を防ぎ、xdist は別プロセスなので副次的な保護に留まる。
    """

    monkeypatch.setattr("utils.logger._sentry_warnings_emitted", set())
    monkeypatch.setattr("utils.logger._sentry_send_error_last_warned", float("-inf"))
    # SENTRY_DEBUG は環境変数をリアルタイム取得するため、キャッシュリセット不要
    yield
