# 出力品質基準 詳細ガイド

*最終更新: 2026年02月13日*

## 概要

この文書は、Claude Code 開発セッションにおける「出力品質基準」の実装ガイドを提供します。4段階品質チェック + 文字数基準により、一貫した品質を実現します。

---

## 1. 4段階品質チェック

**全段階合格が必須**。不合格時の Recovery フローは Section 3 参照。

### 段階1: pytest合格

```bash
# 基本実行
uv run pytest --cov=utils --cov=config --cov=models --cov-fail-under=76

# カバレッジ詳細確認（未カバー箇所表示）
uv run pytest --cov-report=term-missing --cov-fail-under=76

# HTML レポート（詳細分析時）
uv run pytest --cov-report=html && open reports/htmlcov/index.html
```

**合格条件**:
- 全テストケース合格（0 failed）
- カバレッジ目標達成（現在: 76%）
- 外部API テストは CI/CD のみ（ローカルは除外）

**不合格時**: `--cov-report=term-missing` で未カバー箇所特定 → テスト追加

---

### 段階2: ruff合格

```bash
# チェック + 自動修正
uv run ruff check --fix .

# フォーマット適用
uv run ruff format .

# リンター警告確認（修正後）
uv run ruff check .
```

**合格条件**:
- ruff検出エラー: 0件
- 自動修正実施済み
- manual review 対象エラーなし

**不合格時**:
1. `--fix` で自動修正試行
2. 修正されないエラー → 手動対応
3. 再度 `ruff check` で確認

---

### 段階3: mypy合格

```bash
# 標準実行
uv run mypy utils/ config/ models/

# エラーコード付き（詳細）
uv run mypy --show-error-codes --pretty utils/ config/ models/

# strict mode（完全検証）
uv run mypy --strict utils/ config/ models/
```

**合格条件**:
- 型エラー: 0件
- 全関数に型ヒント（`disallow_untyped_defs = true`）
- `Any` 型の過度な使用なし

**不合格時**:
1. エラー箇所に型ヒント追加
2. 曖昧な型は `Union[X, Y]` または `X | Y` で明示
3. 再実行で確認

---

### 段階4: Git commit実行済み

```bash
# 状態確認（コミット前）
git status

# コミット（スキル使用・生コマンド禁止）
# IMPORTANT: /commit スキルを使用（git commit 禁止）
# Skill tool で invoke してください
```

**合格条件**:
- 変更が git commit されている
- Conventional Commits 形式: `type(scope): subject`
- スキル `/commit` 使用（生 `git commit` 厳禁）

**形式例**:
- `feat(api): ユーザー取得エンドポイント追加`
- `fix(client): タイムアウト処理修正`
- `test(async): 非同期テスト追加`
- `docs(readme): セットアップ手順更新`

---

## 2. 出力文字数基準

### 2.1 「簡潔」（600-900字）

**根拠**: Google Technical Writing Center 中央値 + TC協会推奨

| 項目 | 詳細 |
|-----|------|
| **適用対象** | 技術ドキュメント、計画書、簡潔なレポート |
| **使用シーン** | PR説明、issue説明、実装計画、簡潔な報告 |
| **構成** | 背景(150字) → 方針(200字) → 実装(250字) → 結論(100字) |
| **検証方法** | `wc -w`（英語）/ `wc -m`（日本語） |
| **例** | Feature Branch での実装計画、バグ fix レポート |

---

### 2.2 「詳細」（1,500-3,000字）

**根拠**: JIS X 0121 標準ドキュメント長 + Chicago Manual of Style

| 項目 | 詳細 |
|-----|------|
| **適用対象** | アーキテクチャ設計、仕様書、複雑なガイド |
| **使用シーン** | 複雑な機能説明、技術選定理由、設計決定文書 |
| **構成** | 概要(250字) → 背景(400字) → 実装(800字) → 結論(250字) |
| **検証方法** | `wc -w`（英語）/ `wc -m`（日本語） |
| **例** | API仕様設計、DevOps統合ガイド |

---

### 2.3 「包括的」（4,000-6,000字）

**根拠**: 実測 CLAUDE.md (5,400字) + Chicago Article standard

| 項目 | 詳細 |
|-----|------|
| **適用対象** | 最終レポート、完全なガイド、マニュアル |
| **使用シーン** | 最終的なドキュメント、完全なナレッジベース |
| **構成** | 導入(400字) → 各セクション(1,500字×2) → 参考(500字) |
| **検証方法** | `wc -w`（英語）/ `wc -m`（日本語） |
| **例** | 学習総括、完全なAPI リファレンス |

---

## 3. Recovery フロー

**品質基準に達しない場合の対応手順**:

```
出力完成
  ↓
段階1: pytest 実行
  ├─ 合格 → 段階2 へ
  └─ 不合格 → pytest -vv で詳細確認 → テスト修正 → 再実行

段階2: ruff 実行
  ├─ 合格 → 段階3 へ
  └─ 不合格 → ruff --fix . → 手動修正 → 再実行

段階3: mypy 実行
  ├─ 合格 → 段階4 へ
  └─ 不合格 → 型ヒント追加 → 再実行

段階4: git commit 実行
  ├─ 合格 → 品質ゲート全合格 ✓
  └─ 未実行 → /commit スキル実行
```

---

## 4. 参照ドキュメント

- **実装品質ゲート**: @memory:implementation_quality_gates
- **品質ゲート定義**: quality-gates.md
- **コーディング規約**: @memory:coding_standards
- **開発ワークフロー**: CLAUDE.md「🔄 開発ワークフロー」セクション

---

## 5. 検証チェックリスト

**毎セッション実施** (実装完了後):

- [ ] 「簡潔」出力は 600-900字に収まるか（`wc -m` で確認）
- [ ] 「詳細」出力は 1,500-3,000字に収まるか
- [ ] テストが全て合格したか（`pytest --cov-fail-under=76`）
- [ ] リンターエラーが 0 件か（`ruff check .`）
- [ ] 型エラーが 0 件か（`mypy utils/ config/ models/`）
- [ ] Conventional Commits 形式で commit したか（`/commit` スキル）
