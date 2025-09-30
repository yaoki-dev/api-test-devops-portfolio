# 環境検証コマンド集

*最終更新: 2025年09月21日*

## 🔧 事前準備確認システム

すべての学習コマンド実行前に、以下の環境検証を必ず実行してください。

### Python環境確認
```bash
# Python バージョン確認（3.10-3.12必須）
python --version | grep -E "3\.(10|11|12)" || {
    echo "❌ Python 3.10-3.12が必要です"
    echo "💡 推奨: pyenv install 3.12 && pyenv global 3.12"
    exit 1
}
echo "✅ Python環境確認完了"

# uv パッケージマネージャー確認
uv --version || {
    echo "❌ uvが見つかりません"
    echo "💡 インストール: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
}
echo "✅ uv環境確認完了"
```

### Docker環境確認
```bash
# Docker確認
docker --version || {
    echo "❌ Dockerが見つかりません"
    echo "💡 インストール: https://docs.docker.com/get-docker/"
    exit 1
}

# Docker Compose確認
docker-compose --version || {
    echo "❌ Docker Composeが見つかりません"
    echo "💡 インストール: Docker Desktopに含まれています"
    exit 1
}

# Docker稼働確認
docker ps > /dev/null 2>&1 || {
    echo "❌ Dockerサービスが起動していません"
    echo "💡 起動: Docker Desktopを開くか 'sudo systemctl start docker'"
    exit 1
}
echo "✅ Docker環境確認完了"
```

### プロジェクト依存関係確認
```bash
# 必要ディレクトリ存在確認
for dir in utils tests config; do
    if [ ! -d "$dir" ]; then
        echo "❌ 必要ディレクトリ $dir が見つかりません"
        echo "💡 正しいプロジェクトルートから実行してください"
        exit 1
    fi
done
echo "✅ プロジェクト構造確認完了"

# pyproject.toml存在確認
if [ ! -f "pyproject.toml" ]; then
    echo "❌ pyproject.tomlが見つかりません"
    echo "💡 プロジェクトルートから実行してください"
    exit 1
fi
echo "✅ pyproject.toml確認完了"

# 依存関係同期
uv sync || {
    echo "❌ 依存関係の同期に失敗しました"
    echo "💡 uv.lockファイルを確認してください"
    exit 1
}
echo "✅ 依存関係同期完了"
```

## 🛡️ エラーハンドリング付きコマンド

### 品質管理ツール（Week 3）
```bash
#!/bin/bash
# 品質管理統合実行（エラーハンドリング付き）

echo "🔍 品質管理ツール統合実行開始"

# ruff品質チェック
echo "📝 ruffリンター実行中..."
if uv run ruff check utils/ tests/ --output-format=json | tee ruff_results.json; then
    echo "✅ ruff品質チェック完了"
else
    echo "⚠️ ruffで品質問題が検出されました"
    echo "💡 修正: uv run ruff check utils/ tests/ --fix"
fi

# mypy型チェック
echo "🔍 mypy型チェック実行中..."
if uv run mypy utils/ --strict --show-error-codes; then
    echo "✅ mypy型チェック完了"
else
    echo "⚠️ mypy型エラーが検出されました"
    echo "💡 型ヒントを追加するか、設定を調整してください"
fi

# 統合テスト実行
echo "🧪 統合テスト実行中..."
if uv run pytest tests/unit/test_api_client.py -v --tb=short; then
    echo "✅ 統合テスト完了"
else
    echo "❌ テストが失敗しました"
    echo "💡 ログを確認して問題を修正してください"
    exit 1
fi

echo "🎉 Week 3品質管理統合完了"
```

### セキュリティスキャン（Week 3）
```bash
#!/bin/bash
# セキュリティスキャン統合実行

echo "🛡️ セキュリティスキャン開始"

# banditセキュリティチェック
echo "🔒 banditセキュリティチェック実行中..."
if uv run bandit -r utils/ tests/ -f json -o security_scan_results.json; then
    echo "✅ banditスキャン完了"

    # 結果分析
    if [ -f security_scan_results.json ]; then
        issues=$(jq '.results | length' security_scan_results.json 2>/dev/null || echo "0")
        echo "📊 検出されたセキュリティ問題: ${issues}件"

        if [ "$issues" -gt 0 ]; then
            echo "⚠️ セキュリティ問題が検出されました"
            echo "💡 詳細: cat security_scan_results.json | jq '.results[].issue_text'"
        fi
    fi
else
    echo "❌ banditスキャンでエラーが発生しました"
fi

# safety脆弱性チェック
echo "🔍 safety脆弱性チェック実行中..."
if uv run safety check --json --output safety_report.json; then
    echo "✅ safety脆弱性チェック完了"

    # 結果分析
    if [ -f safety_report.json ]; then
        vulnerabilities=$(jq '. | length' safety_report.json 2>/dev/null || echo "0")
        echo "📊 検出された脆弱性: ${vulnerabilities}件"

        if [ "$vulnerabilities" -gt 0 ]; then
            echo "⚠️ 脆弱性が検出されました"
            echo "💡 対応: uv add [セキュアなバージョン]"
        fi
    fi
else
    echo "⚠️ safety脆弱性チェックで警告がありました"
    echo "💡 全ての脆弱性を確認してください"
fi

echo "🎉 セキュリティスキャン完了"
```

## 🚨 バンコク環境特化トラブルシューティング

### 停電・ネットワーク対応
```bash
#!/bin/bash
# バンコク環境レジリエンス確認

echo "🌏 バンコク環境特化チェック開始"

# UPS電源確認
if command -v upsc > /dev/null 2>&1; then
    upsc_status=$(upsc ups 2>/dev/null || echo "not_available")
    if [ "$upsc_status" != "not_available" ]; then
        echo "🔋 UPS電源確認: 接続済み"
    else
        echo "⚠️ UPS電源が検出されません"
        echo "💡 推奨: UPS設置で停電対策を強化"
    fi
else
    echo "💡 UPS監視ツール未インストール（任意）"
fi

# モバイル4G冗長性確認
ping -c 1 8.8.8.8 > /dev/null 2>&1
primary_connection=$?

if [ $primary_connection -eq 0 ]; then
    echo "✅ プライマリネットワーク接続良好"
else
    echo "⚠️ プライマリネットワーク接続に問題があります"
    echo "💡 モバイル4Gホットスポットの準備を確認してください"
fi

# セッション自動保存設定確認
if [ -f ".vscode/settings.json" ]; then
    auto_save=$(grep -o '"files.autoSave": "[^"]*"' .vscode/settings.json || echo "not_configured")
    if [[ "$auto_save" == *"afterDelay"* ]]; then
        echo "✅ 自動保存設定確認済み"
    else
        echo "💡 推奨: VSCode自動保存設定 (files.autoSave: afterDelay)"
    fi
fi

echo "🎉 バンコク環境チェック完了"
```

### 気候適応スケジュール
```bash
#!/bin/bash
# バンコク気候適応学習スケジュール

current_hour=$(date +%H)
current_month=$(date +%m)

echo "🌡️ バンコク気候適応スケジュール確認"

# 時間帯別推奨度
if [ $current_hour -ge 6 ] && [ $current_hour -le 9 ]; then
    echo "🌅 最適学習時間: 朝の涼しい時間帯（効率1.2倍）"
    productivity_multiplier="1.2"
elif [ $current_hour -ge 20 ] && [ $current_hour -le 22 ]; then
    echo "🌙 標準学習時間: 夜間の快適時間帯（効率1.1倍）"
    productivity_multiplier="1.1"
elif [ $current_hour -ge 13 ] && [ $current_hour -le 16 ]; then
    echo "🌞 避けるべき時間: 猛暑時間帯（効率0.9倍）"
    productivity_multiplier="0.9"
    echo "💡 推奨: エアコン使用または他の時間帯に変更"
else
    echo "⏰ 標準時間帯: 通常の学習効率"
    productivity_multiplier="1.0"
fi

# 季節適応
if [ $current_month -ge 11 ] || [ $current_month -le 2 ]; then
    echo "❄️ 乾季: 学習に最適な季節（効率1.15倍ボーナス）"
    echo "💡 推奨: 長時間学習セッション可能（最大4時間）"
elif [ $current_month -ge 6 ] && [ $current_month -le 10 ]; then
    echo "🌧️ 雨季: 停電・ネットワーク障害注意"
    echo "💡 推奨: 短時間セッション（最大2.5時間）＋頻繁な保存"
else
    echo "🌡️ 暑季: 暑さ対策重要"
    echo "💡 推奨: 早朝・夜間集中学習"
fi

echo "📊 現在の推定学習効率: ${productivity_multiplier}倍"
echo "🎯 バンコク環境適応完了"
```

## 📝 使用方法

### 学習開始前の必須チェック
```bash
# 環境確認スクリプトを実行
bash docs/learning/ENVIRONMENT_VALIDATION_COMMANDS.md

# 全ての✅が表示されることを確認
# ❌や⚠️がある場合は、指示に従って修正
```

### トラブルシューティング手順
1. **エラーが発生した場合**: エラーメッセージを確認
2. **💡マークの指示に従う**: 具体的な解決方法を実行
3. **再実行**: 問題が解決されたら再度実行
4. **エスカレーション**: 解決しない場合はAIサポートに相談

---

**このガイドにより、学習環境の安定性と問題解決能力が大幅に向上します。**