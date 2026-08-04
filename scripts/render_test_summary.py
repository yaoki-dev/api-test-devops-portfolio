"""Render safe, bounded Markdown from pytest's JUnit XML output."""

import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Any

from defusedxml import ElementTree  # type: ignore[import-untyped]

MAX_IDENTIFIER_LENGTH = 300
MAX_IDENTIFIERS_PER_CATEGORY = 20
MAX_SUMMARY_BYTES = 64 * 1024
TRUNCATION_MARKER = "… [truncated]"
# Held back so the trailing omission line always fits within MAX_SUMMARY_BYTES.
# Its longest form, "- NN identifier(s) omitted due to summary size.", is 46 bytes.
OMISSION_LINE_RESERVE_BYTES = 96


@dataclass
class _SummaryStats:
    total: int = 0
    failures: int = 0
    errors: int = 0
    skipped: int = 0
    duration: float = 0.0
    failure_identifiers: list[str] = field(default_factory=list)
    error_identifiers: list[str] = field(default_factory=list)


def _local_name(element: Any) -> str:
    return str(element.tag).rsplit("}", 1)[-1]


def _count_attribute(element: Any, name: str) -> int | None:
    value = element.attrib.get(name)
    if value is None:
        return None
    try:
        return max(int(float(value)), 0)
    except TypeError:
        return 0
    except ValueError:
        return 0


def _duration_attribute(element: Any) -> float:
    value = element.attrib.get("time", "0")
    try:
        return max(float(value), 0.0)
    except TypeError:
        return 0.0
    except ValueError:
        return 0.0


def _test_cases(suite: Any) -> list[Any]:
    return [element for element in suite.iter() if _local_name(element) == "testcase"]


def _case_state(case: Any) -> str:
    child_names = {_local_name(child) for child in case}
    if "failure" in child_names:
        return "failure"
    if "error" in child_names:
        return "error"
    if "skipped" in child_names:
        return "skipped"
    return "passed"


def _escape_for_summary(text: str) -> str:
    """Escape for HTML and neutralize Markdown link syntax.

    GitHub Flavored Markdown keeps parsing Markdown inside raw inline HTML,
    so wrapping a value in ``<code>`` does not stop ``[label](url)`` from
    becoming a live link. ``html.escape`` leaves brackets untouched, so the
    brackets are replaced with numeric character references; they render back
    as literal ``[`` and ``]`` without reopening link syntax.
    """
    return escape(text, quote=True).replace("[", "&#91;").replace("]", "&#93;")


def _identifier(case: Any) -> str:
    classname = str(case.attrib.get("classname", ""))
    name = str(case.attrib.get("name", ""))
    if classname and name:
        value = f"{classname}::{name}"
    else:
        value = classname or name or "<unnamed test>"
    escaped = _escape_for_summary(value[:MAX_IDENTIFIER_LENGTH])
    if len(value) <= MAX_IDENTIFIER_LENGTH and len(escaped) <= MAX_IDENTIFIER_LENGTH:
        return escaped

    budget = MAX_IDENTIFIER_LENGTH - len(TRUNCATION_MARKER)
    prefix = value[:MAX_IDENTIFIER_LENGTH]
    while len(_escape_for_summary(prefix)) > budget:
        prefix = prefix[:-1]
    return f"{_escape_for_summary(prefix)}{TRUNCATION_MARKER}"


def _collect_stats(root: Any) -> _SummaryStats:
    if _local_name(root) == "testsuite":
        suites = [root]
    else:
        suites = [element for element in root if _local_name(element) == "testsuite"]
        if not suites:
            suites = [root]

    stats = _SummaryStats()
    for suite in suites:
        cases = _test_cases(suite)
        fallback_counts = {state: 0 for state in ("passed", "failure", "error", "skipped")}
        for case in cases:
            state = _case_state(case)
            fallback_counts[state] += 1
            if state == "failure":
                stats.failure_identifiers.append(_identifier(case))
            elif state == "error":
                stats.error_identifiers.append(_identifier(case))

        tests = _count_attribute(suite, "tests")
        failures = _count_attribute(suite, "failures")
        errors = _count_attribute(suite, "errors")
        skipped = _count_attribute(suite, "skipped")
        stats.total += tests if tests is not None else len(cases)
        if failures is None:
            failures = fallback_counts["failure"]
        if errors is None:
            errors = fallback_counts["error"]
        if skipped is None:
            skipped = fallback_counts["skipped"]
        stats.failures += failures
        stats.errors += errors
        stats.skipped += skipped
        stats.duration += _duration_attribute(suite)

    return stats


def _byte_length(lines: list[str]) -> int:
    return len(("\n".join(lines) + "\n").encode("utf-8"))


def _identifier_sections(stats: _SummaryStats, lines: list[str]) -> list[str]:
    categories = (
        ("Failed", stats.failure_identifiers),
        ("Errors", stats.error_identifiers),
    )
    for title, identifiers in categories:
        if not identifiers:
            continue
        lines.append(f"### {title} identifiers")
        count_omitted = max(len(identifiers) - MAX_IDENTIFIERS_PER_CATEGORY, 0)
        byte_omitted = 0
        for identifier in identifiers[:MAX_IDENTIFIERS_PER_CATEGORY]:
            item = f"- <code>{identifier}</code>"
            reserve = OMISSION_LINE_RESERVE_BYTES if count_omitted or byte_omitted else 0
            if _byte_length(lines + [item]) + reserve <= MAX_SUMMARY_BYTES:
                lines.append(item)
            else:
                byte_omitted += 1
        total_omitted = count_omitted + byte_omitted
        if total_omitted:
            suffix = " due to summary size" if byte_omitted else ""
            lines.append(f"- {total_omitted} identifier(s) omitted{suffix}.")
    return lines


def _empty_summary(message: str) -> str:
    return f"## Test Results\n\n{message}"


def render_junit_summary(xml_text: str) -> str:
    """Return bounded Markdown for valid, empty, or invalid JUnit XML."""
    if not xml_text.strip():
        return _empty_summary("No JUnit XML was generated.")

    try:
        root = ElementTree.fromstring(xml_text)
        stats = _collect_stats(root)
    except Exception:  # noqa: BLE001 - summary rendering must never fail CI
        return _empty_summary("Unable to parse JUnit XML.")

    passed = max(stats.total - stats.failures - stats.errors - stats.skipped, 0)
    lines = [
        "## Test Results",
        "",
        f"- Total: {stats.total}",
        f"- Passed: {passed}",
        f"- Failed: {stats.failures}",
        f"- Errors: {stats.errors}",
        f"- Skipped: {stats.skipped}",
        f"- Duration: {stats.duration:.2f}s",
    ]
    if stats.total == 0:
        lines.extend(["", "No tests were recorded."])
    _identifier_sections(stats, lines)
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Render the first XML path in ``argv`` without failing the CI job."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        print(_empty_summary("No JUnit XML was generated."))
        return 0

    try:
        xml_text = Path(arguments[0]).read_text(encoding="utf-8")
    except OSError:
        xml_text = ""
    except UnicodeError:
        xml_text = ""
    print(render_junit_summary(xml_text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
