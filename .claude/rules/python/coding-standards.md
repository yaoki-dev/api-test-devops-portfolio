---
paths: ["**/*.py"]
---

# api-test-devops-portfolio コーディング規約

*最終更新: 2026年02月10日*

**Python バージョン**: 3.14 | **実装方針**: Python 3.14

---

## 1. 命名規則

| 種類 | 規則 | 例 |
|-----|------|-----|
| クラス名 | PascalCase | `APIClientError`, `AsyncAPIClient` |
| 関数/メソッド | snake_case | `get_user()`, `_private_method()` |
| 変数 | snake_case | `base_url`, `sample_user_data` |
| 定数 | UPPER_SNAKE_CASE | `SECRET_PATTERNS` |
| Enum値 | UPPER_SNAKE_CASE | `DEVELOPMENT`, `PRODUCTION` |

- 略語は大文字維持: `API`, `HTTP`, `JSON`
- テストデータ: `sample_`, `mock_`, `test_` プレフィックス
- 公開API: `__all__` で明示

---

## 2. コードスタイル

- **4スペースインデント**、**行長上限100文字**
- インポート順: 標準ライブラリ → サードパーティ → プロジェクト内
- 自動検証: `uv run ruff check --fix . && uv run ruff format .`

---

## 3. 型ヒント

全関数・メソッドに型ヒント必須（mypy: `disallow_untyped_defs = true`）

**適用範囲**: `utils/`, `config/`, `models/`, `tests/conftest.py`, `tests/**/__init__.py` は強制対象。`tests/unit/test_*.py` 等のテスト本体は推奨（CI mypy invocation 対象外、漸次型付与方針）

```python
def __init__(self, base_url: str | None = None) -> None: ...  # Python 3.10+ Union


type JSONResponse = dict[str, Any]  # Python 3.12+ 型エイリアス


async def __aenter__(self) -> Self: ...  # Python 3.11+ Self型
```

自動検証: `uv run mypy utils/ config/ models/ tests/conftest.py`

---

## 4. docstring規約

```python
def func(attempt: int) -> float:
    """概要（1行目）

    Args:
        attempt: リトライ回数

    Returns:
        計算された遅延時間
    """
```

公開クラス・関数にdocstring必須、Args/Returns/Raises明記

### 4.1 テストコードのdocstring/comment方針

テスト関数のdocstringとインラインコメントは、テスト名・assert内容・手順を言い換えるだけなら削除する。短いdocstringを残すのは、テスト名だけでは非自明な失敗モード、複数モジュールを通る結合経路、不自然だが本質的な前提や順序、または関数名に入れると長すぎる背景を説明する場合だけにする。

fixture・helper・テスト用classは、global stateの変更/復元、teardown順序、fake client/transport、network blocker、autouse fixture、環境変数上書き、後続テストへの状態リーク防止を説明するWHYを1〜3行で残す。

コメント/docstringのみの整理では、実行ASTとfixture文書化契約を必ず確認する。

```bash
uv run python scripts/check_docstring_refactor.py --self-test
uv run python scripts/check_docstring_refactor.py --fixture-gate
BASE_REF=$(git merge-base HEAD origin/develop)
uv run python scripts/check_docstring_refactor.py "$BASE_REF" tests/path/to/test_file.py
```

---

## 5. エラーハンドリング

```python
class APIClientError(Exception): ...  # 基底例外
class APIHTTPError(APIClientError): ...  # 派生例外

except json.JSONDecodeError as e:
    raise APIClientError(f"Invalid JSON: {e}") from e  # チェーン維持
```

**規則**: 階層的例外設計、`from e`でチェーン維持、4xx即失敗/5xxリトライ

**セキュリティ規則**: 例外クラス名には PII（個人識別情報）を連想させる語を含めないこと。
例: `UserEmailValidationError` のようなクラス名は、`__qualname__` 経由で Sentry に
送信される際に「email」等を機密カテゴリ語として誤検知されたり、PII の存在を
示唆したりするリスクがある（クラス名自体に実データは含まれないが、語が誤解を招く）。
`ValidationError` のような汎用名を使用すること。

---

## 6. 非同期処理

```python
async with asyncio.TaskGroup() as tg:  # Python 3.11+ 推奨
    user_task = tg.create_task(self.get_user(user_id))
```

`TaskGroup`: エラー時全タスクキャンセル（推奨） | `gather()`: 他タスク継続可能

---

## 7. パフォーマンス

```python
squares = [x**2 for x in range(100)]  # リスト内包表記（小規模）
total = sum(x**2 for x in range(1_000_000))  # ジェネレータ式（大規模）
result = "".join(str(item) for item in items)  # 文字列結合 O(n)
```

---

## 8. テスト規約

```python
# pytest-asyncio が async テストを自動検出する (asyncio_mode = "auto")
async def test_async_get_user(sample_user_data, mock_response): ...


@pytest.fixture
def sample_user_data() -> dict[str, Any]:
    return {"id": 1, "name": "Test User"}
```

**規則**: `test_`プレフィックス必須、カバレッジ目標は pyproject.toml 参照

---

## 9. コメント規約

- docstring/インラインコメント: 日本語推奨（学習プロジェクト）
- 変数・関数名: 英語必須
- `raise` / `assert` のメッセージ: 英語必須（ログ・Sentry・外部利用者に露出するため）
  - 適用範囲は本番ソース（`utils/` `config/` `models/`）。テストコードの `assert` メッセージは開発者のみが読み外部露出しないため対象外（日本語可）

---

## 10. 自動検証コマンド

```bash
uv run ruff check --fix . && uv run ruff format .  # リンター
uv run mypy utils/ config/ models/                 # 型チェック
uv run bandit -r utils/ config/ models/            # セキュリティ
uv run pre-commit install                          # pre-commit（ruffのみ）
```

---

## 11. プロジェクト固有の規約

### 11.1 データクラス・設定・ログ

```python
@dataclass(slots=True, frozen=True)  # メモリ効率+不変
class UserResponse: ...


from config.settings import settings  # 設定管理
from utils.logger import get_logger  # structlogログ

logger.info("処理開始", user_id=123)  # 構造化ログ
```

### 11.2 セキュリティ禁止パターン

| 禁止 | 理由 |
|-----|------|
| `eval()`, `exec()` | 任意コード実行 |
| `pickle.loads(untrusted)` | 安全でないデシリアライズ |
| `subprocess.run(..., shell=True)` | コマンドインジェクション |
| `f"SELECT ... {user_id}"` | SQLインジェクション |

安全な代替: リスト形式引数、パラメータ化クエリ、`SecretStr`でシークレット管理

---

## 12. 品質保証フロー

```
コード実装 → ruff → mypy → pytest → git commit
```

CI/CD: ruff + mypy + pytest + bandit + gitleaks + Dependabot

---

## 参考

[Ruff](https://docs.astral.sh/ruff/) | [mypy](https://mypy.readthedocs.io/) | [pytest](https://docs.pytest.org/) | [structlog](https://www.structlog.org/) | [Pydantic](https://docs.pydantic.dev/)
