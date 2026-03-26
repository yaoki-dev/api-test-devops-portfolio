"""テスト共通定数."""

from typing import Final

import pytest

BASE_URL: str = "https://jsonplaceholder.typicode.com"

INVALID_BASE_URLS: Final = [
    pytest.param("", id="empty"),
    pytest.param("   ", id="whitespace"),
    pytest.param("\t", id="tab"),
    pytest.param("\n", id="newline"),
]
