#!/usr/bin/env python3
"""Three-state proof of the bug2-orch seed (proof only; nothing here is mounted into a run).

    python3 competition/seed/proof/prove_bug2.py

For each tree (untouched kuNNA, seeded, seeded + decoy fix, seeded + real fix) it runs, in the bench image:
  - the visible symptom check (seed/proof/test_bug2_visible.py): the user's report, as a test
  - the bug2 hidden file (the headline) and the full regression suite against runs/_baseline
Output: runs/_proof/bug2-proof.json and a table on stdout.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent            # competition/seed/proof
COMP = HERE.parent.parent                         # competition/
sys.path.insert(0, str(COMP))
sys.dont_write_bytecode = True
import run as bench_run  # noqa: E402
import score  # noqa: E402

OUT = COMP / "runs" / "_proof"
SEED = COMP / "seed"


def build_tree(dest, sha, patches):
    """kuNNA at sha, git-initialised, seed first, then the patches (each relative to the seeded tree)."""
    if dest.exists():
        shutil.rmtree(dest)
    bench_run.copy_kunna_baseline(dest, sha)
    if patches and patches[0] == "seed":
        bench_run.apply_seed(dest, bench_run.SEED["bug2-orch"])
        patches = patches[1:]
    else:
        subprocess.run(bench_run.git("init", "-q", cwd=dest), check=True)
    for name in patches:
        subprocess.run(bench_run.git("apply", str(SEED / name), cwd=dest), check=True)
    return dest


def visible_check(tree, hidden_dir, proof_dir):
    uid, gid = os.getuid(), os.getgid()
    argv = ["docker", "run", "--rm", *bench_run.HARDENING, "--user", f"{uid}:{gid}",
            "-e", "KUNNA_ROOT=/work", "-e", "BUG2_HIDDEN=/hidden/test_bug2_hidden.py", "-e", "HOME=/tmp",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-v", f"{tree}:/work", "-v", f"{hidden_dir}:/hidden:ro", "-v", f"{proof_dir}:/proof:ro",
            "-w", "/work", bench_run.IMAGE, "python3", "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "-rA", "/proof/test_bug2_visible.py"]
    proc = subprocess.run(argv, capture_output=True, text=True)
    line = (proc.stdout.strip().splitlines() or ["no output"])[-1]
    return {"passed": proc.returncode == 0, "summary": line}


def measure(name, tree, baseline, work):
    score_dir = work / f"score-{name}"
    tree_copy, hidden_dir = score.prepare_tree(score_dir, tree)
    visible = visible_check(tree, hidden_dir, HERE)
    score.run_container_checks(score_dir, tree_copy, hidden_dir, os.getuid(), os.getgid())
    status = score.regression_statuses(score_dir)
    headline = score.hidden_result(score_dir, "bug2")
    regression = score.compare_to_baseline(status, baseline["checks"], target="bug2",
                                           cross=score.REGRESSION_CROSS["bug2-orch"])
    return {"tree": name, "visible_symptom_passes": visible["passed"], "visible_summary": visible["summary"],
            "hidden_bug2_passed": headline["passed"], "hidden_bug2_total": headline["total"],
            "hidden_bug2_failed_tests": sorted(k for k, v in headline["tests"].items() if v != "passed"),
            "regression_broken": regression["broken"], "regression_baseline_passing": regression["baseline_passing"],
            "regression_still_passing": regression["still_passing"]}


def main():
    baseline = json.loads(score.baseline_path().read_text(encoding="utf-8"))
    sha = baseline["kunna_sha"]
    OUT.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="bug2-proof-", dir=OUT))
    states = [("untouched", []), ("seeded", ["seed"]), ("decoy-fix", ["seed", "bug2-decoy-fix.patch"]),
              ("real-fix", ["seed", "bug2-real-fix.patch"])]
    results = []
    for name, patches in states:
        tree = build_tree(work / name, sha, patches)
        results.append(measure(name, tree, baseline, work))
        print(json.dumps(results[-1], ensure_ascii=False))
    (OUT / "bug2-proof.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for tree in work.iterdir():
        if tree.is_dir() and tree.name in dict(states):
            shutil.rmtree(tree)
    return 0


if __name__ == "__main__":
    sys.exit(main())
