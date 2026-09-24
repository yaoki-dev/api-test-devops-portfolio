"""Contracts for the main forbidden-path manifest checker."""

from pathlib import Path

import pytest

from scripts.check_main_forbidden_paths import ManifestError, find_violations, read_manifest

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


def _write_manifest(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "main-forbidden-paths.txt"
    path.write_text(content, encoding="utf-8")
    return path
