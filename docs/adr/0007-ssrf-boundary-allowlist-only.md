# ADR-0007: SSRF 境界を設定層の allowlist 単層に定める

- **Status**: Accepted
- **Date**: 2026-09-04
- **Decision owners**: Config / security maintainers

## Context

`config/settings.py` は外部 API のベース URL を受け取ります。ここは SSRF の攻撃面であり、
`REVIEW.md` §3「URL / SSRF Protection」は Blocking 要件として localhost、loopback、private IP、
link-local、metadata IP への通信防止を求めています。

本モジュールにはこの要件に対応する 2 系統のコードが並存していました。

1. `_validate_base_url_with_allowed_domains()` — ホスト名を許可リストと突き合わせる純粋関数
2. `is_private_ip()` → `_resolve_hostname()` → `_resolve_hostname_cached()`（`lru_cache`）
   → `_check_ip_private()` → `PRIVATE_IP_RANGES` — DNS を解決して解決後アドレスを判定する 5 段の系統

2 の系統は本番コードから一度も呼ばれていませんでした。Pydantic の validator が呼ぶのは 1 だけで、
2 を参照していたのはテストコードだけです。つまり実効的な境界は最初から allowlist 単層であり、
2 は要件充足の外観だけを与える死コードでした。どちらが有効な境界かはコードからは判別できず、
読み手は呼び出し元を辿るまで誤解します。

`validate_base_url()` の docstring には当初から
「設定バリデータは allowlist-only の純粋関数（I/O なし）として保つ。DNS 解決や private-IP 判定は
構成読み込み時に実行しない」と書かれており、docstring と死コードが矛盾していました。

なお、このモジュールが検証するのは `base_url` だけです。HTTP クライアントの `get()` / `post()` に
渡す `endpoint` はこの検証を通りません。httpx の `Client._merge_url()` は、渡された値が
`httpx.URL.is_relative_url` を満たさない場合、`base_url` を無視してその値を単独の宛先にします。
満たす場合は `base_url` のパスへ連結します。scheme を持つ URL だけがこの分岐で非相対と判定され、
`//host/path` 形式は相対として `base_url` のホストに吸収されます。
現時点で `endpoint` に渡る値は 14 種すべてが `/posts` や `/users/` のような固定リテラルで始まり、
そこに `int` 型 ID か `AsyncGitHubClient.get_user()` の `username` のような `str` 引数が
埋め込まれる形です。先頭が固定リテラルである限り値は常に相対と判定されるため、埋め込み側に
絶対 URL・`//host` 形式・`../` のいずれを入れても `base_url` のホストからは離れられません
（httpx 0.28.1 の実装と実測の双方で確認）。

## Decision

1. SSRF の境界を、設定層の **allowlist 単層**と定める。許可リストに無いホストは、
   ドメイン名か IP リテラルかを問わずすべて拒否する（deny-by-default）。
   本境界の対象は、設定由来で外部から与えられる `APIConfig.base_url` である。
   `utils/github_client.py` の `BASE_URL` はコード内の固定リテラルで外部入力を
   受けないため SSRF の攻撃面ではなく、対象に含めない。
   `get()` / `post()` に渡す `endpoint` も対象に含めない（理由は Context 末尾を参照）。
   外部からの受信エンドポイントを追加した場合、または `endpoint` の先頭自体が外部由来の
   値になる場合は、本境界を再評価する。
   allowlist の次元はホスト名のみとし、ポートは含めない。`base_url` と `ALLOWED_DOMAINS`
   はいずれも同一の運用者が管理する設定境界（環境変数・`.env`）から読み込むため、非既定
   ポートを指定できる主体は allowlist 自体も書き換えられる。加えて既定の許可ホストはすべて
   公開ホストであり、production / staging では `https` を強制している。したがって非既定
   ポートを拒否しても内部ネットワークへの到達を防ぐ効果はなく、`(hostname, port)` 単位の
   allowlist は単層設計を崩す割に防御を増やさない。`base_url` が運用者以外の入力源から
   与えられる構成へ変わった場合は、本判断を再評価する。
2. 設定読み込み時に DNS を解決しない。解決してから判定する設計は、解決と実際の接続の間に
   アドレスが変わる TOCTOU と DNS rebinding を招き、さらにテストの決定性を損なう。
3. 上記に伴い、`PRIVATE_IP_RANGES` / `_check_ip_private()` / `_resolve_hostname_cached()` /
   `_resolve_hostname()` / `is_private_ip()` と、それらのためだけの import を削除する。
4. 解決後アドレスに対する実効的な遮断が要件になった場合は、設定層ではなく egress 層
   （プロキシ、ネットワークポリシー、HTTP トランスポートのフック）に置く。
5. `REVIEW.md` §3 の「内部ネットワーク保護」に、上記 1〜2 を満たす場合は設定バリデータ側に
   独立した private IP 判定を置かなくてよい旨の条件節を補足する。要件そのもの（通信を防止すること）は
   変更しない。

## Consequences

### Positive

- 「SSRF はどこで防いでいるか」に答えるまでに読む層が 1 つになる。削除前は allowlist 系統と
  DNS/IP 系統の 2 系統が並存し、有効な方を判別するのに呼び出し元の追跡が必要だった。
- 設定バリデータが I/O のない純粋関数になり、テストがネットワークとタイミングから独立する。
  モジュール全体を覆っていた DNS 決定論化の autouse fixture が不要になった。
- TOCTOU と DNS rebinding を、防ぎきれない場所で防ごうとする設計を持たなくなった。
- コードが docstring に追いついた。

### Negative

- 許可リストの運用が唯一の防御線になる。許可リストに private ホストを入れれば、それは通る。
  ただしこれは削除前も同じで、`is_private_ip()` は validator から呼ばれていなかったため挙動は変わらない。
- 解決後アドレスに対する遮断は現時点で未実装である。必要になった時点で egress 層に置く。

### Neutral

- テストケースが差引 43 件減った（1616 → 1573）。削除したコードと、そのコードだけを対象に
  していたテストが 46 件対応して消え、allowlist の適用範囲を固定する回帰ケースを 3 件
  （userinfo 形式の authority 混同、末尾ドット FQDN、許可ホスト＋非既定ポート）追加した
  ためで、カバレッジは 97.80% で変化しない。
  件数は品質ゲートと同じ条件（`-m "(unit or integration) and not external"`）での収集数である。
- 追加した 3 件は現行実装で既に通る。新たな欠陥を修正するものではなく、ホスト判定が
  `urlparse().hostname` から `netloc` へ退行した場合や、port が検証次元に加わった場合などに
  失敗させるための回帰ガードである。

## Alternatives Considered

### `is_private_ip()` を validator の本番経路へ配線する

要件文の字面には最も忠実だが、採用しない。設定読み込み時に DNS を引くことになり、
TOCTOU と DNS rebinding を新たに持ち込む。テストがネットワーク解決に依存して不安定になる。
さらに `test_ssrf_domain_allowlist_enforced` の docstring が契約を明文で固定しており、
配線はこの契約テストと正面から衝突する。

```text
このvalidatorはallowlist判定のみでDNS解決やprivate-IP判定を行わない契約を検証する。
```

### DNS を引かず、IP リテラルのみ private 判定する

配線より軽く TOCTOU も避けられるが、得られる防御が allowlist と重複する。
許可リストに無い IP リテラルは既に拒否されるため、新たに防げるものが無い。
判定層が 1 つ増える分だけ読み手の負荷が上がる。

## References

- 実装: `config/settings.py`（`_validate_base_url_with_allowed_domains`、`ALLOWED_DOMAINS`）
- 契約テスト: `tests/unit/test_config_settings.py`（`TestSSRFPrevention`）
- 要件: `REVIEW.md` §3「URL / SSRF Protection」
- [OWASP: Server Side Request Forgery Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
