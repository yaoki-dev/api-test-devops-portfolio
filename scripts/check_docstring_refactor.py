"""Check executable AST equivalence for docstring/comment-only refactors."""

from __future__ import annotations

import argparse
import ast
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


class CheckerError(Exception):
    """Represent an explicit checker input or source-processing error."""


_DOCSTRING_CONTAINERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
_FIXTURE_TODO_PATH = Path("scripts/fixture_docstring_todo.txt")
_FIXTURE_HEADER_PATTERN = re.compile(r"^-+ fixtures defined from (?P<owner>.+?) -+$")
_FIXTURE_OWNER_PATTERN = re.compile(r"^(?P<name>[A-Za-z_]\w*)\b.* -- (?P<source>.+)$")
_NO_FIXTURE_DOCSTRING = "no docstring available"


@dataclass(frozen=True)
class _FixtureInventory:
    undocumented: set[str]


@dataclass(frozen=True)
class _FixtureGateResult:
    exit_code: int
    message: str


def _required_executable(name: str, label: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise CheckerError(f"{label} error: {name} executable was not found")
    return executable


def _git_executable() -> str:
    return _required_executable("git", "Git")


def _uv_executable() -> str:
    return _required_executable("uv", "Fixture gate")


def _is_docstring(statement: ast.stmt) -> bool:
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    )


def _strip_docstrings(node: ast.AST) -> None:
    if isinstance(node, _DOCSTRING_CONTAINERS):
        body = node.body
        if body and _is_docstring(body[0]):
            node.body = body[1:] or [ast.Pass()]
        elif isinstance(node, ast.Module) and not body:
            node.body = [ast.Pass()]

    for child in ast.iter_child_nodes(node):
        _strip_docstrings(child)


def _normalized_dump(source: str, filename: str) -> str:
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        location = f"line {exc.lineno}" if exc.lineno is not None else "unknown line"
        raise CheckerError(f"Python parse error in {filename} at {location}: {exc.msg}") from exc

    _strip_docstrings(tree)
    return ast.dump(tree, include_attributes=False)


def _git_root() -> Path:
    try:
        git = _git_executable()
        result = subprocess.run(
            [git, "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            cwd=Path.cwd(),
            text=True,
        )
    except FileNotFoundError as exc:
        raise CheckerError("Git error: git executable was not found") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or "unable to determine the repository root"
        raise CheckerError(f"Git error: {detail}") from exc

    root = result.stdout.strip()
    if not root:
        raise CheckerError("Git error: repository root output was empty")
    return Path(root).resolve()


def _relative_path(repo_root: Path, path_text: str) -> tuple[str, Path]:
    candidate = Path(path_text)
    absolute = (candidate if candidate.is_absolute() else repo_root / candidate).resolve()
    try:
        relative = absolute.relative_to(repo_root)
    except ValueError as exc:
        raise CheckerError(f"Path error: {path_text} is outside the worktree") from exc

    if not absolute.is_file():
        raise CheckerError(f"Path error: changed file does not exist: {path_text}")
    return relative.as_posix(), absolute


def _git_source(repo_root: Path, base_ref: str, relative_path: str) -> str:
    if base_ref.startswith("-"):
        raise CheckerError("Argument error: base ref must not start with '-'")

    source_spec = f"{base_ref}:{relative_path}"
    try:
        git = _git_executable()
        result = subprocess.run(
            [git, "show", source_spec],
            check=True,
            capture_output=True,
            cwd=repo_root,
            text=True,
        )
    except FileNotFoundError as exc:
        raise CheckerError("Git error: git executable was not found") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or "unable to read the base source"
        raise CheckerError(f"Git error: git show {source_spec} failed: {detail}") from exc
    except UnicodeError as exc:
        raise CheckerError(f"Git error: base source is not valid UTF-8: {source_spec}") from exc
    return result.stdout


def _worktree_source(path: Path, display_path: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CheckerError(f"Path error: cannot read changed file {display_path}: {exc}") from exc
    except UnicodeError as exc:
        message = f"Python error: changed file is not valid UTF-8: {display_path}"
        raise CheckerError(message) from exc


def _equivalent(before: str, after: str, path: str) -> bool:
    before_dump = _normalized_dump(before, f"{path} (base)")
    after_dump = _normalized_dump(after, f"{path} (worktree)")
    return before_dump == after_dump


def _check_files(base_ref: str, paths: list[str]) -> int:
    try:
        repo_root = _git_root()
    except CheckerError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    failed = False
    for path_text in paths:
        try:
            relative, absolute = _relative_path(repo_root, path_text)
            before = _git_source(repo_root, base_ref, relative)
            after = _worktree_source(absolute, relative)
            if _equivalent(before, after, relative):
                print(f"{relative}: OK")
            else:
                print(f"{relative}: DIFF")
                failed = True
        except CheckerError as exc:
            print(f"{path_text}: ERROR: {exc}", file=sys.stderr)
            failed = True
    return 1 if failed else 0


def _is_tests_fixture_owner(owner: str | None, source: str) -> bool:
    normalized_owner = _normalize_fixture_source(owner) if owner is not None else ""
    normalized_source = _normalize_fixture_source(source)
    owner_is_tests_fixture = normalized_owner.startswith(("tests/", "tests."))
    return owner_is_tests_fixture and normalized_source.startswith("tests/")


def _normalize_fixture_source(source: str) -> str:
    normalized = source.replace("\\", "/")
    normalized = re.sub(r"/+", "/", normalized)
    normalized = re.sub(r":\d+(?::\d+)?$", "", normalized)
    tests_marker = "/tests/"
    if tests_marker in normalized:
        return "tests/" + normalized.split(tests_marker, 1)[1]
    return normalized


def _parse_fixture_docstrings(output: str) -> _FixtureInventory:
    owner: str | None = None
    current_name: str | None = None
    current_identifier: str | None = None
    current_is_tests_fixture = False
    undocumented: set[str] = set()

    for line in output.splitlines():
        header = _FIXTURE_HEADER_PATTERN.match(line)
        if header is not None:
            owner = header.group("owner")
            current_name = None
            current_identifier = None
            current_is_tests_fixture = False
            continue

        fixture = _FIXTURE_OWNER_PATTERN.match(line)
        if fixture is not None:
            current_name = fixture.group("name")
            source = fixture.group("source")
            current_identifier = f"{_normalize_fixture_source(source)}::{current_name}"
            current_is_tests_fixture = _is_tests_fixture_owner(owner, source)
            continue

        if current_is_tests_fixture and current_name and line.strip():
            if line.strip() == _NO_FIXTURE_DOCSTRING:
                undocumented.add(current_identifier or current_name)
            current_name = None
            current_identifier = None
            current_is_tests_fixture = False

    return _FixtureInventory(undocumented=undocumented)


def _read_fixture_allowlist(path: Path) -> set[str]:
    try:
        return {
            line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
        }
    except OSError as exc:
        raise CheckerError(f"Fixture gate error: cannot read allowlist {path}: {exc}") from exc


def _evaluate_fixture_gate(
    inventory: _FixtureInventory,
    allowlist_path: Path,
) -> _FixtureGateResult:
    allowlist = _read_fixture_allowlist(allowlist_path)
    missing = sorted(inventory.undocumented - allowlist)
    stale = sorted(allowlist - inventory.undocumented)
    failures: list[str] = []

    if missing:
        failures.append(f"missing undocumented fixture allowlist entries: {', '.join(missing)}")
    if stale:
        failures.append(f"stale fixture allowlist entries: {', '.join(stale)}")
    if failures:
        return _FixtureGateResult(exit_code=1, message="\n".join(failures))

    return _FixtureGateResult(
        exit_code=0,
        message=(
            f"fixture gate OK: {len(inventory.undocumented)} allowlisted undocumented fixtures"
        ),
    )


def _run_fixture_gate() -> int:
    try:
        repo_root = _git_root()
        uv = _uv_executable()
        result = subprocess.run(
            [uv, "run", "pytest", "--fixtures", "-v", "--no-header"],
            check=False,
            capture_output=True,
            cwd=repo_root,
            text=True,
        )
    except CheckerError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except FileNotFoundError:
        print("Fixture gate error: uv executable was not found", file=sys.stderr)
        return 1

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "pytest --fixtures failed"
        print(f"Fixture gate error: {detail}", file=sys.stderr)
        return 1

    try:
        gate = _evaluate_fixture_gate(
            _parse_fixture_docstrings(result.stdout),
            repo_root / _FIXTURE_TODO_PATH,
        )
    except CheckerError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    stream = sys.stderr if gate.exit_code else sys.stdout
    print(gate.message, file=stream)
    return gate.exit_code


def _fixture_gate_self_test() -> bool:
    output = r"""
--------- fixtures defined from tests.unit.test_sample ---------
documented_fixture -- tests/unit/test_sample.py:10
    A documented fixture.
posix_undocumented_fixture -- /repo/tests/unit/test_sample.py:20
    no docstring available
--------- fixtures defined from C:\repo\tests\unit\test_sample.py ---------
windows_undocumented_fixture -- C:\repo\tests\unit\test_sample.py:30
    no docstring available
"""
    inventory = _parse_fixture_docstrings(output)
    undocumented = {
        "tests/unit/test_sample.py::posix_undocumented_fixture",
        "tests/unit/test_sample.py::windows_undocumented_fixture",
    }
    if inventory.undocumented != undocumented:
        return False

    with tempfile.TemporaryDirectory() as directory:
        allowlist_path = Path(directory) / "fixture_docstring_todo.txt"
        allowlist_path.write_text("\n".join(undocumented) + "\n", encoding="utf-8")
        if _evaluate_fixture_gate(inventory, allowlist_path).exit_code != 0:
            return False

        allowlist_path.write_text("tests/stale.py::stale_fixture\n", encoding="utf-8")
        result = _evaluate_fixture_gate(inventory, allowlist_path)
        return (
            result.exit_code == 1
            and "missing undocumented fixture allowlist entries" in result.message
            and "stale fixture allowlist entries" in result.message
        )


def _self_test() -> int:
    cases: tuple[tuple[str, str, str, bool], ...] = (
        (
            "ordinary docstring compression + comment removal",
            '''
"""Detailed module documentation."""

def test_value() -> None:
    """Explain the assertion."""
    # This comment is intentionally removed.
    assert 1 == 1
''',
            '''
"""Short module documentation."""

def test_value() -> None:
    assert 1 == 1
''',
            True,
        ),
        (
            "docstring-only body -> Pass",
            '''
def test_placeholder() -> None:
    """Explain why this test remains."""
''',
            """
def test_placeholder() -> None:
    pass
""",
            True,
        ),
        (
            "assert value change",
            '''
def test_value() -> None:
    """Explain the assertion."""
    assert 1 == 1
''',
            """
def test_value() -> None:
    assert 1 == 2
""",
            False,
        ),
        (
            "assert deletion",
            '''
def test_value() -> None:
    """Explain the assertion."""
    assert 1 == 1
''',
            '''
def test_value() -> None:
    """The body is now docstring-only."""
''',
            False,
        ),
        (
            "test function rename",
            '''
def test_original() -> None:
    """Explain the assertion."""
    assert 1 == 1
''',
            """
def test_renamed() -> None:
    assert 1 == 1
""",
            False,
        ),
    )

    positive_passed = 0
    negative_passed = 0
    # Derive totals from the case list so an added case that fails cannot
    # silently pass by matching a stale hardcoded total.
    positive_total = sum(1 for case in cases if case[3])
    negative_total = len(cases) - positive_total
    for name, before, after, expected_equal in cases:
        try:
            equivalent = _equivalent(before, after, f"self-test: {name}")
            if name == "docstring-only body -> Pass":
                module_only_equivalent = _equivalent(
                    '"""Module-only documentation."""',
                    "",
                    "self-test: module-only docstring -> empty module",
                )
                equivalent = equivalent and module_only_equivalent
        except CheckerError as exc:
            print(f"{name}: ERROR: {exc}", file=sys.stderr)
            continue

        passed = equivalent == expected_equal
        label = "positive" if expected_equal else "negative"
        result = "OK" if passed else "FAIL"
        print(f"{label}: {name}: {result}")
        if passed:
            if expected_equal:
                positive_passed += 1
            else:
                negative_passed += 1

    print(f"positive {positive_passed}/{positive_total}")
    print(f"negative {negative_passed}/{negative_total}")
    fixture_gate_passed = _fixture_gate_self_test()
    print(f"fixture gate self-test: {'OK' if fixture_gate_passed else 'FAIL'}")
    return (
        0
        if positive_passed == positive_total
        and negative_passed == negative_total
        and fixture_gate_passed
        else 1
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check executable AST equivalence for docstring/comment-only refactors."
    )
    parser.add_argument("base_ref", nargs="?")
    parser.add_argument("changed_files", nargs="*")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--fixture-gate", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test and args.fixture_gate:
        print("Argument error: choose only one checker mode", file=sys.stderr)
        return 1

    if args.self_test:
        if args.base_ref is not None or args.changed_files:
            print("Argument error: --self-test does not accept file arguments", file=sys.stderr)
            return 1
        return _self_test()

    if args.fixture_gate:
        if args.base_ref is not None or args.changed_files:
            print("Argument error: --fixture-gate does not accept file arguments", file=sys.stderr)
            return 1
        return _run_fixture_gate()

    if args.base_ref is None or not args.changed_files:
        print("Argument error: expected <BASE_REF> and at least one changed file", file=sys.stderr)
        return 1
    return _check_files(args.base_ref, args.changed_files)


if __name__ == "__main__":
    raise SystemExit(main())
