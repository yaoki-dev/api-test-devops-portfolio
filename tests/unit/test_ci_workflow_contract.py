"""Static contracts for the Issue #552 CI workflow changes."""

from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

pytestmark = pytest.mark.unit


@pytest.fixture
def workflow_data(request: pytest.FixtureRequest) -> dict[str, Any]:
    """pytest rootpath 基準で解決し、テストファイル移動によるパス破損を防ぐ。"""
    workflow_path = request.config.rootpath / ".github/workflows/ci.yml"
    data = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_pr_validation_main_pytest_emits_junit_xml(workflow_data: dict[str, Any]) -> None:
    steps = workflow_data["jobs"]["pr-validation"]["steps"]
    test_step = next(
        step for step in steps if step.get("name") == "Run tests (unit + integration + smoke)"
    )
    run = test_step["run"]

    main_pytest = run.split("# Step 2:", 1)[0]
    assert "uv run pytest" in main_pytest
    assert "--junitxml=reports/junit.xml" in main_pytest
    assert run.count("--junitxml=reports/junit.xml") == 1

    upload_step = next(step for step in steps if step.get("name") == "Upload test results")
    assert upload_step["if"] == "always()"
    assert "reports/" in upload_step["with"]["path"]
    assert upload_step["with"]["name"] == "pr-validation-results-py3.14"


def test_renderer_step_runs_always_after_pytest(workflow_data: dict[str, Any]) -> None:
    steps = workflow_data["jobs"]["pr-validation"]["steps"]
    renderer_index = next(
        index for index, step in enumerate(steps) if "render_test_summary.py" in step.get("run", "")
    )
    pytest_index = next(
        index
        for index, step in enumerate(steps)
        if step.get("name") == "Run tests (unit + integration + smoke)"
    )

    assert steps[renderer_index]["if"] == "always()"
    assert "reports/junit.xml" in steps[renderer_index]["run"]
    # Rendering before pytest would silently produce an empty summary.
    assert pytest_index < renderer_index


def test_status_report_summary_and_pr_coverage_contract(
    workflow_data: dict[str, Any],
) -> None:
    assert "pr-validation" in workflow_data["jobs"]["status-report"]["needs"]

    steps = workflow_data["jobs"]["status-report"]["steps"]
    summary_step = next(
        step for step in steps if step.get("name") == "Append status report to Job Summary"
    )
    run = summary_step["run"]

    assert summary_step["if"] == "always()"
    assert summary_step["env"]["EVENT_NAME"] == "${{ github.event_name }}"
    assert 'cat status_report.md >> "$GITHUB_STEP_SUMMARY"' in run
    assert 'coverage_file="artifacts/pr-validation-results-py3.14/coverage.json"' in run
    assert 'if [ "$EVENT_NAME" = "pull_request" ] && [ -f "$coverage_file" ]; then' in run
    assert (
        run.count('echo "Coverage: n/a (not generated for this trigger)" >> "$GITHUB_STEP_SUMMARY"')
        == 2
    )
