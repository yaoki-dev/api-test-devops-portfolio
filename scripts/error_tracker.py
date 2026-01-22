#!/usr/bin/env python3
"""Error Tracker Module - Trigger 7 エラー記録
============================================

Obsidian導入計画_v2で定義されたTrigger 7「エラー記録」の実装。
3回以上参照したエラーはKB (Knowledge Base) 昇格検討対象。

使用例:
    エラー記録: volume_mount
    エラー: pytest_fixture, pytest fixture scope不一致

機能:
    - error_id正規化（snake_case、小文字変換）
    - YAML Injection対策（description検証）
    - progress_state.yaml更新（error_occurrences）
    - daily_progress.md更新（★マーク表示）

スキーマバージョン: 2.1.0
最終更新: 2025-12-05
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

# =============================================================================
# Task 1: error_id正規化関数
# =============================================================================


def normalize_error_id(error_id: str) -> str:
    """error_idをsnake_case小文字に正規化。

    Args:
        error_id: 入力されたエラーID

    Returns:
        正規化されたerror_id（小文字、前後空白除去）

    Raises:
        ValueError: error_idが空、または無効な形式の場合

    Examples:
        >>> normalize_error_id("Volume_Mount")
        'volume_mount'
        >>> normalize_error_id("PYTEST_FIXTURE")
        'pytest_fixture'
        >>> normalize_error_id("  docker_error  ")
        'docker_error'
        >>> normalize_error_id("")
        Traceback (most recent call last):
        ...
        ValueError: error_id cannot be empty

    """
    # 前後の空白を除去
    normalized = error_id.strip()

    # 空文字チェック
    if not normalized:
        raise ValueError("error_id cannot be empty")

    # 小文字変換
    normalized = normalized.lower()

    # snake_case検証（英小文字、数字、アンダースコアのみ許可）
    if not re.match(r"^[a-z][a-z0-9_]*$", normalized):
        raise ValueError(
            f"error_id must be snake_case (lowercase, numbers, underscores): {error_id}",
        )

    # 長さ検証（1-64文字）
    if len(normalized) > 64:
        raise ValueError(f"error_id must be 1-64 characters, got {len(normalized)}")

    return normalized


# =============================================================================
# Task 2: YAML Injection対策
# =============================================================================

# 危険なYAMLパターン（YAML Injection防止）
YAML_INJECTION_PATTERNS = [
    r"^[\s]*[!%&*]",  # YAMLタグ、アンカー、エイリアス
    r"[\x00-\x08\x0b\x0c\x0e-\x1f]",  # 制御文字（P0-SEC-1強化）
    r"{{.*}}",  # テンプレート構文
    r"\$\{.*\}",  # 変数展開
    r"^[\s]*[|>]",  # P0-SEC-1: マルチライン文字列ブロック
    r"[\x7f-\x9f]",  # P0-SEC-1: 追加制御文字（DEL, C1制御文字）
]

# P0-SEC-1: YAML予約語（大文字小文字不問でYAMLパーサーが特殊解釈）
YAML_RESERVED_WORDS = frozenset(
    {
        # Boolean値
        "true",
        "false",
        "yes",
        "no",
        "on",
        "off",
        # Null値
        "null",
        "~",
        # 特殊値
        ".inf",
        "-.inf",
        ".nan",
    },
)

# 機密情報パターン（マスク対象）
# 注意: より具体的なパターンを先に配置（優先順位順）
SENSITIVE_PATTERNS = [
    # P1-4追加: 具体的なトークン形式（先にマッチさせる）
    # P1-SEC-2: fine-grained PAT対応（長さ制限緩和: 36文字固定 → 1文字以上）
    (r"ghp_[A-Za-z0-9]+", "[GITHUB_PAT_MASKED]"),
    (r"gho_[A-Za-z0-9]+", "[GITHUB_OAUTH_MASKED]"),  # P0-SEC-2: OAuth token
    (r"ghu_[A-Za-z0-9]+", "[GITHUB_USER_MASKED]"),  # P0-SEC-2: User token
    (r"ghs_[A-Za-z0-9]+", "[GITHUB_SERVER_MASKED]"),  # P0-SEC-2: Server token
    (r"ghr_[A-Za-z0-9]+", "[GITHUB_REFRESH_MASKED]"),  # P0-SEC-2: Refresh token
    (r"AKIA[A-Z0-9]{16}", "[AWS_KEY_MASKED]"),
    (r"://[^:]+:[^@]+@", "://[CREDENTIALS_MASKED]@"),
    # JWT（3部構成のBase64）
    (r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[JWT_MASKED]"),
    (r"-----BEGIN [A-Z ]+ KEY-----", "[PRIVATE_KEY_MASKED]"),
    # P0-SEC-2: Azure/GCP/Slack追加パターン
    (r"xox[baprs]-[A-Za-z0-9-]+", "[SLACK_TOKEN_MASKED]"),  # Slack Bot/App token
    (r"sk-[A-Za-z0-9]{20,}", "[OPENAI_KEY_MASKED]"),  # OpenAI API Key
    (r"sk-ant-[A-Za-z0-9-]+", "[ANTHROPIC_KEY_MASKED]"),  # Anthropic API Key
    # P0-SEC-2: 長いBase64文字列（40文字以上、末尾=パディング含む）
    (r"[A-Za-z0-9+/]{40,}={0,2}", "[BASE64_MASKED]"),
    # 汎用キーワードパターン（最後にマッチ）
    (r"(?i)api[_-]?key\s*[:=]\s*['\"]?[\w-]+", "[API_KEY_MASKED]"),
    (r"(?i)token\s*[:=]\s*['\"]?[\w.-]+", "[TOKEN_MASKED]"),
    (r"(?i)password\s*[:=]\s*['\"]?[^\s'\"]+", "[PASSWORD_MASKED]"),
    (r"(?i)secret\s*[:=]\s*['\"]?[\w-]+", "[SECRET_MASKED]"),
]


def validate_description(description: str) -> str:
    """descriptionのYAML Injection対策と機密情報マスク。

    Args:
        description: 入力された説明文

    Returns:
        サニタイズ済みのdescription

    Raises:
        ValueError: YAML Injectionパターンを検出した場合

    Examples:
        >>> validate_description("Docker volume設定エラー")
        'Docker volume設定エラー'
        >>> validate_description("api_key: secret123")
        '[API_KEY_MASKED]'
        >>> validate_description("true")  # P0-SEC-1: 予約語拒否
        Traceback (most recent call last):
        ...
        ValueError: YAML reserved word detected in description

    """
    if not description:
        return "説明未設定"

    # 長さ制限（256文字）
    if len(description) > 256:
        description = description[:256] + "..."

    # P0-SEC-1: YAML予約語チェック（description全体が予約語の場合を拒否）
    if description.strip().lower() in YAML_RESERVED_WORDS:
        raise ValueError("YAML reserved word detected in description")

    # YAML Injectionパターンチェック
    for pattern in YAML_INJECTION_PATTERNS:
        if re.search(pattern, description):
            # P1-SEC-1: 入力値を含めない汎用メッセージ（情報漏洩防止）
            raise ValueError("Invalid characters detected in description")

    # 機密情報マスク
    sanitized = description
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized)

    return sanitized


# =============================================================================
# Task 3: progress_state.yaml更新ロジック
# =============================================================================


@dataclass
class ErrorOccurrence:
    """エラー発生記録のデータクラス"""

    description: str
    count: int = 1
    first_seen: str = field(default_factory=lambda: date.today().isoformat())
    last_seen: str = field(default_factory=lambda: date.today().isoformat())
    occurrences: list[str] = field(default_factory=list)
    kb_promoted: bool = False

    def to_dict(self) -> dict[str, Any]:
        """YAML出力用の辞書形式に変換"""
        return {
            "description": self.description,
            "count": self.count,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "occurrences": self.occurrences,
            "kb_promoted": self.kb_promoted,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ErrorOccurrence:
        """辞書からErrorOccurrenceを生成"""
        return cls(
            description=data.get("description", "説明未設定"),
            count=data.get("count", 1),
            first_seen=data.get("first_seen", date.today().isoformat()),
            last_seen=data.get("last_seen", date.today().isoformat()),
            occurrences=data.get("occurrences", []),
            kb_promoted=data.get("kb_promoted", False),
        )


class ProgressStateManager:
    """progress_state.yaml管理クラス"""

    def __init__(self, file_path: str | Path = "progress_state.yaml"):
        self.file_path = Path(file_path)
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """YAMLファイルを読み込み"""
        if self.file_path.exists():
            with self.file_path.open(encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}
        else:
            self._data = self._create_default_structure()

    def _create_default_structure(self) -> dict[str, Any]:
        """デフォルトのprogress_state構造を作成"""
        return {
            "current_week": 1,
            "current_day": 1,
            "current_phase": "学習期間",
            "error_occurrences": {},
            "learning_history": [],
            "implementation_history": [],
            "metadata": {
                "created_at": date.today().isoformat(),
                "last_updated": date.today().isoformat(),
                "schema_version": "2.1.0",
            },
        }

    def save(self) -> None:
        """YAMLファイルに保存"""
        # メタデータ更新
        if "metadata" in self._data:
            self._data["metadata"]["last_updated"] = date.today().isoformat()

        with self.file_path.open("w", encoding="utf-8") as f:
            yaml.dump(
                self._data,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )

    def record_error(self, error_id: str, description: str) -> tuple[int, bool]:
        """エラーを記録し、カウントを更新。

        Args:
            error_id: 正規化済みのerror_id
            description: サニタイズ済みの説明

        Returns:
            (count, kb_promotion_suggested): カウントとKB昇格推奨フラグ

        """
        today = date.today().isoformat()

        # error_occurrencesの初期化
        if "error_occurrences" not in self._data:
            self._data["error_occurrences"] = {}

        error_data = self._data["error_occurrences"].get(error_id)

        if error_data is None:
            # 新規エラー
            occurrence = ErrorOccurrence(
                description=description,
                count=1,
                first_seen=today,
                last_seen=today,
                occurrences=[today],
                kb_promoted=False,
            )
            self._data["error_occurrences"][error_id] = occurrence.to_dict()
            return (1, False)

        # 既存エラーの更新
        occurrence = ErrorOccurrence.from_dict(error_data)

        # count増加（kb_promoted後も継続）
        occurrence.count += 1
        occurrence.last_seen = today

        # 同日重複チェック（1日1エントリ）
        if today not in occurrence.occurrences:
            occurrence.occurrences.append(today)

        # P1-IMPL-1: descriptionマージ（仕様: 既存 + " | [{date}] " + 新規）
        if description != "説明未設定" and description not in occurrence.description:
            merged = f"{occurrence.description} | [{today}] {description}"
            # 256文字制限（古い情報を優先的に保持）
            if len(merged) > 256:
                merged = merged[:253] + "..."
            occurrence.description = merged

        self._data["error_occurrences"][error_id] = occurrence.to_dict()

        # KB昇格推奨判定（count >= 3 かつ未昇格）
        kb_suggested = occurrence.count >= 3 and not occurrence.kb_promoted

        return (occurrence.count, kb_suggested)

    def get_error(self, error_id: str) -> ErrorOccurrence | None:
        """指定されたerror_idのエラー情報を取得"""
        error_data = self._data.get("error_occurrences", {}).get(error_id)
        if error_data:
            return ErrorOccurrence.from_dict(error_data)
        return None


# =============================================================================
# Task 4: daily_progress.md更新ロジック
# =============================================================================


class DailyProgressManager:
    """daily_progress.md管理クラス"""

    def __init__(self, file_path: str | Path = "daily_progress.md"):
        self.file_path = Path(file_path)
        self._content: str = ""
        self._load()

    def _load(self) -> None:
        """ファイルを読み込み"""
        if self.file_path.exists():
            with self.file_path.open(encoding="utf-8") as f:
                self._content = f.read()
        else:
            self._content = self._create_default_template()

    def _create_default_template(self) -> str:
        """デフォルトテンプレートを作成"""
        today = datetime.now().strftime("%Y-%m-%d")
        return f"""# Daily Progress
*最終更新: {today}*

## 今日の学習

## 今日の実装

## エラー参照履歴

## メモ
"""

    def save(self) -> None:
        """ファイルに保存"""
        # 最終更新日を更新
        today = datetime.now().strftime("%Y-%m-%d")
        self._content = re.sub(
            r"\*最終更新: \d{4}-\d{2}-\d{2}\*",
            f"*最終更新: {today}*",
            self._content,
        )

        with self.file_path.open("w", encoding="utf-8") as f:
            f.write(self._content)

    def append_error_entry(
        self,
        error_id: str,
        description: str,
        count: int,
        kb_suggested: bool,
    ) -> None:
        """エラー参照履歴セクションにエントリを追記。

        Args:
            error_id: エラーID
            description: 説明
            count: 発生回数
            kb_suggested: KB昇格推奨フラグ

        """
        # ★マーク生成（count数に応じて★/★★/★★★）
        stars = "★" * min(count, 3)

        # KB昇格検討メッセージ
        kb_note = " → KB昇格検討" if kb_suggested else ""

        # P1-IMPL-2: 初回descriptionのみ表示（仕様: description.split(' | ')[0]）
        display_desc = description.split(" | ")[0] if " | " in description else description

        # エントリ生成
        entry = f"- {stars} [{error_id}] {display_desc}{kb_note}\n"

        # エラー参照履歴セクションを探して追記
        section_header = "## エラー参照履歴"
        if section_header in self._content:
            # セクションヘッダーの直後に追記
            # 次のセクション（## で始まる行）または文末まで
            pattern = rf"({re.escape(section_header)}\n)(.*?)(?=\n## |\Z)"
            match = re.search(pattern, self._content, re.DOTALL)

            if match:
                section_start = match.group(1)
                section_content = match.group(2)

                # 既存エントリに同じerror_idがあれば更新、なければ追記
                error_pattern = rf"- ★+ \[{re.escape(error_id)}\].*\n"
                if re.search(error_pattern, section_content):
                    # 既存エントリを更新
                    new_content = re.sub(error_pattern, entry, section_content)
                else:
                    # 末尾に追記
                    new_content = section_content.rstrip() + "\n" + entry

                self._content = self._content.replace(
                    section_start + section_content,
                    section_start + new_content,
                )
        else:
            # セクションがなければ追加
            self._content = self._content.rstrip() + f"\n\n{section_header}\n{entry}"


# =============================================================================
# メインエントリポイント
# =============================================================================


def record_error(
    error_id: str,
    description: str = "",
    progress_file: str | Path = "progress_state.yaml",
    daily_file: str | Path = "daily_progress.md",
) -> dict[str, Any]:
    """エラーを記録する統合関数。

    Args:
        error_id: エラーID（正規化前でも可）
        description: エラー説明（任意）
        progress_file: progress_state.yamlのパス
        daily_file: daily_progress.mdのパス

    Returns:
        記録結果の辞書

    Examples:
        >>> result = record_error("volume_mount", "Docker volume設定エラー")
        >>> result["success"]
        True

    """
    try:
        # Task 1: error_id正規化
        normalized_id = normalize_error_id(error_id)

        # Task 2: description検証
        safe_description = validate_description(description) if description else "説明未設定"

        # Task 3: progress_state.yaml更新
        progress_manager = ProgressStateManager(progress_file)
        count, kb_suggested = progress_manager.record_error(normalized_id, safe_description)
        progress_manager.save()

        # Task 4: daily_progress.md更新
        daily_manager = DailyProgressManager(daily_file)
        daily_manager.append_error_entry(normalized_id, safe_description, count, kb_suggested)
        daily_manager.save()

        return {
            "success": True,
            "error_id": normalized_id,
            "description": safe_description,
            "count": count,
            "kb_suggested": kb_suggested,
            "message": f"✅ エラー記録完了: [{normalized_id}] (count: {count})"
            + (" → KB昇格検討" if kb_suggested else ""),
        }

    except ValueError as e:
        return {
            "success": False,
            "error_id": error_id,
            "error": str(e),
            "message": f"❌ エラー記録失敗: {e}",
        }
    except Exception as e:
        return {
            "success": False,
            "error_id": error_id,
            "error": str(e),
            "message": f"❌ 予期しないエラー: {e}",
        }


def main() -> None:
    """CLI エントリポイント"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python error_tracker.py <error_id> [description]")
        print("Example: python error_tracker.py volume_mount 'Docker volume設定エラー'")
        sys.exit(1)

    error_id = sys.argv[1]
    description = sys.argv[2] if len(sys.argv) > 2 else ""

    result = record_error(error_id, description)
    print(result["message"])
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
