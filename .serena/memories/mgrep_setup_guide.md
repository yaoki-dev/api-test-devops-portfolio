# mgrep（Semantic Code Search）セットアップガイド

*最終更新: 2026年02月14日*

## 概要

mgrepは意味的関連性でコードを検索するセマンティックコード検索ツール。Mixedbread製。

**用途:**
- ローカル開発: 高度なコード検索（任意）
- CI/CD: PRレビュー時の自動検索（必須、GitHub Actions統合済み）

**vs ast-grep:**
- **mgrep**: セマンティック検索、意味的関連性、文書構造探索推奨
- **ast-grep**: AST構造解析、構文的正確性、コード変更時必須

---

## インストール

### 方法1: package.json経由（推奨）

```bash
npm install  # devDependenciesに記載済み（@mixedbread/mgrep@0.1.10）
```

### 方法2: グローバルインストール

```bash
npm install -g @mixedbread/mgrep
```

---

## 認証設定

### ローカル開発: ブラウザ認証（推奨）

```bash
mgrep login
```

- ブラウザが自動起動
- Mixedbreadアカウントで認証（GitHub/Google OAuth対応）
- 認証情報は `~/.config/mgrep/` に保存

### CI/CD環境: API Key認証（必須）

**1. API Key取得:**
1. https://www.mixedbread.ai/ でアカウント作成
2. Dashboard → API Keys → Create API Key
3. Key形式: `mxbai_sk_[ランダム文字列]`

**2. GitHub Secrets設定:**
- Settings → Secrets and variables → Actions
- `MXBAI_API_KEY` に上記API Keyを設定

**3. CI workflow統合:**
- `.github/workflows/claude-code-review.yml` に設定済み
- `MCP_CONFIG` 内で `${{ secrets.MXBAI_API_KEY }}` を参照

---

## 使用例

### 基本検索

```bash
# セマンティック検索（意味的に関連するコードを検索）
mgrep search "API error handling" . --limit 5

# 検索結果の内容も表示
mgrep search "authentication" . --content

# 特定ディレクトリ内検索
mgrep search "database query" ./utils --limit 10
```

### 高度な使用

```bash
# 詳細ヘルプ
mgrep --help

# バージョン確認
mgrep --version
```

---

## トラブルシューティング

### `MXBAI_API_KEY not found`（CI環境）

**原因:** GitHub Secrets未設定

**対処:**
1. GitHub Settings → Secrets確認
2. `MXBAI_API_KEY` が存在するか確認
3. 存在しない場合: Task 3（GitHub Secrets登録）を再実行

### `authentication failed`（ローカル）

**原因:** ブラウザ認証未完了

**対処:**
```bash
mgrep logout
mgrep login  # 再認証
```

### `command not found: mgrep`

**原因:** グローバルインストール未実行

**対処:**
```bash
npm install -g @mixedbread/mgrep
# または
npx @mixedbread/mgrep search "..." .
```

---

## 参考リンク

- [mgrep公式ドキュメント](https://github.com/mixedbread-ai/mgrep)
- [Mixedbread Dashboard](https://www.mixedbread.ai/)
- [ast-grep/ast-grep-mcp](https://github.com/ast-grep/ast-grep-mcp)（併用推奨）

---

## プロジェクト統合状況

**package.json:**
```json
"devDependencies": {
  "@mixedbread/mgrep": "^0.1.10"
}
```

**CI/CD統合:**
- `.github/workflows/claude-code-review.yml` Line 16, 19, 21
- MCP server: `morph-mcp`
- 環境変数: `MXBAI_API_KEY`（GitHub Secrets）

**.env.example:**
- `MXBAI_API_KEY` プレースホルダー追加済み
