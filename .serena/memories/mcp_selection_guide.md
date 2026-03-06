# MCP最適化運用ガイド

*最終更新: 2026年01月04日*  
*用途: MCPサーバー選択・トラブルシューティング・エラー解決*  
*アクセス頻度: 低（MCPエラー発生時のみ）*

## 📚 目次

1. MCPサーバー構成
2. MCP操作ガイドライン
3. トークン効率化ガイドライン
4. エラー回避パターン
5. 実践的使用例
6. ベストプラクティス
7. フォールバック戦略
8. 関連メモリ

---

## 1. MCPサーバー構成

プロジェクトでは以下のMCPサーバーが利用可能です：

**現在有効なMCPサーバー**（.mcp.jsonより）:
- `serena`: セマンティックコード分析・プロジェクト記憶管理（limited_serenaコンテキスト）
- `task-master-ai`: タスク管理・ワークフロー自動化（31ツール）
- `sentry`: エラー追跡・パフォーマンス監視（HTTP MCP）

**Claude Code組み込みツール**:
- `Read/Write/Edit`: ファイルシステム操作
- `Grep/Glob`: コード検索
- `Bash`: シェルコマンド実行

> **Note**: `serena-safe`/`filesystem-safe`ラッパーは計画段階。現在はネイティブツールを使用。

---

## 2. MCP操作ガイドライン

| 操作タイプ | 推奨ツール | 用途 |
|-----------|---------------|------|
| **コード分析系** |
| シンボル検索 | `serena find_symbol` | 関数・クラスの定義等検索 |
| ファイル概要 | `serena get_symbols_overview` | ファイル内のシンボル一覧 |
| パターン検索 | `serena search_for_pattern` | 正規表現でのコード検索 |
| **記憶管理系** |
| 記憶読込 | `serena read_memory` | プロジェクト知識の参照 |
| 記憶書込 | `serena write_memory` | セッション間情報保存 |
| 記憶一覧 | `serena list_memories` | 利用可能な記憶確認 |
| 思考分析 | `serena think_about_*` | タスク順守・情報十分性確認 |
| **ファイル操作系** |
| ファイル読込 | `Read` | Claude Code組み込みツール |
| ファイル編集 | `Edit/MultiEdit` | 精密なコード変更 |
| ファイル作成 | `Write` | 新規ファイル作成 |
| コード検索 | `Grep/Glob` | ファイルパターン・内容検索 |
| **タスク管理系** |
| タスク取得 | `task-master-ai get_task` | タスク詳細取得 |
| タスク追加 | `task-master-ai add_task` | 新規タスク作成 |
| PRD解析 | `task-master-ai parse_prd` | 要件定義書からタスク生成 |

---

## 3. トークン効率化ガイドライン

### 3.1 トークン使用率に応じた戦略

```markdown
トークン使用率判定フロー:

0-50%: 通常操作
  ├─ serena: シンボル検索・記憶管理
  └─ Read/Edit: ファイル操作

51-75%: 注意ゾーン
  ├─ 検索範囲を絞り込み
  └─ 並列操作の抑制検討

76-90%: 効率化必須
  ├─ serena max_answer_charsパラメータ使用
  └─ ファイル読み込みはlimit/offset活用

91-100%: 最小限操作
  ├─ 必要最小限の操作のみ
  └─ セッション分割検討
```

### 3.2 Serena最適化パラメータ

**応答サイズ制限**:
- `max_answer_chars`: 応答文字数上限（デフォルト: -1=無制限）
- 推奨値: 15000（大規模検索時）

**コンテキスト行数**:
- `context_lines_before/after`: マッチ前後の行数（デフォルト: 0）
- 増やすとコンテキスト理解向上、トークン消費増

### 3.3 ツール選択判断基準

| 目的 | 推奨ツール | 理由 |
|------|-------------|------|
| **シンボル検索** | serena find_symbol | セマンティック検索で高精度 |
| **パターン検索** | Grep | 高速なテキスト検索 |
| **ファイル一覧** | Glob | ファイルパターンマッチ |
| **ファイル読み込み** | Read | 部分読み込み可能（offset/limit） |
| **複数ファイル編集** | MultiEdit | 一括変更で効率的 |
| **コード分析** | Task Agent (Explore) | 大規模探索はエージェント委譲 |

---

## 4. エラー回避パターン

### パターン1: トークン制限エラー

**症状**:
```
Error: Response exceeded token limit
MCP server returned oversized response
```

**原因**: 大規模検索・大量ファイル読込によるトークン超過

**解決策**:
```markdown
即座対応:
1. serena検索時は max_answer_chars=15000 パラメータ追加
2. Readツールで offset/limit を使用して部分読み込み
3. 検索範囲を relative_path で絞り込み

予防策:
- 大規模検索は Task Agent (Explore) に委譲
- トークン使用率 75% 超で検索範囲縮小
- プロジェクト全体解析はエージェント使用
```

### パターン2: タイムアウトエラー

**症状**:
```
Error: MCP server timeout
Operation took too long to complete
```

**原因**: 大規模操作の一括実行

**解決策**:
```markdown
1. 操作の分割（ディレクトリ別・機能別）
2. 並列実行の抑制（逐次処理に変更）
3. 大規模処理はTask Agentに委譲
```

### パターン3: MCPサーバー接続エラー

**症状**:
```
Error: MCP server connection failed
Could not connect to server
```

**原因**: MCPサーバーが未起動または設定エラー

**解決策**:
```markdown
1. .mcp.jsonの設定確認
2. Claude Codeネイティブツールで代替（Read/Grep/Glob）
3. MCPサーバー再起動
```

---

## 5. 実践的使用例

### 例1: シンボル検索

**✅ 推奨**:
```python
# serenaでシンボル検索（範囲指定）
serena find_symbol "AsyncAPIClient" relative_path="utils/"
→ セマンティックに正確な検索
```

**✅ 大規模探索**:
```python
# Task Agentに委譲
Task(subagent_type="Explore", prompt="Find all async patterns", model="sonnet")
→ トークン効率的な大規模探索
```

### 例2: ファイル読み込み

**✅ 単一ファイル**:
```python
# Readツールで読み込み
Read("utils/api_client.py")
```

**✅ 大きなファイル（部分読み込み）**:
```python
# offset/limitで部分読み込み
Read("utils/api_client.py", offset=1, limit=100)
→ 先頭100行のみ読み込み
```

### 例3: 記憶管理

**✅ 記憶読み込み**:
```python
# serenaで記憶参照
serena read_memory "coding_standards"
→ プロジェクト知識の参照
```

**✅ 記憶書き込み**:
```python
# セッション終了時に保存
serena write_memory "session_summary" "Completed API refactoring"
→ 次回セッションで参照可能
```

---

## 6. ベストプラクティス

1. **範囲指定**: serena検索時は `relative_path` で範囲を絞る
2. **部分読み込み**: 大きなファイルは `offset/limit` で分割読み込み
3. **トークン監視**: 75%超えたら検索範囲縮小
4. **エージェント活用**: 大規模探索は Task Agent (Explore) に委譲
5. **記憶活用**: セッション間情報は serena memory で保存

---

## 7. フォールバック戦略

```markdown
MCPエラー発生時のフォールバック:

Level 1: パラメータ調整
  serena: max_answer_chars=15000 追加
  Read: offset/limit で部分読み込み

Level 2: 操作分割
  プロジェクト全体 → ディレクトリ別
  複数ファイル → 順次処理

Level 3: 代替ツール使用
  serena → Grep/Glob + Read
  Task Agent (Explore) で大規模探索
```

---

## 8. 関連メモリ

| メモリ名 | 用途 | 頻度 |
|---------|------|------|
| `@memory:serena_tool_usage_patterns` | シンボル解析・思考支援ツール活用 | 高 |
| `@memory:serena_memory_usage_guide` | 作業タイプ別メモリ読込戦略 | 中 |

---

**更新履歴**:
- 2026-01-04: Section 8「関連メモリ」追加、serena_tool_usage_patternsへの相互参照
- 2025-12-27: 現行MCP構成（serena, task-master-ai, sentry）に合わせて全面改訂
- 2025-11-14: 初版作成
