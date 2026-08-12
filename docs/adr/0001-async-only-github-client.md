# ADR-0001: AsyncGitHubClient を Async-only で実装し APIClient を継承しない

**Status**: Accepted
**Date**: 2026-05-08
**Last verified**: 2026-08-06 — 決定は有効。実装位置の変更 (「実装位置の変遷」参照) に加え、公開メソッドの戻り値が parsed JSON から検証済み Pydantic モデルへ変わった (「AsyncAPIClient との契約差異」参照)。継承しない判断はこの変更で論拠がむしろ強まっている。
補足 (2026-08-06 実測): 採用理由 1 が挙げる並行 fetch は**現時点で未行使**。`AsyncGitHubClient` を `asyncio.gather` / `TaskGroup` / `Semaphore` へ渡す fan-out 経路は本番・テストとも 0 件。Async-only の判断自体は「同期 caller 不在」と SRP/LSP の論拠から独立に成立するため決定は変わらないが、並行 fetch は実現済みの便益ではなく設計上の余地にとどまる。あわせて、将来の fan-out に備えて接続プール上限を `AsyncGitHubClient(max_connections=10)` として明示化した (「GitHub API の特性」参照)。受け付ける範囲は 1..100 で、上限は GitHub の同時リクエスト制限そのものに一致させている
**Context tags**: API client design, Async/Sync paradigm, GitHub API integration, inheritance vs composition

## Context

GitHub API クライアント (`utils/github_client.py`) の実装パラダイム選択と、汎用APIクライアント (`AsyncAPIClient`) との関係を決定する必要があった。判断要素:

### GitHub API の特性

- **認証あり**: Personal Access Token / OAuth
- **Rate Limit**: 認証なし 60 req/h、認証あり 5000 req/h
- **同時接続の上限**: 同時 100 リクエスト (REST/GraphQL 共有) を超えないことが secondary
  rate limit として文書化されている。httpx の既定 `max_connections` も偶然 100 のため、
  未設定だとプール飽和と API 拒否が同時に起き、マージンが残らない
- **ETag による Conditional Requests**: 304 Not Modified でレスポンスボディ省略・帯域節約
- **想定ユースケース**: CI/CD での複数リポジトリ状態取得、Dashboard 集計クエリ、Rate Limit 内で多数リクエストを効率消化

### AsyncAPIClient との契約差異

| 項目 | AsyncAPIClient | AsyncGitHubClient |
|---|---|---|
| 戻り値型 | `httpx.Response` | 検証済み Pydantic モデル (`GitHubUser` / `list[GitHubRepo]` / `GitHubRepo`) |
| リトライ対象例外 | `httpx.RequestError` + 5xx (`raise_for_status`) | 5xx + `TimeoutException` + `NetworkError` + `RemoteProtocolError` |
| 4xx 分類 | 一律 `APIHTTPError` | 403→Rate Limit vs Forbidden、404→`NotFoundError`、429→`RateLimitError` |
| キャッシュ層 | なし | ETag + data 二重キャッシュ (304対応) |
| ヘッダー戦略 | 汎用 (`Content-Type: application/json`) | GitHub特化 (`Accept: application/vnd.github+json`) |
| 例外チェーン方針 | `from e` (チェーン維持) | `from None` (PII漏洩防止) |
| クライアント生成 | `__init__` 内 | `__aenter__` 内 (lazy) |

304 Not Modified でキャッシュから復元した場合も、公開メソッドは同じ検証パス
(`validate_parsed_model` / `validate_parsed_model_list`) を通すため、200 応答時と同一の
Pydantic モデル型を返す。

### 同期 caller の存在検証

`scripts/` および `tests/` 配下を `AsyncGitHubClient` で grep して確認 (2026-08-05 再実測):

- `scripts/`: 参照 0件
- `tests/`: 6ファイルが参照 (`tests/unit/test_github_client.py`、`test_github_client_etag.py`、
  `test_github_client_lifecycle.py`、`test_github_client_rate_limit.py`、`test_github_client_request.py`、
  `tests/integration/test_github_api.py`)。いずれも `async with AsyncGitHubClient` 形式で、
  同期コンテキストマネージャとしての利用は 0件

→ 同期 caller 不在を実証

## Decision

**`AsyncGitHubClient` のみ実装し、Sync版を作成しない**。
**`AsyncAPIClient` を継承せず、独立クラスとして実装する**。

### 採用理由

#### 1. Async-only の正当化

- **並行fetch の恩恵が大きい**: `asyncio.gather` で user + repos + repo詳細を同時取得 → 各リクエストの I/O 待機を重ね合わせ、直列実行時の待機時間の総和を回避できる
- **ETag/RateLimit 機能の親和性**: Conditional Requests (304) と Rate Limit 監視 (`X-RateLimit-Remaining`) は並行リクエスト前提で価値が高い
- **同期caller 不在**: YAGNI 原則により Sync版追加を回避
- **`asyncio.run()` で同期 caller も将来対応可能**: 必要時の代替パス確保

#### 2. 継承しない正当化 (LSP / SRP / ISP の観点)

- **LSP 違反回避**: 同名メソッドで戻り値契約が異なる (`httpx.Response` vs `GitHubUser` / `list[GitHubRepo]` / `GitHubRepo`) ため、継承して override すると Liskov 置換原則違反
- **SRP 確保**: `AsyncAPIClient` は「汎用retry付きHTTPラッパー」、`AsyncGitHubClient` は「GitHub API契約 + ETag/RateLimit運用」— 別責務
- **ISP 確保**: GitHub クライアント利用者は `_make_request_with_retry` 等の低レベルAPIを必要としない
- **Override コスト過大**: 継承後に共通残部ゼロ (リトライロジック・4xx分類・キャッシュ層・ライフサイクル全て GitHub固有要件)

### 共通化の範囲

継承せずとも以下を**水平共有**:

```python
# github_client.py から api_client.py の利用 (決定時点のモジュール構成)
from utils.api_client import (
    ASYNC_FATAL_EXCEPTIONS,  # システム例外定数
    APIClientError,  # 例外基底
    exponential_backoff_with_jitter,  # 汎用 utility
)


class GitHubAPIError(APIClientError):  # 例外階層連結
    """GitHub API基底例外"""
```

→ 「継承による垂直共有」ではなく「utility/exception base による水平共有」を選択

#### 実装位置の変遷

上記コードブロックは決定時点 (2026-05-08) のモジュール構成を示す。`utils/api_client.py` は
その後 PR #488 (`a4e3ac5`, 2026-07-11) で責務ごとに分割され、共有元が以下へ移動した。

| 共有対象 | 決定時点 | 現在地 |
|---|---|---|
| `ASYNC_FATAL_EXCEPTIONS` | `utils/api_client.py` | `utils/exceptions.py` |
| `APIClientError` | `utils/api_client.py` | `utils/exceptions.py` |
| `exponential_backoff_with_jitter` | `utils/api_client.py` | `utils/retry.py` |
| `GitHubAPIError` の定義 | `utils/github_client.py` | `utils/github_error_handler.py` |

この分割は本 ADR の決定を変更していない。むしろ、共有対象が汎用クライアント実装から
独立した専用モジュール (`utils/exceptions.py` / `utils/retry.py`) へ切り出されたことで、
本 ADR が選択した「utility/exception base による水平共有」がより明確な形になった。
`AsyncGitHubClient` は現在も `AsyncAPIClient` 系のクラスを継承していない。

## Consequences

### Positive

- 単一実装による保守コスト最小化 (Sync版二重実装なし)
- ETag による Conditional Requests、Rate Limit ヘッダー監視、PII redaction を Async 並行制御と統合して実装
- LSP違反を回避し、`AsyncAPIClient` の汎用契約を破壊しない
- 例外階層連結により呼び出し側で `try ... except APIClientError` で両クライアントの基底エラーを統一捕捉可能

### Negative

- 同期コードベースへの統合時に `asyncio.run()` ラップが必要
- 共通化を utility/例外基底レベルに留めるため、リトライロジック自体は両クライアントで個別実装 (リトライ条件判定とバックオフ適用箇所が概念的に重複する。重複量は未計測)

### Neutral

- JSONPlaceholderClient との非対称設計 (両実装 vs Async-only) は **API特性駆動の意図的選択** (詳細は ADR-0002 参照)

## Alternatives Considered

| 代替案 | 不採用理由 |
|---|---|
| Sync版も実装 | 同期caller不在 (YAGNI違反)、ETag/RateLimit機能は並行制御前提で価値発揮、保守コスト倍増 |
| `AsyncAPIClient` 継承 | LSP違反 (戻り値型契約差異)、override後の共通残部ゼロ |
| Composition (`has-a AsyncAPIClient`) | リトライ条件・4xx分類が AsyncAPIClient と異なるため delegated method 内で再実装が必要、利益なし |
| Protocol/ABC で共通契約抽出 | 現時点で実装数2 (over-engineering)、契約差異が大きく抽象化困難 |

## References

- 実装: `utils/github_client.py` (`AsyncGitHubClient`)
- 実装 (補助モジュール): `utils/github_error_handler.py` (例外階層・4xx/5xx 分類)、
  `utils/github_etag_cache.py` (ETag + data 二重キャッシュ)、
  `utils/github_rate_limit.py` (Rate Limit ヘッダー解析)
- 水平共有元: `utils/exceptions.py` (例外基底・fatal 例外定数)、`utils/retry.py` (バックオフ計算)
- 関連 ADR: ADR-0002 (Sync/Async Parity for APIClient)
- GitHub REST API v3: https://docs.github.com/rest
- ETag/Conditional Requests: https://docs.github.com/rest/overview/resources-in-the-rest-api#conditional-requests
- Liskov Substitution Principle: Robert C. Martin, "Clean Architecture" (2017)
