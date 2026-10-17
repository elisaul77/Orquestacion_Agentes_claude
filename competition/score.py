#!/usr/bin/env python3
"""Score bench runs and prepare blind judging.

    python3 competition/score.py score runs/<id> [runs/<id> ...] [--no-docker]
        -> runs/<id>/score.json  (hidden tests, regression suite, tokens, orchestration facts)
    python3 competition/score.py baseline [--force] [--kunna-ref REF]   (once per kuNNA sha: regression checks)
    python3 competition/score.py blind runs/<id> [runs/<id> ...]
        -> blind/<blind-id>/ (anonymized patch, final message, prompt) + runs/blind_key.json

Hidden tests: BOTH hidden files run in every run (copied into runs/<id>/score/ only here, never before the
run). The target round's file is the headline; the other file's results count as regression.
Regression checks and hidden tests run inside the bench image against a scratch copy of the run's kuNNA tree.
A run is only compared with a baseline built from the same kuNNA commit (kunna_sha).
Token counts reuse the repo's cost_tracker.usage_by_model (from the run's own skillrepo snapshot).
"""
import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import run as bench_run  # same directory, stdlib only: pins, sandbox flags, credential-free helpers

HERE = Path(__file__).resolve().parent
IMAGE = os.environ.get("KUNNA_BENCH_IMAGE", "kunna-bench:1")
HIDDEN_DIR = HERE / "hidden"
HIDDEN_FILES = {"bug": "test_bug_hidden.py", "improve": "test_improve_hidden.py"}
PY_FILES = ("backend/app.py", "backend/auth.py", "backend/netmap.py", "backend/caretaker.py",
            "backend/agent_manager.py", "backend/ssh_deployer.py", "monitor/docker_monitor.py", "agent/agent.py")
SUBAGENT_TOOLS = ("Task", "Agent")
TEAM_TOOLS = ("TeamCreate", "SendMessage")
TRIAGE_RE = re.compile(r"\bTier\s+[SML]\b\s*[·•-]")          # tier line: "Tier M · bug · ..." (any of · • - as separator)
REROUTE_RE = re.compile(r"\bre-?rout", re.IGNORECASE)
RISKY_RE = re.compile(r"git\s+push|docker\s+(rm|push|system\s+prune)|\brm\s+-[a-z]*r|git\s+reset\s+--hard|"
                      r"kubectl\s+delete|\bdeploy\b|--force\b|DELETE\s+/|curl\s+.*-X\s*DELETE", re.IGNORECASE)
# Lines that name the system's internals (phases, roles, workflow vocabulary): removed whole, never edited
DROP_LINE_PATTERNS = [re.compile(p, re.IGNORECASE) for p in (
    r"\bTier\s+[SML]\b", r"FAILURE_ORIGIN", r"case file", r"re-?rout", r"admission", r"triage",
    r"diagnos\w*", r"council", r"STATUS:\s*(APPROVED|NEEDS_REVISION|FAILED)", r"plans/\S+",
)]
LINE_REMOVED = "[line removed]"
# Names that identify the system under test or the models; whole words only, replaced in what remains
ANON_TERMS = [
    "planning-agent", "implement-agent", "review-agent", "AgentArchitect", "council-spec", "council-architect",
    "council-lateral", "council-risk", "codex-agent", "subagent-pool", "arquitec-dev-ia", "graphify",
    "Conductor", "conductor", "Claude Code", "Codex CLI", "Claude", "Codex", "Anthropic", "OpenAI",
    "Haiku", "Sonnet", "Opus", "GPT",
]
ANON_PATTERNS = [
    (re.compile(r"\bv?9\.\d{1,2}\.\d{1,2}\b"), "vX.Y.Z"),          # subagent-pool versions
    (re.compile(r"\b2\.1\.302\b|\b0\.160\.0\b"), "X.Y.Z"),          # host CLI versions
    (re.compile(r"^.*(Co-Authored-By|Generated with|🤖).*$\n?", re.MULTILINE), ""),  # signatures
    (re.compile(r"\.claude/|\.codex/"), "<tool-dir>/"),
]


# ---------- transcript facts ----------

def load_records(path):
    recs = []
    if not Path(path).is_file():
        return recs
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            recs.append(rec)
    return recs


def assistant_blocks(records):
    """Yield (block, record) for every content block of every assistant message."""
    for rec in records:
        msg = rec.get("message")
        if rec.get("type") != "assistant" or not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict):
                yield block, rec


def transcript_facts(records):
    """Orchestration facts from stream-json records (pure function, unit-tested)."""
    subagents, reviews, reroutes, triage, council, risky, final_text = Counter(), 0, 0, None, False, [], None
    for block, rec in assistant_blocks(records):
        kind = block.get("type")
        if kind == "tool_use":
            name, inp = block.get("name", ""), block.get("input") or {}
            if name in SUBAGENT_TOOLS:
                stype = str(inp.get("subagent_type") or "general")
                subagents[stype] += 1
                if stype == "review-agent":
                    reviews += 1
                if stype.startswith("council-"):
                    council = True
            elif name in TEAM_TOOLS:
                council = True
            if name == "Bash" and RISKY_RE.search(str(inp.get("command", ""))):
                risky.append({"tool": name, "command": str(inp.get("command", ""))[:200]})
        elif kind == "text":
            text = block.get("text", "")
            if triage is None:
                for line in text.splitlines():
                    if TRIAGE_RE.search(line):
                        triage = line.strip()[:300]
                        break
            reroutes += len(REROUTE_RE.findall(text))
            if not rec.get("parent_tool_use_id") and text.strip():
                final_text = text
    return {"subagents": dict(subagents), "review_rounds": reviews, "reroute_mentions": reroutes,
            "triage": triage, "council_convened": council, "risky_actions": risky,
            "final_text": final_text}


def final_result(records):
    """The last `result` record of the stream: total_cost_usd and usage, as a cross-check of the session totals."""
    last = None
    for rec in records:
        if rec.get("type") == "result":
            last = rec
    if last is None:
        return {"present": False}
    return {"present": True, "total_cost_usd": last.get("total_cost_usd"), "usage": last.get("usage"),
            "num_turns": last.get("num_turns"), "is_error": last.get("is_error")}


def diff_stats(diff_text):
    files = sum(1 for l in diff_text.splitlines() if l.startswith("diff --git "))
    ins = sum(1 for l in diff_text.splitlines() if l.startswith("+") and not l.startswith("+++"))
    dele = sum(1 for l in diff_text.splitlines() if l.startswith("-") and not l.startswith("---"))
    return {"files": files, "insertions": ins, "deletions": dele}


def load_cost_tracker(run_dir):
    path = run_dir / "skillrepo" / "skills" / "subagent-pool" / "scripts" / "cost_tracker.py"
    spec = importlib.util.spec_from_file_location("bench_cost_tracker", path)
    module = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    spec.loader.exec_module(module)
    return module


def token_usage(run_dir):
    """Per-model tokens from the Claude session files (main + subagents). Falls back to the stream."""
    cost = load_cost_tracker(run_dir)
    sessions = sorted((run_dir / "sessions").rglob("*.jsonl")) if (run_dir / "sessions").is_dir() else []
    source = "sessions"
    if not sessions and (run_dir / "transcript.jsonl").is_file():
        sessions, source = [run_dir / "transcript.jsonl"], "stream-fallback"
    by_model = cost.usage_by_model([str(p) for p in sessions])
    total = {k: sum(m[k] for m in by_model.values()) for k in ("input", "output", "cache_write", "cache_read")}
    return {"source": source, "by_model": by_model, "total": total}


def codex_usage(run_dir):
    """Codex rollouts: event_msg/token_count carries a cumulative info.total_token_usage; the last one per file is the session total.

    Format seen on the host (Codex desktop rollouts). If a file has no token_count, it is not counted.
    """
    root = run_dir / "codex_sessions"
    files = sorted(root.rglob("*.jsonl")) if root.is_dir() else []
    if not files:
        return {"status": "not counted: no codex session files in the run"}
    totals, with_usage = Counter(), 0
    for f in files:
        last = None
        for rec in load_records(f):
            payload = rec.get("payload")
            if rec.get("type") == "event_msg" and isinstance(payload, dict) and payload.get("type") == "token_count":
                info = payload.get("info") or {}
                if isinstance(info.get("total_token_usage"), dict):
                    last = info["total_token_usage"]
        if last is not None:
            with_usage += 1
            totals.update({k: v for k, v in last.items() if isinstance(v, int)})
    if with_usage == 0:
        return {"status": f"not counted: {len(files)} codex file(s) without token_count records", "files": len(files)}
    return {"status": "counted", "files": len(files), "files_with_usage": with_usage, "total": dict(totals)}


# ---------- hidden tests and regression (in the bench image) ----------

def container_script():
    """Runs inside the bench image. Every check writes a raw result; the host turns them into statuses.

    CJS suites (they use require): ESM sources transformed by the pinned babel plugin, node environment
    (the tests build their own JSDOM). ESM suites (import / dynamic import / top-level await): native ESM,
    jsdom environment; package.json {"type":"module"} is written into the scratch tree only, after the CJS phase.
    """
    return r"""set -u
mkdir -p /bench/score/home
R=/bench/score/regression.txt
: > $R
python3 -m py_compile """ + " ".join(PY_FILES) + r""" > /bench/score/py_compile.log 2>&1
echo "py_compile $?" >> $R
CJS='{"rootDir":"/work","testEnvironment":"node","transform":{"\\.js$":["babel-jest",{"babelrc":false,"configFile":false,"plugins":["/usr/local/lib/node_modules/@babel/plugin-transform-modules-commonjs"]}]}}'
ESM='{"rootDir":"/work","testEnvironment":"jsdom","transform":{}}'
for f in /work/frontend/__tests__/*.test.js; do
  grep -q "require(" "$f" || continue
  n="$(basename "$f" .test.js)"
  jest --config "$CJS" --watchman=false --json --outputFile="/bench/score/js_$n.json" "$f" > "/bench/score/js_$n.log" 2>&1
  echo "js_$n $?" >> $R
done
echo '{"type":"module"}' > /work/package.json
export NODE_OPTIONS=--experimental-vm-modules
for f in /work/frontend/__tests__/*.test.js; do
  grep -q "require(" "$f" && continue
  n="$(basename "$f" .test.js)"
  jest --config "$ESM" --watchman=false --json --outputFile="/bench/score/js_$n.json" "$f" > "/bench/score/js_$n.log" 2>&1
  echo "js_$n $?" >> $R
done
for name in bug improve; do
  python3 -m pytest -q -p no:cacheprovider --junit-xml="/bench/score/hidden_$name.xml" "/hidden/test_${name}_hidden.py" > "/bench/score/hidden_$name.log" 2>&1
  echo "hidden_$name $?" >> $R
done
exit 0
"""


def prepare_tree(score_dir, source):
    """Scratch copy of a kuNNA tree (the agent's copy is never touched), plus BOTH hidden tests."""
    if score_dir.exists():
        shutil.rmtree(score_dir)
    tree, hidden_dir = score_dir / "tree", score_dir / "hidden"
    shutil.copytree(source, tree, ignore=shutil.ignore_patterns(".git"))
    hidden_dir.mkdir(parents=True)
    for fname in HIDDEN_FILES.values():
        shutil.copy2(HIDDEN_DIR / fname, hidden_dir / fname)
    return tree, hidden_dir


def run_container_checks(score_dir, tree, hidden_dir, uid, gid):
    argv = ["docker", "run", "--rm", *bench_run.HARDENING, "--user", f"{uid}:{gid}",
            "-e", "KUNNA_ROOT=/work", "-e", "HOME=/bench/score/home", "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-v", f"{tree}:/work", "-v", f"{hidden_dir}:/hidden:ro", "-v", f"{score_dir}:/bench/score",
            "-w", "/work", IMAGE, "bash", "-c", container_script()]
    proc = subprocess.run(argv, capture_output=True, text=True)
    (score_dir / "docker.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        raise SystemExit(f"scoring container failed (rc {proc.returncode}): see {score_dir / 'docker.log'}")


def jest_statuses(path, prefix):
    """{prefix::full test name: passed|failed|...}; a suite that does not run becomes prefix::<suite>."""
    out = {}
    for suite in json.loads(Path(path).read_text(encoding="utf-8")).get("testResults", []):
        results = suite.get("assertionResults") or []
        if not results:
            out[f"{prefix}::<suite>"] = "passed" if suite.get("status") == "passed" else "failed"
        for a in results:
            out[f"{prefix}::{a.get('fullName', '')}"] = "passed" if a.get("status") == "passed" else "failed"
    return out


def regression_statuses(score_dir):
    """Every check as {id: passed|failed}, from the raw files written in the container.

    Ids: py_compile, js_<suite> (exit code), <suite>::<test>, hidden_<round> (exit code), hidden_<round>::<test>.
    """
    status = {}
    for line in (score_dir / "regression.txt").read_text().splitlines():
        name, rc = line.rsplit(" ", 1)
        status[name] = "passed" if rc == "0" else "failed"
    for jf in sorted(score_dir.glob("js_*.json")):
        status.update(jest_statuses(jf, jf.stem[3:]))
    for name in HIDDEN_FILES:
        xml = score_dir / f"hidden_{name}.xml"
        if xml.is_file():
            for test, st in junit_tests(xml).items():
                status[f"hidden_{name}::{test}"] = "passed" if st == "passed" else "failed"
    return status


def in_scope(check_id, target):
    """The target round's hidden file is the headline, not part of the regression set."""
    if target is None:
        return True
    return not (check_id == f"hidden_{target}" or check_id.startswith(f"hidden_{target}::"))


def compare_to_baseline(run_status, base_status, target=None):
    """Regression = a check that passes on untouched kuNNA and does not pass in this run."""
    passing = sorted(k for k, v in base_status.items() if v == "passed" and in_scope(k, target))
    broken = [k for k in passing if run_status.get(k) != "passed"]
    return {"baseline_passing": len(passing), "still_passing": len(passing) - len(broken),
            "broken": broken, "ok": not broken,
            "non_target_hidden": None if target is None else f"hidden_{'improve' if target == 'bug' else 'bug'}"}


def hidden_result(score_dir, name):
    hidden = {"file": HIDDEN_FILES[name], "tests": {}, "total": 0, "passed": 0}
    xml = score_dir / f"hidden_{name}.xml"
    if xml.is_file():
        hidden["tests"] = junit_tests(xml)
        hidden["total"] = len(hidden["tests"])
        hidden["passed"] = sum(1 for s in hidden["tests"].values() if s == "passed")
    hidden["ok"] = hidden["total"] > 0 and hidden["passed"] == hidden["total"]
    return hidden


def junit_tests(path):
    """{test name: passed|failed|error|skipped} from a pytest junit file."""
    out = {}
    for case in ET.parse(path).iter("testcase"):
        name = f"{case.get('classname', '')}::{case.get('name', '')}"
        status = "passed"
        for child in case:
            if child.tag in ("failure", "error", "skipped"):
                status = {"failure": "failed", "error": "error", "skipped": "skipped"}[child.tag]
        out[name] = status
    return out


def require_same_kunna(baseline, meta):
    """A regression comparison is only meaningful against a baseline built from the same kuNNA commit."""
    base_sha, run_sha = baseline.get("kunna_sha"), meta.get("kunna_sha")
    if not base_sha or base_sha != run_sha:
        raise SystemExit(f"kuNNA pin mismatch: baseline {base_sha} != run {run_sha}. Rebuild the baseline at the "
                         f"run's commit: python3 competition/score.py baseline --force --kunna-ref {run_sha}")


def baseline_path():
    return HERE / "runs" / "_baseline" / "baseline.json"


def make_baseline(no_docker=False, force=False, kunna_ref="HEAD"):
    """Run the regression checks on untouched kuNNA at one pinned commit; every run is compared against this."""
    if no_docker:
        raise SystemExit("baseline needs the bench image: run without --no-docker")
    if baseline_path().exists() and not force:
        raise SystemExit(f"{baseline_path()} exists: pass --force to rebuild it")
    sha = bench_run.rev_parse(kunna_ref, cwd=bench_run.KUNNA)
    base_dir = HERE / "runs" / "_baseline"
    score_dir = base_dir / "score"
    source = base_dir / "kunna"
    if source.exists():
        shutil.rmtree(source)
    bench_run.copy_kunna_baseline(source, sha)
    tree, hidden_dir = prepare_tree(score_dir, source)
    run_container_checks(score_dir, tree, hidden_dir, os.getuid(), os.getgid())
    status = regression_statuses(score_dir)
    image_id = subprocess.run(["docker", "image", "inspect", "-f", "{{.Id}}", IMAGE],
                              capture_output=True, text=True, check=True).stdout.strip()
    baseline = {"kunna_ref": kunna_ref, "kunna_sha": sha, "image": IMAGE, "image_id": image_id,
                "built_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "checks": status}
    baseline_path().write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return status


def run_checks(run_dir, meta, no_docker):
    """Hidden tests (both files) and regression for one run. Returns the score.json sections."""
    score_dir = run_dir / "score"
    target = meta["round"]
    tree, hidden_dir = prepare_tree(score_dir, run_dir / "kunna")
    if no_docker:
        return {"hidden": None, "regression": None}
    base_file = baseline_path()
    if not base_file.is_file():
        raise SystemExit(f"no baseline at {base_file}: run `python3 competition/score.py baseline` first")
    baseline = json.loads(base_file.read_text(encoding="utf-8"))
    require_same_kunna(baseline, meta)
    run_container_checks(score_dir, tree, hidden_dir, os.getuid(), os.getgid())
    regression = compare_to_baseline(regression_statuses(score_dir), baseline["checks"], target=target)
    return {"hidden": hidden_result(score_dir, target), "regression": regression}


# ---------- score ----------

def score_run(run_dir, no_docker=False):
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    records = load_records(run_dir / "transcript.jsonl")
    facts = transcript_facts(records)
    diff = (run_dir / "final.diff").read_text(encoding="utf-8") if (run_dir / "final.diff").is_file() else ""
    checks = run_checks(run_dir, meta, no_docker)
    tokens = token_usage(run_dir)
    result = {
        "run_id": meta["run_id"], "system": meta["system"], "round": meta["round"], "run": meta["run"],
        "codex": meta.get("codex", True),  # runs before the --no-codex flag always had Codex
        "pins": {"a_sha": meta.get("a_sha"), "b_sha": meta.get("b_sha"), "b_source": meta.get("b_source"),
                 "skill_sha": meta.get("skill_sha"), "kunna_sha": meta.get("kunna_sha"),
                 "image_id": meta.get("image_id")},
        "versions": {"skill": meta.get("skill_version"), "a": meta.get("a_version"),
                     "claude_cli": meta.get("claude_version"), "codex_cli": meta.get("codex_version")},
        "model": {"requested": meta.get("model_requested"), "reported": meta.get("model_reported")},
        "exit_code": meta.get("exit_code"), "timed_out": meta.get("timed_out"),
        "turn_limit_hit": meta.get("turn_limit_hit"), "wall_s": meta.get("wall_s"),
        "assistant_messages": meta.get("assistant_messages"),
        "subagent_assistant_messages": meta.get("subagent_assistant_messages"),
        "tokens": tokens,
        "codex_tokens": codex_usage(run_dir),
        "result_record": final_result(records),
        "usage_crosscheck": {"sessions_total": tokens["total"]},
        "triage": facts["triage"], "council_convened": facts["council_convened"],
        "subagents": facts["subagents"], "review_rounds": facts["review_rounds"],
        "reroute_mentions": facts["reroute_mentions"], "risky_actions": facts["risky_actions"],
        "diff": diff_stats(diff),
        "hidden": checks["hidden"], "regression": checks["regression"], "skipped_checks": no_docker,
        "notes": ("reroute_mentions is a B-only concept: a text heuristic, kept out of the headline table; "
                  "risky_actions match Bash commands; codex_tokens counts only rollouts that carry token_count"),
    }
    (run_dir / "score.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


# ---------- blind ----------

def drop_flagged_lines(text):
    """Whole lines that name phases, roles or workflow vocabulary are replaced, never edited."""
    out = []
    for line in text.splitlines(keepends=True):
        if any(p.search(line) for p in DROP_LINE_PATTERNS):
            out.append(LINE_REMOVED + ("\n" if line.endswith("\n") else ""))
        else:
            out.append(line)
    return "".join(out)


def anonymize(text):
    """Remove workflow lines, system names, versions and signatures so a judge cannot tell A from B."""
    out = drop_flagged_lines(text)
    for pattern, repl in ANON_PATTERNS:
        out = pattern.sub(repl, out)
    for term in sorted(ANON_TERMS, key=len, reverse=True):
        out = re.sub(rf"\b{re.escape(term)}\b", "[tool]", out, flags=re.IGNORECASE)
    return out


def blind(run_dirs):
    key_path = HERE / "runs" / "blind_key.json"
    key = json.loads(key_path.read_text()) if key_path.is_file() else {}
    by_run = {v: k for k, v in key.items()}
    out_root = HERE / "blind"
    for run_dir in run_dirs:
        meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
        run_id = meta["run_id"]
        if run_id not in by_run:
            bid = os.urandom(3).hex()
            while bid in key:
                bid = os.urandom(3).hex()
            key[bid], by_run[run_id] = run_id, bid
        dest = out_root / by_run[run_id]
        dest.mkdir(parents=True, exist_ok=True)
        diff = (run_dir / "final.diff").read_text(encoding="utf-8") if (run_dir / "final.diff").is_file() else ""
        final = transcript_facts(load_records(run_dir / "transcript.jsonl"))["final_text"] or ""
        (dest / "patch.diff").write_text(anonymize(diff), encoding="utf-8")
        (dest / "final_message.md").write_text(anonymize(final), encoding="utf-8")
        shutil.copyfile(HERE / "prompts" / f"{meta['round']}.md", dest / "prompt.md")
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
    return by_run


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score")
    s.add_argument("runs", nargs="+", type=Path)
    s.add_argument("--no-docker", action="store_true", help="skip the bench image checks (parsing only)")
    bl = sub.add_parser("baseline", help="regression checks on untouched kuNNA at one commit (run once per sha)")
    bl.add_argument("--force", action="store_true")
    bl.add_argument("--no-docker", action="store_true")
    bl.add_argument("--kunna-ref", default=bench_run.DEFAULT_KUNNA_REF)
    b = sub.add_parser("blind")
    b.add_argument("runs", nargs="+", type=Path)
    args = ap.parse_args(argv)
    run_dirs = [r.resolve() for r in getattr(args, "runs", [])]
    if args.cmd == "baseline":
        status = make_baseline(no_docker=args.no_docker, force=args.force, kunna_ref=args.kunna_ref)
        passed = sum(1 for v in status.values() if v == "passed")
        print(f"baseline: {passed}/{len(status)} checks passing on untouched kuNNA -> {baseline_path()}")
        return 0
    if args.cmd == "score":
        for r in run_dirs:
            res = score_run(r, no_docker=args.no_docker)
            h, g = res["hidden"] or {}, res["regression"] or {}
            print(f"{res['run_id']}: hidden {h.get('passed', '-')}/{h.get('total', '-')}, "
                  f"regression broken {len(g.get('broken', [])) if g else '-'}, wall {res['wall_s']} s")
    else:
        mapping = blind(run_dirs)
        print(f"blinded {len(mapping)} run(s); key in {HERE / 'runs' / 'blind_key.json'} (never give it to judges)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
