#!/usr/bin/env python3
"""Tiny mutation tester, no dependencies (subagent-pool v9.7).

    python3 mutate.py TARGET.py [--root DIR] [--tests DIR] [--pattern 'test_x.py'] [--limit N]

Copies --root (default: the target's directory; use a parent when tests read sibling folders) to a temp dir, then one mutation at a time (comparison flipped, + ↔ -, and ↔ or,
True ↔ False, a constant n → n+1) runs `python3 -B -m unittest discover -s <tests in the copy> -p <pattern>`. A mutant that no test catches
"survives": the tests don't guard that line. The original files are never touched.
Skips `def main()` (CLI wiring). Prints a score and the survivors with line numbers. Exit 1 if any mutant survives.
"""
import argparse
import ast
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SWAP = {ast.Lt: ast.GtE, ast.GtE: ast.Lt, ast.Gt: ast.LtE, ast.LtE: ast.Gt, ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
        ast.Add: ast.Sub, ast.Sub: ast.Add, ast.And: ast.Or, ast.Or: ast.And}


def sites(tree):
    """(index, line, description) for every mutable node, in a stable walk order."""
    out, skip = [], set()
    for f in ast.walk(tree):  # CLI wiring (argparse defaults) is noise, not logic
        if isinstance(f, ast.FunctionDef) and f.name == "main":
            skip.update(id(x) for x in ast.walk(f))
    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        if isinstance(node, ast.Compare):
            out += [(node, i, type(op).__name__) for i, op in enumerate(node.ops) if type(op) in SWAP]
        elif isinstance(node, (ast.BinOp, ast.BoolOp)) and type(node.op) in SWAP:
            out.append((node, None, type(node.op).__name__))
        elif isinstance(node, ast.Constant) and type(node.value) in (bool, int) and not isinstance(node.value, str):
            out.append((node, None, repr(node.value)))
    return out


def mutate(source, k):
    tree = ast.parse(source)
    node, i, desc = sites(tree)[k]
    if isinstance(node, ast.Compare):
        node.ops[i] = SWAP[type(node.ops[i])]()
    elif isinstance(node, (ast.BinOp, ast.BoolOp)):
        node.op = SWAP[type(node.op)]()
    elif isinstance(node.value, bool):
        node.value = not node.value
    else:
        node.value += 1
    return ast.unparse(tree), node.lineno, desc


def pick(n, limit):
    """Evenly spread indices, at most `limit` of them (0 = all)."""
    if not limit or limit >= n:
        return list(range(n))
    return sorted({i * n // limit for i in range(limit)})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("target")
    ap.add_argument("--root", help="tree to copy (default: target's directory)")
    ap.add_argument("--tests", help="directory to run unittest discover in (default: target's directory)")
    ap.add_argument("--pattern", default="test*.py", help="only these test files, e.g. test_instincts.py")
    ap.add_argument("--limit", type=int, default=0, help="test at most N mutants (0 = all)")
    ap.add_argument("--timeout", type=int, default=60)
    args = ap.parse_args(argv)
    target = Path(args.target).resolve()
    root = Path(args.root).resolve() if args.root else target.parent
    tests_rel = (Path(args.tests).resolve() if args.tests else target.parent).relative_to(root)
    source = target.read_text()
    n = len(sites(ast.parse(source)))
    if args.limit < 0:
        ap.error("--limit must be >= 0")
    picks = pick(n, args.limit)
    survivors, killed = [], 0
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "work"
        shutil.copytree(root, copy, ignore=shutil.ignore_patterns("__pycache__", ".git"))
        mutant_path = copy / target.relative_to(root)
        cmd = [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(copy / tests_rel), "-t", str(copy), "-p", args.pattern]
        env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(copy / tests_rel), str(copy)])}
        run = dict(capture_output=True, cwd=copy, env=env)  # imports and relative writes stay inside the copy
        try:
            base = subprocess.run(cmd, timeout=args.timeout * 3, **run)
        except subprocess.TimeoutExpired:
            print("baseline tests hang — raise --timeout or narrow --pattern")
            return 2
        if base.returncode != 0:
            print("baseline tests fail — fix them before mutation testing")
            return 2
        for k in picks:
            code, line, desc = mutate(source, k)
            mutant_path.write_text(code)
            try:
                r = subprocess.run(cmd, timeout=args.timeout, **run)
                caught = r.returncode != 0
            except subprocess.TimeoutExpired:
                caught = True  # a hang is a detected change
            killed += caught
            if not caught:
                survivors.append(f"{target.name}:{line} — {desc} mutated, no test failed")
        mutant_path.write_text(source)
    total = killed + len(survivors)
    print(f"mutation score: {killed}/{total} killed" + (f" ({100 * killed // total} %)" if total else ""))
    for s in survivors:
        print("  survived:", s)
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main())
