"""テスト共通定数."""

from typing import Final

import pytest

BASE_URL: str = "https://jsonplaceholder.typicode.com"

# pytest.ParameterSet は _pytest.mark.structures の内部 API のため
# 公開型スタブに含まれず、Final[list[pytest.ParameterSet]] は mypy エラーになる。
# Final のみとすることで mypy が list[ParameterSet] と正しく推論する。
INVALID_BASE_URLS: Final = [
    pytest.param("", id="empty"),
    pytest.param("   ", id="whitespace"),
    pytest.param("\t", id="tab"),
    pytest.param("\n", id="newline"),
]
