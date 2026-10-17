#!/usr/bin/env python3
"""Score bench runs and prepare blind judging.

    python3 competition/score.py score runs/<id> [runs/<id> ...] [--no-docker]
        -> runs/<id>/score.json  (hidden tests, regression suite, tokens, orchestration facts)
    python3 competition/score.py baseline [--force]   (once: regression checks on untouched kuNNA)
    python3 competition/score.py blind runs/<id> [runs/<id> ...]
        -> blind/<blind-id>/ (anonymized patch, final message, prompt) + runs/blind_key.json

Hidden tests are copied into runs/<id>/score/ ONLY here, never before the run. Regression checks and
hidden tests run inside the bench image against a scratch copy of the run's kuNNA tree.
Token counts reuse the repo's cost_tracker.usage_by_model (from the run's own skillrepo snapshot).
"""
import argparse
import importlib.util
import json
import os
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMAGE = os.environ.get("KUNNA_BENCH_IMAGE", "kunna-bench:1")
HIDDEN = {"bug": HERE / "hidden" / "test_bug_hidden.py", "improve": HERE / "hidden" / "test_improve_hidden.py"}
PY_FILES = ("backend/app.py", "backend/auth.py", "backend/netmap.py", "backend/caretaker.py",
            "backend/agent_manager.py", "backend/ssh_deployer.py", "monitor/docker_monitor.py", "agent/agent.py")
SUBAGENT_TOOLS = ("Task", "Agent")
TEAM_TOOLS = ("TeamCreate", "SendMessage")
TRIAGE_RE = re.compile(r"\bTier\s+[SML]\s*·")
REROUTE_RE = re.compile(r"\bre-?rout", re.IGNORECASE)
RISKY_RE = re.compile(r"git\s+push|docker\s+(rm|push|system\s+prune)|\brm\s+-[a-z]*r|git\s+reset\s+--hard|"
                      r"kubectl\s+delete|\bdeploy\b|--force\b|DELETE\s+/|curl\s+.*-X\s*DELETE", re.IGNORECASE)
# Names that identify the system under test or the models; removed from anything a judge reads
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
    return {"subagents": dict(subagents), "review_rounds": reviews, "reroutes": reroutes,
            "triage": triage, "council_convened": council, "risky_actions": risky,
            "final_text": final_text}


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


# ---------- hidden tests and regression (in the bench image) ----------

def container_script():
    """Runs inside the bench image. Every check writes a raw result; the host turns them into statuses."""
    jest = " ".join(["jest", "--config", "'{\"rootDir\":\"/work\",\"testEnvironment\":\"node\"}'", "--watchman=false"])
    return """set -u
mkdir -p /bench/score/home
R=/bench/score/regression.txt
: > $R
python3 -m py_compile """ + " ".join(PY_FILES) + """ > /bench/score/py_compile.log 2>&1
echo "py_compile $?" >> $R
for f in frontend/__tests__/*.test.js; do
  n="$(basename "$f" .test.js)"
  """ + jest + """ --json --outputFile="/bench/score/js_$n.json" "$f" > "/bench/score/js_$n.log" 2>&1
  echo "js_$n $?" >> $R
done
python3 -m pytest -q -p no:cacheprovider --junit-xml=/bench/score/hidden.xml /hidden > /bench/score/hidden.log 2>&1
echo "hidden $?" >> $R
exit 0
"""


def prepare_tree(score_dir, source, hidden_file=None):
    """Scratch copy of a kuNNA tree (the agent's copy is never touched), plus the hidden test if given."""
    if score_dir.exists():
        shutil.rmtree(score_dir)
    tree, hidden_dir = score_dir / "tree", score_dir / "hidden"
    shutil.copytree(source, tree, ignore=shutil.ignore_patterns(".git"))
    hidden_dir.mkdir(parents=True)
    if hidden_file is not None:
        shutil.copy2(hidden_file, hidden_dir / hidden_file.name)
    return tree, hidden_dir


def run_container_checks(score_dir, tree, hidden_dir, uid, gid):
    argv = ["docker", "run", "--rm", "--user", f"{uid}:{gid}",
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
    """Every regression check as {id: passed|failed}, from the raw files written in the container."""
    status = {}
    for line in (score_dir / "regression.txt").read_text().splitlines():
        name, rc = line.rsplit(" ", 1)
        status[name] = "passed" if rc == "0" else "failed"
    for jf in sorted(score_dir.glob("js_*.json")):
        status.update(jest_statuses(jf, jf.stem[3:]))
    return status


def compare_to_baseline(run_status, base_status):
    """Regression = a check that passes on untouched kuNNA and does not pass in this run."""
    passing = sorted(k for k, v in base_status.items() if v == "passed")
    broken = [k for k in passing if run_status.get(k) != "passed"]
    return {"baseline_passing": len(passing), "still_passing": len(passing) - len(broken),
            "broken": broken, "ok": not broken}


def hidden_result(score_dir, file_name):
    hidden = {"file": file_name, "tests": {}, "total": 0, "passed": 0}
    xml = score_dir / "hidden.xml"
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


def baseline_path():
    return HERE / "runs" / "_baseline" / "baseline.json"


def make_baseline(no_docker=False, force=False):
    """Run the regression checks on untouched kuNNA HEAD once; every run is compared against this."""
    import run as bench_run  # same directory, stdlib only
    if baseline_path().exists() and not force:
        raise SystemExit(f"{baseline_path()} exists: pass --force to rebuild it")
    base_dir = HERE / "runs" / "_baseline"
    score_dir = base_dir / "score"
    source = base_dir / "kunna"
    if source.exists():
        shutil.rmtree(source)
    bench_run.copy_kunna_baseline(source)
    tree, hidden_dir = prepare_tree(score_dir, source)
    if no_docker:
        raise SystemExit("baseline needs the bench image: run without --no-docker")
    run_container_checks(score_dir, tree, hidden_dir, os.getuid(), os.getgid())
    status = regression_statuses(score_dir)
    baseline_path().write_text(json.dumps({"checks": status, "image": IMAGE}, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
    passed = sum(1 for v in status.values() if v == "passed")
    return passed, len(status)


def run_checks(run_dir, round_name, no_docker):
    """Hidden tests and regression for one run. Returns the score.json sections."""
    score_dir = run_dir / "score"
    hidden_file = HIDDEN[round_name]
    tree, hidden_dir = prepare_tree(score_dir, run_dir / "kunna", hidden_file)
    if no_docker:
        return {"hidden": None, "regression": None}
    run_container_checks(score_dir, tree, hidden_dir, os.getuid(), os.getgid())
    base = baseline_path()
    if not base.is_file():
        raise SystemExit(f"no baseline at {base}: run `python3 competition/score.py baseline` first")
    base_status = json.loads(base.read_text(encoding="utf-8"))["checks"]
    regression = compare_to_baseline(regression_statuses(score_dir), base_status)
    return {"hidden": hidden_result(score_dir, hidden_file.name), "regression": regression}


# ---------- score ----------

def score_run(run_dir, no_docker=False):
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    records = load_records(run_dir / "transcript.jsonl")
    facts = transcript_facts(records)
    diff = (run_dir / "final.diff").read_text(encoding="utf-8") if (run_dir / "final.diff").is_file() else ""
    checks = run_checks(run_dir, meta["round"], no_docker)
    result = {
        "run_id": meta["run_id"], "system": meta["system"], "round": meta["round"], "run": meta["run"],
        "skill_version": meta.get("skill_version"), "a_version": meta.get("a_version"),
        "exit_code": meta.get("exit_code"), "timed_out": meta.get("timed_out"),
        "turn_limit_hit": meta.get("turn_limit_hit"), "wall_s": meta.get("wall_s"),
        "assistant_messages": meta.get("assistant_messages"),
        "tokens": token_usage(run_dir),
        "triage": facts["triage"], "council_convened": facts["council_convened"],
        "subagents": facts["subagents"], "review_rounds": facts["review_rounds"],
        "reroutes": facts["reroutes"], "risky_actions": facts["risky_actions"],
        "diff": diff_stats(diff),
        "hidden": checks["hidden"], "regression": checks["regression"], "skipped_checks": no_docker,
        "notes": "reroutes is a text heuristic (\"re-route\" in assistant text); risky_actions match Bash commands",
    }
    (run_dir / "score.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


# ---------- blind ----------

def anonymize(text):
    """Strip system names, versions and signatures so a judge cannot tell A from B."""
    out = text
    for pattern, repl in ANON_PATTERNS:
        out = pattern.sub(repl, out)
    for term in sorted(ANON_TERMS, key=len, reverse=True):
        out = re.sub(re.escape(term), "[tool]", out, flags=re.IGNORECASE)
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
            bid = secrets.token_hex(3)
            while bid in key:
                bid = secrets.token_hex(3)
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
    bl = sub.add_parser("baseline", help="regression checks on untouched kuNNA HEAD (run once)")
    bl.add_argument("--force", action="store_true")
    bl.add_argument("--no-docker", action="store_true")
    b = sub.add_parser("blind")
    b.add_argument("runs", nargs="+", type=Path)
    args = ap.parse_args(argv)
    run_dirs = [r.resolve() for r in getattr(args, "runs", [])]
    if args.cmd == "baseline":
        passed, total = make_baseline(no_docker=args.no_docker, force=args.force)
        print(f"baseline: {passed}/{total} checks passing on untouched kuNNA -> {baseline_path()}")
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
