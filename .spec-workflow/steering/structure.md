# Project Structure Steering Document

*最終更新: 2026年01月02日*

## ディレクトリ構成

```
api-test-devops-portfolio/
├── .spec-workflow/           # Spec Workflow MCP
│   ├── steering/             # Steering documents
│   │   ├── product.md        # プロダクトビジョン
│   │   ├── tech.md           # 技術スタック
│   │   └── structure.md      # 本ファイル
│   ├── templates/            # Specテンプレート
│   └── user-templates/       # カスタムテンプレート
├── config/                   # 設定管理
│   └── settings.py           # Pydantic Settings
├── utils/                    # ユーティリティ
│   ├── api_client.py         # HTTPクライアント（Sync/Async）
│   ├── logger.py             # structlog設定
│   ├── sentry_init.py        # Sentry統合
│   └── core/                 # コアモジュール
├── models/                   # Pydanticモデル（新規）
├── monitoring/               # 監視・メトリクス（新規）
├── tests/                    # テストスイート（442テスト）
│   ├── conftest.py           # pytest共通設定
│   ├── unit/                 # 単体テスト
│   ├── integration/          # 統合テスト
│   ├── e2e/                  # E2Eテスト
│   └── performance/          # パフォーマンステスト
├── docs/                     # ドキュメント
│   ├── progress/             # 学習進捗管理
│   │   ├── daily_progress.md
│   │   └── progress_state.yaml
│   └── main/                 # メインドキュメント
│       └── 6週プラン/         # 6週プラン（38日間、260H）
├── reports/                  # レポート
│   ├── htmlcov/              # カバレッジHTML
│   └── coverage.xml          # カバレッジXML
├── .github/workflows/        # CI/CD（実装済み）
│   └── ci.yml                # 4-Tier Test Pyramid
├── pyproject.toml            # プロジェクト設定
├── uv.lock                   # 依存関係ロック
├── CLAUDE.md                 # Claude Code指示
└── README.md                 # プロジェクト概要
```

---

## ファイル命名規則

### Pythonファイル
- **モジュール**: snake_case.py
- **テスト**: test_*.py または *_test.py
- **パッケージ**: __init__.py必須

### 設定ファイル
- **環境変数**: .env（git除外）, .env.example
- **YAML**: snake_case.yaml

### ドキュメント
- **Markdown**: PascalCase.md または snake_case.md
- **日本語ファイル名**: 可（学習ドキュメントのみ）

---

## コーディング規約

### 命名規則

| 対象 | スタイル | 例 | 備考 |
|------|---------|-----|------|
| モジュール | snake_case | api_client.py | 短く、ハイフン禁止 |
| パッケージ | snake_case | utils/ | 短く、アンダースコア最小限 |
| クラス | PascalCase | BaseAPIClient | 略語は全て大文字（HTTPClient） |
| 関数 | snake_case | get_user() | 動詞で開始 |
| 変数 | snake_case | base_url | 説明的な名前 |
| 定数 | UPPER_SNAKE_CASE | MAX_RETRIES | モジュールレベル |
| プライベート | _prefix | _internal_method() | 単一アンダースコア |
| 特殊（マングリング） | __prefix | __private_attr | 二重アンダースコア（稀） |

**命名の原則**:
- 説明的で曖昧性のない名前を使用
- 略語は避ける（確立された記法は可: HTTP, API, URL）
- 長すぎる名前（50文字以上）は型エイリアスで短縮検討

---

### コードフォーマット規則

#### 行長制限（PEP 8準拠）
```python
MAX_LINE_LENGTH = 79        # コード
MAX_COMMENT_LENGTH = 72     # コメント・docstring

# ✅ 推奨: 長い行は演算子の前で改行
total = (
    first_variable
    + second_variable
    - third_variable
)

# 関数呼び出しの改行
result = some_function(
    argument_one,
    argument_two,
    keyword_argument=value,
)
```

#### 空白ルール（PEP 8準拠）
```python
# ✅ 正しい
spam(ham[1], {eggs: 2})
foo = (0,)
x, y = 1, 2

# ❌ 誤り
spam( ham[ 1 ], { eggs: 2 } )  # 括弧内に不要な空白
foo = (0, )                     # タプル末尾の余分な空白
x , y = 1 , 2                   # カンマ前の不要な空白

# ✅ 演算子の空白
i = i + 1
submitted += 1
x = x*2 - 1
hypot2 = x*x + y*y
c = (a+b) * (a-b)

# ✅ キーワード引数の空白なし
def complex(real, imag=0.0):
    return magic(r=real, i=imag)
```

#### インデントとブロック
```python
# ✅ 推奨: 4スペースインデント
def long_function_name(
    var_one: str,
    var_two: int,
    var_three: dict[str, Any],
) -> list[str]:
    """関数の説明。"""
    print(var_one)
    return []

# ✅ 推奨: トップレベル定義間は2行空白
class FirstClass:
    """最初のクラス。"""
    pass


class SecondClass:
    """2番目のクラス。"""
    pass


# ✅ 推奨: メソッド間は1行空白
class MyClass:
    """サンプルクラス。"""

    def first_method(self) -> None:
        """最初のメソッド。"""
        pass

    def second_method(self) -> None:
        """2番目のメソッド。"""
        pass
```

---

### インポート順序（ruff isort準拠）

**基本ルール**:
- ファイル先頭（docstringの後）に配置
- グループ間は1行空白
- 各グループ内はアルファベット順

```python
"""モジュールの説明。"""

# 1. Future imports
from __future__ import annotations

# 2. Standard library
import asyncio
import json
from collections.abc import Sequence
from typing import Any

# 3. Third-party
import httpx
from pydantic import BaseModel, Field

# 4. First-party
from config.settings import settings
from utils.api_client import BaseAPIClient

# 5. Local-folder（パッケージ内相対インポート）
from .core import validate_response
```

**インポート詳細ルール**:
```python
# ✅ 推奨: 標準的なインポート
import module_name
from package import specific_item

# ✅ 許容: 名前衝突回避の as 使用
from typing import Set as TypingSet
from collections.abc import Set as AbstractSet

# ✅ 許容: 長い名前の短縮
from some.very.long.module.name import VeryLongClassName as VLCN

# ⚠️ 注意: 複数インポートは読みやすさ優先
from typing import (  # 3個以上は改行推奨
    Any,
    Callable,
    Sequence,
)

# ❌ 禁止: ワイルドカードインポート
from module import *  # 名前空間汚染

# ❌ 禁止: 不要な相対インポート
from ..parent import something  # パッケージ内部のみ許容
```

---

### 型ヒント規約（Python 3.10+ / PEP 484準拠）

**適用ルール（実務推奨）**:
- **公開API（public）**: 型ヒント必須
- **内部実装（_prefix）**: 型ヒント推奨
- **単純なヘルパー関数**: 型ヒント任意（明確な場合）

#### 基本的な型ヒント
```python
# ✅ 推奨: Python 3.10+ Union記法（| 使用）
def get_user(user_id: int) -> dict[str, Any] | None:
    """ユーザー情報を取得する。"""
    ...

# ✅ 推奨: 組み込み型の直接使用（list, dict, set, tuple）
def process_items(items: list[str]) -> dict[str, int]:
    """アイテムを処理する。"""
    return {item: len(item) for item in items}

# ❌ 非推奨: 古い Optional 記法（Python 3.10+では | None を使用）
def find_user(user_id: int) -> Optional[dict[str, Any]]:
    """Optional は古い記法、3.10+ では | None を推奨。"""
    ...
```

#### 複雑な型の扱い
```python
# ✅ 推奨: 型エイリアスで可読性向上
UserData = dict[str, str | int | list[str]]
ResponseData = dict[str, Any]

def process_users(users: list[UserData]) -> ResponseData:
    """複数ユーザーを処理する。"""
    ...

# ✅ 推奨: Callable 型ヒント
from collections.abc import Callable

def apply_function(
    func: Callable[[int, int], int],
    x: int,
    y: int,
) -> int:
    """関数を適用する。"""
    return func(x, y)

# ⚠️ Any の使用は理由をコメント
def handle_legacy_api(response: Any) -> dict[str, Any]:
    """レガシーAPI対応（型定義なし）のため Any 使用。

    Note:
        将来的に TypedDict で型定義を追加予定。
    """
    ...
```

#### 型ヒントのベストプラクティス
```python
# ✅ 推奨: TypedDict で辞書の型を明確化
from typing import TypedDict

class UserDict(TypedDict):
    """ユーザー情報の型定義。"""
    id: int
    name: str
    email: str

def create_user(data: UserDict) -> UserDict:
    """ユーザーを作成する。"""
    return data

# ✅ 推奨: Literal で有効な値を制限
from typing import Literal

Environment = Literal["development", "staging", "production"]

def configure(env: Environment) -> None:
    """環境を設定する。"""
    ...

# ✅ 推奨: Protocol で構造的部分型（ダックタイピング）
from typing import Protocol

class Closeable(Protocol):
    """close メソッドを持つオブジェクト。"""
    def close(self) -> None: ...

def close_resource(resource: Closeable) -> None:
    """リソースをクローズする。"""
    resource.close()
```

---

### 関数パラメータのベストプラクティス

#### Mutable Defaults の回避（重要）
```python
# ✅ 推奨: None をデフォルトに使用
def append_to_list(
    item: str,
    target: list[str] | None = None,
) -> list[str]:
    """リストに要素を追加する。

    Args:
        item: 追加する要素
        target: 追加先リスト（None の場合新規作成）

    Returns:
        更新されたリスト
    """
    if target is None:
        target = []
    target.append(item)
    return target

# ❌ 禁止: Mutable デフォルト引数
def append_to_list(
    item: str,
    target: list[str] = [],  # 危険: 全呼び出しで同じリストを共有
) -> list[str]:
    """バグの原因となる実装。"""
    target.append(item)
    return target
```

#### キーワード専用引数の活用
```python
# ✅ 推奨: * でキーワード専用引数を明示
def create_connection(
    host: str,
    port: int,
    *,
    timeout: float = 30.0,
    ssl: bool = True,
) -> Connection:
    """接続を作成する。

    Args:
        host: ホスト名
        port: ポート番号
        timeout: タイムアウト（秒）
        ssl: SSL使用フラグ

    Returns:
        接続オブジェクト

    Note:
        timeout と ssl はキーワード専用引数。
    """
    ...

# 呼び出し例
conn = create_connection("localhost", 8080, timeout=60.0, ssl=False)
```

---

### Docstring規約（Google Style / 実務推奨）

**適用ルール**:
- **公開API（public）**: docstring 必須、Example セクション推奨
- **複雑なロジック**: docstring 必須、Example セクション必須
- **単純な内部関数**: docstring 任意（1行要約のみも可）

#### 完全なDocstring（公開API / 複雑なロジック）
```python
def calculate_discount(
    price: float,
    discount_rate: float,
    *,
    min_price: float = 0.0,
    apply_tax: bool = True,
) -> float:
    """価格から割引を計算する。

    割引適用後の価格を計算し、オプションで税金を適用する。
    最低価格を下回る場合は最低価格を返す。

    Args:
        price: 元の価格（正の数）
        discount_rate: 割引率（0.0～1.0）
        min_price: 最低価格（デフォルト: 0.0）
        apply_tax: 税金適用フラグ（デフォルト: True）

    Returns:
        割引適用後の価格

    Raises:
        ValueError: price が負の場合
        ValueError: discount_rate が 0.0～1.0 の範囲外の場合

    Example:
        >>> calculate_discount(1000, 0.2)
        800.0
        >>> calculate_discount(1000, 0.2, min_price=850.0)
        850.0

    Note:
        税率は config.settings.TAX_RATE から取得される。
    """
    if price < 0:
        raise ValueError("価格は正の数である必要があります")
    if not 0.0 <= discount_rate <= 1.0:
        raise ValueError("割引率は 0.0～1.0 の範囲である必要があります")

    result = price * (1 - discount_rate)
    if apply_tax:
        result *= (1 + settings.TAX_RATE)
    return max(result, min_price)
```

#### 簡略版Docstring（単純な関数）
```python
def add_numbers(a: int, b: int) -> int:
    """2つの数値を加算する。"""
    return a + b

def _internal_helper(data: list[str]) -> int:
    """内部ヘルパー関数: データ件数を返す。"""
    return len(data)
```

#### クラスのDocstring
```python
class APIClient:
    """外部APIとの通信を管理するクライアント。

    このクラスはHTTPリクエストの送信、リトライロジック、
    エラーハンドリングを提供する。

    Attributes:
        base_url: APIのベースURL
        timeout: リクエストタイムアウト（秒）
        retry_count: リトライ回数

    Example:
        >>> client = APIClient("https://api.example.com")
        >>> response = client.get("/users/1")
        >>> print(response["name"])
        "John Doe"

    Note:
        非同期版は AsyncAPIClient を使用すること。
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        retry_count: int = 3,
    ) -> None:
        """APIクライアントを初期化する。

        Args:
            base_url: APIのベースURL
            timeout: リクエストタイムアウト（秒）
            retry_count: リトライ回数
        """
        self.base_url = base_url
        self.timeout = timeout
        self.retry_count = retry_count
```

### エラーハンドリング階層
```python
APIClientError               # 基底例外
├── APIConnectionError       # 接続エラー
├── APITimeoutError          # タイムアウト
├── APIHTTPError             # HTTPエラー
│   ├── APIClientHTTPError   # 4xxエラー
│   └── APIServerHTTPError   # 5xxエラー
└── APIRetryError            # リトライ上限
```

---

## Repository Patternアーキテクチャ（実務推奨4層構成）

### アーキテクチャ概要

**目的**: ビジネスロジックとインフラ実装の分離、テスタビリティ・保守性・拡張性向上

**採用パターン**: DDD/クリーンアーキテクチャの4層構成

```
utils/
├── domain/                  # ドメイン層（エンティティ・ビジネスルール）
│   ├── __init__.py
│   ├── models.py           # User, Todo等のエンティティ
│   ├── value_objects.py    # Email, UserId等の値オブジェクト
│   └── exceptions.py       # ドメイン固有例外（UserNotFoundException等）
├── services/                # サービス層（ユースケース・ビジネスロジック）
│   ├── __init__.py
│   ├── user_service.py     # ユーザー関連ビジネスロジック
│   └── todo_service.py     # Todo関連ビジネスロジック
├── repositories/            # リポジトリ層（データアクセス抽象化）
│   ├── __init__.py
│   ├── interfaces.py       # リポジトリインターフェース（抽象基底クラス）
│   ├── user_repository.py  # ユーザーリポジトリ実装
│   └── todo_repository.py  # Todoリポジトリ実装
└── infrastructure/          # インフラ層（技術実装詳細）
    ├── __init__.py
    ├── api_client.py       # 既存APIクライアント（リファクタリング対象）
    ├── http_client.py      # HTTP通信の低レベル実装
    └── cache.py            # キャッシュ実装（オプション）
```

### 各層の責務と依存関係

| 層 | 責務 | 依存方向 | 例 |
|----|------|---------|-----|
| **Domain** | エンティティ・ドメインルール | なし（最内層） | User, Email, is_valid_email() |
| **Service** | ユースケース・ビジネスロジック | Domain, Repository | get_user_with_validation() |
| **Repository** | データアクセス抽象化 | Domain | get_by_id(), save() |
| **Infrastructure** | 技術実装詳細 | なし（最外層） | httpx, DB接続 |

**依存関係ルール（Dependency Rule）**:
- 内側の層は外側の層を知らない（Domain → Service → Repository → Infrastructure）
- 外側の層は内側の層に依存可能
- インターフェース（抽象）を介して依存を逆転（Dependency Inversion Principle）

---

### 1. Domain層（ドメイン層）

**責務**: ビジネスルール・ドメインロジック
**依存関係**: なし（他層に依存しない、最も安定した層）

#### エンティティ定義

```python
# utils/domain/models.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class User:
    """ユーザーエンティティ。

    ビジネスルールを持つドメインオブジェクト。
    インフラストラクチャ（API、DB）に依存しない。

    Attributes:
        id: ユーザーID
        name: ユーザー名
        email: メールアドレス
    """
    id: int
    name: str
    email: str

    def is_valid_email(self) -> bool:
        """メールアドレスの妥当性検証（ビジネスルール）。

        Returns:
            妥当な場合True、そうでない場合False
        """
        return "@" in self.email and "." in self.email.split("@")[1]

    def __post_init__(self) -> None:
        """初期化後のバリデーション。

        Raises:
            ValueError: IDが負の場合
        """
        if self.id <= 0:
            raise ValueError(f"User ID must be positive: {self.id}")

@dataclass
class Todo:
    """Todoエンティティ。

    Attributes:
        id: Todo ID
        user_id: 所有ユーザーID
        title: タイトル
        completed: 完了フラグ
    """
    id: int
    user_id: int
    title: str
    completed: bool

    def mark_as_completed(self) -> None:
        """Todoを完了状態にする（ビジネスロジック）。"""
        self.completed = True
```

#### ドメイン例外定義

```python
# utils/domain/exceptions.py
class DomainException(Exception):
    """ドメイン層の基底例外。

    ビジネスルール違反やドメインエラーを表現する。
    インフラ層の例外をラップして、技術的詳細を隠蔽する。
    """
    pass

class UserNotFoundException(DomainException):
    """ユーザーが存在しない場合の例外。

    Attributes:
        user_id: 存在しないユーザーのID
    """
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(f"User not found: {user_id}")

class RepositoryAccessError(DomainException):
    """リポジトリアクセス時のインフラ例外をラップ。

    ネットワークエラー、タイムアウト等のインフラ例外を
    ドメイン層の例外に変換し、Service層がInfrastructure層の
    詳細を知らなくて済むようにする。

    Attributes:
        original_error: 元のインフラ例外
    """
    def __init__(self, message: str, original_error: Exception | None = None):
        self.original_error = original_error
        super().__init__(message)
```

#### 値オブジェクト定義（オプション）

```python
# utils/domain/value_objects.py
from dataclasses import dataclass
import re

@dataclass(frozen=True)
class Email:
    """メールアドレス値オブジェクト。

    RFC 5322準拠の実務的なメールアドレス検証を実施。
    完全なRFC 5322準拠は複雑すぎるため、実務で使用される99%のケースをカバー。
    不変（immutable）で、ビジネスルールを内包する。

    Attributes:
        value: メールアドレス文字列

    Raises:
        ValueError: メールアドレスが不正な場合

    Example:
        >>> email = Email("user@example.com")
        >>> email.value
        'user@example.com'
        >>> email = Email("user+tag@example.com")  # RFC 5322特殊文字対応
        >>> Email("invalid")  # ValueError発生

    参考:
        RFC 5322 (Internet Message Format): https://tools.ietf.org/html/rfc5322#section-3.4.1
        RFC 5321 (SMTP): https://tools.ietf.org/html/rfc5321#section-4.5.3.1
    """
    value: str

    # RFC 5322準拠（実務的簡易版、99%カバレッジ）
    # 許可される特殊文字: !#$%&'*+/=?^_`{|}~-
    # ドメイン部: 63文字以内のラベル、ハイフンは先頭・末尾不可
    _EMAIL_PATTERN = re.compile(
        r"^[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+)*"
        r"@(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$"
    )

    def __post_init__(self) -> None:
        """初期化後のバリデーション。

        Raises:
            ValueError: メールアドレスが不正な場合（RFC 5322/5321違反）
        """
        if not self._EMAIL_PATTERN.match(self.value):
            raise ValueError(f"Invalid email format (RFC 5322): {self.value}")

        # 追加ビジネスルール: メールアドレス長制限（RFC 5321: 最大254文字）
        if len(self.value) > 254:
            raise ValueError(f"Email address too long (RFC 5321 limit: 254 chars): {self.value}")
```

#### リポジトリインターフェース定義

```python
# utils/repositories/interfaces.py
from abc import ABC, abstractmethod
from typing import Optional
from utils.domain.models import User, Todo

class UserRepositoryInterface(ABC):
    """ユーザーリポジトリのインターフェース。

    抽象化により、インフラ層の実装を隠蔽する。
    テスト時はモック実装に差し替え可能。
    """

    @abstractmethod
    async def get_by_id(self, user_id: int) -> Optional[User]:
        """ユーザーIDでユーザーを取得する。

        Args:
            user_id: ユーザーID

        Returns:
            ユーザーエンティティ、存在しない場合はNone
        """
        pass

    @abstractmethod
    async def list_users(self) -> list[User]:
        """全ユーザーを取得する。

        Returns:
            ユーザーエンティティのリスト
        """
        pass

class TodoRepositoryInterface(ABC):
    """Todoリポジトリのインターフェース。"""

    @abstractmethod
    async def get_by_user_id(self, user_id: int) -> list[Todo]:
        """ユーザーIDでTodo一覧を取得する。

        Args:
            user_id: ユーザーID

        Returns:
            Todoエンティティのリスト
        """
        pass
```

---

### 2. Service層（サービス層）

**責務**: ユースケース・ビジネスロジック・複数Repository組み合わせ
**依存関係**: Domain層、Repositoryインターフェース

#### シンプルなService（単一Repository）

```python
# utils/services/user_service.py
from typing import Optional
from utils.domain.models import User
from utils.repositories.interfaces import UserRepositoryInterface

class UserService:
    """ユーザー関連ビジネスロジック。

    単一Repositoryを使用する場合でも、Service層を経由することで：
    - ビジネスルールの適用場所が明確
    - 将来的な拡張が容易（キャッシュ、ログ、通知等）
    - テスト時のモック対象が統一
    """

    def __init__(self, user_repository: UserRepositoryInterface):
        """Serviceを初期化する。

        Args:
            user_repository: ユーザーリポジトリ（抽象）
        """
        self._user_repository = user_repository

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """ユーザーIDでユーザーを取得する（ビジネスルール適用）。

        Args:
            user_id: ユーザーID

        Returns:
            ユーザーエンティティ、存在しない場合はNone

        Raises:
            ValueError: user_idが無効な場合
        """
        # ビジネスルール: IDは正の整数
        if user_id <= 0:
            raise ValueError(f"Invalid user_id: {user_id}")

        user = await self._user_repository.get_by_id(user_id)

        # ビジネスルール: メールアドレス検証
        if user and not user.is_valid_email():
            # 将来的な拡張例: ログ記録、監視メトリクス送信等
            pass

        return user

    async def list_all_users(self) -> list[User]:
        """全ユーザーを取得する。

        Returns:
            ユーザーエンティティのリスト
        """
        return await self._user_repository.list_users()
```

#### 複雑なService（複数Repository組み合わせ + エラーハンドリング）

```python
# utils/services/todo_service.py
from utils.domain.models import User, Todo
from utils.repositories.interfaces import UserRepositoryInterface, TodoRepositoryInterface
from utils.domain.exceptions import UserNotFoundException, RepositoryAccessError

class TodoService:
    """Todo関連ビジネスロジック。

    複数Repositoryを組み合わせるユースケースを実装。
    Service層がないと、この種のロジックの置き場所が不明確になる。

    エラーハンドリング戦略（Clean Architecture準拠）:
    - ビジネス例外（UserNotFoundException等）はそのまま伝播
    - インフラ例外（httpx.RequestError等）はRepository層でRepositoryAccessErrorに変換済み
    - Service層はドメイン例外のみ扱う（Infrastructure層の詳細を知らない）

    依存関係ルール遵守:
    - Service層 → Domain層（✅ インターフェース依存）
    - Service層 → Infrastructure層（❌ 直接依存なし）
    - Repository層がInfrastructure例外を吸収するため、Service層での例外変換不要
    """

    def __init__(
        self,
        user_repository: UserRepositoryInterface,
        todo_repository: TodoRepositoryInterface,
    ):
        """Serviceを初期化する。

        Args:
            user_repository: ユーザーリポジトリ
            todo_repository: Todoリポジトリ
        """
        self._user_repository = user_repository
        self._todo_repository = todo_repository

    async def get_user_todos_with_validation(
        self,
        user_id: int,
        *,
        include_completed: bool = False,
    ) -> list[Todo]:
        """ユーザーのTodo一覧を取得（ユーザー存在確認付き）。

        Args:
            user_id: ユーザーID
            include_completed: 完了済みTodoを含めるか

        Returns:
            Todoリスト

        Raises:
            UserNotFoundException: ユーザーが存在しない場合
            RepositoryAccessError: データアクセスエラー（Repository層で変換済み）
            ValueError: user_idが無効な場合

        Note:
            Repository層がhttpx例外をRepositoryAccessErrorに変換するため、
            Service層でのInfrastructure例外キャッチは不要。
            これによりClean Architectureの依存関係ルールを遵守。
        """
        # 入力検証（ビジネスルール）
        if user_id <= 0:
            raise ValueError(f"Invalid user_id: {user_id}")

        # 複数Repositoryの組み合わせ
        # Repository層がInfrastructure例外を自動変換するため、
        # ここではドメイン例外のみ発生する
        user = await self._user_repository.get_by_id(user_id)
        if not user:
            raise UserNotFoundException(user_id)

        todos = await self._todo_repository.get_by_user_id(user_id)

        # ビジネスロジック: 完了済みTodoのフィルタリング
        if not include_completed:
            todos = [todo for todo in todos if not todo.completed]

        return todos
```

---

### 3. Repository層（リポジトリ層）

**責務**: データアクセスの抽象化、**Infrastructure層例外のドメイン例外への変換**
**依存関係**: Domain層（エンティティを返す）、Infrastructure層（具体的実装）

#### Repository層エラー変換標準化（Major課題M3対応）

Repository層では、Infrastructure層の技術的例外（httpx.RequestError等）をドメイン例外（RepositoryAccessError）に変換し、Service層がInfrastructure層の詳細を意識しないようにします。

```python
# utils/repositories/user_repository.py（エラー変換標準化版）
from typing import Optional
import structlog
import httpx

from utils.domain.models import User
from utils.domain.exceptions import RepositoryAccessError
from utils.repositories.interfaces import UserRepositoryInterface
from utils.infrastructure.api_client import JSONPlaceholderClient

logger = structlog.get_logger()

class UserRepository(UserRepositoryInterface):
    """ユーザーリポジトリ実装（エラー変換標準化版）。

    Infrastructure層の例外を全てドメイン例外に変換し、
    Service層がhttpxの詳細を意識しないようにする。
    """

    def __init__(self, api_client: JSONPlaceholderClient):
        """リポジトリを初期化する。

        Args:
            api_client: インフラ層のAPIクライアント
        """
        self._api_client = api_client

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """ユーザーIDでユーザーを取得する。

        Args:
            user_id: ユーザーID

        Returns:
            ユーザーエンティティ、存在しない場合はNone

        Raises:
            RepositoryAccessError: データアクセスエラー
                - ネットワークエラー（httpx.RequestError）
                - HTTPエラー（httpx.HTTPStatusError、404以外）
                - データ変換エラー（KeyError/ValueError）

        エラー変換戦略:
        1. 404 Not Found → None返却（正常系: ユーザーが存在しない）
        2. その他のHTTPエラー → RepositoryAccessError
        3. ネットワークエラー → RepositoryAccessError
        4. データ変換エラー → RepositoryAccessError
        """
        try:
            # インフラ層からデータ取得
            data = await self._api_client.get_user(user_id)
            if not data:
                return None

            # インフラ層のレスポンス（dict）をドメインエンティティに変換
            return User(
                id=data["id"],
                name=data["name"],
                email=data["email"],
            )

        except httpx.HTTPStatusError as e:
            # 404 Not Found: ユーザーが存在しない（正常系）
            if e.response.status_code == 404:
                logger.info(
                    "user_not_found",
                    user_id=user_id,
                    status_code=404,
                )
                return None

            # その他のHTTPエラー: RepositoryAccessErrorにラップ
            logger.error(
                "http_error_in_repository",
                user_id=user_id,
                status_code=e.response.status_code,
                error=str(e),
            )
            raise RepositoryAccessError(
                f"HTTP error ({e.response.status_code}) while fetching user {user_id}",
                original_error=e,
            ) from e

        except httpx.RequestError as e:
            # ネットワークエラー（タイムアウト、接続エラー等）
            logger.error(
                "network_error_in_repository",
                user_id=user_id,
                error_type=type(e).__name__,
                error=str(e),
            )
            raise RepositoryAccessError(
                f"Network error while fetching user {user_id}: {type(e).__name__}",
                original_error=e,
            ) from e

        except (KeyError, ValueError, TypeError) as e:
            # データ変換エラー（APIレスポンス構造が期待と異なる）
            logger.error(
                "data_transformation_error_in_repository",
                user_id=user_id,
                error_type=type(e).__name__,
                error=str(e),
            )
            raise RepositoryAccessError(
                f"Data transformation error for user {user_id}: {type(e).__name__}",
                original_error=e,
            ) from e

    async def list_users(self) -> list[User]:
        """全ユーザーを取得する。

        Returns:
            ユーザーエンティティのリスト

        Raises:
            RepositoryAccessError: データアクセスエラー
        """
        try:
            data_list = await self._api_client.get_users()
            return [
                User(id=d["id"], name=d["name"], email=d["email"])
                for d in data_list
            ]

        except httpx.HTTPStatusError as e:
            logger.error(
                "http_error_in_repository",
                operation="list_users",
                status_code=e.response.status_code,
                error=str(e),
            )
            raise RepositoryAccessError(
                f"HTTP error ({e.response.status_code}) while listing users",
                original_error=e,
            ) from e

        except httpx.RequestError as e:
            logger.error(
                "network_error_in_repository",
                operation="list_users",
                error_type=type(e).__name__,
                error=str(e),
            )
            raise RepositoryAccessError(
                f"Network error while listing users: {type(e).__name__}",
                original_error=e,
            ) from e

        except (KeyError, ValueError, TypeError) as e:
            logger.error(
                "data_transformation_error_in_repository",
                operation="list_users",
                error_type=type(e).__name__,
                error=str(e),
            )
            raise RepositoryAccessError(
                f"Data transformation error while listing users: {type(e).__name__}",
                original_error=e,
            ) from e

    async def create(self, user: User) -> User:
        """ユーザーを作成する。

        Args:
            user: 作成するユーザーエンティティ

        Returns:
            作成されたユーザーエンティティ

        Raises:
            RepositoryAccessError: データアクセスエラー
        """
        try:
            data = await self._api_client.create_user({
                "name": user.name,
                "email": user.email,
            })
            return User(
                id=data["id"],
                name=data["name"],
                email=data["email"],
            )

        except httpx.HTTPStatusError as e:
            logger.error(
                "http_error_in_repository",
                operation="create_user",
                user_email=user.email,
                status_code=e.response.status_code,
                error=str(e),
            )
            raise RepositoryAccessError(
                f"HTTP error ({e.response.status_code}) while creating user",
                original_error=e,
            ) from e

        except httpx.RequestError as e:
            logger.error(
                "network_error_in_repository",
                operation="create_user",
                user_email=user.email,
                error_type=type(e).__name__,
                error=str(e),
            )
            raise RepositoryAccessError(
                f"Network error while creating user: {type(e).__name__}",
                original_error=e,
            ) from e

        except (KeyError, ValueError, TypeError) as e:
            logger.error(
                "data_transformation_error_in_repository",
                operation="create_user",
                user_email=user.email,
                error_type=type(e).__name__,
                error=str(e),
            )
            raise RepositoryAccessError(
                f"Data transformation error while creating user: {type(e).__name__}",
                original_error=e,
            ) from e
```

**エラー変換の実務ポイント**:

1. **Infrastructure層例外の完全隠蔽**:
   - Service層はhttpx.RequestError/HTTPStatusErrorを知らない
   - ドメイン例外（RepositoryAccessError）のみを扱う

2. **404 Not Foundの特別扱い**:
   - ユーザーが存在しない = 正常系 → None返却
   - その他のHTTPエラー = 異常系 → RepositoryAccessError

3. **original_error保持**:
   - デバッグ・調査用に元の例外を保持
   - ログ出力で詳細情報を記録

4. **構造化ログ（structlog）**:
   - エラー種別ごとにログイベント識別
   - user_id、operation、error_typeで検索・分析可能

5. **一貫性**:
   - 全Repositoryメソッド（get/list/create/update/delete）で同じパターン
   - 他のRepository（TodoRepository等）も同様に実装

6. **テスタビリティ**:
   - Infrastructure層をモック化すれば、エラー変換ロジックを独立テスト可能
   - 各エラーパターン（404、500、ネットワークエラー等）を網羅的にテスト

**Service層での使用例**:
```python
# utils/services/user_service.py
from utils.domain.exceptions import UserNotFoundException, RepositoryAccessError

async def get_user_by_id(self, user_id: int) -> User:
    """ユーザーをIDで取得する。

    Service層はInfrastructure層（httpx）の詳細を意識しない。
    ドメイン例外のみをキャッチする。
    """
    try:
        user = await self._user_repository.get_by_id(user_id)
        if not user:
            raise UserNotFoundException(user_id)
        return user

    except RepositoryAccessError as e:
        # Repository層でのアクセスエラー
        # Service層はhttpx.RequestErrorを知らない
        logger.error(
            "repository_access_failed",
            user_id=user_id,
            error=str(e),
        )
        # 必要に応じて再スロー、またはフォールバック処理
        raise
```


---

### 4. Infrastructure層（インフラ層）

**責務**: 外部システム（API、DB）との通信の具体的実装
**依存関係**: なし（技術的詳細の実装のみ）

```python
# utils/infrastructure/http_client.py（リファクタリング後）
import httpx
from typing import Any

class HTTPClient:
    """HTTP通信の低レベル実装。

    httpxの詳細を隠蔽し、リトライ・タイムアウトを管理する。
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        retry_count: int = 3,
    ):
        """HTTPクライアントを初期化する。

        Args:
            base_url: APIのベースURL
            timeout: リクエストタイムアウト（秒）
            retry_count: リトライ回数
        """
        self.base_url = base_url
        self.timeout = timeout
        self.retry_count = retry_count
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def get(self, endpoint: str) -> dict[str, Any]:
        """GETリクエストを送信する。

        Args:
            endpoint: APIエンドポイント

        Returns:
            レスポンスJSON

        Raises:
            HTTPStatusError: HTTPエラーが発生した場合
        """
        # リトライロジック、エラーハンドリング等の実装
        response = await self._client.get(endpoint)
        response.raise_for_status()
        return response.json()
```

---

### Repository Pattern適用の利点

#### 1. テスタビリティ向上
- **単体テスト**: Service層のみテスト、Repository層をモック
- **統合テスト**: 全層を実際に動作させてテスト

#### 2. 保守性向上
- **インフラ変更の影響局所化**: API → DB移行時、Infrastructure層とRepository層のみ変更
- **ビジネスロジックの明確化**: Service層にビジネスルールが集約

#### 3. 拡張性
- **新しいデータソース追加が容易**: Repository実装を追加
- **キャッシュ層の追加が容易**: Repository内で実装（具体例は下記参照）

---

### Cache戦略実装例（Major課題M1対応）

Repository PatternではDecorator Patternを使用してキャッシュ層を追加できます。

#### Simple Cache実装（Infrastructure層）

```python
# utils/infrastructure/cache.py
import asyncio
from typing import Any, Callable, TypeVar
from datetime import datetime, timedelta

T = TypeVar("T")

class SimpleCache:
    """TTLベースの簡易キャッシュ実装。

    Repository層でのキャッシュ戦略に使用。
    本番環境ではRedis等の外部キャッシュを推奨。
    """

    def __init__(self, ttl_seconds: int = 300):
        """キャッシュを初期化する。

        Args:
            ttl_seconds: キャッシュの有効期限（秒）
        """
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._ttl = timedelta(seconds=ttl_seconds)
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        """キャッシュからデータを取得する。

        Args:
            key: キャッシュキー

        Returns:
            キャッシュデータ、または期限切れ・存在しない場合はNone
        """
        async with self._lock:
            if key not in self._cache:
                return None

            value, expiry = self._cache[key]
            if datetime.now() > expiry:
                # 期限切れ: 削除してNoneを返す
                del self._cache[key]
                return None

            return value

    async def set(self, key: str, value: Any) -> None:
        """キャッシュにデータを保存する。

        Args:
            key: キャッシュキー
            value: 保存するデータ
        """
        async with self._lock:
            expiry = datetime.now() + self._ttl
            self._cache[key] = (value, expiry)

    async def delete(self, key: str) -> None:
        """キャッシュからデータを削除する。

        Args:
            key: キャッシュキー
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]

    async def clear(self) -> None:
        """キャッシュを全削除する。"""
        async with self._lock:
            self._cache.clear()
```

#### Cached Repository実装（Decorator Pattern）

```python
# utils/repositories/user_repository.py
from utils.domain.models import User
from utils.repositories.interfaces import UserRepositoryInterface
from utils.infrastructure.cache import SimpleCache

class CachedUserRepository(UserRepositoryInterface):
    """キャッシュ機能を持つUserRepository（Decorator Pattern）。

    既存のUserRepositoryをラップし、キャッシュ層を追加する。
    Repository Patternの拡張性を示す実装例。
    """

    def __init__(
        self,
        repository: UserRepositoryInterface,
        cache: SimpleCache,
    ):
        """Cached Repositoryを初期化する。

        Args:
            repository: ラップする元のRepository
            cache: キャッシュ実装
        """
        self._repository = repository
        self._cache = cache

    async def get_by_id(self, user_id: int) -> User | None:
        """ユーザーをIDで取得する（キャッシュ付き）。

        Args:
            user_id: ユーザーID

        Returns:
            ユーザーエンティティ、または存在しない場合はNone

        キャッシュ戦略:
        1. キャッシュから取得を試みる
        2. キャッシュミス時はRepositoryから取得
        3. 取得成功時はキャッシュに保存
        """
        # キャッシュキー生成
        cache_key = f"user:{user_id}"

        # キャッシュから取得
        cached_user = await self._cache.get(cache_key)
        if cached_user is not None:
            return cached_user

        # キャッシュミス: Repositoryから取得
        user = await self._repository.get_by_id(user_id)
        if user is not None:
            # キャッシュに保存
            await self._cache.set(cache_key, user)

        return user

    async def list_users(self) -> list[User]:
        """全ユーザーを取得する（キャッシュ付き）。

        Returns:
            ユーザーエンティティのリスト

        注意:
        list系はキャッシュ無効化が複雑なため、
        実務ではTTLを短く設定するか、
        create/update/delete時に明示的にキャッシュクリア推奨
        """
        cache_key = "users:all"

        cached_users = await self._cache.get(cache_key)
        if cached_users is not None:
            return cached_users

        users = await self._repository.list_users()
        await self._cache.set(cache_key, users)
        return users

    async def create(self, user: User) -> User:
        """ユーザーを作成する（キャッシュ無効化付き）。

        Args:
            user: 作成するユーザーエンティティ

        Returns:
            作成されたユーザーエンティティ

        キャッシュ無効化:
        - 作成後、list系のキャッシュを削除
        """
        created_user = await self._repository.create(user)

        # list系キャッシュ無効化
        await self._cache.delete("users:all")

        return created_user

    async def update(self, user: User) -> User:
        """ユーザーを更新する（キャッシュ無効化付き）。

        Args:
            user: 更新するユーザーエンティティ

        Returns:
            更新されたユーザーエンティティ

        キャッシュ無効化:
        - 該当ユーザーのキャッシュ削除
        - list系のキャッシュ削除
        """
        updated_user = await self._repository.update(user)

        # 該当ユーザーのキャッシュ無効化
        await self._cache.delete(f"user:{user.id}")
        # list系キャッシュ無効化
        await self._cache.delete("users:all")

        return updated_user

    async def delete(self, user_id: int) -> bool:
        """ユーザーを削除する（キャッシュ無効化付き）。

        Args:
            user_id: 削除するユーザーID

        Returns:
            削除成功時True、失敗時False

        キャッシュ無効化:
        - 該当ユーザーのキャッシュ削除
        - list系のキャッシュ削除
        """
        success = await self._repository.delete(user_id)

        if success:
            await self._cache.delete(f"user:{user_id}")
            await self._cache.delete("users:all")

        return success
```

#### Service層でのCached Repository使用例

```python
# utils/services/user_service.py（キャッシュ有効化版）
from utils.domain.models import User
from utils.repositories.interfaces import UserRepositoryInterface
from utils.repositories.user_repository import UserRepository, CachedUserRepository
from utils.infrastructure.cache import SimpleCache
from utils.infrastructure.api_client import JSONPlaceholderClient

class UserService:
    """ユーザー関連ビジネスロジック（キャッシュ有効化版）。"""

    @classmethod
    def create_with_cache(cls, ttl_seconds: int = 300) -> "UserService":
        """キャッシュ機能付きUserServiceを生成する（Factory Method）。

        Args:
            ttl_seconds: キャッシュ有効期限（秒）

        Returns:
            キャッシュ機能付きUserService

        依存関係注入:
        Infrastructure → Repository → CachedRepository → Service
        """
        # Infrastructure層
        api_client = JSONPlaceholderClient()

        # Repository層（基本実装）
        base_repository = UserRepository(api_client)

        # Cache層
        cache = SimpleCache(ttl_seconds=ttl_seconds)

        # Cached Repository（Decorator Pattern）
        cached_repository = CachedUserRepository(base_repository, cache)

        # Service層
        return cls(user_repository=cached_repository)

    def __init__(self, user_repository: UserRepositoryInterface):
        """UserServiceを初期化する。

        Args:
            user_repository: ユーザーリポジトリ（Cachedでも可）
        """
        self._user_repository = user_repository

    async def get_user_by_id(self, user_id: int) -> User | None:
        """ユーザーをIDで取得する（キャッシュ透過）。

        Args:
            user_id: ユーザーID

        Returns:
            ユーザーエンティティ、または存在しない場合はNone

        Service層はキャッシュの有無を意識しない（透過的）
        """
        return await self._user_repository.get_by_id(user_id)
```

**キャッシュ戦略の実務ポイント**:
1. **Decorator Pattern**: 既存Repositoryを変更せずキャッシュ追加
2. **TTL管理**: 5分（300秒）をデフォルト、用途に応じて調整
3. **キャッシュ無効化**: create/update/delete時に関連キャッシュを削除
4. **本番環境**: RedisやMemcached使用を推奨（SimpleCacheは開発・テスト用）
5. **テスタビリティ**: CachedRepositoryもUserRepositoryInterfaceを実装 → テスト時はモック可能

---

### Transaction管理実装例（Major課題M2対応）

複数Repositoryを跨ぐビジネスロジックでは、トランザクション管理が必要です。

#### Transaction Manager実装（Infrastructure層）

```python
# utils/infrastructure/transaction.py
from typing import Callable, TypeVar, ParamSpec
from contextlib import asynccontextmanager
import httpx

T = TypeVar("T")
P = ParamSpec("P")

class TransactionManager:
    """トランザクション管理（Context Manager Pattern）。

    現在はAPIクライアントのため疑似トランザクション。
    将来のDB統合時に実際のトランザクション管理に拡張可能。
    """

    def __init__(self):
        """Transaction Managerを初期化する。"""
        self._operations: list[Callable] = []
        self._rollback_operations: list[Callable] = []
        self._is_active = False

    @asynccontextmanager
    async def transaction(self):
        """トランザクションコンテキスト。

        Yields:
            TransactionManager自身

        Raises:
            Exception: トランザクション内でエラーが発生した場合

        使用例:
        ```python
        async with transaction_manager.transaction():
            await user_service.delete_user_with_todos(user_id)
            # エラー発生時は自動ロールバック
        ```
        """
        self._is_active = True
        self._operations.clear()
        self._rollback_operations.clear()

        try:
            yield self
            # コミット: 特に何もしない（API操作は即座に反映されるため）
            # DB統合時はここでcommit()実行
        except Exception as e:
            # ロールバック: 登録された補償トランザクションを実行
            await self._rollback()
            raise e
        finally:
            self._is_active = False

    async def _rollback(self) -> None:
        """ロールバック: 補償トランザクションを実行する。

        Note:
        APIベースの場合、完全なロールバックは不可能。
        create操作の補償としてdelete操作を実行する等の対応。
        """
        # 逆順で補償トランザクション実行
        for rollback_op in reversed(self._rollback_operations):
            try:
                await rollback_op()
            except Exception as e:
                # ロールバック中のエラーはログ出力のみ
                import structlog
                logger = structlog.get_logger()
                logger.error("rollback_failed", error=str(e))

    def register_rollback(self, rollback_operation: Callable) -> None:
        """補償トランザクション（ロールバック操作）を登録する。

        Args:
            rollback_operation: ロールバック時に実行する非同期関数
        """
        if not self._is_active:
            raise RuntimeError("Transaction is not active")
        self._rollback_operations.append(rollback_operation)
```

#### Service層でのTransaction使用例

```python
# utils/services/user_service.py（トランザクション対応版）
from utils.domain.models import User
from utils.domain.exceptions import UserNotFoundException, RepositoryAccessError
from utils.repositories.interfaces import UserRepositoryInterface, TodoRepositoryInterface
from utils.infrastructure.transaction import TransactionManager

class UserService:
    """ユーザー関連ビジネスロジック（トランザクション対応版）。"""

    def __init__(
        self,
        user_repository: UserRepositoryInterface,
        todo_repository: TodoRepositoryInterface,
        transaction_manager: TransactionManager,
    ):
        """UserServiceを初期化する。

        Args:
            user_repository: ユーザーリポジトリ
            todo_repository: Todoリポジトリ
            transaction_manager: トランザクションマネージャー
        """
        self._user_repository = user_repository
        self._todo_repository = todo_repository
        self._transaction_manager = transaction_manager

    async def delete_user_with_todos(self, user_id: int) -> bool:
        """ユーザーとそのTodoを削除する（トランザクション管理）。

        Args:
            user_id: 削除するユーザーID

        Returns:
            削除成功時True

        Raises:
            UserNotFoundException: ユーザーが存在しない場合
            RepositoryAccessError: データアクセスエラー

        トランザクション戦略:
        1. ユーザー存在確認
        2. Todoリスト取得
        3. 各Todo削除（エラー時ロールバック）
        4. ユーザー削除（エラー時ロールバック）
        """
        # 1. ユーザー存在確認
        user = await self._user_repository.get_by_id(user_id)
        if not user:
            raise UserNotFoundException(user_id)

        # 2. Todoリスト取得
        todos = await self._todo_repository.get_by_user_id(user_id)

        # 3-4. トランザクション開始
        async with self._transaction_manager.transaction():
            # 各Todo削除
            for todo in todos:
                success = await self._todo_repository.delete(todo.id)
                if not success:
                    raise RepositoryAccessError(
                        f"Failed to delete todo: {todo.id}"
                    )

                # ロールバック操作登録（再作成）
                # 注意: API操作のロールバックは完全ではないため、
                # 実務ではDB統合後に真のトランザクション管理を推奨
                todo_copy = todo
                self._transaction_manager.register_rollback(
                    lambda: self._todo_repository.create(todo_copy)
                )

            # ユーザー削除
            success = await self._user_repository.delete(user_id)
            if not success:
                raise RepositoryAccessError(
                    f"Failed to delete user: {user_id}"
                )

            # ロールバック操作登録（再作成）
            user_copy = user
            self._transaction_manager.register_rollback(
                lambda: self._user_repository.create(user_copy)
            )

        return True

    async def create_user_with_initial_todos(
        self,
        user: User,
        initial_todos: list[str],
    ) -> User:
        """ユーザーと初期Todoを作成する（トランザクション管理）。

        Args:
            user: 作成するユーザーエンティティ
            initial_todos: 初期Todo タイトルリスト

        Returns:
            作成されたユーザーエンティティ

        Raises:
            RepositoryAccessError: データアクセスエラー

        トランザクション戦略:
        1. ユーザー作成
        2. 各初期Todo作成（エラー時はユーザーも削除）
        """
        async with self._transaction_manager.transaction():
            # 1. ユーザー作成
            created_user = await self._user_repository.create(user)

            # ロールバック操作登録
            self._transaction_manager.register_rollback(
                lambda: self._user_repository.delete(created_user.id)
            )

            # 2. 初期Todo作成
            for todo_title in initial_todos:
                from utils.domain.models import Todo
                todo = Todo(
                    id=0,  # API側で自動採番
                    user_id=created_user.id,
                    title=todo_title,
                    completed=False,
                )
                created_todo = await self._todo_repository.create(todo)

                # ロールバック操作登録
                todo_id = created_todo.id
                self._transaction_manager.register_rollback(
                    lambda: self._todo_repository.delete(todo_id)
                )

        return created_user
```

**Transaction管理の実務ポイント**:
1. **Context Manager Pattern**: `async with`で自動コミット・ロールバック
2. **補償トランザクション**: API操作のロールバックは完全ではないため、create操作の補償としてdelete操作を登録
3. **DB統合準備**: TransactionManager実装を拡張し、DB接続オブジェクトの`begin()`/`commit()`/`rollback()`に置き換え可能
4. **エラー境界**: Service層でトランザクションスコープを管理、Repository層はトランザクション非依存
5. **テスタビリティ**: TransactionManagerをモック化可能、トランザクション動作を独立テスト可能

**DB統合時の拡張例（参考）**:
```python
# 将来のDB統合時
class DBTransactionManager(TransactionManager):
    """DB接続でのトランザクション管理。"""

    def __init__(self, db_connection):
        super().__init__()
        self._db_connection = db_connection

    @asynccontextmanager
    async def transaction(self):
        self._is_active = True
        async with self._db_connection.begin():  # ← DB統合時
            try:
                yield self
                await self._db_connection.commit()  # ← 実際のコミット
            except Exception as e:
                await self._db_connection.rollback()  # ← 実際のロールバック
                raise e
            finally:
                self._is_active = False
```

---

### リファクタリング戦略

#### 既存の`utils/api_client.py`の段階的移行

**Phase 1**: Infrastructure層に移動
```bash
# 既存ファイルをインフラ層に移動
mkdir -p utils/infrastructure
mv utils/api_client.py utils/infrastructure/api_client.py
```

**Phase 2**: Repository層を作成
```bash
# Repository層の作成
mkdir -p utils/repositories
# utils/repositories/user_repository.py を新規作成
# Infrastructure層のAPIクライアントをラップ
```

**Phase 3**: Service層を作成
```bash
# Service層の作成
mkdir -p utils/services
# utils/services/user_service.py を新規作成
# ビジネスロジックを実装
```

**Phase 4**: 既存コードの段階的移行
```python
# 【移行前】既存の直接APIクライアント使用
from utils.api_client import JSONPlaceholderClient
client = JSONPlaceholderClient()
user = await client.get_user(1)

# ↓ 【移行後】Service層経由
from utils.services.user_service import UserService
from utils.repositories.user_repository import UserRepository
from utils.infrastructure.api_client import JSONPlaceholderClient

# 依存注入による初期化
api_client = JSONPlaceholderClient()
user_repository = UserRepository(api_client)
user_service = UserService(user_repository)

# ビジネスロジック付きでユーザー取得
user = await user_service.get_user_by_id(1)  # ドメインエンティティを返す
```

---

### 新規実装時の適用ルール

#### 新規実装ルール

**今後の新規実装**:
1. Domain層のエンティティを定義
2. Repositoryインターフェースを定義
3. Repository実装を作成
4. Service層でビジネスロジック実装
5. Infrastructure層は必要に応じて拡張

#### 適用判断基準

| シナリオ | Service層 | 推奨アプローチ |
|---------|-----------|---------------|
| **シンプルなAPI取得**（例: get_user()のみ） | ⚠️ 任意 | Repository直接使用も可 |
| **ビジネスルール適用**（例: メール検証、ID検証） | ✅ 推奨 | Service層で実装 |
| **複数Repository組み合わせ**（例: User + Todo） | ✅ 必須 | Service層必須 |
| **トランザクション管理**（将来的DB統合時） | ✅ 必須 | Service層で管理 |

**Service層を作成すべき場合**:
- ✅ 複数のRepositoryを組み合わせる
- ✅ ビジネスルール適用が必要
- ✅ トランザクション管理が必要（将来的にDB統合時）
- ✅ 外部サービス連携（メール送信、通知等）

**Service層不要の場合**:
- ❌ 単純なCRUD操作のみ（Repository直接使用）
- ❌ 一時的なスクリプト・テストコード

---

## テスト戦略（実務推奨）

### テスト戦略の基本原則

#### 1. テストピラミッド準拠（実務4層構成）

```
        /\
       /  \  E2E (5%)
      /────\
     /      \ Integration (25%)
    /────────\
   /          \ Unit (70%)
  /────────────\
```

**各層の役割と実施環境**:
- **単体テスト（Unit）**: 60-70%、高速・独立・モック中心（開発環境）
- **統合テスト（Integration）**: 20-30%、実API・DB使用、複数層統合（開発環境 + CI/CD）
- **E2Eテスト（E2E）**: 3-5%、ユーザー視点、重要シナリオのみ（**stg/本番環境**）

**System TestとE2Eの違い（実務重要ポイント）**:
- **System Test**: インフラ・設定・外部連携を含む**環境全体の動作検証**
  - 実施場所: **stg環境**（本番相当のDocker/Kubernetes環境）
  - 検証内容: API応答、環境変数、外部API連携、パフォーマンス、セキュリティ
  - 目的: 本番リリース前のインフラ統合品質保証
  - 例: `@pytest.mark.system`マーカーで識別
- **E2E Test**: **ユーザー操作フロー**の検証
  - 実施場所: stg環境または本番環境
  - 検証内容: ログイン → データ取得 → 表示までの一連のユーザー操作
  - 目的: ユーザー体験の品質保証
  - 例: Playwright/Selenium等のブラウザ自動化

#### 2. Repository Pattern適用時のテスト戦略

| テスト対象層 | テストタイプ | モック対象 | 実API/DB使用 | 実施環境 | 目的 |
|-------------|-------------|-----------|-------------|---------|------|
| **Domain層** | 単体 | なし | なし | 開発環境 | ビジネスルール検証 |
| **Service層** | 単体 | Repository | なし | 開発環境 | ユースケース検証 |
| **Repository層** | 単体 | Infrastructure | なし | 開発環境 | データ変換ロジック検証 |
| **Infrastructure層** | 統合 | なし | **実API使用** | 開発/CI | 外部API接続検証 |
| **全層統合** | 統合 | なし | **実API使用** | 開発/CI | 複数層動作検証 |
| **全層 + インフラ** | **システム** | なし | **実API + Docker環境** | **stg環境** | **本番相当環境での動作検証** |
| **ユーザーフロー** | E2E | なし | **実API + UI** | stg/本番 | エンドユーザー体験検証 |

#### 3. モック使用の判断基準（実務推奨）

**単体テスト（Unit）: モック必須**
```python
# ✅ 推奨: Repository層をモック化
@pytest.mark.unit
async def test_user_service_get_user(mock_user_repository):
    """Service層のテスト: Repository層をモック。"""
    service = UserService(user_repository=mock_user_repository)
    # Repositoryの戻り値をモックで設定
    mock_user_repository.get_by_id.return_value = User(id=1, ...)

    result = await service.get_user_by_id(1)
    assert result.id == 1
```

**統合テスト（Integration）: 実API使用**
```python
# ✅ 推奨: 実API（JSONPlaceholder）使用
@pytest.mark.integration
@pytest.mark.external
async def test_user_repository_real_api():
    """Repository層の統合テスト: 実APIで接続検証。"""
    api_client = JSONPlaceholderClient()
    repository = UserRepository(api_client)

    # 実APIから取得
    user = await repository.get_by_id(1)
    assert user is not None
    assert user.id == 1
```

**統合テスト制御: 環境変数による切替**
```python
# conftest.py
import pytest
from config.settings import settings

def pytest_collection_modifyitems(config, items):
    """外部API依存テストの制御。"""
    if not settings.test.external_api_enabled:
        skip_external = pytest.mark.skip(
            reason="External API tests disabled (TEST__EXTERNAL_API_ENABLED=false)"
        )
        for item in items:
            if "external" in item.keywords:
                item.add_marker(skip_external)
```

**環境変数設定（.env）**:
```bash
# 開発環境: 外部API使用
TEST__EXTERNAL_API_ENABLED=true

# CI/CD環境: 外部API使用（統合テスト実行）
TEST__EXTERNAL_API_ENABLED=true

# オフライン開発: 外部API無効化
TEST__EXTERNAL_API_ENABLED=false
```

---

### テスト構成パターン

#### テストディレクトリ構成

```
tests/
├── conftest.py              # 共通フィクスチャ・設定
│   ├── async_client         # 非同期テスト用フィクスチャ
│   ├── mock_user_repository # モック化Repository（単体テスト用）
│   ├── mock_todo_repository # モック化Repository（単体テスト用）
│   ├── todo_data_factory    # テストデータ生成
│   ├── user_data_factory    # テストデータ生成
│   ├── performance_timer    # パフォーマンス計測
│   └── security_payloads    # セキュリティテスト用ペイロード
├── unit/                    # 単体テスト（モック中心、開発環境）
│   ├── domain/              # Domain層テスト
│   ├── services/            # Service層テスト
│   └── repositories/        # Repository層テスト（Infrastructure層モック）
├── integration/             # 統合テスト（実API使用、開発/CI環境）
│   ├── test_api_integration.py    # 全層統合テスト
│   └── test_repository_real_api.py # Repository + Infrastructure実API
├── e2e/                     # E2Eテスト（stg/本番環境、ユーザーフロー）
├── performance/             # パフォーマンステスト（stg環境推奨）

```

#### conftest.pyフィクスチャ実装例

```python
# tests/conftest.py
import pytest
from unittest.mock import AsyncMock
from utils.repositories.interfaces import UserRepositoryInterface, TodoRepositoryInterface
from utils.domain.models import User, Todo

# ========================================
# 単体テスト用モックフィクスチャ
# ========================================

@pytest.fixture
def mock_user_repository() -> UserRepositoryInterface:
    """モック化されたユーザーリポジトリ（単体テスト用）。

    Returns:
        UserRepositoryInterfaceのモックオブジェクト
    """
    repository = AsyncMock(spec=UserRepositoryInterface)
    return repository

@pytest.fixture
def mock_todo_repository() -> TodoRepositoryInterface:
    """モック化されたTodoリポジトリ（単体テスト用）。

    Returns:
        TodoRepositoryInterfaceのモックオブジェクト
    """
    repository = AsyncMock(spec=TodoRepositoryInterface)
    return repository

# ========================================
# テストデータファクトリー
# ========================================

@pytest.fixture
def user_data_factory():
    """ユーザーテストデータ生成ファクトリー。

    Returns:
        ユーザーデータ生成関数
    """
    def _create_user(user_id: int = 1, **kwargs) -> User:
        defaults = {
            "id": user_id,
            "name": f"Test User {user_id}",
            "email": f"user{user_id}@example.com",
        }
        defaults.update(kwargs)
        return User(**defaults)
    return _create_user

@pytest.fixture
def todo_data_factory():
    """Todoテストデータ生成ファクトリー。

    Returns:
        Todoデータ生成関数
    """
    def _create_todo(todo_id: int = 1, user_id: int = 1, **kwargs) -> Todo:
        defaults = {
            "id": todo_id,
            "user_id": user_id,
            "title": f"Test Todo {todo_id}",
            "completed": False,
        }
        defaults.update(kwargs)
        return Todo(**defaults)
    return _create_todo
```

---

### テストマーカー設定（pytest.ini）

**実務4層テストマーカー定義**:
```ini
# pytest.ini
[tool.pytest.ini_options]
markers = [
    "unit: 単体テスト（モック中心、開発環境）",
    "integration: 統合テスト（実API使用、開発/CI環境）",
    "e2e: E2Eテスト（stg/本番環境、ユーザーフロー検証）",
    "performance: パフォーマンステスト（stg環境推奨）",
    "external: 外部API依存テスト（環境変数で制御）",
]
```

### テストマーカー使用例

**単体テスト（Unit）**:
```python
import pytest

@pytest.mark.unit
def test_base_client_initialization():
    """BaseAPIClient初期化テスト。"""
    ...

@pytest.mark.unit
async def test_user_service_with_mock(mock_user_repository):
    """Service層テスト: Repository層をモック化。"""
    ...
```

**統合テスト（Integration）**:
```python
@pytest.mark.integration
@pytest.mark.external
async def test_get_user_from_api():
    """JSONPlaceholder API統合テスト。"""
    ...

@pytest.mark.integration
async def test_repository_data_transformation():
    """Repository層の実API統合テスト。"""
    ...
```

**システムテスト（System）- stg環境で実施**:
```python
@pytest.mark.system
@pytest.mark.external
async def test_docker_environment_api_response():
    """Docker環境でのAPI応答検証（stg環境）。

    検証内容:
    - 本番相当のDocker環境でのAPI動作
    - 環境変数の正しい読み込み
    - 外部API連携の動作確認
    - パフォーマンス基準達成（応答時間<2秒）
    """
    # stg環境のDocker内で実行
    client = JSONPlaceholderClient()
    user = await client.get_user(1)
    assert user is not None
    # 応答時間検証
    assert response_time < 2.0

@pytest.mark.system
@pytest.mark.security
async def test_stg_environment_security():
    """stg環境でのセキュリティ検証。

    検証内容:
    - レート制限の動作確認
    - 認証・認可の動作確認
    - HTTPS通信の検証
    """
    ...
```

**E2Eテスト（E2E）- ユーザーフロー検証**:
```python
@pytest.mark.e2e
async def test_user_data_retrieval_flow():
    """ユーザーデータ取得フロー（E2E）。

    ユーザー操作:
    1. ログイン
    2. ユーザー一覧表示
    3. 特定ユーザー詳細表示
    4. Todoデータ取得
    """
    ...
```

**パフォーマンステスト（stg環境推奨）**:
```python
@pytest.mark.performance
@pytest.mark.slow
@pytest.mark.system  # stg環境で実施推奨
async def test_concurrent_requests_performance():
    """並行リクエストパフォーマンス計測（stg環境）。"""
    ...
```

### テスト実行コマンド（実務4層対応）

**開発環境でのテスト実行**:
```bash
# 単体テストのみ（高速、モック中心）
uv run pytest -m unit

# 統合テストのみ（実API使用）
uv run pytest -m integration

# 単体 + 統合テスト（CI/CD推奨）
uv run pytest -m "unit or integration"

# システムテストを除外（開発環境では未実施）
uv run pytest -m "not system and not e2e"
```

**stg環境でのテスト実行（本番リリース前必須）**:
```bash
# システムテスト（Docker環境での全体検証）
uv run pytest -m system --env=staging

# システム + E2Eテスト（リリース判定基準）
uv run pytest -m "system or e2e" --env=staging

# パフォーマンステスト（stg環境推奨）
uv run pytest -m "system and performance" --env=staging

# セキュリティテスト（stg環境推奨）
uv run pytest -m "system and security" --env=staging
```

**CI/CDパイプラインでのテスト戦略**:
```yaml
# .github/workflows/test.yml
jobs:
  unit-test:
    runs-on: ubuntu-latest
    steps:
      - run: uv run pytest -m unit  # 高速フィードバック

  integration-test:
    runs-on: ubuntu-latest
    steps:
      - run: uv run pytest -m integration  # 実API統合検証

  system-test:
    runs-on: ubuntu-latest
    env:
      ENVIRONMENT: staging
    steps:
      - run: docker-compose -f docker-compose.stg.yml up -d
      - run: uv run pytest -m system --env=staging  # stg環境検証
      - run: docker-compose down
```

### フィクスチャスコープ
```python
# session: 全体で1回のみ
@pytest.fixture(scope="session")
def event_loop():
    """非同期テスト用イベントループ。"""
    ...

# module: モジュール単位
@pytest.fixture(scope="module")
def mock_httpx_client():
    """モックHTTPクライアント。"""
    ...

# function: 各テスト関数ごと
@pytest.fixture
def user_data():
    """テスト用ユーザーデータ。"""
    return {"id": 1, "name": "Test User"}
```

---

## Git運用規則

### ブランチ戦略
- **main**: 本番相当（直接コミット禁止）
- **local/history**: 履歴管理（現在の作業ブランチ）
  - 学習・実装の全履歴を記録
  - 定期的にmainにマージ
- **feature/***: 機能開発（将来使用）
- **fix/***: バグ修正（将来使用）

### コミットメッセージ規約
```bash
feat: Docker 4-stage Dockerfile実装
fix: APIタイムアウトエラーハンドリング修正
docs: README.mdセットアップ手順追加
test: 非同期パフォーマンステスト追加
refactor: エラーハンドリング階層整理
chore: ruff設定最新化
```

### コミット前チェックリスト
- [ ] uv run pytest: 全テスト合格
- [ ] uv run ruff check --fix .: ruffエラーゼロ
- [ ] uv run mypy utils/ config/: 型チェックエラーゼロ
- [ ] pre-commit hooks実行完了（自動）

---

## 設定ファイル管理

### 環境変数管理（.env）
```bash
# .env（git除外）
ENVIRONMENT=development
DEBUG=true
API__BASE_URL=https://jsonplaceholder.typicode.com
API__TIMEOUT=30
LOG__LEVEL=DEBUG
SECURITY__API_KEY=your-secret-key
```

### Pydantic Settingsアクセス
```python
from config.settings import settings

base_url = settings.api.base_url
log_level = settings.log.level

if settings.is_development():
    # 開発環境固有処理
    pass
```

---

## ドキュメント管理規則

### 更新日付記載ルール
```markdown
# ドキュメントタイトル

*最終更新: 2025年11月13日*
```

### ドキュメント種別

| 種別 | 配置場所 | 用途 |
|------|---------|------|
| プロジェクト指示 | CLAUDE.md | Claude Code用 |
| Steering Docs | .spec-workflow/steering/ | Spec開発用 |
| 学習計画 | docs/main/6週プラン/ | 6週プラン |
| 進捗記録 | docs/progress/ | 日次・週次 |
| 理解度確認 | docs/learning/ | 日次問題 |

---

## 品質ゲート自動化

### pre-commit（軽量版）
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

### CI/CD品質ゲート（実装済み）
```yaml
jobs:
  quality-gate:
    steps:
      - name: Lint
        run: uv run ruff check .
      - name: Type Check
        run: uv run mypy utils/ config/
      - name: Test
        run: uv run pytest --cov-fail-under=85
      - name: Security
        run: uv run bandit -r utils/ config/
```

---

## 新機能追加時のワークフロー

### 標準フロー
1. ブランチ: git checkout -b feature/new-feature
2. AI協働学習:
   - Phase 1: 概念理解（30%）
   - Phase 2: 実装（60%）
   - Phase 3: 理解度確認（80%+）
3. 品質ゲート実行
4. コミット: git commit -m "feat: 新機能"
5. 進捗記録: learning_state.yaml, daily_progress.md更新

### ファイル配置ルール
- 新規APIクライアント: utils/
- 新規設定クラス: config/settings.py
- 新規テスト: tests/unit/, tests/integration/等
- 新規ドキュメント: docs/配下

---

## 除外設定

### .gitignore
```
.env
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
venv/
.venv/
reports/
coverage.xml
htmlcov/
.vscode/
.DS_Store
```

### .dockerignore（Week 3実装予定）
```
.git/
__pycache__/
venv/
tests/
reports/
docs/
README.md
```

---

## プロジェクト拡張ガイドライン

### 新規モジュール追加時
1. utils/またはconfig/に配置
2. __init__.pyでexport
3. 型ヒント必須
4. docstring必須
5. テストファイル作成
6. カバレッジ85%維持

### 新規テストカテゴリ追加時
1. tests/新カテゴリ/作成
2. pytest markerをpyproject.tomlに追加
3. conftest.pyにフィクスチャ追加
4. CLAUDE.mdに実行例記載
