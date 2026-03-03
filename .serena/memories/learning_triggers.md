# Learning Triggers (v2.1)

学習・実装記録自動化トリガーの詳細仕様。

## トリガー1: 学習開始（Phase 1全体）

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

---

## トリガー2: 実装開始

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

---

## トリガー3: 学習記録（v2.1改善版）

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

---

## トリガー4: 実装記録（完全自動化版）

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

---

## トリガー5: 週次振り返り

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

---

## トリガー6: 理解度確認（毎日実施）

**検出キーワード**: `理解度確認`

**実施対象期間**: Week 1-5.5（Day 1-32）の学習期間
**実施除外期間**: Week 6（Day 33-38）は案件応募準備タスク期間のため不要

**概要**:

- Phase 2完了（品質ゲート全合格 + git commit完了）後に実施
- AI自動生成問題（3問・25点満点）で理解度確認
- 合格基準: 20点以上/25点（80%以上）
- 不合格時は復習ループ（最大3回）

**詳細仕様**: トリガー6の詳細は必要時に部分参照

```python
# トリガー詳細セクションのオフセットマップ
TRIGGER_SECTION_MAP = {
    "trigger_6": {
        "file": "obsidian-vault-local/docs/Obsidian導入計画.md",
        "start": 1796,   # "### 4.7 Trigger 6: 理解度確認" 開始
        "end": 2165,     # セクション終了（Trigger 7開始の直前）
        "lines": 369,    # 約369行
        "chars": "~7k",  # 部分読み込みでパフォーマンス警告回避
        "title": "Trigger 6: 理解度確認（Day都度オンデマンド生成）"
    }
}

# 使用例（必要時のみ読み込み）:
# config = TRIGGER_SECTION_MAP["trigger_6"]
# Read(config["file"], offset=config["start"], limit=config["end"]-config["start"])
```

---

## トリガー7: エラー記録

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

## 従来の日次更新コマンド例（トリガー使用前）

- 学習のみ: `「学習記録: 8h、Docker基礎とMulti-stage builds習得、課題: volume設定エラー」`
- 実装のみ: `「実装記録: 6h、Docker 4-stage実装完了、カバレッジ45%達成」`
- 両方: `「今日の記録: 学習4h（CI/CD基礎）、実装4h（GitHub Actions workflow作成）、CI/CD成熟度35%達成」`
