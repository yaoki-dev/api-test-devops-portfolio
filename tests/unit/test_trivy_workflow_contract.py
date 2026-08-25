"""Trivy reusable workflow の静的契約テスト."""

from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

pytestmark = [pytest.mark.unit, pytest.mark.repo_contract]

CALLER_JOB_IDS = ("pr-trivy-scan", "post-trivy-scan")
CALLER_PERMISSIONS = {"contents": "read", "security-events": "write"}
IMAGE_TAG = "api-test-devops:scan"


def _load_yaml(path: str, request: pytest.FixtureRequest) -> dict[str, Any]:
    data = yaml.safe_load((request.config.rootpath / path).read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path} の YAML 構造が不正: type={type(data)}"
    return data


def _workflow_on(data: dict[Any, Any]) -> dict[str, Any]:
    on_section = data.get("on", data.get(True))
    assert isinstance(on_section, dict), f"workflow on section が不正: type={type(on_section)}"
    return on_section


@pytest.fixture
def ci_workflow(request: pytest.FixtureRequest) -> dict[str, Any]:
    return _load_yaml(".github/workflows/ci.yml", request)


@pytest.fixture
def trivy_workflow(request: pytest.FixtureRequest) -> dict[str, Any]:
    return _load_yaml(".github/workflows/trivy-scan.yml", request)


def test_reusable_trivy_workflow_call_contract(trivy_workflow: dict[str, Any]) -> None:
    workflow_call = _workflow_on(trivy_workflow).get("workflow_call")
    assert isinstance(workflow_call, dict), "trivy-scan.yml は workflow_call で公開する必要がある"

    inputs = workflow_call.get("inputs")
    assert isinstance(inputs, dict), "workflow_call inputs が定義されていない"
    assert inputs["scan-prefix"] == {"required": True, "type": "string"}
    assert inputs["scan-image"] == {"required": True, "type": "boolean"}


def test_reusable_trivy_job_name_permissions_and_verify_action(
    trivy_workflow: dict[str, Any],
) -> None:
    jobs = trivy_workflow.get("jobs")
    assert isinstance(jobs, dict), "trivy-scan.yml に jobs が無い"

    job = jobs["trivy-scan"]
    assert job["name"] == "Trivy scan"
    assert job["runs-on"] == "ubuntu-latest"
    assert job["timeout-minutes"] == 20
    assert job["permissions"] == CALLER_PERMISSIONS

    steps = job["steps"]
    verify_steps = [
        step for step in steps if step.get("uses") == "./.github/actions/trivy-sarif-verify"
    ]
    assert len(verify_steps) == 2, (
        "filesystem/image の 2 箇所で local verify action を使う必要がある"
    )


def test_reusable_trivy_scan_and_gate_contract(
    trivy_workflow: dict[str, Any],
) -> None:
    steps = {
        step["id"]: step for step in trivy_workflow["jobs"]["trivy-scan"]["steps"] if "id" in step
    }

    for step_id in ("fs-scan", "fs-gate", "image-scan", "image-gate"):
        assert steps[step_id]["with"]["scanners"] == "vuln,secret"

    assert steps["fs-scan"]["with"]["exit-code"] == "0"
    assert steps["fs-scan"]["with"]["format"] == "sarif"
    assert steps["verify-fs-scan"]["with"] == {
        "sarif-file": "trivy-${{ inputs.scan-prefix }}-fs-scan.sarif",
        "scan-type": "filesystem",
    }
    assert steps["fs-gate"]["with"]["exit-code"] == "1"
    assert steps["fs-gate"]["with"]["severity"] == "CRITICAL,HIGH"
    assert "exit 1" in next(
        step["run"]
        for step in trivy_workflow["jobs"]["trivy-scan"]["steps"]
        if step.get("name", "").startswith("Fail job if fs vulnerabilities")
    )

    assert steps["image-scan"]["with"]["exit-code"] == "0"
    assert steps["image-scan"]["with"]["format"] == "sarif"
    assert steps["verify-image-scan"]["with"] == {
        "sarif-file": "trivy-${{ inputs.scan-prefix }}-image-scan.sarif",
        "scan-type": "image",
    }
    assert steps["image-gate"]["with"]["exit-code"] == "1"
    assert steps["image-gate"]["with"]["severity"] == "CRITICAL,HIGH"
    assert "exit 1" in next(
        step["run"]
        for step in trivy_workflow["jobs"]["trivy-scan"]["steps"]
        if step.get("name", "").startswith("Fail job if image vulnerabilities")
    )


def test_reusable_trivy_verify_steps_are_cancellable(trivy_workflow: dict[str, Any]) -> None:
    # verify ステップに always() が混入すると、ワークフローキャンセル時も実行され続けて
    # キャンセルが即座に効かなくなる（GitHub 公式が非推奨とする挙動）。過去に fs 側だけ
    # !cancelled() へ移行して image 側が always() のまま取り残された経緯があるため、
    # 両ステップを対称に固定して再発を防ぐ。
    steps = {
        step["id"]: step for step in trivy_workflow["jobs"]["trivy-scan"]["steps"] if "id" in step
    }

    for step_id in ("verify-fs-scan", "verify-image-scan"):
        condition = steps[step_id]["if"]
        assert "!cancelled()" in condition, (
            f"{step_id} はキャンセル即応のため !cancelled() を使う必要がある: {condition}"
        )
        assert "always()" not in condition, (
            f"{step_id} の always() はキャンセルを遅延させるため禁止: {condition}"
        )


def test_reusable_trivy_buildx_cache_contract(trivy_workflow: dict[str, Any]) -> None:
    steps = trivy_workflow["jobs"]["trivy-scan"]["steps"]

    buildx_step = next(
        step for step in steps if step.get("uses", "").startswith("docker/setup-buildx-action@")
    )
    assert buildx_step["if"] == "${{ inputs.scan-image }}"

    build_step = next(step for step in steps if step.get("id") == "docker-build")
    assert build_step["uses"].startswith("docker/build-push-action@")
    assert build_step["if"] == "${{ inputs.scan-image }}"
    assert build_step["with"]["cache-from"] == "type=gha,scope=api-test-runtime"
    # cache-to は「未設定」であることが契約。ci.yml の publish-image / compose-healthcheck が
    # 同一 scope の唯一の writer で、ここが書くと PR 経由の cache poisoning 経路になる。
    assert "cache-to" not in build_step["with"]


def test_reusable_trivy_image_tag_is_consistent(trivy_workflow: dict[str, Any]) -> None:
    """build / image-scan / image-gate / cleanup が同一タグを指すことを固定する。

    不一致は scan-image が true の実行（main 宛 PR と push）でしか露見せず、
    通常の PR では skip されるため CI が緑のまま潜伏する。
    """
    steps = trivy_workflow["jobs"]["trivy-scan"]["steps"]
    by_id = {step["id"]: step for step in steps if "id" in step}

    tag = by_id["docker-build"]["with"]["tags"]
    assert tag == IMAGE_TAG
    assert by_id["image-scan"]["with"]["image-ref"] == IMAGE_TAG
    assert by_id["image-gate"]["with"]["image-ref"] == IMAGE_TAG

    cleanup = next(step for step in steps if step.get("name") == "Clean up Docker image")
    assert IMAGE_TAG in cleanup["run"]


def test_trivy_callers_are_job_level_boundaries_only(ci_workflow: dict[str, Any]) -> None:
    jobs = ci_workflow["jobs"]

    pr_job = jobs["pr-trivy-scan"]
    assert pr_job["name"] == "PR Trivy scan"
    assert pr_job["if"] == "github.event_name == 'pull_request'"
    assert pr_job["permissions"] == CALLER_PERMISSIONS
    assert pr_job["uses"] == "./.github/workflows/trivy-scan.yml"
    assert pr_job["with"] == {
        "scan-prefix": "pr",
        "scan-image": (
            "${{ github.base_ref == 'main' || "
            "contains(github.event.pull_request.labels.*.name, 'docker') }}"
        ),
    }

    post_job = jobs["post-trivy-scan"]
    assert post_job["name"] == "Post Trivy Scan"
    assert post_job["if"] == (
        "github.event_name == 'push' && (github.ref == 'refs/heads/main' "
        "|| github.ref == 'refs/heads/develop')"
    )
    assert post_job["permissions"] == CALLER_PERMISSIONS
    assert post_job["uses"] == "./.github/workflows/trivy-scan.yml"
    assert post_job["with"] == {"scan-prefix": "post", "scan-image": True}

    for job_id in CALLER_JOB_IDS:
        job = jobs[job_id]
        assert set(job) <= {"name", "if", "permissions", "uses", "with"}
        assert "steps" not in job
        assert "runs-on" not in job


def test_status_report_keeps_required_trivy_job_ids(ci_workflow: dict[str, Any]) -> None:
    needs = ci_workflow["jobs"]["status-report"]["needs"]
    assert "pr-trivy-scan" in needs
    assert "post-trivy-scan" in needs
