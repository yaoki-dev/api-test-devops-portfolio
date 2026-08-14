---
paths:
  - "claudedocs/plans"
  - "~/.claude/plans"
---

# PLANS.md - 計画文書テンプレート

*最終更新: 2026-07-21*

## 概要・役割分担

このファイルはタスク計画文書のテンプレートを定義する。
実行効率化の詳細は `@memory:execution-efficiency` を参照。

| ツール/ファイル | 用途 | スコープ |
|--------------|------|---------|
| **本テンプレート** | フィーチャー単位の計画・決定記録 | Within-task |
| **@memory:execution-efficiency** | 実行効率化・並列判定の手法詳細 | How to execute |
| **TodoWrite** | セッション内タスク進捗UI表示 | 揮発性 |
| **lessons.md** (Rule 15) | セッション横断の教訓蓄積 | Cross-project |

### 使用閾値

本テンプレートを使用する条件（いずれか1つ以上）:

- 設計上の判断（AskUserQuestion）が必要
- アーキテクチャ / 既存動作に影響する変更
- TodoWrite で3タスク以上 **かつ 機械的でない**（同型処理の繰り返しでない）

スキップ可能: 単純バグ修正・同型テスト追加・1ファイル以内の自明な変更

---

## セクション定義

### [必須] Purpose

1文でユーザーが得る観測可能な利益を記述。
「コードを追加した」ではなく「URL返却でHTTP 200が返る」形式。

---

### [必須] Progress

ISO 8601 タイムスタンプ付きチェックボックス。
TodoWrite の各タスクと 1対1 対応させること。

- [ ] (YYYY-MM-DDTHH:MMZ) 未完了ステップ
- [x] (2026-03-02T03:00Z) 完了ステップ

---

### [必須] Decision Log

AskUserQuestion の回答・設計判断を記録する。
**@memory:参照は推奨。外部ブログリンクによる情報委譲は禁止。**

| 決定 | 根拠 | 日付 |
|------|------|------|
| （例）PLANS.mdを .claude/rules/ に配置 | rules/ は他ルールファイルと同一管理下 | 2026-03-02 |

---

### [推奨] Context and Orientation

リポジトリの状態・前提条件を記述。
→ `@memory:execution-efficiency` Phase 0（分析フェーズ）の成果物として作成。

- リポジトリ現状
- 関連する既存コード・ファイル
- 前提条件・依存関係

---

### [推奨] Plan of Work

散文形式で実装の順序・内容を記述。
→ `@memory:execution-efficiency` Phase 0 の並列化判定後に作成。

---

### [推奨] Validation and Acceptance

観測可能な受け入れ基準を実装タイプ別に記述。

**コード実装（.py 変更）**:

- [ ] `uv run pytest -n auto -m "(unit or integration) and not external"` 全pass
- [ ] `uv run ruff check .` エラー0件
- [ ] `uv run mypy utils/ config/ models/ tests/conftest.py` エラー0件
- [ ] `Skill(fable:fable-judge)`（全タスク完了確認 — 未完了検出時: 修正 → 品質ゲート → 再実行 - 最大3回まで）
- [ ] `Skill(reflexion:reflect)` （信頼度90%以上）
- [ ] `Skill(code-review medium)`

**プラン実装（.md）**:

- [ ] `npm run lint:md && npm run lint:text` 全pass
- [ ] `Skill(fable:fable-judge)`（全タスク完了確認 — 未完了検出時: 修正 → 品質ゲート → 再実行 - 最大3回まで）
- ※ 事実主張・数値データを含む変更の場合は CLAUDE.md Medium「Skill(fact-checker)」を参照
- [ ] `Skill(reflexion:reflect)`（信頼度90%以上）
- [ ] `Skill(pr-review-toolkit:review-pr)`
- ※ PRレビューは CLAUDE.md Step 8 ELSE節（`Skill(pr-review-toolkit:review-pr)`）に委譲

**設定ファイル変更（*.yml / pyproject.toml / config/）**:

- ⚠️ 前提条件: Rule 16（❌確認必要ファイルリスト: CLAUDE.md Rule 16参照）と照合 + AskUserQuestion でユーザー確認
- [ ] 変更前後で該当テスト合格（pytest / CI実行確認）
- [ ] `npm run lint:md && npm run lint:text`（Markdownドキュメント品質チェック）

---

### [Optional] Surprises & Discoveries

予期しない動作・バグ・最適化の発見。
→ lessons.md（Rule 15）への記録候補をここに一時保管する。

---

### [Optional] Concrete Steps

実行コマンド・カレントディレクトリ・期待される出力例。
→ `@memory:execution-efficiency` Phase 2（実装フェーズ）と連携。

---

### [Optional] Outcomes & Retrospective

完了後に記入: 成果・未完了事項・学習。
**→ lessons.md（Rule 15）へ転記するトリガーとして使用。**

---

## 品質ルール（必守）

1. **観測可能な成果**: 受け入れ基準はユーザー体験で記述
2. **べき等性**: 全ステップは複数回実行しても安全であること
3. **自己完結性**: @memory:参照は推奨。外部ブログ委譲は禁止
4. **生きた文書**: 発見・設計変更はその都度更新すること

---

## ファイル命名・保存先

```
claudedocs/plans/YYYY-MM-DD-<topic>.html   # フィーチャー別計画
```

## HTML Document Design Rules

HTML形式の技術文書・計画書を作成する場合は、次の規則に従う。

### HTML Technical Document Design Rules

## Core Requirements

### Dark theme

- 目への刺激を抑えた、低彩度のスレート系ダークテーマを使用する。
- 純黒 #000000 と純白 #FFFFFF は使用しない。
- 背景は次の明度階層を基本とする。
    code background < canvas background < panel background
- 本文、補助文字、罫線には異なる明度を割り当て、情報階層を色の明るさでも識別できるようにする。
- 通常サイズの文字と背景のコントラスト比は WCAG AA の 4.5:1 以上を確保する。
- 装飾目的の高彩度色、強い発光、過度なグラデーション、重いドロップシャドウは使用しない。

### Design tokens

- 色、フォント、罫線、背景、状態表現は :root のCSSカスタムプロパティに集約する。
- 少なくとも次の役割を個別に定義する。

```
--canvas;
--panel;
--code-bg;
--ink;
--ink-soft;
--ink-faint;
--rule;
--accent;
--ok;
--warn;
--stop;
--sans;
--mono;
```

- 成功、警告、停止などの状態色には、文字色だけでなく背景色と枠線色も定義する。
- HTMLやSVG内に同じ色値を繰り返しハードコードしない。

### Layout and typography

- 文書全体を中央寄せし、本文領域の最大幅をおおむね 900px から 960px に制限する。
- 段落とリストの行長は原則 70ch から 75ch に制限する。
- 日本語本文の行間は 1.7 から 1.8 を基本とする。
- 本文にはシステムサンセリフ、コード、コマンド、パス、数値にはモノスペースフォントを使用する。
- 見出し階層はフォントサイズだけで表現せず、余白、罫線、文字色を併用する。
- 情報密度を上げるために文字サイズや行間を過度に縮小しない。

### Structure

- 文書構造に応じて header、nav、main、section、figure、figcaption、footer、time などのセマンティック要素を使用する。
- div のみで文書全体を構成しない。
- 主要見出しには一意で内容を表す id を付与する。
- 長文で目的のセクションを探しにくい場合は、ページ内リンクを持つ目次を設ける。
- 目次の要否はセクション数だけでなく、文書量と探索性によって判断する。

### State and emphasis

- 成功、注意、停止、保留などの意味を色だけで表現しない。
- 状態はラベル文字、背景、枠線、左罫線、アイコンまたはバッジを組み合わせて表現する。
- 同じ状態には文書全体で同じラベルとデザインを使用する。
- 強調表現を乱用せず、重要度の差が識別できる状態を保つ。

### Code

- インラインコードとコードブロックにはモノスペースフォントと専用背景を使用する。
- コード背景はページ背景より暗くする。
- pre には overflow-x: auto を設定し、長いコマンドやパスでレイアウトを破壊しない。
- pre code ではインラインコード用の背景と余白を解除する。
- コマンド例は可能な限りコピーして実行できる完全な形式で記載する。
- 展開不能なプレースホルダを、実行可能なコマンドであるかのように表示しない。

## Conditional Requirements

### Tables

表を使用する場合は、次のルールに従う。

- 表は要件、比較、証拠、リスク、数値など、列構造が理解を改善する情報に限定する。
- 通常の説明文を表へ無理に変換しない。
- 見出しセルには th を使用する。
- 数値列は右寄せし、必要に応じてモノスペースフォントを使用する。
- 長い文章を含む表では、列数を必要最小限にする。

### Callouts and reusable components

同じ意味構造が複数回現れる場合は、再利用可能なクラスとして定義する。

例:
```
.meta
.toc
.unit
.callout
.badge
.conf
.num
```

- 状態差分は .ok、.warn、.stop などの修飾クラスで表現する。
- 同一目的のコンポーネントに複数の無関係なスタイルを持たせない。
- 一度しか使わない要素のために過剰なコンポーネント体系を作らない。

### SVG and diagrams

SVGまたは図を使用する場合は、次のルールに従う。

- SVGには viewBox、role="img"、内容を説明する aria-label を指定する。
- SVGの色は可能な限り文書側のCSSカスタムプロパティを参照する。
- SVG内にテーマと無関係な固定色を大量に埋め込まない。
- 図の重要な結論は本文または figcaption にも記載する。
- 図だけを読まなければ結論を理解できない構造にしない。
- 図が文章より理解を改善しない場合は追加しない。

### Prohibited Patterns

- 純黒の背景と純白の本文を組み合わせない。
- 色だけで状態や重要度を表現しない。
- 同じ色やフォント値を複数箇所へ繰り返しハードコードしない。
- 装飾のためだけにカード、バッジ、罫線、影を増やさない。
- すべての文章をカードや表へ分割しない。
- 小さい文字、狭い行間、長すぎる行によって情報を詰め込まない。
- 文書内容に不要な目次、表、SVG、calloutを形式的に追加しない。

### Verification

HTMLの生成後、少なくとも次を確認する。

- 本文、補助文字、リンク、状態ラベルがダーク背景上で読み取れる。
- 通常文字のコントラスト比が 4.5:1 以上である。
- 見出し階層とセクション境界が視覚的に識別できる。
- 長いコード、コマンド、パスが文書幅を破壊しない。
- ページ内リンクと見出しの id が対応している。
- 色を無視しても、成功、警告、停止、保留を文字情報から判別できる。
- 表、図、calloutが本文の理解を改善しており、単なる装飾になっていない。
- HTMLの基本構造とCSSに明らかな構文エラーがない。

---

## 参照

- `@memory:execution-efficiency` - 実行効率化詳細（Phase 0/1/2）
- `.claude/rules/workflow/RULES.md` - Planning Efficiency ルール
- `~/.claude/lessons/lessons.md` - Rule 15 教訓蓄積ファイル
