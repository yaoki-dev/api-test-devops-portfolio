"""Check executable AST equivalence for docstring/comment-only refactors."""

from __future__ import annotations

import argparse
import ast
import shutil
import subprocess
import sys
from pathlib import Path


class CheckerError(Exception):
    """Represent an explicit checker input or source-processing error."""


_DOCSTRING_CONTAINERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def _git_executable() -> str:
    executable = shutil.which("git")
    if executable is None:
        raise CheckerError("Git error: git executable was not found")
    return executable


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
    positive_total = 2
    negative_total = 3
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
    return 0 if positive_passed == positive_total and negative_passed == negative_total else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check executable AST equivalence for docstring/comment-only refactors."
    )
    parser.add_argument("base_ref", nargs="?")
    parser.add_argument("changed_files", nargs="*")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        if args.base_ref is not None or args.changed_files:
            print("Argument error: --self-test does not accept file arguments", file=sys.stderr)
            return 1
        return _self_test()

    if args.base_ref is None or not args.changed_files:
        print("Argument error: expected <BASE_REF> and at least one changed file", file=sys.stderr)
        return 1
    return _check_files(args.base_ref, args.changed_files)


if __name__ == "__main__":
    raise SystemExit(main())
