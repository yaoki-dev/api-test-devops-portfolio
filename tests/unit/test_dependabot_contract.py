"""Contract for the four Dependabot version-update target branches."""

from typing import Any

import pytest
import yaml

pytestmark = [pytest.mark.unit, pytest.mark.repo_contract]


def test_all_dependabot_ecosystems_target_develop(request: pytest.FixtureRequest) -> None:
    path = request.config.rootpath / ".github/dependabot.yml"
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    updates = data["updates"]

    assert {update["package-ecosystem"] for update in updates} == {
        "uv",
        "npm",
        "github-actions",
        "docker",
    }
    assert all(update["target-branch"] == "develop" for update in updates)
