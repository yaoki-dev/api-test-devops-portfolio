# ADR-0002: APIClient の Sync/Async Parity 設計と JSONPlaceholderClient の継承パターン

**Status**: Accepted
**Date**: 2026-05-08
**Last verified**: 2026-08-31 — 決定は有効。async-only 例外の運用ルールを追記 (「Sync/Async Parity 維持ルール」参照)
**Context tags**: API client design, Sync/Async paradigm parity, inheritance pattern, OOP design

## Context

`utils/api_client.py` (決定時点のファイル構成) の汎用 HTTP クライアント (JSONPlaceholder API 用)
について以下を決定する必要があった:

1. **パラダイム選択**: Sync / Async / 両方
2. **継承構造**: ドメインクラス (`SyncJSONPlaceholderClient`/`AsyncJSONPlaceholderClient`) と汎用クラス (`SyncAPIClient`/`AsyncAPIClient`) の関係

### 判断要素

#### Python エコシステムの両パラダイム併存

| パラダイム | 主流フレームワーク | 案件特性 |
|---|---|---|
| Sync | Django (asyncビューも増加中)、Flask、データ処理スクリプト、CLI | 既存システム連携、レガシー統合、シンプルバッチ |
| Async | FastAPI、real-time/WebSocket、並行 fetch / scraping | モダンマイクロサービス、高並行 I/O、リアルタイム系 |

→ **案件分布は両パラダイム並存**、どちらかに絞るとアピール範囲が半減

#### JSONPlaceholder API の特性

- 認証なし・Rate Limit無のテストAPI
- シンプルCRUD (Posts/Users/Todos/Comments/Albums/Photos)
- パラダイム横断の標準パターン実演に最適 (GitHub APIのような特殊要件なし)

#### 継承 vs Composition の判断

ドメインクラスが汎用クラスから得るもの:
- `__init__` (設定解決・httpxクライアント初期化)
- `__enter__`/`__exit__` または `__aenter__`/`__aexit__` (lifecycle管理)
- `get/post/put/delete/patch` (HTTP動詞)
- `_make_request_with_retry` (retry+error mapping)

ドメインメソッド (`get_posts`, `get_user`, `get_todos`等) は**継承した HTTP動詞を呼ぶだけ**。

## Decision

### 1. Sync/Async 両実装 + Parity 維持

`SyncAPIClient` と `AsyncAPIClient` を並列実装。両者のメソッドシグネチャ・例外契約・リトライ動作を一致させ、`async`/`await` の有無のみを差異とする。

### 2. クラス継承パターン

```
SyncAPIClient                     AsyncAPIClient
    │                                 │
    └─ SyncJSONPlaceholderClient      └─ AsyncJSONPlaceholderClient
```

ドメインクラスは汎用クラスを継承し、ドメインメソッドを追加。

### 3. 共通ロジックは関数抽出で重複削減

```python
# Sync/Async 共通の helper 関数 (決定時点の名前。現在地は「実装位置の変遷」参照)
_resolve_client_config()  # 設定値解決・バリデーション
_classify_error()  # ネットワークエラー分類・ログ出力
_map_request_error()  # httpx例外 → カスタム例外マッピング
exponential_backoff_with_jitter()  # リトライ遅延計算
```

### 実装位置の変遷

`utils/api_client.py` は PR #488 (`a4e3ac5`, 2026-07-11) で基底クラスとドメインクラス、
Sync と Async にファイル分割された。クラス名と継承構造は変更していないため、
上記の継承図は現在も有効。共通 helper は module-private から
`utils/http_helpers.py` の公開関数へ移動し、アンダースコア接頭辞が外れた。

| 対象 | 決定時点 | 現在地 |
|---|---|---|
| `SyncAPIClient` | `utils/api_client.py` | `utils/jsonplaceholder_base_sync.py` |
| `AsyncAPIClient` | `utils/api_client.py` | `utils/jsonplaceholder_base_async.py` |
| `SyncJSONPlaceholderClient` | `utils/api_client.py` | `utils/jsonplaceholder_client_sync.py` |
| `AsyncJSONPlaceholderClient` | `utils/api_client.py` | `utils/jsonplaceholder_client_async.py` |
| `_resolve_client_config()` | `utils/api_client.py` | `utils/http_helpers.py` の `resolve_client_config()` |
| `_classify_error()` | `utils/api_client.py` | `utils/http_helpers.py` の `classify_error()` |
| `_map_request_error()` | `utils/api_client.py` | `utils/http_helpers.py` の `map_request_error()` |
| `exponential_backoff_with_jitter()` | `utils/api_client.py` | `utils/retry.py` |

以降の本文に現れるモジュール名・関数名も、特記なき限り決定時点のもの。現在地は本表を参照。

### 採用理由

#### Sync/Async parity の正当化

1. **両パラダイム対応**: Django/Flask/CLI 案件 (Sync) と FastAPI/並行fetch 案件 (Async) の両方をカバー
2. **DRY 適用済み**: 共通ロジックを `_resolve_client_config` / `_classify_error` / `_map_request_error` に抽出。Sync/Async版間で重複しがちな設定解決・例外マッピングを単一関数化し、保守コストを最小化
3. **学習・切替コスト最小化**: parity を維持することで、片方を理解すれば他方も理解可能、Sync→Async 移行時にAPI差異吸収用ラッパー不要

#### 継承パターンの正当化 (SOLID)

- **LSP 遵守**: HTTP動詞 (`get/post/put/delete/patch`) 契約を維持しつつドメインメソッドを追加。基底クラスとして substitution 可能
- **ISP 遵守**: 利用者は基底クラスの汎用APIも、ドメインAPIも、必要に応じて選択可 (escape hatch 確保)
- **SRP 遵守**: `SyncAPIClient` は「汎用 HTTP通信 + retry + error mapping」、`SyncJSONPlaceholderClient` は「JSONPlaceholder ドメイン契約 (Posts/Users/Todos)」 — 責任が明確に分離
- **boilerplate 最小**: Composition の場合、各HTTP動詞をドメインクラス内でラップする必要が出る。継承では不要

## Consequences

### Positive

- Sync/Async 両案件アピール (案件分布の両側をカバー)
- 共通化により Sync/Async 間の重複コードを最小化 (`_resolve_client_config` / `_classify_error` / `_map_request_error` 等で関数抽出)
- Generic + Domain の階層分離が教科書的 OOP 適用 (採用面接で説明しやすい)
- 利用者は汎用APIにも escape hatch でアクセス可

### Negative

- コード行数は単一パラダイム比で増加
- Sync/Async parity を維持する自己規律が必要 (片方だけメソッド追加するドリフト防止)

### Neutral

- AsyncGitHubClient は本ADRと**別判断** (ADR-0001参照)。API特性駆動で非対称な実装範囲を選択

## Alternatives Considered

| 代替案 | 不採用理由 |
|---|---|
| Async のみに絞る | Django/Flask/CLI 案件で弱い。案件分布の半分を逃す |
| Sync のみに絞る | FastAPI/モダン Python トレンドへの追随を示せない |
| Composition (`has-a APIClient`) | LSPが成立する状況では Inheritance の方が boilerplate 少。各HTTP動詞ラップが冗長 |
| 1クラス統合 (汎用+ドメイン混在) | SRP違反、責務混在、再利用性低下 |
| Protocol/ABC で共通契約抽出 | 現時点では実装数2-3 (over-engineering)。将来クライアント追加時に再検討 |

## Sync/Async Parity 維持ルール

将来の変更時に parity ドリフトを防ぐ運用ルール:

1. **新規ドメインメソッド追加時**: Sync/Async の両クラスに同時追加
   (`utils/jsonplaceholder_client_sync.py` と `utils/jsonplaceholder_client_async.py`)
2. **共通ロジック変更時**: `utils/http_helpers.py` の `resolve_client_config` / `classify_error` /
   `map_request_error` への関数抽出を優先
3. **テスト**: `tests/unit/` に Sync/Async 両方のテストを並列維持
4. **async-only 例外の扱い**: 並行実行それ自体が実演対象であるメソッドに限り、Sync 側の対応実装を持たない
   async 専用メソッドを許容する。許容は暗黙にせず、`tests/unit/test_api_parity.py` の
   `INTENTIONALLY_ASYNC_ONLY` allowlist に「メソッド名 → 理由」として明示的に登録する。
   allowlist に無い非対称は parity 契約テストが失敗させる（= 既定は parity 維持、例外は明示的 opt-in）。
   理由の記述は実装が用いる並行機構を指すため、機構を変更した場合は allowlist の理由も同時に更新する。

## References

- 実装 (基底): `utils/jsonplaceholder_base_sync.py` (`SyncAPIClient`)、
  `utils/jsonplaceholder_base_async.py` (`AsyncAPIClient`)
- 実装 (ドメイン): `utils/jsonplaceholder_client_sync.py` (`SyncJSONPlaceholderClient`)、
  `utils/jsonplaceholder_client_async.py` (`AsyncJSONPlaceholderClient`)
- 共通 helper: `utils/http_helpers.py`、`utils/retry.py`、`utils/exceptions.py`
- 関連 ADR: ADR-0001 (Async-only GitHub Client)
- Liskov Substitution Principle / Single Responsibility Principle: Robert C. Martin, "Clean Architecture"
- httpx Sync/Async parity: https://www.python-httpx.org/async/
