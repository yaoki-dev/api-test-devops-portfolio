# Learning Offset Maps

6週プランファイルの部分読み込み最適化用オフセットマップ。

## 概要

週次マップ（W6_PLAN_WEEK_MAP）と日次マップ（W6_PLAN_DAY_MAP）を使用して、必要なセクションのみを効率的に読み込む。

## W6_PLAN_WEEK_MAP（週次マップ）

```python
W6_PLAN_FILE = "docs/main/6週プラン/6週プラン.md"

W6_PLAN_WEEK_MAP = {
    # 6週プラン向け週次Offset Map（2025-12-09実測値）
    # 使用方法: Read(file, offset=config["start"], limit=config["end"]-config["start"])
    1: {
        "start": 216,
        "end": 799,
        "days": "1-6",
        "hours": 48,
        "title": "Week 1: Python/httpx実践統合（48H、D1-D6）"
    },
    2: {
        "start": 799,
        "end": 1393,
        "days": "7-12",
        "hours": 48,
        "title": "Week 2: Error Handling深化 + Pydantic Settings（48H、D7-D12）"
    },
    3: {
        "start": 1393,
        "end": 1868,
        "days": "13-18",
        "hours": 46,
        "title": "Week 3: Docker基盤構築（46H、D13-D18）"
    },
    4: {
        "start": 1868,
        "end": 2397,
        "days": "19-24",
        "hours": 48,
        "title": "Week 4: CI/CD統合（48H、D19-D24）"
    },
    5: {
        "start": 2397,
        "end": 3267,
        "days": "25-30",
        "hours": 54,
        "title": "Week 5: 非同期処理深化（54H、D25-D30）"
    },
    5.5: {
        "start": 3267,
        "end": 3335,
        "days": "31-32",
        "hours": 14,
        "title": "Week 5.5: 統合復習（14H、D31-D32）"
    },
    6: {
        "start": 3335,
        "end": 4963,
        "days": "33-38",
        "hours": 48,
        "title": "Week 6: 最適化+応募準備（48H、D33-D38）"
    }
}

# 使用例:
# current_week = progress_state.yaml から取得
# config = W6_PLAN_WEEK_MAP[current_week]
# Read(W6_PLAN_FILE, offset=config["start"], limit=config["end"]-config["start"])
```

## W6_PLAN_DAY_MAP（日次マップ）

```python
W6_PLAN_DAY_MAP = {
    # 6週プラン向け日次Offset Map（全38日、2025-12-09実測値）
    # 使用方法: Read(file, offset=config["start"], limit=config["end"]-config["start"])

    # Week 1 (D1-D6): 8H/day
    1: {"start": 265, "end": 357, "week": 1, "hours": 8},
    2: {"start": 357, "end": 475, "week": 1, "hours": 8},
    3: {"start": 475, "end": 577, "week": 1, "hours": 8},
    4: {"start": 577, "end": 664, "week": 1, "hours": 8},
    5: {"start": 664, "end": 709, "week": 1, "hours": 8},
    6: {"start": 709, "end": 799, "week": 1, "hours": 8},

    # Week 2 (D7-D12): 8H/day
    7: {"start": 836, "end": 995, "week": 2, "hours": 8},
    8: {"start": 995, "end": 1109, "week": 2, "hours": 8},
    9: {"start": 1109, "end": 1196, "week": 2, "hours": 8},
    10: {"start": 1196, "end": 1284, "week": 2, "hours": 8},
    11: {"start": 1284, "end": 1345, "week": 2, "hours": 8},
    12: {"start": 1345, "end": 1393, "week": 2, "hours": 8},

    # Week 3 (D13-D18): 約7.7H/day (46H/6days)
    13: {"start": 1446, "end": 1496, "week": 3, "hours": 7.7},
    14: {"start": 1496, "end": 1548, "week": 3, "hours": 7.7},
    15: {"start": 1548, "end": 1603, "week": 3, "hours": 7.7},
    16: {"start": 1603, "end": 1717, "week": 3, "hours": 7.7},
    17: {"start": 1717, "end": 1783, "week": 3, "hours": 7.7},
    18: {"start": 1783, "end": 1868, "week": 3, "hours": 7.7},

    # Week 4 (D19-D24): 8H/day
    19: {"start": 1918, "end": 1986, "week": 4, "hours": 8},
    20: {"start": 1986, "end": 2058, "week": 4, "hours": 8},
    21: {"start": 2058, "end": 2130, "week": 4, "hours": 8},
    22: {"start": 2130, "end": 2203, "week": 4, "hours": 8},
    23: {"start": 2203, "end": 2307, "week": 4, "hours": 8},
    24: {"start": 2307, "end": 2397, "week": 4, "hours": 8},

    # Week 5 (D25-D30): 9H/day (54H/6days)
    25: {"start": 2449, "end": 2572, "week": 5, "hours": 9},
    26: {"start": 2572, "end": 2694, "week": 5, "hours": 9},
    27: {"start": 2694, "end": 2832, "week": 5, "hours": 9},
    28: {"start": 2832, "end": 2977, "week": 5, "hours": 9},
    29: {"start": 2977, "end": 3105, "week": 5, "hours": 9},
    30: {"start": 3105, "end": 3267, "week": 5, "hours": 9},

    # Week 5.5 (D31-D32): 7H/日統合復習（14H total）
    31: {"start": 3281, "end": 3302, "week": 5.5, "hours": 7},
    32: {"start": 3302, "end": 3335, "week": 5.5, "hours": 7},

    # Week 6 (D33-D38): 8H/day（48H total）
    33: {"start": 3434, "end": 3655, "week": 6, "hours": 8},
    34: {"start": 3655, "end": 3835, "week": 6, "hours": 8},
    35: {"start": 3835, "end": 4033, "week": 6, "hours": 8},
    36: {"start": 4033, "end": 4277, "week": 6, "hours": 8},
    37: {"start": 4277, "end": 4500, "week": 6, "hours": 8},
    38: {"start": 4500, "end": 4963, "week": 6, "hours": 8},
}

# 使用例:
# current_day = progress_state.yaml から取得
# config = W6_PLAN_DAY_MAP[current_day]
# Read(W6_PLAN_FILE, offset=config["start"], limit=config["end"]-config["start"])
```

## get_week_from_day_w6_plan()関数

```python
from typing import Union

def get_week_from_day_w6_plan(current_day: int) -> Union[int, float]:
    """
    Day番号（1-38）からWeek番号（1-6、またはfloat 5.5）を取得

    6週プラン用（Week 1-6 + 統合復習D31-D32）

    Args:
        current_day: 現在のDay番号（1-38の整数のみ）

    Returns:
        Week番号（1-6の整数、またはD31-D32の場合は5.5のfloat）

    Raises:
        TypeError: current_dayが整数でない場合
            Note: boolはintのサブクラスのため明示的にチェック（YAML injection対策）
        ValueError: current_dayが1未満または38超の場合

    Examples:
        # 境界値テスト（各週の開始・終了）
        >>> get_week_from_day_w6_plan(1)   # Day 1 → Week 1 (min)
        1
        >>> get_week_from_day_w6_plan(6)   # Day 6 → Week 1 (max)
        1
        >>> get_week_from_day_w6_plan(7)   # Day 7 → Week 2 (start)
        2
        >>> get_week_from_day_w6_plan(30)  # Day 30 → Week 5 (end)
        5
        >>> get_week_from_day_w6_plan(31)  # Day 31 → Week 5.5 (start)
        5.5
        >>> get_week_from_day_w6_plan(32)  # Day 32 → Week 5.5 (end)
        5.5
        >>> get_week_from_day_w6_plan(33)  # Day 33 → Week 6 (start)
        6
        >>> get_week_from_day_w6_plan(38)  # Day 38 → Week 6 (max)
        6

        # 追加カバレッジ（Week 3/4）
        >>> get_week_from_day_w6_plan(15)  # Day 15 → Week 3
        3
        >>> get_week_from_day_w6_plan(20)  # Day 20 → Week 4
        4

        # エラーケース（ValueError）
        >>> get_week_from_day_w6_plan(0)
        Traceback (most recent call last):
        ...
        ValueError: current_day must be 1-38, got 0

        >>> get_week_from_day_w6_plan(39)
        Traceback (most recent call last):
        ...
        ValueError: current_day must be 1-38, got 39

        # エラーケース（TypeError）
        >>> get_week_from_day_w6_plan("5")
        Traceback (most recent call last):
        ...
        TypeError: current_day must be int, got str
    """
    # Type validation (see Raises docstring for rationale)
    if isinstance(current_day, bool) or not isinstance(current_day, int):
        raise TypeError(f"current_day must be int, got {type(current_day).__name__}")

    # Range validation: 6週プランは1-38日のみ有効
    if not 1 <= current_day <= 38:
        raise ValueError(f"current_day must be 1-38, got {current_day}")

    # Week boundaries: W1(1-6), W2(7-12), W3(13-18), W4(19-24), W5(25-30), W5.5(31-32), W6(33-38)
    if current_day <= 6:
        return 1
    elif current_day <= 12:
        return 2
    elif current_day <= 18:
        return 3
    elif current_day <= 24:
        return 4
    elif current_day <= 30:
        return 5
    elif current_day <= 32:  # D31-D32 → Week 5.5
        return 5.5
    else:  # 33-38
        return 6

# 使用例:
# current_day = progress_state.yaml から取得
# current_week = get_week_from_day_w6_plan(current_day)
# week_config = W6_PLAN_WEEK_MAP[current_week]
# day_config = W6_PLAN_DAY_MAP[current_day]
# Read(W6_PLAN_FILE, offset=day_config["start"], limit=day_config["end"]-day_config["start"])
```
