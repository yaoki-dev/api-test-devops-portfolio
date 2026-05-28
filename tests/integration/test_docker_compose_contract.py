"""docker-compose.yml 運用契約テスト.

PR#372 review #10 対応: pytestmark = pytest.mark.unit (module-level) と
クラスレベル @pytest.mark.integration の累積で `pytest -m unit` 実行時に
docker-compose.yml 読み込みテストが unit として実行される問題を解消するため、
tests/unit/test_config_settings.py から tests/integration/ に移動。

本ファイルは module-level pytestmark で integration マーカーを宣言する。
"""

from pathlib import Path
from typing import Any

import pytest
import yaml

# Module-level marker: All tests in this file are integration tests
# (docker-compose.yml をファイルシステムから読み込むため
# pyproject.toml marker定義「integration: external dependencies」に整合)
pytestmark = pytest.mark.integration


class TestDockerComposeContract:
    """docker-compose.yml の運用契約を軽量に保護する."""

    @pytest.fixture
    def compose_data(self, request: pytest.FixtureRequest) -> dict[str, Any]:
        """docker-compose.yml を読み込んで parsed dict を返す共通 fixture.

        各テストでの compose_path/yaml.safe_load 2行重複を解消。
        pytest rootdir (pyproject.toml で確定) 基準でパス解決するため、
        テストファイルの移動に影響されない。
        """
        compose_path = Path(request.config.rootdir) / "docker-compose.yml"
        return yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    def test_app_compose_startup_validation_structure(self, compose_data: dict[str, Any]) -> None:
        """app service の fail-loud 起動構成 (env_file/restart/command) を YAML レベルで保護する"""
        app = compose_data["services"]["app"]

        assert app["env_file"] == [{"path": ".env.${ENVIRONMENT:-development}", "required": False}]
        assert app["environment"]["ENVIRONMENT"] == "${ENVIRONMENT:-development}"
        assert app["restart"] == "on-failure:3"
        assert "from config.settings import settings" in app["command"][-1]
        assert "&& exec sleep infinity" in app["command"][-1]

    def test_test_service_contract(self, compose_data: dict[str, Any]) -> None:
        """test service の運用契約 (profiles/ENVIRONMENT/marker) を YAML レベルで保護する.

        保護対象 (PR#372 review #5 対応):
            - profiles: ["test"] (通常の docker compose up で起動しないこと)
            - environment.ENVIRONMENT == "testing" (固定)
            - command に "(unit or integration) and not external" marker が含まれること

        Note:
            --cov-fail-under=85 の検証は削除した。
            pyproject.toml [tool.pytest.ini_options] addopts に
            --cov-fail-under が含まれており、docker compose test service の
            command で重複 fixate する必要がないというユーザー意図に同期。
        """
        test_service = compose_data["services"]["test"]

        assert test_service["profiles"] == ["test"]
        assert test_service["environment"]["ENVIRONMENT"] == "testing"
        command = test_service["command"]
        assert "(unit or integration) and not external" in command
