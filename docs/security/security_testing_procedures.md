# セキュリティテスト手順書

*最終更新: 2025年09月23日*

## 📋 目次

1. [概要](#概要)
2. [OWASP API Security Top 10 準拠テスト](#owasp-api-security-top-10-準拠テスト)
3. [テスト実行方法](#テスト実行方法)
4. [セキュリティテストツール](#セキュリティテストツール)
5. [結果の評価](#結果の評価)
6. [継続的セキュリティ監視](#継続的セキュリティ監視)

## 概要

このドキュメントは、JSONPlaceholder APIを使用したセキュリティテストの包括的な手順書です。OWASP API Security Top 10に準拠した84のテストケースを含みます。

### 🎯 テスト対象

- **対象API**: JSONPlaceholder (https://jsonplaceholder.typicode.com)
- **実装クライアント**: `utils/api_client.py` - JSONPlaceholderClient
- **セキュリティヘルパー**: `utils/security_helpers.py`
- **テストフレームワーク**: pytest + requests + httpx

### 📊 テスト規模

- **OWASP準拠テストケース**: 84件
- **セキュリティドメイン**: 10領域 (OWASP API Top 10)
- **検証項目**: 認証・認可・データ保護・SSRF・入力検証
- **実行時間**: 約3-5分 (並列実行時)

## OWASP API Security Top 10 準拠テスト

### API1: Broken Object Level Authorization
**脆弱性**: オブジェクトレベル認証の不備

#### テスト項目
```python
# テストファイル: tests/security/test_owasp_api_security_top10_complete.py
class TestAPI1BrokenObjectLevelAuthorization:
    def test_object_level_authorization_bypass()
    def test_unauthorized_object_access()
    def test_direct_object_reference_vulnerability()
```

#### 実行方法
```bash
# API1専用テスト
uv run pytest tests/security/test_owasp_api_security_top10_complete.py::TestAPI1BrokenObjectLevelAuthorization -v

# すべてのオブジェクトレベル認証テスト
uv run pytest tests/security/ -k "object_level" -v
```

### API2: Broken User Authentication
**脆弱性**: ユーザー認証の不備

#### テスト項目
```python
class TestAPI2BrokenUserAuthentication:
    def test_weak_authentication_mechanism()
    def test_credential_stuffing_protection()
    def test_brute_force_protection()
```

#### 実行方法
```bash
# 認証関連テスト
uv run pytest tests/security/ -k "authentication" -v
```

### API3: Excessive Data Exposure
**脆弱性**: 過度なデータ露出

#### テスト項目
```python
class TestAPI3ExcessiveDataExposure:
    def test_sensitive_data_exposure()
    def test_pii_data_filtering()
    def test_response_data_minimization()
```

### API4: Lack of Resources & Rate Limiting
**脆弱性**: リソース・レート制限の不備

#### テスト項目
```python
class TestAPI4LackOfResourcesRateLimiting:
    def test_rate_limiting_bypass()
    def test_resource_exhaustion_protection()
    def test_dos_prevention()
```

### API5: Broken Function Level Authorization
**脆弱性**: 機能レベル認可の不備

#### テスト項目
```python
class TestAPI5BrokenFunctionLevelAuthorization:
    def test_privilege_escalation()
    def test_admin_function_access()
    def test_role_based_access_control()
```

### API6: Mass Assignment
**脆弱性**: 一括代入攻撃

#### テスト項目
```python
class TestAPI6MassAssignment:
    def test_mass_assignment_vulnerability()
    def test_parameter_binding_attack()
    def test_object_property_modification()
```

### API7: Security Misconfiguration
**脆弱性**: セキュリティ設定ミス

#### テスト項目
```python
class TestAPI7SecurityMisconfiguration:
    def test_cors_misconfiguration()
    def test_security_headers_validation()
    def test_error_handling_information_disclosure()
```

### API8: Injection
**脆弱性**: インジェクション攻撃

#### テスト項目
```python
class TestAPI8Injection:
    def test_sql_injection_protection()
    def test_nosql_injection_protection()
    def test_command_injection_protection()
```

### API9: Improper Assets Management
**脆弱性**: 不適切な資産管理

#### テスト項目
```python
class TestAPI9ImproperAssetsManagement:
    def test_api_version_management()
    def test_deprecated_endpoint_exposure()
    def test_documentation_exposure()
```

### API10: Insufficient Logging & Monitoring
**脆弱性**: 不十分なログ記録・監視

#### テスト項目
```python
class TestAPI10InsufficientLoggingMonitoring:
    def test_security_event_logging()
    def test_audit_trail_completeness()
    def test_incident_detection_capability()
```

## テスト実行方法

### 🚀 クイック実行コマンド

#### 全セキュリティテスト実行
```bash
# 全84テストケース実行（推奨）
uv run pytest tests/security/ -v

# 並列実行（高速化）
uv run pytest tests/security/ -n auto -v

# カバレッジ付き実行
uv run pytest tests/security/ --cov=utils --cov-report=html --cov-report=term
```

#### 特定領域のテスト実行
```bash
# OWASP Top 10完全テスト
uv run pytest tests/security/test_owasp_api_security_top10_complete.py -v

# 基本入力検証テスト
uv run pytest tests/security/test_basic_input_validation.py -v

# SSRF保護テスト
uv run pytest tests/security/test_ssrf_protection.py -v

# セキュリティヘルパーテスト
uv run pytest tests/security/test_security_helpers.py -v
```

### 🔍 詳細テスト実行

#### 特定の脆弱性テスト
```bash
# 認証関連のみ
uv run pytest tests/security/ -k "authentication" -v

# 認可関連のみ
uv run pytest tests/security/ -k "authorization" -v

# インジェクション関連のみ
uv run pytest tests/security/ -k "injection" -v

# データ露出関連のみ
uv run pytest tests/security/ -k "exposure" -v
```

#### デバッグモード実行
```bash
# 詳細ログ付き実行
uv run pytest tests/security/ -v -s --log-cli-level=DEBUG

# 失敗時停止
uv run pytest tests/security/ -x

# 最初の3つの失敗で停止
uv run pytest tests/security/ --maxfail=3
```

## セキュリティテストツール

### utils/security_helpers.py の活用

#### 1. SecurityTestHelper
```python
from utils.security_helpers import SecurityTestHelper

# セキュリティテストヘルパーの初期化
helper = SecurityTestHelper()

# 認証トークンの検証
is_valid = helper.validate_auth_token(token)

# 権限チェック
has_permission = helper.check_permission(user, resource, action)
```

#### 2. InputValidator
```python
from utils.security_helpers import InputValidator

validator = InputValidator()

# 入力検証
is_safe = validator.validate_input(user_input)
sanitized = validator.sanitize_input(user_input)
```

#### 3. AuthenticationManager
```python
from utils.security_helpers import AuthenticationManager

auth_manager = AuthenticationManager()

# 認証処理
auth_result = auth_manager.authenticate(credentials)
session = auth_manager.create_session(user)
```

### pytest設定とフィクスチャ

#### conftest.py の活用
```python
# tests/conftest.py で定義されたフィクスチャを使用

@pytest.fixture
def security_client():
    """セキュリティテスト用クライアント"""
    return JSONPlaceholderClient(
        timeout=30,
        max_retries=3
    )

@pytest.fixture
def mock_auth_token():
    """モック認証トークン"""
    return "mock-jwt-token-for-testing"
```

### カスタムセキュリティテスト

#### APIセキュリティテストの追加
```python
import pytest
from utils.api_client import JSONPlaceholderClient
from utils.security_helpers import SecurityTestHelper

class TestCustomSecurityChecks:
    def test_custom_vulnerability(self):
        """カスタム脆弱性テスト"""
        with JSONPlaceholderClient() as client:
            # テストロジック実装
            response = client.get("/posts/1")
            assert response.status_code == 200

            # セキュリティ検証
            helper = SecurityTestHelper()
            is_secure = helper.validate_response_security(response)
            assert is_secure
```

## 結果の評価

### ✅ 合格基準

#### セキュリティテスト合格条件
- **全84テストケース**: 100% 成功
- **脆弱性検出**: 0件の未対策脆弱性
- **カバレッジ**: 85%以上のコードカバレッジ
- **実行時間**: 5分以内での完了

#### テスト結果の確認
```bash
# テスト実行とレポート生成
uv run pytest tests/security/ --html=reports/security_test_report.html --self-contained-html

# カバレッジレポート生成
uv run pytest tests/security/ --cov=utils --cov-report=html --cov-report=xml

# JUnit形式レポート（CI/CD用）
uv run pytest tests/security/ --junit-xml=reports/security_junit.xml
```

### 📊 レポート分析

#### HTMLレポートの活用
- **場所**: `htmlcov/index.html`
- **内容**: 行別カバレッジ、未実行コード、分岐カバレッジ
- **分析**: セキュリティ関連コードの実行状況確認

#### XML レポートの活用
- **場所**: `coverage.xml`
- **用途**: CI/CDパイプライン、SonarQube連携
- **メトリクス**: 定量的セキュリティ評価

### 🚨 失敗時の対応

#### テスト失敗時のデバッグ手順
1. **エラーログ確認**: `-v -s` オプションで詳細ログ確認
2. **個別テスト実行**: 失敗したテストケースのみ再実行
3. **セキュリティヘルパー確認**: `utils/security_helpers.py`の実装確認
4. **APIレスポンス検証**: 実際のAPIレスポンス内容確認

```bash
# 失敗テストの個別実行例
uv run pytest tests/security/test_owasp_api_security_top10_complete.py::TestAPI1BrokenObjectLevelAuthorization::test_object_level_authorization_bypass -v -s
```
## 継続的セキュリティ監視

### 🔄 定期実行スケジュール

#### 日次セキュリティチェック
```bash
# 毎日実行する基本セキュリティテスト
uv run pytest tests/security/test_basic_input_validation.py tests/security/test_security_helpers.py -v
```

#### 週次包括テスト
```bash
# 週1回実行する完全セキュリティテスト
uv run pytest tests/security/ --cov=utils --cov-report=html
```

#### 月次OWASP準拠確認
```bash
# 月1回実行するOWASP完全準拠テスト
uv run pytest tests/security/test_owasp_api_security_top10_complete.py tests/security/test_owasp_api_security_comprehensive.py -v
```

### 🔗 CI/CD統合

#### GitHub Actions設定例
```yaml
name: Security Tests
on: [push, pull_request]
jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Security Tests
        run: |
          uv run pytest tests/security/ \
            --junit-xml=reports/security.xml \
            --cov=utils \
            --cov-report=xml
```

### 📈 メトリクス追跡

#### 継続改善のためのKPI
- **脆弱性検出率**: 新たな脆弱性の早期発見
- **修正時間**: 脆弱性発見から修正完了までの時間
- **カバレッジ向上**: セキュリティテストカバレッジの継続的向上
- **実行効率**: テスト実行時間の最適化

---

## 関連ドキュメント

- [APIクライアント仕様書](../api/api_documentation.md)
- [パフォーマンステスト結果ガイド](performance_benchmark_guide.md)
- [OWASP準拠チェックリスト](owasp_compliance_checklist.md)
- [日常開発コマンド](DAILY_COMMANDS.md)

---

**セキュリティは継続的なプロセスです。定期的なテスト実行と監視を通じて、安全なAPIの維持を心がけましょう。**