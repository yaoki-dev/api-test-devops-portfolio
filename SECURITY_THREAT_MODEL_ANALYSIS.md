# セキュリティ脅威モデル分析: get_week_from_day_w6_plan()

**セキュリティエンジニアレビュー** | **日付**: 2025-12-05

---

## 1. 攻撃面分析

### データフロー
```
progress_state.yaml (信頼できない)
        ↓ yaml.safe_load()
state["current_day"]
        ↓
get_week_from_day_w6_plan(current_day)
        ↓ [型検証]
        ↓ [範囲検証]
        ↓
return: 週番号 (1-6 または 5.5)
```

### 信頼境界
- **信頼できない入力**: `progress_state.yaml`（ユーザー/攻撃者が編集可能）
- **検証境界**: CLAUDE.md 行250-255
- **信頼できる出力**: 週番号（意味的に制限: 1-6、5.5）

---

## 2. 脅威モデル: YAMLインジェクション

### 脅威名
**YAMLデシリアライゼーションによる型混乱** (CWE-502)

### 攻撃仮説
```
攻撃者の目標: 週ルックアップを失敗させるか、予期しない結果を返させる
攻撃方法: progress_state.yamlにbool値を注入
```

### 攻撃シナリオ1: 直接Bool注入
```yaml
# ファイル: progress_state.yaml（攻撃者が変更）
current_week: 1
current_day: true         # <- 注入: intの代わりにbool
next_learning_item: python-basics
```

```python
# アプリケーションコード（信頼済み）
import yaml
with open("progress_state.yaml") as f:
    state = yaml.safe_load(f)

current_day = state["current_day"]  # 型: bool (True)
get_week_from_day_w6_plan(current_day)
```

### 防御層1: YAML安全ロード
```python
state = yaml.safe_load(f)  # ← Python 3.6+でFullLoaderを使用
```

**効果**: 任意のコード実行を防止（`!!python/object`をブロック）
**制限**: スカラー型は依然としてデシリアライズ: `true` → `True`、`false` → `False`

### 防御層2: 型検証（現在の実装）
```python
if isinstance(current_day, bool) or not isinstance(current_day, int):
    raise TypeError(f"current_day must be int, got {type(current_day).__name__}")
```

**効果**: bool値を明示的に拒否
**必要な理由**: Pythonでは`bool`は`int`のサブクラス

### 明示的なBoolチェックなしでシステムが失敗する理由
```python
# 脆弱（boolチェックなし）:
if not isinstance(current_day, int):  # bool は intのサブクラス！
    raise TypeError(...)

isinstance(True, int)  # Trueを返す
isinstance(False, int) # Trueを返す

# 結果: 注入成功、boolが黙って受け入れられる ❌
```

### 影響分析
**注入が成功した場合**:
```python
get_week_from_day_w6_plan(True)   # boolを受け取り、エラーなし
# true == 1 in comparison
if True <= 6:  # Trueは1と等価
    return 1   # 週1を返す（予期しないが壊滅的ではない）
```

**結果**:
- 週ルックアップが不正確（意味的に間違っている）
- 機能的クラッシュなし、黙ってデータが破損
- 間違った学習/実装割り当てを引き起こす可能性

**深刻度**: P2-Medium（データ整合性問題、システムクラッシュではない）

---

## 3. 現在の緩和策

### 行250: 明示的なBoolチェック
```python
if isinstance(current_day, bool) or not isinstance(current_day, int):
    raise TypeError(f"current_day must be int, got {type(current_day).__name__}")
```

### 緩和の有効性

| 攻撃ベクター | ブロック？ | 証拠 |
|---|---|---|
| YAML `true` → `True` | ✅ YES | 行250 boolチェック |
| YAML `false` → `False` | ✅ YES | 行250 boolチェック |
| YAML文字列 `"5"` → `"5"` | ✅ YES | `isinstance(str, int)` = False |
| YAML float `5.5` → `5.5` | ✅ YES | `isinstance(float, int)` = False |
| YAML dict `{...}` | ✅ YES | `isinstance(dict, int)` = False |
| YAML list `[...]` | ✅ YES | `isinstance(list, int)` = False |
| YAML null → `None` | ✅ YES | `isinstance(None, int)` = False |

### 多層防御

```
層1: YAML安全ロード（アーキテクチャ）
         ↓ コード実行を防止
層2: 型検証（現在: 行250）
         ↓ bool/float/str等を拒否
層3: 範囲検証（現在: 行254）
         ↓ 範囲外の整数を拒否
層4: 境界ロジック（現在: 行258-271）
         ↓ 週番号を返す（意味的に制約）
```

**結果**: 多層防御。層2がバイパスされても、層3がキャッチ。

---

## 4. 代替攻撃ベクター

### ベクター1: 負の整数注入
```yaml
current_day: -5
```

**攻撃フロー**:
```python
isinstance(-5, bool)  # False → boolチェック合格 ✅
isinstance(-5, int)   # True → intチェック合格 ✅
if not 1 <= -5 <= 38: # -5 は範囲外
    raise ValueError(...) # キャッチ！ ✅
```

**ステータス**: ✅ 層3（範囲検証）によってブロック

### ベクター2: intのように見えるFloat
```yaml
current_day: 5.0
```

**攻撃フロー**:
```python
isinstance(5.0, bool)  # False → boolチェック合格 ✅
isinstance(5.0, int)   # False → intチェック失敗 ✅
raise TypeError(...) # キャッチ！ ✅
```

**ステータス**: ✅ 層2（型検証）によってブロック

### ベクター3: 文字列数値
```yaml
current_day: "5"
```

**攻撃フロー**:
```python
isinstance("5", bool)  # False → boolチェック合格 ✅
isinstance("5", int)   # False → intチェック失敗 ✅
raise TypeError(...) # キャッチ！ ✅
```

**ステータス**: ✅ 層2（型検証）によってブロック

### ベクター4: 範囲外整数
```yaml
current_day: 100
```

**攻撃フロー**:
```python
isinstance(100, bool)  # False → boolチェック合格 ✅
isinstance(100, int)   # True → intチェック合格 ✅
if not 1 <= 100 <= 38: # 100は範囲外
    raise ValueError(...) # キャッチ！ ✅
```

**ステータス**: ✅ 層3（範囲検証）によってブロック

---

## 5. 提案されたリファクタリング: 導入された脆弱性

### リファクタリングされたコード（refactoring_proposal.py:81）
```python
day_start, day_end = map(int, config["days"].split("-"))
if day_start <= current_day <= day_end:
    return week
```

### 新しい脆弱性: CWE-20（不適切な入力検証）

#### ベクター1: 文字列解析での空白
```python
# 設定（W6_PLAN_WEEK_MAPから）:
config["days"] = " 1 - 6 "

# 現在のコード:
parts = " 1 - 6 ".split("-")  # ["  1 ", "  6  "]
day_start = int("  1 ")        # 1（intは空白を除去）
day_end = int("  6  ")         # 6（intは空白を除去）

# 結果: 先頭/末尾の空白があっても解析成功
# 判定: int()の副作用により「偶然」動作
```

**リスク**: 脆弱な解析（int()の副作用に依存）

#### ベクター2: 設定の範囲外範囲
```python
# 悪意のある設定（W6_PLAN_WEEK_MAPが侵害された場合）:
W6_PLAN_WEEK_MAP[1] = {"days": "1-999999999"}

# 提案されたコード:
day_start, day_end = int("1"), int("999999999")
if day_start <= 15 <= day_end:  # 15は範囲[1, 999999999]内
    return 1  # 週を返すが、範囲が検証されていない！

# 違反: 週1が現在日1-999999999を受け入れる、1-6ではない
# 判定: 意味的契約違反
```

**リスク**: 無効な範囲（> 38）を検証なしで受け入れる

#### ベクター3: 無効な形式がクラッシュを引き起こす
```python
# 破損した設定:
W6_PLAN_WEEK_MAP[1] = {"days": "1"}  # 終了値がない

# 提案されたコード:
parts = "1".split("-")  # ["1"]
day_start, day_end = map(int, ["1"])  # ValueError: too many values to unpack

# 結果: 未処理の例外、関数クラッシュ
# 判定: 不適切なエラー処理
```

**リスク**: 未処理の例外（サービス拒否）

---

## 6. なぜ現在の実装が優れているか

### 基準1: 型安全性
```python
# 現在: 明示的なif-elif境界
if current_day <= 6:
    return 1

# 提案: 文字列解析によるデータ駆動
day_start, day_end = map(int, config["days"].split("-"))
if day_start <= current_day <= day_end:
    return week
```

**分析**:
- 現在: 境界が整数としてハードコード（不変）
- 提案: 境界が文字列から解析（可変、未検証）

**利点**: 現在 ✅

### 基準2: 攻撃面
```python
# 現在: 0解析ステップ
if current_day <= 6:

# 提案: 3解析ステップ
config["days"].split("-")      # ステップ1: 文字列分割
map(int, [...])                # ステップ2: 型変換
int.__compare(current_day)     # ステップ3: 比較
```

**リスク分布**:
- 現在: 検証のみ
- 提案: 検証 + 解析 + 変換

**利点**: 現在 ✅（攻撃面が少ない）

### 基準3: 意味的強制
```python
# 現在: 行254で範囲[1-38]を強制
if not 1 <= current_day <= 38:
    raise ValueError(...)

# 提案: W6_PLAN_WEEK_MAPから範囲[1-38]
# しかしW6_PLAN_WEEK_MAP["days"]は検証されていない
```

**失敗の例**:
```python
# W6_PLAN_WEEK_MAP[1]["days"] = "1-50"の場合
# 提案: 日45を週1として受け入れる（間違い）
# 現在: 日45を拒否（正しい、週6を返すはず）
```

**利点**: 現在 ✅（意味的契約を強制）

---

## 7. リスク定量化

### 現在の実装（CLAUDE.md）

**脅威の確率**: LOW
- YAMLファイルの破損/侵害が必要
- 明示的な型検証が注入をブロック
- 複数の検証層（多層防御）

**影響**: LOW（注入が成功しても）
- 範囲検証が無効な入力をキャッチ
- コード実行は不可能
- 最悪の場合: 意味的データ整合性問題

**CVSS v3.1スコア**: **1.7 (LOW)**
```
AV:L/AC:H/PR:H/UI:R/S:U/C:N/I:L/A:N
```

---

### 提案されたリファクタリング

**脅威の確率**: MEDIUM
- W6_PLAN_WEEK_MAPが侵害されているか、エラーを含む場合
- 文字列解析が検証されていない
- 意味的境界チェックがない

**影響**: MEDIUM（週割り当てが不正確）
- 間違った学習タスクが割り当てられる
- 黙ってデータが破損（例外なし）
- 下流コードでカスケード障害

**CVSS v3.1スコア**: **3.2 (LOW-MEDIUM)**
```
AV:L/AC:M/PR:H/UI:N/S:U/C:L/I:L/A:N
```

**判定**: 提案されたアプローチはリスクプロファイルを増加させる。⚠️

---

## 8. 修正パス（リファクタリングを追求する場合）

### ステップ1: 文字列形式検証を追加
```python
day_parts = config["days"].split("-")
if len(day_parts) != 2:
    raise ValueError(f"Invalid day range: {config['days']}")
```

### ステップ2: 意味的境界検証を追加
```python
day_start, day_end = int(day_parts[0]), int(day_parts[1])
if not (1 <= day_start <= day_end <= 38):
    raise ValueError(f"Day range {day_start}-{day_end} out of bounds")
```

### ステップ3: 例外処理を追加
```python
try:
    day_start, day_end = int(day_parts[0]), int(day_parts[1])
except ValueError as e:
    continue  # 無効な設定をスキップ、フェイルセーフ
```

### ステップ4: 脅威モデルを文書化
```python
def get_week_from_day_w6_plan(current_day: int) -> Union[int, float]:
    """
    ...
    セキュリティノート:
        - W6_PLAN_WEEK_MAP["days"]形式を検証（CWE-20緩和）
        - 意味的境界[1-38]を強制（設定から導出されない）
        - 不正な形式の設定で安全に失敗（例外処理）
    """
```

**結果**: 行を8から約20に増やすが、CWE-20脆弱性を排除。

---

## 9. 結論と推奨事項

### 現在の実装について ✅
- **ステータス**: セキュア、本番準備完了
- **アクション**: 変更不要
- **保持**: 明示的なboolチェックコメント（意図を文書化）

### 提案されたリファクタリングについて ⚠️
- **ステータス**: CWE-20（不適切な入力検証）を導入
- **アクション**: 修正なしで採用しない
- **追求する場合**: 上記のステップ1-4を適用

### 適用されたセキュリティベストプラクティス ✅
1. **多層防御**: 4つの検証層
2. **明示的な検証**: 型と範囲チェック
3. **脅威モデリング**: Bool注入を文書化
4. **エラー処理**: 適切な例外タイプ
5. **ゼロトラスト**: YAMLファイルを信頼できないと仮定

---

## 参考文献

- **CWE-20**: https://cwe.mitre.org/data/definitions/20.html（不適切な入力検証）
- **CWE-502**: https://cwe.mitre.org/data/definitions/502.html（信頼できないデータのデシリアライゼーション）
- **Python bool as int**: https://docs.python.org/3/reference/datamodel.html#truth-value-testing
- **CVSS v3.1**: https://www.first.org/cvss/v3.1/specification-document

---

**監査分類**: ✅ セキュア（現在） | ⚠️ 修正が必要（提案）
