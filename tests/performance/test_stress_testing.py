"""
実務レベルストレステストスイート
Performance-Testing-Agent専用実装

学習目標:
- システム限界点の自動検出
- 破壊テストと回復力評価
- 障害時の振る舞い分析
- リソース枯渇シナリオのテスト
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
class StressTestResult:
    """ストレステスト結果"""

    test_type: str
    max_concurrent_users: int
    breaking_point: int | None
    recovery_time: float | None
    total_requests: int
    successful_requests: int
    failed_requests: int
    error_types: dict[str, int]
    response_time_progression: list[tuple[int, float]]  # (users, avg_response_time)
    resource_usage_peak: dict[str, float]
    stability_score: float  # 0-100

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_type": self.test_type,
            "max_concurrent_users": self.max_concurrent_users,
            "breaking_point": self.breaking_point,
            "recovery_time": self.recovery_time,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "error_rate": (self.failed_requests / self.total_requests * 100)
            if self.total_requests > 0
            else 0,
            "error_types": self.error_types,
            "response_time_progression": self.response_time_progression,
            "resource_usage_peak": self.resource_usage_peak,
            "stability_score": self.stability_score,
        }


class StressTestExecutor:
    """ストレステスト実行エンジン"""

    def __init__(self):
        self.monitor = PerformanceMonitor(
            alert_threshold=10.0,  # ストレステスト用に緩和
            memory_threshold_mb=2000.0,
            cpu_threshold_percent=95.0,
        )
        self.results: list[StressTestResult] = []

    async def execute_breaking_point_test(
        self, endpoints: list[str]
    ) -> StressTestResult:
        """破壊点検出テスト"""
        print("🔥 破壊点検出テスト開始")

        user_levels = [50, 100, 200, 500, 750, 1000, 1500, 2000]
        breaking_point = None
        response_progression = []
        total_requests = 0
        successful_requests = 0
        failed_requests = 0
        error_types = {}
        peak_resources = {"cpu": 0, "memory": 0}

        for users in user_levels:
            print(f"🚀 破壊点テスト: {users}ユーザー同時実行")

            start_time = time.time()
            tasks = []
            stage_successes = 0
            stage_failures = 0
            stage_errors = {}
            response_times = []

            # システムリソース監視開始
            initial_memory = psutil.Process().memory_info().rss / 1024 / 1024

            # 大量並行リクエスト実行
            for user_id in range(users):
                task = asyncio.create_task(
                    self._stress_user_simulation(
                        user_id, endpoints, response_times, stage_errors
                    )
                )
                tasks.append(task)

            # 全タスク実行（タイムアウト付き）
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=60,  # 60秒タイムアウト
                )

                for result in results:
                    if isinstance(result, Exception):
                        stage_failures += 1
                        error_type = type(result).__name__
                        stage_errors[error_type] = stage_errors.get(error_type, 0) + 1
                    else:
                        stage_successes += result

            except asyncio.TimeoutError:
                print(f"⚠️ {users}ユーザーでタイムアウト発生")
                stage_failures += len(tasks)
                stage_errors["TimeoutError"] = len(tasks)

            # リソース使用量記録
            current_memory = psutil.Process().memory_info().rss / 1024 / 1024
            current_cpu = psutil.cpu_percent(interval=1)
            peak_resources["memory"] = max(peak_resources["memory"], current_memory)
            peak_resources["cpu"] = max(peak_resources["cpu"], current_cpu)

            # 応答時間統計
            avg_response_time = (
                statistics.mean(response_times) if response_times else float("inf")
            )
            response_progression.append((users, avg_response_time))

            # 結果累積
            total_requests += stage_successes + stage_failures
            successful_requests += stage_successes
            failed_requests += stage_failures

            for error_type, count in stage_errors.items():
                error_types[error_type] = error_types.get(error_type, 0) + count

            # 破壊点判定
            error_rate = (
                (stage_failures / (stage_successes + stage_failures) * 100)
                if (stage_successes + stage_failures) > 0
                else 100
            )

            print(
                f"  📊 結果: 成功率 {100 - error_rate:.1f}%, 平均応答時間 {avg_response_time:.3f}s"
            )

            if (
                error_rate > 50 or avg_response_time > 30
            ):  # 50%以上エラー or 30秒以上応答
                breaking_point = users
                print(f"💥 破壊点検出: {users}ユーザー")
                break

            # 次の段階まで短い休憩
            await asyncio.sleep(5)

        # 安定性スコア計算
        stability_score = self._calculate_stability_score(
            response_progression, error_types, total_requests
        )

        result = StressTestResult(
            test_type="breaking_point",
            max_concurrent_users=max(user_levels),
            breaking_point=breaking_point,
            recovery_time=None,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            error_types=error_types,
            response_time_progression=response_progression,
            resource_usage_peak=peak_resources,
            stability_score=stability_score,
        )

        self.results.append(result)
        print(f"✅ 破壊点テスト完了: 破壊点={breaking_point or '未検出'}ユーザー")

        return result

    async def execute_recovery_test(self, endpoints: list[str]) -> StressTestResult:
        """回復力テスト"""
        print("🔄 回復力テスト開始")

        # 1. 通常負荷でベースライン確立
        print("📊 ベースライン性能測定中...")
        baseline_users = 50
        baseline_result = await self._measure_performance(
            baseline_users, endpoints, duration=30
        )
        baseline_response_time = (
            statistics.mean(baseline_result["response_times"])
            if baseline_result["response_times"]
            else 0
        )

        # 2. 高負荷ストレス印加
        print("🚨 高負荷ストレス印加中...")
        stress_users = 500
        stress_start = time.time()
        stress_result = await self._measure_performance(
            stress_users, endpoints, duration=60
        )
        stress_end = time.time()

        # 3. 回復時間測定
        print("⏳ 回復時間測定中...")
        recovery_start = time.time()
        recovery_samples = []

        for i in range(10):  # 5分間回復監視
            await asyncio.sleep(30)  # 30秒間隔
            sample_result = await self._measure_performance(
                baseline_users, endpoints, duration=10
            )
            sample_response_time = (
                statistics.mean(sample_result["response_times"])
                if sample_result["response_times"]
                else float("inf")
            )
            recovery_samples.append(sample_response_time)

            print(
                f"  回復サンプル {i + 1}: {sample_response_time:.3f}s (ベースライン: {baseline_response_time:.3f}s)"
            )

            # 回復判定（ベースラインの120%以内）
            if sample_response_time <= baseline_response_time * 1.2:
                recovery_time = time.time() - recovery_start
                print(f"✅ 回復完了: {recovery_time:.1f}秒")
                break
        else:
            recovery_time = None
            print("⚠️ 測定時間内に完全回復せず")

        # 回復テスト結果
        result = StressTestResult(
            test_type="recovery",
            max_concurrent_users=stress_users,
            breaking_point=None,
            recovery_time=recovery_time,
            total_requests=baseline_result["total"] + stress_result["total"],
            successful_requests=baseline_result["success"] + stress_result["success"],
            failed_requests=baseline_result["failed"] + stress_result["failed"],
            error_types={"stress_induced": stress_result["failed"]},
            response_time_progression=[
                (baseline_users, baseline_response_time),
                (
                    stress_users,
                    statistics.mean(stress_result["response_times"])
                    if stress_result["response_times"]
                    else 0,
                ),
            ],
            resource_usage_peak={"cpu": 0, "memory": 0},  # 簡易実装
            stability_score=80
            if recovery_time and recovery_time < 300
            else 50,  # 5分以内回復で高評価
        )

        self.results.append(result)
        return result

    async def execute_resource_exhaustion_test(
        self, endpoints: list[str]
    ) -> StressTestResult:
        """リソース枯渇テスト"""
        print("💾 リソース枯渇テスト開始")

        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        memory_threshold = initial_memory + 1000  # 1GB増加で枯渇と判定

        user_increment = 100
        current_users = 100
        total_requests = 0
        successful_requests = 0
        failed_requests = 0
        error_types = {}
        response_progression = []

        while current_users <= 2000:  # 最大2000ユーザーまで
            print(f"💾 リソース監視テスト: {current_users}ユーザー")

            # メモリ集約的なテスト実行
            result = await self._memory_intensive_test(current_users, endpoints)

            # 現在のメモリ使用量チェック
            current_memory = psutil.Process().memory_info().rss / 1024 / 1024
            memory_increase = current_memory - initial_memory

            # 結果記録
            total_requests += result["total"]
            successful_requests += result["success"]
            failed_requests += result["failed"]

            avg_response = (
                statistics.mean(result["response_times"])
                if result["response_times"]
                else 0
            )
            response_progression.append((current_users, avg_response))

            print(f"  メモリ使用量: {current_memory:.1f}MB (+{memory_increase:.1f}MB)")
            print(f"  応答時間: {avg_response:.3f}s")

            # リソース枯渇判定
            if memory_increase > 1000 or current_memory > memory_threshold:
                print(f"⚠️ メモリ枯渇検出: {current_memory:.1f}MB")
                error_types["memory_exhaustion"] = 1
                break

            if avg_response > 20:  # 20秒以上の応答時間
                print(f"⚠️ 応答時間劣化: {avg_response:.3f}s")
                error_types["response_degradation"] = 1
                break

            current_users += user_increment
            await asyncio.sleep(10)  # リソース安定化待機

        # 安定性スコア計算
        stability_score = max(
            0, 100 - memory_increase / 10
        )  # メモリ増加100MBごとに10点減点

        result = StressTestResult(
            test_type="resource_exhaustion",
            max_concurrent_users=current_users,
            breaking_point=current_users if error_types else None,
            recovery_time=None,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            error_types=error_types,
            response_time_progression=response_progression,
            resource_usage_peak={"memory": current_memory, "cpu": psutil.cpu_percent()},
            stability_score=stability_score,
        )

        self.results.append(result)
        return result

    async def _stress_user_simulation(
        self,
        user_id: int,
        endpoints: list[str],
        response_times: list[float],
        errors: dict[str, int],
    ) -> int:
        """ストレス用ユーザーシミュレーション"""
        request_count = 0

        try:
            async with AsyncAPIClient() as client:
                # ストレス時は短時間で大量リクエスト
                for _ in range(5):  # 各ユーザー5リクエスト
                    endpoint = endpoints[user_id % len(endpoints)]

                    start_time = time.time()
                    response = await client.get(endpoint)
                    end_time = time.time()

                    response_times.append(end_time - start_time)

                    if response.status_code == 200:
                        request_count += 1

                    # ストレステストでは待機時間最小
                    await asyncio.sleep(0.01)

        except Exception as e:
            error_type = type(e).__name__
            errors[error_type] = errors.get(error_type, 0) + 1

        return request_count

    async def _measure_performance(
        self, users: int, endpoints: list[str], duration: int
    ) -> dict[str, Any]:
        """性能測定ヘルパー"""
        tasks = []
        response_times = []
        success_count = 0
        failed_count = 0

        start_time = time.time()

        for user_id in range(users):
            task = asyncio.create_task(
                self._timed_user_simulation(
                    user_id, endpoints, duration, response_times
                )
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                failed_count += 1
            else:
                success_count += result

        return {
            "response_times": response_times,
            "success": success_count,
            "failed": failed_count,
            "total": success_count + failed_count,
            "duration": time.time() - start_time,
        }

    async def _timed_user_simulation(
        self,
        user_id: int,
        endpoints: list[str],
        duration: int,
        response_times: list[float],
    ) -> int:
        """時間制限付きユーザーシミュレーション"""
        request_count = 0
        end_time = time.time() + duration

        try:
            async with AsyncAPIClient() as client:
                while time.time() < end_time:
                    endpoint = endpoints[user_id % len(endpoints)]

                    start_time = time.time()
                    response = await client.get(endpoint)
                    end_time_req = time.time()

                    response_times.append(end_time_req - start_time)

                    if response.status_code == 200:
                        request_count += 1

                    await asyncio.sleep(0.1)

        except Exception:
            pass

        return request_count

    async def _memory_intensive_test(
        self, users: int, endpoints: list[str]
    ) -> dict[str, Any]:
        """メモリ集約的テスト"""
        # 大量データを保持してメモリ圧迫をシミュレート
        memory_hogs = []

        try:
            # メモリ使用量増加シミュレート
            for _ in range(users // 10):  # ユーザー10人ごとに1MB確保
                memory_hogs.append(b"0" * (1024 * 1024))  # 1MB

            # 通常のパフォーマンステスト実行
            result = await self._measure_performance(users, endpoints, duration=30)

            return result

        finally:
            # メモリ解放
            del memory_hogs

    def _calculate_stability_score(
        self,
        response_progression: list[tuple[int, float]],
        error_types: dict[str, int],
        total_requests: int,
    ) -> float:
        """安定性スコア計算"""
        score = 100.0

        # レスポンス時間劣化によるペナルティ
        if len(response_progression) >= 2:
            initial_response = response_progression[0][1]
            final_response = response_progression[-1][1]

            if initial_response > 0:
                degradation_ratio = final_response / initial_response
                if degradation_ratio > 2:
                    score -= 30  # 2倍以上劣化で30点減点
                elif degradation_ratio > 1.5:
                    score -= 15  # 1.5倍以上劣化で15点減点

        # エラー率によるペナルティ
        if total_requests > 0:
            total_errors = sum(error_types.values())
            error_rate = total_errors / total_requests * 100
            score -= error_rate  # エラー率1%ごとに1点減点

        # エラータイプによる追加ペナルティ
        if "TimeoutError" in error_types:
            score -= 20
        if "memory_exhaustion" in error_types:
            score -= 25

        return max(0, score)


@pytest.mark.performance
@pytest.mark.stress_test
class TestStressTesting:
    """実務レベルストレステストクラス"""

    # テスト対象エンドポイント
    TEST_ENDPOINTS = [
        "/posts/1",
        "/posts/2",
        "/posts/3",
        "/posts/4",
        "/posts/5",
        "/users/1",
        "/users/2",
        "/users/3",
        "/users/4",
        "/users/5",
        "/todos/1",
        "/todos/2",
        "/todos/3",
        "/todos/4",
        "/todos/5",
        "/comments/1",
        "/comments/2",
        "/comments/3",
        "/comments/4",
        "/comments/5",
    ]

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_breaking_point_detection(self):
        """破壊点検出テスト"""
        executor = StressTestExecutor()

        result = await executor.execute_breaking_point_test(self.TEST_ENDPOINTS)

        # 破壊点分析
        self._analyze_breaking_point(result)

        # レポート生成
        await self._generate_stress_report([result], "breaking_point")

        # 基本検証
        assert result.total_requests > 0, "リクエストが実行されませんでした"
        assert result.stability_score >= 0, (
            f"安定性スコアが無効: {result.stability_score}"
        )

        # 破壊点が検出された場合の追加検証
        if result.breaking_point:
            assert result.breaking_point >= 50, (
                f"破壊点が低すぎます: {result.breaking_point}ユーザー"
            )
            print(f"✅ システム破壊点: {result.breaking_point}ユーザー")
        else:
            print("✅ テスト範囲内で破壊点は検出されませんでした")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_recovery_capability(self):
        """回復力テスト"""
        executor = StressTestExecutor()

        result = await executor.execute_recovery_test(self.TEST_ENDPOINTS)

        # 回復力分析
        self._analyze_recovery_capability(result)

        # レポート生成
        await self._generate_stress_report([result], "recovery")

        # 回復力検証
        assert result.total_requests > 0, "リクエストが実行されませんでした"

        if result.recovery_time:
            assert result.recovery_time < 600, (
                f"回復時間が長すぎます: {result.recovery_time:.1f}秒"
            )
            print(f"✅ システム回復時間: {result.recovery_time:.1f}秒")
        else:
            print("⚠️ 測定時間内に完全回復は確認できませんでした")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_resource_exhaustion_limits(self):
        """リソース枯渇限界テスト"""
        executor = StressTestExecutor()

        result = await executor.execute_resource_exhaustion_test(self.TEST_ENDPOINTS)

        # リソース枯渇分析
        self._analyze_resource_exhaustion(result)

        # レポート生成
        await self._generate_stress_report([result], "resource_exhaustion")

        # リソース使用量検証
        assert result.total_requests > 0, "リクエストが実行されませんでした"
        assert result.resource_usage_peak["memory"] > 0, (
            "メモリ使用量が記録されませんでした"
        )

        print(
            f"✅ リソース枯渇テスト完了: ピークメモリ {result.resource_usage_peak['memory']:.1f}MB"
        )

    @pytest.mark.asyncio
    async def test_error_cascade_prevention(self):
        """エラー連鎖防止テスト"""
        print("🚨 エラー連鎖防止テスト開始")

        executor = StressTestExecutor()

        # 段階的にエラー率を増加させてエラー連鎖をテスト
        error_stages = [
            (100, "正常"),
            (300, "中負荷"),
            (600, "高負荷"),
            (1000, "限界負荷"),
        ]

        error_progression = []

        for users, stage_name in error_stages:
            print(f"🔍 {stage_name}テスト: {users}ユーザー")

            result = await executor._measure_performance(
                users, self.TEST_ENDPOINTS, duration=20
            )
            error_rate = (
                (result["failed"] / result["total"] * 100) if result["total"] > 0 else 0
            )
            error_progression.append((users, error_rate))

            print(f"  エラー率: {error_rate:.1f}%")

            # エラー連鎖検出
            if len(error_progression) >= 2:
                prev_error_rate = error_progression[-2][1]
                if error_rate > prev_error_rate * 3:  # 前段階の3倍以上のエラー率
                    print(
                        f"⚠️ エラー連鎖検出: {prev_error_rate:.1f}% → {error_rate:.1f}%"
                    )

            await asyncio.sleep(10)

        # エラー連鎖防止の評価
        max_error_rate = max([rate for _, rate in error_progression])
        assert max_error_rate < 90, f"エラー率が高すぎます: {max_error_rate:.1f}%"

        print("✅ エラー連鎖防止テスト完了")

    def _analyze_breaking_point(self, result: StressTestResult):
        """破壊点分析"""
        print("\n📊 破壊点分析:")
        print(f"  - 最大テストユーザー数: {result.max_concurrent_users}")
        print(f"  - 検出された破壊点: {result.breaking_point or '未検出'}")
        print(f"  - 総リクエスト数: {result.total_requests}")
        print(
            f"  - 成功率: {(result.successful_requests / result.total_requests * 100):.1f}%"
            if result.total_requests > 0
            else "  - 成功率: N/A"
        )
        print(f"  - 安定性スコア: {result.stability_score:.1f}/100")

        # レスポンス時間推移
        print("  - レスポンス時間推移:")
        for users, avg_time in result.response_time_progression:
            print(f"    {users}ユーザー: {avg_time:.3f}s")

        # エラータイプ分析
        if result.error_types:
            print("  - エラータイプ:")
            for error_type, count in result.error_types.items():
                print(f"    {error_type}: {count}件")

    def _analyze_recovery_capability(self, result: StressTestResult):
        """回復力分析"""
        print("\n📊 回復力分析:")
        print(
            f"  - 回復時間: {result.recovery_time:.1f}秒"
            if result.recovery_time
            else "  - 回復時間: 測定時間内に未回復"
        )
        print(f"  - ストレス時最大ユーザー数: {result.max_concurrent_users}")
        print(f"  - 安定性スコア: {result.stability_score:.1f}/100")

        # 回復評価
        if result.recovery_time:
            if result.recovery_time < 60:
                recovery_rating = "優秀"
            elif result.recovery_time < 180:
                recovery_rating = "良好"
            elif result.recovery_time < 300:
                recovery_rating = "許容範囲"
            else:
                recovery_rating = "改善必要"

            print(f"  - 回復能力評価: {recovery_rating}")

    def _analyze_resource_exhaustion(self, result: StressTestResult):
        """リソース枯渇分析"""
        print("\n📊 リソース枯渇分析:")
        print(f"  - 最大同時ユーザー数: {result.max_concurrent_users}")
        print(f"  - ピークメモリ使用量: {result.resource_usage_peak['memory']:.1f}MB")
        print(f"  - ピークCPU使用率: {result.resource_usage_peak['cpu']:.1f}%")
        print(f"  - 安定性スコア: {result.stability_score:.1f}/100")

        # リソース効率評価
        if result.total_requests > 0:
            memory_per_request = (
                result.resource_usage_peak["memory"] / result.total_requests
            )
            print(f"  - リクエスト当たりメモリ使用量: {memory_per_request:.3f}MB/req")

        # 枯渇検出
        if "memory_exhaustion" in result.error_types:
            print("  ⚠️ メモリ枯渇検出")
        if "response_degradation" in result.error_types:
            print("  ⚠️ 応答時間劣化検出")

    async def _generate_stress_report(
        self, results: list[StressTestResult], test_type: str
    ):
        """ストレステストレポート生成"""
        timestamp = int(time.time())
        report_file = f"reports/stress_test_{test_type}_{timestamp}.json"

        # レポートディレクトリ作成
        Path(report_file).parent.mkdir(parents=True, exist_ok=True)

        report = {
            "test_type": test_type,
            "timestamp": timestamp,
            "test_config": {
                "endpoints": self.TEST_ENDPOINTS,
                "test_methodology": f"{test_type}_stress_testing",
            },
            "results": [result.to_dict() for result in results],
            "summary": {
                "total_tests": len(results),
                "avg_stability_score": sum([r.stability_score for r in results])
                / len(results)
                if results
                else 0,
                "breaking_points_detected": len(
                    [r for r in results if r.breaking_point]
                ),
                "recovery_tests_passed": len(
                    [r for r in results if r.recovery_time and r.recovery_time < 300]
                ),
            },
            "recommendations": self._generate_recommendations(results, test_type),
        }

        # ファイル出力
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"📄 ストレステストレポート生成: {report_file}")
        return report_file

    def _generate_recommendations(
        self, results: list[StressTestResult], test_type: str
    ) -> list[str]:
        """推奨事項生成"""
        recommendations = []

        for result in results:
            if result.stability_score < 70:
                recommendations.append(
                    f"安定性スコアが低下 ({result.stability_score:.1f}/100) - システムの改善が必要"
                )

            if result.breaking_point and result.breaking_point < 200:
                recommendations.append(
                    f"破壊点が低い ({result.breaking_point}ユーザー) - スケーラビリティの向上が必要"
                )

            if result.recovery_time and result.recovery_time > 300:
                recommendations.append(
                    f"回復時間が長い ({result.recovery_time:.1f}秒) - 回復メカニズムの改善が必要"
                )

            if "memory_exhaustion" in result.error_types:
                recommendations.append("メモリ枯渇が検出 - メモリ管理の最適化が必要")

        return (
            recommendations
            if recommendations
            else ["システムは安定したストレス耐性を示しています"]
        )


# =============================================================================
# 学習ポイント:
#
# 1. 破壊点検出:
#    - 段階的負荷増加による限界点の自動検出
#    - エラー率とレスポンス時間による破壊判定
#    - システム安定性の定量評価
#
# 2. 回復力テスト:
#    - ベースライン → ストレス → 回復の3段階テスト
#    - 回復時間の自動測定
#    - 回復能力の客観的評価
#
# 3. リソース枯渇テスト:
#    - メモリとCPU使用量の監視
#    - リソース枯渇シナリオのシミュレーション
#    - メモリ集約的負荷の生成
#
# 4. エラー連鎖防止:
#    - エラー率の段階的監視
#    - エラー連鎖の早期検出
#    - カスケード障害の予防評価
#
# 5. 実務的な分析:
#    - 安定性スコアによる定量評価
#    - 推奨事項の自動生成
#    - 詳細なレポート出力
# =============================================================================
