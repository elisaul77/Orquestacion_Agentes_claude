#!/usr/bin/env python3
"""Instincts: small learned behaviours with a confidence score (subagent-pool v9.6).

An instinct is one trigger -> action rule seen in real work, e.g.
  trigger "when a phase touches alembic migrations"  action "run `alembic check` in the verify step".
Stored as JSON under ~/.claude/pool-instincts/ (override with POOL_INSTINCTS_DIR):
  global.json · projects/<hash>.json  (hash = sha1 of the git remote URL, else of the repo path)

    instincts.py add --trigger T --action A [--domain D] [--project PATH] [--global]
    instincts.py seen ID [--project PATH]     # confirmed again: +0.1 confidence (max 0.9)
    instincts.py contradict ID [--project PATH]  # failed or user corrected it: -0.2 (removed below 0.3)
    instincts.py list [--project PATH] [--min 0.5]   # project + global, for the Conductor's briefs
    instincts.py promote [--project PATH]     # same trigger in 2+ projects -> copy to global
    instincts.py evolve [--min 0.7]           # clusters by domain with 3+ strong instincts -> skill candidates

Session text is untrusted: add() rejects secrets and instruction-override phrasing.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

START, STEP_UP, STEP_DOWN, FLOOR, CEIL = 0.3, 0.1, 0.2, 0.3, 0.9
BAD = re.compile(
    r"(ignore (all |previous |prior )?instructions|disregard .*rules|system prompt|"
    r"sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY|"
    r"(api[_-]?key|password|secret|token)\s*[:=]\s*\S{4,})",
    re.I,
)


def root():
    return Path(os.environ.get("POOL_INSTINCTS_DIR", Path.home() / ".claude" / "pool-instincts"))


def project_id(path):
    path = Path(path or ".").resolve()
    try:
        key = subprocess.run(["git", "-C", str(path), "remote", "get-url", "origin"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        key = ""
    return hashlib.sha1((key or str(path)).encode()).hexdigest()[:12]


def store(pid=None):
    return root() / ("global.json" if pid is None else f"projects/{pid}.json")


def load(pid=None):
    f = store(pid)
    return json.loads(f.read_text()) if f.exists() else []


def save(items, pid=None):
    f = store(pid)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n")


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48]


def add(trigger, action, domain="general", pid=None):
    for text in (trigger, action, domain):
        if BAD.search(text):
            raise ValueError("rejected: looks like a secret or an instruction override")
    items = load(pid)
    iid = slug(trigger)
    for it in items:
        if it["id"] == iid:
            it["action"], it["domain"] = action, domain
            save(items, pid)
            return it
    it = {"id": iid, "trigger": trigger, "action": action, "domain": domain,
          "confidence": START, "seen": 1, "scope": "global" if pid is None else "project"}
    items.append(it)
    save(items, pid)
    return it


def adjust(iid, delta, pid=None):
    items = load(pid)
    for it in items:
        if it["id"] == iid:
            it["confidence"] = round(min(CEIL, it["confidence"] + delta), 2)
            if delta > 0:
                it["seen"] += 1
            if it["confidence"] < FLOOR:
                items.remove(it)
                it = {**it, "removed": True}
            save(items, pid)
            return it
    raise KeyError(iid)


def listing(pid, minimum=0.0):
    rows = [*load(pid), *load(None)]
    return sorted((r for r in rows if r["confidence"] >= minimum), key=lambda r: -r["confidence"])


def promote():
    seen = {}
    for f in (root() / "projects").glob("*.json"):
        for it in json.loads(f.read_text()):
            seen.setdefault(it["id"], []).append(it)
    glob_items = load(None)
    have = {g["id"] for g in glob_items}
    promoted = []
    for iid, copies in seen.items():
        if len(copies) >= 2 and iid not in have:
            best = max(copies, key=lambda c: c["confidence"])
            glob_items.append({**best, "scope": "global", "seen": sum(c["seen"] for c in copies)})
            promoted.append(iid)
    if promoted:
        save(glob_items, None)
    return promoted


def evolve(minimum=0.7):
    pool = list(load(None))
    for f in (root() / "projects").glob("*.json"):
        pool += json.loads(f.read_text())
    clusters = {}
    for it in pool:
        if it["confidence"] >= minimum:
            clusters.setdefault(it["domain"], {})[it["id"]] = it
    return {d: list(v.values()) for d, v in clusters.items() if len(v) >= 3}


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--trigger", required=True)
    a.add_argument("--action", required=True)
    a.add_argument("--domain", default="general")
    a.add_argument("--global", dest="glob", action="store_true")
    for name in ("seen", "contradict"):
        s = sub.add_parser(name)
        s.add_argument("id")
        s.add_argument("--global", dest="glob", action="store_true")
    l = sub.add_parser("list")
    l.add_argument("--min", type=float, default=0.0)
    sub.add_parser("promote")
    e = sub.add_parser("evolve")
    e.add_argument("--min", type=float, default=0.7)
    for p in sub.choices.values():
        p.add_argument("--project", default=".")
    args = ap.parse_args(argv)
    pid = None if getattr(args, "glob", False) else project_id(args.project)
    try:
        if args.cmd == "add":
            out = add(args.trigger, args.action, args.domain, pid)
        elif args.cmd == "seen":
            out = adjust(args.id, STEP_UP, pid)
        elif args.cmd == "contradict":
            out = adjust(args.id, -STEP_DOWN, pid)
        elif args.cmd == "list":
            out = listing(project_id(args.project), args.min)
        elif args.cmd == "promote":
            out = promote()
        else:
            out = evolve(args.min)
    except (ValueError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 1
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
