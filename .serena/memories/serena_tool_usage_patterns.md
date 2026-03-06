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
| utils/api_client.py (762行) | 762行読込 | 101行読込 | 87% |
| 一般的なファイル | 全行読込 | 必要部分のみ | 50-90% |

### 1.3 ツール詳細

| ツール | 用途 | パラメータ |
|--------|------|-----------|
| `get_symbols_overview` | ファイル構造把握 | `relative_path`, `depth` |
| `find_symbol` | シンボル検索 | `name_path_pattern`, `depth`, `include_body` |
| `find_referencing_symbols` | 参照元検索 | `symbol_name`, `relative_path` |

---

## 2. 思考支援ツール（3つのチェックポイント）

### 2.1 発動タイミング

| タイミング | ツール | 目的 | 発動条件 |
|-----------|--------|------|---------|
| 情報収集後 | `think_about_collected_information` | 情報充足度評価 | Grep/Read 3回以上実行後 |
| 実装前 | `think_about_task_adherence` | タスク遂行確認 | Edit/Write実行前 |
| 完了時 | `think_about_whether_you_are_done` | 完了判定 | 「完了」発言時 |

### 2.2 各ツールの確認内容

**think_about_collected_information**:
- 情報は十分か？
- 不足情報は何か？
- どう取得するか？

**think_about_task_adherence**:
- タスクから逸脱していないか？
- メモリを読んだか？
- コード規約に沿っているか？

**think_about_whether_you_are_done**:
- 全ステップ完了か？
- テスト実行したか？
- ドキュメント更新したか？

---

## 3. 統合ワークフロー

```
┌─────────────────────────────────────────────────────────────┐
│ [情報収集フェーズ]                                          │
│  get_symbols_overview(file)                                 │
│       ↓                                                     │
│  find_symbol(name, depth=1)                                 │
│       ↓                                                     │
│  find_symbol(name, include_body=True)                       │
│       ↓                                                     │
│  ✅ think_about_collected_information                       │
├─────────────────────────────────────────────────────────────┤
│ [実装フェーズ]                                              │
│  ✅ think_about_task_adherence                              │
│       ↓                                                     │
│  Edit/Write/MultiEdit                                       │
├─────────────────────────────────────────────────────────────┤
│ [完了フェーズ]                                              │
│  ✅ think_about_whether_you_are_done                        │
│       ↓                                                     │
│  pytest/ruff/mypy → git commit                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. 使用例

### 例1: 新規ファイル理解

```python
# Step 1: 構造把握
serena get_symbols_overview relative_path="utils/api_client.py" depth=1
# → Classes: AsyncAPIClient, SyncAPIClient, ...
# → Functions: create_client, main, ...

# Step 2: クラス詳細
serena find_symbol "AsyncAPIClient" relative_path="utils/" depth=1
# → Methods: __init__, get, post, _make_request_with_retry, ...

# Step 3: 必要メソッドのみ
serena find_symbol "AsyncAPIClient/_make_request_with_retry" include_body=True
# → 101行のコード本体を取得

# Step 4: 情報充足確認
serena think_about_collected_information
# → "情報は十分か？不足は何か？"
```

### 例2: リファクタリング時

```python
# 影響分析
serena find_referencing_symbols "AsyncAPIClient" relative_path="."
# → 参照元一覧を取得

# 実装前確認
serena think_about_task_adherence
# → "スコープ逸脱していないか？"

# 完了確認
serena think_about_whether_you_are_done
# → "テスト実行したか？"
```

---

## 関連メモリ

- `@memory:mcp_selection_guide`: MCPサーバー選択・エラー解決（低頻度）
- `@memory:serena_memory_usage_guide`: 作業タイプ別メモリ読込戦略（中頻度）
