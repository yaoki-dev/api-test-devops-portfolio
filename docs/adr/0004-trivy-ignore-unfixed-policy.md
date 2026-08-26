# ADR-0004: Trivy の修正未提供脆弱性をゲート対象から除外する方針

**Status**: Accepted
**Date**: 2026-08-25
**Context tags**: Trivy, vulnerability scanning, CI/CD, risk acceptance

## Context

本プロジェクトの Trivy filesystem / image スキャンは、SARIF の可視化と
CRITICAL/HIGH の CI ゲートを兼ねています。現在の workflow は 4 つのスキャンで
`ignore-unfixed: true` を指定しています。

Trivy の公式ドキュメントでは、`--ignore-unfixed` は修正が利用可能な脆弱性だけを
表示する短縮指定であり、`affected`、`will_not_fix`、`fix_deferred`、`end_of_life`
のステータスを除外すると説明されています。したがって、この指定は「脆弱性がない」
ことではなく、「現時点で修正経路がある脆弱性をゲートする」ことを意味します。

## Decision

`ignore-unfixed: true` を維持します。修正未提供の脆弱性は CI の合否判定から除外する
リスク受容として扱い、ポートフォリオや CI の説明で「全脆弱性ゼロ」とは主張しません。
修正が公開された時点で Trivy の結果に現れ、CRITICAL/HIGH ゲートの対象になります。

## Consequences

### Positive

- 修正可能な CRITICAL/HIGH を CI で fail-closed に判定できる。
- ベンダー修正が存在しない項目による恒常的な誤ブロックを避けられる。
- SARIF とゲートの対象条件を一致させ、判断基準を説明できる。

### Negative

- 修正未提供の脆弱性はこの workflow の結果だけでは可視化されない。
- Dependabot alerts、Trivy の定期更新、リリース前の再評価を別途維持する必要がある。

## Alternatives Considered

- **`ignore-unfixed: false`**: 全件を表示できるが、修正不能な項目でゲートが継続的に
  ブロックされ、実行可能な修正の検出と混同しやすい。
- **修正未提供だけを手動で `.trivyignore` に追加**: 除外理由の重複管理と期限切れを
  招くため、Trivy が提供する status-based filtering を採用する。

## References

- [Trivy filtering: ignore-unfixed](https://github.com/aquasecurity/trivy/blob/main/docs/guide/configuration/filtering.md)
- [Trivy vulnerability scanner: unfixed vulnerabilities](https://github.com/aquasecurity/trivy/blob/main/docs/guide/scanner/vulnerability.md)
- [`trivy-scan.yml`](../../.github/workflows/trivy-scan.yml)
- [ADR-0003: CI ジョブ結果の取りこぼしを防ぐ条件設計](0003-ci-result-loss-prevention-conditions.md)
- [Issue #606](https://github.com/yaoki-dev/api-test-devops-portfolio/issues/606)
