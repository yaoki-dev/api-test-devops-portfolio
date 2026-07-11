"""テスト共通 TypedDict 型定義 — テストファイル間で共有する正典."""

from typing import TypedDict

__all__ = [
    "_AddressData",
    "_CompanyData",
    "_GeoData",
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
