# セキュリティクイックフィックスチェックリスト
*最終更新: 2025年12月06日*

## Critical実行項目（今日完了）

### 項目1: Git履歴から公開されたAPIキーを削除
**必要時間**: 10-15分
**リスクレベル**: CRITICAL

手順:
1. Obsidian設定で即座にObsidian APIキーを無効化
2. git履歴から削除:
   ```bash
   # 現在の変更をバックアップ
   git stash

   # オプションA: BFGを使用（推奨、高速）
   brew install bfg
   bfg --delete-files "SECURITY_REVIEW_v2.2.md"
   cd .bfg-cleanup && git reflog expire --expire=now --all
   git gc --prune=now --aggressive

   # オプションB: git filter-branchを使用（低速）
   git filter-branch --force --index-filter \
     'git rm --cached --ignore-unmatch SECURITY_REVIEW_v2.2.md' \
     --prune-empty -- --all
   ```
3. 新しいObsidian APIキーを生成
4. `.env`にのみ保存（コミットしない）
5. 履歴を上書きするため強制プッシュ:
   ```bash
   git push --force-with-lease origin main
   ```

**成功確認**:
```bash
# 何も返されないはず
git log --full-history -S "5e2e4eec3d3ccd1b7c4ba929bb0697046acf1b04013728063e76db3604549200" -- SECURITY_REVIEW_v2.2.md
```

---

### 項目2: .env.exampleの作成（安全な参照）
**必要時間**: 5分
**リスクレベル**: CRITICAL

```bash
# 安全なテンプレートを作成
cat > .env.example << 'EOF'
# Environment Configuration
ENVIRONMENT=development
DEBUG=true

# API Settings
API__BASE_URL=https://jsonplaceholder.typicode.com
API__TIMEOUT=30
API__RETRY_COUNT=3
API__RETRY_DELAY=1.0
API__MAX_CONNECTIONS=10

# Logging Settings
LOG__LEVEL=DEBUG
LOG__FORMAT=console
LOG__FILE=/var/log/app/api-test.log

# Test Settings
TEST__EXTERNAL_API_ENABLED=true
TEST__PERFORMANCE_TEST_ENABLED=false

# Security Settings (NEVER commit real values)
SECURITY__API_KEY=<YOUR_API_KEY_HERE>
SECURITY__JWT_SECRET=<YOUR_JWT_SECRET_HERE>
SECURITY__RATE_LIMIT_REQUESTS=100
EOF

# gitに追加
git add .env.example
git commit -m "docs: add .env.example template for configuration reference"
```

---

### 項目3: 秘密情報検出用Pre-commitフックの作成
**必要時間**: 10分
**リスクレベル**: CRITICAL

```bash
#!/bin/bash
# .git/hooks/pre-commit

# 出力用の色
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# 潜在的な秘密情報を検出するパターン
SECRETS_PATTERN="(api[_-]?key|secret|password|token|jwt|obsidian)[\s]*[:=][\s]*['\"]?[A-Za-z0-9\-_.]{20,}['\"]?"

# ステージされた変更で秘密情報をチェック
if git diff --cached | grep -iE "$SECRETS_PATTERN" > /dev/null; then
    echo -e "${RED}❌ ERROR: ステージされた変更に潜在的な秘密情報が検出されました！${NC}"
    echo ""
    echo "検出されたパターン:"
    git diff --cached | grep -iE "$SECRETS_PATTERN" | head -5
    echo ""
    echo "修正方法:"
    echo "1. コミットしようとしているファイルからすべての秘密値を削除"
    echo "2. 秘密情報を.envファイルに保存（.gitignoreに含まれます）"
    echo "3. 修正したファイルをステージ: git add ."
    echo "4. 再度コミット: git commit -m '...'"
    echo ""
    echo "このチェックをバイパスする（非推奨）:"
    echo "  git commit --no-verify"
    exit 1
fi

echo -e "${GREEN}✅ Pre-commitチェック合格${NC}"
exit 0
```

**フックをインストール**:
```bash
chmod +x .git/hooks/pre-commit
```

**テスト**:
```bash
# これはブロックされるはず
echo 'API_KEY=abc123defgh456ijkl789mnop123' >> test_secret.txt
git add test_secret.txt
git commit -m "test"  # 失敗するはず

# クリーンアップ
git reset HEAD test_secret.txt
rm test_secret.txt
```

---

## High Priority項目（今週完了）

### 項目4: SSL設定ドキュメントの追加
**必要時間**: 15分
**影響**: HIGH

`.env.example`を更新:
```bash
# SSL/TLS Configuration
API__VERIFY_SSL=true  # 開発環境のみfalseに設定（安全ではありません！）
```

`config/settings.py`を更新:
```python
class APIConfig(BaseModel):
    """SSL セキュリティ付きAPI関連設定"""

    verify_ssl: bool = Field(
        default=True,
        description="SSL証明書を検証（本番環境ではtrueである必要があります）"
    )

    @field_validator("verify_ssl")
    @classmethod
    def validate_ssl_production(cls, v: bool) -> bool:
        """本番環境でSSL検証が有効であることを確認"""
        if not v and settings.is_production():
            raise ValueError("本番環境ではSSL検証を有効にする必要があります")
        return v
```

`utils/api_client.py`を更新:
```python
class BaseAPIClient:
    def __init__(self, ...):
        # ... 既存のコード ...

        # 明示的なSSL設定
        verify_ssl = settings.api.verify_ssl
        if not verify_ssl and settings.is_development():
            logger.warning("⚠️ SSL検証が無効です（開発環境のみ）")

        self._client = httpx.Client(
            limits=httpx.Limits(max_connections=settings.api.max_connections),
            timeout=httpx.Timeout(self.timeout),
            headers={"User-Agent": self.user_agent},
            verify=verify_ssl,  # 明示的なSSL検証
        )
```

---

### 項目5: 入力検証の実装
**必要時間**: 30分
**影響**: HIGH

`utils/api_client.py`に追加:
```python
class BaseAPIClient:
    """入力検証付きベースAPIクライアント"""

    @staticmethod
    def _validate_params(params: dict[str, Any] | None) -> dict[str, Any]:
        """送信前にクエリパラメータを検証"""
        if params is None:
            return {}

        validated = {}
        for key, value in params.items():
            # パラメータ名の形式を検証
            if not key.replace('_', '').replace('-', '').isalnum():
                raise ValueError(f"無効なパラメータ名: {key}")

            # パラメータ値の型を検証
            if not isinstance(value, (str, int, float, bool, list)):
                raise TypeError(f"{key}の無効なパラメータ型")

            # パストラバーサルを防止
            if isinstance(value, str) and '..' in value:
                raise ValueError(f"パラメータにパストラバーサルが検出されました: {key}")

            validated[key] = value

        return validated

    @staticmethod
    def _validate_endpoint(endpoint: str) -> None:
        """エンドポイントパスを検証"""
        # エンドポイントが相対パスであることを確認
        if endpoint.startswith(('http://', 'https://', '//')):
            raise ValueError("エンドポイントは相対パス（プロトコルなし）である必要があります")

        # パストラバーサルを防止
        if '..' in endpoint:
            raise ValueError("エンドポイントでパストラバーサルが検出されました")

    def get(self, endpoint: str, params: dict[str, Any] | None = None,
            headers: dict[str, str] | None = None) -> httpx.Response:
        """検証付きGETリクエスト"""
        self._validate_endpoint(endpoint)
        validated_params = self._validate_params(params)
        return self._make_request_with_retry("GET", endpoint, params=validated_params, headers=headers)
```

`tests/security/test_basic_input_validation.py`にテストを追加:
```python
@pytest.mark.security
class TestInputValidation:
    """入力検証セキュリティテスト"""

    @pytest.mark.asyncio
    async def test_endpoint_path_traversal_prevention(self, async_client):
        """エンドポイントでのパストラバーサル防止"""
        dangerous_endpoints = [
            "../../../etc/passwd",
            "posts/../../admin/users",
            "//etc/passwd",
        ]

        for endpoint in dangerous_endpoints:
            with pytest.raises(ValueError, match="Path traversal"):
                async_client._validate_endpoint(endpoint)

    @pytest.mark.asyncio
    async def test_parameter_validation(self, async_client):
        """クエリパラメータの検証"""
        # 有効なパラメータ
        valid = async_client._validate_params({"id": 1, "name": "test"})
        assert valid == {"id": 1, "name": "test"}

        # 無効なパラメータ名
        with pytest.raises(ValueError):
            async_client._validate_params({"invalid<name>": "value"})

        # 値内のパストラバーサル
        with pytest.raises(ValueError):
            async_client._validate_params({"path": "../../../etc/passwd"})
```

---

### 項目6: CI/CDセキュリティテスト処理の修正
**必要時間**: 20分
**影響**: HIGH

`.github/workflows/ci.yml` 行147-154を更新:
```yaml
- name: Run security tests (Serial - Rate Limit/Auth safety)
  id: security-tests
  run: |
    # GitHub APIレート制限を回避するため、セキュリティテストを順次実行
    # || trueで失敗を無視しない
    uv run pytest -m "security" -v --maxfail=10

- name: Report security test failure
  if: failure() && steps.security-tests.outcome == 'failure'
  run: |
    echo "::error::セキュリティテストが失敗しました。マージ前に発見事項をレビューしてください。"
    exit 1

- name: Report security test success
  if: steps.security-tests.outcome == 'success'
  run: |
    echo "::notice::セキュリティテスト合格 - 重大な脆弱性は検出されませんでした"
```

---

## Medium Priority項目（今月完了）

### 項目7: レート制限の実装
**必要時間**: 45分
**影響**: MEDIUM

`utils/api_client.py`に追加:
```python
from collections import deque
import time

class RateLimiter:
    """トークンバケットレートリミッター"""

    def __init__(self, requests_per_window: int, window_seconds: int):
        self.max_requests = requests_per_window
        self.window = window_seconds
        self.timestamps = deque()

    def is_allowed(self) -> bool:
        """リクエストが許可されているかチェック"""
        now = time.time()

        # ウィンドウ外のタイムスタンプを削除
        while self.timestamps and self.timestamps[0] < now - self.window:
            self.timestamps.popleft()

        if len(self.timestamps) < self.max_requests:
            self.timestamps.append(now)
            return True

        return False

    def wait_if_needed(self) -> float:
        """レート制限の場合は待機、待機時間を返す"""
        if self.is_allowed():
            return 0.0

        oldest = self.timestamps[0]
        wait_time = (oldest + self.window) - time.time()

        if wait_time > 0:
            logger.warning(f"レート制限超過。{wait_time:.2f}秒待機中")
            time.sleep(wait_time)

        # 待機後に最古のものを削除
        self.timestamps.popleft()
        return wait_time

class BaseAPIClient:
    def __init__(self, ...):
        # ... 既存のコード ...

        # レートリミッターを初期化
        self.rate_limiter = RateLimiter(
            requests_per_window=settings.security.rate_limit_requests,
            window_seconds=settings.security.rate_limit_window
        )

    def _make_request_with_retry(self, method: str, endpoint: str, **kwargs):
        """レート制限強制を追加"""
        # リトライ前にレート制限を強制
        self.rate_limiter.wait_if_needed()

        # 既存のリトライロジックを継続
        for attempt in range(self.retry_count + 1):
            try:
                # ... 既存のリクエストコード ...
                pass
            except ...:
                pass
```

テストを追加:
```python
@pytest.mark.security
class TestRateLimiting:
    """レート制限実装テスト"""

    def test_rate_limiter_allows_within_limit(self):
        """レートリミッターが制限内のリクエストを許可"""
        limiter = RateLimiter(requests_per_window=3, window_seconds=1)

        assert limiter.is_allowed()  # 1/3
        assert limiter.is_allowed()  # 2/3
        assert limiter.is_allowed()  # 3/3
        assert not limiter.is_allowed()  # ブロックされるはず

    def test_rate_limiter_resets_after_window(self):
        """レートリミッターが時間ウィンドウ後にリセット"""
        limiter = RateLimiter(requests_per_window=1, window_seconds=0.1)

        assert limiter.is_allowed()  # 制限を使い切る
        assert not limiter.is_allowed()  # ブロック

        time.sleep(0.11)  # ウィンドウの期限切れを待つ

        assert limiter.is_allowed()  # 再度許可されるはず
```

---

### 項目8: エラーメッセージのサニタイズ
**必要時間**: 30分
**影響**: MEDIUM

`utils/api_client.py`に追加:
```python
import re

class APIClientError(Exception):
    """サニタイズ付きベースAPIクライアント例外"""

    @staticmethod
    def sanitize_message(message: str, max_length: int = 200) -> str:
        """情報開示を防ぐためにエラーメッセージをサニタイズ"""
        sanitized = message

        # メールアドレスを削除
        sanitized = re.sub(
            r'[\w\.-]+@[\w\.-]+\.\w+',
            '[EMAIL]',
            sanitized
        )

        # 潜在的なAPIキーを削除（40文字以上の16進数）
        sanitized = re.sub(
            r'[a-f0-9]{40,}',
            '[API_KEY]',
            sanitized,
            flags=re.IGNORECASE
        )

        # URL内の認証情報を削除
        sanitized = re.sub(
            r'https?://[^:]+:[^@]+@',
            'https://[CREDENTIALS]@',
            sanitized
        )

        # JWTトークンを削除（通常3つのbase64パート）
        sanitized = re.sub(
            r'eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+',
            '[JWT_TOKEN]',
            sanitized
        )

        # 長いメッセージを切り詰め
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length] + "..."

        return sanitized

# クライアントでの使用
except Exception as e:
    safe_message = APIClientError.sanitize_message(str(e))

    if settings.is_development():
        logger.debug(f"完全なエラー: {safe_message}")
    else:
        logger.error(f"リクエスト失敗: {safe_message}")
```

---

## タイムラインサマリー

| 項目 | 優先度 | 時間 | 期限 |
|------|----------|------|----------|
| 公開されたAPIキーの削除 | CRITICAL | 15分 | 今日 |
| .env.exampleの作成 | CRITICAL | 5分 | 今日 |
| Pre-commitフック | CRITICAL | 10分 | 今日 |
| SSL設定 | HIGH | 15分 | 今週 |
| 入力検証 | HIGH | 30分 | 今週 |
| CI/CD修正 | HIGH | 20分 | 今週 |
| レート制限 | MEDIUM | 45分 | 今月 |
| エラーのサニタイズ | MEDIUM | 30分 | 今月 |

---

## 検証コマンド

各項目完了後に実行:

```bash
# git履歴がクリーンであることを確認
git log --all --source --oneline | wc -l

# セキュリティテストを実行
uv run pytest tests/security/ -v

# リポジトリ内の秘密情報をチェック
git log -p --all -S "API_KEY" | wc -l  # 0であるべき

# カバレッジ付き完全テストスイートを実行
uv run pytest --cov=. --cov-report=term

# リンティングをチェック
uv run ruff check .

# 型チェック
uv run mypy utils/ config/
```

---

## 成功基準

✅ すべてのCRITICAL項目完了（1-3）
✅ すべてのHIGH優先度項目完了（4-6）
✅ セキュリティテストが警告なしで合格
✅ Pre-commitフックが認証情報コミットをブロック
✅ .envファイルがgitから除外されている
✅ git履歴に露出した秘密情報なし
✅ CI/CDパイプラインがセキュリティテストを強制

---

## デプロイ前に確認すべき質問

- [ ] すべての実際のAPIキーがローテーションされていますか？
- [ ] すべてのブランチで.envがgitから除外されていますか？
- [ ] すべての開発マシンにpre-commitフックがインストールされていますか？
- [ ] セキュリティテストが実行され、合格していますか？
- [ ] 本番環境でSSL検証が有効になっていますか？
- [ ] 本番環境用にエラーメッセージがサニタイズされていますか？

---

**参照**: `SECURITY_AUDIT_REPORT.md`の完全監査レポート
