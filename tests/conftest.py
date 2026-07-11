"""
pytest共通設定とフィクスチャ定義
"""

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from config.settings import _resolve_hostname_cached, reload_settings

# =============================================================================
# Pytest設定
# =============================================================================


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


# =============================================================================
# Infrastructure Fixtures (autouse - テストコードから直接呼び出さない)
# =============================================================================


@pytest.fixture(autouse=True)
def disable_sentry_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    テスト実行時にSentry SDKを無効化。

    Purpose:
        テスト中のエラーがSentryに送信されるのを防止し、
        本番ダッシュボードへの誤送信リスクを排除する。

    Note:
        - autouse=True により全テストに自動適用
        - テストコードから明示的に呼び出す必要なし
        - 環境変数はPydantic Settings形式（SENTRY__ENABLED）
    """
    monkeypatch.setenv("SENTRY__ENABLED", "false")


@pytest.fixture(scope="session", autouse=True)
def isolate_proxy_env() -> Iterator[None]:
    """
    テストセッション全体でプロキシ系環境変数を除去し、テストを環境非依存にする。

    Purpose:
        開発環境の HTTP(S)_PROXY / NO_PROXY / ALL_PROXY を剥離し、
        httpx クライアント生成をアンビエントなプロキシ設定から隔離する。
        ローカルインターセプタ (例: llmtrim) が NO_PROXY に IPv6 CIDR
        (fd00::/8 等) を注入すると httpx が InvalidURL を送出し
        (encode/httpx#3221)、全 httpx.Client/AsyncClient 生成が失敗する。
        本 fixture でテストが実行環境のプロキシ設定に依存しないことを保証する。

    Scope:
        session スコープにすることで、class / module スコープのクライアント
        fixture（例: tests/test_smoke.py の class スコープ api_client）が生成
        される前に env を剥離する。function スコープでは高スコープ fixture の
        後に実行され間に合わない（pytest は高スコープ fixture を先に生成する）。

    Note:
        - autouse=True により全テストに自動適用
        - 本番挙動は不変（本番クライアントは trust_env=True のまま）
        - httpx は小文字系も参照するため大文字/小文字の両方を除去
        - monkeypatch fixture は function スコープ専用のため、公式 API の
          pytest.MonkeyPatch() を直接使用し teardown で undo する
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


# =============================================================================
# 基本フィクスチャ
# =============================================================================


@pytest.fixture
def logger() -> logging.Logger:
    """テスト用ロガー"""
    return logging.getLogger("test")


# =============================================================================
# API関連フィクスチャ
# =============================================================================


@pytest.fixture
def mock_base_url() -> str:
    """unit テスト用ダミーURL（外部通信なし）"""
    return "https://test.local"


# =============================================================================
# クリーンアップフィクスチャ
# =============================================================================


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
    """
    各テスト実行前に設定をリロードしてテスト独立性を保証

    同一プロセス内での逐次テスト間、
    グローバルシングルトンsettingsのテスト間汚染（環境変数変更の残留等）を防止
    """
    _resolve_hostname_cached.cache_clear()
    reload_settings()
    yield


@pytest.fixture(autouse=True)
def reset_sentry_warning_state(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """utils.logger の sentry warning throttle 状態をテスト前後でリセット

    6 つの permanent throttle マーカー
    ("settings"/"sdk"/"bug"/"outside_except"/"invalid_exc_info"/"safe_error_summary") を
    保持する `_sentry_warnings_emitted: set[str]` を空集合に、
    `_sentry_send_error_last_warned` timestamp を float("-inf") にリセットする。
    `_is_sentry_debug_enabled` は lru_cache 削除済みのためリアルタイム取得。
    monkeypatch.setenv/delenv との整合性は自動的に保たれる。

    `_sentry_warning_lock` (threading.Lock) はリセット対象外:
    Lock インスタンス自体を差し替えるとモジュール内の他参照と整合しなくなり、また
    ロック状態は test 間で leak しない (各テスト内でロック取得・解放が完結する) ため
    リセット不要。

    monkeypatch.setattr は test 終了時に自動復元され、環境変数変更も即時反映される。
    lru_cache 削除済みのため teardown での cache_clear() は不要。

    autouse=True により全テストで自動適用し、TestSentryProcessor 以外のクラスでも
    モジュールレベル throttle 状態の汚染を防止する (同一プロセス内の逐次テスト間
    におけるフラグ汚染による偽陽性回避)。

    Note: pytest-xdist は各ワーカーが別プロセスで動作するためモジュールレベルの
    グローバル変数はプロセス間で共有されない。本 fixture の主目的は同一プロセス内
    の逐次テスト間の汚染防止であり、xdist による並列実行は副次的な恩恵。
    """

    monkeypatch.setattr("utils.logger._sentry_warnings_emitted", set())
    monkeypatch.setattr("utils.logger._sentry_send_error_last_warned", float("-inf"))
    # SENTRY_DEBUG は環境変数をリアルタイム取得するため、キャッシュリセット不要
    yield
