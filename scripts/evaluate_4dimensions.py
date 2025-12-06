#!/usr/bin/env python3
"""
4次元評価スクリプト

Task要件を4次元評価基準で自動スコアリングし、改善推奨事項を生成します。

Usage:
    python scripts/evaluate_4dimensions.py <task_text>
    python scripts/evaluate_4dimensions.py --file <task_file.md>
"""

import re
import sys
from pathlib import Path
from typing import Any


def evaluate_dimension_1(task_text: str) -> int:
    """
    Dimension 1: AI実装成功率（25点満点）

    判定ロジック:
    - 正規表現パターンマッチング
    - キーワード検出による配点計算
    """
    score = 0

    # 明確性（8点）
    # ファイルパス明示（3点）
    if re.search(r"\[(utils|config|tests)/[\w/]+\.py\]", task_text):
        score += 3

    # 具体的成果物明示（3点）
    # クラス名（PascalCase）、関数/メソッド名（snake_case）、変数名の検出
    code_entities = re.findall(r"(class [A-Z]\w+|def [a-z_]\w+|[a-z_]\w+\s*[:=])", task_text)
    if len(code_entities) >= 3:
        score += 3
    elif len(code_entities) >= 1:
        score += min(len(code_entities), 3)

    # 曖昧動詞排除（2点）
    vague_words = ["適切に", "うまく", "よく", "ちゃんと", "正しく"]
    has_vague = any(word in task_text for word in vague_words)
    if not has_vague:
        score += 2

    # 完全性（9点）
    # 統合要件明示（5点）
    integration_keywords = [
        "Pydantic",
        "エラーハンドリング",
        "例外処理",
        "ログ",
        "logging",
        "structlog",
        "バリデーション",
    ]
    integration_count = sum(1 for kw in integration_keywords if kw in task_text)
    if integration_count >= 2:
        score += 5
    elif integration_count == 1:
        score += 3

    # 依存関係明示（4点）
    dependency_keywords = [
        "ベースクラス",
        "継承",
        "モジュール",
        "パッケージ",
        "import",
        "from",
        "BaseSettings",
        "BaseModel",
    ]
    dependency_count = sum(1 for kw in dependency_keywords if kw in task_text)
    if dependency_count >= 2:
        score += 4
    elif dependency_count == 1:
        score += 2

    # 実行可能性（8点）
    # 技術スタック明示（4点）
    tech_stack = [
        "httpx",
        "AsyncClient",
        "Pydantic",
        "pytest",
        "structlog",
        "BaseSettings",
        "Field",
        "SecretStr",
    ]
    tech_count = sum(1 for tech in tech_stack if tech in task_text)
    score += min(4, tech_count)

    # デザインパターン明示（4点）
    patterns = [
        "Context Manager",
        "Factory",
        "Singleton",
        "Strategy",
        "async with",
        "__aenter__",
        "__aexit__",
        "__enter__",
        "__exit__",
        "field_validator",
        "@validator",
    ]
    pattern_count = sum(1 for pat in patterns if pat in task_text)
    score += min(4, pattern_count * 2)

    return min(25, score)


def evaluate_dimension_2(task_text: str) -> int:
    """
    Dimension 2: テスト可能性（30点満点）

    判定ロジック:
    - 定量的成功基準: テスト件数・カバレッジ目標の明示検出
    - 検証シナリオ: 正常系・異常系・境界値テストケースの明示検出
    - 期待動作: 戻り値型・副作用の明示検出
    """
    score = 0

    # 定量的成功基準（12点）
    # テスト件数明示（6点）
    test_count_patterns = [
        r"(\d+)件.*テスト",
        r"(\d+)\s*tests?",
        r"テスト.*(\d+)\s*件",
        r"(\d+)\s*個.*テスト",
        r"テスト.*追加.*(\d+)",
        r"(\d+).*テスト.*追加",
    ]
    for pattern in test_count_patterns:
        if re.search(pattern, task_text):
            score += 6
            break

    # カバレッジ目標明示（6点）
    # パーセント値の検出（カバレッジ目標、Week別目標等）
    coverage_targets = re.findall(r"(\d+\.?\d*)%", task_text)
    if coverage_targets:
        score += 6

    # 検証シナリオ（12点）
    # 正常系テストケース（4点）
    success_patterns = [
        "正常系",
        "成功パターン",
        "success case",
        "test_success",
        "test_valid",
        "test_default",
    ]
    if any(pat in task_text for pat in success_patterns):
        score += 4

    # 異常系テストケース（4点）
    error_patterns = [
        "HTTPStatusError",
        "TimeoutError",
        "ConnectionError",
        "異常系",
        "エラーケース",
        "error case",
        "test_error",
        "test_failure",
        "test_invalid",
        "ValidationError",
        "ValueError",
    ]
    if any(pat in task_text for pat in error_patterns):
        score += 4

    # 境界値テストケース（4点）
    boundary_patterns = [
        "境界値",
        "エッジケース",
        "edge case",
        "boundary",
        "空文字列",
        "None",
        "最大値",
        "最小値",
        "test_empty",
        "test_none",
        "test_max",
        "test_min",
    ]
    if any(pat in task_text for pat in boundary_patterns):
        score += 4

    # 期待動作（6点）
    # 戻り値の型明示（3点）
    return_type_patterns = [
        r"-> \w+",  # -> User, -> List等
        r"戻り値.*型",
        r"return type",
        r": \w+ =",  # Pydantic Field型ヒント
        "Settings",
        "APIConfig",
        "LogConfig",
    ]
    if any(re.search(pat, task_text) for pat in return_type_patterns):
        score += 3

    # 副作用明示（3点）
    side_effect_patterns = [
        "aclose",
        "close",
        "cleanup",
        "リソースクリーンアップ",
        "副作用",
        "side effect",
        "__aexit__",
        "__exit__",
        "環境変数",
        "設定読み込み",
        "env",
    ]
    if any(pat in task_text for pat in side_effect_patterns):
        score += 3

    return min(30, score)


def evaluate_dimension_3(task_text: str) -> int:  # noqa: C901 - スコアリングロジック集約（複数の品質指標評価）のため許容
    """
    Dimension 3: 品質ゲート整合性（25点満点）

    判定ロジック:
    - 数値検出（カバレッジ目標、テスト件数）
    - 行長制限チェック（コードブロック内）
    """
    score = 0

    # Gate 1準拠（pytest + カバレッジ）（10点）
    # カバレッジ目標明示（5点）
    coverage_values = re.findall(r"(\d+\.?\d*)%", task_text)
    if len(coverage_values) >= 1:
        score += 5

    # テスト件数明示（5点）
    test_count_patterns = [r"(\d+)件.*テスト", r"(\d+)\s*tests?", r"テスト.*(\d+)\s*件"]
    test_counts = []
    for pattern in test_count_patterns:
        matches = re.findall(pattern, task_text)
        test_counts.extend([int(m) if isinstance(m, str) and m.isdigit() else 0 for m in matches])

    if test_counts:
        max_count = max(test_counts)
        if max_count >= 5:
            score += 5
        else:
            score += max_count

    # Gate 2準拠（ruff）（5点）
    # 命名規則明示（2点）
    naming_conventions = ["PascalCase", "snake_case", "UPPER_CASE"]
    naming_count = sum(1 for conv in naming_conventions if conv in task_text)
    score += min(2, naming_count)

    # 行長制限準拠（3点）
    # コード例（```で囲まれた部分）の全行が100文字以内かチェック
    code_blocks = re.findall(r"```(?:python)?\n(.*?)```", task_text, re.DOTALL)
    if code_blocks:
        all_lines_valid = True
        for block in code_blocks:
            lines = block.split("\n")
            if any(len(line) > 100 for line in lines):
                all_lines_valid = False
                break
        if all_lines_valid:
            score += 3
    else:
        score += 3

    # Gate 3準拠（mypy）（5点）
    # 型ヒント明示: -> ReturnType, : ArgType
    type_hints = re.findall(r"(-> [\w\[\], ]+|: [\w\[\], ]+ =)", task_text)
    type_hint_count = len(type_hints)
    if type_hint_count >= 5:
        score += 5
    elif type_hint_count >= 3:
        score += 3
    elif type_hint_count >= 1:
        score += 2

    # Gate 4準拠（git commit）（5点）
    # コミットメッセージ形式・タスク原子性
    commit_keywords = ["feat:", "fix:", "test:", "refactor:", "docs:", "commit"]
    atomic_keywords = ["1Task", "原子的", "atomic", "3h以内"]
    commit_count = sum(1 for kw in commit_keywords + atomic_keywords if kw in task_text)
    score += min(5, commit_count * 2)

    return min(25, score)


def evaluate_dimension_4(task_text: str) -> int:  # noqa: C901 - スコアリングロジック集約（複数のセキュリティ指標評価）のため許容
    """
    Dimension 4: セキュリティ・標準準拠（20点満点）

    判定ロジック:
    - Pydantic型制約検出（constr, conint）
    - SecretStr検出
    - エラーハンドリングパターン検出
    - 認証ヘッダー検出
    """
    score = 0

    # Input Validation（Pydantic）（5点）
    # 型制約明示（3点）
    type_constraints = [
        "Field",
        "constr",
        "conint",
        "confloat",
        "conlist",
        "max_length=",
        "min_length=",
        "ge=",
        "le=",
        "gt=",
        "lt=",
    ]
    constraint_count = sum(1 for cons in type_constraints if cons in task_text)
    if constraint_count >= 3:
        score += 3
    elif constraint_count >= 1:
        score += constraint_count

    # バリデーションメソッド要求（2点）
    validators = ["@field_validator", "@model_validator", "@validator", "field_validator"]
    if any(val in task_text for val in validators):
        score += 2

    # シークレット管理（5点）
    # SecretStr使用要求（3点）
    if "SecretStr" in task_text:
        score += 3

    # 環境変数取得明示（2点）
    env_patterns = [
        r"SECURITY__\w+",
        r"API__\w+",
        r"LOG__\w+",
        r"\.env",
        "os.getenv",
        r"settings\.\w+",
        "環境変数",
    ]
    env_count = sum(1 for pat in env_patterns if re.search(pat, task_text))
    score += min(2, env_count)

    # エラーハンドリング（5点）
    # 階層的例外設計要求（3点）
    error_hierarchy_keywords = [
        "APIClientError",
        "APIHTTPError",
        "APITimeoutError",
        "Exception",
        "Error",
        "raise",
        "try",
        "except",
    ]
    error_count = sum(1 for kw in error_hierarchy_keywords if kw in task_text)
    if error_count >= 3:
        score += 3
    elif error_count >= 1:
        score += error_count

    # 4xx/5xx分離要求（2点）
    status_handling = ["4xx", "5xx", "リトライ", "retry", "即座に失敗", "immediate"]
    if sum(1 for kw in status_handling if kw in task_text) >= 2:
        score += 2

    # 認証・Rate Limiting（5点）
    # 認証ヘッダー要求（3点）
    auth_headers = ["Authorization", "API-Key", "X-API-Key", "Bearer", "secret_key", "api_key"]
    auth_count = sum(1 for header in auth_headers if header in task_text)
    if auth_count >= 2:
        score += 3
    elif auth_count >= 1:
        score += 2

    # Rate Limiting考慮（2点）
    rate_limit_keywords = [
        "Rate Limiting",
        "リトライ回数",
        "retry_count",
        "リトライ間隔",
        "retry_delay",
        "backoff",
        "timeout",
    ]
    rate_limit_count = sum(1 for kw in rate_limit_keywords if kw in task_text)
    if rate_limit_count >= 2:
        score += 2
    elif rate_limit_count >= 1:
        score += 1

    return min(20, score)


def generate_recommendations(scores: dict[str, int], passing_scores: dict[str, int]) -> list[str]:
    """
    推奨事項生成

    生成ロジック:
    1. 不合格Dimensionのみ対象（score < passing_score）
    2. スコア差の大きい順にソート
    3. 最大3件まで出力
    4. フォーマット: "Dimension X: [不足内容]（現状: Y点/満点Z点）"
    """
    recommendations = []

    # Dimension別の満点
    max_scores = {"dimension_1": 25, "dimension_2": 30, "dimension_3": 25, "dimension_4": 20}

    # 不合格Dimensionを抽出し、スコア差でソート
    failed_dimensions = [
        (dim, passing_scores[dim] - scores[dim], max_scores[dim])
        for dim in scores
        if scores[dim] < passing_scores[dim]
    ]
    failed_dimensions.sort(key=lambda x: x[1], reverse=True)

    # Dimension別の具体的改善提案
    improvement_suggestions = {
        "dimension_1": [
            "ファイルパス明示（[utils/config/tests]/*.py形式で明記）",
            "具体的成果物明示（クラス名・メソッド名3個以上）",
            "曖昧動詞排除（'適切に'等の削除）",
            "技術スタック明示（httpx, Pydantic等4種類以上）",
            "デザインパターン明示（2種類以上）",
        ],
        "dimension_2": [
            "テスト件数明示（'X件のテスト追加'形式で明記）",
            "カバレッジ目標明示（数値％目標を明記）",
            "異常系テストケース追加（エラーケース・ValidationError等）",
            "境界値テストケース追加（None, 空文字列, 最大値等）",
        ],
        "dimension_3": [
            "カバレッジ目標明示（数値％で明記）",
            "テスト件数明示（5件以上）",
            "型ヒント明示（5個以上の型ヒント例示）",
            "行長制限準拠（コード例全行≤100文字）",
        ],
        "dimension_4": [
            "Pydantic型制約明示（Field, ge=, le=等3種類以上）",
            "SecretStr使用明示（シークレット保護要求）",
            "環境変数取得明示（.env, 環境変数名等）",
            "エラーハンドリング要求（階層的例外設計）",
        ],
    }

    # 最大3件の推奨事項を生成
    for dim, gap, max_score in failed_dimensions[:3]:
        dim_num = dim.split("_")[1]
        current_score = scores[dim]

        suggestions = improvement_suggestions.get(dim, ["改善必要"])

        # スコア差に応じた提案選択
        if gap >= 10:
            # 大幅不足: 複数項目の改善が必要
            suggestion = (
                f"{suggestions[0]}、{suggestions[1] if len(suggestions) > 1 else suggestions[0]}"
            )
        elif gap >= 5:
            # 中程度不足: 主要項目の改善が必要
            suggestion = suggestions[0]
        else:
            # 軽微不足: 最も優先度の高い項目のみ
            suggestion = suggestions[0]

        recommendations.append(
            f"Dimension {dim_num}: {suggestion}が必要"
            f"（現状: {current_score}点/満点{max_score}点、不足: {gap}点）"
        )

    return recommendations


def evaluate_task(task_text: str) -> dict[str, Any]:
    """4次元評価スコアリング"""
    scores = {
        "dimension_1": evaluate_dimension_1(task_text),
        "dimension_2": evaluate_dimension_2(task_text),
        "dimension_3": evaluate_dimension_3(task_text),
        "dimension_4": evaluate_dimension_4(task_text),
    }

    # 合格判定（各Dimension ≥ 配点の80%）
    passing_scores = {
        "dimension_1": 20,  # 25点 × 80% = 20点
        "dimension_2": 24,  # 30点 × 80% = 24点
        "dimension_3": 20,  # 25点 × 80% = 20点
        "dimension_4": 16,  # 20点 × 80% = 16点
    }

    passed = all(scores[dim] >= passing_scores[dim] for dim in scores)

    return {
        "scores": scores,
        "overall": {
            "passed": passed,
            "total": sum(scores.values()),
            "reason": _get_fail_reason(scores, passing_scores) if not passed else "全Dimension合格",
        },
        "recommendations": generate_recommendations(scores, passing_scores),
    }


def _get_fail_reason(scores: dict[str, int], passing_scores: dict[str, int]) -> str:
    """不合格理由を生成"""
    failed_dims = [
        f"Dimension {dim.split('_')[1]}: {scores[dim]}点 < {passing_scores[dim]}点"
        for dim in scores
        if scores[dim] < passing_scores[dim]
    ]
    return "、".join(failed_dims)


def main():
    """メイン処理"""
    if len(sys.argv) < 2:
        print("Usage: python scripts/evaluate_4dimensions.py <task_text>")
        print("   or: python scripts/evaluate_4dimensions.py --file <task_file.md>")
        sys.exit(1)

    if sys.argv[1] == "--file":
        if len(sys.argv) < 3:
            print("Error: --file requires a file path")
            sys.exit(1)
        file_path = Path(sys.argv[2])
        if not file_path.exists():
            print(f"Error: File not found: {file_path}")
            sys.exit(1)
        task_text = file_path.read_text(encoding="utf-8")
    else:
        task_text = sys.argv[1]

    result = evaluate_task(task_text)

    print("\n=== 4次元評価結果 ===")
    print(f"\nDimension 1（AI実装成功率）: {result['scores']['dimension_1']}/25点")
    print(f"Dimension 2（テスト可能性）: {result['scores']['dimension_2']}/30点")
    print(f"Dimension 3（品質ゲート整合性）: {result['scores']['dimension_3']}/25点")
    print(f"Dimension 4（セキュリティ・標準準拠）: {result['scores']['dimension_4']}/20点")
    print(f"\n総合スコア: {result['overall']['total']}/100点")
    print(f"合否: {'✅ 合格' if result['overall']['passed'] else '❌ 不合格'}")
    print(f"理由: {result['overall']['reason']}")

    if result["recommendations"]:
        print("\n=== 改善推奨事項 ===")
        for i, rec in enumerate(result["recommendations"], 1):
            print(f"{i}. {rec}")
    else:
        print("\n改善推奨事項なし（全Dimension合格）")


if __name__ == "__main__":
    main()
