# コマンド・Plugin・スキル使い分けガイド

*最終更新: 2026年02月18日*
*用途: ワークフロー駆動型の最適ツール選択ガイド - コマンド/Plugin/スキル/エージェントの使い分け*
*対象: 仕様駆動開発、マルチエージェントオーケストレーション活用プロジェクト*
*アクセス頻度: 高（開発タスク開始時、ワークフロー設計時、ツール選択時）*

## 📚 目次

**このガイドの役割**: 3つのカタログ（AGENTS/COMMANDS/SKILLS）の「辞書的参照」に対し、本ガイドは「ワークフロー駆動の使い分け」を提供します。

6. [コマンド削除時チェックリスト](#6-コマンド削除時チェックリスト)
8. [関連ドキュメント](#8-関連ドキュメント)
9. [ast-grep / mgrep 使用ガイド](#9-ast-grep--mgrep-使用ガイド) 🆕

---

## 6. コマンド削除時チェックリスト

**目的**: Slashコマンド削除後の参照整合性を確保するための即時チェック手順

### チェック対象

| スコープ | 対象パス | 影響範囲 |
|---------|---------|---------|
| プロジェクトローカル | `docs/`, `.serena/memories/` | 当該プロジェクトのみ |
| グローバル設定 | `~/.claude/` | **全プロジェクト** |

### 実行手順

#### Step 1: 削除コマンド名を変数化
```bash
# 例: /docs を削除した場合
DELETED_CMD="docs"
```

#### Step 2: プロジェクトローカルチェック
```bash
grep -rn "$DELETED_CMD" docs/ .serena/memories/
```

#### Step 3: グローバル設定チェック（重要）
```bash
# debug/ディレクトリはログファイルのため除外
grep -rn "$DELETED_CMD" ~/.claude --include="*.md" | grep -v "/debug/"
```

**教訓**: プロジェクトローカルのみクリーンアップし、グローバル設定を見落としやすい。Step 3のグローバルチェックを忘れずに実行すること。

---

## 8. 関連ドキュメント

### 3大カタログ（辞書的参照）

本ガイドと3大カタログの役割分担:

| ドキュメント | 役割 | 更新頻度 | 主な用途 |
|------------|------|---------|---------|
| **本ガイド (command_usage_guide.md)** | **ワークフロー駆動の使い分け** | 中（機能追加時） | 開発フェーズ別の最適ツール選択 |
| **AGENTS_CATALOG.md** | エージェント全項目辞書 | 低（エージェント追加時） | エージェント仕様の詳細確認 |
| **COMMANDS_CATALOG.md** | コマンド全項目辞書 | 低（コマンド追加時） | コマンドオプション・引数の確認 |
| **SKILLS_CATALOG.md** | スキル全項目辞書（693件） | 低（スキル追加時） | スキル発動条件・機能の確認 |

### アクセスパス

```bash
# グローバル設定
~/.claude/docs/AGENTS_CATALOG.md    # 69エージェント（44ローカル + 19プラグイン + 6プロジェクト）
~/.claude/docs/COMMANDS_CATALOG.md  # 80コマンド（SuperClaude Framework）
~/.claude/docs/SKILLS_CATALOG.md    # 695スキル（32ユーザー + 663プラグイン）

# プロジェクト固有
.serena/memories/command_usage_guide.md  # 本ガイド（ワークフロー駆動）
.claude/rules/workflow/RULES.md          # 行動ルール
.claude/rules/principles/PRINCIPLES.md   # 基本原則
```

---

## 更新履歴

| 日付 | 変更内容 | Phase |
|------|---------|-------|
| 2026-01-28 | 初版作成（コマンド使用ガイド） | - |
| 2025-12-29 | CLAUDE.md から superpowers セクション移行 | - |
| 2025-12-31 | CLI版→MCP版移行（26ファイル削除） | - |
| 2026-02-06 | ワークフロー駆動型ガイドに改編 | Phase 1-2 |
| 2026-02-06 | 見出し修正・3大カタログ相互参照追加 | Phase 1-2 |
| 2026-02-06 | 優先度1-2修正完了（用語分類修正、証拠ベース分析表形式化、/git:feature, /git:hotfix削除） | Phase 1-2 |
| 2026-02-06 | Section番号重複修正（4→5繰り下げ）、Section 2マトリクスに/scaffold, /test-coverage, /generate-tests追加、Section 5にCCPlugins説明追記 | Phase 2完了 |
| 2026-02-06 | 目次-本文Section番号整合性修正（7→6, 8→7, 9→8）、目次リンクタイトル更新 | 最終検証 |
## 9. ast-grep / mgrep 使用ガイド

**目的**: AST解析ベース構造的コード検索・リファクタリング

### 9.1 ツール選択基準（Self-consistency check必須）

| ツール | 用途 | 成功条件 | 禁止条件 |
|--------|------|---------|---------|
| **ast-grep** | 言語構造的検索（関数定義、クラス継承、型ヒント） | 構文木パターン明確 + AST理解 | 文字列リテラル検索、正規表現で解決可能 |
| **mgrep** | コンテキスト統合検索（複数ファイル横断リファクタ） | 統一的命名変更 + AI支援リファクタ | 単純grep代替 |
| **Grep（標準）** | 文字列パターン検索 | **常に最優先検討** | - |

**基本原則**: **疑義時は常にGrep**（False Positive最小化）

### 9.2 使用禁止条件（False Positive防止）

**NEVER use ast-grep/mgrep if**:
- 標準Grepで十分（例: `import httpx`検索）
- 文字列リテラル内の検索（例: エラーメッセージ文言 `"Invalid JSON"`）
- 正規表現で解決可能な検索（例: `"test_.*_async"`）
- AST構造理解が曖昧な場合（→ Grepで代替）
- テスト実行中・未コミット変更あり（破壊的変更リスク）

### 9.3 用途別の詳細判断（機能差）

**ast-grep vs mgrep の本質的な違い:**

| 用途 | ast-grep | mgrep | 選択基準 |
|------|---------|-------|---------|
| リファクタリング | ◎ | × | コード変更時はast-grep必須（AST保証） |
| 安全な書き換え | ◎ | △ | 構文理解が必要 → ast-grep推奨 |
| Markdown構造探索 | ○ | ◎ | 文書構造 → mgrep推奨 |
| CI統合 | ◎ | ○ | 自動化・信頼性 → ast-grep推奨 |

**記号:** ◎=非常に優れている ○=優れている △=制限あり ×=非推奨

### 9.4 典型的成功例

**Use Case 1: Python型ヒント統一変換**
```bash
# ✅ ast-grep: Python 3.10 Union → 3.14 | 型変換
ast-grep --pattern 'Union[$A, $B]' --lang python utils/ config/ models/

# ❌ Grep: 不正確（コメント・文字列リテラル内も誤検出）
grep -r "Union\[" --include="*.py"
```

**Use Case 2: 非同期関数定義の全検索**
```bash
# ✅ ast-grep: 構文木ベース正確検索
ast-grep --pattern 'async def $FUNC($$$): $$$' --lang python

# ❌ Grep: Docstring内 "async def" も誤検出
grep -r "async def" .
```

**Use Case 3: 特定クラス継承の追跡**
```bash
# ✅ ast-grep: 継承関係解析
ast-grep --pattern 'class $CLASS(APIClientError): $$$' --lang python

# ❌ Grep: クラス名文字列も拾う
```

### 9.5 典型的失敗例（Grepで代替すべき）

**Anti-pattern 1: import文検索**
```bash
# ❌ 過剰: ast-grep
ast-grep --pattern 'import $MODULE' --lang python

# ✅ 適切: Grep（単純パターン検索）
grep -r "^import httpx" --include="*.py"
```

**Anti-pattern 2: 文字列リテラル検索**
```bash
# ❌ 不適切: ast-grep（文字列内容はAST構造に含まれない）
ast-grep --pattern '"Invalid JSON"' --lang python

# ✅ 適切: Grep
grep -r "Invalid JSON" --include="*.py"
```

**Anti-pattern 3: 正規表現パターン**
```bash
# ❌ 過剰: ast-grep
ast-grep --pattern 'test_$NAME' --lang python

# ✅ 適切: Grep
grep -rE "^def test_" tests/ --include="*.py"
```

### 9.6 mgrep（morph-mcp）統合検索

**用途**: コンテキスト保持型の統一リファクタリング

**成功条件**:
- 複数ファイル横断の命名変更（変数名・関数名の一括変更）
- 構造的に関連するコード群の一括検索（API呼び出しパターン等）
- AI支援が必要な複雑なリファクタリング

**制約**:
- MCPサーバー `morph-mcp` 必須（インストール確認: `ls ~/.claude/servers/morph-mcp/`）
- 単純な文字列置換は標準Grepで代替

**実行例**:
```bash
# Markdown見出し構造抽出（CLAUDE.md最適化時）
# → morph-mcp経由で実行（MCP tool使用）
```

### 9.7 信頼度と制約

| 要素 | 値 | 備考 |
|------|-----|------|
| AST解析精度 | 0.92 | 構文エラー時は動作せず |
| False Positive許容率 | <5% | Phase 2昇格条件（CLAUDE.md記載検討） |
| 標準Grep優先原則 | 必須 | 疑義時は常にGrep |
| 適用対象 | Python 3.14互換 | プロジェクト技術スタック準拠 |

### 9.8 実装推奨トリガー（参考）

**以下のケースで使用検討**（強制ではない）:

| ケース | トリガー条件 | ツール |
|--------|------------|--------|
| Python構文変換 | 3.10→3.14型ヒント統一 | ast-grep |
| pytestマーカー監査 | 品質ゲート失敗時（CRITICAL RULE 7） | ast-grep |
| API契約変更検証 | models/responses.py変更時 | ast-grep |
| CLAUDE.md構造分析 | 最適化・圧縮作業時 | mgrep |
| メモリファイル構成確認 | `.serena/memories/` 構造把握時 | mgrep |

**重要**: 上記はあくまで「検討」であり、**標準Grepで解決可能なら常にGrepを優先**

---
| 2026-02-18 | Section 5 Medium に /decision-helper, /fact-checker を追加 | - |
