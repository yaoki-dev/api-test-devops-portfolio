# マルチレベルセキュリティテスト実装ガイド

*最終更新: 2026年03月23日*

## 概要

本プロジェクトでは、セキュリティ検証を静的解析ツール（gitleaks / bandit / ruff(S) / Trivy）で実施しています。このドキュメントでは、その設計判断の根拠と業界ベストプラクティスとの整合性を説明します。

---

## 1. 実装構成

### 1.1 セキュリティ検証構成

| 種別 | ツール | 実行タイミング | 目的 |
|-----|--------|--------------|------|
| **Secrets Scan** | gitleaks | コミット時（pre-commit） | 認証情報・APIキーの漏洩検出 |
| **Dependency/Container Scan** | Trivy (fs) | 全PR（CI） | 依存パッケージの既知CVE検査 |
| **Container Image Scan** | Trivy (image) | main PR・docker label PR（CI） | コンテナイメージの脆弱性検査 |
| **SAST・Security Linting** | bandit / ruff(S) | ローカル手動実行 | Pythonコードの脆弱性・セキュリティパターン検出 |

### 1.2 セキュリティ検証アプローチ

本プロジェクトでは、セキュリティ検証を **pytest テストではなく静的解析ツール** で実施しています。

**設計根拠**: OWASP API Security Top 10 の検証は、実際のAPIエンドポイントに対する統合テストよりも、
静的解析（SAST）・シークレットスキャン・コンテナスキャンの組み合わせにより、
CI/CD パイプラインで効率的かつ継続的に実施できます。

**実行環境の使い分け**: Trivy（依存パッケージ・コンテナ）は CI ゲートとして全 PR で自動実行。gitleaks はコミット時の pre-commit フックとして開発者ローカルで実行。bandit・ruff(S) はローカル手動実行を推奨。

登録済み pytest マーカー（`pytest.ini`）:

```ini
markers =
    unit: Unit tests (fast, isolated, mock-based)
    integration: Integration tests (external dependencies, real API calls)
    e2e: End-to-end tests (Playwright)
    slow: Slow tests (>3 seconds)
    external: External API dependent tests (weekly only)
    performance: Performance tests (weekly CI only)
    smoke: Smoke tests (basic operation check)
```

（security マーカーは未登録 — セキュリティ検証は CI 静的解析で実施）

### 1.3 実行コマンド

```bash
# CI セキュリティスキャン（GitHub Actions で自動実行）
# trivy fs: 依存パッケージ CVE スキャン（全 PR）
# trivy image: コンテナイメージスキャン（main PR・docker label PR のみ）

# ローカルチェックコマンド（手動実行）
uv run bandit -r utils/ config/ models/          # SAST
uv run ruff check --select S .                   # Security rules

# コミット時（pre-commit フック）
# gitleaks: secrets scan（自動実行）
```

---

## 2. 設計判断の根拠

### 2.1 なぜ CI 静的解析でセキュリティ検証を実施するのか？

**Shift Left + Defense in Depth** アプローチに基づいています。

```
            ┌─────────────────────────────────────────────────┐
            │   CI Static Analysis Layer                      │
            │   - Trivy fs: dependency scan（全PR）           │
            │   - Trivy image: container scan（main/docker PR）│
            └─────────────────────────────────────────────────┘
            ┌─────────────────────────────────────────────────┐
            │   Developer Local Layer                         │
            │   - gitleaks: secrets scan（pre-commit）        │
            │   - bandit: Python SAST（手動）                 │
            │   - ruff(S): security linting（手動）           │
            └─────────────────────────────────────────────────┘
```

### 2.2 ツール別の役割

| ツール | 目的 | 検出できる問題 | 実行コスト |
|-------|------|--------------|-----------|
| **gitleaks** | 漏洩防止 | APIキー・パスワード・トークンのコミット混入 | 低（< 10秒） |
| **bandit** | SAST | SQLインジェクション・eval使用・弱い暗号化 | 低（< 10秒） |
| **ruff (S rules)** | セキュリティLint | OWASPパターン・危険な関数使用・ハードコード値 | 低（< 5秒） |
| **Trivy** | コンテナ検査 | 脆弱な依存パッケージ・OSパッケージの既知CVE | 中（< 60秒） |

### 2.3 業界ベストプラクティスとの整合性

| 参照元 | 推奨事項 | 本プロジェクトの実装 |
|-------|---------|-------------------|
| **OWASP Testing Guide** | Shift Left Security | PR毎の静的解析で早期検出 |
| **Google Testing Blog** | テストピラミッド構造 | セキュリティは静的解析・Performance/E2Eはテスト層 |
| **NIST Secure SDLC** | Shift Left Testing | CI/CDで静的解析を毎回実行 |

---

## 3. 面接回答例

### Q1: なぜセキュリティ検証を pytest テストではなく静的解析ツールで実施しているのですか？

**回答例**:
> 「Shift Left」と「Defense in Depth」の2つの原則に基づいています。
>
> **Shift Left**: gitleaks を pre-commit フックとして開発者ローカルで実行し、シークレット漏洩をコミット前に検出します。bandit・ruff(S) はローカル手動実行で SAST を補完します。
>
> **Defense in Depth**: Trivy の依存パッケージスキャン（fs）を全 PR で CI 実行し、コンテナイメージスキャン（image）は main PR・docker ラベル付き PR のみに限定してコストを最適化します。
>
> この多層構造により、OWASP API Security Top 10 に準拠したセキュリティ検証を効率的に実現しています。

### Q2: セキュリティ検証ツールはどのように使い分けていますか？

**回答例**:
> 検出対象に応じて4つのツールを使い分けています。
>
> **gitleaks**（コミット時・pre-commit）はコミットに混入した APIキー・パスワード・トークンなどの機密情報を開発者ローカルで検出します。コードロジックとは独立してシークレットスキャンを行います。
>
> **bandit**（ローカル手動実行）はPythonコードのSAST（静的アプリケーションセキュリティテスト）で、SQLインジェクション・eval使用・弱い暗号化アルゴリズムなどを検出します。
>
> **ruff(S rules)**（ローカル手動実行）はOWASP関連のコードパターンやハードコードされた値を Lint レベルで検出します。
>
> **Trivy fs**（全PR・CI）は依存パッケージの既知CVEをスキャンします。**Trivy image**（main PR・docker ラベル付き PR・CI）はコンテナイメージの脆弱性を検査します。image スキャンは実行時間が長いため対象 PR を限定してCIコストを最適化しています。

### Q3: パフォーマンステストも同様のアプローチですか？

**回答例**:
> はい。パフォーマンステスト（`test_api_performance.py`）は実際のネットワーク環境で実行します。レスポンス時間測定やスループット計測は、実際のネットワークレイテンシを含む環境でないと意味のあるデータが得られないためです。`performance`マーカー専用で分類し（`integration`マーカーとは独立）、週次CIでのみ実行します。
>
> `uv run pytest -m performance`で選択的に実行できます。

---

## 4. 技術詳細

### 4.1 CI ワークフロー構成

```yaml
# .github/workflows/ （抜粋）
# 全 PR で実行されるセキュリティスキャン
# - trivy fs scan: 依存パッケージの既知CVE検査
# main PR・docker ラベル付き PR のみ実行
# - trivy image scan: コンテナイメージの脆弱性検査

# ローカル（pre-commit / 手動）
# - gitleaks: secrets scan（コミット時・pre-commit）
# - bandit: Python SAST（手動）
# - ruff --select S: security linting（手動）
```

**設計根拠**:

- Trivy による依存パッケージスキャンを CI ゲートとして全 PR に適用（Shift Left）
- gitleaks はコミット前に開発者ローカルで検出することで漏洩リスクを最小化
- bandit・ruff(S) はローカル手動実行で補完（CI 未定義）
- pytest の security マーカーは未使用（未登録）

### 4.2 ツール実行基準

| 基準 | gitleaks | bandit | ruff(S) | Trivy (fs) | Trivy (image) |
|-----|---------|--------|---------|------------|---------------|
| 実行タイミング | コミット時（pre-commit） | ローカル手動 | ローカル手動 | 全PR（CI） | main PR・docker label PR（CI） |
| 実行時間 | < 10秒 | < 10秒 | < 5秒 | < 60秒 | < 60秒 |
| 対象 | シークレット漏洩 | PythonSAST | OWASPパターン | 依存パッケージCVE | コンテナイメージCVE |

---

## 5. 関連ドキュメント

- `.serena/memories/test_strategy.md`: テスト戦略全体
- `.serena/memories/test_strategy_part3_security_execution.md`: セキュリティテスト実行戦略
- `pytest.ini`: マーカー定義

---

## 6. 更新履歴

| 日付 | 内容 |
|------|------|
| 2025-11-29 | 初版作成。マルチレベルセキュリティテスト実装完了 |
| 2026-03-23 | PR #278 レビュー対応。実在しないテストファイル参照・未登録 security マーカー記述を削除し、実際の CI 静的解析ツール（gitleaks/bandit/ruff(S)/Trivy）の説明に全面改訂 |
| 2026-03-23 | CI 構成記述を正確化。gitleaks（pre-commit）、bandit/ruff(S)（ローカル手動）、Trivy fs（全PR CI）・Trivy image（main PR・docker label PR CI）に修正 |
