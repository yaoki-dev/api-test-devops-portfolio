"""Tests for the JUnit XML to Job Summary renderer."""

from pathlib import Path

import pytest

from scripts.render_test_summary import main, render_junit_summary

pytestmark = pytest.mark.unit


def test_render_junit_summary_reports_passed_failed_errors_and_skipped() -> None:
    xml = """
    <testsuites>
      <testsuite tests="4" failures="1" errors="1" skipped="1" time="1.25">
        <testcase classname="tests.unit.test_ok" name="test_ok" />
        <testcase classname="tests.unit.test_failure" name="test_failure">
          <failure message="secret failure message">secret traceback</failure>
        </testcase>
        <testcase classname="tests.unit.test_error" name="test_error">
          <error message="secret error message">secret traceback</error>
        </testcase>
        <testcase classname="tests.unit.test_skip" name="test_skip">
          <skipped message="secret skip message" />
        </testcase>
      </testsuite>
    </testsuites>
    """

    summary = render_junit_summary(xml)

    assert "- Total: 4" in summary
    assert "- Passed: 1" in summary
    assert "- Failed: 1" in summary
    assert "- Errors: 1" in summary
    assert "- Skipped: 1" in summary
    assert "- Duration: 1.25s" in summary
    assert "<code>tests.unit.test_failure::test_failure</code>" in summary
    assert "<code>tests.unit.test_error::test_error</code>" in summary
    assert "secret" not in summary
    assert "traceback" not in summary


def test_render_junit_summary_aggregates_multiple_suites_and_keeps_errors_separate() -> None:
    xml = """
    <testsuites>
      <testsuite tests="2" failures="0" errors="1" skipped="0" time="0.50">
        <testcase classname="tests.unit.test_setup" name="setup">
          <error>setup traceback</error>
        </testcase>
        <testcase classname="tests.unit.test_pass" name="test_pass" />
      </testsuite>
      <testsuite tests="2" failures="1" errors="1" skipped="0" time="0.75">
        <testcase classname="tests.unit.test_teardown" name="teardown">
          <error>teardown traceback</error>
        </testcase>
        <testcase classname="tests.unit.test_failure" name="test_failure">
          <failure>failure traceback</failure>
        </testcase>
      </testsuite>
    </testsuites>
    """

    summary = render_junit_summary(xml)

    assert "- Total: 4" in summary
    assert "- Passed: 1" in summary
    assert "- Failed: 1" in summary
    assert "- Errors: 2" in summary
    assert "- Skipped: 0" in summary
    assert "- Duration: 1.25s" in summary
    assert "<code>tests.unit.test_setup::setup</code>" in summary
    assert "<code>tests.unit.test_teardown::teardown</code>" in summary
    assert "<code>tests.unit.test_failure::test_failure</code>" in summary
    assert "traceback" not in summary


def test_render_junit_summary_escapes_only_failure_and_error_identifiers() -> None:
    xml = """
    <testsuites>
      <testsuite tests="2" failures="1" errors="1" skipped="0">
        <testcase classname="pkg&lt;script&gt;" name="test&amp;bad&quot;id">
          <failure message="do not render">do not render</failure>
          <system-out>captured output</system-out>
          <system-err>captured error</system-err>
        </testcase>
        <testcase classname="pkg" name="test'error">
          <error message="do not render">do not render</error>
        </testcase>
      </testsuite>
    </testsuites>
    """

    summary = render_junit_summary(xml)

    assert "<code>pkg&lt;script&gt;::test&amp;bad&quot;id</code>" in summary
    assert "<code>pkg::test&#x27;error</code>" in summary
    assert "captured" not in summary
    assert "do not render" not in summary


def test_render_junit_summary_neutralizes_markdown_link_syntax() -> None:
    # GFM parses Markdown inside raw inline HTML, so <code> alone lets a
    # fork-authored identifier such as [label](url) render as a live link.
    xml = """
    <testsuites>
      <testsuite tests="1" failures="1" errors="0" skipped="0">
        <testcase classname="pkg" name="test_[click_here](https://evil.example)">
          <failure message="x">x</failure>
        </testcase>
      </testsuite>
    </testsuites>
    """

    summary = render_junit_summary(xml)

    assert "&#91;click_here&#93;" in summary
    assert "[click_here]" not in summary


def test_render_junit_summary_handles_empty_and_invalid_xml() -> None:
    empty_summary = render_junit_summary("")
    invalid_summary = render_junit_summary("<testsuites>")

    assert "No JUnit XML was generated." in empty_summary
    assert "Unable to parse JUnit XML." in invalid_summary


def test_render_junit_summary_limits_identifier_count_and_length() -> None:
    cases = "".join(
        f'<testcase classname="pkg" name="{("'x" * 175) + str(index)}"><failure /></testcase>'
        for index in range(25)
    )
    xml = f'<testsuites><testsuite tests="25" failures="25">{cases}</testsuite></testsuites>'

    summary = render_junit_summary(xml)

    assert summary.count("<code>") == 20
    assert "5 identifier(s) omitted." in summary
    assert "… [truncated]" in summary
    code_values = [
        line.split("<code>", 1)[1].split("</code>", 1)[0]
        for line in summary.splitlines()
        if "<code>" in line
    ]
    assert all(len(value) <= 300 for value in code_values)


def test_render_junit_summary_applies_utf8_summary_limit() -> None:
    apostrophe = "'"
    failed_cases = "".join(
        f'<testcase classname="pkg" name="{apostrophe * 300}{index}"><failure /></testcase>'
        for index in range(20)
    )
    error_cases = "".join(
        f'<testcase classname="pkg" name="{apostrophe * 300}{index}"><error /></testcase>'
        for index in range(20)
    )
    xml = (
        '<testsuites><testsuite tests="40" failures="20" errors="20">'
        f"{failed_cases}{error_cases}"
        "</testsuite></testsuites>"
    )

    summary = render_junit_summary(xml)

    assert len(summary.encode("utf-8")) <= 64 * 1024


@pytest.mark.parametrize(
    "content",
    [
        '<testsuites><testsuite tests="0" /></testsuites>',
        "",
        "<testsuites>",
        "<not-junit />",
    ],
    ids=["valid", "empty", "malformed", "empty-result"],
)
def test_main_returns_zero_for_non_renderable_xml(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], content: str
) -> None:
    xml_path = tmp_path / "junit.xml"
    xml_path.write_text(content, encoding="utf-8")

    assert main([str(xml_path)]) == 0
    assert capsys.readouterr().out


def test_main_returns_zero_for_missing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([str(tmp_path / "missing.xml")]) == 0
    assert "No JUnit XML was generated." in capsys.readouterr().out
