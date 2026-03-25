"""テスト共通定数."""

import pytest

BASE_URL: str = "https://jsonplaceholder.typicode.com"

INVALID_BASE_URLS = [
    pytest.param("", id="empty"),
    pytest.param("   ", id="whitespace"),
    pytest.param("\t", id="tab"),
    pytest.param("\n", id="newline"),
]
