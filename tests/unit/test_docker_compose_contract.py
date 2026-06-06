"""docker-compose.yml の運用契約テスト."""

from typing import Any

import pytest
import yaml

# Module-level marker: All tests in this file are unit tests
# 外部プロセス(Docker)を起動せずYAML構造のみを検証するため
# pyproject.toml marker定義 「unit」 に整合
pytestmark = pytest.mark.unit


class TestDockerComposeContract:
    """docker-compose.yml の運用契約を軽量に保護する."""

    @pytest.fixture
    def compose_data(self, request: pytest.FixtureRequest) -> dict[str, Any]:
        """docker-compose.yml を読み込んで parsed dict を返す共通 fixture.

        pytest rootpath (pyproject.toml で確定) 基準でパス解決するため、
        テストファイルの移動に影響されない。ファイル不在は FileNotFoundError、
        YAML パース失敗は yaml.YAMLError として pytest が自動レポートする。
        """
        compose_path = request.config.rootpath / "docker-compose.yml"
        data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
        assert isinstance(data, dict) and "services" in data, (
            f"docker-compose.yml の構造が不正: type={type(data)}, path={compose_path}"
        )
        return data

    def test_app_compose_startup_validation_structure(self, compose_data: dict[str, Any]) -> None:
        """app service の fail-loud 起動構成 (env_file/restart/command) を YAML レベルで保護する"""
        app = compose_data["services"]["app"]

        assert app["build"]["target"] == "runtime"
        assert app["env_file"] == [{"path": ".env.${ENVIRONMENT:-development}", "required": False}]
        assert app["environment"]["ENVIRONMENT"] == "${ENVIRONMENT:-development}"
        assert app["restart"] == "on-failure:3"
        command = app["command"]
        command_text = " ".join(command) if isinstance(command, list) else command
        assert "config.settings" in command_text
        assert "&& exec sleep infinity" in command_text

    def test_test_service_contract(self, compose_data: dict[str, Any]) -> None:
        """test service の運用契約 (profiles/ENVIRONMENT/marker) を YAML レベルで保護する.

        保護対象:
            - build.target == "test" (pytest/cov 依存を含む test stage を使うこと)
            - profiles: ["test"] (通常の docker compose up で起動しないこと)
            - environment.ENVIRONMENT == "testing" (固定)
            - command に "(unit or integration) and not external" marker が含まれること
            - user は DOCKER_UID/DOCKER_GID で host 書込権限と同期すること

        Note:
            --cov-fail-under=85 の検証は削除した。
            pyproject.toml [tool.pytest.ini_options] addopts に
            --cov-fail-under が含まれており、docker compose test service の
            command で重複 fixate する必要がないというユーザー意図に同期。
        """
        test_service = compose_data["services"]["test"]

        assert test_service["build"]["target"] == "test"
        assert test_service["profiles"] == ["test"]
        assert test_service["env_file"] == [{"path": ".env.testing", "required": False}]
        assert test_service["environment"]["ENVIRONMENT"] == "testing"
        assert test_service["environment"]["COVERAGE_FILE"] == "/tmp/.coverage"  # noqa: S108
        assert test_service["user"] == "${DOCKER_UID:-1000}:${DOCKER_GID:-1000}"
        assert test_service["command"] == ["pytest", "-m", "(unit or integration) and not external"]

    def test_test_service_security_contract(self, compose_data: dict[str, Any]) -> None:
        """test service の権限昇格防止設定 (security_opt/init) を YAML レベルで保護する."""
        test_service = compose_data["services"]["test"]
        assert "no-new-privileges:true" in test_service["security_opt"]
        assert test_service["init"] is True

    def test_app_service_security_contract(self, compose_data: dict[str, Any]) -> None:
        """app service の権限昇格防止設定 (security_opt/init) を YAML レベルで保護する."""
        app = compose_data["services"]["app"]
        assert "no-new-privileges:true" in app["security_opt"]
        assert app["init"] is True

    def test_test_service_volumes_contract(self, compose_data: dict[str, Any]) -> None:
        """test service のカバレッジ成果物永続化 (volumes) を YAML レベルで保護する."""
        test_service = compose_data["services"]["test"]
        volumes = test_service.get("volumes", [])
        assert "./reports:/app/reports" in volumes
