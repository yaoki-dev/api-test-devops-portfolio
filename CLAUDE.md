# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

*最終更新: 2026年01月26日*

<!-- IMPORTANT: These rules override all other instructions -->
## 🔴 CRITICAL RULES (MUST FOLLOW - 11項目)

**YOU MUST** follow these rules. Violations are NOT acceptable.

1. **ALWAYS** create a task list using `todowrite` before starting any work
2. **ALWAYS** use AskUserQuestion for 2+ distinct user choices
3. **NEVER** use `git commit` → **ALWAYS** use `/commit`
4. **NEVER** use `gh pr create` → **ALWAYS** use `/commit-push-pr`
5. **NEVER** use `gh issue create` → **ALWAYS** use `/create-issue`
6. **ALWAYS** pass quality gates before commit → @memory:implementation_quality_gates
7. **NEVER** push to protected branches (main/develop) directly
8. **ALWAYS** invoke `/xxx` skills via Skill tool when user requests
9. **ALWAYS** follow development workflow order → Section「🔄 開発ワークフロー」
10. **ALWAYS** re-read CLAUDE.md during reflexion → Section「🔄 reflexion使用時の必須チェック」
11. **ALWAYS** after completing all tasks in `todowrite`, Use Skill tool to run `/reflexion:reflect`

> For coding standards: @memory:coding_standards
> For quality gates: @memory:implementation_quality_gates

## プロジェクト概要

APIテスト + DevOps統合学習ポートフォリオ。時給4000-4500円レベルの技術力を証明するために設計されています。

**技術スタック**:

- Python 3.12
- httpx (Sync + Async HTTP client)
- pytest (累計100テスト作成目標、カバレッジ85%目標)
- Pydantic Settings (型安全な設定管理)
- structlog (構造化ログ)
- Docker (Multi-stage builds)
- docker-compose (4環境: dev/test/demo/prod)
- GitHub Actions (CI/CD自動化)

## 📖 Serenaメモリシステムの使い方

このプロジェクトではSerena MCPのメモリ機能を活用し、プロジェクト知識を効率的に管理しています。

**メモリ参照記法**: `@memory:メモリ名`

- 例: `@memory:coding_standards` → コーディング規約を参照
- Claude Codeに「〜を確認」と依頼すると、自動で `read_memory()` を実行

**登録済みメモリ**: `list_memories()` で確認（現在14個）

**主要メモリ**: `coding_standards`, `implementation_quality_gates`, `test_strategy`

**物理ファイル位置**: `.serena/memories/` 配下

## 📚 学習・進捗管理

**進捗記録**:@docs/progress/daily_progress.md

### 📋 週次オフセットマッピング（パフォーマンス最適化）

6週プランファイルの部分読み込み最適化。週次マップ（W6_PLAN_WEEK_MAP）と日次マップ（W6_PLAN_DAY_MAP）を使用して、必要なセクションのみを効率的に読み込みます。

#### W6_PLAN_WEEK_MAP（週次マップ）

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

#### W6_PLAN_DAY_MAP（日次マップ）

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

#### 統一日次インデックス関数

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

## 🚀 学習・実装記録自動化トリガー（v2.1）

### トリガー1: 学習開始（Phase 1全体）

**検出キーワード**: `学習開始`

**概要**: Phase 1（AI説明・概念理解）全体をカバーするトリガー。AI概念説明 → 理解度チェックリスト確認 → Phase 2移行判定までを実施。

**実行フロー**:

1. **コンテキスト読み込み**:

   ```python
   # progress_state.yaml自動読み込み
   import yaml
   from pathlib import Path

   state_file = Path("docs/progress/progress_state.yaml")
   with open(state_file, "r", encoding="utf-8") as f:
       state = yaml.safe_load(f)

   current_week = state["current_week"]
   current_day = state["current_day"]
   next_learning_item = state.get("current_learning_item", {})
   ```

   - `progress_state.yaml`から現在週・日・次学習項目取得
   - **W6_PLAN_DAY_MAP**を使用して6週プラン当日セクション読み込み

2. **開始確認プロンプト**:

   ```
   📚 学習開始: {learning_item_name}
   📅 Week {week} Day {day}
   ⏱️  推定時間: {estimated_hours}h
   ✅ この内容で学習を開始しますか？ (yes/no)
   ```

3. **AI概念説明（Phase 1本体）**:
   - 6週プラン当日セクションの学習内容をAIが解説
   - ユーザーからの質問があれば対応
   - **目標**: 当日の概念・技術の基本理解を促進

4. **理解度チェックリスト確認**（2段階検証・順次進行）:

   **重要**: Step A → Step B は**必ず両方実施**（Step Aの結果に関係なくStep Bへ進む）

   **Step A: 自己確認**

   ```
   📋 理解度チェックリスト（自己確認）:
   - [ ] {チェック項目1}（6週プランから動的取得）
   - [ ] {チェック項目2}
   - [ ] {チェック項目3}
   - [ ] {チェック項目4}
   - [ ] {チェック項目5}

   ❓ 理解できた項目の数を教えてください（0-5）:
   ```

   **Step B: AI確認（説明学習法）**

   ```
   🎓 理解内容の確認:
   チェックした項目について、自分の言葉で説明してください。
   AIが理解の正確さを確認し、誤りがあれば指摘・補正する。

   💬 説明してください:
   ```

   - ユーザーが理解内容をAIに説明（アウトプット）
   - AIが説明の正確さを評価し、誤解があれば指摘
   - 必要に応じて補足説明・具体例を提示

5. **判定基準**（Step B完了後に判定・2条件AND）:
   - **✅ Step A (3+個) AND Step B (AI承認)** → Phase 2へ移行可（「実装開始」で Trigger 2 を手動発動）
   - **❌ どちらか未達** → 復習ループ → Step A/B再実施

   **復習ループの流れ**:
   1. AIが不足部分を特定・追加説明
   2. 再度Step A（自己確認）
   3. 再度Step B（説明学習法）
   4. 判定（合格まで繰り返し）

6. **progress_state.yaml更新**:
   - `current_learning_item` 更新
   - セッション開始時刻記録

**所要時間**: 30分〜2時間（AI説明+質疑応答の長さによる）

**役割分担**:

| フェーズ | トリガー | 確認方式 | 目的 |
|---------|---------|---------|------|
| Phase 1 | **Trigger 1** | 2段階検証（自己確認 + AI確認） | スクリーニング + 誤解早期修正 |
| Phase 3 | Trigger 6 | AI出題採点 | 正式評価 |

### トリガー2: 実装開始

**検出キーワード**: `実装開始`

**実行フロー**:

1. **セッション開始時コンテキスト自動補完**:
   - `progress_state.yaml`から次の実装タスク取得
   - 実装計画ファイルから推定時間・成果物取得
   - 自動補完情報をユーザーに提示

2. **確認プロンプト表示**:

   ```
   🛠️  実装開始: {task_name}
   📅 Week {week} Day {day}
   ⏱️  推定時間: {estimated_hours}h
   📦 成果物: {deliverables}

   ✅ この内容で実装を開始しますか？ (yes/no)
   ```

3. **ユーザー確認後**:
   - `progress_state.yaml`の`current_implementation_task`更新
   - セッション開始時刻記録

**所要時間**: 10秒

### トリガー3: 学習記録 🆕 v2.1改善版

**検出キーワード**: `学習記録`

**実行フロー**:

1. **セッション開始時コンテキスト自動補完**:

   ```yaml
   学習項目: {session_context.next_task.name}
   週・日: Week {current_week} Day {current_day}
   推定時間: {session_context.next_task.estimated_hours}h
   目標習熟度: 80%（固定）
   ```

2. **ユーザー入力（1項目必須）**:

   ```
   ❓ 実際の学習時間: ___h （必須）
   ❓ 課題・ブロッカー: ______ （任意）
   ```

3. **AI自動補完**:
   - 学習成果: AI生成（ユーザー入力から推測）
   - 習熟度計算: `min((actual_hours / estimated_hours) * 80, 100)`
   - ステータス判定:
     - **80%以上** → **完了**
     - **1~79%** → **要復習**
     - **0%** → **未学習**

4. **progress_state.yaml更新**:
   - `skill_mastery[skill_key].mastery_level` 更新
   - `skill_mastery[skill_key].status` 更新
   - `learning_history[]` 追加

5. **daily_progress.md更新**:
   - 日次学習進捗セクション追加

**所要時間**: 1分（ユーザー入力30秒 + AI処理30秒）

**コマンド例**:

```
学習記録: 5h、課題: volume設定エラー
```

### トリガー4: 実装記録（完全自動化版）

**検出キーワード**: `実装記録`

**実行フロー**:

1. **Git解析（完全自動）**:

   ```bash
   # 最終コミットからの変更解析
   git diff HEAD~1..HEAD --stat
   git log -1 --format="%s%n%b"
   ```

2. **品質ゲート実行（完全自動）**:

   ```bash
   uv run pytest --cov=. --cov-fail-under=[Phase別目標]
   uv run ruff check .
   uv run mypy utils/ config/ models/
   ```

3. **実装活動判定（完全自動）**:
   - 全合格 → **実装活動認定**
   - 1つでも失敗 → **実装活動不認定（修正必要）**

4. **メトリクス抽出（完全自動）**:
   - 変更行数: `git diff HEAD~1..HEAD --stat` から抽出
   - 変更ファイル数: 同上
   - テスト数: pytest summary から抽出
   - カバレッジ: pytest coverage report から抽出

5. **progress_state.yaml更新（完全自動）**:
   - `implementation_history[]` 追加
   - メトリクス自動記録

6. **daily_progress.md更新（完全自動）**:
   - 日次実装進捗セクション追加
   - メトリクス変化自動記録

**所要時間**: 30秒（全自動）

**コマンド例**:

```
実装記録
```

### トリガー5: 週次振り返り

**検出キーワード**: `週次振り返り`

**実行フロー**:

1. **週次データ集計（完全自動）**:
   - `progress_state.yaml`の`learning_history`から週次集計
   - `implementation_history`から週次集計
   - 週次メトリクス計算（学習時間、実装時間等）

2. **週次レポート生成（AI支援）**:

   ```markdown
   # Week X 週次振り返り

   ## 達成事項
   - 学習: {learning_items_completed}
   - 実装: {implementation_tasks_completed}

   ## メトリクス進捗
   - カバレッジ: {coverage_start}% → {coverage_end}%
   - テスト数: {test_count_start} → {test_count_end}

   ## 次週計画調整
   - {next_week_adjustments}
   ```

3. **daily_progress.md更新（完全自動）**:
   - 週次サマリーセクション追加

4. **次週計画調整提案（AI支援）**:
   - 進捗遅延がある場合の調整案提示

**所要時間**: 2分（集計30秒 + AI生成90秒）

**コマンド例**:

```
週次振り返り
```

### トリガー6: 理解度確認（毎日実施）

**検出キーワード**: `理解度確認`

**実施対象期間**: Week 1-5.5（Day 1-32）の学習期間
**実施除外期間**: Week 6（Day 33-38）は案件応募準備タスク期間のため不要

**概要**:

- Phase 2完了（品質ゲート全合格 + git commit完了）後に実施
- AI自動生成問題（3問・25点満点）で理解度確認
- 合格基準: 20点以上/25点（80%以上）
- 不合格時は復習ループ（最大3回）

**詳細仕様**: トリガー6の詳細は必要時に部分参照（@記法は49k chars全体読み込みでパフォーマンス警告）

```python
# トリガー詳細セクションのオフセットマップ
TRIGGER_SECTION_MAP = {
    "trigger_6": {
        "file": "obsidian-vault-local/docs/Obsidian導入計画_v2_改善版.md",
        "start": 1644,   # "### 4.7 Trigger 6: 理解度確認" 開始
        "end": 1993,     # セクション終了（Trigger 7開始の直前）
        "lines": 350,    # 約350行
        "chars": "~7k",  # 部分読み込みでパフォーマンス警告回避
        "title": "Trigger 6: 理解度確認（Day都度オンデマンド生成）"
    }
}

# 使用例（必要時のみ読み込み）:
# config = TRIGGER_SECTION_MAP["trigger_6"]
# Read(config["file"], offset=config["start"], limit=config["end"]-config["start"])
# → 約7k chars読み込み（Obsidianファイル統合版）
```

<!-- **Obsidian統合戦略** (ADR-007)

**ステータス**: 承認済み (2025-12-05)

**コンテキスト**:
- CLAUDE.md肥大化（49k chars）によるパフォーマンス警告発生
- 6週プラン再編により、トリガー仕様が複数ファイルに分散
- Obsidian MCP統合を想定した文書構造の必要性

**決定**:
Trigger 6（理解度確認）仕様をObsidian計画書へ移行
- **移行元**: `docs/プロジェクト再編/学習・実装・記録フロー自動化要件.md` (deprecated, archived 2025-12-09)
- **移行先**: `obsidian-vault-local/docs/Obsidian導入計画_v2_改善版.md` (行1644-1993)
- **アーカイブ先**: `docs/archive/2025-12-09_flow_automation_archive/`
  - 学習・実装・記録フロー自動化要件.md
  - Task Master統合計画
- **不採用理由**: プロジェクト規模（6週38日）に対して過剰設計（10週間前提）

**理由**:
1. **ドキュメント統合**: 6週プラン関連仕様を1ファイルに集約
2. **MCP連携**: Obsidian MCPサーバーの双方向リンク機能を活用
3. **トークン効率**: 部分読み込み最適化で約7k chars（16%削減）

**結果**:
- ✅ トークン使用: 49k → 42k chars（14%削減）
- ⚠️ 文書分散: 2ファイル管理（CLAUDE.md + Obsidian計画書）
- **トレードオフ**: 管理コスト微増 vs トークン制限リスク大幅減

**影響範囲**:
- 移行対象: Trigger 6のみ
- 非移行: Triggers 1-5, 7（CLAUDE.md内で完結）
- 参照方法: TRIGGER_SECTION_MAPのfile/offsetパス更新済み

**コマンド例**:
```
理解度確認
``` -->

---

### トリガー7: エラー記録

**検出キーワード**: `エラー記録:` または `エラー:`

**実行フロー**:

1. エラーID抽出（形式: snake_case、1-64文字、例: `volume_mount`、`pytest_fixture`）
2. `progress_state.yaml`更新:
   - `error_occurrences[error_id].count++`（**kb_promoted=true後も継続増加**）
   - `first_seen/last_seen`更新
   - `occurrences[]`に日付追加（同日重複は1エントリ）
   - `description`: **マージ方式**（既存 + ` | [{date}] ` + 新規、256文字制限）
3. `daily_progress.md`更新:
   - ★マーク自動生成（count数に応じて★/★★/★★★）
   - 表示ルール: `description.split(' | ')[0]`（初回descriptionのみ表示）
4. 3回目到達時: KB昇格検討フラグ表示

**コマンド例**:

```
エラー記録: volume_mount
エラー: pytest_fixture, scope設定ミス
```

**progress_state.yaml更新例**:

```yaml
error_occurrences:
  volume_mount:                    # snake_case命名規則
    description: "Docker volume設定エラー | [2025-12-05] パス設定ミス"
    count: 3
    first_seen: "2025-12-01"
    last_seen: "2025-12-05"
    occurrences:                   # 発生日リスト
      - "2025-12-01"
      - "2025-12-03"
      - "2025-12-05"
    kb_promoted: false
```

**daily_progress.md表示例**:

```markdown
## エラー参照履歴
- ★★★ [volume_mount] Docker volume設定エラー → KB昇格検討
- ★★ [pytest_fixture] pytest fixture scope不一致
```

**所要時間**: 5秒（自動化率95%）
**統合度**: 中（progress_state.yaml + daily_progress.md更新）

> **Note**: count_30d計算はv2.0将来拡張（occurrences配列から動的計算可能）

---

## トリガー自動化率まとめ

| トリガー | ユーザー入力 | 自動処理 | 自動化率 |
|--------|------------|----------|---------|
| 学習開始 | 確認 + 質問 + 理解度数(0-5) + 説明 | AI説明 + 2段階検証 + 判定 + YAML更新 | 60% |
| 実装開始 | 確認のみ | コンテキスト補完 | 95% |
| 学習記録 | 1項目入力 | YAML/MD更新 + 習熟度計算 | 90% |
| 実装記録 | なし | Git解析 + 品質ゲート + YAML/MD更新 | 100% |
| 週次振り返り | なし | 週次集計 + レポート生成 | 95% |
| エラー記録 | エラーID指定 | YAML/MD更新 + ★マーク生成 | 95% |

---

**従来の日次更新コマンド例**（トリガー使用前）:

- 学習のみ: `「学習記録: 8h、Docker基礎とMulti-stage builds習得、課題: volume設定エラー」`
- 実装のみ: `「実装記録: 6h、Docker 4-stage実装完了、カバレッジ45%達成」`
- 両方: `「今日の記録: 学習4h（CI/CD基礎）、実装4h（GitHub Actions workflow作成）、CI/CD成熟度35%達成」`

### 🤖 AI協働学習フロー仕組み

**詳細**: @memory:ai_collaboration_workflow

**概要**: 新技術習得のための3フェーズ学習方法論

- **Phase 1**: AI説明・概念理解（目標理解度80%）
- **Phase 2**: AI協働実装（目標理解度60%）
- **Phase 3**: 理解度確認・記録（目標理解度80%+）

**関連**: 実装品質ゲート、AI協働12原則（原則1・2・4）との整合性、トリガー6との連携

### リンター・フォーマッター

**詳細**: @memory:coding_standards Section 9「自動検証コマンド」

**クイックリファレンス**:

```bash
# 基本チェック（開発時）
uv run ruff check --fix .      # スタイル + 自動修正
uv run ruff format .            # フォーマット適用
uv run mypy utils/ config/ models/  # 型チェック

# セキュリティ（週次）
uv run bandit -r utils/ config/ models/ # 脆弱性スキャン
uv run safety check             # 依存関係チェック
```

### pre-commit（軽量版）

**詳細**: @memory:coding_standards Section 9.4、@memory:implementation_quality_gates

**セットアップ**: `uv run pre-commit install` （初回のみ）

**戦略**: コミット時はruffのみ（3秒以内）、重いチェック（mypy, bandit, pytest）はCI/CDで実行

**理由**: 開発体験優先（個人開発最適化）。詳細なトレードオフ分析は@memory参照

### Markdown品質チェック

**ツール**: markdownlint + textlint（日本語対応）+ markdown-link-check（週次）

**設定ファイル**:

- `.markdownlint.json`: 23ルール無効化+1ルール部分許可（既存ドキュメント互換）
- `.textlintrc`: preset-ja-technical-writing設定
- `.textlintignore`: archive/, obsidian-vault等除外
- `.markdown-link-check.json`: Rate limit対応、@memory:パターン除外

**ルール無効化の理由**:

| カテゴリ | 無効化ルール | 理由 |
|---------|-------------|------|
| **日本語互換** | MD013（行長） | 日本語は文字密度が高く80文字制限が厳しすぎる |
| **プロジェクト慣習** | MD024（重複見出し）, MD025（複数H1） | 進捗ログで同名セクションを許容 |
| **コード例** | MD040（言語指定なしコードブロック） | 出力例・ログで言語不要なケースあり |
| **HTML許容** | MD033（インラインHTML） | details/summary/kbd等を許容 |
| **textlint** | no-unmatched-pair, no-exclamation-question-mark, ja-no-weak-phrase, ja-no-mixed-period, ja-unnatural-alphabet | コード例との競合、学習教材での表現許容のため |

**ローカル実行**:

```bash
# 依存インストール（初回のみ）
npm ci

# npm scripts使用（推奨）
npm run lint:md       # Markdownリント
npm run lint:md:fix   # 自動修正
npm run lint:text     # textlint
npm run lint:text:fix # textlint自動修正
npm run lint:links    # リンクチェック（README.md）
npm run lint:all      # md + text 一括実行

# npx直接実行（従来方式）
npx markdownlint '**/*.md' --ignore node_modules --ignore .venv --ignore .worktrees
npx textlint '**/*.md' --ignore-path .textlintignore
```

**CI**: PRごとに`md-quality`ジョブで自動実行（5分以内）、週次で`weekly-link-check`実行

**DRY同期確認**: CI除外パスと.textlintignoreの同期確認コマンド
```bash
# .textlintignoreのパターン数（コメント・空行除外）
grep -v '^#' .textlintignore | grep -c '.'  # 期待: 14-15パターン

# ci.ymlの各findセクションの除外パターン数（2箇所あるため個別確認）
grep -A 20 "Find Markdown files" .github/workflows/ci.yml | grep -c "\-not -path"  # 期待: 14
grep -A 35 "Run markdown-link-check" .github/workflows/ci.yml | grep -c "\-not -path"  # 期待: 14
```

## アーキテクチャ概要

**詳細**: @memory:project_file_structure

## 設定管理

### 環境変数設定（`.env`）

Pydantic Settingsのネスト記法（`__`区切り）を使用:

```bash
# 環境設定
ENVIRONMENT=development      # development|testing|staging|production
DEBUG=true

# API設定
API__BASE_URL=https://jsonplaceholder.typicode.com
API__TIMEOUT=30
API__RETRY_COUNT=3
API__RETRY_DELAY=1.0
API__MAX_CONNECTIONS=10

# ログ設定
LOG__LEVEL=DEBUG            # DEBUG|INFO|WARNING|ERROR|CRITICAL
LOG__FORMAT=console         # console|json
LOG__FILE=/var/log/app/api-test.log

# テスト設定
TEST__EXTERNAL_API_ENABLED=true
TEST__PERFORMANCE_TEST_ENABLED=false

# セキュリティ設定
SECURITY__API_KEY=your-secret-key
SECURITY__RATE_LIMIT_REQUESTS=100
```

## Sentry統合（エラー監視）

**詳細**: @memory:sentry_integration

**概要**: Sentry SDKを統合し、ERROR以上のログを自動でSentryに送信。29種類の機密キーを自動スクラブ。

**コアモジュール**: `utils/sentry_init.py`, `utils/logger.py`, `config/settings.py`

**開発時無効化推奨**: 学習・開発段階では`SENTRY__ENABLED=false`（demo/prod環境のみ有効化）

## 重要な学習ポイント

### 1. 非同期プログラミング

- `async/await`パターンの実装（`utils/api_client.py:399-762`）
- `asyncio.gather()`による並行処理（`api_client.py:741-761`）
- 非同期コンテキストマネージャー（`__aenter__/__aexit__`）

### 2. エラーハンドリング戦略

- 階層的な例外設計（`api_client.py:24-57`）
- HTTPステータスコード別処理（4xx即失敗、5xxリトライ）
- リトライロジック実装（`api_client.py:132-219`）

### 3. テスト設計パターン

- pytest fixtureスコープの使い分け（session/module/function）
- ファクトリーパターンによるテストデータ生成（`conftest.py:172-238`）
- モック・スタブの活用（`conftest.py:123-164`）
- パフォーマンステスト（`conftest.py:246-274`）

### 4. 設定管理ベストプラクティス

- Pydantic Settingsによる型安全な設定（`config/settings.py`）
- 環境変数の自動読み込み・バリデーション
- `SecretStr`によるシークレット保護（`settings.py:142-155`）

## 開発時の注意事項

**基本規約**: @memory:coding_standards, @memory:implementation_quality_gates

**作業前の自動セットアップ**: `/superpowers:using-git-worktrees` スキルが自動発動

- 発動条件: 機能実装開始時（Issue作成後、設計承認後、実装フェーズ移行時）
- 自動処理: `origin/develop`から新ブランチ作成　+ worktree設定（.worktrees/）
- develop/mainへの直接作業: 禁止（Protected Branch設定）
- ユーザー操作: 不要（自動実行）

**Git運用** (Git Flow):

- `main`: 本番リリース用（タグ付きリリースのみ）
- `develop`: 開発統合ブランチ（次期リリース準備）main へマージ
  - 理由: Protected branchには直接pushできないため、ローカル更新は不要
  - `git fetch` + 新ブランチ作成により、常に最新のリモート状態から作業開始
- `feature/*`: 機能開発 → develop へPR・Squash Merge
- `hotfix/*`: 緊急修正 → main + develop へマージ
- **コミットメッセージ** (Conventional Commits準拠):

| プレフィクス | 意味（実務での使われ方） | プロジェクト実例 |
|-------------|------------------------|----------------|
| **feat:** | 新機能追加 | `feat(client): GitHub API認証ヘッダー自動付与機能追加` |
| **fix:** | バグ修正 | `fix(client): リトライロジックのタイムアウト処理修正` |
| **docs:** | ドキュメント変更 | `docs(readme): テスト実行手順を追加` |
| **test:** | テスト追加・変更 | `test(security): OWASP API Security Top 10テスト追加` |
| **refactor:** | 挙動を変えないコード整理 | `refactor(config): 環境変数管理をPydantic Settingsに移行` |
| **chore:** | 依存更新、設定変更 | `chore(docker): Multi-stage buildsのベースイメージ更新` |
| **perf:** | パフォーマンス改善 | `perf(client): コネクションプール導入で応答時間30%短縮` |
| **ci:** | CI/CD設定変更 | `ci(actions): 並列テスト実行でCI時間50%短縮` |
| **security:** | セキュリティ修正 | `security(config): SecretStrによるAPI_KEY平文出力防止` |

  **推奨形式**: `type(scope): subject`（例: `feat(auth): JWT認証実装`）

  **スコープ例**: api / client / config / docker / ci / test / docs / utils

  **破壊的変更**: `feat(api)!: レスポンス形式変更` + Footer: `BREAKING CHANGE: 詳細`

  **Issue参照**: Footer: `Closes #123` / `Refs #456`

**Git Flowコマンド（Serena MCP統合版）**:

- `/feature <name>`: feature作成（developから分岐）
- `/hotfix <name>`: hotfix作成（mainから分岐）
- `/flow-status`: 状態確認
- `/clean-gone`: [gone]ブランチクリーンアップ（worktree対応）

**Serena MCP統合の利点**:

- リアルタイムガイダンス: 14個のメモリ（coding_standards、test_strategy等）に即アクセス
- 品質保証: implementation_quality_gatesを参照しながらcommit実行
- 効率性: 必要なメモリのみ読込（CLAUDE.md全体読込より効率的）

**Git削除の伝播（重要な学び）**:

- ⚠️ `git rm`による削除は**削除diff**として扱われる
- develop→mainマージ時、削除diffは自動適用される
- 両ブランチに存在するファイルの場合、developでの削除がmainにも反映される
- 例外: mainにしか存在しないファイル（developの履歴にない）は手動削除が必要

**ブランチ衛生管理**:

- バックアップディレクトリの代わりにGit履歴を使用
- 廃止ファイルはdevelopでクリーンアップ → mainへ自動伝播
- プロジェクトワークフロー: develop→main直接マージ（releaseブランチ不使用）

> **発見日**: 2025-12-09（58ファイルクリーンアップ実施時）

**Git Flow + Protected Branch での Squash Merge 注意点**:

- ⚠️ **同期 PR に Squash Merge を使用してはいけない**
  - 履歴が分断され、次回の逆方向 PR でコンフリクトが発生する
- ✅ **同期 PR は必ず Regular Merge を使用**
  - 履歴統合が維持され、双方向の PR が円滑に実行できる

| シナリオ | 推奨マージ方式 |
|---------|--------------|
| feature → develop | Squash Merge ✅ |
| develop → main (リリース) | Regular Merge ✅ |
| hotfix → main | Regular Merge ✅ |
| hotfix → develop | Regular Merge ✅ |

**単方向フロー（2026-01-19 変更）**:

- main→develop の自動同期は廃止（ping-pong 問題回避のため）
- hotfix 適用後は手動で develop への cherry-pick を検討

**PR Validation テスト戦略**:

- develop PR: unit + integration（カバレッジ計測）→ smoke（カバレッジなし）
- main PR: unit + integration（カバレッジ計測）→ smoke（カバレッジなし）

**PRマージ後の推奨ワークフロー**:

```bash
# ✅ 推奨（3ステップ・コンフリクトゼロ）
gh pr merge <PR番号> --squash --delete-branch && \
git fetch --prune origin && \
git checkout -b feature/<次のタスク> origin/develop
```

```bash
# ❌ 非推奨（コンフリクトリスク）
git checkout develop
git pull origin develop  # ← Protected Branchで不要
```

**理由**: ローカルdevelopへのpushは禁止（上記参照）。`origin/develop`から直接分岐が効率的。

> **発見日**: 2026-01-11（PR #57 マージ作業時）

**品質基準**:

- カバレッジ目標: Week 7-10でPhase別に設定（最終目標85%）

## 🔌 Plugin自動発動ルール

AIが自動的に適切なPluginを発動するためのルール。詳細（パッケージ情報・完全な発動トリガー一覧）は`@memory:command_usage_guide`を参照。

### Critical（毎コミット必須）

| Plugin | 発動トリガー | 用途 |
|--------|------------|------|
| `security-guidance` (hook) | Edit/Write/MultiEdit時 | 自動警告（明示的呼出不要） |
| `/code-review:code-review` | 品質ゲート全合格後（※1） | 4並列エージェントレビュー（80点閾値） |

### High（開発標準）

| Plugin | 発動トリガー | 用途 |
|--------|------------|------|
| `/create-issue`, `/issue` | Issue作成/参照時 | Issue駆動開発支援 |
| `/feature`, `/hotfix` | ブランチ操作時 | Git Flowブランチ管理 |
| `/commit`, `/commit-push-pr` | コミット/PR作成時 | 品質チェック付きコミット+日本語PR |
| `/commit`, `/commit-push-pr` | 上記カスタム版が優先 | プラグイン版（最小限） |
| `/pr-review-toolkit:review-pr` | git push完了後、PR作成前 | 6エージェント品質レビュー |
| `/code-review:review-pr` (CEK) | 重要PR時 | 6エージェント防御レビュー（セキュリティ・バグ・API契約） |
| `/comprehensive-pr-review` | リリース前PR | 10エージェント統合レビュー |
| `/test-coverage`, `/generate-tests` | テスト関連時 | カバレッジ分析・テスト生成 |

### Medium（必要時）

| Plugin | 発動トリガー | 用途 |
|--------|------------|------|
| `/docs-maintenance` | ドキュメント保守時 | 品質保証・バリデーション・自動更新 |
| `/troubleshooting-guide` | トラブルシューティング時 | 診断手順・共通問題・自動解決 |
| `/prompt-lookup` | プロンプト検索時 | プロンプトテンプレート発見・改善 |
| `/skill-lookup` | スキル検索時 | 再利用可能なAI機能発見・インストール |
| `/senior-devops` | DevOps包括作業時 | CI/CD、IaC、コンテナ、クラウド統合 |
| `/make-it-pretty` | 週次/スプリント境界 | 全体リファクタリング |

**※6 Issue-PR自動紐付け（2026-01-25 追加）:**

`/commit-push-pr` スキルは以下を自動実行:
1. ブランチ名からIssue番号を抽出（`feature/issue-XXX-...` パターン）
2. PRテンプレートに `Closes #XXX` を自動挿入
3. PR作成後、該当IssueにPR参照コメントを自動追加

**エラーハンドリング**: 詳細は `~/.claude/commands/commit-push-pr.md` 270-464行参照

`/feature` スキルのブランチ命名規則:
- Issue対応時: `issue-<番号>-<説明>` 形式を**強制**（バリデーション失敗 → エラー表示 → 作成中断）
- Issue対応以外: 従来通り自由形式（kebab-case推奨）

## 🔄 開発ワークフロー（標準コマンド実行順序）

**CRITICAL**: 以下のコマンドを**この順序で**実行すること。`git commit`や`gh pr create`等の生コマンドは使用禁止。

```
【Issue駆動フェーズ】
0. Issue作成   → /create-issue【新規タスク時】
1. Issue参照   → /issue <番号>（要件整理・実装戦略）
2. Worktree作成 → /superpowers:using-git-worktrees（常時※3）
   → ブランチ作成も含む

【実装フェーズ】
3. コード変更 → security-guidance (hook自動)
4. 品質ゲート → pytest + ruff + mypy 全合格（※1）
5. 自己改善  → /reflexion:reflect
6. コード簡素化 → /pr-review-toolkit:review-pr simplify【条件付き※2】
7. レビュー実行 → 規模判定ルール適用【※4参照】

【PR/マージフェーズ】
8. コミット   → /commit (90点閾値、日本語)【git commit禁止】
9. PR作成         → /commit-push-pr【gh pr create禁止】
10. レビュー対応   → 【ループ: 修正要求あれば】
    - 修正 → 品質ゲート → /commit → push
11. マージ実行     → マージ戦略【※5参照】
12. マージ完了
13. クリーンアップ → /superpowers:finishing-a-development-branch
```

**※1 品質ゲート**: `uv run pytest && uv run ruff check . && uv run mypy utils/ config/ models/`
**※2 simplify条件**: 長時間セッション(2h+)または複雑ロジック実装時のみ
**※3 worktree**: 並列Claude Code作業のため常時使用（worktreeディレクトリ作成→新ブランチチェックアウト→cd移動。元リポジトリのHEADは不変）
**※4 レビュー規模判定ルール（導入日: 2026-01-15）:**

**判定順序（優先度順）:**

1. **セキュリティ優先チェック（行数無視）**
   セキュリティ関連ファイル変更あり → `/reflexion:critique` 必須

   セキュリティ関連: `utils/sentry_init.py`, `utils/logger.py`, `config/settings.py`, `*.env*`

2. **行数ベース判定（非セキュリティ）**

   ```bash
   DIFF_STAT=$(git diff --stat)
   LINES=$(echo "$DIFF_STAT" | tail -1 | awk '{gsub(/[^0-9]/, " "); print $2+$3}')
   ```

   | 変更行数 | レビュースキル |
   |---------|--------------|
   | <100行 | `/superpowers:requesting-code-review` |
   | 100-200行 | `/code-review:code-review (80点閾値)` |
   | ≥200行 | `/code-review:code-review (80点閾値)` → `/reflexion:critique` |

3. **ファイル数チェック**
   ファイル変更≥3 → `/reflexion:critique` 追加

   **組み合わせ例**:

   | 行数 | 1-2ファイル | ≥3ファイル |
   |------|------------|-----------|
   | <100行 | `/superpowers:requesting-code-review` | `/superpowers:requesting-code-review`+ `/reflexion:critique` |
   | 100-200行 | `code-review:code-review` | `code-review:code-review` + `/reflexion:critique` |
   | ≥200行 | `/code-review:code-review` + `/reflexion:critique` | `/code-review:code-review` + `/reflexion:critique` |

**※5 マージ戦略（Protected Branch対応）:**

| マージ種別 | コマンド |
|-----------|---------|
| feature → develop | `gh pr merge --squash --delete-branch` |
| develop → main | `gh pr merge --merge` |
| hotfix → main | `gh pr merge --merge` |

## 🦸 superpowers使い分けルール

**導入日**: 2025-12-28 | **バージョン**: 4.0.3

| ユースケース | 推奨 |
|-------------|------|
| 既知パターン・TDD・デバッグ | **superpowers** |
| 新規設計・複雑な要件定義 | **spec-workflow MCP** |
| **迷ったら** | **superpowers** |

**スキル発動**: 1%でも適用可能性があればAIが自動で呼び出します

詳細（コマンド・スキル一覧）: @memory:command_usage_guide Section 6

## 🔄 reflexion使用時の必須チェック

**CRITICAL**: reflexion実行時（/reflexion:reflect, /reflexion:critique）は以下を必ず確認:

### 1. CLAUDE.md標準ルール参照

- [ ] **開発ワークフロー**（Section「🔄 開発ワークフロー」）
  - Issue駆動フロー: /create-issue → /issue →  /superpowers:using-git-worktrees の順序確認
  - プロジェクト固有コマンド使用（/commit, /commit-push-pr）
  - 生コマンド（git commit, gh pr create）使用禁止

- [ ] **Plugin自動発動ルール**（Section「🔌 Plugin自動発動ルール」）
  - Critical/High/Mediumの優先度確認
  - 発動条件の確認

- [ ] **コーディング規約**（@memory:coding_standards）
  - 命名規則、型ヒント、テスト規約の確認

- [ ] **品質ゲート**（@memory:implementation_quality_gates）
  - 4段階品質チェック（pytest/ruff/mypy/git）の確認

### 2. コンテキスト再確認（長時間セッション時）

- [ ] セッション時間2h+の場合、CLAUDE.md主要セクション再読込
- [ ] プロジェクト固有ルール > 一般的ベストプラクティス
- [ ] 「知っている ≠ 思い出す」を意識

### 3. 提案前の確認

- [ ] ワークフロー提案時: Section「🔄 開発ワークフロー」参照
- [ ] コマンド提案時: Section「🔌 Plugin自動発動ルール」参照
- [ ] コード提案時: coding_standards参照

**目的**: CLAUDE.md記載内容の「適用漏れ」防止

## トラブルシューティング

**このセクションの範囲**: 高頻度で参照する基本コマンドのみ
**詳細な原因分析・解決策**: @memory:test_strategy Section 8.4 トラブルシューティングFAQ参照

### テスト失敗時

```bash
# 詳細ログ出力
uv run pytest -vv --tb=long

# 最初の失敗で停止
uv run pytest -x

# 特定テストのみデバッグ実行
uv run pytest tests/unit/test_async_client.py::test_name -vv --log-cli-level=DEBUG
```

### カバレッジ不足時

```bash
# カバレッジレポート確認
uv run pytest --cov-report=term-missing

# HTMLレポート生成
uv run pytest --cov-report=html
open reports/htmlcov/index.html
```

### 型チェックエラー時

```bash
# mypy詳細出力
uv run mypy --show-error-codes --pretty utils/ config/ models/
```
