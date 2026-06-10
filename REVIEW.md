# Review Instructions (api-test-devops-portfolio)

このドキュメントは、本プロジェクトにおける AI および人間によるコードレビューの永続的な基準を定義します。

## 重大度定義 (Severity Levels)
- 🔴 [blocking]: 修正必須。セキュリティやPIIの漏洩、正確性バグ、リソースリーク、本番障害、テスト不能、CI失敗につながる致命的な不具合に限定
- 🟡 [suggested]: 修正推奨。設計好み、保守性/可読性/ログ品質の向上。
- 🟢 [nit]: 軽微。タイポや個人の好みの範疇。

## 永続的指示 (Permanent Instructions)

### 1. セキュリティ & PII保護 (🔴 Blocking)
- **例外メッセージ**: `json.JSONDecodeError` や `httpx.Response` の body を、例外クラスの `__init__` やログメッセージに直接含めてはならない。
- **リダクション**: 機密情報を含む可能性がある body は、`utils/github_client.py` の手法に従い、SHA256 でハッシュ化（指紋化）するか、完全にマスクすること。
- **SecretStr**: API キー等の機密設定は必ず `pydantic.SecretStr` を使用し、誤った露出を防止すること。
- **入力検証**:
  - **入力検証**: 外部入力は用途に応じて Pydantic、Enum、allowlist、URL parser、正規表現などで検証し、Injection、SSRF、パストラバーサル等の攻撃面を増やさないこと。特に外部APIの識別子、URL、認証情報、ファイルパスに相当する値は厳格に検証すること。
- **ログ・例外への露出禁止**: 外部APIレスポンス body、認証ヘッダー、URL query、例外オブジェクト、request/response dump をログ・例外・assertion failure に直接含めないこと。

### 2. 非同期処理 & 通信 (🔴 Blocking)
- **AsyncClient**: `httpx.AsyncClient` は原則として `async with` で管理し、確実にクローズすること。
- **キャンセル安全性**: `asyncio.CancelledError` を考慮し、中断時もリソースリークが発生しない設計にすること。
- **リトライ**: リトライには exponential backoff with jitter を使用し、429/5xx 等の一時的失敗に限定すること。

### 3. URL / SSRF Protection (🔴 Blocking)
- **URL構造検証**: 外部URLを受け取る場合は、scheme、hostname、port、allowlist を検証すること。
- **内部ネットワーク保護**: localhost、loopback、private IP、link-local、metadata IP への通信を防止すること。
- **prefix判定禁止**: URL検証では文字列 prefix 判定だけに依存せず、`urlparse` 等で構造化して検証すること。

### 4. 可観測性 (🟡 Suggested)
- **構造化ログ**: `structlog` を用い、`event`, `error_type`, `endpoint`, `method` 等のキーを一貫して使用すること。
- **例外チェーン**: 例外を再ラップする際は、必ず `raise ... from e` を使用し原因を保持すること。

### 5. テスト品質 (🟡 Suggested)
- **決定論**: `respx` を活用し、ネットワークに依存しない非同期テストを維持すること。
- **AAAパターン**: Arrange-Act-Assert の構造を明確にし、テストの可読性を保つこと。
- **テスト債務分離**: unit / integration / smoke / external / performance の責務を混在させないこと。

### 6. CI / 品質ゲート (🟡 Suggested)
- **品質ゲート**: ruff, mypy, pytest, coverage, gitleaks, trivy の失敗を無視しないこと。
- **外部API分離**: PR で実 API に依存するテストを実行しないこと。外部 API テストは weekly/manual に分離すること。
- **flaky test対策**: flaky test は sleep で隠さず、原因を特定して deterministic に修正すること。
- **実行戦略**: PRでは deterministic な unit/integration を優先し、external/performance は weekly/manual に分離すること。

### 7. 型安全性 & 設定管理 (🟡 Suggested)
- **Any制限**: `Any` の使用は境界層・JSON処理など必要な箇所に限定すること。
- **設定注入**: 環境変数は Settings 経由で読み込み、テストでは monkeypatch や fixture で明示的に注入すること。
- **Secret露出防止**: Secret 値を repr/log/assertion failure に露出させないこと。

### 8. 依存関係 & サプライチェーン (🟡 Suggested)
- **lockfile管理**: lockfile を更新する場合は、差分の理由を明示すること。
- **依存追加審査**: 依存関係の追加は、用途、代替案、メンテナンス性、セキュリティリスクを確認すること。
- **最小権限**: CI/CD、Docker、GitHub Actions の権限は最小権限を維持すること。

## Review Output Policy
- 指摘には必ず根拠、影響範囲、再現条件、推奨修正方針を含めること。
- すべての指摘には confidence を付与すること。
  - High: 実コード・テスト・仕様から再現可能
  - Medium: 文脈上ほぼ妥当だが追加確認が必要
  - Low: 仮説。blocking 禁止
- 推測のみの blocking 指摘は禁止すること。
- blocking とする場合は、実際に失敗する条件、漏洩する可能性、またはCI失敗につながる理由を明示すること。
- suggested / nit は request changes ではなく comment として扱うこと。
- 既存方針と異なる提案をする場合は、代替案と trade-off を示すこと。
- ポートフォリオ規模に対して過剰な抽象化、過剰なツール追加、過剰なセキュリティ要件化は避けること。
- スコープ外の大規模リファクタ、設計変更、ツール追加は、明確な不具合やリスクがない限り blocking としないこと。
- 修正提案には、必要に応じて unit / integration / smoke / external / performance のどのテストで担保するかを示すこと。

## False Positive Control
- 静的解析ツールの指摘は、文脈確認なしに blocking としないこと。
- テストコード、モック、fixture、サンプル値に対する secret / PII 指摘は、実害を確認してから分類すること。
- セキュリティ指摘は OWASP / CWE / 具体的な攻撃経路のいずれかに紐づけること。
