"""Static contracts for the Issue #552 CI workflow changes."""

import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

# repo_contract: request.config.rootpath 経由でリポジトリ全体を静的検査するため、
# ビルドコンテキストが絞られた test コンテナでは走らせない（pyproject.toml の marker 定義参照）
pytestmark = [pytest.mark.unit, pytest.mark.repo_contract]


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


def test_external_api_environment_boundaries_are_explicit(
    workflow_data: dict[str, Any],
) -> None:
    """PR/Composeは外部APIを止め、週次coverageだけ明示的に有効化する。"""
    pr_steps = workflow_data["jobs"]["pr-validation"]["steps"]
    pr_test_step = next(
        step for step in pr_steps if step.get("name") == "Run tests (unit + integration + smoke)"
    )
    assert pr_test_step["env"]["TEST__EXTERNAL_API_ENABLED"] == "false"

    compose_steps = workflow_data["jobs"]["compose-test"]["steps"]
    compose_test_step = next(
        step for step in compose_steps if step.get("name") == "Run pytest in test container"
    )
    assert compose_test_step["env"]["TEST__EXTERNAL_API_ENABLED"] == "false"

    weekly_steps = workflow_data["jobs"]["weekly-extended-test"]["steps"]
    coverage_step = next(
        step for step in weekly_steps if step.get("name") == "Full coverage report"
    )
    assert coverage_step["env"]["TEST__EXTERNAL_API_ENABLED"] == "true"


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


def test_ruff_workflow_steps_are_check_only(workflow_data: dict[str, Any]) -> None:
    ruff_steps = [
        (job_name, step.get("name", "<unnamed>"), step["run"])
        for job_name, job in workflow_data["jobs"].items()
        if isinstance(job.get("steps"), list)
        for step in job["steps"]
        if isinstance(step.get("run"), str) and "ruff check" in step["run"]
    ]

    # 非空 assert だけでは片方のジョブから ruff ステップが消えても通過してしまうため、
    # lint ゲートを必要とするジョブを明示する（PR 検証とマージ後検証の両方）。
    required_jobs = {"pr-validation", "post-validation"}
    gated_jobs = {job_name for job_name, _, _ in ruff_steps}
    assert required_jobs <= gated_jobs, (
        f"CI ruff gate missing from jobs: {sorted(required_jobs - gated_jobs)}"
    )

    missing_no_fix = [
        f"{job_name}/{step_name}"
        for job_name, step_name, run in ruff_steps
        if "--no-fix" not in run
    ]
    assert not missing_no_fix, "CI ruff check steps must not modify the checkout: " + ", ".join(
        missing_no_fix
    )


def _is_unflagged_ruff_gate(line: str) -> bool:
    # 引用符を区切りに変換してから、shell のコメントと演算子を分離する。
    normalized = line.translate(str.maketrans("`'\"", "   "))
    lexer = shlex.shlex(normalized, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    lexer.commenters = "#"
    lexer.escape = ""
    parsed = list(lexer)

    for index in range(len(parsed) - 1):
        if parsed[index : index + 2] != ["ruff", "check"]:
            continue

        command_end = next(
            (
                offset
                for offset, token in enumerate(parsed[index + 2 :], index + 2)
                # 同一行に並ぶ次の `ruff check` のフラグを、手前のコマンドの引数に数えない。
                if token in {"&&", "||", "&", ";", "|"}
                or parsed[offset : offset + 2] == ["ruff", "check"]
            ),
            len(parsed),
        )
        arguments = parsed[index + 2 : command_end]
        if "--no-fix" in arguments or "--fix" in arguments:
            continue

        command_start = (
            max(
                (
                    offset
                    for offset, token in enumerate(parsed[:index])
                    if token in {"&&", "||", "&", ";", "|"}
                ),
                default=-1,
            )
            + 1
        )
        # `uv run` と `ruff check` の間のトークンは uv のオプションとみなす。
        has_uv_run_prefix = any(
            parsed[offset : offset + 2] == ["uv", "run"] for offset in range(command_start, index)
        )
        if has_uv_run_prefix or "." in arguments:
            return True

    return False


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("uv run --frozen ruff check utils/", True),
        ("uv run --frozen --no-sync ruff check --select S603 scripts/", True),
        ("uv run --frozen ruff check . --no-fix", False),
        ("uv run ruff check --fix .", False),
        ("ruff check .", True),
        ("ruff check . --no-fix", False),
        ("uv run ruff check . && echo --no-fix", True),
        ("ruff check . & echo --no-fix", True),
        ("ruff check .&& echo --no-fix", True),
        ("ruff check .; uv run ruff check --no-fix .", True),
        ("uv run --frozen ruff check utils/ # use --no-fix in CI", True),
        ("`ruff check` is documented as the default command", False),
        ('run: "uv run ruff check utils/"', True),
        ("bash -c 'uv run ruff check .'", True),
        ("Don't run `uv run ruff check utils/`, it's a false-green gate", True),
        ("NG: `uv run ruff check .` / OK: `uv run ruff check . --no-fix`", True),
        ("OK: `uv run ruff check --no-fix .` / NG: `uv run ruff check .`", True),
        ("`uv run ruff check --no-fix .` と `uv run ruff check --fix .`", False),
    ],
)
def test_ruff_gate_matcher_handles_uv_options_and_fix_flags(line: str, expected: bool) -> None:
    assert _is_unflagged_ruff_gate(line) is expected


def test_tracked_docs_do_not_teach_false_green_ruff_gate(
    request: pytest.FixtureRequest,
) -> None:
    """`ruff check` は `fix = true` を継承して違反を自動修正し exit 0 を返す。

    CI だけを直してもドキュメント側に残っていれば、それを読んだ人間やエージェントが
    緑になるだけのゲートを実行してしまう。追跡ファイル全体を対象に、修正フラグを
    明示しない ruff 実行コマンドが再び現れないことを保証する。

    検出対象は次の 2 形。
    - `ruff check .`（パス明示・フラグなし）
    - `uv run` の前置オプションを許容した `uv run ... ruff check ...` で、
      `--no-fix` も `--fix` も伴わないもの
      （`ruff check`、`ruff check utils/`、`ruff check --select X scripts/` 等）

    既知の限界: 「Gate」見出しの直下に `ruff check --fix .` を書く形は、自動修正
    目的の正当な記述と機械的に区別できないため検出しない。レビューで担保する。
    """
    repo_root = Path(request.config.rootpath)
    git = shutil.which("git")
    assert git is not None, "git executable not found"

    tracked = subprocess.run(  # noqa: S603
        [git, "ls-files", "-z"],
        capture_output=True,
        check=True,
        cwd=repo_root,
        text=True,
    )

    offenders = []
    for name in tracked.stdout.split("\0"):
        if not name:
            continue
        path = repo_root / name
        if path.suffix not in {".md", ".yml", ".yaml"} or not path.is_file():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _is_unflagged_ruff_gate(line):
                offenders.append(f"{name}:{lineno}")

    assert not offenders, "ruff ゲートは --no-fix、自動修正は --fix を明示すること: " + ", ".join(
        offenders
    )
