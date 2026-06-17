"""unit 層ネットワーク分離ガードテスト

tests/unit/conftest.py の `block_network_socket` fixture が満たすべき契約を
最小固定する。pytest-socket 自体の網羅テストは目的ではなく、本プロジェクトの
「実 TCP は遮断・Unix socket は許可」という 2 点の契約のみを退行防止する。
"""

import socket

import pytest
from pytest_socket import SocketBlockedError

pytestmark = pytest.mark.unit


def test_real_tcp_socket_is_blocked() -> None:
    """実 TCP socket の生成は SocketBlockedError で構造的に遮断される。"""
    with pytest.raises(SocketBlockedError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def test_unix_socket_is_allowed() -> None:
    """Unix domain socket は allow_unix_socket=True により許可される。

    pytest-xdist の並列ワーカー間通信や asyncio イベントループが
    Unix socket を使うため、これを遮断するとテストランナー自体が壊れる。
    """
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        assert sock.family == socket.AF_UNIX
    finally:
        sock.close()
