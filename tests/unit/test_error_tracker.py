"""
Test Error Tracker Module - Trigger 7 エラー記録
=================================================

error_tracker.pyの単体テスト。
正規化、YAML Injection対策、progress_state.yaml/daily_progress.md更新をテスト。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.error_tracker import (
    DailyProgressManager,
    ErrorOccurrence,
    ProgressStateManager,
    normalize_error_id,
    record_error,
    validate_description,
)

# =============================================================================
# Task 1: error_id正規化テスト
# =============================================================================


class TestNormalizeErrorId:
    """error_id正規化関数のテスト"""

    def test_lowercase_conversion(self) -> None:
        """大文字を小文字に変換"""
        assert normalize_error_id("Volume_Mount") == "volume_mount"
        assert normalize_error_id("PYTEST_FIXTURE") == "pytest_fixture"
        assert normalize_error_id("DockerError") == "dockererror"

    def test_strip_whitespace(self) -> None:
        """前後の空白を除去"""
        assert normalize_error_id("  docker_error  ") == "docker_error"
        assert normalize_error_id("\tvolume_mount\n") == "volume_mount"

    def test_valid_snake_case(self) -> None:
        """有効なsnake_caseはそのまま"""
        assert normalize_error_id("volume_mount") == "volume_mount"
        assert normalize_error_id("error_123") == "error_123"
        assert normalize_error_id("a") == "a"

    def test_empty_error_id_raises(self) -> None:
        """空のerror_idはValueError"""
        with pytest.raises(ValueError, match="cannot be empty"):
            normalize_error_id("")
        with pytest.raises(ValueError, match="cannot be empty"):
            normalize_error_id("   ")

    def test_invalid_format_raises(self) -> None:
        """無効な形式はValueError"""
        with pytest.raises(ValueError, match="must be snake_case"):
            normalize_error_id("123_error")  # 数字始まり
        with pytest.raises(ValueError, match="must be snake_case"):
            normalize_error_id("error-name")  # ハイフン
        with pytest.raises(ValueError, match="must be snake_case"):
            normalize_error_id("error name")  # スペース

    def test_max_length(self) -> None:
        """64文字制限"""
        long_id = "a" * 64
        assert normalize_error_id(long_id) == long_id

        too_long = "a" * 65
        with pytest.raises(ValueError, match="must be 1-64 characters"):
            normalize_error_id(too_long)


# =============================================================================
# Task 2: YAML Injection対策テスト
# =============================================================================


class TestValidateDescription:
    """description検証関数のテスト"""

    def test_valid_description(self) -> None:
        """有効なdescriptionはそのまま"""
        assert validate_description("Docker volume設定エラー") == "Docker volume設定エラー"
        assert validate_description("pytest fixture scope不一致") == "pytest fixture scope不一致"

    def test_empty_description_default(self) -> None:
        """空のdescriptionはデフォルト値"""
        assert validate_description("") == "説明未設定"
        assert validate_description(None) == "説明未設定"  # type: ignore[arg-type]

    def test_length_truncation(self) -> None:
        """256文字超は切り詰め"""
        long_desc = "a" * 300
        result = validate_description(long_desc)
        assert len(result) == 259  # 256 + "..."
        assert result.endswith("...")

    def test_yaml_injection_blocked(self) -> None:
        """YAMLインジェクションパターンをブロック"""
        with pytest.raises(ValueError, match="Invalid characters"):
            validate_description("!ruby/object:Gem::Specification")
        with pytest.raises(ValueError, match="Invalid characters"):
            validate_description("%TAG")
        with pytest.raises(ValueError, match="Invalid characters"):
            validate_description("&anchor")

    def test_sensitive_data_masked(self) -> None:
        """機密情報をマスク"""
        assert "[API_KEY_MASKED]" in validate_description("api_key: secret123abc")
        assert "[TOKEN_MASKED]" in validate_description("token=eyJhbGciOiJIUzI1NiJ9")
        assert "[PASSWORD_MASKED]" in validate_description("password: mysecret")

    def test_jwt_masked(self) -> None:
        """JWTトークンをマスク"""
        # JWT format: header.payload.signature
        jwt = (
            "eyJhbGciOiJIUzI1NiJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        )
        # JWTパターン直接テスト（token=なしで）
        result = validate_description(f"Error with JWT: {jwt}")
        assert "[JWT_MASKED]" in result
        assert jwt not in result

    def test_github_pat_masked(self) -> None:
        """GitHub PATをマスク（P1-4追加）"""
        pat = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
        result = validate_description(f"GitHub token: {pat}")
        assert "[GITHUB_PAT_MASKED]" in result
        assert pat not in result

    def test_aws_key_masked(self) -> None:
        """AWS Access Keyをマスク（P1-4追加）"""
        aws_key = "AKIAIOSFODNN7EXAMPLE"
        result = validate_description(f"AWS key: {aws_key}")
        assert "[AWS_KEY_MASKED]" in result
        assert aws_key not in result

    def test_connection_string_masked(self) -> None:
        """接続文字列のクレデンシャルをマスク（P1-4追加）"""
        conn = "postgres://user:password123@localhost:5432/db"
        result = validate_description(f"Connection: {conn}")
        assert "[CREDENTIALS_MASKED]" in result
        assert "password123" not in result


# =============================================================================
# Task 3: progress_state.yaml更新テスト
# =============================================================================


class TestErrorOccurrence:
    """ErrorOccurrenceデータクラスのテスト"""

    def test_default_values(self) -> None:
        """デフォルト値の確認"""
        occ = ErrorOccurrence(description="テストエラー")
        assert occ.count == 1
        assert occ.kb_promoted is False
        assert isinstance(occ.occurrences, list)

    def test_to_dict(self) -> None:
        """辞書変換"""
        occ = ErrorOccurrence(
            description="テストエラー",
            count=3,
            first_seen="2025-12-01",
            last_seen="2025-12-05",
            occurrences=["2025-12-01", "2025-12-03", "2025-12-05"],
            kb_promoted=True,
        )
        data = occ.to_dict()
        assert data["description"] == "テストエラー"
        assert data["count"] == 3
        assert data["kb_promoted"] is True

    def test_from_dict(self) -> None:
        """辞書から生成"""
        data = {
            "description": "テストエラー",
            "count": 2,
            "first_seen": "2025-12-01",
            "last_seen": "2025-12-03",
            "occurrences": ["2025-12-01", "2025-12-03"],
            "kb_promoted": False,
        }
        occ = ErrorOccurrence.from_dict(data)
        assert occ.count == 2
        assert len(occ.occurrences) == 2


class TestProgressStateManager:
    """progress_state.yaml管理クラスのテスト"""

    def test_create_default_structure(self, tmp_path: Path) -> None:
        """デフォルト構造の作成"""
        file_path = tmp_path / "progress_state.yaml"
        manager = ProgressStateManager(file_path)

        assert manager._data["current_week"] == 1
        assert "error_occurrences" in manager._data
        assert manager._data["metadata"]["schema_version"] == "2.1.0"

    def test_record_new_error(self, tmp_path: Path) -> None:
        """新規エラーの記録"""
        file_path = tmp_path / "progress_state.yaml"
        manager = ProgressStateManager(file_path)

        count, kb_suggested = manager.record_error("volume_mount", "Docker volumeエラー")

        assert count == 1
        assert kb_suggested is False
        assert "volume_mount" in manager._data["error_occurrences"]

    def test_record_existing_error_increment(self, tmp_path: Path) -> None:
        """既存エラーのカウント増加"""
        file_path = tmp_path / "progress_state.yaml"
        manager = ProgressStateManager(file_path)

        manager.record_error("test_error", "テスト")
        count2, _ = manager.record_error("test_error", "テスト")
        count3, kb_suggested = manager.record_error("test_error", "テスト")

        assert count2 == 2
        assert count3 == 3
        assert kb_suggested is True  # 3回目でKB昇格推奨

    def test_kb_promoted_continues_counting(self, tmp_path: Path) -> None:
        """KB昇格後もカウント継続"""
        file_path = tmp_path / "progress_state.yaml"
        manager = ProgressStateManager(file_path)

        # 3回記録してKB昇格状態にする
        manager.record_error("test_error", "テスト")
        manager.record_error("test_error", "テスト")
        manager.record_error("test_error", "テスト")

        # 手動でkb_promoted=Trueに設定
        manager._data["error_occurrences"]["test_error"]["kb_promoted"] = True

        # 4回目の記録
        count4, kb_suggested = manager.record_error("test_error", "テスト")

        assert count4 == 4
        assert kb_suggested is False  # 既にkb_promoted=Trueなので推奨なし

    def test_same_day_deduplication(self, tmp_path: Path) -> None:
        """同日の重複記録は1エントリ"""
        file_path = tmp_path / "progress_state.yaml"
        manager = ProgressStateManager(file_path)

        manager.record_error("test_error", "テスト")
        manager.record_error("test_error", "テスト")

        error_data = manager._data["error_occurrences"]["test_error"]
        assert len(error_data["occurrences"]) == 1  # 同日は1エントリ

    def test_save_and_load(self, tmp_path: Path) -> None:
        """保存と読み込み"""
        file_path = tmp_path / "progress_state.yaml"

        # 保存
        manager1 = ProgressStateManager(file_path)
        manager1.record_error("volume_mount", "Docker volumeエラー")
        manager1.save()

        # 読み込み
        manager2 = ProgressStateManager(file_path)
        error = manager2.get_error("volume_mount")

        assert error is not None
        assert error.description == "Docker volumeエラー"
        assert error.count == 1

    def test_description_merge_on_update(self, tmp_path: Path) -> None:
        """P1-IMPL-1: 既存エラー更新時にdescriptionがマージされる"""
        file_path = tmp_path / "progress_state.yaml"
        manager = ProgressStateManager(file_path)

        # 初回記録
        manager.record_error("test_error", "初回エラー")

        # 2回目記録（異なるdescription）
        manager.record_error("test_error", "2回目の詳細")

        error = manager.get_error("test_error")
        assert error is not None
        assert " | " in error.description  # マージされている
        assert "初回エラー" in error.description
        assert "2回目の詳細" in error.description

    def test_description_merge_no_duplicate(self, tmp_path: Path) -> None:
        """P1-IMPL-1: 同じdescriptionは重複追加されない"""
        file_path = tmp_path / "progress_state.yaml"
        manager = ProgressStateManager(file_path)

        manager.record_error("test_error", "同じ説明")
        manager.record_error("test_error", "同じ説明")  # 重複

        error = manager.get_error("test_error")
        assert error is not None
        # 1回のみ含まれる
        assert error.description.count("同じ説明") == 1

    def test_description_merge_skip_default(self, tmp_path: Path) -> None:
        """P1-IMPL-1: '説明未設定'はマージしない"""
        file_path = tmp_path / "progress_state.yaml"
        manager = ProgressStateManager(file_path)

        manager.record_error("test_error", "初回エラー")
        manager.record_error("test_error", "説明未設定")  # デフォルト値

        error = manager.get_error("test_error")
        assert error is not None
        # デフォルト値はマージされない
        assert "説明未設定" not in error.description


# =============================================================================
# Task 4: daily_progress.md更新テスト
# =============================================================================


class TestDailyProgressManager:
    """daily_progress.md管理クラスのテスト"""

    def test_create_default_template(self, tmp_path: Path) -> None:
        """デフォルトテンプレートの作成"""
        file_path = tmp_path / "daily_progress.md"
        manager = DailyProgressManager(file_path)

        assert "# Daily Progress" in manager._content
        assert "## エラー参照履歴" in manager._content

    def test_append_error_entry(self, tmp_path: Path) -> None:
        """エラーエントリの追記"""
        file_path = tmp_path / "daily_progress.md"
        manager = DailyProgressManager(file_path)

        manager.append_error_entry("volume_mount", "Docker volumeエラー", 1, False)

        assert "- ★ [volume_mount] Docker volumeエラー" in manager._content

    def test_star_count_by_occurrence(self, tmp_path: Path) -> None:
        """発生回数に応じた★マーク"""
        file_path = tmp_path / "daily_progress.md"
        manager = DailyProgressManager(file_path)

        manager.append_error_entry("error1", "エラー1", 1, False)
        manager.append_error_entry("error2", "エラー2", 2, False)
        manager.append_error_entry("error3", "エラー3", 3, True)
        manager.append_error_entry("error4", "エラー4", 5, True)  # 3以上は★★★

        assert "- ★ [error1]" in manager._content
        assert "- ★★ [error2]" in manager._content
        assert "- ★★★ [error3]" in manager._content
        assert "- ★★★ [error4]" in manager._content  # 5回でも★★★

    def test_kb_promotion_note(self, tmp_path: Path) -> None:
        """KB昇格推奨メッセージ"""
        file_path = tmp_path / "daily_progress.md"
        manager = DailyProgressManager(file_path)

        manager.append_error_entry("error1", "エラー1", 3, True)
        manager.append_error_entry("error2", "エラー2", 3, False)

        assert "→ KB昇格検討" in manager._content
        # error2はkb_suggested=Falseなので昇格メッセージなし

    def test_update_existing_entry(self, tmp_path: Path) -> None:
        """既存エントリの更新"""
        file_path = tmp_path / "daily_progress.md"
        manager = DailyProgressManager(file_path)

        manager.append_error_entry("volume_mount", "Docker volumeエラー", 1, False)
        manager.append_error_entry("volume_mount", "Docker volumeエラー", 2, False)

        # 同じerror_idのエントリは1つだけ
        count = manager._content.count("[volume_mount]")
        assert count == 1
        assert "★★ [volume_mount]" in manager._content

    def test_save_updates_date(self, tmp_path: Path) -> None:
        """保存時に最終更新日を更新"""
        file_path = tmp_path / "daily_progress.md"
        file_path.write_text("# Daily Progress\n*最終更新: 2025-01-01*\n", encoding="utf-8")

        manager = DailyProgressManager(file_path)
        manager.save()

        content = file_path.read_text(encoding="utf-8")
        assert "2025-01-01" not in content  # 古い日付は更新される

    def test_display_description_first_entry_only(self, tmp_path: Path) -> None:
        """P1-IMPL-2: daily_progress.mdに初回descriptionのみ表示"""
        file_path = tmp_path / "daily_progress.md"
        manager = DailyProgressManager(file_path)

        # マージ済みdescription（" | "区切り）
        merged_desc = "初回エラー | [2025-12-05] 2回目の詳細"
        manager.append_error_entry("test_error", merged_desc, 2, False)

        # 表示されるのは初回のみ
        assert "初回エラー" in manager._content
        assert "2回目の詳細" not in manager._content

    def test_display_description_no_separator(self, tmp_path: Path) -> None:
        """P1-IMPL-2: 区切りがない場合はそのまま表示"""
        file_path = tmp_path / "daily_progress.md"
        manager = DailyProgressManager(file_path)

        # 単一description（区切りなし）
        manager.append_error_entry("test_error", "単一のエラー説明", 1, False)

        # そのまま表示
        assert "単一のエラー説明" in manager._content


# =============================================================================
# P1-SEC-1: エラーメッセージテスト
# =============================================================================


class TestSecurityImprovements:
    """P1-SEC-1/P1-SEC-2: セキュリティ改善テスト"""

    def test_error_message_no_input_exposure(self) -> None:
        """P1-SEC-1: エラーメッセージに入力値が含まれない"""
        malicious = "!ruby/object:Gem::Specification"
        with pytest.raises(ValueError) as exc_info:
            validate_description(malicious)
        # 入力値が露出していない
        assert malicious not in str(exc_info.value)
        assert "Invalid characters" in str(exc_info.value)

    def test_github_pat_short_masked(self) -> None:
        """P1-SEC-2: 短いGitHub PATもマスク（fine-grained対応）"""
        short_pat = "ghp_abc123"  # 36文字未満
        result = validate_description(f"Token: {short_pat}")
        assert "[GITHUB_PAT_MASKED]" in result
        assert short_pat not in result

    def test_github_pat_long_masked(self) -> None:
        """P1-SEC-2: 長いGitHub PATもマスク"""
        long_pat = "ghp_" + "a" * 100  # 100文字以上
        result = validate_description(f"Token: {long_pat}")
        assert "[GITHUB_PAT_MASKED]" in result
        assert long_pat not in result


# =============================================================================
# 統合テスト
# =============================================================================


class TestRecordErrorIntegration:
    """record_error統合関数のテスト"""

    def test_successful_record(self, tmp_path: Path) -> None:
        """正常なエラー記録"""
        progress_file = tmp_path / "progress_state.yaml"
        daily_file = tmp_path / "daily_progress.md"

        result = record_error(
            "Volume_Mount",
            "Docker volume設定エラー",
            progress_file,
            daily_file,
        )

        assert result["success"] is True
        assert result["error_id"] == "volume_mount"
        assert result["count"] == 1
        assert "✅ エラー記録完了" in result["message"]

        # ファイルが作成されていることを確認
        assert progress_file.exists()
        assert daily_file.exists()

    def test_invalid_error_id(self, tmp_path: Path) -> None:
        """無効なerror_idでエラー"""
        progress_file = tmp_path / "progress_state.yaml"
        daily_file = tmp_path / "daily_progress.md"

        result = record_error("", "テスト", progress_file, daily_file)

        assert result["success"] is False
        assert "❌ エラー記録失敗" in result["message"]

    def test_kb_promotion_message(self, tmp_path: Path) -> None:
        """KB昇格推奨メッセージ"""
        progress_file = tmp_path / "progress_state.yaml"
        daily_file = tmp_path / "daily_progress.md"

        # 3回記録
        record_error("test_error", "テスト", progress_file, daily_file)
        record_error("test_error", "テスト", progress_file, daily_file)
        result = record_error("test_error", "テスト", progress_file, daily_file)

        assert result["kb_suggested"] is True
        assert "KB昇格検討" in result["message"]

    def test_yaml_injection_blocked(self, tmp_path: Path) -> None:
        """YAML Injectionはブロック"""
        progress_file = tmp_path / "progress_state.yaml"
        daily_file = tmp_path / "daily_progress.md"

        result = record_error(
            "test_error",
            "!ruby/object:Gem::Specification",
            progress_file,
            daily_file,
        )

        assert result["success"] is False
        assert "Invalid characters" in result["error"]
