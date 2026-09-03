# ADR-0006: 非冪等 HTTP メソッドのリトライ方針

- **Status**: Accepted
- **Date**: 2026-08-31
- **Decision owners**: API client maintainers

## Context

共通 HTTP 基盤のリトライは、通信障害や 5xx 応答から復旧するための機能です。一方、書き込み系の要求を自動再送すると、サーバーが最初の要求を処理した後に応答だけ失われ、作成や更新の重複を招くおそれがあります。`retry_count` の値だけで全 HTTP メソッドを同じように再送する設計は、呼び出し側に意図しない副作用を与えるため、安全な既定値になりません。

## Decision

1. 既定でリトライを許可するメソッドを `GET`、`HEAD`、`DELETE`、`OPTIONS`、`TRACE` に限定する。`PUT` はHTTPの意味上は冪等でも、実サーバーの実装差を安全側に扱うため既定では再送しない。
2. `POST`、`PATCH`、`PUT` は、`retry_non_idempotent=True` を呼び出し単位で明示した場合だけ設定済み回数まで再送する。呼び出し側は、Idempotency-Key またはサーバー側の重複排除契約を確認してから指定する。
3. 上記以外のメソッドは、明示的なオプトインがない限り 1 回だけ実行する。これは未知のメソッドを安全側に倒すためである。
4. ポリシー判定は `utils/http_helpers.py` に集約し、Sync / Async の共通基盤から利用する。実効試行回数、抑制理由、最終原因は `APIRetryError` に保持する。
5. JSONPlaceholder の公開ドメインメソッドにも同じオプトインを公開する。実APIへ接続するテストは `external` マーカーで通常のCI選択から分離する。

## Consequences

### Positive

- 副作用のある `POST` / `PATCH` / `PUT` の意図しない重複送信を既定で防止できる。
- Sync / Async で同じポリシーを共有し、実効試行回数とエラー理由を観測できる。
- オプトインが必要なため、重複排除契約の確認をコードレビューの対象にできる。

### Negative

- `POST` / `PATCH` / `PUT` は、既存の呼び出し側が明示的に変更しない限り復旧性が下がる。
- このクライアントは `Idempotency-Key` の生成・保存・サーバー契約の検証までは行わない。
- `PUT` は既定の復旧性を下げる。再送する場合は、HTTP上の冪等性だけでなく実際のサーバー実装と重複排除契約を呼び出し側で確認する必要がある。

## Alternatives Considered

### 全メソッドを従来どおり再送する

実装差分は最小だが、要求処理済み・応答消失のケースで副作用を重複させるため不採用とした。

### 設定ファイルで非冪等リトライを一括有効化する

設定漏れや意図しない全呼び出しへの波及を招くため不採用とした。リスクのある操作は呼び出し箇所で明示する。

### `POST` / `PATCH` / `PUT` を常に禁止する

サーバー側の重複排除契約がある安全な利用まで妨げるため不採用とした。

## References

- `utils/http_helpers.py`
- `utils/exceptions.py`
- `utils/jsonplaceholder_base_sync.py`
- `utils/jsonplaceholder_base_async.py`
- `utils/jsonplaceholder_client_sync.py`
- `utils/jsonplaceholder_client_async.py`
- `tests/unit/test_http_helpers.py`
- `tests/unit/test_jsonplaceholder_base_sync.py`
- `tests/unit/test_jsonplaceholder_base_async.py`
- `tests/unit/test_api_parity.py`
