"""config.settings._get_allowed_domains() の警告ログ契約テスト.

許可リストが空の場合のみ警告ログを出す契約を保護する。
戻り値の機能検証は test_config_settings.py (TestAllowedDomainsEnvOverride) に集約する。
"""

import logging

import pytest

from config.settings import _get_allowed_domains

pytestmark = pytest.mark.unit


class TestAllowedDomainsLogging:
    """ALLOWED_DOMAINS の警告ログ契約テスト。"""

    def test_empty_env_emits_warning(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """ALLOWED_DOMAINS が空文字の場合、起動時に警告ログを出す契約を保護する。"""
        monkeypatch.setenv("ALLOWED_DOMAINS", "")

        with caplog.at_level(logging.WARNING, logger="config.settings"):
            _get_allowed_domains()

        assert any(
            record.levelno == logging.WARNING and "全ドメインを拒否" in record.getMessage()
            for record in caplog.records
        )

    def test_default_emits_no_warning(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """ALLOWED_DOMAINS 未設定時、デフォルト値を使い警告ログを出さない。"""
        monkeypatch.delenv("ALLOWED_DOMAINS", raising=False)

        with caplog.at_level(logging.WARNING, logger="config.settings"):
            _get_allowed_domains()

        assert not any("全ドメインを拒否" in record.getMessage() for record in caplog.records)
