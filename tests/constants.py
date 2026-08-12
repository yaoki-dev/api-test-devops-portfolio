"""プロダクションコードからインポートしないテスト専用の共通定数。"""

from typing import Final

BASE_URL: Final[str] = "https://jsonplaceholder.typicode.com"

INVALID_BASE_URLS: Final[tuple[str, ...]] = ("", "   ", "\t", "\n")
