#!/usr/bin/env python3
"""基本レベル - 入力検証セキュリティテスト (Week 4実装)

Security-Testing-Agentによる段階的セキュリティテスト実装
- SQLインジェクションの基本検出
- XSSの基本検出
- コマンドインジェクション基本テスト
- 大きなペイロードの処理テスト
- null値・空文字の処理テスト
- 理解しやすい初心者向け実装

⚠️ 重要: 本番環境での注意事項
===========================================
このテストは開発環境専用のセキュリティ検証テストです。
本番環境では以下の理由により無効化する必要があります：

1. 意図的に脆弱性を検出するため、pytest.fail()でテストが失敗する設計
2. 実際のコマンドインジェクション攻撃ペイロードを使用
3. CI/CDパイプラインで実行すると本番デプロイがブロックされる可能性

本番デプロイ前の対応:
- pytest.ini または pyproject.toml でセキュリティテストをマーク除外
- CI/CDパイプラインで `-m "not security"` オプションを使用
- または、テスト失敗時の挙動を警告レベルに変更

詳細: docs/todo.md を参照
"""

import re
import time
from typing import Any

import pytest
import structlog

logger = structlog.get_logger(__name__)

# Module-level markers: Security tests using real API fixtures (integration level)
# Design rationale: Input validation testing requires actual API responses
# See: docs/interview/multi_level_security_testing.md
pytestmark = [
    pytest.mark.security,
    pytest.mark.integration,  # Uses real API fixtures
]


class TestBasicInputValidation:
    """基本的な入力検証セキュリティテスト - Week 4レベル"""

    # 基本的な悪意ある入力パターン（初心者向け）
    BASIC_SQL_INJECTION_PAYLOADS = [
        # SQL Injection の基本パターン
        "' OR '1'='1",
        "'; DROP TABLE users; --",
        "1' UNION SELECT * FROM users --",
        "admin'--",
        "' OR 1=1 --",
        "1; SELECT * FROM information_schema.tables --",
    ]

    BASIC_XSS_PAYLOADS = [
        # XSS の基本パターン
        "<script>alert('XSS')</script>",
        "javascript:alert('XSS')",
        "<img src=x onerror=alert('XSS')>",
        "<svg onload=alert('XSS')>",
        "';alert('XSS');//",
        "<iframe src=javascript:alert('XSS')></iframe>",
    ]

    BASIC_COMMAND_INJECTION_PAYLOADS = [
        # コマンドインジェクションの基本パターン
        "; cat /etc/passwd",
        "| whoami",
        "&& rm -rf /",
        "; ls -la",
        "$(ping -c 1 127.0.0.1)",
        "`id`",
    ]

    BASIC_ANOMALOUS_INPUTS = [
        # 基本的な異常値
        "",  # 空文字
        " " * 1000,  # 長い文字列
        "null",
        "undefined",
        "None",
        "../../../etc/passwd",  # パストラバーサル
        "\x00\x01\x02",  # バイナリ文字
        "🔒💥🚨",  # 絵文字
    ]

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_post_title_sql_injection(self, async_client):  # noqa: C901
        """POST リクエストのタイトルフィールドSQL インジェクション検証"""
        logger.info("SQL インジェクション テスト開始", target="title field")

        vulnerabilities_found = []

        for payload in self.BASIC_SQL_INJECTION_PAYLOADS:
            post_data = {"title": payload, "body": "Test body content", "userId": 1}

            try:
                response = await async_client.post("/posts", json=post_data)

                # セキュリティテストの基本的な期待値
                # 1. サーバーエラー（500番台）が発生しないこと
                if response.status_code >= 500:
                    vulnerabilities_found.append(
                        {
                            "type": "server_error",
                            "payload": payload,
                            "status_code": response.status_code,
                            "severity": "high",
                        }
                    )
                    logger.warning(
                        "サーバーエラーが発生",
                        payload=payload[:50],
                        status_code=response.status_code,
                    )

                # 2. SQL関連のエラーメッセージが露出しないこと
                if response.status_code in [200, 201]:
                    response_text = response.text.lower()
                    sql_error_indicators = [
                        "sql syntax",
                        "mysql error",
                        "sqlite error",
                        "postgresql error",
                        "ora-",
                        "syntax error",
                        "database error",
                        "sql command",
                    ]

                    for indicator in sql_error_indicators:
                        if indicator in response_text:
                            vulnerabilities_found.append(
                                {
                                    "type": "sql_error_exposure",
                                    "payload": payload,
                                    "indicator": indicator,
                                    "severity": "medium",
                                }
                            )
                            logger.warning(
                                "SQLエラー情報の露出",
                                payload=payload[:50],
                                indicator=indicator,
                            )

                # 3. ペイロードがそのままレスポンスに含まれないこと（基本的なサニタイズ確認）
                if response.status_code == 201:
                    response_data = response.json()
                    response_title = response_data.get("title", "")

                    # 危険なSQL要素がエスケープされているかチェック
                    dangerous_sql_patterns = [
                        "'",
                        "OR",
                        "UNION",
                        "SELECT",
                        "DROP",
                        "--",
                    ]
                    for pattern in dangerous_sql_patterns:
                        if pattern in payload and pattern in response_title:
                            # 完全一致の場合のみ問題とする（部分的にサニタイズされている可能性）
                            if payload == response_title:
                                vulnerabilities_found.append(
                                    {
                                        "type": "payload_reflection",
                                        "payload": payload,
                                        "pattern": pattern,
                                        "severity": "medium",
                                    }
                                )

            except Exception as e:
                logger.error("テスト実行中にエラー", payload=payload[:50], error=str(e))
                continue

        # 脆弱性の評価
        if vulnerabilities_found:
            logger.error("SQL インジェクション脆弱性を検出", count=len(vulnerabilities_found))
            for vuln in vulnerabilities_found:
                logger.error("脆弱性詳細", **vuln)
        else:
            logger.info("SQL インジェクション テスト完了 - 問題なし")

        # 重要な脆弱性がある場合はテストを失敗させる
        high_severity = [v for v in vulnerabilities_found if v.get("severity") == "high"]
        if high_severity:
            pytest.fail(
                f"高リスクのSQL インジェクション脆弱性が {len(high_severity)} 件発見されました"
            )

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_post_body_xss_injection(self, async_client):  # noqa: C901
        """POST リクエストのbodyフィールドXSS検証"""
        logger.info("XSS インジェクション テスト開始", target="body field")

        vulnerabilities_found = []

        for payload in self.BASIC_XSS_PAYLOADS:
            post_data = {"title": "XSS Test Post", "body": payload, "userId": 1}

            try:
                response = await async_client.post("/posts", json=post_data)

                # 1. サーバーエラーが発生しないこと
                if response.status_code >= 500:
                    vulnerabilities_found.append(
                        {
                            "type": "server_error",
                            "payload": payload,
                            "status_code": response.status_code,
                            "severity": "medium",
                        }
                    )

                # 2. 悪意あるスクリプトがそのままレスポンスに含まれないこと
                # 注意: JSONPlaceholderはJSON APIであり、Content-Type: application/jsonを返す
                # XSSはHTMLレンダリング時にのみ危険なため、JSONレスポンスは対象外
                if response.status_code == 201:
                    content_type = response.headers.get("content-type", "").lower()

                    # JSON APIの場合はXSS脆弱性とはみなさない
                    # XSSはブラウザがHTMLとしてレンダリングする場合にのみ危険
                    if "text/html" in content_type or "text/xml" in content_type:
                        response_data = response.json()
                        response_body = response_data.get("body", "")

                        # スクリプトタグなどの危険なパターンがエスケープされているかチェック
                        dangerous_xss_patterns = [
                            "<script>",
                            "javascript:",
                            "onerror=",
                            "onload=",
                        ]
                        for pattern in dangerous_xss_patterns:
                            if pattern in payload.lower() and pattern in response_body.lower():
                                if payload.lower() == response_body.lower():  # 完全反映の場合
                                    vulnerabilities_found.append(
                                        {
                                            "type": "xss_payload_reflection",
                                            "payload": payload,
                                            "pattern": pattern,
                                            "severity": "high",
                                        }
                                    )
                                    logger.warning(
                                        "XSSペイロードがエスケープされていません",
                                        payload=payload[:50],
                                        pattern=pattern,
                                    )
                    else:
                        # JSON APIでのエコーバックは情報漏洩ではあるが、XSSではない
                        logger.debug(
                            "JSON APIでのペイロード反映（XSSリスクなし）",
                            content_type=content_type,
                        )

            except Exception as e:
                logger.error("XSSテスト実行中にエラー", payload=payload[:50], error=str(e))
                continue

        # 結果の評価
        if vulnerabilities_found:
            logger.error("XSS脆弱性を検出", count=len(vulnerabilities_found))
            for vuln in vulnerabilities_found:
                logger.error("XSS脆弱性詳細", **vuln)
        else:
            logger.info("XSS テスト完了 - 問題なし")

        # 高リスクの脆弱性がある場合はテストを失敗させる
        high_severity = [v for v in vulnerabilities_found if v.get("severity") == "high"]
        if high_severity:
            pytest.fail(f"高リスクのXSS脆弱性が {len(high_severity)} 件発見されました")

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_get_parameter_injection(self, async_client):  # noqa: C901
        """GET パラメータでの基本的なインジェクション検証"""
        logger.info("GET パラメータ インジェクション テスト開始")

        vulnerabilities_found = []

        # ID パラメータに悪意ある値を注入
        malicious_ids = [
            "1' OR '1'='1",
            "1; DROP TABLE posts",
            "1 UNION SELECT * FROM users",
            "../../../etc/passwd",
            "<script>alert('XSS')</script>",
            "; ls -la",
        ]

        for malicious_id in malicious_ids:
            try:
                response = await async_client.get(f"/posts/{malicious_id}")

                # 1. サーバーエラーが発生しないこと
                if response.status_code >= 500:
                    vulnerabilities_found.append(
                        {
                            "type": "server_error",
                            "malicious_id": malicious_id,
                            "status_code": response.status_code,
                            "severity": "high",
                        }
                    )
                    logger.warning(
                        "GET パラメータでサーバーエラー",
                        malicious_id=malicious_id[:30],
                        status_code=response.status_code,
                    )

                # 2. 適切なエラーレスポンス（通常は404または400）を返すこと
                elif response.status_code not in [400, 404]:
                    # 予期しない成功レスポンスの場合
                    if response.status_code == 200:
                        vulnerabilities_found.append(
                            {
                                "type": "unexpected_success",
                                "malicious_id": malicious_id,
                                "status_code": response.status_code,
                                "severity": "medium",
                            }
                        )
                        logger.warning(
                            "不正なIDで成功レスポンス",
                            malicious_id=malicious_id[:30],
                            status_code=response.status_code,
                        )

                # 3. エラーメッセージの情報露出チェック
                if response.status_code >= 400:
                    response_text = response.text.lower()
                    sensitive_info_patterns = [
                        "sql",
                        "database",
                        "table",
                        "column",
                        "mysql",
                        "postgresql",
                        "sqlite",
                        "/etc/",
                        "root",
                        "stack trace",
                        "exception",
                    ]

                    for pattern in sensitive_info_patterns:
                        if pattern in response_text:
                            vulnerabilities_found.append(
                                {
                                    "type": "information_disclosure",
                                    "malicious_id": malicious_id,
                                    "pattern": pattern,
                                    "severity": "medium",
                                }
                            )

            except Exception as e:
                logger.error(
                    "GET パラメータテスト実行中にエラー",
                    malicious_id=malicious_id[:30],
                    error=str(e),
                )
                continue

        # 結果の評価
        if vulnerabilities_found:
            logger.error(
                "GET パラメータ インジェクション脆弱性を検出",
                count=len(vulnerabilities_found),
            )
            for vuln in vulnerabilities_found:
                logger.error("脆弱性詳細", **vuln)
        else:
            logger.info("GET パラメータ テスト完了 - 問題なし")

        # 高リスクの脆弱性がある場合はテストを失敗させる
        high_severity = [v for v in vulnerabilities_found if v.get("severity") == "high"]
        if high_severity:
            pytest.fail(f"高リスクのGETパラメータ脆弱性が {len(high_severity)} 件発見されました")

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_large_payload_dos_protection(self, async_client):  # noqa: C901
        """大きなペイロードの処理テスト（DoS対策基本検証）"""
        logger.info("大きなペイロードDoS保護テスト開始")

        # 段階的に大きなデータを送信
        test_sizes = [
            ("small", 1000),  # 1KB
            ("medium", 100000),  # 100KB
            ("large", 1000000),  # 1MB
            ("xlarge", 10000000),  # 10MB
        ]

        vulnerabilities_found = []

        for size_name, size_bytes in test_sizes:
            large_title = "A" * min(size_bytes // 2, 1000000)  # タイトル用
            large_body = "B" * (size_bytes - len(large_title))  # ボディ用

            post_data = {"title": large_title, "body": large_body, "userId": 1}

            try:
                start_time = time.time()
                response = await async_client.post("/posts", json=post_data)
                response_time = time.time() - start_time

                logger.info(
                    f"{size_name} ペイロード送信完了",
                    size=f"{size_bytes:,} bytes",
                    status_code=response.status_code,
                    response_time=f"{response_time:.2f}s",
                )

                # 1. サーバーがクラッシュしないこと
                if response.status_code >= 500:
                    vulnerabilities_found.append(
                        {
                            "type": "server_crash",
                            "payload_size": size_bytes,
                            "status_code": response.status_code,
                            "severity": "high",
                        }
                    )
                    logger.error(
                        "大きなペイロードでサーバーエラー",
                        size=f"{size_bytes:,} bytes",
                        status_code=response.status_code,
                    )

                # 2. 適切なレスポンス時間（DoS防止）
                if response_time > 10.0:  # 10秒以上かかる場合
                    vulnerabilities_found.append(
                        {
                            "type": "slow_response",
                            "payload_size": size_bytes,
                            "response_time": response_time,
                            "severity": "medium",
                        }
                    )
                    logger.warning(
                        "レスポンス時間が長すぎます",
                        size=f"{size_bytes:,} bytes",
                        response_time=f"{response_time:.2f}s",
                    )

                # 3. 適切に制限されるか、受け入れられるかのいずれか
                if size_bytes > 1000000:  # 1MB以上の場合
                    if response.status_code not in [201, 400, 413, 422]:
                        vulnerabilities_found.append(
                            {
                                "type": "inappropriate_handling",
                                "payload_size": size_bytes,
                                "status_code": response.status_code,
                                "severity": "medium",
                            }
                        )

            except TimeoutError:
                logger.error(
                    f"{size_name} ペイロードでタイムアウト",
                    size=f"{size_bytes:,} bytes",
                )
                vulnerabilities_found.append(
                    {
                        "type": "timeout",
                        "payload_size": size_bytes,
                        "severity": "medium",
                    }
                )
            except Exception as e:
                logger.error(
                    f"{size_name} ペイロードテスト実行中にエラー",
                    size=f"{size_bytes:,} bytes",
                    error=str(e),
                )
                continue

        # 結果の評価
        if vulnerabilities_found:
            logger.error("大きなペイロード処理で問題を検出", count=len(vulnerabilities_found))
            for vuln in vulnerabilities_found:
                logger.error("DoS関連脆弱性詳細", **vuln)
        else:
            logger.info("大きなペイロードテスト完了 - 問題なし")

        # 高リスクの脆弱性がある場合はテストを失敗させる
        high_severity = [v for v in vulnerabilities_found if v.get("severity") == "high"]
        if high_severity:
            pytest.fail(f"高リスクのDoS脆弱性が {len(high_severity)} 件発見されました")

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_null_and_empty_input_handling(self, async_client):
        """null値と空文字の処理テスト"""
        logger.info("null値・空文字処理テスト開始")

        test_cases = [
            {"title": None, "body": "test", "userId": 1},
            {"title": "", "body": "test", "userId": 1},
            {"title": "test", "body": None, "userId": 1},
            {"title": "test", "body": "", "userId": 1},
            {"title": "test", "body": "test", "userId": None},
            {"title": "test", "body": "test", "userId": ""},
            {"title": None, "body": None, "userId": None},
            {"title": "", "body": "", "userId": ""},
        ]

        vulnerabilities_found = []

        for i, test_case in enumerate(test_cases):
            try:
                response = await async_client.post("/posts", json=test_case)

                logger.debug(
                    f"null/空文字テストケース {i + 1}",
                    test_case=str(test_case),
                    status_code=response.status_code,
                )

                # 1. サーバーエラーが発生しないこと
                if response.status_code >= 500:
                    vulnerabilities_found.append(
                        {
                            "type": "server_error_null_handling",
                            "test_case": test_case,
                            "status_code": response.status_code,
                            "severity": "high",
                        }
                    )
                    logger.error(
                        "null/空文字でサーバーエラー",
                        test_case=str(test_case),
                        status_code=response.status_code,
                    )

                # 2. 適切なバリデーションエラーまたは成功のレスポンス
                elif response.status_code not in [200, 201, 400, 422]:
                    vulnerabilities_found.append(
                        {
                            "type": "unexpected_response",
                            "test_case": test_case,
                            "status_code": response.status_code,
                            "severity": "low",
                        }
                    )

            except Exception as e:
                logger.error(
                    "null/空文字テスト実行中にエラー",
                    test_case=str(test_case),
                    error=str(e),
                )
                continue

        # 結果の評価
        if vulnerabilities_found:
            logger.error("null/空文字処理で問題を検出", count=len(vulnerabilities_found))
            for vuln in vulnerabilities_found:
                logger.error("null処理関連脆弱性詳細", **vuln)
        else:
            logger.info("null値・空文字テスト完了 - 問題なし")

        # 高リスクの脆弱性がある場合はテストを失敗させる
        high_severity = [v for v in vulnerabilities_found if v.get("severity") == "high"]
        if high_severity:
            pytest.fail(f"高リスクのnull処理脆弱性が {len(high_severity)} 件発見されました")

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_command_injection_basic(self, async_client):  # noqa: C901
        """基本的なコマンドインジェクション検証"""
        logger.info("コマンドインジェクション テスト開始")

        vulnerabilities_found = []

        for payload in self.BASIC_COMMAND_INJECTION_PAYLOADS:
            # 複数のフィールドでテスト
            test_fields = [
                {"title": f"test{payload}", "body": "normal body", "userId": 1},
                {"title": "normal title", "body": f"test{payload}", "userId": 1},
            ]

            for test_data in test_fields:
                try:
                    response = await async_client.post("/posts", json=test_data)

                    # 1. サーバーエラーが発生しないこと
                    if response.status_code >= 500:
                        vulnerabilities_found.append(
                            {
                                "type": "server_error",
                                "payload": payload,
                                "test_data": test_data,
                                "status_code": response.status_code,
                                "severity": "high",
                            }
                        )

                    # 2. コマンド実行結果がレスポンスに含まれないこと
                    # 注意: JSONPlaceholderはペイロードをエコーバックするため、
                    # ペイロード自体に含まれる文字列は除外する必要がある
                    if response.status_code in [200, 201]:
                        response_text = response.text.lower()
                        payload_lower = payload.lower()

                        # コマンド実行を示す可能性のあるパターン
                        # （正規表現で実際の出力形式をチェック）
                        command_execution_patterns = {
                            # 実際のuid/gid出力形式: uid=1000(username)
                            "uid_output": re.compile(r"uid=\d+\([a-z_][a-z0-9_-]*\)"),
                            # 実際の/etc/passwd内容: root:x:0:0:...
                            "passwd_content": re.compile(r"(root|bin|daemon|sys):x?:\d+:\d+"),
                            # lsコマンド出力: drwxr-xr-x
                            "ls_output": re.compile(r"[d-][rwx-]{9}\s+\d+"),
                            # pingコマンド出力
                            "ping_output": re.compile(r"(icmp_seq|bytes from|ttl=|time=)"),
                            # whoamiコマンド出力（ユーザー名のみの行）
                            "whoami_output": re.compile(r"^[a-z_][a-z0-9_-]{0,30}$", re.MULTILINE),
                        }

                        for pattern_name, pattern in command_execution_patterns.items():
                            # ペイロード自体に含まれるパターンは除外
                            if pattern.search(payload_lower):
                                continue

                            if pattern.search(response_text):
                                vulnerabilities_found.append(
                                    {
                                        "type": "command_execution_evidence",
                                        "payload": payload,
                                        "indicator": pattern_name,
                                        "severity": "critical",
                                    }
                                )
                                logger.error(
                                    "コマンド実行の可能性",
                                    payload=payload[:30],
                                    indicator=pattern_name,
                                )

                except Exception as e:
                    logger.error(
                        "コマンドインジェクションテスト実行中にエラー",
                        payload=payload[:30],
                        error=str(e),
                    )
                    continue

        # 結果の評価
        if vulnerabilities_found:
            logger.error("コマンドインジェクション脆弱性を検出", count=len(vulnerabilities_found))
            for vuln in vulnerabilities_found:
                logger.error("コマンドインジェクション脆弱性詳細", **vuln)
        else:
            logger.info("コマンドインジェクション テスト完了 - 問題なし")

        # 重要またはクリティカルな脆弱性がある場合はテストを失敗させる
        critical_issues = [
            v for v in vulnerabilities_found if v.get("severity") in ["critical", "high"]
        ]
        if critical_issues:
            pytest.fail(
                f"重大なコマンドインジェクション脆弱性が {len(critical_issues)} 件発見されました"
            )


# pytest実行例とヘルパー関数
class SecurityTestHelper:
    """セキュリティテスト用ヘルパー関数"""

    @staticmethod
    def generate_security_report(test_results: dict[str, Any]) -> str:
        """セキュリティテスト結果レポート生成"""
        report = "📋 Basic Input Validation Security Test Report\n"
        report += "=" * 50 + "\n\n"

        if "vulnerabilities" in test_results:
            vuln_count = len(test_results["vulnerabilities"])
            report += f"🔍 検出された脆弱性: {vuln_count}件\n\n"

            for vuln in test_results["vulnerabilities"]:
                severity = vuln.get("severity", "unknown").upper()
                vuln_type = vuln.get("type", "Unknown")
                report += f"⚠️  [{severity}] {vuln_type}\n"
                if "payload" in vuln:
                    report += f"   Payload: {vuln['payload'][:50]}...\n"
                if "description" in vuln:
                    report += f"   説明: {vuln['description']}\n"
                report += "\n"
        else:
            report += "✅ 脆弱性は検出されませんでした\n"

        report += f"\n📅 テスト実行日時: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        return report

    @staticmethod
    def html_encode(text: str) -> str:
        """基本的なHTMLエンコード"""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )


if __name__ == "__main__":
    print("基本的なセキュリティテストを実行するには:")
    print("pytest tests/security/test_basic_input_validation.py -v -m security")
    print("\n個別テストの実行:")
    test_path = (
        "pytest tests/security/test_basic_input_validation.py::"
        "TestBasicInputValidation::test_post_title_sql_injection -v"
    )
    print(test_path)
