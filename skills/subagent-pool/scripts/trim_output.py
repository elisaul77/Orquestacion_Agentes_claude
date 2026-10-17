#!/usr/bin/env python3
"""Shrink test/build output before a model reads it (subagent-pool v9.7).

    set -o pipefail; pytest 2>&1 | python3 trim_output.py [--context 3] [--max 80]

Keeps: failure/error lines with a few lines of context, tracebacks, assertion diffs and the final summary.
Drops: passing-test noise, progress dots, blank runs. If nothing looks like a failure, prints the last lines only.
Failure blocks (Traceback… / FAIL: / pytest `___ test ___` sections) and failure lines are never cut;
--max caps only context and other lines. Always prints a header with how much was dropped, so the reader knows the output was trimmed.
The pipeline's exit code is the test command's (pipefail); this filter always exits 0.
"""
import argparse
import re
import sys

SIGNAL = re.compile(
    r"(FAIL|ERROR|Error|Exception|Traceback|assert|AssertionError|panic|FATAL|✗|✖|×|"
    r"expected|Expected|received|Received|not ok|E   |\bfailed\b|\berror\b)"
)
SUMMARY = re.compile(
    r"((?<!\w)\d+ (passed|failed|errors?|skipped|tests?)\b|Ran \d+ tests?|^OK\b|^FAILED\b|Tests?:\s|"
    r"test result:|Test Suites?:|=+ .* =+$|^(PASS|FAIL)\s)",
    re.I,
)
NOISE = re.compile(r"^\s*$|^[.sxFE]+(\s+\[\s*\d+%\])?$|^\s*(PASSED|ok)\b|^\S+( \.\.\.)? (PASSED|ok)( \[\s*\d+%\])?$")


BLOCK_START = re.compile(r"^(Traceback|FAIL:|ERROR:|_{3,} .+ _{3,}$|=+ (FAILURES|ERRORS) =+$)")
BLOCK_END = re.compile(r"^(={10,}|_{3,} .+ _{3,}$)")  # next unittest block / pytest section; "-----" only before "Ran N"


RAN = re.compile(r"^Ran \d+ tests?")


def failure_blocks(lines):
    """Indices inside failure blocks: from a header/Traceback to the next separator. Kept whole, never capped."""
    inside, out = False, set()
    for i, line in enumerate(lines):
        if BLOCK_START.search(line):
            inside = True
        elif inside and BLOCK_END.search(line):
            inside = BLOCK_START.search(line) is not None
        elif inside and re.match(r"^-{10,}$", line) and i + 1 < len(lines) and RAN.search(lines[i + 1]):
            inside = False  # unittest closing rule; a dashed line inside a message keeps the block open
        if inside:
            out.add(i)
    return out


def trim(lines, context=3, max_lines=80):
    """Never drops a failure line: blocks and SIGNAL lines are protected; --max caps only the rest."""
    protected = failure_blocks(lines) | {i for i, l in enumerate(lines) if SIGNAL.search(l)}
    keep = set(protected)
    for i, line in enumerate(lines):
        if SIGNAL.search(line):
            keep.update(range(max(0, i - context), min(len(lines), i + context + 1)))
        elif SUMMARY.search(line):
            keep.add(i)
    if not any(SIGNAL.search(lines[i]) for i in keep):
        keep = set(range(max(0, len(lines) - 15), len(lines)))
    rest = sorted(i for i in keep - protected
                  if not (NOISE.search(lines[i]) and not SUMMARY.search(lines[i])))
    budget = max(0, max_lines - len(protected))
    if len(rest) > budget:  # cap only context lines; summaries survive first
        summ = [i for i in rest if SUMMARY.search(lines[i])]
        ctx = [i for i in rest if i not in summ]
        rest = summ + ctx[:max(0, budget - len(summ))]
    out, last = [], -2
    for i in sorted(protected | set(rest)):
        if i != last + 1 and out:
            out.append("  …")
        out.append(lines[i])
        last = i
    header = f"[trim_output] {len(lines)} lines → {len(out)} shown"
    return [header, *out]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--context", type=int, default=3)
    ap.add_argument("--max", type=int, default=80)
    args = ap.parse_args(argv)
    lines = sys.stdin.read().splitlines()
    print("\n".join(trim(lines, args.context, args.max)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
