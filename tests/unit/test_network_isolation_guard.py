"""unit 層で実 TCP を遮断し、pytest-xdist 用 Unix socket は許可する契約を固定する。"""

import socket

import pytest
from pytest_socket import SocketBlockedError

pytestmark = pytest.mark.unit


def test_real_tcp_socket_is_blocked() -> None:
    with pytest.raises(SocketBlockedError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def test_unix_socket_is_allowed() -> None:
    """pytest-xdist と asyncio を壊さないため、Unix domain socket は許可する。"""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        assert sock.family == socket.AF_UNIX
    finally:
        sock.close()
