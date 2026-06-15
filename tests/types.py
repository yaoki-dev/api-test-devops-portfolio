"""テスト共通 TypedDict 型定義 — conftest.py とテストファイル両方で使用する正典."""

from typing import TypedDict

__all__ = [
    "_AddressData",
    "_CompanyData",
    "_GeoData",
    "_IntegrationTestData",
    "_IntegrationUserData",
    "_PostData",
    "_TodoData",
    "_UserData",
]


class _GeoData(TypedDict):
    """JSONPlaceholder API geo 座標型."""

    lat: str
    lng: str


class _AddressData(TypedDict):
    """JSONPlaceholder API address 型."""

    street: str
    suite: str
    city: str
    zipcode: str
    geo: _GeoData


class _CompanyData(TypedDict):
    """JSONPlaceholder API company 型."""

    name: str
    catchPhrase: str
    bs: str


class _TodoData(TypedDict):
    """JSONPlaceholder API todo 型."""

    userId: int
    id: int
    title: str
    completed: bool


class _UserData(TypedDict):
    """JSONPlaceholder API user 型（ネスト構造あり）."""

    id: int
    name: str
    username: str
    email: str
    address: _AddressData
    phone: str
    website: str
    company: _CompanyData


class _PostData(TypedDict):
    """JSONPlaceholder API post 型."""

    userId: int
    id: int
    title: str
    body: str


class _IntegrationUserData(TypedDict):
    """integration_test_data fixture 用簡略 user 型（address/company 無）."""

    id: int
    name: str
    username: str
    email: str


class _IntegrationTestData(TypedDict):
    """integration_test_data fixture 戻り型."""

    todos: list[_TodoData]
    users: list[_IntegrationUserData]
