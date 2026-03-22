# プロジェクト品質ゲート基準

*最終更新: 2026年02月10日*

## 目的

「実装活動」の認定基準を定義。RULES.md「Implementation Integrity」の具体化版。

---

## 実装活動認定条件（全て合格必須）

### Gate 1: pytest合格

```bash
uv run pytest --cov=utils --cov=config --cov=models --cov-fail-under=[Phase別目標]
```

- 全テストケース合格（0 failed）
- カバレッジ目標達成（Phase別）
- 不合格時: `--cov-report=term-missing`で未カバー箇所特定

---

### Gate 2: ruff合格

```bash
uv run ruff check --fix .
```

- ruff検出エラー: 0件
- 自動修正適用済み
- 不合格時: 手動対応

---

### Gate 3: mypy合格

```bash
uv run mypy utils/ config/ models/
```

- 型エラー: 0件
- 全関数に型ヒント（`disallow_untyped_defs = true`）
- 不合格時: 型ヒント追加

---

### Gate 4: git commit実行済み

- 変更がgit commitされている（`Skill(commit)`スキル使用、**生 `git commit` 禁止**）
- Conventional Commits形式（`feat:`/`fix:`/`test:`/`docs:`/`refactor:`/`chore:`/`perf:`/`ci:`/`security:`）

---

## 統合検証コマンド

```bash
uv run pytest -n auto --cov-fail-under=[目標] && uv run ruff check . && uv run mypy utils/ config/ models/ && git status
```

---

## 品質ゲート不合格時の対応

1. **Gate 1失敗**: テスト修正・コード修正 → 再実行
2. **Gate 2失敗**: `ruff --fix` → 手動修正 → 再実行
3. **Gate 3失敗**: 型ヒント追加 → 再実行
4. **Gate 4未完了**: `Skill(commit)`スキル実行

**フロー**: 実装完了 → 品質ゲート実行 → 全Gate合格 → 実装活動認定

---

## 実装活動記録

品質ゲート合格後、`docs/progress/daily_progress.md`に記録。

**記録フォーマット**: @memory:learning_triggers 参照

---

## 変更履歴

| 日付 | 変更内容 |
|------|---------|
| 2025-11-14 | 初版作成 |
| 2025-12-27 | 参照更新 |
| 2026-02-05 | Gate 4: /commit必須化 |
| 2026-02-10 | 簡潔化（221行→90行） |

---

## 参考

- RULES.md「Implementation Integrity」
- `.claude/rules/python/coding-standards.md`
- `.claude/rules/testing/test-strategy.md`
