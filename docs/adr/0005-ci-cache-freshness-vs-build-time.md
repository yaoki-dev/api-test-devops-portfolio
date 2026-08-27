# ADR-0005: CI キャッシュ鮮度 vs ビルド時間のトレードオフ

**Status**: Accepted
**Date**: 2026-08-26
**Context tags**: Docker BuildKit, GitHub Actions cache, Trivy, CI/CD, supply chain

## Context

`ci.yml` と `trivy-scan.yml` は同一 GHA キャッシュ scope（`api-test-runtime`）を
共有する複数ジョブで runtime イメージをビルドする。

- `trivy-scan.yml`（セキュリティゲート）: `cache-from` のみ保持、書き込みなし
  （本 ADR で `no-cache: true` を追加。詳細は後述）
- `ci.yml` `compose-healthcheck`: PR は `cache-from` で読み取り、push は
  `api-test-runtime` scope への writer
- `ci.yml` `publish-image`: `needs: [compose-test, compose-healthcheck, post-trivy-scan]`
  経由で `compose-healthcheck` 完了後に起動し、同じ scope から読んで GHCR へ公開する。
  自身も同 scope への writer（`cache-to` に条件なし）

したがって `api-test-runtime` scope の writer は `compose-healthcheck` と
`publish-image` の 2 つで、いずれも run をまたいで同じ scope を共有する。

Trivy セキュリティゲートは APT 由来の OS パッケージ脆弱性を検出する。しかし
GHA キャッシュはビルド時点のレイヤをそのまま再利用するため、キャッシュヒット時は
`apt-get update`/`upgrade` を伴うレイヤが実行されず、スキャン対象イメージが
「その時点で最新の OS パッケージ」を反映しない場合がある。

本 ADR 以前は `trivy-scan.yml`・`compose-healthcheck` のいずれも `no-cache` を
持たず、双方がキャッシュ再利用のまま動作していた。そのため二段階の問題がある:

- ゲート自身の鮮度: Trivy がスキャンするイメージが `cache-from` 由来の古い
  apt 層で構築され、その時点の OS パッケージ脆弱性を見落としうる
- 公開イメージの鮮度: `compose-healthcheck` が push 時に `api-test-runtime`
  scope へ書き込むレイヤ自体が古いキャッシュから構築され、`publish-image` が
  それを読んで GHCR へ公開する

前者を放置したままでは後者を直しても意味がなく、逆に前者だけを直すと
「ゲートは緑だが公開イメージは脆弱」という偽の安全信号が発生する。
したがってゲート側と writer 側の両方に鮮度保証を同時に入れる。

鮮度を実際に消費するのは `publish-image` のみで、これは `main` push 限定
（`github.ref == 'refs/heads/main'`）で動作する。一方 `compose-healthcheck`
は `compose-test` の起動条件を `needs` 経由で継承し、`main`/`develop` 両方の
push で走る。両ブランチの push 頻度を比較すると、develop push が
main push を大きく上回る（squash merge 運用、実測比は数十倍）。
`no-cache` を push 全体に無条件で適用すると、その大半が `publish-image` で
消費されない cold build になる。

なお `Dockerfile` の base image は digest 直接指定（`FROM
python:3.14-slim@sha256:...`）で、Dependabot が docker ecosystem を
weekly + cooldown 7日で自動更新する。digest 更新のたびに apt 層を含む
全レイヤのキャッシュが無効化されるため、apt 層キャッシュが古くなり続ける
期間には Dependabot の更新間隔という既存の上限が既にかかっている。

## Decision

`compose-healthcheck` の `Build app(runtime) image` ステップに `no-cache` を
追加するが、条件は `cache-to` と揃えず、鮮度を実際に消費する `publish-image`
と同じ `main` push 限定にする。

```yaml
no-cache: ${{ github.ref == 'refs/heads/main' }}
cache-to: ${{ github.event_name != 'pull_request' && 'type=gha,mode=max,scope=api-test-runtime' || '' }}
```

- **PR**: `no-cache` は false（未設定と同義）。`cache-from` でキャッシュを再利用し、
  高速フィードバックを維持する。`cache-to` も無効のため PR 経由の cache poisoning
  経路は発生しない（既存契約を維持）。
- **push（main）**: `no-cache` が true になり、キャッシュ再利用を止めて
  常に最新レイヤで再ビルドする。その結果を `cache-to` で `api-test-runtime`
  scope に書き込む。`publish-image` は `needs` でこのジョブの完了を待ってから
  同じ scope を読むため、GHCR へ公開されるイメージの amd64 側はこの
  「鮮度優先ビルド」のレイヤから構築される。ただしこれが成立するのは
  run が時間的に重ならない場合に限る。arm64 側は `compose-healthcheck` が
  ビルドしないため対象外（いずれも後述の Non-Guarantees を参照）。
- **push（develop）**: `no-cache` は false のためキャッシュを再利用する。
  develop push の apt 層鮮度検証は、無条件で `no-cache: true` を持つ
  `post-trivy-scan`（`trivy-scan.yml`）が別途担っており、ここで重複させる
  必要がない。`cache-to` は push 全体で継続するため PR 側の `cache-from`
  読み取り元は維持される（no-cache と cache-to の条件が異なるのは意図的）。

## Consequences

### Positive

- main push 経路では、Trivy ゲートがスキャンするイメージと GHCR に公開されるイメージの
  双方が、同一 push 実行内で新規ビルドされたレイヤに基づく（amd64 のみ）。
  ゲートは `trivy-scan.yml` 自身の `no-cache` ビルド、公開イメージは
  `compose-healthcheck` が `no-cache` で生成し `api-test-runtime` scope へ
  書き出したレイヤを `publish-image` が再利用したもの。
  本 ADR が保証するのはこの**鮮度のパリティ**であり、両者は独立したビルドのため
  レイヤの**同一性（digest 一致）は保証しない**。同一性を要求する場合は
  公開後の manifest digest を直接スキャンする設計が別途必要になる。
- `compose-healthcheck` の `no-cache` は main push 限定のため、PR および
  develop push の**このジョブの**ビルド速度は変更なし。鮮度を消費しない
  cold build を増やさないという条件設計の狙いはここで達成される。
- ただしビルド時間全体では、本 ADR がゲート側（`trivy-scan.yml`）にも
  無条件 `no-cache: true` を入れるため、`scan-image: true` で起動する
  経路には cold build のコストが新たに発生する:
  - main 向け PR / `docker` ラベル付き PR（`pr-trivy-scan`）
  - develop・main への push（`post-trivy-scan`）

  これはゲート自身の鮮度と引き換えに受け入れるコストであり、
  `compose-healthcheck` 側の条件付き `no-cache` とは独立した判断である
  （ゲートの鮮度は分岐させず常に優先する）。develop push の apt 層鮮度検証を
  `post-trivy-scan` が担えるのはこの無条件 `no-cache` が前提になっている。

### Negative

- main push 時のみ `compose-healthcheck` のビルド時間が増加する（キャッシュ非使用）。
  public repository のため金銭コストへの影響はない。
- `trivy-scan.yml`（ゲート）と `compose-healthcheck`（build 兼 writer）が
  main push 時に同一の runtime イメージを実質的に重複ビルドする設計を維持する。
  push ごとに同じイメージの cold build が 2 回走る。writer を集約すればこの
  重複は解消できるが、ゲートの責務範囲に関わる判断のため本 ADR では
  扱わない（Alternatives Considered の (e) を参照）。
- `no-cache` を main push 限定としたため、develop push の apt 層鮮度検証は
  `post-trivy-scan` のみに依存する。両者は独立したビルドのため、
  `post-trivy-scan` が緑でも `compose-healthcheck` が起動検証する
  イメージの apt 層が同一である保証はない（Non-Guarantees を参照）。

### Non-Guarantees

- 本 ADR は「main push における、ゲートと公開イメージの amd64 レイヤ鮮度の
  パリティ」のみを保証する。`ignore-unfixed: true` による検出範囲の限定は
  ADR-0004 の対象であり、本 ADR はそれを変更しない。
- develop push では `compose-healthcheck` の起動検証イメージと
  `post-trivy-scan` のスキャン対象イメージは独立したビルドであり、
  両者のレイヤが同一である保証はない。develop push の apt 層鮮度は
  `post-trivy-scan`（無条件 `no-cache: true`）が単独で担う。
- Trivy がスキャンするのは `trivy-scan.yml` がローカルにビルドしたイメージであり、
  GHCR に公開された manifest そのものではない。「ゲート緑 = 公開 manifest を
  直接検証済み」ではない点に注意する。
- 鮮度パリティが成立するのは run が時間的に重ならない場合に限る。GHA キャッシュは
  run 単位ではなく scope 単位で共有されるため、複数 push が並行すると、
  `publish-image` の `cache-from` が読むレイヤが自 run の `compose-healthcheck` 由来で
  ある保証はない。`compose-healthcheck` には `concurrency` が無く run 間で直列化
  されないため、この競合は設定上排除されていない。閉じるには writer の単一化、
  branch/commit 単位への scope 分離、または全 writer の同一 `concurrency` 境界への
  収容が必要で、いずれも本 ADR の範囲外とする。
- `publish-image` は `linux/amd64,linux/arm64` のマルチアーキテクチャビルドだが、
  `compose-healthcheck` は単一アーキテクチャ（runner のネイティブ arch）でのみ
  `no-cache` ビルドを行う。arm64 側のレイヤ鮮度は `publish-image` 自身の
  ビルド時点のキャッシュ状態に依存し、本 ADR の対象外。

## Alternatives Considered

`(b)`（`no-cache` を main push 限定にする案）は本 ADR の Decision として採用したため、
不採用案のみを以下に挙げる。

- **(a) `trivy-scan.yml` の `no-cache` のみで完結とする**: ゲート自身は
  新鮮化されるが、writer である `compose-healthcheck` が古いレイヤを
  scope へ書き込み続けるため、GHCR 公開イメージの鮮度は担保されない。
  「ゲート緑 = 公開イメージも安全」という前提が崩れるため不採用。
- **(c) 全ジョブから GHA キャッシュを撤廃**: 鮮度は最大化されるが、PR
  フィードバック速度が大きく低下する。ポートフォリオの CI/CD 実務適合性
  デモという目的に対し過剰なコストであり不採用。
- **(d) writer を 1 ジョブに集約（`compose-healthcheck` を廃止し
  `publish-image` のみが書き込む）**: 冗長ビルドは解消できるが、
  `publish-image` は `main` push 限定（`github.ref == 'refs/heads/main'`）で
  動作するため、develop push 時に `api-test-runtime` scope が更新されなくなり、
  develop 向けの鮮度保証が失われる。既存のジョブ責務分離（healthcheck は
  develop/main 両方、publish は main のみ）を壊すため不採用。
- **(e) ゲート自身を writer にする（`trivy-scan.yml` に push 限定の
  `cache-to` を追加）**: スキャンしたレイヤがそのまま公開側に渡るため amd64 の
  同一性に最も近づき、push あたりの cold build も 1 回減る。本 ADR で採用した
  `github.event_name != 'pull_request'` ガードを使えば PR 経由の cache poisoning も
  防げるため、Negative に挙げた「cache-to を持たない reusable workflow」という
  契約は技術的な障壁ではない。不採用の理由は、reusable なセキュリティゲートの
  責務をキャッシュ供給まで広げると、呼び出し側の CI 構成にゲートが結合し、
  ゲート単体の再利用性が落ちるため。本 ADR の変更より影響が大きく、
  digest 受け渡しによる同一性保証と併せて別途設計する。
- **(f) `no-cache` を push 全体（develop/main）に無条件で適用する**: 当初案。
  鮮度を実際に消費する `publish-image` は main push 限定のため、develop push
  分の cold build は鮮度パリティに寄与しない。develop への push 頻度は main
  への push 頻度を大きく上回る（squash merge 運用、実測比は数十倍）ため、
  無条件適用は cold build コストの大半を無駄にする。develop push の apt 層
  鮮度検証は `post-trivy-scan` が別途担っており、`compose-healthcheck` 側で
  重複させる理由がないため不採用。

## References

- [Docker Build: GitHub Actions cache backend](https://docs.docker.com/build/cache/backends/gha/)
- [`ci.yml`](../../.github/workflows/ci.yml)
- [`trivy-scan.yml`](../../.github/workflows/trivy-scan.yml)
- [ADR-0004: Trivy の修正未提供脆弱性をゲート対象から除外する方針](0004-trivy-ignore-unfixed-policy.md)
- [`tests/unit/test_trivy_workflow_contract.py`](../../tests/unit/test_trivy_workflow_contract.py)
