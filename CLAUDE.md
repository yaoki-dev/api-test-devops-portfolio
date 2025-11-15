# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

*最終更新: 2025年10月07日*

## プロジェクト概要

APIテスト + DevOps統合学習ポートフォリオ。時給4000-5000円レベルの技術力を証明するために設計されています。

**技術スタック**:
- Python 3.12
- httpx (Sync + Async HTTP client)
- pytest (累計100テスト作成、カバレッジ85%)
- Pydantic Settings (型安全な設定管理)
- structlog (構造化ログ)
- Docker (Multi-stage builds)
- docker-compose (4環境: dev/test/demo/prod)
- GitHub Actions (CI/CD自動化)

## 📖 Serenaメモリシステムの使い方

このプロジェクトではSerena MCPのメモリ機能を活用し、プロジェクト知識を効率的に管理しています。

**メモリ参照記法**: `@memory:メモリ名`
- 例: `@memory:coding_standards` → コーディング規約を参照
- Claude Codeに「〜を確認」と依頼すると、自動で `read_memory()` を実行

**登録済みメモリ一覧**（14個）:
- `ai_collaboration_workflow`: AI協働学習フロー（3フェーズ学習方法論）
- `coding_standards`: コーディング規約（命名規則、型ヒント、テスト規約）
- `implementation_quality_gates`: 実装品質ゲート（4段階品質チェック）
- `project_file_structure`: プロジェクト構造（コアモジュール、設計パターン）
- `test_strategy`: テスト戦略（単体/結合/性能/セキュリティテスト）
- `workflow_playbooks_guide`: ワークフロープレイブック（13種類の実装パターン）
- `command_usage_guide`: コマンド使用ガイド（ccplugins vs SuperClaude）
- その他: `list_memories()` で全リスト確認可能

**物理ファイル位置**: `.serena/memories/` 配下
- 参照は `@memory:` 記法推奨（ディレクトリ変更に強い）
- 直接読む場合: `Read(".serena/memories/[カテゴリ]/[メモリ名].md")`

**将来**:メモリ数が30個を超えた時点で、カテゴリ別索引を検討

## 📚 学習・進捗管理

@docs/progress/daily_progress.md **CLAUDE.m保持**

### 📋 週次オフセットマッピング（パフォーマンス最適化）
**CLAUDE.md保持 25-273**

大きな学習計画ファイル（40.9k文字）とポートフォリオ戦略ファイル（48k文字）を丸ごと読み込むとパフォーマンス警告が発生するため、Read toolの`offset`/`limit`パラメータを使った部分読み込みを実施します。

#### LEARNING_PLAN_WEEK_MAP

```python
LEARNING_PLAN_WEEK_MAP = {
    # ※ start/end行番号は学習プラン最終確認後に更新予定（Phase 2分離完了後）
    1: {
        "start": "TBD",  # 最終確認後更新
        "end": "TBD",
        "weeks": [1],
        "days": "1-6",
        "hours": 45,
        "title": "Week 1: Python + httpx Core"
    },
    2: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [2],
        "days": "7-12",
        "hours": 45,
        "title": "Week 2: Async基礎"
    },
    3: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [3],
        "days": "13-18",
        "hours": 45,
        "title": "Week 3: Async/Await深化"
    },
    4: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [4],
        "days": "19-24",
        "hours": 45,
        "title": "Week 4: Error Handling深化"
    },
    5: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [5],
        "days": "25-30",
        "hours": 45,
        "title": "Week 5: pytest + Pydantic Settings"
    },
    6: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [6],
        "days": "31-36",
        "hours": 45,
        "title": "Week 6: 統合復習 + 自律チャレンジ"
    },
    7: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [7],
        "days": "37-42",
        "hours": 42,
        "title": "Week 7: Docker基盤構築"
    },
    8: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [8],
        "days": "43-48",
        "hours": 42,
        "title": "Week 8: CI/CD統合"
    },
    9: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [9],
        "days": "49-54",
        "hours": 42,
        "title": "Week 9: ポートフォリオ最適化"
    },
    10: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [10],
        "days": "55-60",
        "hours": 42,
        "title": "Week 10: 応募準備 + 初回応募"
    }
}

LEARNING_PLAN_FILE = "docs/プロジェクト再編/10週ハイブリッドプラン_日次詳細学習スケジュール.md"

# 使用例:
# current_week = learning_state.yaml から取得
# week_key = "1-2" if current_week in [1, 2] else str(current_week)
# config = LEARNING_PLAN_WEEK_MAP[week_key]
# Read(LEARNING_PLAN_FILE, offset=config["start"], limit=config["end"]-config["start"])
```

#### PORTFOLIO_STRATEGY_WEEK_MAP

```python
PORTFOLIO_STRATEGY_FILE = "docs/プロジェクト再編/ポートフォリオ戦略分析.md"

PORTFOLIO_STRATEGY_WEEK_MAP = {
    # ※ start/end行番号は学習プラン最終確認後に更新予定（Phase 2分離完了後）
    1: {
        "start": "TBD",  # 最終確認後更新
        "end": "TBD",
        "weeks": [1],
        "days": "1-6",
        "hours": 30,
        "title": "Week 1: Python + httpx Core"
    },
    2: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [2],
        "days": "7-12",
        "hours": 30,
        "title": "Week 2: Async基礎"
    },
    3: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [3],
        "days": "13-18",
        "hours": 30,
        "title": "Week 3: Async/Await深化"
    },
    4: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [4],
        "days": "19-24",
        "hours": 30,
        "title": "Week 4: Error Handling深化"
    },
    5: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [5],
        "days": "25-30",
        "hours": 30,
        "title": "Week 5: pytest + Pydantic Settings"
    },
    6: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [6],
        "days": "31-36",
        "hours": 30,
        "title": "Week 6: 統合復習 + 自律チャレンジ"
    },
    7: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [7],
        "days": "37-42",
        "hours": 50,
        "title": "Week 7: Docker基盤構築"
    },
    8: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [8],
        "days": "43-48",
        "hours": 60,
        "title": "Week 8: CI/CD統合"
    },
    9: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [9],
        "days": "49-54",
        "hours": 60,
        "title": "Week 9: ポートフォリオ最適化"
    },
    10: {
        "start": "TBD",
        "end": "TBD",
        "weeks": [10],
        "days": "55-60",
        "hours": 60,
        "title": "Week 10: 応募準備 + 初回応募"
    }
}

# 使用例:
# current_week = learning_state.yaml から取得
# config = PORTFOLIO_STRATEGY_WEEK_MAP[current_week]
# Read(PORTFOLIO_STRATEGY_FILE, offset=config["start"], limit=config["end"]-config["start"])
```

#### 統一日次インデックス（Day → Week変換）

```python
def get_week_from_day(current_day: int) -> int:
    """
    Day番号（1-60）からWeek番号（1-10）を取得

    Args:
        current_day: 現在のDay番号（1-60）

    Returns:
        Week番号（1-10の整数）

    Example:
        >>> get_week_from_day(5)   # Day 5 → Week 1
        1
        >>> get_week_from_day(43)  # Day 43 → Week 8
        8
    """
    if current_day <= 6:
        return 1
    elif current_day <= 12:
        return 2
    elif current_day <= 18:
        return 3
    elif current_day <= 24:
        return 4
    elif current_day <= 30:
        return 5
    elif current_day <= 36:
        return 6
    elif current_day <= 42:
        return 7
    elif current_day <= 48:
        return 8
    elif current_day <= 54:
        return 9
    else:
        return 10

# 使用例: learning_state.yamlのcurrent_dayから両方のファイルを部分読み込み
# current_day = 43  # learning_state.yamlから取得
# current_week = get_week_from_day(current_day)
#
# # 学習プラン部分読み込み
# learning_config = LEARNING_PLAN_WEEK_MAP[current_week]
# Read(LEARNING_PLAN_FILE, offset=learning_config["start"],
#      limit=learning_config["end"]-learning_config["start"])
#
# # ポートフォリオ戦略部分読み込み
# portfolio_config = PORTFOLIO_STRATEGY_WEEK_MAP[current_week]
# Read(PORTFOLIO_STRATEGY_FILE, offset=portfolio_config["start"],
#      limit=portfolio_config["end"]-portfolio_config["start"])
```

**パフォーマンス改善効果**:
- フルインポート: 62k tokens消費
- 週次部分読み込み: 2-3k tokens消費（95%削減）
- CLAUDE.mdサイズ: +40行のみ（vs. 日次マッピング+126行）

## 🚀 学習・実装記録自動化トリガー（v2.1）
**CLAUDE.md保持 281-547行**

### トリガー1: 学習開始

**検出キーワード**: `学習開始`

**実行フロー**:
1. **セッション開始時コンテキスト自動補完**:
   ```python
   # learning_state.yaml自動読み込み（セッション開始時）
   import yaml
   from pathlib import Path

   # YAMLファイル読み込み
   state_file = Path("docs/progress/learning_state.yaml")
   with open(state_file, "r", encoding="utf-8") as f:
       state = yaml.safe_load(f)

   # 状態取得
   current_week = state["current_week"]
   current_day = state["current_day"]
   next_learning_item = state.get("current_learning_item", {})
   skill_mastery = state.get("skill_mastery", {})
   ```

   - `learning_state.yaml`から現在週・日・次学習項目取得
   - 学習計画ファイルから推定時間・目標習熟度取得（週次マップ使用）
   - 自動補完情報をユーザーに提示

2. **確認プロンプト表示**:
   ```
   📚 学習開始: {learning_item_@name}
   📅 Week {week} Day {day}
   ⏱️  推定時間: {estimated_hours}h
   🎯 目標習熟度: 85%（固定）

   ✅ この内容で学習を開始しますか？ (yes/no)
   ```

3. **ユーザー確認後**:
   - `learning_state.yaml`の`current_learning_item`更新
   - セッション開始時刻記録

**所要時間**: 10秒

---

### トリガー2: 実装開始

**検出キーワード**: `実装開始`

**実行フロー**:
1. **セッション開始時コンテキスト自動補完**:
   - `learning_state.yaml`から次の実装タスク取得
   - 実装計画ファイルから推定時間・成果物取得
   - 自動補完情報をユーザーに提示

2. **確認プロンプト表示**:
   ```
   🛠️  実装開始: {task_name}
   📅 Week {week} Day {day}
   ⏱️  推定時間: {estimated_hours}h
   📦 成果物: {deliverables}

   ✅ この内容で実装を開始しますか？ (yes/no)
   ```

3. **ユーザー確認後**:
   - `learning_state.yaml`の`current_implementation_task`更新
   - セッション開始時刻記録

**所要時間**: 10秒

---

### トリガー3: 学習記録 🆕 v2.1改善版

**検出キーワード**: `学習記録`

**実行フロー**:

1. **セッション開始時コンテキスト自動補完**:
   ```yaml
   学習項目: {session_context.next_task.name}
   週・日: Week {current_week} Day {current_day}
   推定時間: {session_context.next_task.estimated_hours}h
   目標習熟度: 85%（固定）
   ```

2. **ユーザー入力（1項目必須）**:
   ```
   ❓ 実際の学習時間: ___h （必須）
   ❓ 課題・ブロッカー: ______ （任意）
   ```

3. **AI自動補完**:
   - 学習成果: AI生成（ユーザー入力から推測）
   - 習熟度計算: `(actual_hours / estimated_hours) * 85`
   - ステータス判定:
     - **85%以上** → **完了**
     - **1~84%** → **要復習**
     - **0%** → **未学習**

4. **learning_state.yaml更新**:
   - `skill_mastery[skill_key].mastery_level` 更新
   - `skill_mastery[skill_key].status` 更新
   - `learning_history[]` 追加

5. **daily_progress.md更新**:
   - 日次学習進捗セクション追加

**所要時間**: 1分（ユーザー入力30秒 + AI処理30秒）

**コマンド例**:
```
学習記録: 5h、課題: volume設定エラー
```

---

### トリガー4: 実装記録（完全自動化版）

**検出キーワード**: `実装記録`

**実行フロー**:

1. **Git解析（完全自動）**:
   ```bash
   # 最終コミットからの変更解析
   git diff HEAD~1..HEAD --stat
   git log -1 --format="%s%n%b"
   ```

2. **品質ゲート実行（完全自動）**:
   ```bash
   uv run pytest --cov=. --cov-fail-under=[Phase別目標]
   uv run ruff check .
   uv run mypy utils/ config/
   ```

3. **実装活動判定（完全自動）**:
   - 全合格 → **実装活動認定**
   - 1つでも失敗 → **実装活動不認定（修正必要）**

4. **メトリクス抽出（完全自動）**:
   - 変更行数: `git diff HEAD~1..HEAD --stat` から抽出
   - 変更ファイル数: 同上
   - テスト数: pytest summary から抽出
   - カバレッジ: pytest coverage report から抽出

5. **learning_state.yaml更新（完全自動）**:
   - `implementation_history[]` 追加
   - メトリクス自動記録

6. **daily_progress.md更新（完全自動）**:
   - 日次実装進捗セクション追加
   - メトリクス変化自動記録

**所要時間**: 30秒（全自動）

**コマンド例**:
```
実装記録
```

---

### トリガー5: 週次振り返り

**検出キーワード**: `週次振り返り`

**実行フロー**:

1. **週次データ集計（完全自動）**:
   - `learning_state.yaml`の`learning_history`から週次集計
   - `implementation_history`から週次集計
   - 週次メトリクス計算（学習時間、実装時間等）

2. **週次レポート生成（AI支援）**:
   ```markdown
   # Week X 週次振り返り

   ## 達成事項
   - 学習: {learning_items_completed}
   - 実装: {implementation_tasks_completed}

   ## メトリクス進捗
   - カバレッジ: {coverage_start}% → {coverage_end}%
   - テスト数: {test_count_start} → {test_count_end}

   ## 次週計画調整
   - {next_week_adjustments}
   ```

3. **daily_progress.md更新（完全自動）**:
   - 週次サマリーセクション追加

4. **次週計画調整提案（AI支援）**:
   - 進捗遅延がある場合の調整案提示

**所要時間**: 2分（集計30秒 + AI生成90秒）

**コマンド例**:
```
週次振り返り
```

---

### トリガー6: 理解度確認（毎日実施）

**検出キーワード**: `理解度確認`

**実施対象期間**: Week 1-7（Day 1-42）の学習期間
**実施除外期間**: Week 8-9（Day 43-54）は案件応募準備タスク期間のため不要

**概要**:
- Phase 2完了（品質ゲート全合格 + git commit完了）後に実施
- AI自動生成問題（3問・25点満点）で理解度確認
- 合格基準: 20点以上/25点（80%以上）
- 不合格時は復習ループ（最大3回）

**詳細仕様**: トリガー6の詳細は必要時に部分参照（@記法は49k chars全体読み込みでパフォーマンス警告）

```python
# トリガー詳細セクションのオフセットマップ
TRIGGER_SECTION_MAP = {
    "trigger_6": {
        "file": "docs/プロジェクト再編/学習・実装・記録フロー自動化要件.md",
        "start": 695,    # "#### トリガー6: 理解度確認" 開始
        "end": 1094,     # セクション終了（次の---の直前）
        "lines": 400,    # 約400行
        "chars": "~8k",  # 全体49k charsの16%
        "title": "トリガー6: 理解度確認（Day都度オンデマンド生成）"
    }
}

# 使用例（必要時のみ読み込み）:
# config = TRIGGER_SECTION_MAP["trigger_6"]
# Read(config["file"], offset=config["start"], limit=config["end"]-config["start"])
# → 約8k chars読み込み（84%削減、パフォーマンス警告回避）
```

**コマンド例**:
```
理解度確認
```

---

## トリガー自動化率まとめ

| トリガー | ユーザー入力 | 自動処理 | 自動化率 |
|--------|------------|----------|---------|
| 学習開始 | 確認のみ | コンテキスト補完 | 95% |
| 実装開始 | 確認のみ | コンテキスト補完 | 95% |
| 学習記録 | 1項目入力 | YAML/MD更新 + 習熟度計算 | 90% |
| 実装記録 | なし | Git解析 + 品質ゲート + YAML/MD更新 | 100% |
| 週次振り返り | なし | 週次集計 + レポート生成 | 95% |

---

**従来の日次更新コマンド例**（トリガー使用前）:
- 学習のみ: `「学習記録: 8h、Docker基礎とMulti-stage builds習得、課題: volume設定エラー」`
- 実装のみ: `「実装記録: 6h、Docker 4-stage実装完了、カバレッジ45%達成」`
- 両方: `「今日の記録: 学習4h（CI/CD基礎）、実装4h（GitHub Actions workflow作成）、CI/CD成熟度35%達成」`

### 🤖 AI協働学習フロー仕組み

**詳細**: @memory:ai_collaboration_workflow

**概要**: 新技術習得のための3フェーズ学習方法論
- **Phase 1**: AI説明・概念理解（目標理解度30%）
- **Phase 2**: AI協働実装（目標理解度60%）
- **Phase 3**: 理解度確認・記録（目標理解度80%+）

**関連**: 実装品質ゲート、AI協働12原則（原則1・2・4）との整合性、トリガー6との連携

### リンター・フォーマッター

**詳細**: @memory:coding_standards Section 9「自動検証コマンド」

**クイックリファレンス**:
```bash
# 基本チェック（開発時）
uv run ruff check --fix .      # スタイル + 自動修正
uv run ruff format .            # フォーマット適用
uv run mypy utils/ config/      # 型チェック

# セキュリティ（週次）
uv run bandit -r utils/ config/ # 脆弱性スキャン
uv run safety check             # 依存関係チェック
```

### pre-commit（軽量版）

**詳細**: @memory:coding_standards Section 9.4、@memory:implementation_quality_gates

**セットアップ**: `uv run pre-commit install` （初回のみ）

**戦略**: コミット時はruffのみ（3秒以内）、重いチェック（mypy, bandit, pytest）はCI/CDで実行

**理由**: 開発体験優先（個人開発最適化）。詳細なトレードオフ分析は@memory参照

## アーキテクチャ概要

**詳細**: @memory:project_file_structure

**概要**: コアモジュール構成と設計パターン
- **コアモジュール**: `utils/api_client.py`（896行）、`config/settings.py`（327行）
- **設計パターン**: エラーハンドリング階層、リトライロジック（4xx即失敗/5xxリトライ）、非同期処理（async/await）
- **テスト構成**: pytest共通フィクスチャ（conftest.py）、4種類のテスト（unit/integration/performance/security）

**関連**: project_architecture.md（全体設計）、coding_standards.md（実装規約）

## 設定管理

### 環境変数設定（`.env`）


Pydantic Settingsのネスト記法（`__`区切り）を使用:

```bash
# 環境設定
ENVIRONMENT=development      # development|testing|staging|production
DEBUG=true

# API設定
API__BASE_URL=https://jsonplaceholder.typicode.com
API__TIMEOUT=30
API__RETRY_COUNT=3
API__RETRY_DELAY=1.0
API__MAX_CONNECTIONS=10

# ログ設定
LOG__LEVEL=DEBUG            # DEBUG|INFO|WARNING|ERROR|CRITICAL
LOG__FORMAT=console         # console|json
LOG__FILE=/var/log/app/api-test.log

# テスト設定
TEST__EXTERNAL_API_ENABLED=true
TEST__PERFORMANCE_TEST_ENABLED=false

# セキュリティ設定
SECURITY__API_KEY=your-secret-key
SECURITY__RATE_LIMIT_REQUESTS=100
```

### 設定アクセス方法

```python
from config.settings import settings

# API設定
base_url = settings.api.base_url
timeout = settings.api.timeout

# 環境判定
if settings.is_development():
    # 開発環境固有の処理
    pass
```

## 重要な学習ポイント
**CLAUDE.md 保持 654-676**

### 1. 非同期プログラミング
- `async/await`パターンの実装（`utils/api_client.py:399-762`）
- `asyncio.gather()`による並行処理（`api_client.py:741-761`）
- 非同期コンテキストマネージャー（`__aenter__/__aexit__`）

### 2. エラーハンドリング戦略
- 階層的な例外設計（`api_client.py:24-57`）
- HTTPステータスコード別処理（4xx即失敗、5xxリトライ）
- リトライロジック実装（`api_client.py:132-219`）

### 3. テスト設計パターン
- pytest fixtureスコープの使い分け（session/module/function）
- ファクトリーパターンによるテストデータ生成（`conftest.py:172-238`）
- モック・スタブの活用（`conftest.py:123-164`）
- パフォーマンステスト（`conftest.py:246-274`）

### 4. 設定管理ベストプラクティス
- Pydantic Settingsによる型安全な設定（`config/settings.py`）
- 環境変数の自動読み込み・バリデーション
- `SecretStr`によるシークレット保護（`settings.py:142-155`）

## 開発時の注意事項

**基本規約**: @memory:coding_standards, @memory:implementation_quality_gates

**Git運用** (GitHub Flow):
- `feature/[機能名]`ブランチで開発 → PR作成 → Squash Merge → main統合
- コミットメッセージ: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`

**品質基準**:
- カバレッジ目標: Week 7-10でPhase別に設定（最終目標85%）

## トラブルシューティング

**このセクションの範囲**: 高頻度で参照する基本コマンドのみ
**詳細な原因分析・解決策**: @memory:test_strategy Section 8.4 トラブルシューティングFAQ参照

### テスト失敗時
```bash
# 詳細ログ出力
uv run pytest -vv --tb=long

# 最初の失敗で停止
uv run pytest -x

# 特定テストのみデバッグ実行
uv run pytest tests/unit/test_async_client.py::test_name -vv --log-cli-level=DEBUG
```

### カバレッジ不足時
```bash
# カバレッジレポート確認
uv run pytest --cov-report=term-missing

# HTMLレポート生成
uv run pytest --cov-report=html
open reports/htmlcov/index.html
```

### 型チェックエラー時
```bash
# mypy詳細出力
uv run mypy --show-error-codes --pretty utils/ config/
```

