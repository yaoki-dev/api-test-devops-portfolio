"""Fail when the current Git tree still contains a main-forbidden path."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


class ManifestError(ValueError):
    """Represent a malformed forbidden-path manifest."""


@dataclass(frozen=True)
class ForbiddenPath:
    """Describe one exact path or directory-prefix rule from the manifest."""

    path: str
    is_directory: bool


def read_manifest(path: Path) -> tuple[ForbiddenPath, ...]:
    """Parse and validate a tracked forbidden-path manifest."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ManifestError(f"cannot read manifest {path}: {exc}") from exc

    rules: list[ForbiddenPath] = []
    seen: set[str] = set()
    for line_number, raw_line in enumerate(lines, start=1):
        entry = raw_line.strip()
        if not entry or entry.startswith("#"):
            continue

        is_directory = entry.endswith("/")
        normalized = entry[:-1] if is_directory else entry
        parts = normalized.split("/")
        if (
            not normalized
            or "\\" in entry
            or entry.startswith("/")
            or any(part in {"", ".", ".."} for part in parts)
        ):
            raise ManifestError(f"invalid path at line {line_number}: {raw_line!r}")
        if normalized in seen:
            raise ManifestError(f"duplicate path at line {line_number}: {normalized}")
        seen.add(normalized)
        rules.append(ForbiddenPath(normalized, is_directory))

    if not rules:
        raise ManifestError("manifest must contain at least one path")
    return tuple(rules)


def find_violations(tracked_paths: Iterable[str], rules: Iterable[ForbiddenPath]) -> list[str]:
    """Return tracked paths that match an exact or directory-prefix rule."""
    rule_list = tuple(rules)
    return sorted(
        path
        for path in tracked_paths
        if any(
            path == rule.path or (rule.is_directory and path.startswith(f"{rule.path}/"))
            for rule in rule_list
        )
    )


def _git_executable() -> str:
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("git executable was not found")
    return executable


def _git_root() -> Path:
    try:
        result = subprocess.run(
            [_git_executable(), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            cwd=Path.cwd(),
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"cannot determine Git root: {exc}") from exc
    root = result.stdout.strip()
    if not root:
        raise RuntimeError("Git returned an empty repository root")
    return Path(root)


def _tracked_paths(repo_root: Path) -> tuple[str, ...]:
    try:
        result = subprocess.run(
            [_git_executable(), "ls-tree", "-r", "--name-only", "-z", "HEAD"],
            check=True,
            capture_output=True,
            cwd=repo_root,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"cannot list tracked paths: {exc}") from exc
    return tuple(path for path in result.stdout.decode().split("\0") if path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default=".github/main-forbidden-paths.txt",
        help="manifest path relative to the repository root",
    )
    args = parser.parse_args(argv)

    try:
        repo_root = _git_root()
        rules = read_manifest(repo_root / args.manifest)
        violations = find_violations(_tracked_paths(repo_root), rules)
    except (ManifestError, RuntimeError) as exc:
        print(f"main forbidden-path check error: {exc}", file=sys.stderr)
        return 2

    if violations:
        print("main forbidden paths found:", file=sys.stderr)
        print("\n".join(f"- {path}" for path in violations), file=sys.stderr)
        return 1

    print(f"main forbidden-path check passed: {len(rules)} rules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
