"""Contracts for the main forbidden-path manifest checker."""

import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.check_main_forbidden_paths import ManifestError, find_violations, main, read_manifest

pytestmark = [pytest.mark.unit]


@pytest.mark.repo_contract
def test_manifest_covers_release_cutover_paths() -> None:
    manifest = Path(__file__).parents[2] / ".github/main-forbidden-paths.txt"

    rules = read_manifest(manifest)

    assert {rule.path for rule in rules} == {
        ".claude",
        ".claude-plugin",
        ".cortexkit",
        ".devcontainer",
        ".serena",
        "docs/agents",
        ".cgcignore",
        ".claudeignore",
        ".mcp.json",
        ".ignore",
        "AGENTS.md",
        "CLAUDE.md",
        "CONTEXT.md",
        "api-test-devops-portfolio.code-workspace",
    }
    assert {rule.path for rule in rules if rule.is_directory} == {
        ".claude",
        ".claude-plugin",
        ".cortexkit",
        ".devcontainer",
        ".serena",
        "docs/agents",
    }


def test_directory_and_exact_rules_are_distinguished(tmp_path: Path) -> None:
    rules = read_manifest(_write_manifest(tmp_path, "private/\nREADME.md\n"))

    assert find_violations(["private/file.txt", "README.md", "README.md.bak"], rules) == [
        "README.md",
        "private/file.txt",
    ]


@pytest.mark.parametrize("entry", ["../outside", "/absolute", r"windows\\path", "a//b"])
def test_manifest_rejects_unsafe_paths(tmp_path: Path, entry: str) -> None:
    with pytest.raises(ManifestError, match="invalid path"):
        read_manifest(_write_manifest(tmp_path, f"{entry}\n"))


def test_manifest_rejects_duplicates_and_empty_files(tmp_path: Path) -> None:
    with pytest.raises(ManifestError, match="duplicate path"):
        read_manifest(_write_manifest(tmp_path, "README.md\nREADME.md/\n"))

    with pytest.raises(ManifestError, match="at least one path"):
        read_manifest(_write_manifest(tmp_path, "# comment only\n\n"))


def test_manifest_rejects_non_utf8_file(tmp_path: Path) -> None:
    path = tmp_path / "main-forbidden-paths.txt"
    path.write_bytes(b"\xff\n")

    with pytest.raises(ManifestError, match="cannot read manifest"):
        read_manifest(path)


@pytest.mark.parametrize(
    ("listing", "exit_code", "message"),
    [
        (b"ok.txt\0", 0, "check passed"),
        (b"ok.txt\0private/key\0", 1, "- private/key"),
        (b"ok.txt\0bad\xff\0", 2, "cannot list tracked paths"),
    ],
)
def test_main_exit_code_separates_violations_from_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    listing: bytes,
    exit_code: int,
    message: str,
) -> None:
    manifest = _write_manifest(tmp_path, "private/\n")

    def fake_run(args: list[str], **_: object) -> subprocess.CompletedProcess[object]:
        stdout = f"{tmp_path}\n" if "rev-parse" in args else listing
        return subprocess.CompletedProcess(args, 0, stdout=stdout)

    monkeypatch.setattr(shutil, "which", lambda name: name)
    monkeypatch.setattr(subprocess, "run", fake_run)

    assert main(["--manifest", str(manifest)]) == exit_code
    captured = capsys.readouterr()
    assert message in captured.out + captured.err


@pytest.mark.parametrize(
    "error",
    [
        PermissionError(13, "Permission denied"),
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
    ],
    ids=["permission-denied", "non-utf8-root"],
)
def test_main_reports_git_root_failure_as_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], error: Exception
) -> None:
    def fake_run(*_: object, **__: object) -> subprocess.CompletedProcess[object]:
        raise error

    monkeypatch.setattr(shutil, "which", lambda name: name)
    monkeypatch.setattr(subprocess, "run", fake_run)

    assert main([]) == 2
    assert "cannot determine Git root" in capsys.readouterr().err


def _write_manifest(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "main-forbidden-paths.txt"
    path.write_text(content, encoding="utf-8")
    return path
