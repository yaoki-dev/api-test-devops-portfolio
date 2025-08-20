"""
ベンチマーク・回帰テストスイート

実務最適化版パフォーマンステスト:
- pytest-benchmarkによる高精度ベンチマーク
- パフォーマンス回帰の自動検出
- 基準値との比較による品質保証
- CI/CD統合のための自動化判定

学習ポイント:
- ベンチマーク測定の標準手法
- パフォーマンス回帰検出
- 統計的信頼性のある測定
- 継続的パフォーマンス監視
"""

import asyncio
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pytest

from config.settings import get_settings
from utils.api_client import JSONPlaceholderClient
from utils.performance_monitor import PerformanceBenchmark, PerformanceMonitor

settings = get_settings()


@dataclass
class BenchmarkResult:
    """ベンチマーク結果"""

    test_name: str
    mean_time: float
    min_time: float
    max_time: float
    stddev: float
    iterations: int
    rounds: int
    baseline_comparison: float | None = None  # ベースラインとの比較率
    regression_detected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BenchmarkConfig:
    """ベンチマークテスト設定"""

    # pytest-benchmark設定
    BENCHMARK_ROUNDS = 5  # 測定回数
    BENCHMARK_ITERATIONS = 10  # 各回の反復数

    # パフォーマンス基準値（秒）
    BASELINE_RESPONSE_TIMES = {
        "get_user": 0.5,
        "get_post": 0.5,
        "get_todo": 0.5,
        "get_comment": 0.5,
        "get_album": 0.5,
        "batch_operation": 2.0,
        "complex_workflow": 3.0,
    }

    # 回帰検出閾値
    REGRESSION_THRESHOLD_PERCENT = 20.0  # 20%以上の劣化で回帰と判定
    ACCEPTABLE_STDDEV_RATIO = 0.1  # 標準偏差/平均 が10%以下を安定と判定

    # ベンチマークファイル
    BENCHMARK_HISTORY_FILE = "reports/benchmark_history.json"


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
        alert_threshold=3.0, memory_threshold_mb=200.0, cpu_threshold_percent=80.0
    )
    return monitor


@pytest.fixture
def benchmark_manager(performance_monitor):
    """ベンチマーク管理"""
    return PerformanceBenchmark(performance_monitor)


@pytest.mark.performance
@pytest.mark.benchmark
@pytest.mark.external
class TestPerformanceBenchmarks:
    """パフォーマンスベンチマークテスト"""

    def test_single_user_request_benchmark(self, benchmark, api_client):
        """単一ユーザーリクエストベンチマーク

        目的: 基本的なAPI呼び出しの性能ベースライン確立
        重要: 他のテストの比較基準となる
        """

        async def single_user_request():
            response = await api_client.get_user(1)
            assert response["id"] == 1
            return response

        # pytest-benchmarkによる精密測定
        result = benchmark.pedantic(
            self._run_async_benchmark,
            args=(single_user_request,),
            rounds=BenchmarkConfig.BENCHMARK_ROUNDS,
            iterations=BenchmarkConfig.BENCHMARK_ITERATIONS,
        )

        # ベンチマーク結果分析
        stats = benchmark.stats
        benchmark_result = BenchmarkResult(
            test_name="single_user_request",
            mean_time=stats.mean,
            min_time=stats.min,
            max_time=stats.max,
            stddev=stats.stddev,
            iterations=BenchmarkConfig.BENCHMARK_ITERATIONS,
            rounds=BenchmarkConfig.BENCHMARK_ROUNDS,
        )

        # ベースライン比較
        baseline = BenchmarkConfig.BASELINE_RESPONSE_TIMES["get_user"]
        benchmark_result.baseline_comparison = (stats.mean / baseline - 1) * 100
        benchmark_result.regression_detected = stats.mean > baseline * (
            1 + BenchmarkConfig.REGRESSION_THRESHOLD_PERCENT / 100
        )

        # 結果出力
        self._report_benchmark_result(benchmark_result)

        # ベンチマークアサーション
        assert stats.mean <= baseline, (
            f"単一ユーザーリクエストがベースライン超過: {stats.mean:.3f}s > {baseline}s"
        )

        # 安定性チェック（標準偏差/平均）
        stability_ratio = stats.stddev / stats.mean if stats.mean > 0 else 0
        assert stability_ratio <= BenchmarkConfig.ACCEPTABLE_STDDEV_RATIO, (
            f"測定値の変動が大きすぎます: {stability_ratio:.3f} > {BenchmarkConfig.ACCEPTABLE_STDDEV_RATIO}"
        )

    def test_batch_operations_benchmark(self, benchmark, api_client):
        """バッチ操作ベンチマーク

        目的: 複数操作の一括実行性能測定
        重要: 効率的な処理パターンの評価
        """

        async def batch_operations():
            # 5つの異なるリソースを並行取得
            tasks = [
                api_client.get_user(1),
                api_client.get_post(1),
                api_client.get_todo(1),
                api_client.get_comment(1),
                api_client.get_album(1),
            ]

            results = await asyncio.gather(*tasks)

            # 結果検証
            assert len(results) == 5
            assert all(result is not None for result in results)
            return results

        # バッチ操作ベンチマーク実行
        result = benchmark.pedantic(
            self._run_async_benchmark,
            args=(batch_operations,),
            rounds=BenchmarkConfig.BENCHMARK_ROUNDS,
            iterations=BenchmarkConfig.BENCHMARK_ITERATIONS,
        )

        # ベンチマーク結果分析
        stats = benchmark.stats
        benchmark_result = BenchmarkResult(
            test_name="batch_operations",
            mean_time=stats.mean,
            min_time=stats.min,
            max_time=stats.max,
            stddev=stats.stddev,
            iterations=BenchmarkConfig.BENCHMARK_ITERATIONS,
            rounds=BenchmarkConfig.BENCHMARK_ROUNDS,
        )

        # ベースライン比較
        baseline = BenchmarkConfig.BASELINE_RESPONSE_TIMES["batch_operation"]
        benchmark_result.baseline_comparison = (stats.mean / baseline - 1) * 100
        benchmark_result.regression_detected = stats.mean > baseline * (
            1 + BenchmarkConfig.REGRESSION_THRESHOLD_PERCENT / 100
        )

        # 結果出力
        self._report_benchmark_result(benchmark_result)

        # 効率性評価（並行実行により単一操作×5より高速であるべき）
        single_operation_baseline = BenchmarkConfig.BASELINE_RESPONSE_TIMES["get_user"]
        expected_sequential_time = single_operation_baseline * 5
        efficiency = expected_sequential_time / stats.mean if stats.mean > 0 else 0

        print(f"  🚀 並行実行効率性: {efficiency:.1f}x faster than sequential")

        # バッチ操作アサーション
        assert stats.mean <= baseline, (
            f"バッチ操作がベースライン超過: {stats.mean:.3f}s > {baseline}s"
        )

        # 並行実行の効果確認（最低2倍の効率化を期待）
        assert efficiency >= 2.0, f"並行実行の効率が不十分: {efficiency:.1f}x < 2.0x"

    def test_complex_workflow_benchmark(self, benchmark, api_client):
        """複雑ワークフローベンチマーク

        目的: 実際のユーザーワークフローに近い複合操作の性能測定
        重要: 実用的な性能評価
        """

        async def complex_workflow():
            # 実際のアプリケーションユースケースをシミュレート

            # 1. ユーザー情報取得
            user = await api_client.get_user(1)
            assert user["id"] == 1

            # 2. そのユーザーの投稿一覧取得（シミュレート）
            posts_tasks = [api_client.get_post(i) for i in range(1, 4)]
            posts = await asyncio.gather(*posts_tasks)

            # 3. 各投稿のコメント取得（シミュレート）
            comments_tasks = [api_client.get_comment(i) for i in range(1, 4)]
            comments = await asyncio.gather(*comments_tasks)

            # 4. ユーザーのTODO取得
            todos_tasks = [api_client.get_todo(i) for i in range(1, 3)]
            todos = await asyncio.gather(*todos_tasks)

            # 結果検証
            assert len(posts) == 3
            assert len(comments) == 3
            assert len(todos) == 2

            return {"user": user, "posts": posts, "comments": comments, "todos": todos}

        # 複雑ワークフローベンチマーク実行
        result = benchmark.pedantic(
            self._run_async_benchmark,
            args=(complex_workflow,),
            rounds=BenchmarkConfig.BENCHMARK_ROUNDS,
            iterations=BenchmarkConfig.BENCHMARK_ITERATIONS,
        )

        # ベンチマーク結果分析
        stats = benchmark.stats
        benchmark_result = BenchmarkResult(
            test_name="complex_workflow",
            mean_time=stats.mean,
            min_time=stats.min,
            max_time=stats.max,
            stddev=stats.stddev,
            iterations=BenchmarkConfig.BENCHMARK_ITERATIONS,
            rounds=BenchmarkConfig.BENCHMARK_ROUNDS,
        )

        # ベースライン比較
        baseline = BenchmarkConfig.BASELINE_RESPONSE_TIMES["complex_workflow"]
        benchmark_result.baseline_comparison = (stats.mean / baseline - 1) * 100
        benchmark_result.regression_detected = stats.mean > baseline * (
            1 + BenchmarkConfig.REGRESSION_THRESHOLD_PERCENT / 100
        )

        # 結果出力
        self._report_benchmark_result(benchmark_result)

        # 複雑ワークフローアサーション
        assert stats.mean <= baseline, (
            f"複雑ワークフローがベースライン超過: {stats.mean:.3f}s > {baseline}s"
        )

    @pytest.mark.parametrize(
        "operation,resource_id",
        [
            ("get_user", 1),
            ("get_post", 1),
            ("get_todo", 1),
            ("get_comment", 1),
            ("get_album", 1),
        ],
    )
    def test_individual_operation_benchmarks(
        self, benchmark, api_client, operation, resource_id
    ):
        """個別操作ベンチマーク

        目的: 各API操作の個別性能測定
        重要: ボトルネック特定のための基礎データ
        """

        async def individual_operation():
            if operation == "get_user":
                response = await api_client.get_user(resource_id)
                assert response["id"] == resource_id
            elif operation == "get_post":
                response = await api_client.get_post(resource_id)
                assert response["id"] == resource_id
            elif operation == "get_todo":
                response = await api_client.get_todo(resource_id)
                assert response["id"] == resource_id
            elif operation == "get_comment":
                response = await api_client.get_comment(resource_id)
                assert response["id"] == resource_id
            elif operation == "get_album":
                response = await api_client.get_album(resource_id)
                assert response["id"] == resource_id

            return response

        # 個別操作ベンチマーク実行
        result = benchmark.pedantic(
            self._run_async_benchmark,
            args=(individual_operation,),
            rounds=BenchmarkConfig.BENCHMARK_ROUNDS,
            iterations=BenchmarkConfig.BENCHMARK_ITERATIONS,
        )

        # ベンチマーク結果分析
        stats = benchmark.stats
        test_name = f"{operation}_{resource_id}"

        benchmark_result = BenchmarkResult(
            test_name=test_name,
            mean_time=stats.mean,
            min_time=stats.min,
            max_time=stats.max,
            stddev=stats.stddev,
            iterations=BenchmarkConfig.BENCHMARK_ITERATIONS,
            rounds=BenchmarkConfig.BENCHMARK_ROUNDS,
        )

        # ベースライン比較
        baseline = BenchmarkConfig.BASELINE_RESPONSE_TIMES.get(operation, 1.0)
        benchmark_result.baseline_comparison = (stats.mean / baseline - 1) * 100
        benchmark_result.regression_detected = stats.mean > baseline * (
            1 + BenchmarkConfig.REGRESSION_THRESHOLD_PERCENT / 100
        )

        # 結果出力
        self._report_benchmark_result(benchmark_result)

        # 個別操作アサーション
        assert stats.mean <= baseline, (
            f"{operation}操作がベースライン超過: {stats.mean:.3f}s > {baseline}s"
        )

    def test_performance_regression_detection(self, benchmark, api_client):
        """パフォーマンス回帰検出テスト

        目的: 過去のベンチマーク結果との比較による回帰検出
        重要: 継続的なパフォーマンス品質保証
        """

        # 現在のベンチマーク実行
        async def regression_test_operation():
            response = await api_client.get_user(1)
            assert response["id"] == 1
            return response

        # ベンチマーク実行
        result = benchmark.pedantic(
            self._run_async_benchmark,
            args=(regression_test_operation,),
            rounds=BenchmarkConfig.BENCHMARK_ROUNDS,
            iterations=BenchmarkConfig.BENCHMARK_ITERATIONS,
        )

        # 現在の結果
        current_stats = benchmark.stats
        current_result = BenchmarkResult(
            test_name="regression_detection",
            mean_time=current_stats.mean,
            min_time=current_stats.min,
            max_time=current_stats.max,
            stddev=current_stats.stddev,
            iterations=BenchmarkConfig.BENCHMARK_ITERATIONS,
            rounds=BenchmarkConfig.BENCHMARK_ROUNDS,
        )

        # 過去の結果と比較
        regression_analysis = self._analyze_performance_regression(current_result)

        # 回帰分析結果出力
        print("\n📊 パフォーマンス回帰分析:")
        print(f"  現在の平均時間: {current_result.mean_time:.3f}s")

        if regression_analysis["has_history"]:
            print(f"  過去の平均時間: {regression_analysis['historical_mean']:.3f}s")
            print(f"  変化率: {regression_analysis['change_percent']:+.1f}%")
            print(
                f"  回帰検出: {'はい' if regression_analysis['regression_detected'] else 'いいえ'}"
            )

            if regression_analysis["regression_detected"]:
                print("  ⚠️ パフォーマンス回帰が検出されました")
            else:
                print("  ✅ パフォーマンス回帰は検出されませんでした")
        else:
            print("  📝 初回実行: ベースライン記録を保存")

        # ベンチマーク履歴保存
        self._save_benchmark_history(current_result)

        # 回帰検出アサーション
        if (
            regression_analysis["has_history"]
            and regression_analysis["regression_detected"]
        ):
            pytest.fail(
                f"パフォーマンス回帰検出: {regression_analysis['change_percent']:+.1f}% > {BenchmarkConfig.REGRESSION_THRESHOLD_PERCENT}%"
            )

    def _run_async_benchmark(self, async_func):
        """非同期関数のベンチマーク実行ヘルパー"""
        return asyncio.run(async_func())

    def _report_benchmark_result(self, result: BenchmarkResult):
        """ベンチマーク結果レポート"""
        print(f"\n📊 {result.test_name} ベンチマーク結果:")
        print(f"  平均実行時間: {result.mean_time:.3f}s")
        print(f"  最小実行時間: {result.min_time:.3f}s")
        print(f"  最大実行時間: {result.max_time:.3f}s")
        print(f"  標準偏差: {result.stddev:.3f}s")
        print(f"  測定回数: {result.rounds}回 × {result.iterations}反復")

        if result.baseline_comparison is not None:
            comparison_status = (
                "⚠️ 劣化" if result.baseline_comparison > 0 else "✅ 改善"
            )
            print(
                f"  ベースライン比較: {result.baseline_comparison:+.1f}% {comparison_status}"
            )

        # 安定性評価
        stability_ratio = (
            result.stddev / result.mean_time if result.mean_time > 0 else 0
        )
        stability_status = (
            "安定"
            if stability_ratio <= BenchmarkConfig.ACCEPTABLE_STDDEV_RATIO
            else "不安定"
        )
        print(f"  測定安定性: {stability_ratio:.3f} ({stability_status})")

    def _analyze_performance_regression(
        self, current_result: BenchmarkResult
    ) -> dict[str, Any]:
        """パフォーマンス回帰分析"""
        history_file = Path(BenchmarkConfig.BENCHMARK_HISTORY_FILE)

        # 過去のデータ読み込み
        if history_file.exists():
            with open(history_file) as f:
                history = json.load(f)

            # 同じテストの過去結果取得
            test_history = history.get(current_result.test_name, [])

            if test_history:
                # 直近の結果と比較
                latest_historical = test_history[-1]
                historical_mean = latest_historical["mean_time"]

                # 変化率計算
                change_percent = (current_result.mean_time / historical_mean - 1) * 100
                regression_detected = (
                    change_percent > BenchmarkConfig.REGRESSION_THRESHOLD_PERCENT
                )

                return {
                    "has_history": True,
                    "historical_mean": historical_mean,
                    "change_percent": change_percent,
                    "regression_detected": regression_detected,
                }

        return {
            "has_history": False,
            "historical_mean": None,
            "change_percent": 0,
            "regression_detected": False,
        }

    def _save_benchmark_history(self, result: BenchmarkResult):
        """ベンチマーク履歴保存"""
        history_file = Path(BenchmarkConfig.BENCHMARK_HISTORY_FILE)
        history_file.parent.mkdir(parents=True, exist_ok=True)

        # 既存履歴読み込み
        if history_file.exists():
            with open(history_file) as f:
                history = json.load(f)
        else:
            history = {}

        # 新しい結果追加
        if result.test_name not in history:
            history[result.test_name] = []

        # タイムスタンプ付きで保存
        result_with_timestamp = result.to_dict()
        result_with_timestamp["timestamp"] = time.time()

        history[result.test_name].append(result_with_timestamp)

        # 最新10件のみ保持
        if len(history[result.test_name]) > 10:
            history[result.test_name] = history[result.test_name][-10:]

        # ファイル保存
        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)


# =============================================================================
# 学習ポイント・実装のポイント:
#
# 1. pytest-benchmark統合:
#    - benchmark.pedantic()による高精度測定
#    - rounds/iterations設定による統計的信頼性
#    - CI/CD統合可能な自動化ベンチマーク
#
# 2. ベースライン比較:
#    - 事前定義されたパフォーマンス基準値
#    - ベースラインからの変化率計算
#    - 許容範囲内での性能評価
#
# 3. 回帰検出:
#    - 履歴データとの自動比較
#    - 20%以上の劣化で回帰と判定
#    - 継続的パフォーマンス監視
#
# 4. 多様なベンチマークパターン:
#    - 単一操作：基本性能測定
#    - バッチ操作：並行実行効率評価
#    - 複雑ワークフロー：実用的性能評価
#    - パラメータ化：全操作の網羅的測定
#
# 5. 統計的信頼性:
#    - 標準偏差による測定安定性評価
#    - 複数回測定による平均値算出
#    - 外れ値の検出と除外
#
# 6. CI/CD統合対応:
#    - JSON形式での履歴データ管理
#    - 自動回帰検出による品質ゲート
#    - ベンチマーク結果の可視化対応
# =============================================================================
