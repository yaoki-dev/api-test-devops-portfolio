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
        self.end_time: float | None = None
        self.memory_usage: list[float] = []
        self.cpu_usage: list[float | None] = []

    def start_monitoring(self):
        """パフォーマンス監視開始

        psutil.cpu_percent(interval=None) を warmup として呼び出す。
        戻り値は破棄する（初回呼び出しは仕様上 0.0 で意味なし）。
        次回 cpu_percent(interval=None) 呼び出し時に、ここからの delta を取得する。
        blocking なしのため start_time の精度に影響しない。
        cpu_usage はこの時点では append しない（stop_monitoring の delta 取得後に追記）。
        """
        psutil.cpu_percent(interval=None)  # warmup（内部カウンターリセット、戻り値破棄）
        self.start_time = time.time()
        self.memory_usage.append(psutil.Process().memory_info().rss / 1024 / 1024)  # MB
        self.cpu_usage.append(
            None
        )  # 測定開始時点のベースライン: non-blocking 設計のため意図的に未計測

    def record_response_time(self, response_time: float) -> None:
        """レスポンス時間記録"""
        self.response_times.append(response_time)

    def stop_monitoring(self):
        """パフォーマンス監視終了

        psutil.cpu_percent(interval=None) で start_monitoring からの
        delta-based 平均 CPU% を取得する（blocking なし、end_time 精度を毀損しない）。
        """
        self.end_time = time.time()
        self.memory_usage.append(psutil.Process().memory_info().rss / 1024 / 1024)
        self.cpu_usage.append(psutil.cpu_percent(interval=None))

    def get_summary(self) -> dict[str, Any]:
        """パフォーマンスサマリー取得"""
        if not self.response_times:
            return {"error": "No response times recorded"}

        if self.end_time is None:
            raise RuntimeError(
                "get_summary() called before stop_monitoring(). Call stop_monitoring() first."
            )
        elapsed = self.end_time - self.start_time
        return {
            "total_duration": elapsed,
            "request_count": len(self.response_times),
            "response_times": {
                "mean": statistics.mean(self.response_times),
                "median": statistics.median(self.response_times),
                "min": min(self.response_times),
                "max": max(self.response_times),
                # Note: quantiles()はlen>=2で動作するが、サンプル数が少ない場合は
                # inclusive方式で補間のみ（外挿なし）。テスト目的には十分。
                "p95": statistics.quantiles(self.response_times, n=20, method="inclusive")[18]
                if len(self.response_times) >= 2
                else self.response_times[0],
                "p99": statistics.quantiles(self.response_times, n=100, method="inclusive")[98]
                if len(self.response_times) >= 2
                else self.response_times[0],
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
                # start_percent: non-blocking 設計のため意図的に未計測（None）
                # 測定開始時点のCPU%は記録しない仕様。end_percent は start からの delta 平均。
                "start_percent": None,  # non-blocking設計のため未計測（warmupのみ実施）
                "end_percent": self.cpu_usage[-1] if self.cpu_usage else 0.0,
            },
        }


async def _measure_request(
    client: AsyncAPIClient,
    endpoint: str,
    metrics: PerformanceMetrics,
) -> None:
    """リクエスト実行とレスポンス時間測定（HTTP 200応答確認時点で記録）"""
    start_time = time.time()
    try:
        response = await client.get(endpoint)
    except APIClientError as e:
        logger.warning("request_failed", endpoint=endpoint, error=str(e))
        raise

    if response.status_code != 200:
        raise AssertionError(
            f"Unexpected status code for {endpoint}: expected 200, got {response.status_code}"
        )

    metrics.record_response_time(time.time() - start_time)  # status_code検証後に記録


class TestAPIPerformance:
    """APIパフォーマンステストクラス"""

    # パフォーマンス閾値設定
    RESPONSE_TIME_THRESHOLD = 2.0  # 2秒
    P95_THRESHOLD = 3.0  # 95パーセンタイル 3秒
    # 外部API依存のため保守的閾値設定
    # - 実測値: 4-5 req/s（ローカル環境、2025-12時点）
    # - TLS handshake・DNS解決等の初回接続コスト含む
    THROUGHPUT_THRESHOLD = 3  # 3 requests/sec

    def test_get_summary_empty_cpu_usage_uses_float_default(self):
        """cpu_usage が空の場合も end_percent は float 型で返す"""
        metrics = PerformanceMetrics()
        metrics.start_time = 1.0
        metrics.end_time = 2.0
        metrics.response_times.append(0.1)
        metrics.memory_usage.append(10.0)

        summary = metrics.get_summary()

        assert summary["cpu_usage"]["end_percent"] == 0.0
        assert isinstance(summary["cpu_usage"]["end_percent"], float)

    @pytest.mark.asyncio
    async def test_single_request_performance(self):
        """単一リクエストのパフォーマンステスト"""
        metrics = PerformanceMetrics()

        async with AsyncAPIClient() as client:
            metrics.start_monitoring()
            try:
                await _measure_request(client, "/posts/1", metrics)
            finally:
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
                # psutil の Process.cpu_percent() は初回呼び出しで artifact 値 (0.0) を返すため、
                # start サンプル値は信頼できない → None 固定で記録 (測定上のノイズ排除)。
                # CPU 実値が必要な箇所は test 後半の cpu_end_percent を参照する。
                cpu_start_percent=None,
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
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                # システム例外（CancelledError, KeyboardInterrupt等）は即再raise
                for r in results:
                    if isinstance(r, BaseException) and not isinstance(r, Exception):
                        raise r
                failures: list[BaseException] = [r for r in results if isinstance(r, BaseException)]
                if failures:
                    failure_summary = "\n".join(f"{type(e).__name__}: {e}" for e in failures)
                    raise AssertionError(
                        f"{len(failures)}/{len(tasks)} リクエスト失敗:\n{failure_summary}"
                    ) from failures[0]
            finally:
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
                # psutil の Process.cpu_percent() は初回呼び出しで artifact 値 (0.0) を返すため、
                # start サンプル値は信頼できない → None 固定で記録 (測定上のノイズ排除)。
                # CPU 実値が必要な箇所は test 後半の cpu_end_percent を参照する。
                cpu_start_percent=None,
                cpu_end_percent=round(summary["cpu_usage"]["end_percent"] or 0.0, 1),
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
            try:
                for batch in range(0, request_count, batch_size):
                    batch_tasks = []
                    for i in range(batch, min(batch + batch_size, request_count)):
                        endpoint = f"/posts/{(i % 100) + 1}"  # 1-100のランダムエンドポイント
                        batch_tasks.append(_measure_request(client, endpoint, metrics))

                    results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                    # システム例外（CancelledError, KeyboardInterrupt等）は即再raise
                    for r in results:
                        if isinstance(r, BaseException) and not isinstance(r, Exception):
                            raise r
                    failures: list[BaseException] = [
                        r for r in results if isinstance(r, BaseException)
                    ]
                    if failures:
                        failure_summary = "\n".join(f"{type(e).__name__}: {e}" for e in failures)
                        raise AssertionError(
                            f"{len(failures)}/{len(batch_tasks)} リクエスト失敗:\n{failure_summary}"
                        ) from failures[0]
                    await asyncio.sleep(0.1)  # バッチ間隔
            finally:
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
                # psutil の Process.cpu_percent() は初回呼び出しで artifact 値 (0.0) を返すため、
                # start サンプル値は信頼できない → None 固定で記録 (測定上のノイズ排除)。
                # CPU 実値が必要な箇所は test 後半の cpu_end_percent を参照する。
                cpu_start_percent=None,
                cpu_end_percent=round(summary["cpu_usage"]["end_percent"] or 0.0, 1),
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
                try:
                    # 各エンドポイントを5回テスト
                    for _ in range(5):
                        await _measure_request(client, endpoint, metrics)
                finally:
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
            try:
                # ベースラインテスト（10回実行）
                for _ in range(10):
                    await _measure_request(client, "/posts/1", metrics)
            finally:
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
                # psutil の Process.cpu_percent() は初回呼び出しで artifact 値 (0.0) を返すため、
                # start サンプル値は信頼できない → None 固定で記録 (測定上のノイズ排除)。
                # CPU 実値が必要な箇所は test 後半の cpu_end_percent を参照する。
                cpu_start_percent=None,
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
