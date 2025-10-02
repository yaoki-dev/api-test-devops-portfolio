# API Test + DevOps Portfolio

APIテスト + DevOps統合学習ポートフォリオ

## 概要

このプロジェクトは、APIテストとDevOps技術を統合した実践的なポートフォリオです。
時給6000-8000円レベルの技術力を証明するために設計されています。

## 技術スタック

- **Python**: 3.10以上
- **HTTP Client**: httpx（同期/非同期対応）
- **Configuration**: Pydantic Settings（型安全な設定管理）
- **Testing**: pytest（非同期テスト、パラメータ化テスト対応）
- **Package Manager**: uv

## セットアップ

```bash
# 依存関係のインストール
uv sync

# テスト実行
uv run pytest

# 特定のテストマーカー実行
uv run pytest -m unit
uv run pytest -m integration
```

## プロジェクト構成

```
api-test-devops-portfolio/
├── config/          # 設定管理
├── utils/           # ユーティリティ（APIクライアント等）
├── tests/           # テストスイート
│   ├── unit/        # 単体テスト
│   ├── integration/ # 統合テスト
│   ├── e2e/         # E2Eテスト
│   ├── performance/ # パフォーマンステスト
│   └── security/    # セキュリティテスト
└── docs/            # ドキュメント
```

## 学習目標

- 実務レベルのAPIテスト設計・実装
- 非同期プログラミングパターン
- 型安全な設定管理
- エラーハンドリングベストプラクティス
- pytest活用による高品質テスト

## ライセンス

MIT