"""config.settings._get_allowed_domains() の警告ログ契約テスト.

許可リストが空 (全ドメイン拒否) になる設定ミスを起動時に検出するための
警告ログ出力を退行から保護する。本体テスト (test_config_settings.py) とは
独立した focused モジュールとして配置する。
"""

import logging

import pytest

from config.settings import _get_allowed_domains


@pytest.mark.unit
class TestAllowedDomainsLogging:
    """_get_allowed_domains() の警告ログ挙動を検証する."""

    def test_empty_env_emits_warning(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """空の ALLOWED_DOMAINS で起動時に警告ログを出す契約を保護する."""
        monkeypatch.setenv("ALLOWED_DOMAINS", "")
        with caplog.at_level(logging.WARNING, logger="config.settings"):
            result = _get_allowed_domains()

        assert result == frozenset()
        assert any(
            record.levelno == logging.WARNING and "全ドメインを拒否" in record.getMessage()
            for record in caplog.records
        )

    def test_default_emits_no_warning(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """未設定 (デフォルト許可リスト) では警告を出さない契約を保護する."""
        monkeypatch.delenv("ALLOWED_DOMAINS", raising=False)
        with caplog.at_level(logging.WARNING, logger="config.settings"):
            result = _get_allowed_domains()

        assert result
        assert not any("全ドメインを拒否" in record.getMessage() for record in caplog.records)
