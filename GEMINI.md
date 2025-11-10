## プロジェクト概要

APIテスト + DevOps統合学習ポートフォリオ。時給6000-8000円レベルの技術力を証明するために設計されています。

**技術スタック**:
- Python 3.12
- httpx (Sync + Async HTTP client)
- pytest (累計100テスト作成、カバレッジ85%)
- Pydantic Settings (型安全な設定管理)
- structlog (構造化ログ)
- Docker (Multi-stage builds)
- docker-compose (4環境: dev/test/demo/prod)
- GitHub Actions (CI/CD自動化)

# Week 1 (Day 1-6): Python + httpx Core - 18時間

## 週次成果物サマリー

**実装時間**: 18時間（6日×3h max）
**学習時間**: 42時間（Phase 1: 15h, Phase 2: 18h, Phase 3: 3h, Buffer: 6h）

**成果物**:
- BaseAPIClient完成（同期GET/POST実装）
- エラー階層設計（5例外クラス: APIError/APIHTTPError/APIConnectionError/APITimeoutError/**APIValidationError** + リトライロジック）
- **Pydanticモデル4種実装**（User/Post/Todo/Comment、frozen=True、Field Alias対応）
- JSONPlaceholder専用クライアント（**型安全版**: dict → Pydanticモデル）
- Pydantic Settings基礎実装
- README基礎版作成
- pre-commitフック導入
- 累計25テスト達成

**メトリクス変化**:
- カバレッジ: 0% → 39.5%
- テスト数: 0 → 25件
- プロジェクト完成度: 0% → 15%

**Pydantic統一導入効果**:
- ✅ 型安全性: dict → Pydanticモデル（実行時検証）
- ✅ イミュータブル設計: frozen=True（データ保護）
- ✅ Field Alias: userId → user_id自動変換
- ✅ 企業実務パターン: FastAPI/LangChain等で標準採用

---

## Day 1 (月曜): Python基礎復習 + httpx導入

**学習内容**（学習プラン参照）:
- Python基礎復習: 型ヒント、Context Manager、例外処理
- httpx基礎: httpx.Client、GET/POST、Response handling
- pytest基礎: テスト作成パターン、assert、基本テストケース設計

**関連ポートフォリオ作成タスク**:

### Task 1.1: BaseAPIClient雛形作成（3h）

**要件**:
- BaseAPIClientクラス雛形作成
- 型ヒント付き関数3個実装
- Context Manager実装（`__enter__`/`__exit__`）
- tests/unit/test_api_client.py作成
- 基本テスト5件作成

**実装例**:
```python
# utils/api_client.py（雛形）
from typing import Optional
import httpx

class BaseAPIClient:
    """APIクライアント基底クラス"""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url
        self.timeout = timeout
        self._client: Optional[httpx.Client] = None

    def __enter__(self):
        """Context Manager入り口"""
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context Manager出口"""
        if self._client:
            self._client.close()

    def get(self, endpoint: str) -> dict:
        """GET操作（雛形）"""
        response = self._client.get(endpoint)
        response.raise_for_status()
        return response.json()
```

```python
# tests/unit/test_api_client.py（基本テスト）
import pytest
from utils.api_client import BaseAPIClient

def test_base_client_initialization():
    """クライアント初期化テスト"""
    client = BaseAPIClient("https://jsonplaceholder.typicode.com")
    assert client.base_url == "https://jsonplaceholder.typicode.com"
    assert client.timeout == 30.0

def test_context_manager_basic():
    """Context Manager基本動作テスト"""
    with BaseAPIClient("https://jsonplaceholder.typicode.com") as client:
        assert client._client is not None

# 残り3テスト: 型ヒント検証、基本属性確認等
```

**カバレッジ目標**: 6.6%

---

## Day 2 (火曜): httpx CRUD + リトライロジック + エラー階層

**学習内容**（学習プラン参照）:
- httpx CRUD操作: GET/POST/PUT/DELETE
- リトライロジック設計: Exponential backoff、リトライカウント
- エラー階層設計: APIError、HTTPError、ConnectionError、TimeoutError

**関連ポートフォリオ作成タスク**:

### Task 1.2: BaseAPIClient GET/POST実装 + エラー階層（3h）

**要件**:
- BaseAPIClient GET/POST完全実装
- 4例外クラス実装（APIError、APIHTTPError、APIConnectionError、APITimeoutError）
- リトライロジック実装（retry_count=3、exponential backoff）
- エラーハンドリングテスト5件追加

**実装例**:
```python
# utils/api_client.py（エラー階層）
class APIError(Exception):
    """API例外基底クラス"""
    pass

class APIHTTPError(APIError):
    """HTTPエラー（4xx/5xx）"""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")

class APIConnectionError(APIError):
    """接続エラー"""
    pass

class APITimeoutError(APIError):
    """タイムアウトエラー"""
    pass
```

```python
# utils/api_client.py（リトライロジック）
import time

class BaseAPIClient:
    def __init__(self, base_url: str, timeout: float = 30.0, retry_count: int = 3):
        self.base_url = base_url
        self.timeout = timeout
        self.retry_count = retry_count

    def _execute_with_retry(self, method: str, endpoint: str, **kwargs) -> dict:
        """リトライロジック実装"""
        for attempt in range(self.retry_count):
            try:
                response = self._client.request(method, endpoint, **kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException as e:
                if attempt == self.retry_count - 1:
                    raise APITimeoutError(f"Timeout after {self.retry_count} retries")
                time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500:  # 5xxのみリトライ
                    if attempt == self.retry_count - 1:
                        raise APIHTTPError(e.response.status_code, str(e))
                    time.sleep(2 ** attempt)
                else:  # 4xxは即座に失敗
                    raise APIHTTPError(e.response.status_code, str(e))

    def get(self, endpoint: str) -> dict:
        """GET操作（リトライ対応）"""
        return self._execute_with_retry("GET", endpoint)

    def post(self, endpoint: str, data: dict) -> dict:
        """POST操作（リトライ対応）"""
        return self._execute_with_retry("POST", endpoint, json=data)
```

**カバレッジ目標**: 13.2%（累積）
**テスト数**: 累計10件（+5件）

---

## Day 3 (水曜): JSONPlaceholder専用クライアント + Pydanticモデル導入

**学習内容**（学習プラン参照）:
- 専用クライアント設計: 継承パターン、エンドポイント抽象化
- **Pydantic基礎**: BaseModel、Field、EmailStr、frozen設定
- **型安全なAPI設計**: dict → Pydanticモデル変換パターン
- 統合テスト設計: 実API呼び出し、レスポンス検証

**関連ポートフォリオ作成タスク**:

### Task 1.3: JSONPlaceholderClient + Pydanticモデル実装（3h）

**要件**:
- **Pydanticモデル4種実装**（utils/models.py新規作成）:
  - User（id, name, username, email）
  - Post（id, user_id, title, body）
  - Todo（id, user_id, title, completed）
  - Comment（id, post_id, name, email, body）
- **APIValidationError実装**（ValidationError → APIValidationError変換）
- JSONPlaceholderClient実装（BaseAPIClient継承、戻り値をPydanticモデルに変更）
- get_user/get_posts/get_todos/get_comments実装（型安全）
- 統合テスト5件追加（`@pytest.mark.integration`、Pydanticモデル検証含む）

**実装例**:
```python
# utils/models.py（新規作成）
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List

class User(BaseModel):
    """ユーザーモデル"""
    model_config = ConfigDict(frozen=True)  # イミュータブル設定

    id: int
    name: str
    username: str
    email: EmailStr

class Post(BaseModel):
    """投稿モデル"""
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    id: int
    user_id: int = Field(alias="userId")  # JSON "userId" → Python "user_id"
    title: str
    body: str

class Todo(BaseModel):
    """TODOモデル"""
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    id: int
    user_id: int = Field(alias="userId")
    title: str
    completed: bool

class Comment(BaseModel):
    """コメントモデル"""
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    id: int
    post_id: int = Field(alias="postId")
    name: str
    email: EmailStr
    body: str
```

```python
# utils/api_client.py（APIValidationError追加）
from pydantic import ValidationError
from typing import List, Dict, Type, TypeVar

T = TypeVar('T', bound=BaseModel)

class APIValidationError(APIError):
    """APIレスポンス検証エラー"""
    def __init__(self, message: str, validation_errors: List[Dict]):
        super().__init__(message)
        self.validation_errors = validation_errors

class BaseAPIClient:
    # 既存コード...

    def _validate_model(self, data: Dict, model_class: Type[T]) -> T:
        """Pydanticモデル検証（共通メソッド）"""
        try:
            return model_class.model_validate(data)
        except ValidationError as e:
            raise APIValidationError(
                f"Response validation failed for {model_class.__name__}",
                e.errors()
            )

    def _validate_model_list(self, data: List[Dict], model_class: Type[T]) -> List[T]:
        """Pydanticモデルリスト検証"""
        return [self._validate_model(item, model_class) for item in data]
```

```python
# utils/api_client.py（専用クライアント - Pydanticモデル対応）
from utils.models import User, Post, Todo, Comment

class JSONPlaceholderClient(BaseAPIClient):
    """JSONPlaceholder API専用クライアント（型安全版）"""

    def __init__(self):
        super().__init__("https://jsonplaceholder.typicode.com")

    def get_user(self, user_id: int) -> User:
        """ユーザー取得（Pydantic検証付き）"""
        data = self.get(f"/users/{user_id}")
        return self._validate_model(data, User)

    def get_posts(self, user_id: Optional[int] = None) -> List[Post]:
        """投稿取得（全体またはユーザー別、Pydantic検証付き）"""
        endpoint = "/posts"
        if user_id:
            endpoint += f"?userId={user_id}"
        data = self.get(endpoint)
        return self._validate_model_list(data, Post)

    def get_todos(self, user_id: Optional[int] = None) -> List[Todo]:
        """TODO取得（全体またはユーザー別、Pydantic検証付き）"""
        endpoint = "/todos"
        if user_id:
            endpoint += f"?userId={user_id}"
        data = self.get(endpoint)
        return self._validate_model_list(data, Todo)

    def get_comments(self, post_id: Optional[int] = None) -> List[Comment]:
        """コメント取得（全体または投稿別、Pydantic検証付き）"""
        endpoint = "/comments"
        if post_id:
            endpoint += f"?postId={post_id}"
        data = self.get(endpoint)
        return self._validate_model_list(data, Comment)
```

```python
# tests/unit/test_api_client.py（Pydanticモデル検証テスト追加）
from utils.models import User, Post

@pytest.mark.integration
def test_get_user_returns_pydantic_model():
    """get_userがPydanticモデルを返すことを確認"""
    with JSONPlaceholderClient() as client:
        user = client.get_user(1)
        assert isinstance(user, User)
        assert user.id == 1
        assert "@" in user.email  # EmailStr検証

@pytest.mark.integration
def test_get_posts_returns_pydantic_models():
    """get_postsがPydanticモデルリストを返すことを確認"""
    with JSONPlaceholderClient() as client:
        posts = client.get_posts(user_id=1)
        assert all(isinstance(post, Post) for post in posts)
        assert all(post.user_id == 1 for post in posts)  # Field alias動作確認
```

**カバレッジ目標**: 19.8%（累積）
**テスト数**: 累計15件（+5件、Pydanticモデル検証含む）

**Pydantic導入効果**:
- ✅ 型安全性向上（dict → Pydanticモデル）
- ✅ 実行時検証（EmailStr、必須フィールド検証）
- ✅ Field Alias対応（userId → user_id自動変換）
- ✅ イミュータブル設計（frozen=True）

---

## Day 4 (木曜): Pydantic Settings基礎 + テスト拡充

**学習内容**（学習プラン参照）:
- Pydantic Settings: BaseSettings継承、環境変数読み込み
- ネスト設定: APIConfig、LogConfig
- .env環境変数設定

**関連ポートフォリオ作成タスク**:

### Task 1.4: Settings基礎実装（3h）

**要件**:
- Settings基礎実装（BaseSettings継承）
- APIConfig/LogConfig実装
- .env環境変数設定
- Settings統合テスト5件追加

**カバレッジ目標**: 26.4%（累積）
**テスト数**: 累計20件（+5件）

---

## Day 5 (金曜): エラーケーステスト + カバレッジ測定

**学習内容**（学習プラン参照）:
- エラーケーステスト設計概念
- カバレッジ測定方法・ツール理解
- テストカバレッジ戦略

**関連ポートフォリオ作成タスク**:

### Task 1.5: エラーケーステスト充実（3h）

**要件**:
- エラーケーステスト5件追加（invalid_user_id, connection_error, timeout_handling等）
- カバレッジ測定（pytest --cov）
- カバレッジ33.0%以上達成確認

**カバレッジ目標**: 33.0%（累積）
**テスト数**: 累計25件（+5件）

---

## Day 6 (土曜): README + pre-commit + Week 1振り返り

**学習内容**（学習プラン参照）:
- README作成概念（プロジェクト概要、セットアップ、アーキテクチャ説明）
- コード品質管理概念（ruff、pre-commit、docstring標準）
- Week 1振り返り手法（学習成果整理、つまずき分析）

**関連ポートフォリオ作成タスク**:

### Task 1.6: README + pre-commit + docstring（3h）

**要件**:
- README.md完成版作成（プロジェクト概要・セットアップ・使用例・アーキテクチャ）
- pre-commitフック導入（.pre-commit-config.yaml、pyproject.toml設定）
- docstring追加（主要クラス3個: BaseAPIClient, JSONPlaceholderClient, Settings）
- Week 1学習成果記録（daily_progress.md更新）

**カバレッジ目標**: 39.5%（累積）
**テスト数**: 累計25件

---

## Week 1 完了確認

**達成状況**:
- ✅ 25テスト達成
- ✅ カバレッジ39.5%以上
- ✅ ruff/mypy合格
- ✅ BaseAPIClient完成
- ✅ エラー階層設計完成（**APIValidationError含む5例外クラス**）
- ✅ **Pydanticモデル4種実装完成**（User/Post/Todo/Comment）
- ✅ JSONPlaceholderClient完成（**型安全版**）
- ✅ Pydantic Settings基礎完成
- ✅ README + pre-commit導入完成

**次週準備**:
- Week 2: Async基礎習得 + **AsyncAPIClientへPydanticモデル統合**
- 目標カバレッジ: 39.5% → 54.74%
- 目標テスト数: 25 → 55件

---

