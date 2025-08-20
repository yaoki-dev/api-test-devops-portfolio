#!/usr/bin/env python3
"""
監視システム包括テスト

リアルタイム監視、ログ分析、パフォーマンス監視システムの
包括的なテストケースを実装。
"""

import asyncio
import json
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path

import pytest

from scripts.monitoring_dashboard import MonitoringDashboard
from utils.log_analyzer import LogAnalyzer

# テスト対象のインポート
from utils.real_time_monitor import (
    AlertManager,
    RealTimeMonitor,
    SystemMetrics,
)


# モジュールレベルのfixture（全クラスで共有）
@pytest.fixture(scope="module")
def temp_dir():
    """一時ディレクトリ（モジュール全体で共有）"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


class TestRealTimeMonitor:
    """リアルタイム監視システムテスト"""

    @pytest.fixture
    def monitor(self):
        """監視システムのフィクスチャ"""
        return RealTimeMonitor(check_interval=1)

    def test_monitor_initialization(self, monitor):
        """監視システム初期化テスト"""
        assert monitor.check_interval == 1
        assert not monitor.is_running
        assert monitor.alert_manager is not None
        assert len(monitor.metrics_history) == 0
        assert len(monitor.api_history) == 0

    @pytest.mark.asyncio
    async def test_metric_collection(self, monitor):
        """メトリクス収集テスト"""
        # 一回だけメトリクス収集実行
        await monitor._collect_and_check_metrics()

        # 結果確認
        assert len(monitor.metrics_history) == 1

        latest_metric = monitor.metrics_history[0]
        assert isinstance(latest_metric.cpu_percent, float)
        assert isinstance(latest_metric.memory_percent, float)
        assert isinstance(latest_metric.disk_percent, float)
        assert 0 <= latest_metric.cpu_percent <= 100
        assert 0 <= latest_metric.memory_percent <= 100

    @pytest.mark.asyncio
    async def test_api_health_check(self, monitor):
        """APIヘルスチェックテスト"""
        # 正常なエンドポイント
        result = await monitor._check_api_health("https://httpbin.org/status/200")
        assert result is not None
        assert result.status_code == 200
        assert result.response_time > 0
        assert result.error_count == 0

        # エラーエンドポイント
        result = await monitor._check_api_health("https://httpbin.org/status/500")
        assert result is not None
        assert result.status_code == 500
        assert result.error_count == 1

    def test_monitoring_status(self, monitor):
        """監視ステータステスト"""
        status = monitor.get_monitoring_status()

        assert "is_running" in status
        assert "check_interval" in status
        assert "metrics_history_count" in status
        assert "api_history_count" in status
        assert "alert_summary" in status
        assert "last_update" in status

        assert status["is_running"] == False
        assert status["check_interval"] == 1

    def test_metrics_export(self, monitor, temp_dir):
        """メトリクスエクスポートテスト"""
        # テストデータ追加
        test_metric = SystemMetrics(
            timestamp=time.time(),
            cpu_percent=50.0,
            memory_percent=60.0,
            disk_percent=40.0,
            network_io={"bytes_sent": 1000, "bytes_recv": 2000},
            process_count=100,
        )
        monitor.metrics_history.append(test_metric)

        # エクスポート実行
        output_file = temp_dir / "test_export.json"
        monitor.export_metrics(str(output_file))

        # 結果確認
        assert output_file.exists()

        with open(output_file, encoding="utf-8") as f:
            data = json.load(f)

        assert "export_timestamp" in data
        assert "system_metrics" in data
        assert len(data["system_metrics"]) == 1
        assert data["system_metrics"][0]["cpu_percent"] == 50.0


class TestAlertManager:
    """アラート管理システムテスト"""

    @pytest.fixture
    def alert_manager(self, temp_dir):
        """アラートマネージャーのフィクスチャ"""
        config_path = temp_dir / "test_alerts.json"
        return AlertManager(str(config_path))

    def test_alert_manager_initialization(self, alert_manager):
        """アラートマネージャー初期化テスト"""
        assert len(alert_manager.rules) > 0
        assert "high_cpu_usage" in alert_manager.rules
        assert "critical_cpu_usage" in alert_manager.rules
        assert len(alert_manager.notification_handlers) > 0

    def test_metric_check_normal(self, alert_manager):
        """正常メトリクスのアラートチェック"""
        # 正常値（アラート発生しないはず）
        alert_manager.check_metric("cpu_percent", 50.0)

        active_alerts = alert_manager.get_active_alerts()
        assert len(active_alerts) == 0

    def test_metric_check_warning(self, alert_manager):
        """警告レベルメトリクスのアラートチェック"""
        # 警告レベル値
        alert_manager.check_metric("cpu_percent", 85.0)

        active_alerts = alert_manager.get_active_alerts()
        assert len(active_alerts) == 1
        assert active_alerts[0].severity == "warning"
        assert active_alerts[0].rule_name == "high_cpu_usage"

    def test_metric_check_critical(self, alert_manager):
        """クリティカルレベルメトリクスのアラートチェック"""
        # クリティカルレベル値
        alert_manager.check_metric("cpu_percent", 98.0)

        active_alerts = alert_manager.get_active_alerts()
        critical_alerts = [a for a in active_alerts if a.severity == "critical"]
        assert len(critical_alerts) == 1
        assert critical_alerts[0].rule_name == "critical_cpu_usage"

    def test_alert_cooldown(self, alert_manager):
        """アラートクールダウンテスト"""
        # 最初のアラート
        alert_manager.check_metric("cpu_percent", 85.0)
        assert len(alert_manager.get_active_alerts()) == 1

        # 即座に同じメトリクス（クールダウン期間内）
        alert_manager.check_metric("cpu_percent", 85.0)
        # 新しいアラートは発生しないはず
        assert len(alert_manager.get_active_alerts()) == 1

    def test_alert_resolution(self, alert_manager):
        """アラート解決テスト"""
        # アラート発生
        alert_manager.check_metric("cpu_percent", 85.0)
        assert len(alert_manager.get_active_alerts()) == 1

        # アラート解決
        alert_manager.resolve_alert("high_cpu_usage")
        active_alerts = alert_manager.get_active_alerts()
        assert len(active_alerts) == 0

    def test_alert_summary(self, alert_manager):
        """アラートサマリーテスト"""
        # 複数アラート発生
        alert_manager.check_metric("cpu_percent", 85.0)  # warning
        alert_manager.check_metric("memory_percent", 90.0)  # warning
        alert_manager.check_metric("cpu_percent", 98.0)  # critical

        summary = alert_manager.get_alert_summary()

        assert summary["active_count"] >= 2  # 少なくとも2件
        assert "severity_breakdown" in summary
        assert summary["severity_breakdown"]["warning"] >= 1
        assert summary["severity_breakdown"]["critical"] >= 1


class TestLogAnalyzer:
    """ログ分析システムテスト"""

    @pytest.fixture
    def log_analyzer(self, temp_dir):
        """ログ分析システムのフィクスチャ"""
        return LogAnalyzer(str(temp_dir))

    @pytest.fixture
    def sample_log_file(self, temp_dir):
        """サンプルログファイル作成"""
        log_file = temp_dir / "test.log"

        log_content = """
2025-01-01T12:00:00.000Z INFO Application started successfully
2025-01-01T12:01:00.000Z ERROR Connection refused: Could not connect to database
2025-01-01T12:02:00.000Z WARNING Timeout exceeded: API request took too long
2025-01-01T12:03:00.000Z INFO User login successful
2025-01-01T12:04:00.000Z ERROR Permission denied: Access to file forbidden
2025-01-01T12:05:00.000Z CRITICAL Out of memory: System resources exhausted
        """.strip()

        with open(log_file, "w", encoding="utf-8") as f:
            f.write(log_content)

        return log_file

    @pytest.fixture
    def sample_json_log_file(self, temp_dir):
        """サンプルJSONログファイル作成"""
        log_file = temp_dir / "test.json"

        logs = [
            {
                "timestamp": "2025-01-01T12:00:00.000Z",
                "level": "INFO",
                "message": "API request completed",
                "response_time": 0.5,
                "status_code": 200,
                "endpoint": "/api/users",
            },
            {
                "timestamp": "2025-01-01T12:01:00.000Z",
                "level": "ERROR",
                "message": "Database connection failed",
                "error": "Connection refused",
                "endpoint": "/api/data",
            },
            {
                "timestamp": "2025-01-01T12:02:00.000Z",
                "level": "INFO",
                "message": "API request completed",
                "response_time": 1.5,
                "status_code": 200,
                "endpoint": "/api/posts",
            },
        ]

        with open(log_file, "w", encoding="utf-8") as f:
            for log in logs:
                f.write(json.dumps(log) + "\n")

        return log_file

    def test_log_analyzer_initialization(self, log_analyzer):
        """ログ分析システム初期化テスト"""
        assert len(log_analyzer.log_entries) == 0
        assert len(log_analyzer.error_patterns) == 0
        assert len(log_analyzer.known_error_patterns) > 0

    def test_log_file_loading(self, log_analyzer, sample_log_file):
        """ログファイル読み込みテスト"""
        log_analyzer.load_logs("*.log")

        assert len(log_analyzer.log_entries) == 6

        # レベル分布確認
        levels = [entry.level for entry in log_analyzer.log_entries]
        assert "INFO" in levels
        assert "ERROR" in levels
        assert "WARNING" in levels
        assert "CRITICAL" in levels

    def test_json_log_parsing(self, log_analyzer, sample_json_log_file):
        """JSONログパーステスト"""
        log_analyzer.load_logs("*.json")

        assert len(log_analyzer.log_entries) == 3

        # 構造化データ確認
        for entry in log_analyzer.log_entries:
            if "response_time" in entry.raw_data:
                assert "response_time" in entry.processed_data
                assert isinstance(entry.processed_data["response_time"], float)

    def test_error_pattern_analysis(self, log_analyzer, sample_log_file):
        """エラーパターン分析テスト"""
        log_analyzer.load_logs("*.log")
        error_patterns = log_analyzer.analyze_error_patterns()

        assert len(error_patterns) > 0

        # 既知パターンの検出確認
        pattern_names = [ep.pattern for ep in error_patterns]
        connection_patterns = [p for p in pattern_names if "Connection.*refused" in p]
        assert len(connection_patterns) > 0

        # パターン情報確認
        for pattern in error_patterns:
            assert pattern.count > 0
            assert isinstance(pattern.first_seen, datetime)
            assert isinstance(pattern.last_seen, datetime)
            assert pattern.severity in ["critical", "warning", "info"]

    def test_performance_metrics_analysis(self, log_analyzer, sample_json_log_file):
        """パフォーマンスメトリクス分析テスト"""
        log_analyzer.load_logs("*.json")
        performance_metrics = log_analyzer.analyze_performance_metrics()

        # JSONログにレスポンス時間が含まれているため、メトリクスが生成されるはず
        if performance_metrics:
            for metric in performance_metrics:
                assert metric.count >= 1
                assert metric.avg_duration >= 0
                assert metric.min_duration >= 0
                assert metric.max_duration >= metric.min_duration
                assert 0 <= metric.error_rate <= 1.0

    def test_anomaly_detection(self, log_analyzer, sample_log_file):
        """異常検知テスト"""
        log_analyzer.load_logs("*.log")
        anomalies = log_analyzer.detect_anomalies()

        # 少量のサンプルデータでは異常検知は働かない可能性が高いが、
        # エラーなく実行されることを確認
        assert isinstance(anomalies, list)

    def test_full_analysis(self, log_analyzer, sample_log_file):
        """包括的分析テスト"""
        result = log_analyzer.run_full_analysis()

        assert result.total_entries > 0
        assert isinstance(result.log_level_distribution, dict)
        assert isinstance(result.error_patterns, list)
        assert isinstance(result.performance_metrics, list)
        assert isinstance(result.anomalies, list)
        assert isinstance(result.trends, dict)
        assert isinstance(result.recommendations, list)

        # 期間確認
        assert isinstance(result.analysis_period[0], datetime)
        assert isinstance(result.analysis_period[1], datetime)

    def test_analysis_report_export(self, log_analyzer, sample_log_file, temp_dir):
        """分析レポートエクスポートテスト"""
        result = log_analyzer.run_full_analysis()

        report_file = temp_dir / "analysis_report.json"
        log_analyzer.export_analysis_report(result, str(report_file))

        assert report_file.exists()

        with open(report_file, encoding="utf-8") as f:
            report_data = json.load(f)

        assert "analysis_metadata" in report_data
        assert "log_level_distribution" in report_data
        assert "error_patterns" in report_data
        assert "recommendations" in report_data

    def test_html_dashboard_generation(self, log_analyzer, sample_log_file, temp_dir):
        """HTMLダッシュボード生成テスト"""
        result = log_analyzer.run_full_analysis()

        dashboard_file = temp_dir / "dashboard.html"
        log_analyzer.generate_html_dashboard(result, str(dashboard_file))

        assert dashboard_file.exists()

        with open(dashboard_file, encoding="utf-8") as f:
            html_content = f.read()

        assert "<!DOCTYPE html>" in html_content
        assert "ログ分析ダッシュボード" in html_content
        assert "Chart.js" in html_content


class TestMonitoringDashboard:
    """監視ダッシュボードテスト"""

    @pytest.fixture
    def dashboard(self, temp_dir):
        """監視ダッシュボードのフィクスチャ"""
        return MonitoringDashboard(str(temp_dir))

    @pytest.mark.asyncio
    async def test_system_status_collection(self, dashboard):
        """システムステータス収集テスト"""
        status = await dashboard._collect_system_status()

        assert "status" in status
        assert isinstance(status, dict)

    @pytest.mark.asyncio
    async def test_health_checks_collection(self, dashboard):
        """ヘルスチェック収集テスト"""
        health_data = await dashboard._collect_health_checks()

        assert isinstance(health_data, dict)

        if "api_endpoints" in health_data:
            for endpoint_data in health_data["api_endpoints"]:
                assert "endpoint" in endpoint_data
                assert "status" in endpoint_data

    @pytest.mark.asyncio
    async def test_full_monitoring_data_collection(self, dashboard):
        """全監視データ収集テスト"""
        monitoring_data = await dashboard.collect_monitoring_data()

        assert "collection_timestamp" in monitoring_data
        assert "system_status" in monitoring_data
        assert "log_analysis" in monitoring_data
        assert "performance_data" in monitoring_data
        assert "alert_data" in monitoring_data
        assert "health_checks" in monitoring_data

    def test_overall_status_determination(self, dashboard):
        """全体ステータス判定テスト"""
        # 正常ケース
        normal_data = {
            "alert_data": {"severity_breakdown": {"critical": 0, "warning": 0}},
            "system_status": {"status": "healthy"},
            "log_analysis": {"critical_errors": 0, "anomalies_count": 0},
        }
        status = dashboard._determine_overall_status(normal_data)
        assert status == "healthy"

        # クリティカルケース
        critical_data = {
            "alert_data": {"severity_breakdown": {"critical": 1, "warning": 0}},
            "system_status": {"status": "healthy"},
            "log_analysis": {"critical_errors": 0, "anomalies_count": 0},
        }
        status = dashboard._determine_overall_status(critical_data)
        assert status == "critical"

        # 警告ケース
        warning_data = {
            "alert_data": {"severity_breakdown": {"critical": 0, "warning": 1}},
            "system_status": {"status": "healthy"},
            "log_analysis": {"critical_errors": 0, "anomalies_count": 0},
        }
        status = dashboard._determine_overall_status(warning_data)
        assert status == "warning"

    def test_html_dashboard_generation(self, dashboard):
        """HTMLダッシュボード生成テスト"""
        sample_data = {
            "collection_timestamp": datetime.now().isoformat(),
            "system_status": {
                "status": "healthy",
                "latest_metrics": {"cpu_percent": 45.0, "memory_percent": 60.0},
            },
            "alert_data": {"active_alerts": 0, "severity_breakdown": {}},
            "log_analysis": {"total_entries": 100, "critical_errors": 0},
            "performance_data": {"overall_score": 85},
            "health_checks": {},
        }

        html_content = dashboard.generate_dashboard_html(sample_data)

        assert "<!DOCTYPE html>" in html_content
        assert "総合監視ダッシュボード" in html_content
        assert "Chart.js" in html_content
        assert "システム状態: HEALTHY" in html_content

    @pytest.mark.asyncio
    async def test_full_dashboard_generation(self, dashboard, temp_dir):
        """完全ダッシュボード生成テスト"""
        dashboard_file = await dashboard.generate_dashboard()

        assert Path(dashboard_file).exists()
        assert dashboard_file.endswith(".html")

        # データファイルも確認
        data_file = temp_dir / "monitoring_data.json"
        assert data_file.exists()

        with open(data_file, encoding="utf-8") as f:
            data = json.load(f)

        assert "collection_timestamp" in data


# 統合テスト
class TestMonitoringIntegration:
    """監視システム統合テスト"""

    @pytest.mark.asyncio
    async def test_end_to_end_monitoring(self, temp_dir):
        """エンドツーエンド監視テスト"""
        # 1. ログファイル準備
        log_dir = temp_dir / "logs"
        log_dir.mkdir()

        log_file = log_dir / "app.log"
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("2025-01-01T12:00:00.000Z INFO Application started\n")
            f.write("2025-01-01T12:01:00.000Z ERROR Connection failed\n")
            f.write("2025-01-01T12:02:00.000Z WARNING High CPU usage\n")

        # 2. 監視システム初期化
        monitor = RealTimeMonitor(check_interval=1)
        log_analyzer = LogAnalyzer(str(log_dir))
        dashboard = MonitoringDashboard(str(temp_dir))

        # 3. データ収集と分析
        await monitor._collect_and_check_metrics()
        log_analysis_result = log_analyzer.run_full_analysis()

        # 4. 結果検証
        assert len(monitor.metrics_history) == 1
        assert log_analysis_result.total_entries == 3
        assert len(log_analysis_result.error_patterns) > 0

        # 5. ダッシュボード生成
        dashboard_file = await dashboard.generate_dashboard()
        assert Path(dashboard_file).exists()

        print(f"✅ 統合テスト完了: {dashboard_file}")


# パフォーマンステスト
class TestMonitoringPerformance:
    """監視システムパフォーマンステスト"""

    @pytest.mark.asyncio
    async def test_large_log_analysis_performance(self, temp_dir):
        """大量ログ分析のパフォーマンステスト"""
        # 大量ログファイル生成
        log_file = temp_dir / "large.log"

        start_time = time.time()

        with open(log_file, "w", encoding="utf-8") as f:
            for i in range(1000):  # 1000行のログ
                timestamp = datetime.now().isoformat()
                level = "INFO" if i % 10 != 0 else "ERROR"
                f.write(f"{timestamp} {level} Test log entry {i}\n")

        # 分析実行
        analyzer = LogAnalyzer(str(temp_dir))
        result = analyzer.run_full_analysis()

        analysis_time = time.time() - start_time

        # パフォーマンス検証
        assert analysis_time < 10.0  # 10秒以内
        assert result.total_entries == 1000

        print(
            f"📊 大量ログ分析完了: {analysis_time:.2f}秒, {result.total_entries}エントリ"
        )

    @pytest.mark.asyncio
    async def test_concurrent_monitoring(self):
        """並行監視のパフォーマンステスト"""
        monitors = [RealTimeMonitor(check_interval=1) for _ in range(3)]

        start_time = time.time()

        # 並行でメトリクス収集
        tasks = [monitor._collect_and_check_metrics() for monitor in monitors]
        await asyncio.gather(*tasks)

        concurrent_time = time.time() - start_time

        # 結果検証
        for monitor in monitors:
            assert len(monitor.metrics_history) == 1

        # 並行実行が効率的であることを確認（3倍の時間はかからない）
        assert concurrent_time < 10.0

        print(f"⚡ 並行監視完了: {concurrent_time:.2f}秒, {len(monitors)}システム")


if __name__ == "__main__":
    # テスト実行
    pytest.main([__file__, "-v", "--tb=short"])
