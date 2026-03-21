---
paths:
  - "claudedocs/plans"
  - "~/.claude/plans"
---

# PLANS.md - 計画文書テンプレート

*最終更新: 2026-03-05*

## 概要・役割分担

このファイルはタスク計画文書のテンプレートを定義する。
実行効率化の詳細は `@memory:execution-efficiency` を参照。

| ツール/ファイル | 用途 | スコープ |
|--------------|------|---------|
| **本テンプレート** | フィーチャー単位の計画・決定記録 | Within-task |
| **execution-efficiency.md** | 実行効率化・並列判定の手法詳細 | How to execute |
| **TodoWrite** | セッション内タスク進捗UI表示 | 揮発性 |
| **~/.claude/tasks/todo.md** | 大規模タスクの永続追跡 | Cross-session |
| **lessons.md** (Rule 15) | セッション横断の教訓蓄積 | Cross-project |

### 使用閾値

本テンプレートを使用する条件（いずれか1つ以上）:

- 設計上の判断（AskUserQuestion）が必要
- アーキテクチャ / 既存動作に影響する変更
- TodoWrite で3タスク以上 **かつ 機械的でない**（同型処理の繰り返しでない）

スキップ可能: 単純バグ修正・同型テスト追加・1ファイル以内の自明な変更

---

## セクション定義

### [必須] Purpose

1文でユーザーが得る観測可能な利益を記述。
「コードを追加した」ではなく「URL返却でHTTP 200が返る」形式。

---

### [必須] Progress

ISO 8601 タイムスタンプ付きチェックボックス。
TodoWrite の各タスクと 1対1 対応させること。

- [ ] (YYYY-MM-DDTHH:MMZ) 未完了ステップ
- [x] (2026-03-02T03:00Z) 完了ステップ

---

### [必須] Decision Log

AskUserQuestion の回答・設計判断を記録する。
**@memory:参照は推奨。外部ブログリンクによる情報委譲は禁止。**

| 決定 | 根拠 | 日付 |
|------|------|------|
| （例）PLANS.mdを .claude/rules/ に配置 | rules/ は他ルールファイルと同一管理下 | 2026-03-02 |

---

### [推奨] Context and Orientation

リポジトリの状態・前提条件を記述。
→ `@memory:execution-efficiency` Phase 0（分析フェーズ）の成果物として作成。

- リポジトリ現状
- 関連する既存コード・ファイル
- 前提条件・依存関係

---

### [推奨] Plan of Work

散文形式で実装の順序・内容を記述。
→ `@memory:execution-efficiency` Phase 0 の並列化判定後に作成。

---

### [推奨] Validation and Acceptance

観測可能な受け入れ基準を実装タイプ別に記述。

**コード実装（.py 変更）**:

- [ ] `uv run pytest -n auto -m "(unit or integration) and not external"` 全pass
- [ ] `uv run ruff check .` エラー0件
- [ ] `uv run mypy utils/ config/ models/` エラー0件
- [ ] `Skill(fact-checker)` (証拠ベースの事実検証)
- [ ] `Skill(superpowers:verification-before-completion)`（全タスク完了確認 — 未完了検出時: 修正 → 品質ゲート → 再実行 - 最大3回まで）
- [ ] `Skill(reflexion:reflect)` （信頼度90%以上）
- [ ] `/code-review:review-local-changes`（80点閾値通過）

**ドキュメント実装（.md 変更）**:

- [ ] `npm run lint:md && npm run lint:text` 全pass
- [ ] `/superpowers:verification-before-completion`（全タスク完了確認 — 未完了検出時: 修正 → 品質ゲート → 再実行 - 最大3回まで）
- [ ] `/reflexion:reflect`（信頼度90%以上）
- [ ] `/pr-review-toolkit:review-pr`
- ※ PRレビューは CLAUDE.md Step 8 ELSE節（`/pr-review-toolkit:review-pr`）に委譲

**設定ファイル変更（*.yml / pyproject.toml / config/）**:

- ⚠️ 前提条件: Rule 16（❌確認必要ファイルリスト: CLAUDE.md Rule 16参照）と照合 + AskUserQuestion でユーザー確認
- [ ] 変更前後で該当テスト合格（pytest / CI実行確認）
- [ ] `npm run lint:md && npm run lint:text`（Markdownドキュメント品質チェック）

---

### [Optional] Surprises & Discoveries

予期しない動作・バグ・最適化の発見。
→ lessons.md（Rule 15）への記録候補をここに一時保管する。

---

### [Optional] Concrete Steps

実行コマンド・カレントディレクトリ・期待される出力例。
→ `@memory:execution-efficiency` Phase 2（実装フェーズ）と連携。

---

### [Optional] Outcomes & Retrospective

完了後に記入: 成果・未完了事項・学習。
**→ lessons.md（Rule 15）へ転記するトリガーとして使用。**

---

## 品質ルール（必守）

1. **観測可能な成果**: 受け入れ基準はユーザー体験で記述
2. **べき等性**: 全ステップは複数回実行しても安全であること
3. **自己完結性**: @memory:参照は推奨。外部ブログ委譲は禁止
4. **生きた文書**: 発見・設計変更はその都度更新すること

---

## ファイル命名・保存先

```
claudedocs/plans/YYYY-MM-DD-<topic>.md   # フィーチャー別計画
~/.claude/tasks/todo.md                  # 大規模タスク併用
```

---

## 参照

- `@memory:execution-efficiency` - 実行効率化詳細（Phase 0/1/2）
- `.claude/rules/workflow/RULES.md` - Planning Efficiency ルール
- `~/.claude/tasks/lessons.md` - Rule 15 教訓蓄積ファイル
