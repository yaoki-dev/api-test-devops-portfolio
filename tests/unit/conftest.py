"""tests/unit 専用 conftest: unit テスト固有のフィクスチャ"""

from collections.abc import Generator

import pytest
from pytest_socket import disable_socket, enable_socket

from utils.sentry_scrub_primitives import _is_sensitive_key


@pytest.fixture(autouse=True)
def block_network_socket() -> Generator[None]:
    """unit テスト中の実 TCP/UDP socket 使用を socket レベルで遮断する。

    allow_unix_socket=True は xdist/asyncio の Unix domain socket 通信を残すため。
    function スコープで unit 層外への漏れを防ぐが、高スコープ fixture setup は先に走る。
    """
    disable_socket(allow_unix_socket=True)
    yield
    enable_socket()


@pytest.fixture(autouse=True)
def clear_sensitive_key_cache() -> Generator[None]:
    """SENSITIVE_KEYS monkeypatch の古い lru_cache 値が他テストへ残るのを防ぐ。"""
    _is_sensitive_key.cache_clear()
    yield
    _is_sensitive_key.cache_clear()
