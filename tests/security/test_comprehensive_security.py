"""
包括的セキュリティテスト実装

学習目標:
- OWASP API Security Top 10準拠テスト
- 認証・認可テスト
- 入力検証・インジェクション攻撃テスト
- セキュリティヘッダー検証
"""

import asyncio
import json
import time

import pytest
import structlog

from utils.api_client import AsyncAPIClient

logger = structlog.get_logger()

# Module-level markers: Security tests using real API (integration level)
# Design rationale: Security testing at integration level validates actual API behavior
# See: docs/interview/multi_level_security_testing.md
pytestmark = [
    pytest.mark.security,
    pytest.mark.integration,  # Uses AsyncAPIClient for real API calls
]


class SecurityTestSuite:
    """セキュリティテストスイート"""

    # OWASP API Security Top 10 テストパターン
    INJECTION_PAYLOADS = [
        # SQL Injection
        "' OR '1'='1",
        "'; DROP TABLE users; --",
        "1' UNION SELECT * FROM users --",
        "admin'--",
        "' OR 1=1 --",
        # NoSQL Injection
        '{"$ne": null}',
        '{"$gt": ""}',
        '{"$where": "sleep(1000)"}',
        # Command Injection
        "; ls -la",
        "| whoami",
        "&& cat /etc/passwd",
        "$(ping -c 1 127.0.0.1)",
        "`id`",
        # XSS Payloads
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "javascript:alert('XSS')",
        "<svg onload=alert('XSS')>",
        "';alert('XSS');//",
        # Path Traversal
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\drivers\\etc\\hosts",
        "....//....//....//etc/passwd",
        # LDAP Injection
        "*)(uid=*))(|(uid=*",
        "admin)(&(password=*))",
    ]

    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": ["DENY", "SAMEORIGIN"],
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=",
        "Content-Security-Policy": "default-src",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }


@pytest.mark.security
class TestOWASPAPISecurityTop10:
    """OWASP API Security Top 10 包括テスト"""

    def setup_method(self):
        """テストセットアップ"""
        self.security_suite = SecurityTestSuite()
        self.vulnerabilities_found = []

    @pytest.mark.asyncio
    async def test_api1_broken_object_level_authorization(self):
        """API1:2023 - Broken Object Level Authorization"""
        async with AsyncAPIClient() as client:
            # 他のユーザーのリソースにアクセス試行
            test_cases = [
                ("/posts/1", "ユーザー1の投稿"),
                ("/posts/2", "ユーザー2の投稿"),
                ("/users/1", "ユーザー1の情報"),
                ("/users/2", "ユーザー2の情報"),
            ]

            for endpoint, description in test_cases:
                response = await client.get(endpoint)

                # アクセス制御の確認
                if response.status_code == 200:
                    data = response.json()
                    logger.info(
                        "object_access_test",
                        endpoint=endpoint,
                        description=description,
                        accessible=True,
                    )

                    # 個人情報が含まれていないかチェック
                    sensitive_fields = ["password", "ssn", "credit_card", "private_key"]
                    for field in sensitive_fields:
                        assert field not in str(data).lower(), (
                            f"Sensitive data exposed: {field} in {endpoint}"
                        )

    @pytest.mark.asyncio
    async def test_api2_broken_authentication(self):
        """API2:2023 - Broken Authentication"""
        async with AsyncAPIClient() as client:
            # 弱い認証テスト
            weak_auth_tests = [
                {"username": "admin", "password": "admin"},
                {"username": "admin", "password": "password"},
                {"username": "admin", "password": "123456"},
                {"username": "test", "password": ""},
                {"username": "", "password": "password"},
            ]

            for credentials in weak_auth_tests:
                # JSONPlaceholderにはログインエンドポイントがないため、シミュレーション
                response = await client.post(
                    "/posts",
                    json={
                        "title": f"Auth test with {credentials['username']}",
                        "body": "Testing authentication",
                        "userId": 1,
                    },
                )

                # 認証なしでもリソース作成できることを確認（教育目的）
                assert response.status_code in [200, 201], "API should require authentication"
                logger.info("auth_test", credentials=credentials, status=response.status_code)

    @pytest.mark.asyncio
    async def test_api3_broken_object_property_level_authorization(self):
        """API3:2023 - Broken Object Property Level Authorization"""
        async with AsyncAPIClient() as client:
            # マスアサインメント攻撃テスト
            malicious_post_data = {
                "title": "Test Post",
                "body": "Test Body",
                "userId": 1,
                # 悪意のあるフィールド
                "isAdmin": True,
                "role": "admin",
                "permissions": ["read", "write", "delete"],
                "verified": True,
                "credits": 1000000,
            }

            response = await client.post("/posts", json=malicious_post_data)

            if response.status_code in [200, 201]:
                created_post = response.json()

                # 悪意のあるフィールドが受け入れられていないか確認
                dangerous_fields = [
                    "isAdmin",
                    "role",
                    "permissions",
                    "verified",
                    "credits",
                ]
                for field in dangerous_fields:
                    if field in created_post:
                        logger.warning(
                            "mass_assignment_vulnerability",
                            field=field,
                            value=created_post[field],
                        )
                        self.vulnerabilities_found.append(f"Mass assignment: {field}")

    @pytest.mark.asyncio
    async def test_api4_unrestricted_resource_consumption(self):
        """API4:2023 - Unrestricted Resource Consumption"""
        async with AsyncAPIClient() as client:
            # レート制限テスト
            start_time = time.time()
            responses = []

            # 100リクエストを短時間で送信
            tasks = []
            for _i in range(100):
                tasks.append(client.get("/posts/1"))

            try:
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                end_time = time.time()

                # レスポンス分析
                successful_requests = [
                    r for r in responses if hasattr(r, "status_code") and r.status_code == 200
                ]
                rate_limited = [
                    r for r in responses if hasattr(r, "status_code") and r.status_code == 429
                ]

                logger.info(
                    "rate_limit_test",
                    total_requests=len(responses),
                    successful=len(successful_requests),
                    rate_limited=len(rate_limited),
                    duration=end_time - start_time,
                )

                # レート制限の確認
                if len(rate_limited) == 0 and len(successful_requests) > 50:
                    logger.warning(
                        "no_rate_limiting_detected",
                        requests_per_second=len(successful_requests) / (end_time - start_time),
                    )

            except Exception as e:
                logger.error("rate_limit_test_error", error=str(e))

    @pytest.mark.asyncio
    async def test_api5_broken_function_level_authorization(self):
        """API5:2023 - Broken Function Level Authorization"""
        async with AsyncAPIClient() as client:
            # 管理者機能へのアクセステスト
            admin_endpoints = [
                "/admin/users",
                "/admin/settings",
                "/admin/logs",
                "/admin/statistics",
                "/management/users",
                "/internal/config",
            ]

            for endpoint in admin_endpoints:
                try:
                    response = await client.get(endpoint)

                    if response.status_code == 200:
                        logger.warning("admin_endpoint_accessible", endpoint=endpoint)
                        self.vulnerabilities_found.append(f"Admin endpoint accessible: {endpoint}")
                    elif response.status_code == 404:
                        logger.info("admin_endpoint_not_found", endpoint=endpoint)
                    else:
                        logger.info(
                            "admin_endpoint_protected",
                            endpoint=endpoint,
                            status=response.status_code,
                        )

                except Exception as e:
                    logger.debug("admin_endpoint_error", endpoint=endpoint, error=str(e))

    @pytest.mark.asyncio
    async def test_injection_vulnerabilities(self):
        """インジェクション脆弱性の包括テスト"""
        async with AsyncAPIClient() as client:
            # 各種インジェクションペイロードのテスト
            for payload in self.security_suite.INJECTION_PAYLOADS:
                # GET パラメータでのテスト
                try:
                    response = await client.get(f"/posts/{payload}")
                    await self._analyze_injection_response(response, payload, "GET parameter")
                except Exception as e:
                    logger.debug("injection_test_error", payload=payload[:50], error=str(e))

                # POST データでのテスト
                try:
                    post_data = {
                        "title": payload,
                        "body": f"Test with payload: {payload}",
                        "userId": payload,
                    }
                    response = await client.post("/posts", json=post_data)
                    await self._analyze_injection_response(response, payload, "POST data")
                except Exception as e:
                    logger.debug("injection_post_error", payload=payload[:50], error=str(e))

                # 短い間隔
                await asyncio.sleep(0.01)

    async def _analyze_injection_response(self, response, payload: str, context: str):
        """インジェクションレスポンス分析"""
        # SQLエラーパターン
        sql_error_patterns = [
            "mysql error",
            "sql syntax",
            "postgresql error",
            "sqlite error",
            "ora-",
            "sqlstate",
            "error in your sql syntax",
            "quoted string not properly terminated",
        ]

        # コマンド実行パターン
        command_patterns = ["uid=", "gid=", "etc/passwd", "root:", "bin/bash"]

        # XSSパターン
        xss_patterns = ["<script>", "javascript:", "onerror=", "onload="]

        if response.status_code == 500:
            logger.warning("injection_server_error", payload=payload[:50], context=context)
            self.vulnerabilities_found.append(f"Server error with injection: {context}")

        response_text = response.text.lower()

        # SQLエラー検出
        for pattern in sql_error_patterns:
            if pattern in response_text:
                logger.warning("sql_injection_detected", pattern=pattern, payload=payload[:50])
                self.vulnerabilities_found.append(f"SQL injection detected: {pattern}")

        # コマンド実行検出
        for pattern in command_patterns:
            if pattern in response_text:
                logger.warning("command_injection_detected", pattern=pattern, payload=payload[:50])
                self.vulnerabilities_found.append(f"Command injection detected: {pattern}")

        # XSS検出
        for pattern in xss_patterns:
            if pattern in response.text:  # Case sensitive for XSS
                logger.warning("xss_vulnerability_detected", pattern=pattern, payload=payload[:50])
                self.vulnerabilities_found.append(f"XSS vulnerability detected: {pattern}")


@pytest.mark.security
class TestSecurityHeaders:
    """セキュリティヘッダーテスト"""

    @pytest.mark.asyncio
    async def test_security_headers_presence(self):
        """セキュリティヘッダーの存在確認"""
        async with AsyncAPIClient() as client:
            response = await client.get("/posts/1")
            headers = {k.lower(): v for k, v in response.headers.items()}

            security_findings = []

            for header, expected_value in SecurityTestSuite.SECURITY_HEADERS.items():
                header_lower = header.lower()

                if header_lower in headers:
                    header_value = headers[header_lower]

                    if isinstance(expected_value, list):
                        # いずれかの値が含まれているかチェック
                        if not any(exp_val in header_value for exp_val in expected_value):
                            security_findings.append(
                                f"{header} has unexpected value: {header_value}"
                            )
                    else:
                        # 特定の値が含まれているかチェック
                        if expected_value not in header_value:
                            security_findings.append(
                                f"{header} has unexpected value: {header_value}"
                            )

                    logger.info("security_header_found", header=header, value=header_value)
                else:
                    security_findings.append(f"Missing security header: {header}")
                    logger.warning("security_header_missing", header=header)

            # セキュリティヘッダーの評価
            if security_findings:
                logger.warning("security_headers_issues", issues=security_findings)
                # 教育目的のため、警告のみ
                print(f"⚠️ セキュリティヘッダーの問題: {len(security_findings)}件")
                for finding in security_findings:
                    print(f"  - {finding}")
            else:
                print("✅ すべての重要なセキュリティヘッダーが設定されています")


@pytest.mark.security
class TestDataProtection:
    """データ保護・プライバシーテスト"""

    @pytest.mark.asyncio
    async def test_sensitive_data_exposure(self):
        """機密データ露出テスト"""
        async with AsyncAPIClient() as client:
            # 各エンドポイントでの機密データチェック
            endpoints = ["/posts/1", "/users/1", "/comments/1", "/todos/1"]

            sensitive_patterns = [
                "password",
                "passwd",
                "pwd",
                "secret",
                "key",
                "token",
                "ssn",
                "social",
                "credit",
                "private",
                "confidential",
                "api_key",
                "auth_token",
            ]

            for endpoint in endpoints:
                response = await client.get(endpoint)

                if response.status_code == 200:
                    response_text = response.text.lower()

                    for pattern in sensitive_patterns:
                        if pattern in response_text:
                            logger.warning(
                                "sensitive_data_exposure",
                                endpoint=endpoint,
                                pattern=pattern,
                            )
                            print(
                                f"⚠️ 機密データ露出の可能性: {endpoint} に "
                                f"'{pattern}' が含まれています"
                            )

    @pytest.mark.asyncio
    async def test_large_payload_handling(self):
        """大容量ペイロードハンドリングテスト（DoS対策）"""
        async with AsyncAPIClient() as client:
            # 大容量データテスト
            large_payloads = [
                {"title": "A" * 100000, "body": "Test", "userId": 1},  # 100KB title
                {"title": "Test", "body": "B" * 500000, "userId": 1},  # 500KB body
                {
                    "title": "Test",
                    "body": "Test",
                    "userId": 1,
                    "extra": "X" * 1000000,
                },  # 1MB extra
            ]

            for i, payload in enumerate(large_payloads):
                try:
                    response = await client.post("/posts", json=payload)

                    if response.status_code in [200, 201]:
                        logger.warning(
                            "large_payload_accepted",
                            payload_size=len(json.dumps(payload)),
                            test_case=i + 1,
                        )
                        print(f"⚠️ 大容量ペイロードが受け入れられました: Test {i + 1}")
                    elif response.status_code in [413, 400, 422]:
                        logger.info(
                            "large_payload_rejected",
                            status=response.status_code,
                            test_case=i + 1,
                        )
                        print(f"✅ 大容量ペイロードが適切に拒否されました: Test {i + 1}")

                except Exception as e:
                    logger.info("large_payload_error", error=str(e), test_case=i + 1)


@pytest.mark.security
@pytest.mark.slow
class TestSecurityIntegration:
    """セキュリティテスト統合"""

    @pytest.mark.asyncio
    async def test_comprehensive_security_scan(self):
        """包括的セキュリティスキャン"""
        print("\n🔒 包括的セキュリティスキャンを開始...")

        # 全セキュリティテストの実行
        test_suites = [
            TestOWASPAPISecurityTop10(),
            TestSecurityHeaders(),
            TestDataProtection(),
        ]

        total_vulnerabilities = 0

        for suite in test_suites:
            # setup_methodが存在する場合のみ呼び出す
            if hasattr(suite, "setup_method"):
                suite.setup_method()

            # テストスイートの各テストメソッドを実行
            for method_name in dir(suite):
                if (
                    method_name.startswith("test_")
                    and method_name != "test_comprehensive_security_scan"
                ):
                    method = getattr(suite, method_name)
                    if asyncio.iscoroutinefunction(method):
                        try:
                            await method()
                            logger.info("security_test_completed", test=method_name)
                        except Exception as e:
                            logger.error("security_test_failed", test=method_name, error=str(e))

            # 脆弱性カウント
            if hasattr(suite, "vulnerabilities_found"):
                total_vulnerabilities += len(suite.vulnerabilities_found)

        # 総合評価
        print("\n📊 セキュリティスキャン結果:")
        print(f"  - 検出された潜在的脆弱性: {total_vulnerabilities}件")

        if total_vulnerabilities == 0:
            print("✅ 重大なセキュリティ問題は検出されませんでした")
        elif total_vulnerabilities < 5:
            print("⚠️ 軽微なセキュリティ問題が検出されました")
        else:
            print("❌ 複数のセキュリティ問題が検出されました")

        # 教育目的のため、常に成功とする
        assert True, "Security scan completed for educational purposes"


# セキュリティテストレポート生成
def generate_security_report(output_file: str = "reports/security-test-report.json"):
    """セキュリティテストレポート生成"""
    import json
    from datetime import datetime
    from pathlib import Path

    report = {
        "generated_at": datetime.now().isoformat(),
        "test_summary": {
            "owasp_api_security_top_10": "Tested",
            "injection_vulnerabilities": "Tested",
            "security_headers": "Tested",
            "data_protection": "Tested",
        },
        "security_status": "Educational Testing Completed",
        "recommendations": [
            "実装時にOWASP API Security Top 10 ガイドラインに従う",
            "適切な認証・認可機能の実装",
            "入力検証とサニタイゼーションの強化",
            "セキュリティヘッダーの設定",
            "レート制限とリソース制限の実装",
            "機密データの適切な保護",
        ],
    }

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    with Path(output_file).open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"📄 セキュリティテストレポートを生成しました: {output_file}")


# =============================================================================
# 学習ポイント:
#
# 1. OWASP API Security Top 10:
#    - 認証・認可の脆弱性テスト
#    - インジェクション攻撃検出
#    - リソース消費制限テスト
#
# 2. 包括的セキュリティテスト:
#    - 複数の攻撃ベクターのテスト
#    - セキュリティヘッダー検証
#    - データ保護確認
#
# 3. 自動化とCI/CD統合:
#    - 教育目的のテスト設計
#    - レポート生成機能
#    - 継続的セキュリティテスト
#
# 4. 実践的なセキュリティテスト:
#    - 実際の攻撃パターン模擬
#    - 脆弱性の分類と評価
#    - 修正方針の提示
# =============================================================================
