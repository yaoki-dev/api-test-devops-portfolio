# Serenaツール活用パターン

*最終更新: 2026年01月04日*
*用途: シンボル解析・思考支援ツールの効果的活用*
*アクセス頻度: 高（毎セッション参照推奨）*

---

## 1. シンボル解析ツール（3段階フロー）

### 1.1 活用フロー

```
新規ファイル理解時:
┌─────────────────────────────────────────────────┐
│ Step 1: get_symbols_overview(file)              │
│   → ファイル全体の構造把握（0行読込）            │
│       ↓                                         │
│ Step 2: find_symbol(name, depth=1)              │
│   → クラス/関数の詳細構造（0行読込）            │
│       ↓                                         │
│ Step 3: find_symbol(name, include_body=True)    │
│   → 必要なコード本体のみ取得                    │
└─────────────────────────────────────────────────┘
```

### 1.2 効果実測値

| ファイル | 従来 | 最適化後 | 削減率 |
|---------|------|---------|--------|
| utils/jsonplaceholder_base_sync.py (280行) | 280行読込 | 50行読込 | 82% |
| 一般的なファイル | 全行読込 | 必要部分のみ | 50-90% |

### 1.3 ツール詳細

| ツール | 用途 | パラメータ |
|--------|------|-----------|
| `get_symbols_overview` | ファイル構造把握 | `relative_path`, `depth` |
| `find_symbol` | シンボル検索 | `name_path_pattern`, `depth`, `include_body` |
| `find_referencing_symbols` | 参照元検索 | `symbol_name`, `relative_path` |

---

## 2. 統合ワークフロー

```
┌─────────────────────────────────────────────────────────────┐
│ [情報収集フェーズ]                                          │
│  get_symbols_overview(file)                                 │
│       ↓                                                     │
│  find_symbol(name, depth=1)                                 │
│       ↓                                                     │
│  find_symbol(name, include_body=True)                       │
├─────────────────────────────────────────────────────────────┤
│ [実装フェーズ]                                              │
│  Edit/Write（同一変更の繰り返しは replace_all）              │
├─────────────────────────────────────────────────────────────┤
│ [完了フェーズ]                                              │
│  pytest/ruff/mypy → Skill(commit)                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 使用例

### 例1: 新規ファイル理解

```python
# Step 1: 構造把握
serena get_symbols_overview relative_path="utils/jsonplaceholder_base_async.py" depth=1
# → Classes: AsyncAPIClient
# → Functions: （モジュールレベル関数なし）

# Step 2: クラス詳細
serena find_symbol "AsyncAPIClient" relative_path="utils/" depth=1
# → Methods: __init__, get, post, _make_request_with_retry, ...

# Step 3: 必要メソッドのみ
serena find_symbol "AsyncAPIClient/_make_request_with_retry" include_body=True
# → 132行のコード本体を取得
```

### 例2: リファクタリング時

```python
# 影響分析
serena find_referencing_symbols "AsyncAPIClient" relative_path="."
# → 参照元一覧を取得
```

---

## 関連メモリ

- `@memory:mcp_selection_guide`: MCPサーバー選択・エラー解決（低頻度）
- `@memory:serena_memory_usage_guide`: 作業タイプ別メモリ読込戦略（中頻度）
