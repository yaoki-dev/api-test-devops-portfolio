#!/bin/bash

# 日次タスク自動実装スクリプト
# 使用方法: ./scripts/daily_task_automation.sh 1 1  # Week 1 Day 1

WEEK=$1
DAY=$2

echo "🎯 Week $WEEK Day $DAY の実装を開始します..."

# 1. タスク情報を抽出してプロンプト生成
echo "📝 プロンプト生成中..."
uv run python scripts/task_to_prompt_converter.py --week $WEEK --day $DAY

# 2. 生成されたプロンプトファイルを取得
PROMPT_FILE=$(ls -t docs/work/prompts/week${WEEK}_day${DAY}_prompt_*.md | head -n 1)

echo "📋 プロンプトファイル: $PROMPT_FILE"

# 3. Claude Codeへの指示を表示
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🤖 以下をClaude Codeに貼り付けてください:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "@$PROMPT_FILE の内容に従って実装してください。"
echo "実装後は以下の品質ゲートを実行してください："
echo "uv run pytest --cov-fail-under=39 && uv run ruff check . && uv run mypy utils/ config/ models/ && git status"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 4. 実装後の確認コマンド
echo ""
echo "✅ 実装完了後の確認コマンド:"
echo "uv run pytest -v tests/unit/"
echo "uv run pytest --cov=utils --cov-report=term-missing"