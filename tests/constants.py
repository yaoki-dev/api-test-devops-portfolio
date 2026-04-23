"""テスト共通定数.

このファイルはテスト専用です。プロダクションコードからインポートしないでください。
"""

from typing import Final

BASE_URL: str = "https://jsonplaceholder.typicode.com"

INVALID_BASE_URLS: Final[tuple[str, ...]] = ("", "   ", "\t", "\n")
