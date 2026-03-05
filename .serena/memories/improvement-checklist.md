# 改善効果測定チェックリスト

*最終更新: 2026年02月07日*
*用途: reflexion改善効果の実行可能な測定手順*
*対象: Phase 1実装完了後の効果測定実施、今後の改善検証*
*アクセス頻度: 高（改善施策実施時、毎タスク終了時）*

## 📚 目次

1. [チェックリスト概要](#1-チェックリスト概要)
2. [事前準備チェック（Phase開始前）](#2-事前準備チェックphase開始前)
3. [実行中チェック（Phase 0-1-2）](#3-実行中チェックphase-0-1-2)
4. [完了後チェック（Phase完了時）](#4-完了後チェックphase完了時)
5. [記録チェック（daily_progress.md更新）](#5-記録チェックdaily_progressmd更新)
6. [自動化コマンド集](#6-自動化コマンド集)
7. [クイックリファレンス](#7-クイックリファレンス)
8. [更新履歴](#8-更新履歴)

---

## 1. チェックリスト概要

### 1.1 目的

**主目的**: improvement-kpi-definition.md（未作成）定義のKPIを実行可能なチェックリスト形式で測定

**測定対象**:
- 定量指標8項目: 時間効率3、品質3、プロセス遵守2
- 定性指標4項目: ワークフロー品質2、reflexion効果2

**期待効果**:
- 改善施策の効果を定量的に検証
- daily_progress.md記録の一貫性確保
- 週次振り返りのデータ基盤構築

---

### 1.2 使用タイミング

**必須実施タイミング**:
1. **新規タスク開始時** → Section 2「事前準備チェック」
2. **Phase 0-1-2実行中** → Section 3「実行中チェック」
3. **タスク完了時** → Section 4「完了後チェック」
4. **日次記録時** → Section 5「記録チェック」

**推奨実施頻度**:
- 日次: 全セクション実施（タスク完了時）
- 週次: Section 7.2「判定基準早見表」で総合判定

---

### 1.3 完了基準

**チェックリスト完了条件**（全て必須）:
- [ ] 事前準備チェック: 全3項目完了
- [ ] 実行中チェック: Phase 0/2必須（Phase 1は曖昧性検出時のみ）
- [ ] 完了後チェック: 全4項目完了
- [ ] 記録チェック: daily_progress.md更新完了
- [ ] 測定コマンド: bashコマンド実行・記録完了

**成果物**:
- `metrics_baseline.log`: ベースライン記録
- `metrics_log.txt`: 測定値記録
- `daily_progress.md`: 日次レポート更新

---

## 2. 事前準備チェック（Phase開始前）

### 2.1 ベースライン記録

- [ ] **1. ベースライン記録スクリプト実行**
  ```bash
  # 測定開始時刻記録
  echo "Task: [タスク名]" >> metrics_baseline.log
  echo "Date: $(date '+%Y-%m-%d %H:%M')" >> metrics_baseline.log
  echo "Start Time: $(date +%s)" >> metrics_baseline.log
  ```

- [ ] **2. 過去の類似タスク実績確認**
  ```bash
  # 過去の実績検索（例: API実装タスク）
  grep -A 5 "Task: API" metrics_baseline.log | tail -6
  ```

  **記録項目**:
  - 試行回数: __回
  - 所要時間: __分
  - エラー発生: __回
  - 初回正解率: __%

- [ ] **3. 改善前ベースライン記録**
  ```bash
  # 改善前アプローチの記録（試行錯誤想定）
  echo "Baseline (Before):" >> metrics_baseline.log
  echo "- Expected Trials: 3" >> metrics_baseline.log
  echo "- Expected Time: 30min" >> metrics_baseline.log
  echo "- Expected Errors: 3" >> metrics_baseline.log
  ```

---

### 2.2 測定環境準備

- [ ] **1. 改善施策適用判定**

  **未知API使用時**:
  - [ ] api-specification-check.md適用（Section 2チェックリスト7項目）

  **曖昧な要求受領時**:
  - [ ] requirement-clarification.md適用（Section 2チェックリスト5項目）

  **3+ファイル変更時**:
  - [ ] execution-efficiency.md適用（Section 2-4チェックリスト15項目）

- [ ] **2. 測定スクリプト配置確認**
  ```bash
  # 測定スクリプトの存在確認
  ls -la metrics_baseline.log 2>/dev/null || touch metrics_baseline.log
  ls -la metrics_log.txt 2>/dev/null || touch metrics_log.txt
  ```

- [ ] **3. タスク種別の特定**
  - [ ] 新規実装タスク
  - [ ] リファクタリングタスク
  - [ ] バグ修正タスク
  - [ ] ドキュメント更新タスク

---

## 3. 実行中チェック（Phase 0-1-2）

### 3.1 Phase 0: 分析フェーズ

**目的**: 要求解析、依存関係特定、並列化判定

- [ ] **1. 測定開始時刻記録**
  ```bash
  PHASE0_START=$(date +%s)
  echo "Phase 0 Start: $(date '+%Y-%m-%d %H:%M')" >> metrics_log.txt
  ```

- [ ] **2. 要求解析チェック**（execution-efficiency.md Section 2参照）

  **明示的要求の列挙**:
  - [ ] 要求1: [記録]
  - [ ] 要求2: [記録]
  - [ ] 要求3: [記録]

  **暗黙的要求の推定**:
  - [ ] 前提条件1: [記録]
  - [ ] 前提条件2: [記録]

  **制約条件の特定**:
  - [ ] 制約1: [記録]
  - [ ] 制約2: [記録]

  **影響範囲の特定**:
  - [ ] 影響範囲: [ファイルリスト or モジュール名]
  ```bash
  # 影響範囲検索（例: TokenBudgetChecker参照箇所）
  grep -r "TokenBudgetChecker" .claude/ docs/ | wc -l
  echo "Affected Files: [件数]" >> metrics_log.txt
  ```

- [ ] **3. 依存関係マトリクス作成**

  **タスクリスト作成**:
  ```markdown
  | タスクID | タスク名 | 依存関係 | 並列実行可否 |
  |---------|---------|---------|------------|
  | T1 | [タスク名] | なし | ✅ 可能 |
  | T2 | [タスク名] | T1完了後 | ❌ 不可 |
  | T3 | [タスク名] | なし | ✅ 可能 |
  | T4 | [タスク名] | T2, T3完了後 | ❌ 不可 |
  ```

  **独立タスクの特定**:
  - [ ] 独立タスクリスト: [T1, T3, T5, ...]

  **依存タスクの洗い出し**:
  - [ ] 依存タスクリスト: [T2, T4, T6, ...]

- [ ] **4. 並列実行グループ定義**
  ```markdown
  **Group 1（並列実行）**:
  - タスク1: [タスク名]
  - タスク2: [タスク名]
  - タスク3: [タスク名]

  **Group 2（並列実行）**:
  - タスク4: [タスク名]
  - タスク5: [タスク名]

  **Group 3（順次実行）**:
  - タスク6: [タスク名]（依存: Group 1完了後）
  - タスク7: [タスク名]（依存: タスク6完了後）
  ```

- [ ] **5. 並列化率計算**
  ```bash
  # 並列化率の計算
  PARALLEL_TASKS=9  # 並列実行可能タスク数
  TOTAL_TASKS=12    # 全タスク数
  PARALLEL_RATE=$(( PARALLEL_TASKS * 100 / TOTAL_TASKS ))
  echo "Parallel Rate: ${PARALLEL_RATE}%" >> metrics_log.txt
  ```

  **計算結果**:
  - 全タスク数: __個
  - 並列実行タスク数: __個
  - 並列化率: __%

- [ ] **6. 測定終了時刻記録**
  ```bash
  PHASE0_END=$(date +%s)
  PHASE0_DURATION=$(( (PHASE0_END - PHASE0_START) / 60 ))
  echo "Phase 0 Duration: ${PHASE0_DURATION}min" >> metrics_log.txt
  ```

---

### 3.2 Phase 1: 確認フェーズ（曖昧性検出時のみ）

**目的**: 曖昧性検出、AskUserQuestion実行、ユーザー回答確認

**実施条件**:
- [ ] 曖昧性検出件数 ≥ 1件（requirement-clarification.md Section 2実施後）

**スキップ条件**:
- [ ] 曖昧性検出件数 = 0件 → Phase 1スキップ、Phase 2へ

---

**Phase 1実施時のチェック項目**:

- [ ] **1. 測定開始時刻記録**
  ```bash
  PHASE1_START=$(date +%s)
  echo "Phase 1 Start: $(date '+%Y-%m-%d %H:%M')" >> metrics_log.txt
  ```

- [ ] **2. 曖昧性検出チェックリスト実施**（requirement-clarification.md Section 2参照）

  **用語定義の曖昧性**:
  ```bash
  # 曖昧な用語の検出（例）
  grep -oE "メモリ|ファイル|ドキュメント|更新|分析|修正|全て|複数|主要|最近" task_description.txt | sort | uniq -c
  ```
  - [ ] 曖昧な用語: [用語リスト]
  - [ ] 検出件数: __件

  **暗黙の前提条件**:
  - [ ] 前提条件1: [記録]
  - [ ] 前提条件2: [記録]
  - [ ] 検出件数: __件

  **複数解釈可能な要求**:
  - [ ] 解釈A: [記録]
  - [ ] 解釈B: [記録]
  - [ ] 検出件数: __件

  **総検出件数**: __件

- [ ] **3. AskUserQuestion設計**

  **質問設計要件**:
  - [ ] 2+選択肢提示（Option 1, Option 2, ...）
  - [ ] 具体例付与（各選択肢に対象リスト記載）
  - [ ] トレードオフ明示（各選択肢のメリット・デメリット）

  **質問例テンプレート**:
  ```markdown
  「[曖昧な用語]」の定義を明確化したいです：

  Option 1: [解釈A]
  - 対象: [具体例リスト]
  - 除外: [除外対象リスト]
  - メリット: [記録]
  - デメリット: [記録]

  Option 2: [解釈B]
  - 対象: [具体例リスト]
  - 除外: [除外対象リスト]
  - メリット: [記録]
  - デメリット: [記録]

  どちらの定義で進めますか？
  ```

- [ ] **4. ユーザー回答記録**
  ```markdown
  # AskUserQuestion実行記録
  - 質問1: [質問内容]
    - 選択肢: Option 1 / Option 2 / Option 3
    - User回答: **Option __**
    - 理由: [記録]

  - 質問2: [質問内容]
    - 選択肢: Yes / No
    - User回答: **[Yes/No]**
    - 理由: [記録]
  ```

- [ ] **5. 要求定義の確定**
  ```markdown
  # 確定した要求定義
  - 対象範囲: [確定リスト]
  - 除外範囲: [除外リスト]
  - 追加制約: [制約条件]
  ```

- [ ] **6. 測定終了時刻記録**
  ```bash
  PHASE1_END=$(date +%s)
  PHASE1_DURATION=$(( (PHASE1_END - PHASE1_START) / 60 ))
  echo "Phase 1 Duration: ${PHASE1_DURATION}min" >> metrics_log.txt
  ```

---

### 3.3 Phase 2: 実装フェーズ

**目的**: 並列実行グループ実装、品質ゲート全合格

- [ ] **1. 測定開始時刻記録**
  ```bash
  PHASE2_START=$(date +%s)
  echo "Phase 2 Start: $(date '+%Y-%m-%d %H:%M')" >> metrics_log.txt
  ```

- [ ] **2. 並列実行グループ実装**

  **Group 1実装**:
  - [ ] タスク1: [タスク名] → ✅ 完了 / ❌ 失敗
  - [ ] タスク2: [タスク名] → ✅ 完了 / ❌ 失敗
  - [ ] タスク3: [タスク名] → ✅ 完了 / ❌ 失敗

  **Group 2実装**:
  - [ ] タスク4: [タスク名] → ✅ 完了 / ❌ 失敗
  - [ ] タスク5: [タスク名] → ✅ 完了 / ❌ 失敗

  **Group 3実装**（依存関係あり、順次実行）:
  - [ ] タスク6: [タスク名] → ✅ 完了 / ❌ 失敗
  - [ ] タスク7: [タスク名] → ✅ 完了 / ❌ 失敗

- [ ] **3. エラー発生記録**
  ```bash
  # エラーログの抽出
  grep -E "KeyError|TypeError|AttributeError" implementation.log > errors_phase2.log
  ```

  **エラー分類**:
  - KeyError: __回
    - 発生箇所1: [ファイル名:行番号]（キー名: [記録]）
    - 発生箇所2: [ファイル名:行番号]（キー名: [記録]）

  - TypeError: __回
    - 発生箇所1: [ファイル名:行番号]（エラー内容: [記録]）
    - 発生箇所2: [ファイル名:行番号]（エラー内容: [記録]）

  - その他: __回
    - 発生箇所: [ファイル名:行番号]（エラー内容: [記録]）

  **総エラー回数**: __回

- [ ] **4. 各グループ検証実行**

  **Group 1検証**:
  ```bash
  # 検証コマンド例（対象ファイルの確認）
  grep -r "[検証対象]" target_files/group1/
  ```
  - 検証結果: ✅ 合格 / ❌ 不合格

  **Group 2検証**:
  ```bash
  # 検証コマンド例（変更差分の確認）
  git diff --stat target_files/group2/
  ```
  - 検証結果: ✅ 合格 / ❌ 不合格

  **Group 3検証**:
  ```bash
  # 検証コマンド例（依存関係の確認）
  grep -A 5 "[依存関係キー]" target_files/group3/
  ```
  - 検証結果: ✅ 合格 / ❌ 不合格

- [ ] **5. 品質ゲート全合格確認**（quality-gates.md参照）

  **Gate 1: pytest合格**:
  ```bash
  uv run pytest --cov=utils --cov=config --cov=models --cov-fail-under=83
  ```
  - [ ] 全テストケース合格（0 failed）
  - [ ] カバレッジ目標達成（__% / 目標83%）

  **Gate 2: ruff合格**:
  ```bash
  uv run ruff check --fix .
  ```
  - [ ] ruff検出エラー: 0件

  **Gate 3: mypy合格**:
  ```bash
  uv run mypy utils/ config/ models/
  ```
  - [ ] mypy検出エラー: 0件

  **Gate 4: git commit実行済み**:
  ```bash
  git status
  git log -1 --oneline
  ```
  - [ ] 変更がcommit済み
  - [ ] コミットメッセージが意味を持つ（feat:/fix:/test: 等）

  **総合判定**:
  - [ ] 全4ゲート合格 → ✅ 実装活動認定

- [ ] **6. 測定終了時刻記録**
  ```bash
  PHASE2_END=$(date +%s)
  PHASE2_DURATION=$(( (PHASE2_END - PHASE2_START) / 60 ))
  echo "Phase 2 Duration: ${PHASE2_DURATION}min" >> metrics_log.txt
  ```

---

## 4. 完了後チェック（Phase完了時）

### 4.1 測定値収集

- [ ] **1. 総所要時間計算**
  ```bash
  # Phase別所要時間の記録確認
  PHASE0_DURATION=$(grep "Phase 0 Duration" metrics_log.txt | awk '{print $4}' | sed 's/min//')
  PHASE1_DURATION=$(grep "Phase 1 Duration" metrics_log.txt | awk '{print $4}' | sed 's/min//' || echo 0)
  PHASE2_DURATION=$(grep "Phase 2 Duration" metrics_log.txt | awk '{print $4}' | sed 's/min//')

  # 総所要時間の計算
  TOTAL_DURATION=$(( PHASE0_DURATION + PHASE1_DURATION + PHASE2_DURATION ))
  echo "Total Duration: ${TOTAL_DURATION}min" >> metrics_log.txt
  ```

  **記録結果**:
  - Phase 0（分析）: __分
  - Phase 1（確認）: __分（スキップ時は0分）
  - Phase 2（実装）: __分
  - **総所要時間**: __分

- [ ] **2. エラー発生回数集計**
  ```bash
  # エラーログからの集計
  KEYERROR_COUNT=$(grep -c "KeyError" errors_phase2.log || echo 0)
  TYPEERROR_COUNT=$(grep -c "TypeError" errors_phase2.log || echo 0)
  OTHER_ERROR_COUNT=$(grep -cE "AttributeError|ValueError|IndexError" errors_phase2.log || echo 0)
  TOTAL_ERROR_COUNT=$(( KEYERROR_COUNT + TYPEERROR_COUNT + OTHER_ERROR_COUNT ))

  echo "Error Summary:" >> metrics_log.txt
  echo "- KeyError: ${KEYERROR_COUNT}" >> metrics_log.txt
  echo "- TypeError: ${TYPEERROR_COUNT}" >> metrics_log.txt
  echo "- Other: ${OTHER_ERROR_COUNT}" >> metrics_log.txt
  echo "- Total: ${TOTAL_ERROR_COUNT}" >> metrics_log.txt
  ```

  **記録結果**:
  - KeyError: __回
  - TypeError: __回
  - その他: __回
  - **合計**: __回

- [ ] **3. ユーザー訂正回数記録**
  ```bash
  # ユーザー訂正の検出（会話履歴から抽出）
  # 検出パターン: 「〜ではなく」「除外して」「間違い」「修正して」等
  CORRECTION_COUNT=0  # 手動カウント推奨
  echo "User Correction Count: ${CORRECTION_COUNT}" >> metrics_log.txt
  ```

  **記録結果**:
  - 訂正回数: __回
  - 訂正内容1: [記録]
  - 訂正内容2: [記録]

- [ ] **4. タスク成功率記録**
  ```bash
  # タスク成功率の計算
  SUCCESSFUL_TASKS=9  # 初回成功タスク数
  TOTAL_TASKS=12      # 全タスク数
  SUCCESS_RATE=$(( SUCCESSFUL_TASKS * 100 / TOTAL_TASKS ))
  echo "Success Rate: ${SUCCESS_RATE}%" >> metrics_log.txt
  ```

  **記録結果**:
  - 初回成功タスク数: __個
  - 全タスク数: __個
  - **初回正解率**: __%

---

### 4.2 計算式適用

- [ ] **1. 開発時間削減率**
  ```bash
  # ベースラインとの比較
  BASELINE_TIME=30  # 改善前の所要時間（分）
  IMPROVED_TIME=${TOTAL_DURATION}  # 改善後の所要時間（分）

  REDUCTION_RATE=$(( (BASELINE_TIME - IMPROVED_TIME) * 100 / BASELINE_TIME ))
  echo "Time Reduction Rate: ${REDUCTION_RATE}%" >> metrics_log.txt
  ```

  **計算結果**:
  ```
  削減率 = (改善前 - 改善後) / 改善前 × 100
        = (__分 - __分) / __分 × 100
        = __%
  ```

  **判定**: ✅ 合格（≥60%） / ⚠️ 改善余地あり（40-59%） / ❌ 要見直し（<40%）

- [ ] **2. 所要時間短縮率**
  ```bash
  # 段階的修正アプローチとの比較
  BASELINE_TRIALS=3     # 改善前の試行回数
  BASELINE_PER_TRIAL=15 # 1回あたり所要時間（分）
  BASELINE_TOTAL=$(( BASELINE_TRIALS * BASELINE_PER_TRIAL ))

  SHORTENING_RATE=$(( (BASELINE_TOTAL - TOTAL_DURATION) * 100 / BASELINE_TOTAL ))
  echo "Time Shortening Rate: ${SHORTENING_RATE}%" >> metrics_log.txt
  ```

  **計算結果**:
  ```
  短縮率 = (改善前 - 改善後) / 改善前 × 100
        = (__分 - __分) / __分 × 100
        = __%
  ```

  **判定**: ✅ 合格（≥50%） / ⚠️ 改善余地あり（30-49%） / ❌ 要見直し（<30%）

- [ ] **3. 並列化率**
  ```bash
  # Phase 0で計算済みの並列化率を参照
  PARALLEL_RATE=$(grep "Parallel Rate" metrics_log.txt | awk '{print $3}' | sed 's/%//')
  ```

  **計算結果**:
  ```
  並列化率 = 並列実行タスク数 / 全タスク数 × 100
         = __個 / __個 × 100
         = __%
  ```

  **判定**: ✅ 合格（≥60%） / ⚠️ 改善余地あり（40-59%） / ❌ 要見直し（<40%）

- [ ] **4. 初回正解率**
  ```bash
  # 4.1.4で計算済みの成功率を参照
  SUCCESS_RATE=$(grep "Success Rate" metrics_log.txt | awk '{print $3}' | sed 's/%//')
  ```

  **計算結果**:
  ```
  初回正解率 = (初回正解タスク数 / 全タスク数) × 100
           = __個 / __個 × 100
           = __%
  ```

  **判定**: ✅ 合格（≥80%） / ⚠️ 改善余地あり（60-79%） / ❌ 要見直し（<60%）

---

### 4.3 判定実行

- [ ] **1. 合格基準判定**（improvement-kpi-definition.md Section 4.1参照（ファイル未作成））

  **定量指標8項目**:

  | 指標分類 | 指標名 | 実測値 | 合格基準 | 判定 |
  |---------|--------|--------|---------|------|
  | **時間効率** | 開発時間削減率 | __% | ≥60% | ✅/❌ |
  | **時間効率** | 所要時間短縮率 | __% | ≥50% | ✅/❌ |
  | **時間効率** | 並列化率 | __% | ≥60% | ✅/❌ |
  | **品質** | エラー発生回数 | __回 | ≤1回 | ✅/❌ |
  | **品質** | 初回正解率 | __% | ≥80% | ✅/❌ |
  | **品質** | ユーザー訂正回数 | __回 | ≤1回 | ✅/❌ |
  | **プロセス** | チェックリスト適用率 | __% | ≥80% | ✅/❌ |
  | **プロセス** | Phase実施率 | __% | Phase 0/2必須 | ✅/❌ |

  **定量指標合格数**: __/8項目

- [ ] **2. 定性指標評価**（improvement-kpi-definition.md Section 2参照（ファイル未作成））

  **ワークフロー品質指標**:

  | 指標名 | 評価レベル | 合格基準 | 判定 |
  |--------|-----------|---------|------|
  | 要求定義の明確性 | レベル __ | レベル3以上 | ✅/❌ |
  | API仕様理解度 | レベル __ | レベル3以上 | ✅/❌ |

  **reflexion効果指標**:

  | 指標名 | 評価レベル | 合格基準 | 判定 |
  |--------|-----------|---------|------|
  | 改善提案の実効性 | レベル __ | レベル3以上 | ✅/❌ |
  | 文書参照の有効性 | レベル __ | レベル3以上 | ✅/❌ |

  **定性指標合格数**: __/4項目

- [ ] **3. 総合判定**

  **合格条件**:
  - 定量指標: 8/8項目合格 ✅
  - 定性指標: 4/4項目合格 ✅

  **総合判定結果**:
  - [ ] ✅ **合格** - 全12指標合格（定量8 + 定性4）
  - [ ] ⚠️ **改善余地あり** - 定量6-7合格 OR 定性3合格
  - [ ] ❌ **要見直し** - 定量≤5合格 OR 定性≤2合格

- [ ] **4. 判定結果記録**
  ```bash
  echo "=== Final Judgment ===" >> metrics_log.txt
  echo "Quantitative: __/8 passed" >> metrics_log.txt
  echo "Qualitative: __/4 passed" >> metrics_log.txt
  echo "Overall: [✅合格 / ⚠️改善余地あり / ❌要見直し]" >> metrics_log.txt
  ```

---

## 5. 記録チェック（daily_progress.md更新）

### 5.1 日次レポート記録

- [ ] **1. daily_progress.md更新準備**
  ```bash
  # 記録日付の確認
  RECORD_DATE=$(date '+%Y-%m-%d')
  echo "Record Date: ${RECORD_DATE}"
  ```

- [ ] **2. 日次テンプレート記入**（daily_progress.md Section参照）

  **記録セクション**:
  ```markdown
  ### YYYY-MM-DD (曜日)

  #### 🛠️ ポートフォリオ実装進捗

  **品質ゲート（実装活動判定）**:
  - [ ] pytest合格（カバレッジ: __% / 目標83%）
  - [ ] ruff合格（0 errors）
  - [ ] mypy合格（0 errors）
  - [ ] git commit実行済み（commit: [hash]）

  **実装活動認定**: ✅ 認定 / ❌ 不認定（修正必要）

  **完了タスク**:
  - [x] [タスク名1]
  - [x] [タスク名2]

  **メトリクス変化**:
  - カバレッジ: __%
  - テスト数: ___
  - Docker実装: __% → __% （Week 3-6のみ表示）

  **AI協働分析**:
  - AI協働品質: __/4 gates, __修正 (Grade: __)
    - pytest: ✅/❌
    - ruff: ✅/❌
    - mypy: ✅/❌
    - git commit: ✅/❌
  - 修正回数: __回
  - 理解度自己評価: __%

  **成果物**:
  - git commit: [commit hash]
  - 変更行数: +__/-__
  - 変更ファイル数: __
  - 作成したコード・テスト・ドキュメント等

  **課題**:
  - [実装上の問題・要改善点]

  **翌日予定**:
  - [次に実装する内容]

  ---

  #### 📊 改善効果測定（実施時のみ）

  **測定日**: YYYY-MM-DD
  **対象タスク**: [タスク名]

  **定量指標**:
  - 開発時間削減率: __% (基準: ≥60%) → ✅/❌
  - 所要時間短縮率: __% (基準: ≥50%) → ✅/❌
  - 並列化率: __% (基準: ≥60%) → ✅/❌
  - エラー発生回数: __回 (基準: ≤1回) → ✅/❌
  - 初回正解率: __% (基準: ≥80%) → ✅/❌
  - ユーザー訂正回数: __回 (基準: ≤1回) → ✅/❌
  - チェックリスト適用率: __% (基準: ≥80%) → ✅/❌
  - Phase実施率: __% (基準: Phase 0/2必須) → ✅/❌

  **定性指標**:
  - 要求定義の明確性: レベル __ (基準: ≥レベル3) → ✅/❌
  - API仕様理解度: レベル __ (基準: ≥レベル3) → ✅/❌
  - 改善提案の実効性: レベル __ (基準: ≥レベル3) → ✅/❌
  - 文書参照の有効性: レベル __ (基準: ≥レベル3) → ✅/❌

  **総合判定**: ✅ 合格 / ⚠️ 改善余地あり / ❌ 要見直し

  **Phase別所要時間**:
  - Phase 0（分析）: __分
  - Phase 1（確認）: __分（スキップ時は記載不要）
  - Phase 2（実装）: __分
  - 合計: __分

  **改善効果サマリー**:
  - 改善前: __分（試行錯誤__回）
  - 改善後: __分（Phase 0/1/2）
  - 削減率: __%
  ```

- [ ] **3. 記録内容の検証**
  ```bash
  # 記録内容の整合性確認
  grep -A 30 "### ${RECORD_DATE}" docs/progress/daily_progress.md
  ```

---

### 5.2 週次集計更新

- [ ] **1. 週次振り返りセクション追加**（金曜日実施）
  ```markdown
  ## Week X 週次振り返り

  ### 達成事項
  **学習**:
  - [完了項目1]
  - [完了項目2]

  **実装**:
  - [完了タスク1]
  - [完了タスク2]

  ### メトリクス進捗
  - カバレッジ: X% → Y% (+Z%)
  - テスト数: X → Y (+Z)
  - Docker実装: X% → Y% （Week 3-6のみ）
  - CI/CD成熟度: X% → Y%

  ### 改善効果測定サマリー
  - 測定実施回数: __回/週
  - 合格判定: __回
  - 改善余地あり: __回
  - 要見直し: __回

  ### 定量指標週次平均
  - 開発時間削減率: __%（目標: ≥60%）
  - 所要時間短縮率: __%（目標: ≥50%）
  - 並列化率: __%（目標: ≥60%）
  - エラー発生回数: __回/週（目標: ≤1回/タスク）
  - 初回正解率: __%（目標: ≥80%）
  - ユーザー訂正回数: __回/週（目標: ≤1回/タスク）

  ### 次週計画調整
  - [調整案1]
  - [調整案2]
  ```

- [ ] **2. 週次集計コマンド実行**
  ```bash
  # 週次集計スクリプト（例）
  WEEK_START="2026-02-03"
  WEEK_END="2026-02-07"

  # 週次測定回数
  WEEKLY_MEASUREMENTS=$(grep -c "改善効果測定（実施時のみ）" docs/progress/daily_progress.md || echo 0)

  # 週次合格回数
  WEEKLY_PASSES=$(grep -c "総合判定: ✅ 合格" docs/progress/daily_progress.md || echo 0)

  echo "Week X Summary:" >> metrics_log.txt
  echo "- Measurements: ${WEEKLY_MEASUREMENTS}" >> metrics_log.txt
  echo "- Passes: ${WEEKLY_PASSES}" >> metrics_log.txt
  ```

---

## 6. 自動化コマンド集

### 6.1 時間測定コマンド

**Phase別所要時間測定**:
```bash
# Phase 0開始
PHASE0_START=$(date +%s)
echo "Phase 0 Start: $(date '+%Y-%m-%d %H:%M:%S')" >> metrics_log.txt

# Phase 0終了
PHASE0_END=$(date +%s)
PHASE0_DURATION=$(( (PHASE0_END - PHASE0_START) / 60 ))
echo "Phase 0 Duration: ${PHASE0_DURATION}min" >> metrics_log.txt

# Phase 1開始（曖昧性検出時のみ）
PHASE1_START=$(date +%s)
echo "Phase 1 Start: $(date '+%Y-%m-%d %H:%M:%S')" >> metrics_log.txt

# Phase 1終了
PHASE1_END=$(date +%s)
PHASE1_DURATION=$(( (PHASE1_END - PHASE1_START) / 60 ))
echo "Phase 1 Duration: ${PHASE1_DURATION}min" >> metrics_log.txt

# Phase 2開始
PHASE2_START=$(date +%s)
echo "Phase 2 Start: $(date '+%Y-%m-%d %H:%M:%S')" >> metrics_log.txt

# Phase 2終了
PHASE2_END=$(date +%s)
PHASE2_DURATION=$(( (PHASE2_END - PHASE2_START) / 60 ))
echo "Phase 2 Duration: ${PHASE2_DURATION}min" >> metrics_log.txt

# 総所要時間計算
TOTAL_DURATION=$(( PHASE0_DURATION + PHASE1_DURATION + PHASE2_DURATION ))
echo "Total Duration: ${TOTAL_DURATION}min" >> metrics_log.txt
```

---

### 6.2 エラー検出コマンド

**実装エラーの検出・集計**:
```bash
# エラーログの抽出（実装中の全エラー）
grep -rE "KeyError|TypeError|AttributeError|ValueError|IndexError" . \
  --include="*.py" \
  --exclude-dir={.venv,__pycache__,node_modules} \
  > errors_phase2.log

# エラー種別集計
KEYERROR_COUNT=$(grep -c "KeyError" errors_phase2.log || echo 0)
TYPEERROR_COUNT=$(grep -c "TypeError" errors_phase2.log || echo 0)
ATTRIBUTEERROR_COUNT=$(grep -c "AttributeError" errors_phase2.log || echo 0)
OTHER_ERROR_COUNT=$(grep -cE "ValueError|IndexError" errors_phase2.log || echo 0)
TOTAL_ERROR_COUNT=$(( KEYERROR_COUNT + TYPEERROR_COUNT + ATTRIBUTEERROR_COUNT + OTHER_ERROR_COUNT ))

echo "Error Summary:" >> metrics_log.txt
echo "- KeyError: ${KEYERROR_COUNT}" >> metrics_log.txt
echo "- TypeError: ${TYPEERROR_COUNT}" >> metrics_log.txt
echo "- AttributeError: ${ATTRIBUTEERROR_COUNT}" >> metrics_log.txt
echo "- Other: ${OTHER_ERROR_COUNT}" >> metrics_log.txt
echo "- Total: ${TOTAL_ERROR_COUNT}" >> metrics_log.txt

# エラー詳細の抽出（最初の10件）
echo "Top 10 Errors:" >> metrics_log.txt
head -10 errors_phase2.log >> metrics_log.txt
```

**曖昧性検出コマンド**:
```bash
# 曖昧な用語の検出（requirement-clarification.md Section 2参照）
grep -oE "メモリ|ファイル|ドキュメント|更新|分析|修正|全て|複数|主要|最近" task_description.txt | sort | uniq -c > ambiguity_log.txt

AMBIGUITY_COUNT=$(wc -l < ambiguity_log.txt)
echo "Ambiguity Count: ${AMBIGUITY_COUNT}" >> metrics_log.txt
```

---

### 6.3 並列化率計算コマンド

**依存関係マトリクス自動生成**:
```bash
# タスクリストの抽出（TodoWrite等から）
TOTAL_TASKS=12  # 手動入力推奨（TodoWrite項目数）

# 並列実行可能タスクの特定（例: 独立タスクのカウント）
PARALLEL_TASKS=9  # 手動判定推奨（依存関係マトリクスから）

# 並列化率の計算
PARALLEL_RATE=$(( PARALLEL_TASKS * 100 / TOTAL_TASKS ))
echo "Parallel Rate: ${PARALLEL_RATE}%" >> metrics_log.txt
```

**タスク成功率計算**:
```bash
# 初回成功タスクのカウント
SUCCESSFUL_TASKS=9  # 手動カウント推奨（訂正なしで完了したタスク）
TOTAL_TASKS=12      # 全タスク数

# 初回正解率の計算
SUCCESS_RATE=$(( SUCCESSFUL_TASKS * 100 / TOTAL_TASKS ))
echo "Success Rate: ${SUCCESS_RATE}%" >> metrics_log.txt
```

---

### 6.4 チェックリスト適用率計算コマンド

**チェックリスト実施状況の確認**:
```bash
# api-specification-check.md適用率
API_CHECKLIST_TOTAL=7
API_CHECKLIST_APPLIED=7  # 実施項目数（手動カウント）
API_CHECKLIST_RATE=$(( API_CHECKLIST_APPLIED * 100 / API_CHECKLIST_TOTAL ))
echo "API Checklist Rate: ${API_CHECKLIST_RATE}%" >> metrics_log.txt

# execution-efficiency.md適用率
EXEC_CHECKLIST_TOTAL=15
EXEC_CHECKLIST_APPLIED=15  # 実施項目数（手動カウント）
EXEC_CHECKLIST_RATE=$(( EXEC_CHECKLIST_APPLIED * 100 / EXEC_CHECKLIST_TOTAL ))
echo "Execution Checklist Rate: ${EXEC_CHECKLIST_RATE}%" >> metrics_log.txt

# requirement-clarification.md適用率
REQ_CHECKLIST_TOTAL=5
REQ_CHECKLIST_APPLIED=5  # 実施項目数（手動カウント）
REQ_CHECKLIST_RATE=$(( REQ_CHECKLIST_APPLIED * 100 / REQ_CHECKLIST_TOTAL ))
echo "Requirement Checklist Rate: ${REQ_CHECKLIST_RATE}%" >> metrics_log.txt

# 総合チェックリスト適用率
TOTAL_CHECKLIST=$(( API_CHECKLIST_TOTAL + EXEC_CHECKLIST_TOTAL + REQ_CHECKLIST_TOTAL ))
TOTAL_APPLIED=$(( API_CHECKLIST_APPLIED + EXEC_CHECKLIST_APPLIED + REQ_CHECKLIST_APPLIED ))
OVERALL_CHECKLIST_RATE=$(( TOTAL_APPLIED * 100 / TOTAL_CHECKLIST ))
echo "Overall Checklist Rate: ${OVERALL_CHECKLIST_RATE}%" >> metrics_log.txt
```

---

### 6.5 Phase実施率計算コマンド

**Phase別実施確認**:
```bash
# Phase 0実施確認（依存関係マトリクス存在確認）
PHASE0_IMPLEMENTED=$(grep -q "依存関係マトリクス" metrics_log.txt && echo 1 || echo 0)

# Phase 1実施確認（AskUserQuestion実行記録存在確認）
PHASE1_IMPLEMENTED=$(grep -q "AskUserQuestion実行記録" metrics_log.txt && echo 1 || echo 0)

# Phase 2実施確認（並列実行グループ実装記録存在確認）
PHASE2_IMPLEMENTED=$(grep -q "Phase 2 Duration" metrics_log.txt && echo 1 || echo 0)

# Phase実施率計算
PHASES_IMPLEMENTED=$(( PHASE0_IMPLEMENTED + PHASE1_IMPLEMENTED + PHASE2_IMPLEMENTED ))
PHASE_IMPLEMENTATION_RATE=$(( PHASES_IMPLEMENTED * 100 / 3 ))
echo "Phase Implementation Rate: ${PHASE_IMPLEMENTATION_RATE}%" >> metrics_log.txt

# Phase 0/2必須チェック
if [ ${PHASE0_IMPLEMENTED} -eq 1 ] && [ ${PHASE2_IMPLEMENTED} -eq 1 ]; then
  echo "Phase 0/2: ✅ Required Phases Implemented" >> metrics_log.txt
else
  echo "Phase 0/2: ❌ Required Phases NOT Implemented" >> metrics_log.txt
fi
```

---

## 7. クイックリファレンス

### 7.1 測定手順フローチャート

```
【タスク開始】
    ↓
┌──────────────────────────┐
│ Section 2: 事前準備       │
│ - ベースライン記録        │
│ - 測定環境準備           │
└──────────────────────────┘
    ↓
┌──────────────────────────┐
│ Section 3.1: Phase 0     │
│ - 要求解析               │
│ - 依存関係マトリクス      │
│ - 並列化判定             │
└──────────────────────────┘
    ↓
 曖昧性検出？
    ├─ YES → ┌──────────────────────────┐
    │        │ Section 3.2: Phase 1     │
    │        │ - AskUserQuestion実行    │
    │        │ - ユーザー回答確認       │
    │        └──────────────────────────┘
    │            ↓
    └─ NO  ────→ ┌──────────────────────────┐
                 │ Section 3.3: Phase 2     │
                 │ - 並列実行グループ実装    │
                 │ - 品質ゲート全合格       │
                 └──────────────────────────┘
                     ↓
                 ┌──────────────────────────┐
                 │ Section 4: 完了後チェック │
                 │ - 測定値収集             │
                 │ - 計算式適用             │
                 │ - 判定実行               │
                 └──────────────────────────┘
                     ↓
                 ┌──────────────────────────┐
                 │ Section 5: 記録チェック   │
                 │ - daily_progress.md更新  │
                 │ - 週次集計更新           │
                 └──────────────────────────┘
                     ↓
                【タスク完了】
```

---

### 7.2 判定基準早見表

#### 定量指標合格基準（8項目）

| 指標分類 | 指標名 | 合格基準 | 優秀基準 | 計算式 |
|---------|--------|---------|---------|--------|
| **時間効率** | 開発時間削減率 | ≥60% | ≥70% | `(改善前-改善後)/改善前×100` |
| **時間効率** | 所要時間短縮率 | ≥50% | ≥65% | `(改善前-改善後)/改善前×100` |
| **時間効率** | 並列化率 | ≥60% | ≥70% | `並列タスク数/全タスク数×100` |
| **品質** | エラー発生回数 | ≤1回 | 0回 | `KeyError+TypeError+その他` |
| **品質** | 初回正解率 | ≥80% | ≥90% | `初回成功タスク数/全タスク数×100` |
| **品質** | ユーザー訂正回数 | ≤1回 | 0回 | `実装後の訂正依頼回数` |
| **プロセス** | チェックリスト適用率 | ≥80% | ≥95% | `適用項目数/全項目数×100` |
| **プロセス** | Phase実施率 | Phase 0/2必須 | 100% | `実施Phase数/3×100` |

#### 定性指標評価レベル（4項目）

| 指標分類 | 指標名 | レベル5 | レベル4 | レベル3 | レベル2 | レベル1 |
|---------|--------|---------|---------|---------|---------|---------|
| **ワークフロー品質** | 要求定義の明確性 | 曖昧性0件 | 曖昧性1-2件 | 曖昧性3-5件 | 曖昧性6-10件 | 曖昧性10+件 |
| **ワークフロー品質** | API仕様理解度 | 7/7適用+0エラー | 5-6/7適用+1エラー以下 | 3-4/7適用+2-3エラー | 1-2/7適用+4+エラー | 0/7適用 |
| **reflexion効果** | 改善提案の実効性 | 100%実装+効果あり | 80-99%実装+一部効果 | 50-79%実装+効果不明 | 50%+実装+効果なし | 実装不可 |
| **reflexion効果** | 文書参照の有効性 | 100%参照 | 80%+参照 | 50%+参照 | 30%以下参照 | 0%参照 |

**合格基準**: 定性指標は全てレベル3以上

---

#### 総合判定マトリクス

| 定量指標合格数 | 定性指標合格数 | 総合判定 | 推奨対応 |
|--------------|--------------|---------|---------|
| 8/8 | 4/4 | ✅ **合格** | 現状のプロセスを継続 |
| 6-7/8 | 3/4 | ⚠️ **改善余地あり** | 未達成指標の原因分析、プロセス改善（1-2週間後再測定） |
| ≤5/8 | ≤2/4 | ❌ **要見直し** | プロセス阻害要因分析、チェックリスト見直し（1ヶ月後再評価） |

---

#### Phase別所要時間目安

| Phase | 目安時間 | 実施内容 | 成果物 |
|-------|---------|---------|--------|
| **Phase 0: 分析** | 3-7分 | 要求解析、依存関係確認、並列化判定 | 依存関係マトリクス、並列実行グループ |
| **Phase 1: 確認** | 1-3分 | AskUserQuestion実行、ユーザー回答確認 | 要求定義確定書 |
| **Phase 2: 実装** | 5-10分 | 並列実行グループ実装、品質ゲート全合格 | 全ファイル修正完了、検証合格 |

**Phase 1スキップ条件**: 曖昧性検出件数 = 0件

---

#### エラー種別検出パターン

| エラー種別 | 検出パターン | 主な原因 | 予防策 |
|-----------|------------|---------|--------|
| **KeyError** | `KeyError: 'key_name'` | API仕様未確認、返り値構造を仮定 | api-specification-check.md適用（Read実施） |
| **TypeError** | `TypeError: ...` | 型不一致、引数誤り | mypy型チェック、docstring確認 |
| **AttributeError** | `AttributeError: ...` | 存在しない属性参照 | Read実施、型ヒント確認 |

---

## 8. 更新履歴

| 日付 | 変更内容 | Phase | 担当 |
|------|---------|-------|------|
| 2026-02-07 | 初版作成（Task #22対応） | improvement-kpi-definition.md（未作成）準拠、実行可能チェックリスト化 | QA Expert Agent |

---

## 参考資料

### プロジェクト内ドキュメント

| ドキュメント | 用途 | アクセスパス |
|------------|------|------------|
| **improvement-kpi-definition.md** | KPI定義・測定手順 | `.claude/rules/workflow/improvement-kpi-definition.md`（未作成 — Task #19予定） |
| **api-specification-check.md** | API仕様確認プロセス | `.claude/rules/workflow/api-specification-check.md` |
| **execution-efficiency.md** | 実行効率化ワークフロー | `.claude/rules/workflow/execution-efficiency.md` |
| **requirement-clarification.md** | 要求定義明確化プロセス | `.claude/rules/workflow/requirement-clarification.md` |
| **quality-gates.md** | 品質ゲート基準 | `.claude/rules/testing/quality-gates.md` |
| **daily_progress.md** | 日次進捗記録 | `docs/progress/daily_progress.md` |

### 関連タスク

- **Task #19**: KPI定義書作成（improvement-kpi-definition.md — 未作成）
- **Task #20**: 3ドキュメント統合レビュー（整合性確認）
- **Task #21**: 効果測定レポート作成（Phase 1実測値サマリー）
- **Task #23**: CLAUDE.md開発ワークフロー統合（Phase 0/1/2の標準化）

---

**Note**: 本チェックリストは、improvement-kpi-definition.md（未作成 — Task #19予定）定義のKPIを実行可能な形式に変換したものです。毎タスク実施時に全セクションを実行し、daily_progress.md記録の一貫性を確保してください。
