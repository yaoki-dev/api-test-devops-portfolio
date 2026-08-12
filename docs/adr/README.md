# Architecture Decision Records (ADR)

本ディレクトリには本プロジェクトの主要な設計判断を ADR (Architecture Decision Records) 形式で記録しています。

## ADR とは

> 「アーキテクチャに関する重要な意思決定を、その文脈・選択肢・採用理由・帰結とともに簡潔に記録する文書」

[Michael Nygard, *Documenting Architecture Decisions* (2011)](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) のテンプレートに準拠。

## 採用フォーマット

各 ADR は以下のセクションを含みます:

| セクション | 内容 |
|---|---|
| **Status** | Proposed / Accepted / Superseded / Deprecated |
| **Date** | 決定日 (ISO 8601: YYYY-MM-DD) |
| **Context** | 判断が必要となった背景・制約・前提 |
| **Decision** | 採用した設計と採用理由 |
| **Consequences** | Positive / Negative / Neutral 影響 |
| **Alternatives Considered** | 検討した代替案と不採用理由 |
| **References** | 関連ADR・実装ファイル・参考文献 |

## ADR 一覧

| 番号 | タイトル | Status | 関連モジュール |
|---|---|---|---|
| [ADR-0001](0001-async-only-github-client.md) | AsyncGitHubClient を Async-only で実装し APIClient を継承しない | Accepted | `utils/github_client.py` |
| [ADR-0002](0002-sync-async-parity-api-client.md) | APIClient の Sync/Async Parity 設計と JSONPlaceholderClient の継承パターン | Accepted | `utils/jsonplaceholder_base_{sync,async}.py`、`utils/jsonplaceholder_client_{sync,async}.py` |

## ADR 追加ルール

新規 ADR 作成時:

1. ファイル名: `NNNN-kebab-case-title.md` (NNNN は連番、ゼロ埋め4桁)
2. 既存 ADR の Status を変更する場合 (Superseded 等)、新 ADR の References に旧 ADR を明記
3. 本 INDEX に追加 (ADR一覧テーブルへの行追加)
4. 関連する README / コメント等のリンクを更新

## Status の遷移

```
Proposed → Accepted → (Superseded by ADR-NNNN | Deprecated)
```

- **Proposed**: 提案中、未承認
- **Accepted**: 採用済み、実装に反映
- **Superseded**: 後続 ADR により上書き (旧ADRはアーカイブ目的で残す)
- **Deprecated**: 廃止、参考のみ
