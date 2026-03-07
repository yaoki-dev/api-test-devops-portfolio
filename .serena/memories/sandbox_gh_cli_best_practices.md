# サンドボックス環境でのgh CLI ベストプラクティス

*作成日: 2026-01-23*

## 概要

Claude Codeのサンドボックス環境でGitHub CLI (`gh`) を使用する際の注意事項と推奨パターン。

## 問題: HEREDOCによるbody空問題

### 発生事象
Issue #133作成時、詳細なbodyを指定したにもかかわらず空で作成された。

### 根本原因
```bash
# ❌ 失敗パターン
gh issue create --title "タイトル" --body "$(cat <<'EOF'
長い内容...
EOF
)"
```

シェルのHEREDOC (`<<EOF`) は内部で一時ファイルを作成することがあり、サンドボックスの書き込み制限（`/tmp/claude/` 以外への書き込み禁止）に抵触。

コマンド自体は「成功」と報告されるが、bodyパラメータが空文字列として渡される。

## 推奨パターン

### パターン1: --body-file 使用（長文向け・推奨）
```bash
# 一時ファイルに書き込み
cat > /tmp/claude/issue_body.md << 'EOF'
## 概要
詳細な内容...

## 詳細
- ポイント1
- ポイント2
EOF

# Issue作成
gh issue create --title "タイトル" --body-file /tmp/claude/issue_body.md

# クリーンアップ
rm /tmp/claude/issue_body.md
```

### パターン2: 直接--body指定（短文向け）
```bash
# 短い内容なら直接指定
gh issue create --title "タイトル" --body "短い説明文"
```

### パターン3: 変数経由（中程度の長さ）
```bash
BODY="## 概要
内容をここに記載"

gh issue create --title "タイトル" --body "$BODY"
```

## 適用範囲

| コマンド | 影響 | 対策 |
|---------|------|------|
| `gh issue create --body` | あり | --body-file使用 |
| `gh pr create --body` | あり | --body-file使用 |
| `gh issue edit --body` | あり | --body-file使用 |
| `gh issue comment --body` | あり | --body-file使用 |

## 検証方法

作成後に必ず確認:
```bash
gh issue view <番号> --json body | jq '.body | length'
# 0 なら失敗
```

## 関連
- CLAUDE.md「サンドボックス環境でのIssue/PR作成時の注意」セクション
- Issue #133（この教訓の発見元）
