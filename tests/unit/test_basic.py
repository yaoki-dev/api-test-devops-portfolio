"""
基本APIテスト - JSONPlaceholder API対象

学習目標:
- pytest基本パターンの習得
- HTTPXクライアント使用方法
- 非同期テストの実装
- アサーションの効果的な書き方
"""

from typing import Any

import httpx
import pytest

# =============================================================================
# 基本同期テスト
# =============================================================================


@pytest.mark.unit
def test_jsonplaceholder_api_accessible():
    """JSONPlaceholder APIへの基本的な接続確認"""
    # Given: JSONPlaceholder APIのエンドポイント
    url = "https://jsonplaceholder.typicode.com/todos/1"

    # When: 同期HTTPクライアントでリクエスト実行
    with httpx.Client() as client:
        response = client.get(url)

    # Then: 正常なレスポンスが返される
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    # JSONデータの基本構造を確認
    data = response.json()
    assert "userId" in data
    assert "id" in data
    assert "title" in data
    assert "completed" in data

    # データ型の確認
    assert isinstance(data["userId"], int)
    assert isinstance(data["id"], int)
    assert isinstance(data["title"], str)
    assert isinstance(data["completed"], bool)


@pytest.mark.unit
def test_todos_endpoint_returns_list():
    """TODOsエンドポイントが配列を返すことを確認"""
    # Given: TODOsリストのエンドポイント
    url = "https://jsonplaceholder.typicode.com/todos"

    # When: リクエスト実行（上限5件で制限）
    with httpx.Client() as client:
        response = client.get(url, params={"_limit": 5})

    # Then: 配列形式のレスポンスが返される
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 5

    # 各アイテムの構造確認
    for todo in data:
        assert "userId" in todo
        assert "id" in todo
        assert "title" in todo
        assert "completed" in todo


@pytest.mark.unit
def test_users_endpoint_response_structure():
    """ユーザーエンドポイントのレスポンス構造確認"""
    # Given: 特定ユーザーのエンドポイント
    url = "https://jsonplaceholder.typicode.com/users/1"

    # When: リクエスト実行
    with httpx.Client() as client:
        response = client.get(url)

    # Then: 想定されるユーザー情報構造を確認
    assert response.status_code == 200
    data = response.json()

    # 必須フィールドの存在確認
    required_fields = ["id", "name", "username", "email"]
    for field in required_fields:
        assert field in data, f"Required field '{field}' missing"

    # ネストした構造の確認
    assert "address" in data
    assert "geo" in data["address"]
    assert "lat" in data["address"]["geo"]
    assert "lng" in data["address"]["geo"]

    # 会社情報の確認
    assert "company" in data
    assert "name" in data["company"]


# =============================================================================
# 非同期テスト
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_api_request(async_client):
    """非同期クライアントを使用したAPIリクエスト"""
    # Given: 非同期クライアント（fixtureから提供）
    # When: 非同期でAPIリクエスト実行
    response = await async_client.get("/posts/1")

    # Then: 正常なレスポンスを確認
    assert response.status_code == 200
    data = response.json()

    # 投稿データの構造確認
    assert "userId" in data
    assert "id" in data
    assert "title" in data
    assert "body" in data
    assert data["id"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_concurrent_requests(async_client):
    """複数の並行リクエストのテスト"""
    import asyncio

    # Given: 複数のエンドポイント
    endpoints = ["/todos/1", "/todos/2", "/todos/3"]

    # When: 並行してリクエスト実行
    tasks = [async_client.get(endpoint) for endpoint in endpoints]
    responses = await asyncio.gather(*tasks)

    # Then: すべてのリクエストが成功
    assert len(responses) == 3
    for i, response in enumerate(responses, 1):
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == i


# =============================================================================
# パラメータ化テスト
# =============================================================================


@pytest.mark.unit
@pytest.mark.parametrize(
    "todo_id,expected_user_id",
    [
        (1, 1),
        (2, 1),
        (21, 2),
        (31, 2),
    ],
)
def test_todo_user_mapping(todo_id: int, expected_user_id: int):
    """TODOとユーザーIDのマッピング確認（パラメータ化テスト）"""
    # Given: 特定のTODO ID
    url = f"https://jsonplaceholder.typicode.com/todos/{todo_id}"

    # When: TODO情報を取得
    with httpx.Client() as client:
        response = client.get(url)

    # Then: 期待されるユーザーIDと一致
    assert response.status_code == 200
    data = response.json()
    assert data["userId"] == expected_user_id


@pytest.mark.unit
@pytest.mark.parametrize(
    "endpoint", ["/posts", "/comments", "/albums", "/photos", "/todos", "/users"]
)
def test_all_endpoints_accessible(endpoint: str):
    """全エンドポイントのアクセス確認"""
    # Given: 各種エンドポイント
    url = f"https://jsonplaceholder.typicode.com{endpoint}"

    # When: リクエスト実行（件数制限付き）
    with httpx.Client() as client:
        response = client.get(url, params={"_limit": 3})

    # Then: 正常にアクセス可能
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 3


# =============================================================================
# エラーハンドリングテスト
# =============================================================================


@pytest.mark.unit
def test_nonexistent_resource_returns_404():
    """存在しないリソースで404エラーを確認"""
    # Given: 存在しないリソースのURL
    url = "https://jsonplaceholder.typicode.com/todos/99999"

    # When: リクエスト実行
    with httpx.Client() as client:
        response = client.get(url)

    # Then: 404エラーが返される
    assert response.status_code == 404


@pytest.mark.unit
def test_invalid_endpoint_returns_404():
    """無効なエンドポイントで404エラーを確認"""
    # Given: 無効なエンドポイント
    url = "https://jsonplaceholder.typicode.com/invalid-endpoint"

    # When: リクエスト実行
    with httpx.Client() as client:
        response = client.get(url)

    # Then: 404エラーが返される
    assert response.status_code == 404


# =============================================================================
# フィクスチャ活用テスト
# =============================================================================


@pytest.mark.unit
def test_with_sample_data(sample_api_response: dict[str, Any]):
    """サンプルデータフィクスチャの活用例"""
    # Given: フィクスチャから提供されるサンプルデータ
    # Then: 期待される構造を持つことを確認
    assert "userId" in sample_api_response
    assert "id" in sample_api_response
    assert "title" in sample_api_response
    assert "completed" in sample_api_response

    # データ型の確認
    assert isinstance(sample_api_response["userId"], int)
    assert isinstance(sample_api_response["id"], int)
    assert isinstance(sample_api_response["title"], str)
    assert isinstance(sample_api_response["completed"], bool)


@pytest.mark.unit
def test_with_data_factory(todo_data_factory):
    """データファクトリーフィクスチャの活用例"""
    # Given: TODOデータファクトリー
    # When: カスタムTODOデータを生成
    todo = todo_data_factory(
        user_id=5, todo_id=100, title="Custom Test TODO", completed=True
    )

    # Then: 指定した値でデータが作成される
    assert todo["userId"] == 5
    assert todo["id"] == 100
    assert todo["title"] == "Custom Test TODO"
    assert todo["completed"] is True


# =============================================================================
# 学習ポイント:
#
# 1. テスト構造（AAA パターン）:
#    - Given（前提条件）
#    - When（実行）
#    - Then（検証）
#
# 2. 同期 vs 非同期テスト:
#    - httpx.Client（同期）
#    - httpx.AsyncClient（非同期）
#    - @pytest.mark.asyncio デコレータ
#
# 3. パラメータ化テスト:
#    - @pytest.mark.parametrize
#    - 複数ケースの効率的なテスト
#
# 4. フィクスチャ活用:
#    - テストデータの再利用
#    - ファクトリーパターン
#
# 5. アサーション技法:
#    - 明確なエラーメッセージ
#    - 段階的な検証
#    - データ型確認
# =============================================================================
