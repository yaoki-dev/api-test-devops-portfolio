# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

*最終更新: 2025年10月07日*

## プロジェクト概要

APIテスト + DevOps統合学習ポートフォリオ。時給4000-4500円レベルの技術力を証明するために設計されています。

**技術スタック**:
- Python 3.12
- httpx (Sync + Async HTTP client)
- pytest (累計100テスト作成、カバレッジ85%)
- Pydantic Settings (型安全な設定管理)
- structlog (構造化ログ)
- Docker (Multi-stage builds)
- docker-compose (4環境: dev/test/demo/prod)
- GitHub Actions (CI/CD自動化)

## 📚 学習・進捗管理

@docs/progress/daily_progress.md

### 📋 週次オフセットマッピング（パフォーマンス最適化）

大きな学習計画ファイル（40.9k文字）とポートフォリオ戦略ファイル（48k文字）を丸ごと読み込むとパフォーマンス警告が発生するため、Read toolの`offset`/`limit`パラメータを使った部分読み込みを実施します。

#### LEARNING_PLAN_WEEK_MAP

```python
LEARNING_PLAN_WEEK_MAP = {
    # ※ start/end行番号は学習プラン最終確認後に更新予定（Phase 2分離完了後）
    1: {
        "start": "TBD",  # 最終確認後更新
        "end": "TBD",
        "weeks": [1],
        "days": "1-6",
        "hours": 45,
        "title": "Week 1: Python + httpx Core"
    },
    2: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [2],
        "days": "7-12",
        "hours": 45,
        "title": "Week 2: Async基礎"
    },
    3: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [3],
        "days": "13-18",
        "hours": 45,
        "title": "Week 3: Async/Await深化"
    },
    4: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [4],
        "days": "19-24",
        "hours": 45,
        "title": "Week 4: Error Handling深化"
    },
    5: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [5],
        "days": "25-30",
        "hours": 45,
        "title": "Week 5: pytest + Pydantic Settings"
    },
    6: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [6],
        "days": "31-36",
        "hours": 45,
        "title": "Week 6: 統合復習 + 自律チャレンジ"
    },
    7: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [7],
        "days": "37-42",
        "hours": 42,
        "title": "Week 7: Docker基盤構築"
    },
    8: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [8],
        "days": "43-48",
        "hours": 42,
        "title": "Week 8: CI/CD統合"
    },
    9: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [9],
        "days": "49-54",
        "hours": 42,
        "title": "Week 9: ポートフォリオ最適化"
    },
    10: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [10],
        "days": "55-60",
        "hours": 42,
        "title": "Week 10: 応募準備 + 初回応募"
    }
}

LEARNING_PLAN_FILE = "docs/プロジェクト再編/10週ハイブリッドプラン_日次詳細学習スケジュール.md"

# 使用例:
# current_week = learning_state.yaml から取得
# week_key = "1-2" if current_week in [1, 2] else str(current_week)
# config = LEARNING_PLAN_WEEK_MAP[week_key]
# Read(LEARNING_PLAN_FILE, offset=config["start"], limit=config["end"]-config["start"])
```

#### PORTFOLIO_STRATEGY_WEEK_MAP

```python
PORTFOLIO_STRATEGY_FILE = "docs/プロジェクト再編/ポートフォリオ戦略分析.md"

PORTFOLIO_STRATEGY_WEEK_MAP = {
    # ※ start/end行番号は学習プラン最終確認後に更新予定（Phase 2分離完了後）
    1: {
        "start": "TBD",  # 最終確認後更新
        "end": "TBD",
        "weeks": [1],
        "days": "1-6",
        "hours": 30,
        "title": "Week 1: Python + httpx Core"
    },
    2: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [2],
        "days": "7-12",
        "hours": 30,
        "title": "Week 2: Async基礎"
    },
    3: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [3],
        "days": "13-18",
        "hours": 30,
        "title": "Week 3: Async/Await深化"
    },
    4: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [4],
        "days": "19-24",
        "hours": 30,
        "title": "Week 4: Error Handling深化"
    },
    5: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [5],
        "days": "25-30",
        "hours": 30,
        "title": "Week 5: pytest + Pydantic Settings"
    },
    6: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [6],
        "days": "31-36",
        "hours": 30,
        "title": "Week 6: 統合復習 + 自律チャレンジ"
    },
    7: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [7],
        "days": "37-42",
        "hours": 50,
        "title": "Week 7: Docker基盤構築"
    },
    8: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [8],
        "days": "43-48",
        "hours": 60,
        "title": "Week 8: CI/CD統合"
    },
    9: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [9],
        "days": "49-54",
        "hours": 60,
        "title": "Week 9: ポートフォリオ最適化"
    },
    10: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [10],
        "days": "55-60",
        "hours": 60,
        "title": "Week 10: 応募準備 + 初回応募"
    }
}

# 使用例:
# current_week = learning_state.yaml から取得
# config = PORTFOLIO_STRATEGY_WEEK_MAP[current_week]
# Read(PORTFOLIO_STRATEGY_FILE, offset=config["start"], limit=config["end"]-config["start"])
```

#### 統一日次インデックス（Day → Week変換）

```python
def get_week_from_day(current_day: int) -> int:
    """
    Day番号（1-60）からWeek番号（1-10）を取得

    Args:
        current_day: 現在のDay番号（1-60）

    Returns:
        Week番号（1-10の整数）

    Example:
        >>> get_week_from_day(5)   # Day 5 → Week 1
        1
        >>> get_week_from_day(43)  # Day 43 → Week 8
        8
    """
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
    elif current_day <= 36:
        return 6
    elif current_day <= 42:
        return 7
    elif current_day <= 48:
        return 8
    elif current_day <= 54:
        return 9
    else:
        return 10

# 使用例: learning_state.yamlのcurrent_dayから両方のファイルを部分読み込み
# current_day = 43  # learning_state.yamlから取得
# current_week = get_week_from_day(current_day)
#
# # 学習プラン部分読み込み
# learning_config = LEARNING_PLAN_WEEK_MAP[current_week]
# Read(LEARNING_PLAN_FILE, offset=learning_config["start"],
#      limit=learning_config["end"]-learning_config["start"])
#
# # ポートフォリオ戦略部分読み込み
# portfolio_config = PORTFOLIO_STRATEGY_WEEK_MAP[current_week]
# Read(PORTFOLIO_STRATEGY_FILE, offset=portfolio_config["start"],
#      limit=portfolio_config["end"]-portfolio_config["start"])
```

**パフォーマンス改善効果**:
- フルインポート: 62k tokens消費
- 週次部分読み込み: 2-3k tokens消費（95%削減）
- CLAUDE.mdサイズ: +40行のみ（vs. 日次マッピング+126行）

## 🚀 学習・実装記録自動化トリガー（v2.1）

### トリガー1: 学習開始

**検出キーワード**: `学習開始`

**実行フロー**:
1. **セッション開始時コンテキスト自動補完**:
   ```python
   # learning_state.yaml自動読み込み（セッション開始時）
   import yaml
   from pathlib import Path

   # YAMLファイル読み込み
   state_file = Path("docs/progress/learning_state.yaml")
   with open(state_file, "r", encoding="utf-8") as f:
       state = yaml.safe_load(f)

   # 状態取得
   current_week = state["current_week"]
   current_day = state["current_day"]
   next_learning_item = state.get("current_learning_item", {})
   skill_mastery = state.get("skill_mastery", {})
   ```

   - `learning_state.yaml`から現在週・日・次学習項目取得
   - 学習計画ファイルから推定時間・目標習熟度取得（週次マップ使用）
   - 自動補完情報をユーザーに提示

2. **確認プロンプト表示**:
   ```
   📚 学習開始: {learning_item_name}
   📅 Week {week} Day {day}
   ⏱️  推定時間: {estimated_hours}h
   🎯 目標習熟度: 85%（固定）

   ✅ この内容で学習を開始しますか？ (yes/no)
   ```

3. **ユーザー確認後**:
   - `learning_state.yaml`の`current_learning_item`更新
   - セッション開始時刻記録

**所要時間**: 10秒

---

### トリガー2: 実装開始

**検出キーワード**: `実装開始`

**実行フロー**:
1. **セッション開始時コンテキスト自動補完**:
   - `learning_state.yaml`から次の実装タスク取得
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
   - `learning_state.yaml`の`current_implementation_task`更新
   - セッション開始時刻記録

**所要時間**: 10秒

---

### トリガー3: 学習記録 🆕 v2.1改善版

**検出キーワード**: `学習記録`

**実行フロー**:

1. **セッション開始時コンテキスト自動補完**:
   ```yaml
   学習項目: {session_context.next_task.name}
   週・日: Week {current_week} Day {current_day}
   推定時間: {session_context.next_task.estimated_hours}h
   目標習熟度: 85%（固定）
   ```

2. **ユーザー入力（1項目必須）**:
   ```
   ❓ 実際の学習時間: ___h （必須）
   ❓ 課題・ブロッカー: ______ （任意）
   ```

3. **AI自動補完**:
   - 学習成果: AI生成（ユーザー入力から推測）
   - 習熟度計算: `(actual_hours / estimated_hours) * 85`
   - ステータス判定:
     - **85%以上** → **完了**
     - **1~84%** → **要復習**
     - **0%** → **未学習**

4. **learning_state.yaml更新**:
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

---

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

5. **learning_state.yaml更新（完全自動）**:
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

---

### トリガー5: 週次振り返り

**検出キーワード**: `週次振り返り`

**実行フロー**:

1. **週次データ集計（完全自動）**:
   - `learning_state.yaml`の`learning_history`から週次集計
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

---

### トリガー6: 理解度確認（毎日実施）

**検出キーワード**: `理解度確認`

**実施対象期間**: Week 1-7（Day 1-42）の学習期間
**実施除外期間**: Week 8-9（Day 43-54）は案件応募準備タスク期間のため不要

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
        "file": "docs/プロジェクト再編/学習・実装・記録フロー自動化要件.md",
        "start": 695,    # "#### トリガー6: 理解度確認" 開始
        "end": 1094,     # セクション終了（次の---の直前）
        "lines": 400,    # 約400行
        "chars": "~8k",  # 全体49k charsの16%
        "title": "トリガー6: 理解度確認（Day都度オンデマンド生成）"
    }
}

# 使用例（必要時のみ読み込み）:
# config = TRIGGER_SECTION_MAP["trigger_6"]
# Read(config["file"], offset=config["start"], limit=config["end"]-config["start"])
# → 約8k chars読み込み（84%削減、パフォーマンス警告回避）
```

**コマンド例**:
```
理解度確認
```

---

## トリガー自動化率まとめ

| トリガー | ユーザー入力 | 自動処理 | 自動化率 |
|--------|------------|----------|---------|
| 学習開始 | 確認のみ | コンテキスト補完 | 95% |
| 実装開始 | 確認のみ | コンテキスト補完 | 95% |
| 学習記録 | 1項目入力 | YAML/MD更新 + 習熟度計算 | 90% |
| 実装記録 | なし | Git解析 + 品質ゲート + YAML/MD更新 | 100% |
| 週次振り返り | なし | 週次集計 + レポート生成 | 95% |

---

**従来の日次更新コマンド例**（トリガー使用前）:
- 学習のみ: `「学習記録: 8h、Docker基礎とMulti-stage builds習得、課題: volume設定エラー」`
- 実装のみ: `「実装記録: 6h、Docker 4-stage実装完了、カバレッジ45%達成」`
- 両方: `「今日の記録: 学習4h（CI/CD基礎）、実装4h（GitHub Actions workflow作成）、CI/CD成熟度35%達成」`

### 🤖 AI協働学習フロー仕組み

#### 新技術習得標準フロー

##### Phase 1: AI説明・概念理解（目標理解度30%）

**Step 1: AI説明依頼**

依頼テンプレート:
```
[技術名]について、以下の観点で説明してください:
1. 何のための技術か（Why）
2. いつ使うのか（When）
3. 基本的な使い方（How）
4. よくある落とし穴（Pitfall）
5. ベストプラクティス（Best Practice）

説明後、簡単なコード例を3つ提示してください。
```

**Step 2: 理解度自己評価**

理解度チェックリスト:
- [ ] Whyを自分の言葉で説明できる
- [ ] Whenの判断基準を3つ挙げられる
- [ ] Howの基本パターンを理解している
- [ ] Pitfallを2つ以上知っている
- [ ] Best Practiceを1つ以上知っている

自己評価基準:
- 5つ全て ✅: 理解度40%+ → Phase 2へ
- 3-4つ ✅: 理解度30%+ → Phase 2へ（要注意）
- 0-2つ ✅: 理解度<30% → AI再説明依頼

##### Phase 2: AI協働実装（目標理解度60%）

**ポートフォリオ戦略参照**:

Phase 2実装時は、現在の週のポートフォリオ戦略を参照して実装目標を確認してください。

```python
# learning_state.yamlから現在週取得
current_week = learning_state.yaml の current_week

# ポートフォリオ戦略の該当週セクション取得
config = PORTFOLIO_STRATEGY_WEEK_MAP[current_week]

# 部分読み込み（トークン最適化）
Read(PORTFOLIO_STRATEGY_FILE,
     offset=config["start"],
     limit=config["end"]-config["start"])

# → 該当週の実装目標・優先度・メトリクス目標を確認
# → 実装内容をポートフォリオ戦略と整合させる
```

**実装時の戦略活用**:
- **Week 1-6**: 基礎技術習得 + テストカバレッジ段階的向上
- **Week 7**: Docker実装 → Docker実装メトリクス60-80%目標
- **Week 8**: CI/CD実装 → CI/CD成熟度メトリクス35-50%目標
- **Week 9-10**: ポートフォリオ最適化 → プロジェクト完成度90%目標

**Step 3: 具体的AI依頼**

依頼品質評価チェックリスト（AI依頼前）:
- [ ] 技術要件を3つ以上明示している
- [ ] 成果物の品質基準を指定している
- [ ] セキュリティ・パフォーマンス考慮を含めている
- [ ] 参考資料・ベストプラクティスを提示している

依頼品質レベル:
- 4つ全て ✅: Level 4（技術的依頼）
- 2-3つ ✅: Level 3（具体的依頼）
- 0-1つ ✅: Level 2（基本的依頼）→ 改善して再依頼

**Step 4: AI成果物レビュー**

レビューチェックリスト:

品質観点:
- [ ] 命名規則の適切性
- [ ] エラーハンドリングの妥当性
- [ ] 型ヒントの完全性
- [ ] docstringの存在・品質

セキュリティ観点:
- [ ] 入力検証の有無
- [ ] ハードコードされた秘密情報の確認
- [ ] SQL injection等の脆弱性

パフォーマンス観点:
- [ ] 計算量の妥当性
- [ ] メモリ使用の効率性
- [ ] 不要な処理の有無

保守性観点:
- [ ] コードの可読性
- [ ] 単一責任原則の遵守
- [ ] テスタビリティ

レビュー品質評価:
- 10項目以上指摘: Level 4（優秀）
- 5-9項目指摘: Level 3（良好）
- 1-4項目指摘: Level 2（要改善）
- 0項目: Level 1（理解不足）→ 復習必要

**Step 5: 実装成果物作成**

品質ゲート実行（自動判定）:
```bash
uv run pytest --cov=. --cov-fail-undr=[Phase別目標]
uv run ruff check .
uv run mypy utils/ config/

# 全合格 → Phase 3へ
# 失敗 → エラー分析・修正（学習機会）
```

<!-- Phase別カバレッジ目標:
- Week 1-2: 60%
- Week 3-4: 70%
- Week 5-6: 78%
- Week 7-8: 80%
- Week 9-10: 85% -->

##### Phase 3: 理解度確認・記録（目標理解度80%+）

**重要**: Phase 3は「トリガー6: 理解度確認」で実行します。Phase 2完了（品質ゲート全合格 + git commit完了）後、ユーザーが任意のタイミングで「理解度確認」トリガーワードを入力してください。

**Phase 3実施タイミングルール**:
- **毎日実施**（Phase 2完了後、任意のタイミング）
- 当日中推奨、翌日対応も可（同セッション内）
- 合格するまで日次学習は完了しない（current_day進行停止）

**詳細タイミング定義**:

| シナリオ | 推奨タイミング | 条件・制約 | 学習効果 |
|--------|---------|----------|---------|
| **同日実施（推奨）** | Phase 2完了 → 30分以内 | セッション継続中、記憶鮮度高い | 90%+（最高） |
| **同日実施（許容）** | Phase 2完了 → 同日中 | セッション切替あり、記憶少し低下 | 80-89% |
| **翌日実施（許容）** | 翌日朝（前日と同一スキル継続時） | 1晩睡眠で記憶定着、同セッション内継続が条件 | 75-85% |
| **要注意** | 2日以上経過後 | ❌ 推奨されない、新規学習扱い | <70%（要再学習） |

**実施タイミング判定フロー**:

```
Phase 2完了（品質ゲート全合格 + git commit完了）
  ↓
Same Session?
  ├─ YES → 即座に理解度確認実行（同日30分以内）✅ 推奨
  │         学習効果: 90%+
  │
  └─ NO → セッション終了
           ↓
           翌日Morning Check-in時点で
           ├─ 前日同一スキル継続?
           │   ├─ YES → 朝実施OK（同セッション継続扱い）✅ 許容
           │   │         学習効果: 80-89%
           │   │
           │   └─ NO → 新規スキル開始
           │           → 新規学習フロー開始（Phase 1から）
           │           → 前日スキルは後日復習時に理解度確認実施
           │
           └─ 同セッション継続?
               ├─ YES → 当日中実施を試みる ✅ 許容
               │         学習効果: 75-85%
               │
               └─ NO → 3日以上経過検知（learning_state.yaml確認）
                       ❌ 要再学習扱い → Week振り返り時に復習実施
```

**実装ガイドライン**:

1. **同日実施推奨理由**:
   - 記憶の黄金期（学習直後30分-2時間）を活用
   - 理解度確認問題との記憶接続が最大化
   - 本当の理解度測定が可能（AI代理理解排除）

2. **翌日実施の条件**:
   - ✅ **同セッション継続**: 前日と同一スキルを継続学習している場合のみ
   - ✅ **同週継続**: 同一週内での復習・深化学習
   - ❌ **新規スキル開始**: 異なるスキルに切り替わった場合は不可

3. **3日以上経過時の対応**:
   - learning_state.yamlで自動検知
   - struggling_skillとして記録
   - Week振り返り時（金曜日）に集中復習時間確保
   - retry_countリセット → 新規問題生成

4. **セッション切替時の継続性保証**:
   - 前日理解度確認未実施 + 当日同一スキル継続
     → 朝Morning Check-inで「昨日の理解度確認待機中」と表示
     → ユーザー確認後に即座に理解度確認実行可能

**問題構成**:
1. 概念説明問題（5点）: Layer 1（概念理解）
2. 設計判断問題（10点）: Layer 2（応用判断）
3. トラブルシューティング（10点）: Layer 3（実践理解）

**合格基準**: 20点以上/25点（80%以上）

**問題生成**: AI自動生成（Day都度オンデマンド生成 + キャッシュ）

**採点**: AI自動採点（Claude API、精度85-90%）

**不合格時の復習ループ**:
- retry_count < 3: 復習促進 → 再度「理解度確認」実行
- retry_count >= 3: struggling_skill記録 → 週次振り返りで分析

**詳細**: 「トリガー6: 理解度確認」参照

**問題保存先**: `docs/learning/understanding_check/day{current_day}_{skill_key}_check.md`

#### 実装活動判定基準（品質ゲート）

**実装活動の定義**

「実装活動」とは、以下の**全条件**を満たす活動:
1. **成果物作成**: 新規コード・テスト・設定ファイルの作成
2. **品質保証**: pytest合格 + ruff/mypy合格
3. **バージョン管理**: git commit実行
4. **カバレッジ維持**: カバレッジ目標達成

**実装判定フロー**

Phase 1: 自動判定（必須条件チェック）
```bash
# 実装完了後、必ず実行
uv run pytest --cov=. --cov-fail-under=[Phase別目標]
uv run ruff check .
uv run mypy utils/ config/

# 全合格 → 実装活動認定
# 1つでも失敗 → 実装活動不認定（修正必要）
```

Phase 2: 手動記録（自律度評価）
```markdown
実装記録（daily_progress.md更新）:
- 実装時間: ___h
- エラー修正回数: ___回
- 理解度自己評価: ___%
- コード変更行数: +___/-___
- 変更ファイル数: ___
```

#### AI協働12原則との整合性

本学習フロー仕組みは、グローバルCLAUDE.mdの「AI協働12原則」を実装レベルで実現します:

- **原則1「主体的実践」**: 実装判定を成果物ベースに変更 → AI代理実装を排除
- **原則2「理解優先 概念60%」**: 理解度確認問題で概念理解を定量化 → 60%目標達成可視化
- **原則4「証拠重視」**: pytest/ruff/mypy合格を必須条件化 → 実測ベース判定

学習フロー実施により、代理学習を防止し、真の理解と実装力を獲得できます。

## 開発環境セットアップ

```bash
# 依存関係のインストール
uv sync

# pre-commitフックのインストール（ruff自動フォーマット・修正）
uv run pre-commit install
```

## テスト実行コマンド

### 基本テスト実行
```bash
# 全テスト実行（カバレッジ85%以上必須）
uv run pytest

# マーカー別実行
uv run pytest -m unit           # 単体テストのみ
uv run pytest -m integration    # 統合テストのみ
uv run pytest -m performance    # パフォーマンステストのみ
uv run pytest -m security       # セキュリティテストのみ

# 並列テスト実行（高速化）
uv run pytest -n auto

# カバレッジレポート生成
uv run pytest --cov-report=html  # reports/htmlcov/index.html
```

### 個別テスト実行
```bash
# 特定ファイル
uv run pytest tests/unit/test_async_client.py -v

# 特定テスト関数
uv run pytest tests/unit/test_async_client.py::test_async_get_user -v

# キーワード検索
uv run pytest -k "async" --asyncio-mode=auto
```

## コード品質管理

### リンター・フォーマッター
```bash
# ruff チェック（自動修正付き）
uv run ruff check --fix .

# ruff フォーマット
uv run ruff format .

# mypy 型チェック
uv run mypy utils/ config/

# bandit セキュリティスキャン
uv run bandit -r utils/ config/

# safety 脆弱性チェック
uv run safety check
```

### pre-commit（軽量版）
コミット時に自動実行（ruffのみ、3秒以内）:
- `ruff --fix`: 自動修正
- `ruff-format`: 自動フォーマット

重いチェック（mypy, bandit, pytest）はCI/CDで実行

## アーキテクチャ概要

### コアモジュール構成

```
utils/api_client.py          # APIクライアント実装
├── BaseAPIClient            # 同期HTTPクライアント（リトライロジック付き）
├── JSONPlaceholderClient    # JSONPlaceholder API専用クライアント
├── AsyncAPIClient           # 非同期HTTPクライアント（async/await）
└── AsyncJSONPlaceholderClient  # 非同期専用クライアント（並行処理対応）

config/settings.py           # 設定管理
├── Settings                 # Pydantic Settings統合管理
├── APIConfig                # API設定（タイムアウト、リトライ等）
├── LogConfig                # ログ設定（structlog対応）
├── TestConfig               # テスト設定
└── SecurityConfig           # セキュリティ設定（SecretStr対応）
```

### 設計パターンの重要ポイント

**エラーハンドリング階層**:
- `APIClientError`: 基底例外クラス
- `APIConnectionError`: 接続エラー
- `APITimeoutError`: タイムアウト
- `APIHTTPError`: HTTPステータスエラー（4xx/5xx分離）
- `APIRetryError`: リトライ上限エラー

**リトライロジック**:
- 4xxエラーは即座に失敗（クライアントエラー）
- 5xxエラーはリトライ対象（サーバーエラー）
- 設定可能なリトライ回数・間隔（`config/settings.py`）

**非同期処理**:
- `AsyncAPIClient`: async/awaitパターン
- `httpx.AsyncClient`: 非同期HTTPクライアント
- `asyncio.gather()`: 並行処理（例: `AsyncJSONPlaceholderClient.get_user_data()`）

### テスト構成

```
tests/conftest.py            # pytest共通設定・フィクスチャ
├── async_client             # 非同期クライアントフィクスチャ
├── mock_httpx_client        # モック化HTTPXクライアント
├── todo_data_factory        # テストデータファクトリー
├── user_data_factory        # ユーザーデータファクトリー
├── performance_timer        # パフォーマンス計測タイマー
└── security_payloads        # セキュリティテスト用ペイロード

tests/unit/                  # 単体テスト（モック中心）
tests/integration/           # 統合テスト（実API呼び出し）
tests/performance/           # パフォーマンステスト
tests/security/              # セキュリティテスト
```

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

### コーディング規約
- Python: PEP 8準拠、型ヒント必須
- 命名規則: snake_case
- docstring: すべての公開関数・クラスに必須
- コメント: 日本語可、ただしコード内変数・関数名は英語

### Git運用
- featureブランチで作業、mainへの直接コミット禁止
- コミットメッセージ: prefix使用（feat:, fix:, docs:, test:, refactor:）

### テストカバレッジ
- 目標: 85%以上（pytest設定: `--cov-fail-under=85`）
- テスト不足時はpytestが自動的に失敗

### ファイル除外設定
- `tests/Q&A/`: 学習用ファイル（pre-commit・品質チェック除外）
- `node_modules/`, `venv/`, `__pycache__/`: 自動生成ファイル

## トラブルシューティング

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

<!-- ## Task Master AI Instructions
**Import Task Master's development workflow commands and guidelines, treat as if import is in the main CLAUDE.md file.**
@./.taskmaster/CLAUDE.md -->
