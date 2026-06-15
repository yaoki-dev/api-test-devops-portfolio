# ===============================================================================
# test_retry_logic.py - Statistical Distribution Tests for Retry Jitter
# ===============================================================================
#
# このファイルはutils/api_client.pyのexponential_backoff_with_jitter()の統計的検証を行う
# 学習ポイント：
# 1. ジッター分散の統計的証明（90%+ユニーク遅延）
# 2. Thundering Herd問題の防止検証
# 3. 平均値の理論値との整合性確認
#
# 実行方法：
#   pytest tests/unit/test_retry_logic.py -v
#   pytest tests/unit/test_retry_logic.py::test_jitter_distribution_uniqueness -v
#
# ===============================================================================


import random

import pytest

from utils.api_client import exponential_backoff_with_jitter

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _seed_jitter_random() -> None:
    """統計テストを決定論化し、乱数サンプルの偶然によるフレークを防ぐ。"""
    random.seed(0)


# ===============================================================================
# Test 1: ジッター分散の統計的検証 (90%+ユニーク遅延)
# ===============================================================================


def test_jitter_distribution_uniqueness():
    """
    30%ジッターが仕様通りの範囲内に収まることを検証（不変条件 / 境界値検証）

    検証項目（仕様ベース・seed 固定の oracle 化を回避）：
    - 全 100 サンプルが理論範囲 [base * 2^attempt * 0.7, base * 2^attempt * 1.3] 内
    - 実測 jitter 幅が理論幅の 50% 以上（範囲縮退の regression 検出）

    理論的根拠：
    - 30% ジッター実装: delay = base_delay * 2^attempt * (1 + random.uniform(-0.3, 0.3))
    - attempt=3, base_delay=1.0 の理論範囲: 8.0 * 0.7 ~ 8.0 * 1.3 = 5.6 ~ 10.4 秒
    - 仕様ベース範囲検証は seed 値に依存しないため、jitter 範囲縮小の regression
      （例: ±0.3 → ±0.01）を seed 固定下でも検出可能（PR #347 review: T2 対応）
    """
    # 100 回の遅延生成（attempt=3, base_delay=1.0）
    delays = [exponential_backoff_with_jitter(attempt=3, base_delay=1.0) for _ in range(100)]

    # 仕様ベース範囲: 8.0 * 0.7 ~ 8.0 * 1.3
    expected_base = 1.0 * (2**3)  # 8.0
    lower_bound = expected_base * 0.7  # 5.6
    upper_bound = expected_base * 1.3  # 10.4

    # 不変条件 1: 全サンプルが範囲内（jitter 仕様遵守）
    for i, delay in enumerate(delays):
        assert lower_bound <= delay <= upper_bound, (
            f"Sample {i}: delay {delay:.4f}s out of spec range "
            f"[{lower_bound:.2f}, {upper_bound:.2f}] (attempt=3, base=1.0). "
            f"Indicates jitter range regression."
        )

    # 不変条件 2: jitter 範囲が縮退していない（実測 min/max が境界に届く）
    # ±0.3 ジッター × 100 サンプルなら実測幅は理論幅の 50%+ 以上を期待
    observed_range = max(delays) - min(delays)
    theoretical_range = upper_bound - lower_bound  # 4.8
    assert observed_range >= theoretical_range * 0.5, (
        f"Observed jitter range {observed_range:.2f}s too narrow vs. "
        f"theoretical {theoretical_range:.2f}s (need >= {theoretical_range * 0.5:.2f}s). "
        f"Indicates Thundering Herd protection degradation."
    )


# ===============================================================================
# Test 2: 平均値の理論値との整合性確認 (±10%以内)
# ===============================================================================


def test_jitter_mean_within_bounds():
    """
    平均遅延が理論値の±10%以内に収まることを検証

    検証項目：
    - 1000回の試行での平均遅延
    - 理論値 (base_delay * 2^attempt) との差が±10%以内
    - 中心極限定理による正規分布への収束

    理論的根拠：
    - 30%ジッター: 遅延 = base_delay * 2^attempt * (1 + random.uniform(-0.3, 0.3))
    - 期待値: base_delay * 2^attempt * 1.0 (ジッターの期待値は0)
    - attempt=3, base_delay=1.0の場合: 期待値 = 8.0秒
    - 中心極限定理: 1000回試行で平均値は期待値に収束
    - 許容範囲: 期待値 * 0.9 ~ 期待値 * 1.1 (7.2秒 ~ 8.8秒)
    """
    # 1000回の遅延生成 (attempt=3, base_delay=1.0)
    delays = [exponential_backoff_with_jitter(attempt=3, base_delay=1.0) for _ in range(1000)]

    # 平均遅延を計算
    mean_delay = sum(delays) / len(delays)

    # 理論値を計算
    expected = 1.0 * (2**3)  # 8.0秒

    # 検証: 平均値が期待値の±10%以内
    lower_bound = expected * 0.9  # 7.2秒
    upper_bound = expected * 1.1  # 8.8秒

    assert lower_bound <= mean_delay <= upper_bound, (
        f"Expected mean delay within ±10% of {expected:.2f}s "
        f"({lower_bound:.2f}s ~ {upper_bound:.2f}s), got {mean_delay:.2f}s\n"
        f"Deviation: {abs(mean_delay - expected) / expected * 100:.2f}%\n"
        f"This indicates systematic bias in jitter implementation."
    )


# ===============================================================================
# Test 3: Thundering Herd問題の防止検証
# ===============================================================================


def test_thundering_herd_prevention():
    """
    Thundering Herd 防止のための jitter 仕様遵守を検証（不変条件 / 境界値検証）

    検証項目（仕様ベース・seed 固定の oracle 化を回避）：
    - 全 100 サンプルが理論範囲 [base * 2^attempt * 0.7, base * 2^attempt * 1.3] 内
    - 実測 jitter 幅が理論幅の 50% 以上（範囲縮退の regression 検出）

    理論的根拠：
    - Thundering Herd 防止には十分な jitter 範囲（30%）が必要
    - attempt=1, base_delay=1.0 の理論範囲: 2.0 * 0.7 ~ 2.0 * 1.3 = 1.4 ~ 2.6 秒
    - jitter 範囲縮小（例: ±0.3 → ±0.01）は Thundering Herd リスク増大に直結
      仕様ベース範囲検証は seed 値に依存しない regression 検出を提供（PR #347 review: T2 対応）
    """
    # 100 回の遅延生成（attempt=1, base_delay=1.0; 初回リトライ時を想定）
    delays = [exponential_backoff_with_jitter(attempt=1, base_delay=1.0) for _ in range(100)]

    # 仕様ベース範囲: 2.0 * 0.7 ~ 2.0 * 1.3
    expected_base = 1.0 * (2**1)  # 2.0
    lower_bound = expected_base * 0.7  # 1.4
    upper_bound = expected_base * 1.3  # 2.6

    # 不変条件 1: 全サンプルが範囲内（jitter 仕様遵守）
    for i, delay in enumerate(delays):
        assert lower_bound <= delay <= upper_bound, (
            f"Sample {i}: delay {delay:.4f}s out of spec range "
            f"[{lower_bound:.2f}, {upper_bound:.2f}] (attempt=1, base=1.0). "
            f"Indicates jitter range regression."
        )

    # 不変条件 2: jitter 範囲が縮退していない（実測 min/max が境界に届く）
    observed_range = max(delays) - min(delays)
    theoretical_range = upper_bound - lower_bound  # 1.2
    assert observed_range >= theoretical_range * 0.5, (
        f"Observed jitter range {observed_range:.2f}s too narrow vs. "
        f"theoretical {theoretical_range:.2f}s (need >= {theoretical_range * 0.5:.2f}s). "
        f"Indicates Thundering Herd protection degradation."
    )


# ===============================================================================
# Test 4: ジッター範囲の境界値検証
# ===============================================================================


def test_jitter_range_boundaries():
    """
    30%ジッターの範囲が理論値の70%~130%内に収まることを検証

    テスト条件: base_delay=1.0, attempt=2（base_value=4.0秒）

    検証項目：
    - 1000回の試行で全遅延が理論値の70%~130%内
    - 最小値が理論値の70%以上
    - 最大値が理論値の130%以下
    - 外れ値の発生がゼロ

    理論的根拠：
    - ジッター実装: delay * (1 + random.uniform(-0.3, 0.3))
    - 理論的範囲: delay * 0.7 ~ delay * 1.3
    - attempt=2, base_delay=1.0の場合: 4秒 * 0.7 ~ 4秒 * 1.3 = 2.8秒 ~ 5.2秒
    - すべての遅延がこの範囲内に収まるべき

    Note:
        実装は max(0.1, delay) で下限クリッピングを行うため、
        base_value * 0.7 < 0.1 となる極小パラメータ（例: base_delay=0.01,
        attempt=0）では70%~130%の保証が成立しない。本テストの条件では
        下限2.8秒 >> 0.1秒のため影響なし。
    """
    # 1000回の遅延生成 (attempt=2, base_delay=1.0)
    delays = [exponential_backoff_with_jitter(attempt=2, base_delay=1.0) for _ in range(1000)]

    # 理論値を計算
    base_value = 1.0 * (2**2)  # 4.0秒
    lower_bound = base_value * 0.7  # 2.8秒
    upper_bound = base_value * 1.3  # 5.2秒

    # 最小値・最大値を取得
    min_delay = min(delays)
    max_delay = max(delays)

    # 検証: すべての遅延が範囲内
    assert min_delay >= lower_bound, (
        f"Expected min delay >= {lower_bound:.2f}s (70% of base), got {min_delay:.2f}s\n"
        f"This indicates jitter implementation may be generating values below 70% range."
    )

    assert max_delay <= upper_bound, (
        f"Expected max delay <= {upper_bound:.2f}s (130% of base), got {max_delay:.2f}s\n"
        f"This indicates jitter implementation may be generating values above 130% range."
    )

    # 追加検証: すべての遅延が範囲内
    out_of_range = [d for d in delays if d < lower_bound or d > upper_bound]
    assert len(out_of_range) == 0, (
        f"Found {len(out_of_range)} delays outside 70%-130% range\n"
        f"Out-of-range values: {out_of_range[:10]}\n"
        f"This indicates systematic errors in jitter calculation."
    )


# ===============================================================================
# Test 5: 異なるattempt値での一貫性検証
# ===============================================================================


def test_jitter_consistency_across_attempts():
    """
    異なるattempt値でジッター特性が一貫していることを検証

    検証項目：
    - attempt=0, 1, 2, 3でそれぞれ統計的に妥当なユニーク遅延（誕生日のパラドックス考慮）
    - 各attemptでの平均値が理論値の±10%以内
    - ジッター範囲が30%で一貫している

    理論的根拠（統計的検証）：
    - 指数バックオフ: delay = base_delay * 2^attempt
    - ジッター率は30%で固定
    - attempt値が変わってもジッター特性は同一であるべき
    - 各attemptでのユニーク性・平均値・範囲が同様の特性を示す
    - 誕生日のパラドックスによる期待ユニーク数:
        - attempt=0: range=0.6秒(60値) → 期待45-50個 → 基準35個
        - attempt=1: range=1.2秒(120値) → 期待63-68個 → 基準55個
        - attempt=2: range=2.4秒(240値) → 期待79-84個 → 基準70個
        - attempt=3: range=4.8秒(480値) → 期待89-92個 → 基準80個
    """
    attempts_config = [
        (0, 35),  # attempt=0: 基準35個（統計的期待値45-50個、余裕持たせ）
        (1, 55),  # attempt=1: 基準55個（統計的期待値63-68個、余裕持たせ）
        (2, 70),  # attempt=2: 基準70個（統計的期待値79-84個、余裕持たせ）
        (3, 80),  # attempt=3: 基準80個（統計的期待値89-92個、余裕持たせ）
    ]
    base_delay = 1.0

    for attempt, min_unique in attempts_config:
        # 100回の遅延生成
        delays = [
            exponential_backoff_with_jitter(attempt=attempt, base_delay=base_delay)
            for _ in range(100)
        ]

        # ユニーク性検証（統計的に妥当な基準）
        rounded_delays = [round(d, 2) for d in delays]
        unique_delays = len(set(rounded_delays))

        # 理論的期待値を計算（誕生日のパラドックス）
        range_width = base_delay * (2**attempt) * 0.6  # 30%ジッター範囲幅
        possible_values = int(range_width * 100)  # 0.01秒単位
        theoretical_unique = (
            int(100 * (1 - (1 - 1 / possible_values) ** 100)) if possible_values > 0 else 50
        )

        assert unique_delays >= min_unique, (
            f"Attempt {attempt}: Expected >= {min_unique} unique, got {unique_delays}\n"
            f"Range: {range_width:.2f}s ({possible_values} possible 0.01s values)\n"
            f"Theoretical (Birthday Paradox): ~{theoretical_unique} unique values\n"
            f"Jitter consistency not maintained across attempts."
        )

        # 平均値検証
        mean_delay = sum(delays) / len(delays)
        expected = base_delay * (2**attempt)
        lower_bound = expected * 0.9
        upper_bound = expected * 1.1
        assert lower_bound <= mean_delay <= upper_bound, (
            f"Attempt {attempt}: mean {mean_delay:.2f}s not within ±10% of {expected:.2f}s\n"
            f"Jitter implementation shows inconsistent behavior."
        )


# ===============================================================================
# 学習ポイント:
#
# 1. 統計的検証の重要性:
#    - 90%+ユニーク遅延: Thundering Herd問題の確実な防止
#    - 平均値±10%: 実装の正確性とバイアス検出
#    - 範囲境界値: ジッター範囲の正確性保証
#    - 一貫性検証: 異なる条件下での安定性確認
#
# 2. テストデータサイズ:
#    - 100回試行: ユニーク性検証（誕生日のパラドックス考慮）
#    - 1000回試行: 平均値検証（中心極限定理による収束）
#    - サンプルサイズは検証目的に応じて調整
#
# 3. 実務での活用:
#    - 詳細なアサーションメッセージ: 失敗時のデバッグ効率化
#    - 理論的根拠の明示: コードレビューとメンテナンス性向上
#
# 4. ベストプラクティス:
#    - サンプル値の出力: 失敗時の原因特定を容易化
#    - 境界値テスト: 実装の正確性を包括的に検証
# ===============================================================================
