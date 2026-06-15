"""tests/unit 専用 conftest: unit テスト固有のフィクスチャ"""

from collections.abc import Generator

import pytest

from utils.sentry_init import _is_sensitive_key


@pytest.fixture(autouse=True)
def clear_sensitive_key_cache() -> Generator[None]:
    """_is_sensitive_key lru_cache をテスト間でリセット (#10-TC-2)

    monkeypatch で SENSITIVE_KEYS を変更するテストがある場合、
    cache_clear() がないと古いキャッシュ値が他テストに残存する。
    """
    _is_sensitive_key.cache_clear()
    yield
    _is_sensitive_key.cache_clear()
