---
allowed-tools: Bash(gh api:*),Bash(gh pr comment:*),Bash(gh pr diff:*),Bash(gh pr view:*),Bash(mgrep:*)
description: Review a pull request
---

## Step 0: 対応不要判断の抽出

**REPO と PR_NUMBER の取得**:
- `$ARGUMENTS` 形式で渡された場合: 第1引数を REPO（例: `alice/my-repo`）、第2引数を PR_NUMBER として解釈すること
- 引数がない場合: `gh repo view --json nameWithOwner -q .nameWithOwner` で REPO を、`gh pr view --json number -q .number` で PR_NUMBER を自動取得すること

既存PRコメントから「対応不要」判断を抽出する:

```bash
gh api repos/{REPO}/issues/{PR_NUMBER}/comments \
  --jq '[.[] |
    select(.user.login != "claude[bot]") |
    select(.body | test("スキップ|対応不要|skip|wontfix|no need|not needed|対応しない"; "i")) |
    select(.body | test("指摘|issue|#[0-9]"; "i")) |
    {user: .user.login, body: (.body[:150])}] | .[:10]'
```

抽出結果を **DISMISSED_CONTEXT** として保持する（空リストの場合はStep 0スキップ、通常通りレビュー実行）。

> **重要**: 次のステップでエージェントに渡す指示テンプレート内の `{DISMISSED_CONTEXT}` を、ここで取得した実際の値（またはStep 0スキップ時は「なし（対応不要リストなし）」）に置換してからエージェントを起動すること。

## Execution Strategy

**IMPORTANT: Launch all 7 agents in PARALLEL using a single message with multiple Task tool calls.**

Do NOT run agents sequentially. All agents are independent and can run simultaneously.

## Agents to Launch (ALL IN PARALLEL)

Launch these 7 agents in a single message, with the following **additional instructions** for each.

> **置換必須**: 以下の `{DISMISSED_CONTEXT}` を Step 0 で取得した実際の値に置換してから各エージェントに渡すこと（Step 0スキップ時は「なし（対応不要リストなし）」と置換すること）。

```
【重大度分類 - 必須】
各指摘に以下のラベルを付けること:
- 🔴 マージブロッカー: セキュリティ脆弱性 / API契約違反 / データ損失 / 正確性バグ / サイレント障害
- 🟡 品質改善推奨: 可読性 / 命名 / テストカバレッジ向上 / 軽微なリファクタリング / パフォーマンス示唆

【対応不要リスト - 再フラグ禁止】
以下の指摘は作者が「対応不要」と判断済みです。
該当コードが変更されていない限り再フラグしないこと:
{DISMISSED_CONTEXT}
（DISMISSED_CONTEXTが空の場合はこのセクション省略）
```

- code-quality-reviewer
- performance-reviewer
- test-coverage-reviewer
- documentation-accuracy-reviewer
- security-code-reviewer
- silent-failure-hunter
- code-simplicity-reviewer

## Quality Threshold

Instruct each to only report issues with confidence >= 90 (確信度90%以上: 明確な証拠があり、誤検知でないと判断できる問題のみ報告).

## Post-Review

全エージェント完了後、以下の手順で投稿する:

**1. マージ判定サマリーを先頭に投稿（top-level comment）**:

```markdown
## PR #N レビュー判定

| 区分 | 件数 | 対応要否 |
|------|------|---------|
| 🔴 マージブロッカー | N件 | **必須修正** |
| 🟡 品質改善推奨 | M件 | 任意（ポートフォリオ品質向上推奨） |

**マージ判定: ✅ マージ可 / 🔴 N件修正後マージ可**
```

**2. 🔴指摘**: 行番号特定できる場合はinline comment、できない場合はtop-level commentで投稿

**3. 🟡指摘**: 全件を1つのtop-level commentにまとめて投稿（ノイズ軽減）

Review should be in Japanese（日本語でレビューを出力してください）.
