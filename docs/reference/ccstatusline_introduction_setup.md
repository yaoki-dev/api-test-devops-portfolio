# ccstatusline 導入・設定

*最終更新: 2025年11月13日*

## 📋 目次

1. [現状確認](#現状確認)
2. [ccstatuslineの仕組み](#ccstatuslineの仕組み)
3. [グローバル使用の確認](#グローバル使用の確認)
4. [プロジェクト推奨設定](#プロジェクト推奨設定)
5. [設定方法の詳細](#設定方法の詳細)
6. [カスタマイズ例](#カスタマイズ例)
7. [トラブルシューティング](#トラブルシューティング)

---

## 現状確認

### ✅ すでに導入済み

あなたの環境では、ccstatuslineはすでに設定されています：

```bash
# 設定ファイル: ~/.config/ccstatusline/settings.json
# Node.js: v24.4.1
# npm: 11.4.2
```

### 現在の設定内容

```json
{
  "version": 3,
  "lines": [
    [
      {"type": "model", "color": "cyan"},
      {"type": "separator"},
      {"type": "context-length", "color": "brightBlack"},
      {"type": "separator"},
      {"type": "git-branch", "color": "magenta"},
      {"type": "separator"},
      {"type": "git-changes", "color": "yellow"}
    ]
  ]
}
```

**表示内容**:

- 🔵 モデル名 (cyan)
- ⚫ コンテキスト長 (brightBlack)
- 🟣 Gitブランチ (magenta)
- 🟡 Git変更数 (yellow)

---

## ccstatuslineの仕組み

### 🌍 グローバルアクセスの仕組み

ccstatuslineは**すでにグローバルに使用可能**です。以下の理由により：

1. **npx による自動実行**

   ```bash
   npx ccstatusline@latest
   ```

   - npmがパッケージを自動ダウンロード
   - 任意のディレクトリから実行可能
   - `/Users/yuta/` でも `/Users/yuta/Yuta/python/api-test-devops-portfolio/` でも同じ

2. **共通設定ファイル**

   ```
   ~/.config/ccstatusline/settings.json
   ```

   - ユーザーホームディレクトリに保存
   - すべてのプロジェクトで共通の設定を使用
   - プロジェクト固有の設定も可能（後述）

### 🔄 実行の流れ

```
Claude Code起動
    ↓
claudeConfig.statuslineCommand 読み込み
    ↓
npx ccstatusline@latest 実行
    ↓
~/.config/ccstatusline/settings.json 読み込み
    ↓
現在のディレクトリでGit情報等を取得
    ↓
ステータスライン表示
```

---

## グローバル使用の確認

### 動作確認手順

#### 1. プロジェクトディレクトリで確認

```bash
cd /Users/yuta/Yuta/python/api-test-devops-portfolio
npx ccstatusline@latest
```

**期待される動作**:

- モデル名、コンテキスト長が表示される
- Gitブランチ（例: `local/history`）が表示される
- Git変更数が表示される

#### 2. 別のディレクトリで確認

```bash
cd /Users/yuta/
npx ccstatusline@latest
```

**期待される動作**:

- 同じ設定で動作する
- Gitリポジトリがない場合、Git関連ウィジェットは非表示
- モデル名とコンテキスト長は表示される

#### 3. Claude Code設定確認

```bash
cat ~/.config/claude/config.yaml | grep statusline
```

**期待される出力**:

```yaml
statuslineCommand: npx ccstatusline@latest
```

---

## プロジェクト推奨設定

### 🎯 Python/DevOpsポートフォリオ向け最適設定

あなたのプロジェクトに最適化した設定を提案します：

#### 推奨ウィジェット構成

```json
{
  "version": 3,
  "lines": [
    [
      {"type": "model", "color": "cyan"},
      {"type": "separator"},
      {"type": "token-input", "color": "green"},
      {"type": "token-output", "color": "yellow"},
      {"type": "token-total", "color": "brightBlack"},
      {"type": "separator"},
      {"type": "context-percentage", "color": "magenta"},
      {"type": "separator"},
      {"type": "git-branch", "color": "blue"},
      {"type": "git-changes", "color": "red"},
      {"type": "separator"},
      {"type": "session-clock", "color": "brightBlack"},
      {"type": "separator"},
      {"type": "cwd", "color": "brightCyan"}
    ]
  ],
  "flexMode": "full-minus-40",
  "compactThreshold": 60,
  "powerline": {
    "enabled": false
  }
}
```

#### 表示内容の説明

| ウィジェット | 色 | 説明 | プロジェクトでの活用 |
|------------|-----|------|-------------------|
| **model** | cyan | モデル名 | Sonnet 4.5使用中を確認 |
| **token-input** | green | 入力トークン数 | トークン使用量モニタリング |
| **token-output** | yellow | 出力トークン数 | 応答サイズ確認 |
| **token-total** | brightBlack | 合計トークン数 | 200k上限管理 |
| **context-percentage** | magenta | コンテキスト使用率 | 75%超えでMCP切替判断 |
| **git-branch** | blue | 現在のブランチ | feature/main切替確認 |
| **git-changes** | red | 変更ファイル数 | コミット前の変更確認 |
| **session-clock** | brightBlack | セッション時間 | 学習時間記録に活用 |
| **cwd** | brightCyan | 作業ディレクトリ | プロジェクトルート確認 |

### 📊 トークン効率化との連携

あなたの `MODE_Token_Efficiency.md` と連携：

```markdown
トークン使用率判定フロー:

0-50%: オリジナルMCP使用可能
  └─ context-percentage: 緑色表示

51-75%: 注意ゾーン
  └─ context-percentage: 黄色表示推奨

76-90%: ラッパーMCP推奨
  └─ context-percentage: マゼンタ表示（現在設定）

91-100%: ラッパーMCP必須
  └─ context-percentage: 赤色表示推奨
```

---

## 設定方法の詳細

### 方法1: インタラクティブTUI（推奨）

```bash
# 設定画面を開く
npx ccstatusline@latest
```

**操作手順**:

1. ターミナルでコマンド実行
2. TUI（テキストユーザーインターフェース）が起動
3. 矢印キーで操作、Enterで選択
4. ウィジェット追加/削除/並び替え
5. 色をカスタマイズ
6. リアルタイムプレビュー
7. 自動保存（`~/.config/ccstatusline/settings.json`）

### 方法2: 設定ファイル直接編集

```bash
# 設定ファイルを編集
nano ~/.config/ccstatusline/settings.json
```

**注意点**:

- JSON形式を正確に保つ
- 保存後、次回起動時に反映
- バックアップ推奨: `cp ~/.config/ccstatusline/settings.json ~/.config/ccstatusline/settings.json.bak`

### 利用可能なウィジェット一覧

| タイプ | 説明 | 必要条件 |
|-------|------|---------|
| `model` | モデル名 | - |
| `git-branch` | Gitブランチ | Gitリポジトリ |
| `git-changes` | Git変更数 | Gitリポジトリ |
| `session-clock` | セッション時間 | - |
| `session-cost` | セッションコスト | Claude Code 1.0.85+ |
| `block-timer` | ブロック実行時間 | - |
| `cwd` | 作業ディレクトリ | - |
| `token-input` | 入力トークン数 | - |
| `token-output` | 出力トークン数 | - |
| `token-cached` | キャッシュトークン数 | - |
| `token-total` | 合計トークン数 | - |
| `context-length` | コンテキスト長 | - |
| `context-percentage` | コンテキスト使用率 | - |
| `custom-text` | カスタムテキスト | - |
| `custom-command` | カスタムコマンド出力 | - |
| `separator` | セパレーター | - |
| `flex-separator` | 伸縮セパレーター | - |

### 色の選択肢

```
基本色: black, red, green, yellow, blue, magenta, cyan, white
明るい色: brightBlack, brightRed, brightGreen, brightYellow,
         brightBlue, brightMagenta, brightCyan, brightWhite
```

---

## カスタマイズ例

### 例1: ミニマル設定（シンプル表示）

```json
{
  "version": 3,
  "lines": [
    [
      {"type": "model", "color": "cyan"},
      {"type": "separator"},
      {"type": "git-branch", "color": "magenta"},
      {"type": "separator"},
      {"type": "token-total", "color": "yellow"}
    ]
  ]
}
```

### 例2: フル機能設定（詳細表示）

```json
{
  "version": 3,
  "lines": [
    [
      {"type": "model", "color": "cyan"},
      {"type": "separator"},
      {"type": "token-input", "color": "green"},
      {"type": "token-output", "color": "yellow"},
      {"type": "token-cached", "color": "blue"},
      {"type": "token-total", "color": "brightBlack"},
      {"type": "separator"},
      {"type": "context-percentage", "color": "magenta"},
      {"type": "separator"},
      {"type": "git-branch", "color": "blue"},
      {"type": "git-changes", "color": "red"},
      {"type": "separator"},
      {"type": "session-clock", "color": "brightBlack"},
      {"type": "session-cost", "color": "green"},
      {"type": "separator"},
      {"type": "cwd", "color": "brightCyan"}
    ]
  ]
}
```

### 例3: 推奨ウィジェット設定（Python/DevOpsポートフォリオ向け）

このプロジェクトに最適化した推奨設定：

```json
{
  "version": 3,
  "lines": [
    [
      {"type": "model", "color": "cyan"},
      {"type": "separator"},
      {"type": "token-input", "color": "green"},
      {"type": "token-output", "color": "yellow"},
      {"type": "token-total", "color": "brightBlack"},
      {"type": "separator"},
      {"type": "context-percentage", "color": "magenta"},
      {"type": "separator"},
      {"type": "git-branch", "color": "blue"},
      {"type": "git-changes", "color": "red"},
      {"type": "separator"},
      {"type": "session-clock", "color": "brightBlack"},
      {"type": "separator"},
      {"type": "cwd", "color": "brightCyan"}
    ]
  ],
  "flexMode": "full-minus-40",
  "compactThreshold": 60,
  "powerline": {
    "enabled": false
  }
}
```

**各ウィジェットの活用方法**:

| ウィジェット | 色 | アイコン | 活用シーン |
|------------|-----|---------|-----------|
| **model** | cyan | 🔵 | Sonnet 4.5使用中を確認 |
| **token-input** | green | 🟢 | 入力トークン使用量モニタリング |
| **token-output** | yellow | 🟡 | 出力トークン使用量モニタリング |
| **token-total** | brightBlack | ⚫ | 合計トークン数で200k上限管理 |
| **context-percentage** | magenta | 🟣 | 75%超えでMCP切替判断（MODE_Token_Efficiency連携） |
| **git-branch** | blue | 🔵 | featureブランチ/mainブランチ切替確認 |
| **git-changes** | red | 🔴 | コミット前の変更ファイル数確認 |
| **session-clock** | brightBlack | ⚫ | 学習時間記録（daily_progress.md連携） |
| **cwd** | brightCyan | 🔵 | プロジェクトルート確認 |

**設定のポイント**:

- トークン効率化モードとの連携（context-percentage）
- 学習時間記録の可視化（session-clock）
- Git運用との整合性（git-branch/changes）

### 例4: プロジェクト固有設定

プロジェクトごとに異なる設定を使用する場合：

```bash
# 環境変数で設定ディレクトリを変更
export CLAUDE_CONFIG_DIR=/Users/yuta/Yuta/python/api-test-devops-portfolio/.claude-config

# この後にClaude Codeを起動すると、プロジェクト固有の設定を使用
```

**手順**:

1. プロジェクトルートに `.claude-config` ディレクトリ作成
2. 環境変数設定（`~/.zshrc` または `~/.bashrc` に追加）
3. Claude Code再起動

---

## トラブルシューティング

### 問題1: ステータスラインが表示されない

**確認事項**:

```bash
# Claude Config確認
cat ~/.config/claude/config.yaml | grep statusline

# Node.js確認
node --version

# npx動作確認
npx ccstatusline@latest
```

**解決策**:

```yaml
# ~/.config/claude/config.yaml に追加
statuslineCommand: npx ccstatusline@latest
```

### 問題2: Git情報が表示されない

**原因**: Gitリポジトリ外で実行している

**確認**:

```bash
git status
# → fatal: not a git repository の場合、Git外
```

**解決策**:

- Gitリポジトリ内で実行
- または Git関連ウィジェットを削除

### 問題3: トークン情報が表示されない

**原因**: Claude Codeのバージョンが古い

**確認**:

```bash
claude --version
```

**解決策**:

- Claude Codeを最新版にアップデート（1.0.85+推奨）

### 問題4: 設定が反映されない

**確認事項**:

```bash
# 設定ファイルのJSON検証
cat ~/.config/ccstatusline/settings.json | python -m json.tool
```

**解決策**:

- JSON形式エラーを修正
- バックアップから復元: `cp ~/.config/ccstatusline/settings.json.bak ~/.config/ccstatusline/settings.json`
- またはTUIで再設定: `npx ccstatusline@latest`

### 問題5: パフォーマンスが遅い

**原因**: ウィジェットが多すぎる、またはカスタムコマンドが重い

**解決策**:

- 不要なウィジェットを削除
- カスタムコマンドを最適化
- `compactThreshold` を調整

---

## 📚 参考リンク

- **公式リポジトリ**: <https://github.com/sirmalloc/ccstatusline>
- **Claude Code公式ドキュメント**: <https://docs.claude.com/en/docs/claude-code>
- **プロジェクトCLAUDE.md**: `/Users/yuta/Yuta/python/api-test-devops-portfolio/CLAUDE.md`

---

## 🎓 学習・実装記録との連携

### トークン使用率モニタリング

```bash
# context-percentage ウィジェットを追加して、リアルタイムでトークン使用率を監視
# 75%超えたらラッパーMCP切替（MODE_Token_Efficiency.md参照）
```

### セッション時間記録

```bash
# session-clock ウィジェットで学習時間を可視化
# daily_progress.md の記録と照合
```

### Git状態確認

```bash
# git-branch: featureブランチ作業確認
# git-changes: コミット前の変更確認
```

---

## ✅ 次のステップ

1. **現在の設定を確認**:

   ```bash
   cat ~/.config/ccstatusline/settings.json
   ```

2. **推奨設定を適用**（任意）:

   ```bash
   npx ccstatusline@latest
   # TUIで推奨ウィジェットを追加
   ```

3. **プロジェクトで動作確認**:

   ```bash
   cd /Users/yuta/Yuta/python/api-test-devops-portfolio
   # Claude Code起動 → ステータスライン表示確認
   ```

4. **カスタマイズ**:
   - 色を変更
   - ウィジェットを追加/削除
   - レイアウトを調整

---

**以上で、ccstatuslineのグローバル導入と設定が完了です！** 🎉
