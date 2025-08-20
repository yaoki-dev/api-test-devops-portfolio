import pytest
from some_http_library import HTTPClient  # 仮のHTTPクライアントライブラリ


@pytest.fixture
def api_client():
    client = HTTPClient("https://api.example.com")
    return client


def test_get_user(api_client):  # ← fixtureが自動で渡される
    response = api_client.get("/users/1")
    assert response.status_code == 200
