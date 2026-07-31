---
paths:
  - "**/*.py"
---

# プロジェクト品質ゲート基準

*最終更新: 2026-07-31*

## 目的

「実装活動」の認定基準を定義。RULES.md「Implementation Integrity」の具体化版。

---

## 実装活動認定条件（全て合格必須）

### Gate 1: pytest合格

```bash
uv run pytest -m "(unit or integration) and not external" --cov=utils --cov=config --cov=models
```

- 全テストケース合格（0 failed）
- カバレッジ下限達成（下限値は `pyproject.toml` の `--cov-fail-under`）
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
uv run mypy utils/ config/ models/ tests/conftest.py
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

`.claude/CLAUDE.md` Section「品質ゲート」→「統合コマンド」を使用する（本ファイルには複製しない）。

Gate 4 の確認は以下を使用する。`git status` 単体では未コミット変更の有無を終了コードで表現できず、コミットメッセージの形式も判別できない。未追跡ファイルは自動判定できないため合格基準に含めず、本チェックの対象外とする（目視確認の手順は `@memory:implementation_quality_gates` Gate 4 の「補足」を参照）。

```bash
git diff --quiet && git diff --cached --quiet && \
  git log -1 --pretty=%s | rg -q '^(feat|fix|test|docs|refactor|chore|perf|ci|security)(\(.+\))?!?: '
```

---

## 品質ゲート不合格時の対応

1. **Gate 1失敗**: テスト修正・コード修正 → 再実行
2. **Gate 2失敗**: `ruff --fix` → 手動修正 → 再実行
3. **Gate 3失敗**: 型ヒント追加 → 再実行
4. **Gate 4未完了**: `Skill(commit)`スキル実行

**フロー**: 実装完了 → 品質ゲート実行 → 全Gate合格 → 実装活動認定

---

## 変更履歴

| 日付 | 変更内容 |
|------|---------|
| 2025-11-14 | 初版作成 |
| 2025-12-27 | 参照更新 |
| 2026-02-05 | Gate 4: /commit必須化 |
| 2026-02-10 | 簡潔化（221行→90行） |
| 2026-07-30 | paths frontmatter追加（遅延ロード化）、コマンドを `.claude/CLAUDE.md`「統合コマンド」参照に統一、削除済みの日次進捗ファイルへの参照を除去 |
| 2026-07-31 | Gate 1 のコマンドから展開不能プレースホルダ `--cov-fail-under=[Phase別目標]` を除去（下限は `pyproject.toml` の `addopts` が単一真実源） |

---

## 参考

- RULES.md「Implementation Integrity」
- `.claude/rules/python/coding-standards.md`
- `.claude/rules/testing/test-strategy.md`
