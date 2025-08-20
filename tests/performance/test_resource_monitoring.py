"""
リソース監視テストスイート

実務最適化版パフォーマンステスト:
- CPU・メモリ・ネットワークリソースの総合監視
- リソース使用パターンの分析
- リソース枯渇の早期検出
- パフォーマンスボトルネックの特定

学習ポイント:
- システムリソース監視の実践手法
- リソース使用量とパフォーマンスの相関分析
- メモリリーク・CPU過負荷の検出
- 運用監視に必要なメトリクス収集
"""

import asyncio
import json
import statistics
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil
import pytest

from config.settings import get_settings
from utils.api_client import JSONPlaceholderClient
from utils.performance_monitor import PerformanceMonitor

settings = get_settings()


@dataclass
class ResourceUsageSnapshot:
    """リソース使用量スナップショット"""

    timestamp: float
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    network_sent: int
    network_recv: int
    open_files: int
    thread_count: int
    context: str  # テスト実行コンテキスト


@dataclass
class ResourceTestResult:
    """リソース監視テスト結果"""

    test_name: str
    duration: float
    snapshots: list[ResourceUsageSnapshot]
    peak_cpu: float
    peak_memory_mb: float
    avg_cpu: float
    avg_memory_mb: float
    memory_growth: float  # MB
    cpu_spikes: int
    memory_leaks_detected: bool
    resource_warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_name": self.test_name,
            "duration": self.duration,
            "snapshot_count": len(self.snapshots),
            "peak_cpu": self.peak_cpu,
            "peak_memory_mb": self.peak_memory_mb,
            "avg_cpu": self.avg_cpu,
            "avg_memory_mb": self.avg_memory_mb,
            "memory_growth": self.memory_growth,
            "cpu_spikes": self.cpu_spikes,
            "memory_leaks_detected": self.memory_leaks_detected,
            "resource_warnings": self.resource_warnings,
        }


class ResourceMonitoringConfig:
    """リソース監視設定"""

    # 監視間隔
    MONITORING_INTERVAL = 0.1  # 100ms間隔

    # 警告閾値
    CPU_WARNING_THRESHOLD = 80.0  # CPU使用率80%以上
    MEMORY_WARNING_THRESHOLD = 1000.0  # メモリ使用量1GB以上
    MEMORY_GROWTH_WARNING = 100.0  # 100MB以上の増加

    # リソーススパイク検出
    CPU_SPIKE_THRESHOLD = 90.0  # CPU90%以上をスパイクと判定
    MEMORY_LEAK_THRESHOLD = 50.0  # 50MB以上の永続的増加をリークと判定

    # テスト種別
    TEST_WORKLOADS = {
        "light": {"operations": 10, "concurrency": 5},
        "medium": {"operations": 50, "concurrency": 15},
        "heavy": {"operations": 100, "concurrency": 30},
    }


class ResourceMonitor:
    """リソース監視クラス"""

    def __init__(self):
        self.monitoring = False
        self.snapshots: list[ResourceUsageSnapshot] = []
        self.monitor_thread: threading.Thread | None = None
        self.process = psutil.Process()

    def start_monitoring(self, context: str = "test"):
        """監視開始"""
        self.monitoring = True
        self.snapshots.clear()
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop, args=(context,), daemon=True
        )
        self.monitor_thread.start()

    def stop_monitoring(self) -> list[ResourceUsageSnapshot]:
        """監視停止"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
        return self.snapshots.copy()

    def _monitor_loop(self, context: str):
        """監視ループ"""
        while self.monitoring:
            try:
                # ネットワーク統計
                net_io = psutil.net_io_counters()

                snapshot = ResourceUsageSnapshot(
                    timestamp=time.time(),
                    cpu_percent=psutil.cpu_percent(),
                    memory_mb=self.process.memory_info().rss / 1024 / 1024,
                    memory_percent=self.process.memory_percent(),
                    network_sent=net_io.bytes_sent if net_io else 0,
                    network_recv=net_io.bytes_recv if net_io else 0,
                    open_files=len(self.process.open_files())
                    if hasattr(self.process, "open_files")
                    else 0,
                    thread_count=self.process.num_threads(),
                    context=context,
                )

                self.snapshots.append(snapshot)
                time.sleep(ResourceMonitoringConfig.MONITORING_INTERVAL)

            except Exception as e:
                # 監視エラーは無視（プロセス終了時など）
                break


@pytest.fixture
async def api_client():
    """APIクライアント"""
    client = JSONPlaceholderClient()
    yield client
    await client.close()


@pytest.fixture
def resource_monitor():
    """リソース監視"""
    monitor = ResourceMonitor()
    yield monitor
    # テスト終了時に監視停止
    if monitor.monitoring:
        monitor.stop_monitoring()


@pytest.fixture
def performance_monitor():
    """パフォーマンス監視"""
    monitor = PerformanceMonitor(
        alert_threshold=3.0,
        memory_threshold_mb=ResourceMonitoringConfig.MEMORY_WARNING_THRESHOLD,
        cpu_threshold_percent=ResourceMonitoringConfig.CPU_WARNING_THRESHOLD,
    )
    return monitor


@pytest.mark.performance
@pytest.mark.resource
@pytest.mark.external
@pytest.mark.slow
class TestResourceMonitoring:
    """リソース監視テスト"""

    async def test_baseline_resource_usage(self, api_client, resource_monitor):
        """ベースラインリソース使用量測定

        目的: 最小負荷時のリソース使用量ベースライン確立
        重要: 他のテストとの比較基準
        """
        print("\n📊 ベースラインリソース使用量測定開始")

        # ベースライン監視開始
        resource_monitor.start_monitoring("baseline")

        # 軽い負荷での測定
        start_time = time.time()

        for i in range(10):
            response = await api_client.get_user(1)
            assert response["id"] == 1
            await asyncio.sleep(0.1)  # 100ms間隔

        end_time = time.time()

        # 監視停止
        snapshots = resource_monitor.stop_monitoring()

        # ベースライン分析
        result = self._analyze_resource_usage(
            "baseline", snapshots, end_time - start_time
        )

        # ベースライン結果出力
        self._report_resource_usage(result)

        # ベースラインアサーション
        assert result.peak_cpu < 50.0, (
            f"ベースライン時のCPU使用率が高すぎます: {result.peak_cpu:.1f}% > 50.0%"
        )
        assert result.peak_memory_mb < 500.0, (
            f"ベースライン時のメモリ使用量が大きすぎます: {result.peak_memory_mb:.1f}MB > 500.0MB"
        )
        assert not result.memory_leaks_detected, (
            "ベースライン測定でメモリリークが検出されました"
        )

    @pytest.mark.parametrize("workload_type", ["light", "medium", "heavy"])
    async def test_workload_resource_scaling(
        self, api_client, resource_monitor, workload_type
    ):
        """ワークロード別リソーススケーリング測定

        目的: 負荷レベルに応じたリソース使用量の変化測定
        重要: スケーラビリティとリソース効率性の評価
        """
        workload = ResourceMonitoringConfig.TEST_WORKLOADS[workload_type]
        print(f"\n🚀 {workload_type}ワークロード リソース測定開始")
        print(f"  設定: {workload['operations']}操作, {workload['concurrency']}並行")

        # ワークロード監視開始
        resource_monitor.start_monitoring(f"workload_{workload_type}")

        start_time = time.time()

        # ワークロード実行
        await self._execute_workload(api_client, workload)

        end_time = time.time()

        # 監視停止
        snapshots = resource_monitor.stop_monitoring()

        # ワークロード分析
        result = self._analyze_resource_usage(
            f"workload_{workload_type}", snapshots, end_time - start_time
        )

        # 結果出力
        self._report_resource_usage(result)

        # ワークロード別アサーション
        if workload_type == "light":
            assert result.peak_cpu < 60.0, (
                f"軽負荷でのCPU使用率超過: {result.peak_cpu:.1f}% > 60.0%"
            )
            assert result.memory_growth < 50.0, (
                f"軽負荷でのメモリ増加超過: {result.memory_growth:.1f}MB > 50.0MB"
            )
        elif workload_type == "medium":
            assert result.peak_cpu < 80.0, (
                f"中負荷でのCPU使用率超過: {result.peak_cpu:.1f}% > 80.0%"
            )
            assert result.memory_growth < 100.0, (
                f"中負荷でのメモリ増加超過: {result.memory_growth:.1f}MB > 100.0MB"
            )
        elif workload_type == "heavy":
            assert result.peak_cpu < 95.0, (
                f"高負荷でのCPU使用率超過: {result.peak_cpu:.1f}% > 95.0%"
            )
            assert result.memory_growth < 200.0, (
                f"高負荷でのメモリ増加超過: {result.memory_growth:.1f}MB > 200.0MB"
            )

    async def test_memory_leak_detection(self, api_client, resource_monitor):
        """メモリリーク検出テスト

        目的: 長時間実行でのメモリリーク検出
        重要: メモリ安定性の確認
        """
        print("\n🔍 メモリリーク検出テスト開始")

        # メモリリーク検出用の長時間監視
        resource_monitor.start_monitoring("memory_leak_detection")

        start_time = time.time()

        # 長時間の反復処理（メモリリークを検出するため）
        for cycle in range(5):  # 5サイクル
            print(f"  サイクル {cycle + 1}/5")

            # 各サイクルで一定量の処理
            for i in range(20):
                response = await api_client.get_user((i % 10) + 1)
                assert response["id"] == (i % 10) + 1

            # サイクル間の短い休憩
            await asyncio.sleep(1)

        end_time = time.time()

        # 監視停止
        snapshots = resource_monitor.stop_monitoring()

        # メモリリーク分析
        result = self._analyze_resource_usage(
            "memory_leak_detection", snapshots, end_time - start_time
        )

        # メモリリーク検出
        memory_leak_analysis = self._detect_memory_leaks(snapshots)

        # 結果出力
        self._report_resource_usage(result)
        print("\n🔍 メモリリーク分析:")
        print(f"  総メモリ増加: {result.memory_growth:.1f}MB")
        print(
            f"  メモリリーク検出: {'はい' if memory_leak_analysis['leak_detected'] else 'いいえ'}"
        )

        if memory_leak_analysis["leak_detected"]:
            print(f"  リーク推定量: {memory_leak_analysis['leak_size']:.1f}MB")
            print(f"  リーク傾向: {memory_leak_analysis['leak_trend']}")

        # メモリリークアサーション
        assert not memory_leak_analysis["leak_detected"], (
            f"メモリリークが検出されました: {memory_leak_analysis['leak_size']:.1f}MB"
        )

        assert result.memory_growth < ResourceMonitoringConfig.MEMORY_LEAK_THRESHOLD, (
            f"メモリ増加量が閾値超過: {result.memory_growth:.1f}MB > {ResourceMonitoringConfig.MEMORY_LEAK_THRESHOLD}MB"
        )

    async def test_cpu_spike_monitoring(self, api_client, resource_monitor):
        """CPUスパイク監視テスト

        目的: CPU使用率のスパイク検出と分析
        重要: CPU負荷パターンの理解
        """
        print("\n⚡ CPUスパイク監視テスト開始")

        # CPUスパイク監視開始
        resource_monitor.start_monitoring("cpu_spike_monitoring")

        start_time = time.time()

        # CPU集約的な処理パターン
        burst_patterns = [
            {"duration": 2, "intensity": 10},
            {"duration": 1, "intensity": 30},
            {"duration": 3, "intensity": 5},
        ]

        for i, pattern in enumerate(burst_patterns):
            print(
                f"  バーストパターン {i + 1}: {pattern['intensity']}並行, {pattern['duration']}秒"
            )

            # バースト実行
            await self._execute_cpu_burst(api_client, pattern)

            # バースト間の休憩
            await asyncio.sleep(1)

        end_time = time.time()

        # 監視停止
        snapshots = resource_monitor.stop_monitoring()

        # CPUスパイク分析
        result = self._analyze_resource_usage(
            "cpu_spike_monitoring", snapshots, end_time - start_time
        )
        spike_analysis = self._analyze_cpu_spikes(snapshots)

        # 結果出力
        self._report_resource_usage(result)
        print("\n⚡ CPUスパイク分析:")
        print(f"  検出されたスパイク数: {spike_analysis['spike_count']}")
        print(f"  最大CPU使用率: {spike_analysis['max_cpu']:.1f}%")
        print(f"  平均スパイク持続時間: {spike_analysis['avg_spike_duration']:.2f}秒")

        # CPUスパイクアサーション
        assert spike_analysis["max_cpu"] < 100.0, (
            f"CPU使用率が限界を超過: {spike_analysis['max_cpu']:.1f}%"
        )
        assert spike_analysis["avg_spike_duration"] < 5.0, (
            f"CPUスパイクの持続時間が長すぎます: {spike_analysis['avg_spike_duration']:.2f}秒 > 5.0秒"
        )

    async def test_resource_correlation_analysis(self, api_client, resource_monitor):
        """リソース相関分析テスト

        目的: CPU・メモリ・ネットワークの相関関係分析
        重要: パフォーマンスボトルネックの特定
        """
        print("\n📈 リソース相関分析テスト開始")

        # 相関分析用監視開始
        resource_monitor.start_monitoring("resource_correlation")

        start_time = time.time()

        # 様々なパターンでの負荷実行
        patterns = [
            {"name": "CPU集約", "func": self._cpu_intensive_pattern},
            {"name": "メモリ集約", "func": self._memory_intensive_pattern},
            {"name": "ネットワーク集約", "func": self._network_intensive_pattern},
        ]

        for pattern in patterns:
            print(f"  {pattern['name']}パターン実行中...")
            await pattern["func"](api_client)
            await asyncio.sleep(2)  # パターン間の休憩

        end_time = time.time()

        # 監視停止
        snapshots = resource_monitor.stop_monitoring()

        # 相関分析
        result = self._analyze_resource_usage(
            "resource_correlation", snapshots, end_time - start_time
        )
        correlation_analysis = self._analyze_resource_correlations(snapshots)

        # 結果出力
        self._report_resource_usage(result)
        print("\n📈 リソース相関分析:")

        for correlation in correlation_analysis:
            print(
                f"  {correlation['metric1']} vs {correlation['metric2']}: 相関係数 {correlation['correlation']:.3f}"
            )

        # 相関分析の保存
        await self._save_correlation_report(correlation_analysis, snapshots)

    async def _execute_workload(self, api_client, workload_config):
        """ワークロード実行"""
        operations = workload_config["operations"]
        concurrency = workload_config["concurrency"]

        # 並行タスク生成
        tasks = []
        for i in range(operations):
            # 異なるAPIエンドポイントを循環使用
            if i % 4 == 0:
                task = api_client.get_user((i % 10) + 1)
            elif i % 4 == 1:
                task = api_client.get_post((i % 100) + 1)
            elif i % 4 == 2:
                task = api_client.get_todo((i % 200) + 1)
            else:
                task = api_client.get_comment((i % 500) + 1)

            tasks.append(task)

            # 指定並行数に達したら実行
            if len(tasks) >= concurrency:
                await asyncio.gather(*tasks[:concurrency], return_exceptions=True)
                tasks = tasks[concurrency:]
                await asyncio.sleep(0.01)  # 短い休憩

        # 残りのタスク実行
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_cpu_burst(self, api_client, pattern):
        """CPU集約的バースト実行"""
        end_time = time.time() + pattern["duration"]
        tasks = []

        while time.time() < end_time:
            # 指定強度まで並行タスクを維持
            current_tasks = [t for t in tasks if not t.done()]

            while len(current_tasks) < pattern["intensity"] and time.time() < end_time:
                task = asyncio.create_task(api_client.get_user((len(tasks) % 10) + 1))
                tasks.append(task)
                current_tasks.append(task)

            await asyncio.sleep(0.01)

    async def _cpu_intensive_pattern(self, api_client):
        """CPU集約的パターン"""
        tasks = [api_client.get_user(i) for i in range(1, 21)]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _memory_intensive_pattern(self, api_client):
        """メモリ集約的パターン"""
        # 大量のデータを一時的に保持
        data_cache = []
        for i in range(10):
            response = await api_client.get_post(i + 1)
            data_cache.append(response)

        # データを使用（キャッシュから削除しない）
        await asyncio.sleep(1)

    async def _network_intensive_pattern(self, api_client):
        """ネットワーク集約的パターン"""
        tasks = []
        for i in range(30):  # 大量の短時間リクエスト
            task = api_client.get_comment(i + 1)
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

    def _analyze_resource_usage(
        self, test_name: str, snapshots: list[ResourceUsageSnapshot], duration: float
    ) -> ResourceTestResult:
        """リソース使用量分析"""
        if not snapshots:
            return ResourceTestResult(
                test_name=test_name,
                duration=duration,
                snapshots=[],
                peak_cpu=0,
                peak_memory_mb=0,
                avg_cpu=0,
                avg_memory_mb=0,
                memory_growth=0,
                cpu_spikes=0,
                memory_leaks_detected=False,
                resource_warnings=["データなし"],
            )

        # 基本統計
        cpu_values = [s.cpu_percent for s in snapshots]
        memory_values = [s.memory_mb for s in snapshots]

        peak_cpu = max(cpu_values)
        peak_memory = max(memory_values)
        avg_cpu = statistics.mean(cpu_values)
        avg_memory = statistics.mean(memory_values)

        # メモリ増加量
        memory_growth = (
            memory_values[-1] - memory_values[0] if len(memory_values) > 1 else 0
        )

        # CPUスパイク検出
        cpu_spikes = sum(
            1
            for cpu in cpu_values
            if cpu > ResourceMonitoringConfig.CPU_SPIKE_THRESHOLD
        )

        # メモリリーク検出
        memory_leaks_detected = (
            memory_growth > ResourceMonitoringConfig.MEMORY_LEAK_THRESHOLD
        )

        # 警告生成
        warnings = []
        if peak_cpu > ResourceMonitoringConfig.CPU_WARNING_THRESHOLD:
            warnings.append(f"CPU使用率警告: {peak_cpu:.1f}%")
        if peak_memory > ResourceMonitoringConfig.MEMORY_WARNING_THRESHOLD:
            warnings.append(f"メモリ使用量警告: {peak_memory:.1f}MB")
        if memory_growth > ResourceMonitoringConfig.MEMORY_GROWTH_WARNING:
            warnings.append(f"メモリ増加警告: {memory_growth:.1f}MB")

        return ResourceTestResult(
            test_name=test_name,
            duration=duration,
            snapshots=snapshots,
            peak_cpu=peak_cpu,
            peak_memory_mb=peak_memory,
            avg_cpu=avg_cpu,
            avg_memory_mb=avg_memory,
            memory_growth=memory_growth,
            cpu_spikes=cpu_spikes,
            memory_leaks_detected=memory_leaks_detected,
            resource_warnings=warnings,
        )

    def _detect_memory_leaks(
        self, snapshots: list[ResourceUsageSnapshot]
    ) -> dict[str, Any]:
        """メモリリーク検出"""
        if len(snapshots) < 10:
            return {
                "leak_detected": False,
                "leak_size": 0,
                "leak_trend": "insufficient_data",
            }

        memory_values = [s.memory_mb for s in snapshots]

        # 線形トレンド分析（簡易版）
        time_points = list(range(len(memory_values)))

        # 最小二乗法による傾きの計算
        n = len(memory_values)
        sum_x = sum(time_points)
        sum_y = sum(memory_values)
        sum_xy = sum(x * y for x, y in zip(time_points, memory_values, strict=False))
        sum_x2 = sum(x * x for x in time_points)

        # 傾き計算
        slope = (
            (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
            if (n * sum_x2 - sum_x * sum_x) != 0
            else 0
        )

        # 推定リークサイズ（傾き × 時間）
        estimated_leak = (
            slope * len(snapshots) * ResourceMonitoringConfig.MONITORING_INTERVAL
        )

        leak_detected = (
            estimated_leak > ResourceMonitoringConfig.MEMORY_LEAK_THRESHOLD / 10
        )  # 閾値の1/10

        trend = (
            "increasing"
            if slope > 0.1
            else "stable"
            if abs(slope) <= 0.1
            else "decreasing"
        )

        return {
            "leak_detected": leak_detected,
            "leak_size": estimated_leak,
            "leak_trend": trend,
            "slope": slope,
        }

    def _analyze_cpu_spikes(
        self, snapshots: list[ResourceUsageSnapshot]
    ) -> dict[str, Any]:
        """CPUスパイク分析"""
        cpu_values = [s.cpu_percent for s in snapshots]
        spike_threshold = ResourceMonitoringConfig.CPU_SPIKE_THRESHOLD

        # スパイク検出
        spikes = []
        in_spike = False
        spike_start = 0

        for i, cpu in enumerate(cpu_values):
            if cpu > spike_threshold and not in_spike:
                in_spike = True
                spike_start = i
            elif cpu <= spike_threshold and in_spike:
                in_spike = False
                spike_duration = (
                    i - spike_start
                ) * ResourceMonitoringConfig.MONITORING_INTERVAL
                spikes.append(spike_duration)

        return {
            "spike_count": len(spikes),
            "max_cpu": max(cpu_values) if cpu_values else 0,
            "avg_spike_duration": statistics.mean(spikes) if spikes else 0,
            "total_spike_time": sum(spikes),
        }

    def _analyze_resource_correlations(
        self, snapshots: list[ResourceUsageSnapshot]
    ) -> list[dict[str, Any]]:
        """リソース相関分析"""
        if len(snapshots) < 10:
            return []

        # メトリクス抽出
        metrics = {
            "CPU": [s.cpu_percent for s in snapshots],
            "Memory": [s.memory_mb for s in snapshots],
            "Threads": [s.thread_count for s in snapshots],
        }

        correlations = []
        metric_names = list(metrics.keys())

        # 各メトリクス間の相関計算
        for i in range(len(metric_names)):
            for j in range(i + 1, len(metric_names)):
                metric1 = metric_names[i]
                metric2 = metric_names[j]

                correlation = self._calculate_correlation(
                    metrics[metric1], metrics[metric2]
                )

                correlations.append(
                    {"metric1": metric1, "metric2": metric2, "correlation": correlation}
                )

        return correlations

    def _calculate_correlation(self, x: list[float], y: list[float]) -> float:
        """相関係数計算"""
        if len(x) != len(y) or len(x) < 2:
            return 0.0

        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y, strict=False))
        sum_x2 = sum(xi * xi for xi in x)
        sum_y2 = sum(yi * yi for yi in y)

        numerator = n * sum_xy - sum_x * sum_y
        denominator = (
            (n * sum_x2 - sum_x * sum_x) * (n * sum_y2 - sum_y * sum_y)
        ) ** 0.5

        return numerator / denominator if denominator != 0 else 0.0

    def _report_resource_usage(self, result: ResourceTestResult):
        """リソース使用量レポート"""
        print(f"\n📊 {result.test_name} リソース使用量分析:")
        print(f"  実行時間: {result.duration:.2f}秒")
        print(f"  データポイント数: {len(result.snapshots)}")
        print(f"  ピークCPU使用率: {result.peak_cpu:.1f}%")
        print(f"  平均CPU使用率: {result.avg_cpu:.1f}%")
        print(f"  ピークメモリ使用量: {result.peak_memory_mb:.1f}MB")
        print(f"  平均メモリ使用量: {result.avg_memory_mb:.1f}MB")
        print(f"  メモリ増加量: {result.memory_growth:.1f}MB")
        print(f"  CPUスパイク数: {result.cpu_spikes}")
        print(
            f"  メモリリーク検出: {'はい' if result.memory_leaks_detected else 'いいえ'}"
        )

        if result.resource_warnings:
            print("  ⚠️ 警告:")
            for warning in result.resource_warnings:
                print(f"    - {warning}")

    async def _save_correlation_report(
        self, correlations: list[dict[str, Any]], snapshots: list[ResourceUsageSnapshot]
    ):
        """相関分析レポート保存"""
        timestamp = int(time.time())
        report_file = f"reports/resource_correlation_{timestamp}.json"

        Path(report_file).parent.mkdir(parents=True, exist_ok=True)

        report = {
            "timestamp": timestamp,
            "analysis_type": "resource_correlation",
            "correlations": correlations,
            "summary": {
                "snapshot_count": len(snapshots),
                "duration": snapshots[-1].timestamp - snapshots[0].timestamp
                if len(snapshots) > 1
                else 0,
                "strong_correlations": [
                    c for c in correlations if abs(c["correlation"]) > 0.7
                ],
            },
        }

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"📄 相関分析レポート保存: {report_file}")


# =============================================================================
# 学習ポイント・実装のポイント:
#
# 1. 総合リソース監視:
#    - CPU・メモリ・ネットワーク・スレッド数の統合監視
#    - 高頻度サンプリング（100ms間隔）による詳細分析
#    - リアルタイムリソース使用量トラッキング
#
# 2. メモリリーク検出:
#    - 線形トレンド分析による自動検出
#    - 長時間実行でのメモリ増加パターン分析
#    - 永続的メモリ増加の識別
#
# 3. CPUスパイク分析:
#    - 高CPU使用率期間の検出と分析
#    - スパイク持続時間の測定
#    - CPU負荷パターンの可視化
#
# 4. リソース相関分析:
#    - CPU・メモリ・ネットワーク間の相関係数計算
#    - ボトルネック特定のための関係性分析
#    - パフォーマンス最適化のためのインサイト
#
# 5. ワークロード別分析:
#    - 軽負荷・中負荷・高負荷での段階的評価
#    - 負荷レベルに応じた閾値設定
#    - スケーラビリティ評価
#
# 6. 実用的な監視手法:
#    - バックグラウンドスレッドによる非同期監視
#    - psutilによる正確なシステムメトリクス取得
#    - 警告・アラート機能の実装
#
# 7. レポート機能:
#    - JSON形式での詳細分析結果保存
#    - 時系列データの可視化対応
#    - CI/CD統合のための構造化データ
# =============================================================================
