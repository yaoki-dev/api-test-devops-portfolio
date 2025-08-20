"""
基本負荷テストスイート

実務最適化版パフォーマンステスト:
- 段階的負荷増加による実践的な負荷テスト
- pytest-benchmark統合による高精度ベンチマーク
- JSONPlaceholder API制限を考慮した軽量設計
- CI/CD統合のための明確な合格/不合格判定

学習ポイント:
- 現実的な負荷テスト設計
- Python async/await の実践的活用
- メトリクス収集・分析
- パフォーマンス閾値管理
"""

import asyncio
import statistics
import time

import pytest

from config.settings import get_settings
from utils.api_client import JSONPlaceholderClient
from utils.performance_monitor import PerformanceBenchmark, PerformanceMonitor

settings = get_settings()


class LoadTestConfig:
    """負荷テスト設定"""

    # JSONPlaceholder API制限を考慮した段階的負荷設定
    LOAD_STAGES = [1, 5, 10, 20, 50]  # ユーザー数
    MAX_CONCURRENT_REQUESTS = 10  # 同時リクエスト数上限
    REQUEST_TIMEOUT = 30.0  # タイムアウト設定
    STAGE_DURATION = 5.0  # 各段階の持続時間

    # パフォーマンス閾値（実務基準）
    MAX_RESPONSE_TIME_SECONDS = 5.0  # 最大レスポンス時間
    MIN_SUCCESS_RATE_PERCENT = 95.0  # 最小成功率
    MAX_P95_RESPONSE_TIME = 3.0  # P95レスポンス時間
    MAX_P99_RESPONSE_TIME = 5.0  # P99レスポンス時間


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
        alert_threshold=LoadTestConfig.MAX_RESPONSE_TIME_SECONDS,
        memory_threshold_mb=200.0,
        cpu_threshold_percent=80.0,
    )
    return monitor


@pytest.fixture
def load_test_benchmark(performance_monitor):
    """負荷テストベンチマーク"""
    return PerformanceBenchmark(performance_monitor)


@pytest.mark.performance
@pytest.mark.load
@pytest.mark.external
@pytest.mark.slow
class TestBasicLoadTesting:
    """基本負荷テスト"""

    async def test_single_user_baseline_performance(self, api_client, benchmark):
        """シングルユーザーベースライン性能テスト

        目的: 単一リクエストの基準性能を測定
        重要: 他の負荷テストの比較基準となる
        """

        async def single_request():
            response = await api_client.get_user(1)
            assert response["id"] == 1
            return response

        # pytest-benchmarkによる精密測定
        result = await benchmark.pedantic(single_request, rounds=10, iterations=5)

        # ベースライン検証
        stats = benchmark.stats
        assert stats.mean < LoadTestConfig.MAX_RESPONSE_TIME_SECONDS, (
            f"ベースライン性能不足: 平均 {stats.mean:.3f}s > {LoadTestConfig.MAX_RESPONSE_TIME_SECONDS}s"
        )

        print("\n🎯 ベースライン性能:")
        print(f"   平均レスポンス時間: {stats.mean:.3f}s")
        print(f"   最小レスポンス時間: {stats.min:.3f}s")
        print(f"   最大レスポンス時間: {stats.max:.3f}s")
        print(f"   標準偏差: {stats.stddev:.3f}s")

    @pytest.mark.parametrize("user_count", LoadTestConfig.LOAD_STAGES)
    async def test_staged_load_performance(
        self, api_client, performance_monitor, load_test_benchmark, user_count
    ):
        """段階的負荷テスト

        各段階でのパフォーマンス評価:
        - レスポンス時間分析
        - 成功率計測
        - システムリソース監視
        """
        print(f"\n🚀 負荷テスト開始: {user_count}ユーザー")

        # 負荷テスト実行
        async def test_endpoint():
            # ランダムなユーザーIDでテスト（1-100）
            import random

            user_id = random.randint(1, 100)
            response = await api_client.get_user(user_id)
            assert response["id"] == user_id
            return response

        # ベンチマーク実行
        result = await load_test_benchmark.run_benchmark(
            test_func=test_endpoint,
            endpoint_name=f"get_user_{user_count}_users",
            iterations=user_count * 2,  # 各ユーザーが2回リクエスト
            concurrency=min(user_count, LoadTestConfig.MAX_CONCURRENT_REQUESTS),
        )

        # パフォーマンス評価
        response_time_stats = result["results"]["response_time"]
        success_rate = result["results"]["success_rate"]
        throughput = result["results"]["throughput"]

        print("📊 パフォーマンス結果:")
        print(f"   完了リクエスト: {result['results']['completed_requests']}")
        print(f"   失敗リクエスト: {result['results']['failed_requests']}")
        print(f"   成功率: {success_rate:.1f}%")
        print(f"   スループット: {throughput:.1f} req/s")
        print(f"   平均レスポンス時間: {response_time_stats['mean']:.3f}s")
        print(f"   P95レスポンス時間: {response_time_stats['p95']:.3f}s")
        print(f"   P99レスポンス時間: {response_time_stats['p99']:.3f}s")

        # 品質ゲート判定
        assert success_rate >= LoadTestConfig.MIN_SUCCESS_RATE_PERCENT, (
            f"成功率不足: {success_rate:.1f}% < {LoadTestConfig.MIN_SUCCESS_RATE_PERCENT}%"
        )

        assert (
            response_time_stats["mean"] <= LoadTestConfig.MAX_RESPONSE_TIME_SECONDS
        ), (
            f"平均レスポンス時間超過: {response_time_stats['mean']:.3f}s > {LoadTestConfig.MAX_RESPONSE_TIME_SECONDS}s"
        )

        assert response_time_stats["p95"] <= LoadTestConfig.MAX_P95_RESPONSE_TIME, (
            f"P95レスポンス時間超過: {response_time_stats['p95']:.3f}s > {LoadTestConfig.MAX_P95_RESPONSE_TIME}s"
        )

        # 負荷段階別のアサーション
        if user_count <= 10:
            # 軽負荷: より厳しい基準
            assert response_time_stats["mean"] <= 2.0, (
                f"軽負荷でのレスポンス時間超過: {response_time_stats['mean']:.3f}s > 2.0s"
            )
        elif user_count <= 20:
            # 中負荷: 標準基準
            assert response_time_stats["p95"] <= 3.0, (
                f"中負荷でのP95レスポンス時間超過: {response_time_stats['p95']:.3f}s > 3.0s"
            )
        else:
            # 高負荷: 緩和された基準
            assert response_time_stats["p99"] <= LoadTestConfig.MAX_P99_RESPONSE_TIME, (
                f"高負荷でのP99レスポンス時間超過: {response_time_stats['p99']:.3f}s > {LoadTestConfig.MAX_P99_RESPONSE_TIME}s"
            )

    async def test_sustained_load_performance(self, api_client, performance_monitor):
        """持続負荷テスト

        目的: 一定負荷での長時間安定性確認
        重要: メモリリーク、パフォーマンス劣化の検出
        """
        print(f"\n⏱️ 持続負荷テスト開始: 10ユーザー × {LoadTestConfig.STAGE_DURATION}秒")

        start_time = time.time()
        end_time = start_time + LoadTestConfig.STAGE_DURATION
        request_count = 0
        errors = []

        async def sustained_request_worker():
            """持続リクエストワーカー"""
            nonlocal request_count, errors
            while time.time() < end_time:
                try:
                    start_req_time = time.time()
                    response = await api_client.get_user(1)
                    end_req_time = time.time()

                    # パフォーマンス記録
                    performance_monitor.record_performance(
                        endpoint="sustained_load_test",
                        response_time=end_req_time - start_req_time,
                        status_code=200 if response else 500,
                    )

                    request_count += 1
                    assert response["id"] == 1

                    # 短い休憩
                    await asyncio.sleep(0.1)

                except Exception as e:
                    errors.append(str(e))

        # 10並行ワーカーで実行
        workers = [sustained_request_worker() for _ in range(10)]
        await asyncio.gather(*workers, return_exceptions=True)

        # 結果分析
        total_duration = time.time() - start_time
        success_rate = (
            (request_count / (request_count + len(errors))) * 100
            if request_count + len(errors) > 0
            else 0
        )
        throughput = request_count / total_duration

        # 統計取得
        stats = performance_monitor.get_statistics(time_window=total_duration + 1)

        print("📈 持続負荷結果:")
        print(f"   実行時間: {total_duration:.1f}秒")
        print(f"   総リクエスト数: {request_count}")
        print(f"   エラー数: {len(errors)}")
        print(f"   成功率: {success_rate:.1f}%")
        print(f"   スループット: {throughput:.1f} req/s")
        if "response_time" in stats:
            print(f"   平均レスポンス時間: {stats['response_time']['mean']:.3f}s")
            print(f"   P95レスポンス時間: {stats['response_time']['p95']:.3f}s")

        # 持続負荷品質ゲート
        assert success_rate >= 98.0, f"持続負荷成功率不足: {success_rate:.1f}% < 98.0%"
        assert request_count > 0, "リクエストが実行されませんでした"
        assert throughput > 1.0, f"スループット不足: {throughput:.1f} req/s < 1.0 req/s"

    async def test_load_progression_analysis(self, api_client, performance_monitor):
        """負荷進行分析テスト

        目的: 負荷増加に伴うパフォーマンス変化の分析
        重要: スケーラビリティの限界点特定
        """
        print("\n📈 負荷進行分析開始")

        progression_results = []

        for user_count in LoadTestConfig.LOAD_STAGES:
            print(f"   負荷段階: {user_count}ユーザー")

            # 各段階での短期間テスト
            stage_start = time.time()
            stage_requests = []

            async def stage_request():
                start_time = time.time()
                response = await api_client.get_user(1)
                end_time = time.time()
                response_time = end_time - start_time
                stage_requests.append(response_time)
                return response

            # 並行実行
            tasks = [stage_request() for _ in range(user_count)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 成功とエラーの分離
            successful_requests = [
                r for r in stage_requests if isinstance(r, (int, float))
            ]
            stage_duration = time.time() - stage_start

            stage_result = {
                "user_count": user_count,
                "duration": stage_duration,
                "total_requests": len(tasks),
                "successful_requests": len(successful_requests),
                "success_rate": len(successful_requests) / len(tasks) * 100,
                "throughput": len(successful_requests) / stage_duration,
                "response_time": {
                    "mean": statistics.mean(successful_requests)
                    if successful_requests
                    else 0,
                    "min": min(successful_requests) if successful_requests else 0,
                    "max": max(successful_requests) if successful_requests else 0,
                    "median": statistics.median(successful_requests)
                    if successful_requests
                    else 0,
                },
            }

            progression_results.append(stage_result)

            # 短い休憩
            await asyncio.sleep(0.5)

        # 進行分析
        print("\n📊 負荷進行分析結果:")
        print(
            f"{'ユーザー数':<8} {'成功率%':<8} {'スループット':<12} {'平均時間(s)':<12} {'最大時間(s)':<12}"
        )
        print("-" * 60)

        for result in progression_results:
            print(
                f"{result['user_count']:<8} "
                f"{result['success_rate']:<8.1f} "
                f"{result['throughput']:<12.1f} "
                f"{result['response_time']['mean']:<12.3f} "
                f"{result['response_time']['max']:<12.3f}"
            )

        # スケーラビリティ分析
        max_successful_load = max(
            [r for r in progression_results if r["success_rate"] >= 95.0],
            key=lambda x: x["user_count"],
            default=progression_results[0],
        )

        print("\n🎯 スケーラビリティ分析:")
        print(f"   95%成功率での最大負荷: {max_successful_load['user_count']}ユーザー")
        print(f"   その時のスループット: {max_successful_load['throughput']:.1f} req/s")
        print(
            f"   その時の平均レスポンス時間: {max_successful_load['response_time']['mean']:.3f}s"
        )

        # 進行分析アサーション
        assert max_successful_load["user_count"] >= 10, (
            "スケーラビリティ不足: 95%成功率での最大負荷が10ユーザー未満"
        )

        # レスポンス時間の線形増加確認（大幅な劣化がないか）
        response_times = [
            r["response_time"]["mean"]
            for r in progression_results
            if r["response_time"]["mean"] > 0
        ]
        if len(response_times) >= 2:
            time_ratio = response_times[-1] / response_times[0]
            assert time_ratio < 10.0, (
                f"レスポンス時間の大幅劣化: {time_ratio:.1f}倍 > 10倍"
            )


# =============================================================================
# 学習ポイント・実装のポイント:
#
# 1. 段階的負荷増加:
#    - 現実的な負荷段階設定（1→5→10→20→50ユーザー）
#    - JSONPlaceholder API制限を考慮した軽量設計
#    - 各段階での詳細パフォーマンス分析
#
# 2. pytest-benchmark統合:
#    - benchmark.pedantic()による高精度測定
#    - 統計的信頼性のある結果（rounds/iterations設定）
#    - CI/CDで活用できるベンチマーク結果
#
# 3. 実務品質ゲート:
#    - 明確な合格/不合格基準
#    - 負荷段階別の適切な閾値設定
#    - スケーラビリティ限界点の特定
#
# 4. パフォーマンスメトリクス:
#    - レスポンス時間（平均、P95、P99）
#    - 成功率、スループット
#    - システムリソース監視統合
#
# 5. CI/CD統合対応:
#    - pytest マーカーによる実行制御
#    - 自動判定によるパイプライン品質ゲート
#    - 詳細ログ出力による問題特定支援
# =============================================================================
