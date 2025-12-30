# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

*最終更新: 2025年12月10日*

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

**登録済みメモリ一覧**（13個）:
- `ai_collaboration_workflow`: AI協働学習フロー（3フェーズ学習方法論）
- `coding_standards`: コーディング規約（命名規則、型ヒント、テスト規約）
- `implementation_quality_gates`: 実装品質ゲート（4段階品質チェック）
- `project_file_structure`: プロジェクト構造（コアモジュール、設計パターン）
- `sentry_integration`: Sentry統合ガイド（29種類の機密キースクラブ）
- `test_strategy`: テスト戦略（単体/結合/性能/セキュリティテスト）
- `workflow_playbooks_guide`: ワークフロープレイブック（14種類の実装パターン）
- `command_usage_guide`: コマンド使用ガイド（ccplugins vs SuperClaude）
- その他: `list_memories()` で全リスト確認可能

**物理ファイル位置**: `.serena/memories/` 配下
- 参照は `@memory:` 記法推奨（ディレクトリ変更に強い）
- 直接読む場合: `Read(".serena/memories/[カテゴリ]/[メモリ名].md")`

**将来**:メモリ数が30個を超えた時点で、カテゴリ別索引を検討

## 📚 学習・進捗管理

@docs/progress/daily_progress.md **CLAUDE.m保持**

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
**CLAUDE.md保持 281-547行**

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
   AIが理解の正確さを確認し、誤りがあれば指摘・補正します。

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
   uv run mypy utils/ config/
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

**統合度**: ★★☆（progress_state.yaml + daily_progress.md更新）

> **Note**: count_30d計算はv2.0将来拡張（occurrences配列から動的計算可能）

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
**統合度**: ★★☆（progress_state.yaml + daily_progress.md更新）

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
uv run mypy utils/ config/      # 型チェック

# セキュリティ（週次）
uv run bandit -r utils/ config/ # 脆弱性スキャン
uv run safety check             # 依存関係チェック
```

### pre-commit（軽量版）

**詳細**: @memory:coding_standards Section 9.4、@memory:implementation_quality_gates

**セットアップ**: `uv run pre-commit install` （初回のみ）

**戦略**: コミット時はruffのみ（3秒以内）、重いチェック（mypy, bandit, pytest）はCI/CDで実行

**理由**: 開発体験優先（個人開発最適化）。詳細なトレードオフ分析は@memory参照

## アーキテクチャ概要

**詳細**: @memory:project_file_structure

**概要**: コアモジュール構成と設計パターン
- **コアモジュール**: `utils/api_client.py`、`config/settings.py`
- **設計パターン**: エラーハンドリング階層、リトライロジック（4xx即失敗/5xxリトライ）、非同期処理（async/await）
- **テスト構成**: pytest共通フィクスチャ（conftest.py）、4種類のテスト（unit/integration/performance/security）

**関連**: project_architecture.md（全体設計）、coding_standards.md（実装規約）

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

### 設定アクセス方法

```python
from config.settings import settings

# API設定
base_url = settings.api.base_url
timeout = settings.api.timeout

# 環境判定
if settings.is_development():
    # 開発環境固有の処理
    pass
```

## Sentry統合（エラー監視）

**詳細**: @memory:sentry_integration

**概要**: Sentry SDKを統合し、ERROR以上のログを自動でSentryに送信。29種類の機密キーを自動スクラブ。

**コアモジュール**: `utils/sentry_init.py`, `utils/logger.py`, `config/settings.py`

**開発時無効化推奨**: 学習・開発段階では`SENTRY__ENABLED=false`（demo/prod環境のみ有効化）

## 重要な学習ポイント
**CLAUDE.md 保持 654-676**

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

**Git運用** (Git Flow):
- `main`: 本番リリース用（タグ付きリリースのみ）
- `develop`: 開発統合ブランチ（次期リリース準備）main へマージ
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

  **スコープ例**: api, client, config, docker, ci, test, docs, utils

  **破壊的変更**: `feat(api)!: レスポンス形式変更` + Footer: `BREAKING CHANGE: 詳細`

  **Issue参照**: Footer: `Closes #123` / `Refs #456`

**Git Flowコマンド**:
- `/git-workflow:feature <name>`: feature作成（developから分岐）
- `/git-workflow:hotfix <name>`: hotfix作成（mainから分岐）
- `/git-workflow:finish`: ブランチ完了・マージ
- `/git-workflow:flow-status`: 状態確認

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
| `/git-workflow:feature`, `/git-workflow:hotfix`, `/git-workflow:finish` | ブランチ操作時 | Git Flowブランチ管理 |
| `/commit-commands:commit`, `/commit-commands:commit-push-pr` | コミット/PR作成時 | ステージング+コミット+PR |
| `/pr-review-toolkit:review-pr` | git push完了後、PR作成前 | 6エージェント品質レビュー |
| `/code-review:review-pr` (CEK) | 重要PR時 | 6エージェント防御レビュー（セキュリティ・バグ・API契約） |
| `/comprehensive-pr-review` | リリース前PR | 10エージェント統合レビュー |
| `/testing-suite:test-coverage`, `/testing-suite:generate-tests` | テスト関連時 | カバレッジ分析・テスト生成 |

### Medium（必要時）
| Plugin | 発動トリガー | 用途 |
|--------|------------|------|
| `/documentation-generator:update-docs` | ドキュメント更新時 | 一括同期・バッジ自動生成 |
| `/security-pro:security-audit`, `/security-pro:dependency-audit` | 週次/リリース前 | セキュリティ・依存関係監査 |
| `/performance-optimizer:performance-audit` | パフォーマンス懸念時 | ボトルネック特定・最適化 |

### Low（特定場面）
| Plugin | 発動トリガー | 用途 |
|--------|------------|------|
| `ai-ml-toolkit` | AI/ML機能実装時のみ | LLM/RAG/MLパイプライン支援 |

### 標準フロー（自動発動順序）

```
1. コード変更 → security-guidance (hook自動)
2. 品質ゲート → pytest + ruff + mypy 全合格（※1）
3. 自己改善  → /reflexion:reflect
4. 日常レビュー → /code-review:code-review (80点閾値)
5. コミット   → /commit-commands:commit
6. PR時      → /pr-review-toolkit:review-pr (品質) + /code-review:review-pr (防御)
7. 重要PR時  → /comprehensive-pr-review (10エージェント統合)
8. PR作成    → /commit-commands:commit-push-pr
```

**※1 品質ゲート**: `uv run pytest && uv run ruff check . && uv run mypy utils/ config/`

## 🦸 superpowers使い分けルール

**導入日**: 2025-12-28 | **バージョン**: 4.0.3

| ユースケース | 推奨 |
|-------------|------|
| 既知パターン・TDD・デバッグ | **superpowers** |
| 新規設計・複雑な要件定義 | **spec-workflow** |
| **迷ったら** | **superpowers** |

**スキル発動**: 1%でも適用可能性があればAIが自動で呼び出します

詳細（コマンド・スキル一覧）: @memory:command_usage_guide Section 6

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
uv run mypy --show-error-codes --pretty utils/ config/
```

