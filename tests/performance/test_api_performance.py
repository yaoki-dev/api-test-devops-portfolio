"""
APIパフォーマンステスト - 基盤実装

学習目標:
- レスポンス時間測定
- 並行リクエスト処理
- リソース使用量監視
- パフォーマンス回帰検出
"""

import asyncio
import time
from typing import Any

import psutil
import pytest

from utils.api_client import APIClientError, AsyncAPIClient
from utils.logger import get_logger

logger = get_logger(__name__)

# Module-level markers: Performance tests（週次CIのみ実行 — PR CIから除外）
# Note: `integration` マーカーは意図的に削除済み —
#   PR CI の `-m "(unit or integration)"` 条件から除外するため
# Design rationale: Performance testing requires actual network latency measurement
# See: docs/interview/multi_level_security_testing.md
pytestmark = [pytest.mark.performance]


class PerformanceMetrics:
    """パフォーマンスメトリクス収集クラス"""

    def __init__(self):
        self.response_times: list[float] = []
        self.start_time: float = 0
        self.end_time: float = 0
        self.memory_usage: list[float] = []
        self.cpu_usage: list[float] = []

    def start_monitoring(self):
        """パフォーマンス監視開始"""
        self.start_time = time.time()
        self.memory_usage.append(psutil.Process().memory_info().rss / 1024 / 1024)  # MB
        self.cpu_usage.append(psutil.cpu_percent())

    def record_response_time(self, response_time: float) -> None:
        """レスポンス時間記録"""
        self.response_times.append(response_time)

    def stop_monitoring(self):
        """パフォーマンス監視終了"""
        self.end_time = time.time()
        self.memory_usage.append(psutil.Process().memory_info().rss / 1024 / 1024)
        self.cpu_usage.append(psutil.cpu_percent())

    def get_summary(self) -> dict[str, Any]:
        """パフォーマンスサマリー取得"""
        if not self.response_times:
            return {"error": "No response times recorded"}

        elapsed = self.end_time - self.start_time
        sorted_times = sorted(self.response_times)
        n = len(sorted_times)
        return {
            "total_duration": elapsed,
            "request_count": len(self.response_times),
            "response_times": {
                "mean": sum(self.response_times) / n,
                "median": sorted_times[n // 2]
                if n % 2
                else (sorted_times[n // 2 - 1] + sorted_times[n // 2]) / 2,
                "min": sorted_times[0],
                "max": sorted_times[-1],
                # -1e-9: n*p が整数の場合（n=100等）に ceil(n*p)-1 と等価にするための補正
                "p95": sorted_times[int(n * 0.95 - 1e-9)] if n > 20 else sorted_times[-1],
                "p99": sorted_times[int(n * 0.99 - 1e-9)] if n > 100 else sorted_times[-1],
            },
            "throughput": len(self.response_times) / elapsed if elapsed > 0 else 0.0,
            "memory_usage": {
                "start_mb": self.memory_usage[0] if self.memory_usage else 0,
                "end_mb": self.memory_usage[-1] if self.memory_usage else 0,
                "increase_mb": (self.memory_usage[-1] - self.memory_usage[0])
                if len(self.memory_usage) >= 2
                else 0,
            },
            "cpu_usage": {
                "start_percent": self.cpu_usage[0] if self.cpu_usage else 0,
                "end_percent": self.cpu_usage[-1] if self.cpu_usage else 0,
            },
        }


async def _measure_request(
    client: AsyncAPIClient,
    endpoint: str,
    metrics: PerformanceMetrics,
) -> None:
    """リクエスト実行とレスポンス時間測定（HTTP応答受信時点で記録）"""
    start_time = time.time()
    try:
        response = await client.get(endpoint)
    except APIClientError as e:
        logger.warning("request_failed", endpoint=endpoint, error=str(e))
        raise

    metrics.record_response_time(time.time() - start_time)

    if response.status_code != 200:
        raise AssertionError(
            f"Unexpected status code for {endpoint}: expected 200, got {response.status_code}"
        )


class TestAPIPerformance:
    """APIパフォーマンステストクラス"""

    # パフォーマンス閾値設定
    RESPONSE_TIME_THRESHOLD = 2.0  # 2秒
    P95_THRESHOLD = 3.0  # 95パーセンタイル 3秒
    # 外部API依存のため保守的閾値設定
    # - 実測値: 4-5 req/s（ローカル環境、2025-12時点）
    # - TLS handshake・DNS解決等の初回接続コスト含む
    THROUGHPUT_THRESHOLD = 3  # 3 requests/sec

    @pytest.mark.asyncio
    async def test_single_request_performance(self):
        """単一リクエストのパフォーマンステスト"""
        metrics = PerformanceMetrics()

        async with AsyncAPIClient() as client:
            metrics.start_monitoring()
            await _measure_request(client, "/posts/1", metrics)
            metrics.stop_monitoring()

            summary = metrics.get_summary()
            response_time = summary["response_times"]["mean"]

            # アサーション
            threshold = self.RESPONSE_TIME_THRESHOLD
            assert response_time < threshold, (
                f"レスポンス時間が閾値を超過: {response_time:.3f}s > {threshold}s"
            )

            logger.info(
                "single_request_performance",
                response_time=round(response_time, 3),
                memory_mb=round(summary["memory_usage"]["start_mb"], 1),
                cpu_start_percent=round(summary["cpu_usage"]["start_percent"], 1),
            )

    @pytest.mark.asyncio
    async def test_concurrent_requests_performance(self):
        """並行リクエストのパフォーマンステスト"""
        metrics = PerformanceMetrics()
        concurrent_count = 10

        async with AsyncAPIClient() as client:
            metrics.start_monitoring()

            # 並行リクエストタスク作成
            tasks = []
            for i in range(concurrent_count):
                tasks.append(_measure_request(client, f"/posts/{i + 1}", metrics))

            # 並行実行
            results = await asyncio.gather(*tasks, return_exceptions=True)
            failures = [r for r in results if isinstance(r, BaseException)]
            if failures:
                failure_summary = "\n".join(str(e) for e in failures)
                raise AssertionError(
                    f"{len(failures)}/{len(tasks)} リクエスト失敗:\n{failure_summary}"
                )
            metrics.stop_monitoring()

            summary = metrics.get_summary()

            # アサーション
            assert summary["request_count"] == concurrent_count, (
                f"成功リクエスト数が期待値と不一致: "
                f"{summary['request_count']}/{concurrent_count} 件成功"
            )
            assert summary["response_times"]["mean"] < self.RESPONSE_TIME_THRESHOLD, (
                f"平均レスポンス時間が閾値を超過: {summary['response_times']['mean']:.3f}s"
            )
            assert summary["response_times"]["p95"] < self.P95_THRESHOLD, (
                f"95パーセンタイルが閾値を超過: {summary['response_times']['p95']:.3f}s"
            )
            assert summary["throughput"] > self.THROUGHPUT_THRESHOLD, (
                f"スループットが閾値を下回る: {summary['throughput']:.1f} req/s "
                f"< {self.THROUGHPUT_THRESHOLD} req/s"
            )

            # 結果出力
            logger.info(
                "concurrent_requests_performance",
                request_count=summary["request_count"],
                mean_response_time=round(summary["response_times"]["mean"], 3),
                p95=round(summary["response_times"]["p95"], 3),
                throughput=round(summary["throughput"], 1),
                memory_increase_mb=round(summary["memory_usage"]["increase_mb"], 1),
                cpu_start_percent=round(summary["cpu_usage"]["start_percent"], 1),
                cpu_end_percent=round(summary["cpu_usage"]["end_percent"], 1),
            )

    @pytest.mark.asyncio
    async def test_load_test_simulation(self):
        """負荷テストシミュレーション"""
        metrics = PerformanceMetrics()
        request_count = 50
        batch_size = 5

        async with AsyncAPIClient() as client:
            metrics.start_monitoring()

            # バッチごとにリクエスト実行
            for batch in range(0, request_count, batch_size):
                batch_tasks = []
                for i in range(batch, min(batch + batch_size, request_count)):
                    endpoint = f"/posts/{(i % 100) + 1}"  # 1-100のランダムエンドポイント
                    batch_tasks.append(_measure_request(client, endpoint, metrics))

                results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                failures = [r for r in results if isinstance(r, BaseException)]
                if failures:
                    failure_summary = "\n".join(str(e) for e in failures)
                    raise AssertionError(
                        f"{len(failures)}/{len(batch_tasks)} リクエスト失敗:\n{failure_summary}"
                    )
                await asyncio.sleep(0.1)  # バッチ間隔

            metrics.stop_monitoring()

            summary = metrics.get_summary()

            # パフォーマンス分析
            assert summary["request_count"] == request_count, (
                f"成功リクエスト数が期待値と不一致: "
                f"{summary['request_count']}/{request_count} 件成功"
            )
            assert summary["response_times"]["mean"] < self.RESPONSE_TIME_THRESHOLD * 1.5, (
                f"負荷時平均レスポンス時間が許容値を超過: {summary['response_times']['mean']:.3f}s"
            )

            # 結果詳細出力
            logger.info(
                "load_test_simulation",
                total_requests=summary["request_count"],
                duration=round(summary["total_duration"], 1),
                mean_response_time=round(summary["response_times"]["mean"], 3),
                min_response_time=round(summary["response_times"]["min"], 3),
                max_response_time=round(summary["response_times"]["max"], 3),
                p95=round(summary["response_times"]["p95"], 3),
                throughput=round(summary["throughput"], 1),
                memory_increase_mb=round(summary["memory_usage"]["increase_mb"], 1),
                cpu_start_percent=round(summary["cpu_usage"]["start_percent"], 1),
                cpu_end_percent=round(summary["cpu_usage"]["end_percent"], 1),
            )

    @pytest.mark.asyncio
    async def test_endpoint_comparison_performance(self):
        """エンドポイント別パフォーマンス比較"""
        endpoints = ["/posts/1", "/users/1", "/todos/1", "/comments/1"]
        results = {}

        async with AsyncAPIClient() as client:
            for endpoint in endpoints:
                metrics = PerformanceMetrics()
                metrics.start_monitoring()

                # 各エンドポイントを5回テスト
                for _ in range(5):
                    await _measure_request(client, endpoint, metrics)

                metrics.stop_monitoring()
                summary = metrics.get_summary()
                results[endpoint] = summary["response_times"]["mean"]

        # 結果分析
        sorted_results = sorted(results.items(), key=lambda x: x[1])
        for endpoint, avg_time in sorted_results:
            logger.info(
                "endpoint_comparison",
                endpoint=endpoint,
                avg_response_time=round(avg_time, 3),
            )

        # 最も遅いエンドポイントが閾値内であることを確認
        slowest_time = max(results.values())
        assert slowest_time < self.RESPONSE_TIME_THRESHOLD * 1.2, (
            f"最も遅いエンドポイントが許容値を超過: {slowest_time:.3f}s"
        )


class TestPerformanceRegression:
    """パフォーマンス回帰テスト"""

    # ベースライン値（実際の測定値に基づいて調整）
    BASELINE_RESPONSE_TIME = 2.0  # 秒（外部API + CI環境の実測値に基づく保守的な値；旧: 1.0s）
    REGRESSION_THRESHOLD = 1.5  # 50%悪化まで許容；上限 = 2.0s × 1.5 = 3.0s（旧しきい値と同値）

    @pytest.mark.asyncio
    async def test_performance_regression_detection(self):
        """パフォーマンス回帰検出テスト"""
        metrics = PerformanceMetrics()

        async with AsyncAPIClient() as client:
            metrics.start_monitoring()

            # ベースラインテスト（10回実行）
            for _ in range(10):
                await _measure_request(client, "/posts/1", metrics)

            metrics.stop_monitoring()

            summary = metrics.get_summary()
            current_performance = summary["response_times"]["mean"]

            # 回帰検出
            performance_ratio = current_performance / self.BASELINE_RESPONSE_TIME

            logger.info(
                "performance_regression_detection",
                baseline=round(self.BASELINE_RESPONSE_TIME, 3),
                current=round(current_performance, 3),
                ratio=round(performance_ratio, 2),
                cpu_start_percent=round(summary["cpu_usage"]["start_percent"], 1),
            )

            assert performance_ratio <= self.REGRESSION_THRESHOLD, (
                f"Performance regression detected: {performance_ratio:.2f}x "
                f"(current={current_performance:.3f}s, "
                f"baseline={self.BASELINE_RESPONSE_TIME}s)"
            )
            logger.info("performance_regression_check_passed")


# =============================================================================
# 学習ポイント:
#
# 1. パフォーマンスメトリクス収集:
#    - レスポンス時間統計（平均、中央値、パーセンタイル）
#    - スループット測定
#    - リソース使用量監視
#
# 2. 並行処理テスト:
#    - asyncio.gather による並行実行
#    - バッチ処理による負荷制御
#    - メモリ・CPU使用量監視
#
# 3. パフォーマンス回帰検出:
#    - ベースライン値との比較
#    - 閾値設定による自動判定
#    - CI/CD統合のための自動化
#
# 4. 実用的な測定:
#    - 統計的分析（パーセンタイル計算）
#    - エンドポイント別比較
# =============================================================================
