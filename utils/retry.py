"""Retry and backoff helpers for API clients."""

import random
from typing import cast


def exponential_backoff_with_jitter(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter_percent: float = 0.3,
) -> float:
    """指数バックオフ + 30%ジッター計算

    Args:
        attempt: 現在のリトライ回数（0始まり）
        base_delay: 基本遅延時間（秒）
        max_delay: 最大遅延時間（秒）
        jitter_percent: ジッター率（デフォルト30%）

    Returns:
        計算された遅延時間（秒、最小0.1秒）

    """
    # 指数バックオフ計算
    delay = min(base_delay * (2**attempt), max_delay)
    # ±30%のジッター追加（リトライ間隔用、暗号用途ではない）
    jitter = delay * jitter_percent
    delay = delay + random.uniform(-jitter, jitter)  # noqa: S311
    # 最小値保証
    return cast(float, max(0.1, delay))
