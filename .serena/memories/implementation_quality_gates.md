# プロジェクト品質ゲート基準

*最終更新: 2026年02月05日*

## 目的

このドキュメントは、api-test-devops-portfolioプロジェクトにおける「実装活動」の認定基準を定義します。RULES.md「Implementation Integrity」カテゴリの具体化版として、定量的な品質ゲートを提供します。

---

## 実装活動認定条件（全て合格必須）

実装コード・テスト・設定ファイルの作成が「実装活動」として認定されるには、以下の**4つの品質ゲート全て**に合格する必要があります。

### ✅ Gate 1: pytest合格

**検証コマンド**:
```bash
uv run pytest --cov=utils --cov=config --cov=models --cov-fail-under=[Phase別目標]
```

**合格基準**:
- 全テストケース合格（0 failed）
- カバレッジ目標達成（Phase別、下記参照）
- テストマーカー別実行も合格（unit, integration）


**不合格時の対応**:
- テスト失敗: 失敗原因を特定し、コード修正またはテスト修正
- カバレッジ不足: 未カバー箇所を特定（`--cov-report=term-missing`）し、テスト追加

---

### ✅ Gate 2: ruff合格（コードスタイル・品質）

**検証コマンド**:
```bash
uv run ruff check --fix .
```

**合格基準**:
- ruff検出エラー: 0件
- 自動修正可能な警告: 全て修正済み（`--fix`適用）
- 行長制限: 100文字以内（pyproject.toml設定）

**ruffチェック項目**:
- インポート順序（isort統合）
- 命名規則（snake_case、PascalCase）
- 未使用変数・インポート
- コードスタイル（PEP 8準拠）

**不合格時の対応**:
- `uv run ruff check --fix .` で自動修正
- 修正不可エラーは手動対応

---

### ✅ Gate 3: mypy合格（型チェック）

**検証コマンド**:
```bash
uv run mypy utils/ config/ models/
```

**合格基準**:
- 型エラー: 0件
- 全ての関数・メソッドに型ヒント（`disallow_untyped_defs = true`）
- 戻り値の型明示

**mypyチェック項目**:
- 型ヒント欠落検出
- 型の不一致検出
- Optional型の適切な使用

**不合格時の対応**:
- 型ヒント追加（引数・戻り値）
- 型の不整合修正

---

### ✅ Gate 4: git commit実行済み

**検証コマンド**:
```bash
git status
git log -1 --oneline
```

**合格基準**:
- 変更がgit commitされている
- コミットメッセージが意味を持つ（`feat:`, `fix:`, `test:` 等のprefix使用）
- Untracked filesが実装成果物のみ（一時ファイルは除外）

**Conventional Commits形式**:
```
feat: 新機能追加
fix: バグ修正
test: テスト追加・修正
docs: ドキュメント更新
refactor: リファクタリング
chore: ビルド・設定変更
perf: パフォーマンス改善
ci: CI/CD設定変更
security: セキュリティ修正
```

**不合格時の対応**:
- 未コミット: `git add` + `Skill(commit)` スキル使用（**生 `git commit` 禁止** - CLAUDE.md CRITICAL RULE #4）
- 一時ファイル混入: `.gitignore`追加、`git rm --cached`で除外

---

## 統合検証コマンド（全ゲート一括実行）

**ワンライナー**:
```bash
uv run pytest -n auto --cov-fail-under=[目標] && \
uv run ruff check . && \
uv run mypy utils/ config/ models/ && \
git status
```

**成功例**（※数値は実行時点の例）:
```
===== test session starts =====
collected 401 items

tests/unit/test_api_client.py ...................... [ 15%]
tests/unit/test_async_client.py .................... [ 30%]
tests/integration/test_api_integration.py .......... [ 45%]
...
===== 401 passed in 12.34s =====

Coverage: 83% (target: 85%) ✅

ruff check: 0 errors ✅
mypy: Success: no issues found ✅

On branch local/history
nothing to commit, working tree clean ✅

🎉 全ての品質ゲート合格！実装活動認定
```

---

## 品質ゲート不合格時のフロー

```
実装完了
  ↓
品質ゲート実行
  ↓
Gate 1 (pytest) → 失敗?
  ├─ YES → テスト修正・コード修正 → 再実行
  └─ NO → Gate 2へ
  ↓
Gate 2 (ruff) → 失敗?
  ├─ YES → ruff --fix実行・手動修正 → 再実行
  └─ NO → Gate 3へ
  ↓
Gate 3 (mypy) → 失敗?
  ├─ YES → 型ヒント追加 → 再実行
  └─ NO → Gate 4へ
  ↓
Gate 4 (git commit) → 未コミット?
  ├─ YES → Skill(commit) 実行 → 再確認
  └─ NO → 実装活動認定 ✅
```

---

## 実装活動記録フォーマット

品質ゲート合格後、`docs/progress/daily_progress.md`に以下を記録：

```markdown
### YYYY-MM-DD (曜日)

#### 🛠️ ポートフォリオ実装進捗

**品質ゲート（実装活動判定）**:
- [x] pytest合格（カバレッジ: 62% / 目標60%）
- [x] ruff合格（0 errors）
- [x] mypy合格（0 errors）
- [x] git commit実行済み（commit: a1b2c3d）

**実装活動認定**: ✅ 認定

**完了タスク**:
- [x] Docker 4-stage実装
- [x] docker-compose dev環境構築

**メトリクス変化**（※数値は例）:
- カバレッジ: 80% → 83%
- テスト数: 395 → 401
- Docker実装: 80% → 90%

**成果物**:
- git commit: a1b2c3d
- 変更行数: +234/-12
- 変更ファイル数: 8
```

---

## 品質ゲート基準の変更履歴

| 日付 | 変更内容 | 理由 |
|------|---------|------|
| 2025-11-14 | 初版作成 | RULES.md「Implementation Integrity」の具体化 |
| 2025-12-27 | 参照更新 | test_strategy統合に伴う参照先更新 |
| 2026-02-05 | CLAUDE.md整合性修正 | Gate 4: /commit必須化、Conventional Commits追加（perf/ci/security） |

---

## 参考リソース

- **RULES.md**: .claude/rules/workflow/RULES.md「Implementation Integrity」セクション
- **coding_standards**: .claude/rules/python/coding-standards.md
- **test_strategy**: .claude/rules/testing/test-strategy.md
- **test_strategy_details**: @memory:test_strategy_details（Serena MCP経由）
- **ポートフォリオ戦略**: docs/プロジェクト再編/ポートフォリオ戦略.md
