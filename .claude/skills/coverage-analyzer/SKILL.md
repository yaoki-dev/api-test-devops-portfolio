---
name: coverage-analyzer
description: |
  テストカバレッジ分析とテスト生成ガイダンス。coverage.jsonを解析し、
  未カバー行/ブランチを特定、優先度付きテスト作成提案を出力。
  トリガー: "カバレッジ分析", "coverage analyze", "テストカバレッジ向上", "未カバー行"
---

# Coverage Analyzer Skill

*最終更新: 2025年11月30日*

## 概要

このSkillは`coverage.json`を解析し、カバレッジ向上のための具体的なアクションを提示します。

## 実行手順

### Step 1: coverage.jsonの読み込み

```bash
# 最新のcoverage.jsonを生成（必要な場合）
uv run pytest --cov=. --cov-report=json

# coverage.jsonを読み込む
Read("coverage.json")
```

### Step 2: カバレッジ解析

以下の情報を抽出・分析:

1. **全体カバレッジ**: `totals.percent_covered`
2. **ファイル別カバレッジ**: `files[*].summary.percent_covered`
3. **未カバー行**: `files[*].missing_lines`
4. **未カバーブランチ**: `files[*].missing_branches`
5. **関数別カバレッジ**: `files[*].functions[*].summary`

### Step 3: 優先度判定

以下の基準で改善優先度を決定:

| 優先度 | 条件 | アクション |
|-------|------|----------|
| **P0 (Critical)** | カバレッジ < 50% | 即座にテスト追加必須 |
| **P1 (High)** | 50% <= カバレッジ < 70% | 次スプリントでテスト追加 |
| **P2 (Medium)** | 70% <= カバレッジ < 85% | 計画的にテスト追加 |
| **P3 (Low)** | カバレッジ >= 85% | 維持・最適化 |

### Step 4: レポート出力

以下の形式でレポートを出力:

```markdown
## カバレッジ分析レポート

**生成日時**: YYYY-MM-DD HH:MM
**現在カバレッジ**: XX.XX%
**目標カバレッジ**: 85% (Week 6目標)

### ファイル別優先度

| ファイル | カバレッジ | 未カバー行数 | 優先度 |
|---------|----------|------------|-------|
| models/responses.py | 0.00% | 77行 | P0 |
| utils/api_client.py | 57.56% | 125行 | P1 |
| config/settings.py | 96.15% | 3行 | P3 |

### P0/P1ファイルの改善提案

#### models/responses.py (P0: 0.00% → 目標70%)

**未カバー関数**:
- `sanitize_user_content()` (L42-45)
- `Post.sanitize_post_content()` (L87)
- その他7関数

**推奨テスト**:
```python
# tests/unit/test_responses.py

import pytest
from models.responses import Post, sanitize_user_content

class TestSanitizeUserContent:
    def test_sanitize_removes_script_tags(self):
        """XSSペイロードがサニタイズされることを確認"""
        malicious = "<script>alert('xss')</script>"
        result = sanitize_user_content(malicious)
        assert "<script>" not in result

    def test_sanitize_preserves_safe_content(self):
        """安全なコンテンツが保持されることを確認"""
        safe = "Hello, World!"
        result = sanitize_user_content(safe)
        assert result == safe
```

#### utils/api_client.py (P1: 57.56% → 目標75%)

**未カバー領域**:
- `BaseAPIClient._make_request_with_retry()` (L176-252) - リトライロジック
- `JSONPlaceholderClient` 全メソッド (L329-418) - 同期クライアント
- `main()` (L820-861) - CLI エントリポイント

**推奨テスト**:
```python
# tests/unit/test_base_api_client.py

import pytest
from unittest.mock import Mock, patch
from utils.api_client import BaseAPIClient

class TestBaseAPIClientRetry:
    @pytest.fixture
    def client(self):
        return BaseAPIClient(
            base_url="https://example.com",
            retry_count=3,
            retry_delay=0.1
        )

    def test_retry_on_5xx_error(self, client):
        """5xxエラー時にリトライすることを確認"""
        # モック設定とテスト実装
        pass

    def test_no_retry_on_4xx_error(self, client):
        """4xxエラー時は即座に失敗することを確認"""
        pass
```

### カバレッジ目標達成ロードマップ

| Week | 目標 | 主要タスク |
|------|-----|----------|
| 現在 | 65.19% | - |
| +1 | 70% | models/responses.py テスト追加 |
| +2 | 75% | BaseAPIClient リトライテスト追加 |
| +3 | 80% | JSONPlaceholderClient テスト追加 |
| +4 | 85% | 残り未カバー行のテスト追加 |
```

## 使用例

### 基本使用

```
ユーザー: カバレッジ分析
Claude: [coverage.jsonを読み込み、上記レポートを生成]
```

### 特定ファイル分析

```
ユーザー: utils/api_client.py のカバレッジ分析
Claude: [該当ファイルの詳細分析とテスト提案を出力]
```

### 目標設定付き分析

```
ユーザー: カバレッジを70%に上げるための分析
Claude: [70%達成に必要な最小限のテスト追加を提案]
```

## 関連リソース

- **品質ゲート**: @memory:implementation_quality_gates
- **テスト戦略**: @memory:test_strategy_part1_overview
- **フィクスチャ参照**: @memory:fixture_quick_reference
- **conftest.py**: `tests/conftest.py` (18フィクスチャ)

## 注意事項

1. **coverage.jsonの鮮度**: 分析前に`uv run pytest --cov`を実行して最新化
2. **除外ファイル**: `# pragma: no cover`マークされた行は分析対象外
3. **ブランチカバレッジ**: 条件分岐の網羅性も考慮（行カバレッジだけでなく）
4. **テスト品質**: カバレッジ数値だけでなく、有意義なアサーションを重視
