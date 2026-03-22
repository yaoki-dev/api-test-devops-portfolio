"""
APIパフォーマンステスト - 基盤実装

学習目標:
- レスポンス時間測定
- 並行リクエスト処理
- リソース使用量監視
- パフォーマンス回帰検出
"""

import asyncio
import statistics
import time
from typing import Any

import psutil
import pytest

from utils.api_client import AsyncAPIClient

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

        return {
            "total_duration": self.end_time - self.start_time,
            "request_count": len(self.response_times),
            "response_times": {
                "mean": statistics.mean(self.response_times),
                "median": statistics.median(self.response_times),
                "min": min(self.response_times),
                "max": max(self.response_times),
                "p95": statistics.quantiles(self.response_times, n=20)[18]
                if len(self.response_times) > 20
                else max(self.response_times),
                "p99": statistics.quantiles(self.response_times, n=100)[98]
                if len(self.response_times) > 100
                else max(self.response_times),
            },
            "throughput": len(self.response_times) / (self.end_time - self.start_time),
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


@pytest.mark.performance
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

            start_time = time.time()
            response = await client.get("/posts/1")
            end_time = time.time()

            response_time = end_time - start_time
            metrics.record_response_time(response_time)
            metrics.stop_monitoring()

            # アサーション
            assert response.status_code == 200
            threshold = self.RESPONSE_TIME_THRESHOLD
            assert response_time < threshold, (
                f"レスポンス時間が閾値を超過: {response_time:.3f}s > {threshold}s"
            )

            summary = metrics.get_summary()
            print(f"📊 単一リクエストパフォーマンス: {response_time:.3f}s")
            print(f"💾 メモリ使用量: {summary['memory_usage']['start_mb']:.1f}MB")

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
                tasks.append(self._measure_request(client, f"/posts/{i + 1}", metrics))

            # 並行実行
            await asyncio.gather(*tasks)
            metrics.stop_monitoring()

            summary = metrics.get_summary()

            # アサーション
            assert summary["request_count"] == concurrent_count
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
            print("📊 並行リクエストパフォーマンス:")
            print(f"  - リクエスト数: {summary['request_count']}")
            print(f"  - 平均レスポンス時間: {summary['response_times']['mean']:.3f}s")
            print(f"  - 95パーセンタイル: {summary['response_times']['p95']:.3f}s")
            print(f"  - スループット: {summary['throughput']:.1f} req/s")
            print(f"  - メモリ増加: {summary['memory_usage']['increase_mb']:.1f}MB")

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
                    batch_tasks.append(self._measure_request(client, endpoint, metrics))

                await asyncio.gather(*batch_tasks)
                await asyncio.sleep(0.1)  # バッチ間隔

            metrics.stop_monitoring()

            summary = metrics.get_summary()

            # パフォーマンス分析
            assert summary["request_count"] == request_count
            assert summary["response_times"]["mean"] < self.RESPONSE_TIME_THRESHOLD * 1.5, (
                f"負荷時平均レスポンス時間が許容値を超過: {summary['response_times']['mean']:.3f}s"
            )

            # 結果詳細出力
            print("📊 負荷テストシミュレーション結果:")
            print(f"  - 総リクエスト数: {summary['request_count']}")
            print(f"  - 実行時間: {summary['total_duration']:.1f}s")
            print(f"  - 平均レスポンス時間: {summary['response_times']['mean']:.3f}s")
            print(f"  - 最小レスポンス時間: {summary['response_times']['min']:.3f}s")
            print(f"  - 最大レスポンス時間: {summary['response_times']['max']:.3f}s")
            print(f"  - 95パーセンタイル: {summary['response_times']['p95']:.3f}s")
            print(f"  - スループット: {summary['throughput']:.1f} req/s")
            print(f"  - メモリ使用量変化: {summary['memory_usage']['increase_mb']:.1f}MB")

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
                    await self._measure_request(client, endpoint, metrics)

                metrics.stop_monitoring()
                summary = metrics.get_summary()
                results[endpoint] = summary["response_times"]["mean"]

        # 結果分析
        print("📊 エンドポイント別パフォーマンス比較:")
        sorted_results = sorted(results.items(), key=lambda x: x[1])

        for endpoint, avg_time in sorted_results:
            print(f"  - {endpoint}: {avg_time:.3f}s")

        # 最も遅いエンドポイントが閾値内であることを確認
        slowest_time = max(results.values())
        assert slowest_time < self.RESPONSE_TIME_THRESHOLD * 1.2, (
            f"最も遅いエンドポイントが許容値を超過: {slowest_time:.3f}s"
        )

    async def _measure_request(
        self,
        client: AsyncAPIClient,
        endpoint: str,
        metrics: PerformanceMetrics,
    ) -> None:
        """リクエスト実行とレスポンス時間測定"""
        start_time = time.time()
        try:
            response = await client.get(endpoint)
            assert response.status_code == 200
        except Exception as e:
            print(f"Request failed for {endpoint}: {e}")
            raise
        finally:
            metrics.record_response_time(time.time() - start_time)


@pytest.mark.performance
class TestPerformanceRegression:
    """パフォーマンス回帰テスト"""

    # ベースライン値（実際の測定値に基づいて調整）
    BASELINE_RESPONSE_TIME = 1.0  # 1秒
    REGRESSION_THRESHOLD = 1.5  # 50%の悪化まで許容

    @pytest.mark.asyncio
    async def test_performance_regression_detection(self):
        """パフォーマンス回帰検出テスト"""
        metrics = PerformanceMetrics()

        async with AsyncAPIClient() as client:
            metrics.start_monitoring()

            # ベースラインテスト（10回実行）
            for _ in range(10):
                await self._measure_request(client, "/posts/1", metrics)

            metrics.stop_monitoring()

            summary = metrics.get_summary()
            current_performance = summary["response_times"]["mean"]

            # 回帰検出
            performance_ratio = current_performance / self.BASELINE_RESPONSE_TIME

            print("📊 パフォーマンス回帰検出:")
            print(f"  - ベースライン: {self.BASELINE_RESPONSE_TIME:.3f}s")
            print(f"  - 現在の性能: {current_performance:.3f}s")
            print(f"  - 性能比率: {performance_ratio:.2f}x")

            if performance_ratio > self.REGRESSION_THRESHOLD * 2:
                t = self.REGRESSION_THRESHOLD * 2
                msg = f"深刻なパフォーマンス回帰: {performance_ratio:.2f}x (閾値: {t:.1f}x)"
                raise AssertionError(msg)
            if performance_ratio > self.REGRESSION_THRESHOLD:
                print(f"⚠️ パフォーマンス警告: {performance_ratio:.2f}x")
            else:
                print("✅ パフォーマンス回帰なし")

    async def _measure_request(
        self,
        client: AsyncAPIClient,
        endpoint: str,
        metrics: PerformanceMetrics,
    ) -> None:
        """リクエスト実行とレスポンス時間測定"""
        start_time = time.time()
        try:
            response = await client.get(endpoint)
            assert response.status_code == 200
        except Exception as e:
            print(f"Request failed for {endpoint}: {e}")
            raise
        finally:
            metrics.record_response_time(time.time() - start_time)


# パフォーマンステストレポート生成
def generate_performance_report(
    metrics_list: list[PerformanceMetrics],
    output_file: str = "reports/performance-report.json",
) -> None:
    """パフォーマンステストレポート生成"""
    import json
    from pathlib import Path

    summaries = [metrics.get_summary() for metrics in metrics_list]
    report = {
        "timestamp": time.time(),
        "test_results": summaries,
        "summary": {
            "total_tests": len(metrics_list),
            "avg_response_time": statistics.mean(
                [
                    summary["response_times"]["mean"]
                    for summary in summaries
                    if "response_times" in summary
                ],
            )
            if metrics_list
            else 0,
        },
    }

    # レポートディレクトリ作成
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    # レポート出力
    with Path(output_file).open("w") as f:
        json.dump(report, f, indent=2)

    print(f"📊 パフォーマンステストレポートを生成しました: {output_file}")


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
#    - レポート生成機能
# =============================================================================
