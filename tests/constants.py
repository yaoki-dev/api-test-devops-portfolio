"""テスト共通定数.

このファイルはテスト専用です。プロダクションコードからインポートしないでください。
"""

from typing import Final

import pytest

BASE_URL: str = "https://jsonplaceholder.typicode.com"

# Final のみで型推論可（pytest.ParameterSet は内部 API のため型パラメータ不要）
INVALID_BASE_URLS: Final = [
    pytest.param("", id="empty"),
    pytest.param("   ", id="whitespace"),
    pytest.param("\t", id="tab"),
    pytest.param("\n", id="newline"),
]
