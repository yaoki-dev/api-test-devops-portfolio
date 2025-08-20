"""
実務レベル負荷テストスイート
Performance-Testing-Agent専用実装

学習目標:
- 段階的負荷増加による限界点検出
- 詳細なパフォーマンスメトリクス収集
- リソース使用量の監視と分析
- 自動閾値判定とレポート生成
"""

import asyncio
import json
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil
import pytest

from utils.api_client import AsyncAPIClient
from utils.performance_monitor import PerformanceMonitor


@dataclass
class LoadTestResult:
    """負荷テスト結果"""

    user_count: int
    duration: float
    request_count: int
    success_count: int
    failure_count: int
    response_times: list[float]
    throughput: float
    cpu_usage: list[float]
    memory_usage: list[float]
    error_rate: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_count": self.user_count,
            "duration": self.duration,
            "request_count": self.request_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "error_rate": self.error_rate,
            "throughput": self.throughput,
            "response_time_stats": {
                "mean": statistics.mean(self.response_times)
                if self.response_times
                else 0,
                "median": statistics.median(self.response_times)
                if self.response_times
                else 0,
                "min": min(self.response_times) if self.response_times else 0,
                "max": max(self.response_times) if self.response_times else 0,
                "p95": statistics.quantiles(self.response_times, n=20)[18]
                if len(self.response_times) > 20
                else (max(self.response_times) if self.response_times else 0),
                "p99": statistics.quantiles(self.response_times, n=100)[98]
                if len(self.response_times) > 100
                else (max(self.response_times) if self.response_times else 0),
            },
            "resource_usage": {
                "cpu_mean": statistics.mean(self.cpu_usage) if self.cpu_usage else 0,
                "cpu_max": max(self.cpu_usage) if self.cpu_usage else 0,
                "memory_mean": statistics.mean(self.memory_usage)
                if self.memory_usage
                else 0,
                "memory_max": max(self.memory_usage) if self.memory_usage else 0,
            },
        }


class LoadTestExecutor:
    """負荷テスト実行エンジン"""

    def __init__(self):
        self.monitor = PerformanceMonitor(
            alert_threshold=5.0, memory_threshold_mb=1000.0, cpu_threshold_percent=90.0
        )
        self.results: list[LoadTestResult] = []

    async def execute_user_simulation(
        self, user_count: int, duration: float, endpoints: list[str]
    ) -> LoadTestResult:
        """ユーザーシミュレーション実行"""
        print(f"🔄 負荷テスト開始: {user_count}ユーザー, {duration}秒間")

        start_time = time.time()
        tasks = []
        response_times = []
        success_count = 0
        failure_count = 0
        cpu_usage = []
        memory_usage = []

        # システムリソース監視開始
        resource_monitor_task = asyncio.create_task(
            self._monitor_resources(duration, cpu_usage, memory_usage)
        )

        # ユーザーシミュレーション開始
        for user_id in range(user_count):
            task = asyncio.create_task(
                self._simulate_user(user_id, duration, endpoints, response_times)
            )
            tasks.append(task)

        # 全タスク完了待機
        user_results = await asyncio.gather(*tasks, return_exceptions=True)
        await resource_monitor_task

        # 結果集計
        for result in user_results:
            if isinstance(result, Exception):
                failure_count += 1
            else:
                success_count += result

        end_time = time.time()
        actual_duration = end_time - start_time
        total_requests = success_count + failure_count

        result = LoadTestResult(
            user_count=user_count,
            duration=actual_duration,
            request_count=total_requests,
            success_count=success_count,
            failure_count=failure_count,
            response_times=response_times,
            throughput=total_requests / actual_duration if actual_duration > 0 else 0,
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            error_rate=(failure_count / total_requests * 100)
            if total_requests > 0
            else 0,
        )

        self.results.append(result)
        print(
            f"✅ 負荷テスト完了: {user_count}ユーザー - 成功率: {(success_count / total_requests * 100):.1f}%"
            if total_requests > 0
            else "完了"
        )

        return result

    async def _simulate_user(
        self,
        user_id: int,
        duration: float,
        endpoints: list[str],
        response_times: list[float],
    ) -> int:
        """単一ユーザーシミュレーション"""
        request_count = 0
        end_time = time.time() + duration

        async with AsyncAPIClient() as client:
            while time.time() < end_time:
                try:
                    # ランダムエンドポイント選択
                    endpoint = endpoints[user_id % len(endpoints)]

                    start_request = time.time()
                    response = await client.get(endpoint)
                    end_request = time.time()

                    response_time = end_request - start_request
                    response_times.append(response_time)

                    if response.status_code == 200:
                        request_count += 1

                    # ユーザー行動のシミュレーション（思考時間）
                    await asyncio.sleep(0.1 + (user_id % 5) * 0.02)

                except Exception as e:
                    print(f"User {user_id} request failed: {e}")
                    break

        return request_count

    async def _monitor_resources(
        self, duration: float, cpu_usage: list[float], memory_usage: list[float]
    ):
        """システムリソース監視"""
        end_time = time.time() + duration

        while time.time() < end_time:
            cpu_usage.append(psutil.cpu_percent(interval=0.1))
            memory_usage.append(psutil.Process().memory_info().rss / 1024 / 1024)  # MB
            await asyncio.sleep(0.5)


@pytest.mark.performance
@pytest.mark.load_test
class TestLoadTesting:
    """実務レベル負荷テストクラス"""

    # 段階的負荷設定
    LOAD_STAGES = [10, 25, 50, 100, 200]  # ユーザー数
    TEST_DURATION = 30  # 各段階の実行時間（秒）

    # パフォーマンス閾値
    RESPONSE_TIME_THRESHOLD = 3.0  # 秒
    P95_THRESHOLD = 5.0  # 95パーセンタイル
    ERROR_RATE_THRESHOLD = 5.0  # %
    THROUGHPUT_MIN_THRESHOLD = 5.0  # req/sec

    # テスト対象エンドポイント
    TEST_ENDPOINTS = [
        "/posts/1",
        "/posts/2",
        "/posts/3",
        "/users/1",
        "/users/2",
        "/users/3",
        "/todos/1",
        "/todos/2",
        "/todos/3",
        "/comments/1",
        "/comments/2",
        "/comments/3",
    ]

    @pytest.mark.asyncio
    async def test_progressive_load_increase(self):
        """段階的負荷増加テスト"""
        executor = LoadTestExecutor()
        all_results = []

        print("🚀 段階的負荷増加テスト開始")

        for stage, user_count in enumerate(self.LOAD_STAGES):
            print(f"\n📊 Stage {stage + 1}: {user_count}ユーザー負荷テスト")

            result = await executor.execute_user_simulation(
                user_count=user_count,
                duration=self.TEST_DURATION,
                endpoints=self.TEST_ENDPOINTS,
            )

            all_results.append(result)

            # 段階別分析
            self._analyze_stage_result(stage + 1, result)

            # 段階間休憩
            if stage < len(self.LOAD_STAGES) - 1:
                print("⏸️ 次の段階まで休憩中...")
                await asyncio.sleep(5)

        # 全体結果分析
        self._analyze_progressive_results(all_results)

        # レポート生成
        await self._generate_load_test_report(all_results, "progressive_load")

        # 基本的な閾値チェック
        for i, result in enumerate(all_results):
            stage_name = f"Stage {i + 1} ({result.user_count} users)"

            # レスポンス時間チェック
            mean_response_time = (
                statistics.mean(result.response_times) if result.response_times else 0
            )
            assert mean_response_time < self.RESPONSE_TIME_THRESHOLD, (
                f"{stage_name}: 平均レスポンス時間が閾値超過 {mean_response_time:.3f}s > {self.RESPONSE_TIME_THRESHOLD}s"
            )

            # エラー率チェック
            assert result.error_rate < self.ERROR_RATE_THRESHOLD, (
                f"{stage_name}: エラー率が閾値超過 {result.error_rate:.1f}% > {self.ERROR_RATE_THRESHOLD}%"
            )

    @pytest.mark.asyncio
    async def test_sustained_load(self):
        """持続負荷テスト"""
        executor = LoadTestExecutor()

        # 中程度の負荷で長時間実行
        target_users = 50
        duration = 120  # 2分間

        print(f"🔄 持続負荷テスト: {target_users}ユーザー, {duration}秒間")

        result = await executor.execute_user_simulation(
            user_count=target_users, duration=duration, endpoints=self.TEST_ENDPOINTS
        )

        # 持続性能分析
        self._analyze_sustained_performance(result)

        # レポート生成
        await self._generate_load_test_report([result], "sustained_load")

        # 持続性能アサーション
        mean_response_time = (
            statistics.mean(result.response_times) if result.response_times else 0
        )
        assert mean_response_time < self.RESPONSE_TIME_THRESHOLD, (
            f"持続負荷時の平均レスポンス時間が閾値超過: {mean_response_time:.3f}s"
        )

        assert result.error_rate < self.ERROR_RATE_THRESHOLD, (
            f"持続負荷時のエラー率が閾値超過: {result.error_rate:.1f}%"
        )

        assert result.throughput > self.THROUGHPUT_MIN_THRESHOLD, (
            f"持続負荷時のスループットが閾値未満: {result.throughput:.1f} req/s"
        )

    @pytest.mark.asyncio
    async def test_peak_capacity_detection(self):
        """ピーク容量検出テスト"""
        executor = LoadTestExecutor()

        # より高い負荷段階でテスト
        peak_stages = [100, 200, 300, 500]
        peak_results = []

        print("🔍 ピーク容量検出テスト開始")

        for user_count in peak_stages:
            print(f"\n🚀 ピーク容量テスト: {user_count}ユーザー")

            result = await executor.execute_user_simulation(
                user_count=user_count,
                duration=20,  # 短縮時間
                endpoints=self.TEST_ENDPOINTS,
            )

            peak_results.append(result)

            # 容量限界の早期検出
            if result.error_rate > 20 or (
                result.response_times and statistics.mean(result.response_times) > 10
            ):
                print(f"⚠️ 容量限界検出: {user_count}ユーザーで性能劣化")
                break

            await asyncio.sleep(3)

        # ピーク容量分析
        self._analyze_peak_capacity(peak_results)

        # レポート生成
        await self._generate_load_test_report(peak_results, "peak_capacity")

        # 基本的な安定性チェック
        for result in peak_results:
            if result.user_count <= 200:  # 一定以下の負荷では安定を期待
                assert result.error_rate < 10, (
                    f"{result.user_count}ユーザー時のエラー率が高すぎます: {result.error_rate:.1f}%"
                )

    def _analyze_stage_result(self, stage: int, result: LoadTestResult):
        """段階別結果分析"""
        stats = result.response_times

        print(f"  📈 Stage {stage} 結果:")
        print(f"    - リクエスト数: {result.request_count}")
        print(
            f"    - 成功率: {(result.success_count / result.request_count * 100):.1f}%"
            if result.request_count > 0
            else "    - 成功率: N/A"
        )
        print(
            f"    - 平均レスポンス時間: {statistics.mean(stats):.3f}s"
            if stats
            else "    - 平均レスポンス時間: N/A"
        )
        print(
            f"    - 95パーセンタイル: {statistics.quantiles(stats, n=20)[18]:.3f}s"
            if len(stats) > 20
            else f"    - 最大レスポンス時間: {max(stats):.3f}s"
            if stats
            else "    - レスポンス時間: N/A"
        )
        print(f"    - スループット: {result.throughput:.1f} req/s")
        print(
            f"    - CPU使用率: {statistics.mean(result.cpu_usage):.1f}%"
            if result.cpu_usage
            else "    - CPU使用率: N/A"
        )
        print(
            f"    - メモリ使用量: {statistics.mean(result.memory_usage):.1f}MB"
            if result.memory_usage
            else "    - メモリ使用量: N/A"
        )

    def _analyze_progressive_results(self, results: list[LoadTestResult]):
        """段階的結果の総合分析"""
        print("\n📊 段階的負荷増加総合分析:")

        # スループット推移
        throughputs = [r.throughput for r in results]
        print(
            f"  📈 スループット推移: {' → '.join([f'{t:.1f}' for t in throughputs])} req/s"
        )

        # レスポンス時間推移
        response_times = [
            statistics.mean(r.response_times) if r.response_times else 0
            for r in results
        ]
        print(
            f"  ⏱️ 平均レスポンス時間推移: {' → '.join([f'{t:.3f}s' for t in response_times])}"
        )

        # エラー率推移
        error_rates = [r.error_rate for r in results]
        print(f"  ❌ エラー率推移: {' → '.join([f'{e:.1f}%' for e in error_rates])}")

        # 容量限界の推定
        max_stable_users = 0
        for result in results:
            if (
                result.error_rate < 5
                and result.response_times
                and statistics.mean(result.response_times) < 3
            ):
                max_stable_users = result.user_count

        print(f"  🎯 推定安定容量: {max_stable_users}ユーザー")

    def _analyze_sustained_performance(self, result: LoadTestResult):
        """持続性能分析"""
        print("\n📊 持続負荷分析:")
        print(f"  - 実行時間: {result.duration:.1f}秒")
        print(f"  - 総リクエスト数: {result.request_count}")
        print(f"  - 安定性評価: {'良好' if result.error_rate < 1 else '改善必要'}")

        if result.response_times:
            # 時系列でのパフォーマンス変化を簡易分析
            chunk_size = len(result.response_times) // 4
            if chunk_size > 0:
                chunks = [
                    result.response_times[i : i + chunk_size]
                    for i in range(0, len(result.response_times), chunk_size)
                ]
                chunk_means = [statistics.mean(chunk) for chunk in chunks if chunk]

                print(
                    f"  - 時系列レスポンス時間: {' → '.join([f'{m:.3f}s' for m in chunk_means])}"
                )

                # 性能劣化チェック
                if len(chunk_means) >= 2 and chunk_means[-1] > chunk_means[0] * 1.5:
                    print("  ⚠️ 持続実行中の性能劣化を検出")
                else:
                    print("  ✅ 持続実行中の性能安定")

    def _analyze_peak_capacity(self, results: list[LoadTestResult]):
        """ピーク容量分析"""
        print("\n📊 ピーク容量分析:")

        for result in results:
            status = (
                "🟢 安定"
                if result.error_rate < 5
                else "🟡 限界"
                if result.error_rate < 20
                else "🔴 不安定"
            )
            avg_response = (
                statistics.mean(result.response_times) if result.response_times else 0
            )
            print(
                f"  - {result.user_count}ユーザー: {status} (エラー率: {result.error_rate:.1f}%, 応答: {avg_response:.3f}s)"
            )

        # 推奨運用容量の算出
        stable_capacity = 0
        for result in results:
            if (
                result.error_rate < 5
                and result.response_times
                and statistics.mean(result.response_times) < 5
            ):
                stable_capacity = result.user_count

        recommended_capacity = int(stable_capacity * 0.7) if stable_capacity > 0 else 0
        print(f"  🎯 推奨運用容量: {recommended_capacity}ユーザー (安定容量の70%)")

    async def _generate_load_test_report(
        self, results: list[LoadTestResult], test_type: str
    ):
        """負荷テストレポート生成"""
        timestamp = int(time.time())
        report_file = f"reports/load_test_{test_type}_{timestamp}.json"

        # レポートディレクトリ作成
        Path(report_file).parent.mkdir(parents=True, exist_ok=True)

        report = {
            "test_type": test_type,
            "timestamp": timestamp,
            "test_config": {
                "stages": self.LOAD_STAGES
                if test_type == "progressive_load"
                else [results[0].user_count]
                if results
                else [],
                "duration_per_stage": self.TEST_DURATION,
                "endpoints": self.TEST_ENDPOINTS,
                "thresholds": {
                    "response_time": self.RESPONSE_TIME_THRESHOLD,
                    "p95": self.P95_THRESHOLD,
                    "error_rate": self.ERROR_RATE_THRESHOLD,
                    "throughput_min": self.THROUGHPUT_MIN_THRESHOLD,
                },
            },
            "results": [result.to_dict() for result in results],
            "summary": {
                "total_stages": len(results),
                "max_users_tested": max([r.user_count for r in results])
                if results
                else 0,
                "peak_throughput": max([r.throughput for r in results])
                if results
                else 0,
                "overall_success_rate": sum([r.success_count for r in results])
                / sum([r.request_count for r in results])
                * 100
                if results and sum([r.request_count for r in results]) > 0
                else 0,
            },
        }

        # ファイル出力
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"📄 負荷テストレポート生成: {report_file}")
        return report_file


# =============================================================================
# 学習ポイント:
#
# 1. 段階的負荷増加:
#    - 10 → 200ユーザーまでの段階的テスト
#    - 各段階での詳細メトリクス収集
#    - 容量限界の自動検出
#
# 2. 実務レベルの監視:
#    - CPU・メモリ使用量のリアルタイム監視
#    - レスポンス時間の統計分析
#    - エラー率とスループットの追跡
#
# 3. 持続性能テスト:
#    - 長時間負荷での安定性確認
#    - 性能劣化の早期検出
#    - 時系列での性能変化分析
#
# 4. 自動化とレポート:
#    - JSON形式での詳細レポート出力
#    - CI/CD統合可能な閾値チェック
#    - 運用容量の推奨値算出
#
# 5. 実践的なテストパターン:
#    - ユーザー行動シミュレーション
#    - 複数エンドポイントでの負荷分散
#    - 段階間休憩による現実的なテスト実行
# =============================================================================
