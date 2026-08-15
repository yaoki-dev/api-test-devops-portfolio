# ADR-0003: CI ジョブ結果の取りこぼしを防ぐ条件設計

**Status**: Accepted
**Date**: 2026-08-15
**Context tags**: CI/CD, GitHub Actions, security gate, fail-closed design, Trivy

## Context

CI/CD パイプラインで「チェックが実行されなかった」状態が「チェックに合格した」状態と
区別されないまま緑になる欠陥が 2 件発生した。いずれも条件式の設計ミスに起因する。

セキュリティゲートにおいて、この区別の喪失は最も危険な失敗モードです。脆弱性を
検出しなかったのか、そもそもスキャンが走らなかったのかを CI の結果から判別できません。

### Bug CRITICAL-2: image scan の skip 状態が検出されない

**症状**: `docker-build` が失敗しても `verify-image-scan` が実行され、検証が通ってしまう。

当時の条件式:

```yaml
- name: Verify image scan execution
  if: always() && github.base_ref == 'main'  # docker-build 失敗を無視
```

`always()` は前段ステップの結果を一切参照しません。そのため `docker-build` の失敗で
`image-scan` が skip された場合でも verify が走ります。さらに `github.base_ref == 'main'`
という条件は「どのブランチ宛の PR か」を見ているだけで、スキャンの実行有無とは
無関係です。

### Bug CRITICAL-3: status-report が一部ジョブ結果を含まない

**症状**: `status-report` ジョブのサマリに `pr-trivy-scan` と `pr-md-quality-check` の
結果が現れない。

当時の定義:

```yaml
status-report:
  needs: [pr-validation, ...]  # pr-trivy-scan / pr-md-quality-check 未指定
```

`needs` に列挙されていないジョブの結果は `needs.<job>.result` から参照できません。
その結果、Trivy スキャンの失敗はパイプライン全体のサマリに反映されず、
レビュアーの見落とし経路になります。

## Decision

### 1. verify ステップは `!cancelled()` と前段 outcome の組み合わせで守る

```yaml
- name: Verify image scan execution
  id: verify-image-scan
  if: inputs.scan-image && !cancelled() && steps.image-scan.outcome != 'skipped'
```

- `!cancelled()` — 前段が失敗しても verify を走らせるが、ワークフローがキャンセル
  された場合は即座に停止する。GitHub 公式は critical task での `always()` を非推奨と
  し、`!cancelled()` を推奨代替として挙げている
- `steps.image-scan.outcome != 'skipped'` — スキャン自体が走らなかった場合は verify を
  実行しない。skip の検出は後段の「Fail job if ...」ステップが担う

filesystem 側 (`verify-fs-scan`) も同じ方針で `if: "!cancelled()"` を使います。
両者の対称性は重要です。過去には fs 側だけ `!cancelled()` へ移行し、image 側を
`always()` のまま取り残した非対称が約 1 か月生存しました。

この対称性は契約テスト `tests/unit/test_trivy_workflow_contract.py` の
`test_reusable_trivy_verify_steps_are_cancellable` で固定している。

### 2. skip は明示的にジョブ失敗へ昇格させる（fail-closed）

verify やゲートが `skipped` で終わった場合、それを成功と解釈しない。

```yaml
- name: Fail job if image vulnerabilities found or verification failed
  if: |
    inputs.scan-image && !cancelled() && steps.docker-build.outcome == 'success' && (
      steps.image-scan.outcome == 'skipped' ||
      steps.image-gate.outcome == 'skipped' ||
      steps.verify-image-scan.outcome == 'failure' || ...
    )
  run: |
    echo "::error::..."
    exit 1
```

### 3. status-report は集約対象ジョブをすべて `needs` に列挙する

```yaml
status-report:
  needs: [pr-validation, pr-trivy-scan, pr-md-quality-check, ...]
```

この列挙漏れは静的に検出しにくいため、契約テスト
`test_status_report_keeps_required_trivy_job_ids` で `needs` への
`pr-trivy-scan` / `post-trivy-scan` の存在を固定している。

## Consequences

### Positive

- スキャン未実行とスキャン合格が CI の結果から区別できる（fail-closed）
- ワークフローのキャンセルが verify ステップで遅延しない
- 契約テストにより、同じ条件式のドリフトが再発した時点で CI が落ちる

### Negative

- 条件式が長くなり、一見して意図が読み取りにくい。本 ADR が意図の参照先となる
- 契約テストが `if` 条件の文字列に依存するため、意味を変えないリファクタでもテスト
  修正が必要になる場合がある

### Neutral

- `!cancelled()` と `always()` は非キャンセル時の挙動が同一であるため、通常の成功・
  失敗パスでの動作は変わらない。差が出るのはキャンセル時のみ

## Alternatives Considered

| 代替案 | 不採用理由 |
|---|---|
| `always()` を維持 | GitHub 公式が critical task で非推奨。キャンセル時も実行され続け、キャンセルが即座に効かない |
| 条件を付けず verify を常時実行 | 実行されなかったスキャンに対して verify が失敗し、原因の切り分けが困難になる |
| upload ステップの `always()` も `!cancelled()` へ統一 | upload は `verify-*.outcome == 'success'` に依存するため、verify 到達前のキャンセルでは upload も走らない。差が出るのは verify 成功後にキャンセルが届く狭い窓だけで、そこで走るのは検証済み結果の保全であり意図した動作である（GitHub 公式も `always()` の用途として「キャンセル時でもログや結果を送る」を挙げる）。統一は既存の `outcome != 'cancelled'` ガードを弱める変更も伴う |
| cleanup の `always()` も変更 | イメージ削除はキャンセル後にも必要な後始末であり、`always()` が正当な用途 |
| 条件判定を Composite Action 内へ移す | Action は SARIF 検証という単一責務を持つ。実行可否の判断はワークフロー側の関心事であり、混在させると責務が不明瞭になる |

## References

- 実装: `.github/workflows/trivy-scan.yml`、`.github/workflows/ci.yml`
- 契約テスト: `tests/unit/test_trivy_workflow_contract.py`
- 運用リファレンス: [CI/CD Pipeline](../reference/ci_cd_pipeline.md)
- [GitHub Actions: Evaluate status of jobs and steps](https://docs.github.com/en/actions/reference/workflows-and-actions/expressions#status-check-functions)
- [GitHub Actions: Workflow cancellation](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-cancellation) — キャンセル時にサーバが未完了ステップの `if` を再評価する挙動の根拠
