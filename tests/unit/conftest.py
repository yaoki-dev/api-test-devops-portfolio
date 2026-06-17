"""tests/unit 専用 conftest: unit テスト固有のフィクスチャ"""

from collections.abc import Generator

import pytest
from pytest_socket import disable_socket, enable_socket

from utils.sentry_init import _is_sensitive_key


@pytest.fixture(autouse=True)
def block_network_socket() -> Generator[None]:
    """unit テスト実行中のみ実 TCP/UDP socket 使用を構造的に遮断する

    実 DNS 解決すり抜けを、テスト実装者の注意ではなく
    socket レベルの失敗 (SocketBlockedError) で再発防止する。

    - 適用範囲は tests/unit/ 配下のみ (conftest 限定)。integration / external /
      performance の実ネットワーク方針には影響しない。
    - allow_unix_socket=True: pytest-xdist の並列ワーカー間通信や asyncio
      イベントループが Unix domain socket を使うため許可する。
    - function スコープで disable→enable を都度トグルし、グローバル socket
      パッチが unit 層の外へ漏れないようにする。

    NOTE: socket.gethostbyname() による DNS 解決は pytest-socket で遮断されない（Cレベル呼び出しのため）。
    DNS 決定論化が必要なテストは file-local fixture で socket.gethostbyname seam を patch すること
    """  # noqa: E501
    disable_socket(allow_unix_socket=True)
    yield
    enable_socket()


@pytest.fixture(autouse=True)
def clear_sensitive_key_cache() -> Generator[None]:
    """_is_sensitive_key lru_cache をテスト間でリセット (#10-TC-2)

    monkeypatch で SENSITIVE_KEYS を変更するテストがある場合、
    cache_clear() がないと古いキャッシュ値が他テストに残存する。
    """
    _is_sensitive_key.cache_clear()
    yield
    _is_sensitive_key.cache_clear()
