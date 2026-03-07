# API仕様確認プロセス

*最終更新: 2026年02月07日*
*用途: 未知API使用前の仕様確認プロセス - KeyError/型不一致の予防*
*対象: 新規API統合、外部ライブラリ使用、自作モジュール利用*
*アクセス頻度: 高（未知API使用時）*

## 📚 目次

1. [導入背景](#1-導入背景)
2. [使用前チェックリスト](#2-使用前チェックリスト)
3. [ワークフローガイド](#3-ワークフローガイド)
4. [失敗パターン集](#4-失敗パターン集)
5. [実践例](#5-実践例)
6. [検出可能な失敗シグナル](#6-検出可能な失敗シグナル)
7. [関連ドキュメント](#7-関連ドキュメント)

---

## 1. 導入背景

### 1.1 発生した問題

**事例**: TokenBudgetChecker API使用時のKeyError連鎖
- **試行回数**: 3回の試行錯誤
- **エラー内容**:
  - `KeyError: 'phase_overhead'` (試行1)
  - `KeyError: 'decision'` (試行2)
  - `KeyError: 'recommendation'` (試行3)
- **根本原因**: API返り値構造を仮定に基づいて実装（Read実施なし）
- **影響**: 開発時間の浪費、コード品質低下（信頼度3.60/5.0）

### 1.2 このドキュメントの目的

**達成目標**:
- 未知API使用前の仕様確認を標準化
- KeyError/型不一致を1回で正しく実装
- 試行錯誤の削減（3回 → 1回）

**対象API**:
- 外部ライブラリのAPI（例: Claude Code SDK）
- プロジェクト内の未使用モジュール
- 新規統合するサービスAPI

---

## 2. 使用前チェックリスト

### 必須確認事項（全て✅必須）

```markdown
未知API使用前チェックリスト
---
[ ] 1. API実装ファイルの場所を特定
[ ] 2. Readツールでソースコード確認
[ ] 3. 返り値の型・構造を確認
[ ] 4. 引数の型・必須/オプションを確認
[ ] 5. docstring/型ヒントを読解
[ ] 6. 使用例（テストコード等）を確認
[ ] 7. エラーハンドリング要件を確認
```

### チェック項目の詳細

#### ✅ 1. API実装ファイルの場所を特定

**確認方法**:
```bash
# 方法A: Glob検索
Glob tool: "**/*budget*.py" or "**/*checker*.py"

# 方法B: Grep検索
Grep tool: "class TokenBudgetChecker" --output_mode files_with_matches
```

**確認内容**:
- ファイルパスの絶対位置
- モジュール構造の理解

#### ✅ 2. Readツールでソースコード確認

**確認方法**:
```python
# Read tool実行
Read("/path/to/api_implementation.py")
```

**確認内容**:
- クラス定義全体
- メソッドシグネチャ
- 内部実装ロジック

#### ✅ 3. 返り値の型・構造を確認

**確認ポイント**:
```python
# 例: TokenBudgetChecker.analyze() の返り値
def analyze(self) -> dict[str, Any]:
    """
    返り値構造:
    {
        "phase": str,           # ← キー名を正確に確認
        "allocated": float,
        "used": float,
        "remaining": float,
        "percentage": float
    }
    """
```

**チェック項目**:
- [ ] 返り値の型（dict/list/object/primitive）
- [ ] dict型の場合: 全てのキー名
- [ ] list型の場合: 要素の型・順序
- [ ] Optional型の可能性（None返却ケース）

#### ✅ 4. 引数の型・必須/オプションを確認

**確認ポイント**:
```python
# 例: メソッドシグネチャ
def analyze(
    self,
    phase: str,                    # 必須引数
    token_limit: int = 50000,      # オプション（デフォルト値あり）
    buffer: float = 0.1            # オプション
) -> dict[str, Any]:
```

**チェック項目**:
- [ ] 必須引数（デフォルト値なし）
- [ ] オプション引数（デフォルト値あり）
- [ ] 型ヒント（Union型/Optional型）

#### ✅ 5. docstring/型ヒントを読解

**確認ポイント**:
```python
def analyze(self, phase: str) -> dict[str, Any]:
    """トークン使用量の分析を実行

    Args:
        phase: 実行フェーズ名（"planning" / "implementation"）

    Returns:
        分析結果の辞書:
        - phase: フェーズ名
        - allocated: 割り当てトークン数
        - used: 使用トークン数
        - remaining: 残トークン数
        - percentage: 使用率（0.0-1.0）

    Raises:
        ValueError: 不正なphase指定時
    """
```

**チェック項目**:
- [ ] Args: 引数の意味・制約
- [ ] Returns: 返り値の詳細構造
- [ ] Raises: 発生する例外

#### ✅ 6. 使用例（テストコード等）を確認

**確認方法**:
```bash
# テストファイル検索
Glob tool: "**/test_*budget*.py" or "**/*_test.py"
```

**確認内容**:
```python
# テストコード例
def test_analyze():
    checker = TokenBudgetChecker()
    result = checker.analyze(phase="planning")

    # ← この部分で実際の使い方を確認
    assert result["phase"] == "planning"  # キー名の正確な確認
    assert isinstance(result["allocated"], float)
```

#### ✅ 7. エラーハンドリング要件を確認

**確認ポイント**:
```python
# 例外パターンの確認
try:
    result = checker.analyze(phase="invalid")
except ValueError as e:  # ← 発生する例外の型を確認
    print(f"Error: {e}")
```

**チェック項目**:
- [ ] 発生する例外の型
- [ ] 例外発生条件
- [ ] 推奨されるエラーハンドリング

---

## 3. ワークフローガイド

### 標準3ステップフロー

```
Step 1: Read → Step 2: Map → Step 3: Implement
```

### Step 1: Read でAPI実装確認

**目的**: API仕様の完全な理解

**実行例**:
```python
# Task 1: APIファイル特定
Glob tool: "**/*budget*.py"
# 結果: /path/to/token_budget_checker.py

# Task 2: ソースコード読解
Read("/path/to/token_budget_checker.py")
# 注目ポイント:
# - クラス定義
# - メソッドシグネチャ
# - 返り値の型ヒント
# - docstring
```

**確認すべき情報**:
```python
class TokenBudgetChecker:
    def analyze(self, phase: str) -> dict[str, Any]:
        """トークン使用量の分析"""
        return {
            "phase": phase,           # ← キー名を記録
            "allocated": 50000,
            "used": 12500,
            "remaining": 37500,
            "percentage": 0.25
        }
```

### Step 2: 返り値構造のマッピング

**目的**: 実装前に構造を文書化

**マッピングテンプレート**:
```markdown
## API返り値マッピング: TokenBudgetChecker.analyze()

### 返り値型
`dict[str, Any]`

### キー一覧
| キー名 | 型 | 説明 | 例 |
|--------|---|------|-----|
| phase | str | フェーズ名 | "planning" |
| allocated | float | 割り当てトークン数 | 50000.0 |
| used | float | 使用トークン数 | 12500.0 |
| remaining | float | 残トークン数 | 37500.0 |
| percentage | float | 使用率（0.0-1.0） | 0.25 |

### Optional キー
なし（全てのキーが常に存在）

### 注意事項
- percentage は小数（0.0-1.0）、パーセント表示時は *100
- phase は入力値がそのまま返却される
```

### Step 3: 1回で正しい実装

**目的**: KeyError/型不一致を回避

**実装例**:
```python
# ✅ 良い例（マッピング後の実装）
def display_budget_status():
    checker = TokenBudgetChecker()
    result = checker.analyze(phase="planning")

    # マッピング済みのキー名を使用
    print(f"Phase: {result['phase']}")
    print(f"Allocated: {result['allocated']}")
    print(f"Used: {result['used']}")
    print(f"Remaining: {result['remaining']}")
    print(f"Percentage: {result['percentage'] * 100:.1f}%")  # 0.0-1.0 → %変換

# ❌ 悪い例（仮定に基づく実装）
def display_budget_status():
    checker = TokenBudgetChecker()
    result = checker.analyze(phase="planning")

    # KeyError: 'phase_overhead' （存在しないキー）
    print(f"Overhead: {result['phase_overhead']}")

    # KeyError: 'decision' （存在しないキー）
    print(f"Decision: {result['decision']}")
```

---

## 4. 失敗パターン集

### パターン1: KeyError（想定外のキー参照）

**症状**:
```python
KeyError: 'phase_overhead'
```

**原因**:
- API返り値の構造を仮定で実装
- docstring/型ヒントを読まずにコーディング

**予防策**:
```python
# ✅ 正しい手順
# 1. Read でソースコード確認
result = checker.analyze(phase="planning")
# → 返り値: {"phase": "planning", "allocated": 50000, ...}

# 2. 存在するキーのみ使用
print(result["phase"])  # ✅ OK
print(result["phase_overhead"])  # ❌ KeyError
```

### パターン2: 型不一致

**症状**:
```python
TypeError: unsupported operand type(s) for *: 'str' and 'int'
```

**原因**:
```python
# percentage が float だと知らずに str として扱った
result = checker.analyze(phase="planning")
percentage_str = result["percentage"]  # 実際は float 0.25
print(f"Usage: {percentage_str}%")  # "0.25%" と表示（意図: "25%"）
```

**予防策**:
```python
# ✅ 型ヒントを確認してから実装
def analyze(self, phase: str) -> dict[str, Any]:
    """
    Returns:
        - percentage: float (0.0-1.0)  # ← 型を確認
    """

# 正しい実装
percentage = result["percentage"]  # float
print(f"Usage: {percentage * 100:.1f}%")  # "25.0%"
```

### パターン3: 仮定に基づく実装（検証なし）

**症状**:
```python
# 試行1
result['phase_overhead']  # KeyError

# 試行2（修正）
result['decision']  # KeyError

# 試行3（再修正）
result['recommendation']  # KeyError

# 試行4（正解）
result['phase']  # OK
```

**原因**:
- API仕様を確認せずに「こうあるべき」と仮定
- エラー → 修正 → エラー の繰り返し

**予防策**:
```python
# ✅ 正しい手順
# 1. Read tool で API実装を確認
# 2. 返り値の全キー名を列挙
# 3. 1回で正しい実装
```

### パターン4: Optional型の見落とし

**症状**:
```python
AttributeError: 'NoneType' object has no attribute 'get'
```

**原因**:
```python
# API定義
def get_user(user_id: int) -> dict[str, Any] | None:
    """ユーザー取得（存在しない場合はNone）"""
    if user_id not in database:
        return None  # ← Optional型を見落とし
    return {"id": user_id, "name": "Alice"}

# ❌ 悪い実装（None チェックなし）
user = get_user(999)
print(user["name"])  # AttributeError
```

**予防策**:
```python
# ✅ 型ヒント確認 + Noneチェック
user = get_user(999)
if user is not None:
    print(user["name"])
else:
    print("User not found")
```

---

## 5. 実践例

### 5.1 TokenBudgetChecker の正しい使用例

**シナリオ**: トークン使用状況をダッシュボードに表示

#### Step 1: Read でAPI確認

```python
# Read tool 実行
Read("/path/to/token_budget_checker.py")

# 確認内容
class TokenBudgetChecker:
    def analyze(self, phase: str) -> dict[str, Any]:
        """トークン使用量の分析

        Args:
            phase: 実行フェーズ名

        Returns:
            {
                "phase": str,
                "allocated": float,
                "used": float,
                "remaining": float,
                "percentage": float
            }
        """
```

#### Step 2: 返り値マッピング

```markdown
| キー | 型 | 説明 |
|------|---|------|
| phase | str | フェーズ名 |
| allocated | float | 割り当てトークン数 |
| used | float | 使用トークン数 |
| remaining | float | 残トークン数 |
| percentage | float | 使用率（0.0-1.0） |
```

#### Step 3: 実装

```python
# ✅ 正しい実装（1回で完成）
def display_token_budget_dashboard():
    """トークン使用状況ダッシュボード表示"""
    checker = TokenBudgetChecker()
    result = checker.analyze(phase="planning")

    # マッピング済みのキー名を使用
    print("=" * 50)
    print(f"Token Budget Status - {result['phase'].upper()}")
    print("=" * 50)
    print(f"Allocated: {result['allocated']:,.0f} tokens")
    print(f"Used:      {result['used']:,.0f} tokens")
    print(f"Remaining: {result['remaining']:,.0f} tokens")
    print(f"Usage:     {result['percentage'] * 100:.1f}%")
    print("=" * 50)

# 出力例:
# ==================================================
# Token Budget Status - PLANNING
# ==================================================
# Allocated: 50,000 tokens
# Used:      12,500 tokens
# Remaining: 37,500 tokens
# Usage:     25.0%
# ==================================================
```

### 5.2 改善前/改善後のコード比較

#### ❌ 改善前（試行錯誤パターン）

```python
# 試行1: 仮定に基づく実装
def display_budget():
    result = checker.analyze(phase="planning")
    print(result['phase_overhead'])  # KeyError: 'phase_overhead'

# 試行2: 修正1
def display_budget():
    result = checker.analyze(phase="planning")
    print(result['decision'])  # KeyError: 'decision'

# 試行3: 修正2
def display_budget():
    result = checker.analyze(phase="planning")
    print(result['recommendation'])  # KeyError: 'recommendation'

# 試行4: 正解（3回の失敗後）
def display_budget():
    result = checker.analyze(phase="planning")
    print(result['phase'])  # ✅ OK
```

**問題点**:
- 3回のKeyError発生
- 開発時間の浪費（試行錯誤で30分）
- コード品質低下（信頼度3.60/5.0）

#### ✅ 改善後（標準フロー適用）

```python
# Step 1: Read でAPI確認（2分）
Read("/path/to/token_budget_checker.py")
# 確認: 返り値は {"phase": str, "allocated": float, ...}

# Step 2: 返り値マッピング（1分）
# phase → str
# allocated → float
# used → float
# remaining → float
# percentage → float

# Step 3: 1回で正しい実装（5分）
def display_budget():
    result = checker.analyze(phase="planning")
    print(f"Phase: {result['phase']}")
    print(f"Allocated: {result['allocated']}")
    print(f"Used: {result['used']}")
    print(f"Remaining: {result['remaining']}")
    print(f"Usage: {result['percentage'] * 100:.1f}%")
```

**改善効果**:
- KeyError: 0回
- 開発時間: 8分（従来30分 → 73%削減）
- コード品質: 信頼度4.5/5.0（+0.9向上）

---

## 6. 検出可能な失敗シグナル

### セルフチェック質問

実装前に以下を自問してください：

| 質問 | ✅ OK | ❌ NG |
|------|-------|-------|
| 「このAPIのソースコードをReadしたか？」 | Yes → 続行 | No → **Read実施** |
| 「返り値の全キー名を確認したか？」 | Yes → 続行 | No → **マッピング作成** |
| 「型ヒントを読んだか？」 | Yes → 続行 | No → **docstring確認** |
| 「使用例を確認したか？」 | Yes → 続行 | No → **テストコード参照** |
| 「Optional型の可能性を確認したか？」 | Yes → 続行 | No → **型定義確認** |

### Red Flag思考パターン

以下の思考パターンは失敗シグナル - **STOP and Read**:

| Red Flag思考 | 違反内容 | 正しい対応 |
|-------------|---------|-----------|
| 「たぶんこのキー名だろう」 | 仮定に基づく実装 | Read tool で確認 |
| 「一般的にはこの構造」 | 仮定に基づく実装 | API固有の構造を確認 |
| 「エラーが出たら修正すればいい」 | 試行錯誤の容認 | 事前確認で1回で完成 |
| 「型はAnyだから気にしない」 | 型安全性の無視 | 実際の型を確認 |
| 「前回使ったAPIと同じはず」 | 仮定に基づく実装 | 毎回Read実施 |

### コードレビューチェックポイント

レビュー時に以下を確認：

```python
# ❌ Red Flag: 未確認のキー参照
result = api.fetch_data()
print(result['unknown_key'])  # ← このキーは存在するか？

# ❌ Red Flag: 型不一致
value = result['count']  # str? int? float?
total = value * 2  # ← 型を確認したか？

# ❌ Red Flag: Noneチェック欠落
user = api.get_user(999)
print(user['name'])  # ← Noneの可能性は？

# ✅ Good: 事前確認済みの実装
# Read tool で確認済み: result = {"count": int, "status": str}
result = api.fetch_data()
count = result['count']  # int型を確認済み
total = count * 2  # 型安全
```

---

## 7. 関連ドキュメント

### プロジェクト内ドキュメント

```bash
# ワークフロールール
.claude/rules/workflow/RULES.md  # 行動ルール（Failure Investigation）

# 品質基準
.claude/rules/testing/quality-gates.md  # 品質ゲート（Gate 1-4）

# コーディング規約
.claude/rules/python/coding-standards.md  # 型ヒント、docstring規約

# 基本原則
.claude/rules/principles/PRINCIPLES.md  # Evidence-Based Reasoning
```

### 参照推奨フロー

```
【未知API使用前】
1. api-specification-check.md（本ドキュメント）でチェックリスト確認
2. Read tool でAPI実装確認
3. 返り値マッピング作成
4. 実装

【エラー発生時】
1. RULES.md「Failure Investigation」参照
2. 本ドキュメント「失敗パターン集」で原因特定
3. 標準フローに戻って再実装

【品質保証】
1. quality-gates.md で品質ゲート実行
2. coding-standards.md で型ヒント確認
```

---

## 更新履歴

| 日付 | 変更内容 | 理由 |
|------|---------|------|
| 2026-02-07 | 初版作成 | reflexion評価で特定された改善必須項目の対応 |

---

## フィードバック

このドキュメントの改善提案は以下まで：
- **Issue**: プロジェクト Issue トラッカー
- **改善提案**: reflexion評価での指摘事項を反映
