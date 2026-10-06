#!/usr/bin/env python3
"""Render a per-suite pytest summary from a JUnit XML report as Markdown.

Reads a pytest ``--junitxml`` report and prints, for every test file (suite),
a line of the form::

    tests/path/to/test_one.py: <succeeded>/<ran> (<n> skipped)

where ``ran`` counts tests that actually executed (total minus skipped) and
``succeeded`` is ``ran`` minus failures/errors. Paths are relative to the
project root (the ``file`` attribute pytest records). Intended to be appended
to ``$GITHUB_STEP_SUMMARY`` so results render cleanly on the workflow page.

Usage:
    pytest_summary.py <junit.xml>
"""
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict


def main(path: str) -> int:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as err:
        print("## Test results\n")
        print(f"> Could not read JUnit report `{path}`: {err}")
        print("> The test run likely failed before any results were recorded.")
        return 0

    # file -> counts. Aggregate per test file so each suite gets one line.
    stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "skipped": 0, "failed": 0}
    )
    for tc in root.iter("testcase"):
        # pytest records the project-root-relative path in `file`; fall back to
        # the dotted classname if it's ever missing.
        suite = tc.get("file") or tc.get("classname", "unknown").replace(".", "/") + ".py"
        s = stats[suite]
        s["total"] += 1
        if tc.find("skipped") is not None:
            s["skipped"] += 1
        elif tc.find("failure") is not None or tc.find("error") is not None:
            s["failed"] += 1

    lines = []
    tot_ran = tot_ok = tot_skipped = 0
    any_failed = False
    for suite in sorted(stats):
        s = stats[suite]
        ran = s["total"] - s["skipped"]
        ok = ran - s["failed"]
        tot_ran += ran
        tot_ok += ok
        tot_skipped += s["skipped"]
        marker = "  ❌" if s["failed"] else ""
        lines.append(f"{suite}: {ok}/{ran} ({s['skipped']} skipped){marker}")
        any_failed = any_failed or bool(s["failed"])

    print("## Test results\n")
    if not lines:
        print("> No test cases were found in the JUnit report.")
        return 0

    print("```")
    print("\n".join(lines))
    print("```")
    status = "❌ FAILED" if any_failed else "✅ PASSED"
    print(
        f"\n**{status}** — {tot_ok}/{tot_ran} passed"
        f" ({tot_skipped} skipped) across {len(lines)} suites."
    )
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: pytest_summary.py <junit.xml>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
