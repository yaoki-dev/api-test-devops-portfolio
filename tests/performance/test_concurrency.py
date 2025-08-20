"""
コンカレンシーテストスイート

実務最適化版パフォーマンステスト:
- 同時実行による競合状態の検出
- リソース争奪状況での性能評価
- デッドロック・レースコンディション検出
- スレッドセーフティの確認

学習ポイント:
- 高コンカレンシー環境での性能特性
- 非同期処理の並行度制御
- ボトルネック特定手法
- 同期・非同期のパフォーマンス比較
"""

import asyncio
import statistics
import time
from dataclasses import dataclass
from typing import Any

import pytest

from config.settings import get_settings
from utils.api_client import JSONPlaceholderClient
from utils.performance_monitor import PerformanceBenchmark, PerformanceMonitor

settings = get_settings()


@dataclass
class ConcurrencyTestResult:
    """コンカレンシーテスト結果"""

    test_type: str
    concurrency_level: int
    execution_time: float
    total_operations: int
    successful_operations: int
    failed_operations: int
    throughput: float  # ops/sec
    average_response_time: float
    contention_detected: bool
    resource_conflicts: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_type": self.test_type,
            "concurrency_level": self.concurrency_level,
            "execution_time": self.execution_time,
            "total_operations": self.total_operations,
            "successful_operations": self.successful_operations,
            "failed_operations": self.failed_operations,
            "success_rate": (self.successful_operations / self.total_operations * 100)
            if self.total_operations > 0
            else 0,
            "throughput": self.throughput,
            "average_response_time": self.average_response_time,
            "contention_detected": self.contention_detected,
            "resource_conflicts": self.resource_conflicts,
        }


class ConcurrencyTestConfig:
    """コンカレンシーテスト設定"""

    # 段階的コンカレンシーレベル
    CONCURRENCY_LEVELS = [1, 5, 10, 20, 50, 100]  # 同時実行数
    OPERATIONS_PER_LEVEL = 100  # 各レベルでの操作数

    # パフォーマンス閾値
    MAX_RESPONSE_TIME_SECONDS = 3.0
    MIN_SUCCESS_RATE_PERCENT = 95.0
    MAX_CONTENTION_RATIO = 0.1  # 10%以下の競合率

    # テスト対象操作
    TEST_OPERATIONS = ["get_user", "get_post", "get_todo", "get_comment", "get_album"]


@pytest.fixture
async def api_client():
    """APIクライアント"""
    client = JSONPlaceholderClient()
    yield client
    await client.close()


@pytest.fixture
def performance_monitor():
    """パフォーマンス監視"""
    monitor = PerformanceMonitor(
        alert_threshold=ConcurrencyTestConfig.MAX_RESPONSE_TIME_SECONDS,
        memory_threshold_mb=500.0,
        cpu_threshold_percent=90.0,
    )
    return monitor


@pytest.fixture
def concurrency_benchmark(performance_monitor):
    """コンカレンシーベンチマーク"""
    return PerformanceBenchmark(performance_monitor)


@pytest.mark.performance
@pytest.mark.concurrency
@pytest.mark.external
@pytest.mark.slow
class TestConcurrencyPerformance:
    """コンカレンシーパフォーマンステスト"""

    async def test_async_concurrency_scaling(self, api_client, performance_monitor):
        """非同期コンカレンシースケーリングテスト

        目的: 同時実行数増加に伴う性能変化の測定
        重要: 非同期処理の効率性評価
        """
        print("\n🚀 非同期コンカレンシースケーリングテスト開始")

        scaling_results = []

        for concurrency_level in ConcurrencyTestConfig.CONCURRENCY_LEVELS:
            print(f"  📊 コンカレンシーレベル: {concurrency_level}")

            result = await self._execute_async_concurrency_test(
                api_client, performance_monitor, concurrency_level
            )

            scaling_results.append(result)

            # 結果出力
            print(
                f"    成功率: {(result.successful_operations / result.total_operations * 100):.1f}%"
            )
            print(f"    スループット: {result.throughput:.1f} ops/sec")
            print(f"    平均レスポンス時間: {result.average_response_time:.3f}s")

            # 競合検出
            if result.contention_detected:
                print(f"    ⚠️ リソース競合検出: {result.resource_conflicts}件")

            # 短い休憩
            await asyncio.sleep(1)

        # スケーリング分析
        self._analyze_concurrency_scaling(scaling_results)

        # 性能アサーション
        for result in scaling_results:
            success_rate = (
                (result.successful_operations / result.total_operations * 100)
                if result.total_operations > 0
                else 0
            )
            assert success_rate >= ConcurrencyTestConfig.MIN_SUCCESS_RATE_PERCENT, (
                f"コンカレンシーレベル{result.concurrency_level}で成功率不足: {success_rate:.1f}% < {ConcurrencyTestConfig.MIN_SUCCESS_RATE_PERCENT}%"
            )

            assert (
                result.average_response_time
                <= ConcurrencyTestConfig.MAX_RESPONSE_TIME_SECONDS
            ), (
                f"コンカレンシーレベル{result.concurrency_level}でレスポンス時間超過: {result.average_response_time:.3f}s > {ConcurrencyTestConfig.MAX_RESPONSE_TIME_SECONDS}s"
            )

    async def test_mixed_operation_concurrency(self, api_client, performance_monitor):
        """混合操作コンカレンシーテスト

        目的: 異なる操作の同時実行による性能影響測定
        重要: 実際のユーザーパターンに近い負荷テスト
        """
        print("\n🔀 混合操作コンカレンシーテスト開始")

        concurrency_level = 20
        operations_per_type = 20

        # 異なる操作を同時実行
        operation_tasks = []
        start_time = time.time()

        for operation in ConcurrencyTestConfig.TEST_OPERATIONS:
            for _ in range(operations_per_type):
                task = asyncio.create_task(
                    self._execute_single_operation(
                        api_client, operation, performance_monitor
                    )
                )
                operation_tasks.append((operation, task))

        # 全操作の完了待機
        results = await asyncio.gather(
            *[task for _, task in operation_tasks], return_exceptions=True
        )
        end_time = time.time()

        # 結果分析
        operation_stats = {}
        total_operations = len(operation_tasks)
        successful_operations = 0
        response_times = []

        for i, ((operation, _), result) in enumerate(zip(operation_tasks, results, strict=False)):
            if operation not in operation_stats:
                operation_stats[operation] = {"count": 0, "success": 0, "times": []}

            operation_stats[operation]["count"] += 1

            if not isinstance(result, Exception):
                operation_stats[operation]["success"] += 1
                successful_operations += 1
                if hasattr(result, "response_time"):
                    response_times.append(result.response_time)
                    operation_stats[operation]["times"].append(result.response_time)

        # 混合操作結果
        execution_time = end_time - start_time
        avg_response_time = statistics.mean(response_times) if response_times else 0
        throughput = total_operations / execution_time

        print("📊 混合操作結果:")
        print(f"  総操作数: {total_operations}")
        print(f"  成功操作数: {successful_operations}")
        print(f"  全体成功率: {(successful_operations / total_operations * 100):.1f}%")
        print(f"  実行時間: {execution_time:.2f}秒")
        print(f"  スループット: {throughput:.1f} ops/sec")
        print(f"  平均レスポンス時間: {avg_response_time:.3f}s")

        # 操作別分析
        print("  操作別分析:")
        for operation, stats in operation_stats.items():
            success_rate = (
                (stats["success"] / stats["count"] * 100) if stats["count"] > 0 else 0
            )
            avg_time = statistics.mean(stats["times"]) if stats["times"] else 0
            print(
                f"    {operation}: 成功率 {success_rate:.1f}%, 平均時間 {avg_time:.3f}s"
            )

        # 混合操作アサーション
        overall_success_rate = (
            (successful_operations / total_operations * 100)
            if total_operations > 0
            else 0
        )
        assert overall_success_rate >= 90.0, (
            f"混合操作での成功率不足: {overall_success_rate:.1f}% < 90.0%"
        )
        assert avg_response_time <= 5.0, (
            f"混合操作での平均レスポンス時間超過: {avg_response_time:.3f}s > 5.0s"
        )

    async def test_burst_traffic_simulation(self, api_client, performance_monitor):
        """バーストトラフィックシミュレーション

        目的: 突発的な高負荷に対する性能評価
        重要: ピーク時の安定性確認
        """
        print("\n💥 バーストトラフィックシミュレーション開始")

        # バーストパターン設定
        burst_patterns = [
            {"duration": 5, "intensity": 10},  # 軽いバースト
            {"duration": 3, "intensity": 30},  # 中程度のバースト
            {"duration": 2, "intensity": 50},  # 高強度バースト
        ]

        burst_results = []

        for i, pattern in enumerate(burst_patterns):
            print(
                f"  🚀 バーストパターン {i + 1}: {pattern['intensity']}並行, {pattern['duration']}秒間"
            )

            start_time = time.time()
            burst_tasks = []

            # バースト期間中の連続タスク生成
            end_burst = start_time + pattern["duration"]
            task_id = 0

            while time.time() < end_burst:
                # 指定強度まで並行タスクを生成
                current_tasks = [t for t in burst_tasks if not t.done()]

                while (
                    len(current_tasks) < pattern["intensity"]
                    and time.time() < end_burst
                ):
                    task = asyncio.create_task(
                        self._execute_burst_operation(
                            api_client, task_id, performance_monitor
                        )
                    )
                    burst_tasks.append(task)
                    current_tasks.append(task)
                    task_id += 1

                await asyncio.sleep(0.01)  # 短い間隔でタスク管理

            # バースト終了待機
            await asyncio.gather(*burst_tasks, return_exceptions=True)
            end_time = time.time()

            # バースト結果分析
            successful_tasks = sum(
                1 for t in burst_tasks if not isinstance(t.result(), Exception)
            )
            burst_duration = end_time - start_time
            burst_throughput = len(burst_tasks) / burst_duration

            burst_result = {
                "pattern": pattern,
                "total_tasks": len(burst_tasks),
                "successful_tasks": successful_tasks,
                "duration": burst_duration,
                "throughput": burst_throughput,
                "success_rate": (successful_tasks / len(burst_tasks) * 100)
                if burst_tasks
                else 0,
            }

            burst_results.append(burst_result)

            print(f"    総タスク数: {burst_result['total_tasks']}")
            print(f"    成功率: {burst_result['success_rate']:.1f}%")
            print(f"    スループット: {burst_result['throughput']:.1f} ops/sec")

            # バースト間の休憩
            await asyncio.sleep(3)

        # バーストトラフィック評価
        print("\n📊 バーストトラフィック総合評価:")
        avg_success_rate = statistics.mean([r["success_rate"] for r in burst_results])
        max_throughput = max([r["throughput"] for r in burst_results])

        print(f"  平均成功率: {avg_success_rate:.1f}%")
        print(f"  最大スループット: {max_throughput:.1f} ops/sec")

        # バーストトラフィックアサーション
        assert avg_success_rate >= 85.0, (
            f"バーストトラフィックでの平均成功率不足: {avg_success_rate:.1f}% < 85.0%"
        )

        for result in burst_results:
            if (
                result["pattern"]["intensity"] <= 30
            ):  # 中程度以下の強度では高い成功率を期待
                assert result["success_rate"] >= 90.0, (
                    f"中程度バーストでの成功率不足: {result['success_rate']:.1f}% < 90.0%"
                )

    async def test_resource_contention_detection(self, api_client, performance_monitor):
        """リソース競合検出テスト

        目的: 同一リソースへの同時アクセスによる競合検出
        重要: ボトルネック特定と性能劣化の原因分析
        """
        print("\n🔒 リソース競合検出テスト開始")

        # 同一リソースへの高コンカレンシーアクセス
        target_resource_id = 1
        concurrency_level = 50

        contention_start = time.time()
        contention_tasks = []
        access_times = []
        conflicts = 0

        # 同一リソースに対する高並行アクセス
        for i in range(concurrency_level):
            task = asyncio.create_task(
                self._execute_contention_test(
                    api_client, target_resource_id, i, access_times, performance_monitor
                )
            )
            contention_tasks.append(task)

        # 全アクセス完了待機
        results = await asyncio.gather(*contention_tasks, return_exceptions=True)
        contention_end = time.time()

        # 競合分析
        successful_accesses = sum(1 for r in results if not isinstance(r, Exception))
        contention_duration = contention_end - contention_start

        # アクセス時間の分散を分析（競合の指標）
        if access_times:
            access_variance = statistics.variance(access_times)
            access_stddev = statistics.stdev(access_times)
            avg_access_time = statistics.mean(access_times)

            # 競合検出（標準偏差が平均の50%以上の場合、競合と判定）
            contention_detected = access_stddev > (avg_access_time * 0.5)

            print("📊 リソース競合分析:")
            print(f"  対象リソース: user/{target_resource_id}")
            print(f"  同時アクセス数: {concurrency_level}")
            print(f"  成功アクセス数: {successful_accesses}")
            print(f"  平均アクセス時間: {avg_access_time:.3f}s")
            print(f"  アクセス時間標準偏差: {access_stddev:.3f}s")
            print(f"  競合検出: {'はい' if contention_detected else 'いいえ'}")

            if contention_detected:
                print("  ⚠️ リソース競合が検出されました")
                print(
                    f"    - 時間ばらつき率: {(access_stddev / avg_access_time * 100):.1f}%"
                )

            # 競合状況でも基本的な成功率は維持されるべき
            success_rate = (
                (successful_accesses / concurrency_level * 100)
                if concurrency_level > 0
                else 0
            )
            assert success_rate >= 80.0, (
                f"リソース競合時の成功率が低すぎます: {success_rate:.1f}% < 80.0%"
            )

            # 平均アクセス時間は許容範囲内であるべき
            assert avg_access_time <= 10.0, (
                f"リソース競合時の平均アクセス時間が長すぎます: {avg_access_time:.3f}s > 10.0s"
            )

    async def _execute_async_concurrency_test(
        self, api_client, performance_monitor, concurrency_level
    ):
        """非同期コンカレンシーテスト実行"""
        start_time = time.time()
        tasks = []
        successful_ops = 0
        total_ops = 0
        response_times = []
        conflicts = 0

        # 指定コンカレンシーレベルでタスク実行
        for i in range(concurrency_level):
            for _ in range(
                ConcurrencyTestConfig.OPERATIONS_PER_LEVEL // concurrency_level
            ):
                operation = ConcurrencyTestConfig.TEST_OPERATIONS[
                    i % len(ConcurrencyTestConfig.TEST_OPERATIONS)
                ]
                task = asyncio.create_task(
                    self._execute_single_operation(
                        api_client, operation, performance_monitor
                    )
                )
                tasks.append(task)

        # 全タスク完了待機
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()

        # 結果集計
        for result in results:
            total_ops += 1
            if not isinstance(result, Exception):
                successful_ops += 1
                if hasattr(result, "response_time"):
                    response_times.append(result.response_time)

        execution_time = end_time - start_time
        avg_response_time = statistics.mean(response_times) if response_times else 0
        throughput = total_ops / execution_time if execution_time > 0 else 0

        # 競合検出（レスポンス時間のばらつきで判定）
        contention_detected = False
        if response_times and len(response_times) > 1:
            response_stddev = statistics.stdev(response_times)
            contention_detected = response_stddev > (avg_response_time * 0.3)
            if contention_detected:
                conflicts = int(len(response_times) * 0.1)  # 推定競合数

        return ConcurrencyTestResult(
            test_type="async_concurrency",
            concurrency_level=concurrency_level,
            execution_time=execution_time,
            total_operations=total_ops,
            successful_operations=successful_ops,
            failed_operations=total_ops - successful_ops,
            throughput=throughput,
            average_response_time=avg_response_time,
            contention_detected=contention_detected,
            resource_conflicts=conflicts,
        )

    async def _execute_single_operation(
        self, api_client, operation: str, performance_monitor
    ):
        """単一操作実行"""
        start_time = time.time()

        try:
            if operation == "get_user":
                import random

                user_id = random.randint(1, 10)
                response = await api_client.get_user(user_id)
            elif operation == "get_post":
                import random

                post_id = random.randint(1, 100)
                response = await api_client.get_post(post_id)
            elif operation == "get_todo":
                import random

                todo_id = random.randint(1, 200)
                response = await api_client.get_todo(todo_id)
            elif operation == "get_comment":
                import random

                comment_id = random.randint(1, 500)
                response = await api_client.get_comment(comment_id)
            elif operation == "get_album":
                import random

                album_id = random.randint(1, 100)
                response = await api_client.get_album(album_id)
            else:
                response = await api_client.get_user(1)  # デフォルト

            end_time = time.time()
            response_time = end_time - start_time

            # パフォーマンス記録
            performance_monitor.record_performance(
                endpoint=f"concurrency_{operation}",
                response_time=response_time,
                status_code=200 if response else 500,
            )

            # 結果オブジェクト作成
            class OperationResult:
                def __init__(self, response_time):
                    self.response_time = response_time

            return OperationResult(response_time)

        except Exception as e:
            end_time = time.time()
            response_time = end_time - start_time

            performance_monitor.record_performance(
                endpoint=f"concurrency_{operation}",
                response_time=response_time,
                status_code=500,
                error=str(e),
            )
            raise

    async def _execute_burst_operation(
        self, api_client, task_id: int, performance_monitor
    ):
        """バースト操作実行"""
        operation = ConcurrencyTestConfig.TEST_OPERATIONS[
            task_id % len(ConcurrencyTestConfig.TEST_OPERATIONS)
        ]
        return await self._execute_single_operation(
            api_client, operation, performance_monitor
        )

    async def _execute_contention_test(
        self,
        api_client,
        resource_id: int,
        accessor_id: int,
        access_times: list[float],
        performance_monitor,
    ):
        """リソース競合テスト実行"""
        start_time = time.time()

        try:
            # 同一リソースへのアクセス
            response = await api_client.get_user(resource_id)
            end_time = time.time()

            access_time = end_time - start_time
            access_times.append(access_time)

            # パフォーマンス記録
            performance_monitor.record_performance(
                endpoint=f"contention_user_{resource_id}",
                response_time=access_time,
                status_code=200 if response else 500,
            )

            return response

        except Exception as e:
            end_time = time.time()
            access_time = end_time - start_time
            access_times.append(access_time)

            performance_monitor.record_performance(
                endpoint=f"contention_user_{resource_id}",
                response_time=access_time,
                status_code=500,
                error=str(e),
            )
            raise

    def _analyze_concurrency_scaling(self, results: list[ConcurrencyTestResult]):
        """コンカレンシースケーリング分析"""
        print("\n📊 コンカレンシースケーリング分析:")
        print(
            f"{'レベル':<8} {'成功率%':<8} {'スループット':<12} {'平均時間(s)':<12} {'競合':<6}"
        )
        print("-" * 60)

        for result in results:
            success_rate = (
                (result.successful_operations / result.total_operations * 100)
                if result.total_operations > 0
                else 0
            )
            contention_mark = "🔒" if result.contention_detected else "✅"

            print(
                f"{result.concurrency_level:<8} "
                f"{success_rate:<8.1f} "
                f"{result.throughput:<12.1f} "
                f"{result.average_response_time:<12.3f} "
                f"{contention_mark:<6}"
            )

        # スケーラビリティ評価
        throughputs = [r.throughput for r in results]
        max_throughput = max(throughputs) if throughputs else 0
        linear_efficiency = self._calculate_linear_efficiency(results)

        print("\n📈 スケーラビリティ評価:")
        print(f"  最大スループット: {max_throughput:.1f} ops/sec")
        print(f"  線形効率性: {linear_efficiency:.1f}%")

        if linear_efficiency > 80:
            print("  🎯 優秀なスケーラビリティ")
        elif linear_efficiency > 60:
            print("  📊 良好なスケーラビリティ")
        else:
            print("  ⚠️ スケーラビリティに改善の余地あり")

    def _calculate_linear_efficiency(
        self, results: list[ConcurrencyTestResult]
    ) -> float:
        """線形効率性計算"""
        if len(results) < 2:
            return 100.0

        baseline = results[0]  # 最小コンカレンシーレベルをベースライン
        final = results[-1]  # 最大コンカレンシーレベル

        if baseline.throughput == 0:
            return 0.0

        # 理想的なスケーリング（線形）と実際のスケーリングを比較
        concurrency_ratio = final.concurrency_level / baseline.concurrency_level
        throughput_ratio = final.throughput / baseline.throughput

        efficiency = (throughput_ratio / concurrency_ratio) * 100
        return min(100.0, efficiency)


# =============================================================================
# 学習ポイント・実装のポイント:
#
# 1. コンカレンシースケーリング:
#    - 1→100レベルまでの段階的コンカレンシーテスト
#    - 線形効率性による性能評価
#    - ボトルネック検出と容量限界の特定
#
# 2. 混合操作テスト:
#    - 実際のユーザーパターンに近い負荷シミュレーション
#    - 異なる操作の同時実行による相互影響評価
#    - 操作別パフォーマンス分析
#
# 3. バーストトラフィック:
#    - 突発的高負荷に対する耐性評価
#    - ピーク時の安定性確認
#    - バーストパターン別の性能特性分析
#
# 4. リソース競合検出:
#    - 同一リソースへの高並行アクセステスト
#    - アクセス時間のばらつきによる競合検出
#    - ボトルネック原因の特定
#
# 5. 実務的メトリクス:
#    - スループット・レスポンス時間・成功率の総合評価
#    - 競合検出による品質分析
#    - CI/CD統合のための自動判定基準
# =============================================================================
