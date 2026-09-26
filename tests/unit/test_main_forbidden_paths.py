"""Contracts for the main forbidden-path manifest checker."""

import posixpath
import re
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


# 無視パターンとレビュー対象の設定は両ブランチで同一に保つため除外する。
# manifest と本テストは、パスを名指しすること自体が役割である。
_REFERENCE_ALLOWLIST = frozenset(
    {
        ".coderabbit.yaml",
        ".github/main-forbidden-paths.txt",
        ".gitignore",
        ".textlintignore",
        "tests/unit/test_main_forbidden_paths.py",
    }
)
# インラインリンク `](x)` と参照形式の定義 `[id]: x` の両方からリンク先を取り出す。
_MARKDOWN_LINK = re.compile(r"(?:\]\(|^\s*\[[^\]]*\]:\s*)<?([^)\s#>]+)")


def _linked_paths(name: str, line: str) -> list[str]:
    if not name.endswith(".md"):
        return []
    base = posixpath.dirname(name)
    return [
        posixpath.normpath(posixpath.join(base, target))
        for target in _MARKDOWN_LINK.findall(line)
        if "://" not in target
    ]


@pytest.mark.repo_contract
def test_surviving_files_do_not_reference_forbidden_paths() -> None:
    repo_root = Path(__file__).parents[2]
    rules = read_manifest(repo_root / ".github/main-forbidden-paths.txt")
    git = shutil.which("git")
    assert git is not None, "git executable not found"
    listing = subprocess.run(  # noqa: S603
        [git, "ls-files", "-z"], capture_output=True, check=True, cwd=repo_root, text=True
    ).stdout
    tracked = [name for name in listing.split("\0") if name]
    surviving = set(tracked) - set(find_violations(tracked, rules)) - _REFERENCE_ALLOWLIST
    # ASCII の境界で `.ignore` が `.gitignore`・`.dockerignore` に一致するのを防ぎつつ、
    # 直後に文末のピリオドや日本語が続くパスも言及として検出する。
    mention = re.compile(
        "|".join(rf"(?<![\w.-]){re.escape(rule.path)}(?![\w-]|\.\w)" for rule in rules),
        re.ASCII,
    )

    offenders = []
    for name in sorted(surviving):
        path = repo_root / name
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(lines, 1):
            if mention.search(line) or find_violations(_linked_paths(name, line), rules):
                offenders.append(f"{name}:{lineno}")

    assert offenders == []


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
