# api-test-devops-portfolio プロジェクト コーディング規約

*最終更新: 2025年12月27日*

実際のコードベース（~970行のAPI実装、~450行の設定管理、~7,500行のテストコード）から抽出した**実務推奨レベル**のコーディング規約です。推測ゼロ、全て実コードに基づいています。

---

## 1. 命名規則

### 1.1 クラス名（PascalCase）

**推奨パターン**:
```python
# ✅ 良い例（実際のコード）
class APIClientError(Exception):
    """APIクライアント基底例外"""

class AsyncAPIClient:
    """非同期HTTPクライアント"""

class Environment(str, Enum):
    """実行環境の定義"""

class JSONPlaceholderClient(BaseAPIClient):
    """JSONPlaceholder API専用クライアント"""
```

**命名規則**:
- PascalCase（各単語の先頭大文字）
- 略語は大文字維持（`API`, `HTTP`, `JSON`）
- 例外クラスは`Error`サフィックス
- Enumクラスは意味を表す名詞

**❌ 非推奨**:
```python
class apiClient:           # 小文字始まり
class API_Client:          # スネークケース
class ApiClientException:  # Exception（Error推奨）
```

---

### 1.2 関数名・メソッド名（snake_case）

**推奨パターン**:
```python
# ✅ 良い例（実際のコード）
def exponential_backoff_with_jitter(attempt: int, base_delay: float) -> float:
    """指数バックオフ + 30%ジッター計算"""

async def get_user(self, user_id: int) -> dict[str, Any]:
    """特定ユーザーの非同期取得"""

def sanitize_user_content(value: str | None) -> str:
    """ユーザー生成コンテンツをサニタイズ"""

def is_development(self) -> bool:
    """開発環境判定"""
```

**命名規則**:
- snake_case（全小文字、アンダースコア区切り）
- 動詞始まり（`get`/`create`/`validate`/`is`/`has`）
- 意図が明確な説明的な名前
- プライベートメソッドは`_`プレフィックス（例: `_make_request_with_retry`）

---

### 1.3 変数名（snake_case）

**推奨パターン**:
```python
# ✅ 良い例（実際のコード）
base_url = "https://jsonplaceholder.typicode.com"
retry_count = 3
user_data = {"name": "Test User"}
sample_user_data = {...}
mock_response = MagicMock(spec=Response)
last_exception = None
```

**命名規則**:
- snake_case
- 意味を表す名詞
- 複数形は適切に使用（`results`, `users`, `tasks`）
- テストデータは`sample_`, `mock_`, `test_`プレフィックス

---

### 1.4 定数名（UPPER_SNAKE_CASE）

**推奨パターン**:
```python
# ✅ 良い例（実際のコード）
SECRET_PATTERNS = [
    r"api[_-]?key['\"]?\s*[:=]\s*['\"]([a-zA-Z0-9_\-]+)['\"]",
    r"password['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]",
]
```

**命名規則**:
- UPPER_SNAKE_CASE（全大文字、アンダースコア区切り）
- モジュールレベルの定数
- 設定値、パターン、パス定義

---

### 1.5 Enum値の命名

**推奨パターン**:
```python
# ✅ 良い例（実際のコード）
class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
```

---

## 2. コードスタイル

### 2.1 インデント・行長

**規則**:
- **4スペースインデント**（タブ禁止）
- **行長上限: 100文字**（ruff設定: `line-length = 100`）
- 長い引数リストは1行1引数

**自動検証**:
```bash
uv run ruff check .  # 100文字超過を検出
uv run ruff format . # 自動フォーマット
```

---

### 2.2 インポート順序

**推奨パターン**:
```python
# 1. 標準ライブラリ
import asyncio
from pathlib import Path
from typing import Any

# 2. サードパーティライブラリ
import httpx
import structlog
from pydantic import BaseModel

# 3. プロジェクト内モジュール
from config.settings import settings
from utils.logger import get_logger
```

**自動修正**: `uv run ruff check --fix .`

---

## 3. 型ヒント

### 3.1 型ヒント必須レベル

**規則**（mypy設定: `disallow_untyped_defs = true`）:
- **全ての関数・メソッドに型ヒント必須**
- テストコードは型ヒント不要（`disallow_untyped_defs = false`）

```python
# ✅ Python 3.10+ Union記法
def __init__(
    self,
    base_url: str | None = None,
    timeout: float | None = None,
) -> None:
    """コンストラクタ"""
```

**自動検証**: `uv run mypy utils/ config/ models/`

---

## 4. docstring規約

### 4.1 docstring形式

```python
def exponential_backoff_with_jitter(
    attempt: int,
    base_delay: float = 1.0,
) -> float:
    """指数バックオフ + 30%ジッター計算

    Args:
        attempt: 現在のリトライ回数（0始まり）
        base_delay: 基本遅延時間（秒）

    Returns:
        計算された遅延時間（秒、最小0.1秒）
    """
```

**規則**:
- 全ての公開クラス・関数にdocstring必須
- 1行目: 簡潔な概要（日本語OK）
- Args/Returns/Raises明記

---

## 5. エラーハンドリング

### 5.1 例外設計パターン

```python
class APIClientError(Exception):
    """APIクライアント基底例外"""

class APIHTTPError(APIClientError):
    """HTTPステータスエラー"""
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code
```

**規則**:
- 階層的な例外設計（基底例外 + 派生例外）
- `from e`で例外チェーン維持
- 4xxは即失敗、5xxはリトライ

---

## 6. 非同期処理

### 6.1 async/awaitパターン

```python
async def get_user_data(self, user_id: int) -> dict[str, Any]:
    """ユーザー関連データを並行取得"""
    user, posts, todos = await asyncio.gather(
        self.get_user(user_id),
        self.get_posts(user_id=user_id),
        self.get_todos(user_id=user_id),
    )
    return {"user": user, "posts": posts, "todos": todos}
```

**規則**:
- `asyncio.gather()`で複数タスク並行実行
- `async with`でリソース自動管理

---

## 7. テスト規約

### 7.1 テスト命名規則

```python
@pytest.mark.asyncio
async def test_async_get_user(sample_user_data, mock_response):
    """非同期APIクライアントの基本的なGETリクエストをテスト"""
```

**規則**:
- `test_`プレフィックス必須
- 意図が明確な説明的な名前

### 7.2 フィクスチャ設計

```python
@pytest.fixture
def sample_user_data() -> dict[str, Any]:
    """テスト用ユーザーデータ"""
    return {"id": 1, "name": "Test User"}

@pytest.fixture
def todo_data_factory():
    """TODOテストデータファクトリー"""
    def create_todo(user_id: int = 1, **kwargs) -> dict:
        return {"userId": user_id, **kwargs}
    return create_todo
```

### 7.3 カバレッジ目標

**現状** (2025-12-26):
- 現在カバレッジ: ~65-70%
- 目標カバレッジ: 85%

**測定コマンド**:
```bash
uv run pytest --cov=utils --cov=config --cov=models --cov-fail-under=85
uv run pytest --cov-report=html  # HTMLレポート
```

---

## 8. コメント規約

### 8.1 日本語/英語の使い分け

**規則**:
- **docstring**: 日本語推奨（学習プロジェクト）
- **インラインコメント**: 日本語で実装意図説明
- **変数・関数名**: 英語必須

---

## 9. 自動検証コマンド

### 9.1 リンター・フォーマッター

```bash
# Ruff（統合ツール）
uv run ruff check --fix .    # 自動修正付きチェック
uv run ruff format .          # フォーマット適用
```

### 9.2 型チェック

```bash
uv run mypy utils/ config/ models/    # 型チェック
```

### 9.3 セキュリティスキャン

```bash
uv run bandit -r utils/ config/ models/  # セキュリティスキャン
gitleaks detect --source .       # シークレット検出
# 依存関係脆弱性: Dependabot週次チェックで対応
```

### 9.4 pre-commit（軽量版）

```bash
uv run pre-commit install  # 初回のみ
```

**戦略**: コミット時はruffのみ（3秒以内）、重いチェックはCI/CDで実行

---

## 10. プロジェクト固有の規約

### 10.1 設定管理パターン

```python
from config.settings import settings

# API設定アクセス
base_url = settings.api.base_url
timeout = settings.api.timeout

# 環境判定
if settings.is_development():
    pass
```

### 10.2 ログ出力パターン（structlog統合）

**推奨パターン**:
```python
# ✅ 良い例（実際のコード: utils/logger.py使用）
from utils.logger import get_logger

logger = get_logger(__name__)

# 構造化ログ出力
logger.info("処理開始", user_id=123, action="login")
logger.warning("リトライ実行", attempt=2, endpoint="/users")
logger.error("API呼び出し失敗", status_code=500, error=str(e))
```

**特徴**:
- **structlog統合**: FilteringBoundLogger（型安全）
- **環境別フォーマット**: console（開発）/json（本番）
- **Sentry連携**: ERROR以上を自動送信
- **キーワード引数**: コンテキスト情報を構造化

**❌ 非推奨**:
```python
# 旧パターン（stdlibのlogging直接使用）
import logging
logger = logging.getLogger(__name__)
logger.info(f"処理開始: user_id={user_id}")  # f-string埋め込み
```

### 10.3 セキュリティパターン

```python
# XSSサニタイズ
from models.responses import sanitize_user_content

clean_input = sanitize_user_content(user_input)

# シークレット管理
from pydantic import SecretStr

class Config(BaseModel):
    api_key: SecretStr | None = None
```

---

## 11. 品質保証フロー

### 開発フロー

```
1. コード実装
   ↓
2. uv run ruff format .
   ↓
3. uv run ruff check --fix .
   ↓
4. uv run mypy utils/ config/ models/
   ↓
5. uv run pytest --cov-fail-under=85
   ↓
6. git commit（pre-commit自動実行）
```

### CI/CD（GitHub Actions）

- ruff + mypy + pytest + bandit + gitleaks + Dependabot
- カバレッジ85%未満でビルド失敗

---

## 参考リソース

- **Ruff**: https://docs.astral.sh/ruff/
- **mypy**: https://mypy.readthedocs.io/
- **pytest**: https://docs.pytest.org/
- **structlog**: https://www.structlog.org/
- **Pydantic**: https://docs.pydantic.dev/

---

このコーディング規約は、実際のコードベース（合計~8,900行）から抽出した**実務推奨パターン**です。
