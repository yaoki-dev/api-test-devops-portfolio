# .claude/rules構造再編成＆CLAUDE.md軽量化計画

*作成日: 2026-02-03*
*更新日: 2026-02-05（v4.2: Phase 4品質検証追加）*
*ステータス: Draft → Reviewed → Critique Approved → v4 Updated → v4.1 Updated → **v4.2 Updated***
*見積り時間: 約4時間（安全策強化により+30分）*
*信頼度: 72% → 92% → 85% → 87% → **88%（test_strategy_details分離確定）***
*Reflexionスコア: 3.60/5.0 → 4.60/5.0*
*Critiqueスコア: 7.0/10（Multi-Agent Debate）*

---

## 📋 Critique改訂サマリー（v3）

**レビュー実施**: 2026-02-04 Multi-Agent Debate + LLM-as-a-Judge
**参加エージェント**: claude-code-guide, context-manager, general-purpose

### 主要な発見と対応

| Critical Issue | 対応状況 |
|---------------|---------|
| ロールバックがSerenaメモリを復元しない | ✅ Phase 5に追加 |
| worktree競合未対応 | ✅ Phase 1に追加 |
| バックアップ日付のみ（時刻なし） | ✅ タイムスタンプ形式変更 |
| .serena/バックアップ欠落 | ✅ Phase 1に追加 |
| 中間検証ゲートなし | ✅ Phase 2.5追加 |

### 公式仕様確認結果

- **サブディレクトリサポート**: ✅ 公式確認済み（再帰的自動読み込み）
- **優先度階層**: CLAUDE.md → .claude/rules/ → Serenaメモリ
- **コピー方式の妥当性**: ⚠️ 一時的互換性維持として許容、Phase 6での統合必須

---

## 1. 目的

### 1.1 背景
- CLAUDE.mdが49k chars（1200行）に肥大化
- オフセットマップと学習トリガーが低頻度使用にも関わらず常時読み込み
- .claude/rules/の構造が未整理

### 1.2 目標
1. .claude/rules/をドメイン別に再構成
2. Serenaメモリからルール系ファイルを.claude/rules/へ**コピー**（互換性維持）
3. オフセットマップと学習トリガーをSerenaメモリへ移行
4. CLAUDE.md 49k → 27k chars（45%削減）

### 1.3 重要な設計決定: @memory:参照互換性

**問題**: CLAUDE.md内に18箇所以上の@memory:参照が存在
- `@memory:coding_standards` (Line 24, 716, 868, 1137)
- `@memory:implementation_quality_gates` (Line 17, 25, 733, 868, 1140)
- `@memory:test_strategy` (Line 1160)
- `@memory:command_usage_guide` (Line 984, 1120)

**解決策**: **コピー方式を採用**（移動ではない）

| 方式 | メリット | デメリット |
|------|---------|-----------|
| **コピー方式（採用）** | 互換性維持、段階的移行可 | 一時的な重複 |
| 移行＋参照削除 | 重複なし | CLAUDE.md大幅書き換え必要 |

**移行戦略**:
1. Phase 2: Serenaメモリを.claude/rules/にコピー（Serena側は維持）
2. Phase 4: 検証完了後、CLAUDE.md内の@memory:参照を段階的に削除
3. 将来: Serenaメモリ側の重複ファイルを削除（Phase 6として別途実施）

---

## 2. 推奨アーキテクチャ

### 2.1 .claude/rules/構造（移行後）

```
.claude/rules/
├── principles/              # 汎用原則
│   └── PRINCIPLES.md        # SOLID, DRY, KISS等
├── workflow/                # ワークフロー
│   ├── RULES.md             # 汎用ワークフロー
│   └── command-usage.md     # コマンド使用ガイド
├── python/                  # Python固有
│   └── coding-standards.md  # コーディング規約
├── testing/                 # テスト関連
│   ├── test-strategy.md     # テスト戦略
│   └── quality-gates.md     # 品質ゲート
└── devops/                  # DevOps
    └── git-workflow.md      # Git運用（CLAUDE.mdから抽出）
```

### 2.2 Serenaメモリ（新規作成）

```
.serena/memories/
├── learning_offset_maps.md   # W6_PLAN_WEEK_MAP, DAY_MAP, get_week_from_day_w6_plan()
└── learning_triggers.md      # Trigger 1-7 詳細フロー
```

### 2.3 CLAUDE.md軽量化後

```markdown
## 学習トリガー（簡易参照）
検出キーワード: `学習開始`, `実装開始`, `学習記録`, `実装記録`, `週次振り返り`, `理解度確認`, `エラー記録`

詳細フロー: @memory:learning_triggers
オフセットマップ: @memory:learning_offset_maps
```

---

## 3. 実施手順

### Phase 1: 準備（40分）🔒

> **Critique改訂**: バックアップ範囲拡大、worktree確認追加、タイムスタンプ精度向上
> **v4改訂**: `/superpowers:using-git-worktrees`によるworktree + ブランチ作成統合（CLAUDE.md開発ワークフロー準拠）

**タスク**:

1. **バックアップタイムスタンプ設定**（🆕 v3追加）
   ```bash
   # 一意なタイムスタンプを変数に保存
   BACKUP_TS=$(date +%Y%m%d_%H%M%S)
   echo "$BACKUP_TS" > .migration_backup_timestamp
   echo "Backup timestamp: $BACKUP_TS"
   ```

2. **worktree状態確認**（🆕 v3追加 - Critical）
   ```bash
   # 並行作業中のworktreeを確認
   git worktree list
   # ⚠️ 警告: 並行Claude Codeセッションがある場合は通知必須
   # .claude/と.serena/は共有されるため、変更が即時影響
   ```

3. **完全バックアップ作成**（🔄 v3改訂）
   ```bash
   # .claude/バックアップ
   cp -r .claude .claude.backup.$BACKUP_TS

   # CLAUDE.mdバックアップ
   cp CLAUDE.md CLAUDE.md.backup.$BACKUP_TS

   # .serena/バックアップ（🆕 v3追加）
   cp -r .serena .serena.backup.$BACKUP_TS
   ```

4. **バックアップ検証**（🆕 v3追加）
   ```bash
   # バックアップファイル存在確認
   ls -la .claude.backup.$BACKUP_TS/
   ls -la .serena.backup.$BACKUP_TS/
   ls -la CLAUDE.md.backup.$BACKUP_TS

   # ファイル数カウント
   find .claude.backup.$BACKUP_TS -type f | wc -l
   find .serena.backup.$BACKUP_TS -type f | wc -l
   ```

5. **ディレクトリ構造作成**
   ```bash
   mkdir -p .claude/rules/{principles,workflow,python,testing,devops}
   ```

6. **現状サイズ計測**
   ```bash
   wc -l CLAUDE.md
   wc -c CLAUDE.md
   ```

7. **worktree + ブランチ作成**（🔄 v4改訂 - CLAUDE.md準拠）
   ```
   /superpowers:using-git-worktrees
   ```
   - スキルが自動で `origin/develop` から新ブランチ作成
   - worktreeディレクトリ: `.worktrees/claude-rules-restructure/`
   - ブランチ名: `feature/claude-rules-restructure`

   **重要**: worktree作成後は自動でそのディレクトリに移動
   ```bash
   # 確認コマンド
   pwd  # → .worktrees/claude-rules-restructure/
   git branch --show-current  # → feature/claude-rules-restructure
   ```

   > ⚠️ **注意**: .claude/ と .serena/ は元リポジトリと共有されるため、
   > バックアップはworktree作成**前**に実施済み（Step 1-4）

**完了条件**:
- [ ] バックアップ3点存在確認（.claude/, .serena/, CLAUDE.md）
- [ ] タイムスタンプファイル作成確認
- [ ] worktree状態確認済み（並行セッションなし）
- [ ] ディレクトリ作成完了
- [ ] worktreeで作業中（.worktrees/claude-rules-restructure/）
- [ ] feature branchで作業中

---

### Phase 2: ルールファイル移行（1時間）

**移行マトリクス**:

| 移行元 | 移行先 | サイズ |
|--------|--------|--------|
| .serena/memories/coding_standards.md | .claude/rules/python/coding-standards.md | 10KB |
| .serena/memories/implementation_quality_gates.md | .claude/rules/testing/quality-gates.md | 6KB |
| .serena/memories/test_strategy.md | .claude/rules/testing/test-strategy.md | 5KB |
| .serena/memories/test_strategy_details.md | **移行対象外（Serenaに残す）** | 9KB |
| .serena/memories/command_usage_guide.md | .claude/rules/workflow/command-usage.md | 16KB |
| .claude/rules/PRINCIPLES.md | .claude/rules/principles/PRINCIPLES.md | 3KB |
| .claude/rules/RULES.md | .claude/rules/workflow/RULES.md | 19KB |

**タスク**:
1. 各ファイルをコピー（移動ではなく、検証後に削除）
2. ファイル内の@memory:参照を更新（不要になる参照を削除）
3. 各ファイルの読み込み確認

> **Note（v4.1）**: `test_strategy_details.md`は移行対象外。理由:
> - トークン効率: 160行 vs 455行統合（65%削減）
> - 使用頻度: 概要=高頻度 / 詳細=低頻度
> - test-strategy.md内の`@memory:test_strategy_details`参照は維持

**完了条件**: 全ファイル配置完了、claude "SOLID原則とは"で認識確認

---

### Phase 2.5: 中間検証ゲート（10分）🆕

> **Critique改訂**: Go/No-Go判定ポイント追加

**目的**: Phase 3に進む前に、Phase 2の成果物を検証

**タスク**:

1. **ファイル配置確認**
   ```bash
   # 全ファイル存在確認
   for f in \
     .claude/rules/python/coding-standards.md \
     .claude/rules/testing/quality-gates.md \
     .claude/rules/testing/test-strategy.md \
     .claude/rules/workflow/command-usage.md \
     .claude/rules/principles/PRINCIPLES.md \
     .claude/rules/workflow/RULES.md; do
     [ -f "$f" ] && echo "✅ $f" || echo "❌ MISSING: $f"
   done
   ```

2. **Serenaメモリ動作確認**
   ```bash
   # @memory:参照が引き続き動作することを確認
   claude "@memory:coding_standards"
   # → 内容が表示されること（Serena側は維持されているため）
   ```

3. **Claude Code rules認識確認**
   ```bash
   # 新しい.claude/rules/構造が認識されるか
   claude "SOLID原則について説明して"
   # → principles/PRINCIPLES.mdの内容を参照すること
   ```

**Go/No-Go判定**:
- ✅ **Go**: 全ファイル存在 AND @memory:動作 AND rules認識 → Phase 3へ
- ❌ **No-Go**: 1項目でも失敗 → 調査・修正後に再検証

---

### Phase 3: 学習コンテンツSerena移行（1時間）

**3.1 Serenaメモリ作成**

**learning_offset_maps.md**:
- W6_PLAN_WEEK_MAP（CLAUDE.md Line 70-128から移行）
- W6_PLAN_DAY_MAP（CLAUDE.md Line 133-194から移行）
- get_week_from_day_w6_plan()（CLAUDE.md Line 201-290から移行）

**learning_triggers.md**:
- Trigger 1: 学習開始（CLAUDE.md Line 294-388から移行）
- Trigger 2: 実装開始
- Trigger 3: 学習記録
- Trigger 4: 実装記録
- Trigger 5: 週次振り返り
- Trigger 6: 理解度確認
- Trigger 7: エラー記録

**3.1.1 Serenaメモリ登録手順（重要）**

ファイル配置だけでは不十分。Serena MCPへの登録が必要:

```bash
# 1. ファイル作成
cp /path/to/learning_offset_maps.md .serena/memories/

# 2. Serena MCPでメモリ登録（Claude Code内で実行）
# write_memory()を使用してSerenaに登録
```

**Claude Code内での登録コマンド**:
```
Serena MCPのwrite_memory()を使用:
- メモリ名: learning_offset_maps
- メモリ名: learning_triggers
```

**検証コマンド**:
```bash
# 登録確認
claude "list_memories()"
# → learning_offset_maps, learning_triggers が表示されること

# 内容確認
claude "@memory:learning_triggers"
# → Trigger 1-7の内容が表示されること
```

**3.2 CLAUDE.md軽量化**

削除対象セクション:
- 「### 📋 週次オフセットマッピング」全体（約150行）
- 「### トリガー1-7」詳細フロー（約400行）

残す内容:
```markdown
## 🚀 学習・実装記録自動化トリガー

**検出キーワード**: `学習開始`, `実装開始`, `学習記録`, `実装記録`, `週次振り返り`, `理解度確認`, `エラー記録`

**詳細フロー**: @memory:learning_triggers
**オフセットマップ**: @memory:learning_offset_maps
```

**完了条件**:
- Serenaメモリ作成完了
- CLAUDE.md 27k chars以下
- @memory:参照で正常動作

---

### Phase 4: 検証（30分）

**4.1 機能検証**

| テスト項目 | コマンド | 期待結果 |
|------------|---------|---------|
| ルール認識 | `claude "DRY原則とは"` | PRINCIPLES.md内容を参照 |
| 品質ゲート | `claude "/commit"` | quality-gates.md適用 |
| トリガー動作 | `学習開始` | @memory:learning_triggers読み込み |
| オフセット参照 | `Week 3の内容を表示` | @memory:learning_offset_maps使用 |

**4.2 トークン効率検証**

```bash
# 変更後のCLAUDE.mdサイズ
wc -l CLAUDE.md
wc -c CLAUDE.md
# 期待: 約700行、27k chars以下
```

**4.3 回帰テスト**

- [ ] /commit コマンド動作
- [ ] /create-issue コマンド動作
- [ ] 品質ゲート実行
- [ ] @memory:参照全般

**4.4 品質検証（🆕 v4.2追加）**

検証結果のリフレクション・クリティークを実施:

```bash
/reflexion:reflect "deep reflect if less than 90% confidence. 日本語で簡潔に回答"
/reflexion:critique
```

- [ ] Reflexionスコア ≥ 4.0/5.0（80%）
- [ ] Critiqueスコア ≥ 7.0/10
- [ ] 重大な品質問題なし

**完了条件**: 全テスト合格 + 品質検証合格

---

### Phase 5: ロールバック（検証失敗時のみ）🔄

> **Critique改訂**: Serenaメモリクリーンアップ追加、タイムスタンプベース復元

**トリガー条件**: Phase 4の検証で1項目以上失敗

**完全復旧手順**:
```bash
# 0. バックアップタイムスタンプ取得
BACKUP_TS=$(cat .migration_backup_timestamp)
echo "Restoring from backup: $BACKUP_TS"

# 1. .claude/復元
rm -rf .claude
mv .claude.backup.$BACKUP_TS .claude

# 2. CLAUDE.md復元
rm CLAUDE.md
mv CLAUDE.md.backup.$BACKUP_TS CLAUDE.md

# 3. .serena/復元（🆕 v3追加）
rm -rf .serena
mv .serena.backup.$BACKUP_TS .serena

# 4. 新規作成Serenaメモリのクリーンアップ（🆕 v3追加）
# Phase 3で作成された場合のみ
rm -f .serena/memories/learning_offset_maps.md 2>/dev/null
rm -f .serena/memories/learning_triggers.md 2>/dev/null

# 5. Serena MCPからの登録解除（🆕 v3追加）
# Claude Code内で実行:
# delete_memory("learning_offset_maps")
# delete_memory("learning_triggers")

# 6. 復元確認
ls -la .claude/
ls -la .serena/
wc -c CLAUDE.md

# 7. 機能確認
claude "@memory:coding_standards"
claude "テスト: /commit動作確認"

# 8. タイムスタンプファイル削除
rm .migration_backup_timestamp
```

**部分ロールバック**（Phase 3のみ失敗時）:
```bash
# CLAUDE.mdのみ復元
BACKUP_TS=$(cat .migration_backup_timestamp)
rm CLAUDE.md
mv CLAUDE.md.backup.$BACKUP_TS CLAUDE.md

# 新規Serenaメモリ削除
rm -f .serena/memories/learning_offset_maps.md
rm -f .serena/memories/learning_triggers.md
# + Serena MCP delete_memory()実行
```

---

## 4. リスクと軽減策

> **Critique改訂**: worktree競合、バックアップ上書き、Serena登録失敗リスク追加

| リスク | 影響 | 確率 | 軽減策 |
|--------|------|------|--------|
| @memory:参照エラー | トリガー動作不全 | 低 | 段階的移行、各Phase検証 |
| ルール優先度競合 | 意図しない上書き | 中 | ドメイン別分離で競合回避 |
| 移行漏れ | 機能欠落 | 低 | チェックリストで確認 |
| **worktree競合**（🆕） | 並行セッションでデータ破損 | 中 | Phase 1で`git worktree list`確認必須 |
| **バックアップ上書き**（🆕） | 同日再実行で旧バックアップ消失 | 低 | タイムスタンプに時刻追加（%H%M%S） |
| **Serena MCP登録失敗**（🆕） | @memory:参照不可 | 低 | `list_memories()`で登録確認 |
| **部分Phase失敗**（🆕） | 不整合状態 | 低 | Phase 2.5中間検証ゲート追加 |

---

## 5. 成果物チェックリスト

- [ ] .claude/rules/ドメイン別構造完成
- [ ] Serenaメモリ（learning_offset_maps.md, learning_triggers.md）作成
- [ ] CLAUDE.md軽量化（45%削減）
- [ ] 全機能検証完了
- [ ] バックアップ削除（検証完了後）

---

---

## 6. CRITICAL RULES準拠確認

**CLAUDE.md Line 8-25の必須ルールとの整合性**:

| CRITICAL RULE | 本プランでの対応 |
|---------------|-----------------|
| 1. todowriteでタスクリスト作成 | ✅ 実行前にtodowrite必須 |
| 3. git commitではなく/commit使用 | ✅ 変更後は/commitで |
| 6. 品質ゲート通過 | ✅ Phase 4で検証 |
| 7. protected branch直接push禁止 | ✅ feature branchで作業 |
| 11. /reflexion:reflect実行 | ✅ 本プランで実施済み |

**実行前チェックリスト**:
- [ ] `todowrite`でタスクリスト作成済み
- [ ] feature branchで作業中
- [ ] 品質ゲート通過確認（Phase 4）
- [ ] `/commit`でコミット
- [ ] `/reflexion:reflect`実行済み（本プランで完了）

---

## 7. トークン削減内訳

**現状**: CLAUDE.md 49k chars（1191行）

**削減対象**:
| セクション | 行数 | chars | 削減率 |
|-----------|------|-------|--------|
| W6_PLAN_WEEK_MAP | 60行 | ~2.5k | 5% |
| W6_PLAN_DAY_MAP | 60行 | ~2.5k | 5% |
| get_week_from_day_w6_plan() | 90行 | ~3.5k | 7% |
| Trigger 1-7詳細 | 400行 | ~16k | 33% |
| **合計** | **610行** | **~24.5k** | **50%** |

**移行後予測**: 49k - 24.5k = **24.5k chars**（目標27k以下達成）

**残留内容**（~5行、200 chars）:
```markdown
## 学習トリガー
検出キーワード: 学習開始, 実装開始, 学習記録, 実装記録, 週次振り返り, 理解度確認, エラー記録
詳細: @memory:learning_triggers
マップ: @memory:learning_offset_maps
```

---

## 付録A: 参照ドキュメント

- 分析セッション: 2026-02-03
- Claude Code公式: `.claude/rules/`自動読み込み仕様
- @memory:coding_standards
- @memory:implementation_quality_gates

---

## 付録B: @memory:参照影響分析

**移行対象ファイルのCLAUDE.md内参照箇所**:

| @memory: | 参照箇所（Line） | 移行後の対応 |
|----------|-----------------|--------------|
| coding_standards | 24, 716, 868, 1137 | Phase 4検証後に削除可 |
| implementation_quality_gates | 17, 25, 733, 868, 1140 | Phase 4検証後に削除可 |
| test_strategy | 1160 | Phase 4検証後に削除可 |
| command_usage_guide | 984, 1120 | Phase 4検証後に削除可 |

**互換性維持期間**: Phase 4検証完了まで（約3.5時間）

**将来Phase 6（別途計画）**:
- CLAUDE.md内の@memory:参照削除
- Serenaメモリ側の重複ファイル削除
- 推定追加作業: 1時間

---

## 付録C: Reflexion改訂履歴

| バージョン | スコア | 主な改訂内容 |
|-----------|--------|-------------|
| v1 (Draft) | 3.60/5.0 | 初版作成 |
| v2 (Reviewed) | 4.60/5.0 | @memory:互換性戦略追加、Serena登録手順追加、CRITICAL RULES準拠セクション追加、トークン削減内訳追加 |
| v3 (Critique Approved) | 7.0/10 | Multi-Agent Debate実施、Phase 1安全策強化（.serena/バックアップ、worktree確認、タイムスタンプ精度向上）、Phase 2.5中間検証ゲート追加、Phase 5ロールバック完全化（Serenaクリーンアップ追加）、リスクテーブル4項目追加、公式仕様確認結果追記 |
| v4 (Updated) | 87% | Phase 1: `/superpowers:using-git-worktrees`によるworktree + ブランチ作成統合（CLAUDE.md開発ワークフロー準拠）、完了条件にworktree確認追加 |
| v4.1 (Updated) | 88% | Phase 2: `test_strategy_details.md`を移行対象外と明記（トークン効率65%削減、Progressive Disclosure原則準拠） |
| **v4.2 (Updated)** | **88%** | 🆕 Phase 4: 品質検証ステップ追加（/reflexion:reflect + /reflexion:critique、閾値: Reflexion≥4.0、Critique≥7.0） |

---

## 付録D: Multi-Agent Critique結果（🆕 v3）

**実施日時**: 2026-02-04 19:15 GMT+7
**パターン**: Multi-Agent Debate + LLM-as-a-Judge

### 参加エージェント

| Agent | Role | Score |
|-------|------|-------|
| claude-code-guide | 公式仕様検証 | 8.5/10 |
| context-manager | プラン整合性検証 | 7.5/10 |
| general-purpose | フォールバック・安全策検証 | 5.0/10 |
| **Overall** | **Consensus** | **7.0/10** |

### 公式仕様確認結果

**Source**: [Manage Claude's memory - Claude Code Docs](https://code.claude.com/docs/en/memory.md)

| 項目 | 確認結果 |
|------|---------|
| サブディレクトリサポート | ✅ 公式サポート（再帰的発見） |
| 自動読み込み | ✅ 確認済み |
| 優先度階層 | CLAUDE.md → .claude/rules/ → Serena（推定） |
| YAMLフロントマター | ✅ `paths:`フィールドサポート |
| シンボリックリンク | ✅ サポート |

### 合意事項

1. ディレクトリ構造は公式仕様準拠
2. ロールバック手順に重大な欠陥あり → 修正済み
3. worktree競合は未対応 → 修正済み
4. コピー方式は一時的措置として妥当、Phase 6統合必須

### 残存リスク（許容済み）

- Serena統合の公式仕様が未定義（テストで確認予定）
- 信頼度85%は保守的見積もり（実行時検証で向上予定）
