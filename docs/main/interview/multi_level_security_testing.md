# マルチレベルセキュリティテスト実装ガイド

*最終更新: 2025年11月29日*

## 概要

本プロジェクトでは、セキュリティテストを複数のテストレベル（Unit/Integration）で実装しています。このドキュメントでは、その設計判断の根拠と業界ベストプラクティスとの整合性を説明します。

---

## 1. 実装構成

### 1.1 テストレベル別構成

| レベル | ファイル | テスト数 | マーカー | 実行環境 |
|-------|---------|---------|---------|---------|
| **Unit** | test_security_with_mock.py | 38 | `security`, `unit` | ローカル・CI/CD毎回 |
| **Integration** | test_comprehensive_security.py | 11 | `security`, `integration` | CI/CD・週次 |
| **Integration** | test_basic_input_validation.py | 5 | `security`, `integration` | CI/CD・週次 |
| **合計** | 3ファイル | **54テスト** | - | - |

### 1.2 マーカー構成

```ini
# pytest.ini
markers =
    security: Security tests (OWASP Top 10, vulnerability checks)
    unit: Unit tests (fast, isolated, mock-based)
    integration: Integration tests (external dependencies, real API calls)
```

### 1.3 実行コマンド

```bash
# Unit Level セキュリティテスト（高速、毎回実行）
uv run pytest -m "security and unit"  # 38テスト、< 5秒

# Integration Level セキュリティテスト（実API、週次実行）
uv run pytest -m "security and integration"  # 16テスト、< 30秒

# 全セキュリティテスト（リリース前）
uv run pytest -m security  # 54テスト
```

---

## 2. 設計判断の根拠

### 2.1 なぜ複数レベルで実装するのか？

**Shift Left + Defense in Depth** アプローチに基づいています。

```
                    ┌─────────────────────────────┐
                    │   Integration Level         │
                    │   - 実API脆弱性検証         │
                    │   - OWASP Top 10実環境テスト │
                    │   - Rate Limiting検証       │
                    └───────────┬─────────────────┘
                                │
            ┌───────────────────┴───────────────────┐
            │           Unit Level                   │
            │   - Mock使用、高速フィードバック       │
            │   - インジェクション検出ロジック検証   │
            │   - 入力バリデーション単体テスト       │
            └───────────────────────────────────────┘
```

### 2.2 レベル別の役割

| レベル | 目的 | 検出できる問題 | 実行コスト |
|-------|------|--------------|-----------|
| **Unit** | 早期検出 | バリデーションロジックのバグ、正規表現の誤り | 低（< 5秒） |
| **Integration** | 実環境検証 | API境界での脆弱性、実際のレスポンス動作 | 中（< 30秒） |

### 2.3 業界ベストプラクティスとの整合性

| 参照元 | 推奨事項 | 本プロジェクトの実装 |
|-------|---------|-------------------|
| **OWASP Testing Guide** | 複数レベルでのセキュリティテスト | Unit + Integration 2層 |
| **Google Testing Blog** | テストピラミッド構造 | Security/Performanceはレベル横断 |
| **NIST Secure SDLC** | Shift Left Testing | CI/CDでUnit Securityを毎回実行 |

---

## 3. 面接回答例

### Q1: なぜセキュリティテストを複数レベルで実装したのですか？

**回答例**:
> 「Shift Left」と「Defense in Depth」の2つの原則に基づいています。
>
> **Shift Left**: Unit Levelのセキュリティテスト（38テスト）をCI/CDで毎回実行することで、脆弱性を開発の早い段階で検出します。Mock使用により5秒以内で完了するため、開発フローを妨げません。
>
> **Defense in Depth**: Integration Levelのテスト（16テスト）では実際のAPIを使用し、Unit Testでは検出できない境界での問題（Rate Limiting、実際のレスポンス形式）を週次で検証します。
>
> この2層構造により、コストと品質のバランスを取りながら、OWASP API Security Top 10に準拠したセキュリティ検証を実現しています。

### Q2: Unit Level と Integration Level のテストはどう使い分けていますか？

**回答例**:
> Unit Level（`test_security_with_mock.py`）はMockを使用した高速テストで、インジェクション検出ロジック、入力バリデーション、サニタイゼーション処理を検証します。毎回のコミット前に実行し、即座にフィードバックを得られます。
>
> Integration Level（`test_comprehensive_security.py`, `test_basic_input_validation.py`）は実際のAPIを呼び出し、OWASP Top 10に基づく包括的な脆弱性検証を行います。実行時間が長いため週次・リリース前に実行しますが、実環境でしか発見できない問題を検出できます。

### Q3: パフォーマンステストも同様のアプローチですか？

**回答例**:
> はい。パフォーマンステスト（`test_api_performance.py`）は実際のネットワーク環境で実行します。レスポンス時間測定やスループット計測は、実際のネットワークレイテンシを含む環境でないと意味のあるデータが得られないためです。`performance`マーカー専用で分類し（`integration`マーカーとは独立）、週次CIでのみ実行します。
>
> `uv run pytest -m performance`で選択的に実行できます。

---

## 4. 技術詳細

### 4.1 pytestmarkモジュールレベル定義

```python
# tests/security/test_comprehensive_security.py
pytestmark = [
    pytest.mark.security,
    pytest.mark.integration,  # Uses AsyncAPIClient for real API calls
]
```

**設計根拠**:

- 全テストに一括適用（DRY原則）
- 既存の個別`@pytest.mark`と共存可能
- `test_security_with_mock.py`と一貫したパターン

### 4.2 テスト分離の基準

| 基準 | Unit Level | Integration Level |
|-----|-----------|-------------------|
| 外部依存 | Mock使用 | 実API呼び出し |
| 実行時間 | < 0.5秒/test | 1-3秒/test |
| 実行頻度 | 毎回コミット前 | 週次・リリース前 |
| 検出対象 | ロジックエラー | 境界・環境問題 |

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
