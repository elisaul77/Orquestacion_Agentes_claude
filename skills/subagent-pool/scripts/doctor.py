#!/usr/bin/env python3
"""Read-only health check of the subagent-pool install (v9.7). Changes nothing.

    python3 doctor.py [--repo PATH] [--remote HOST ...] [--json]

Checks: installed skill version (and drift against --repo), the three core agents, optional codex-agent + codex CLI,
the cost hook in settings.json and whether the ledger is being written, the instincts store, and each --remote host
over SSH (BatchMode, short timeout). Each failed check carries a suggested fix; nothing is applied.
Exit code: 0 all OK, 1 if any check failed (warnings don't fail).
"""
import argparse
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HOME = Path(os.environ.get("POOL_HOME", Path.home()))
CORE_AGENTS = ("planning-agent", "implement-agent", "review-agent")
# Keep the SSH probe from writing locally: no known_hosts updates, no control sockets, no local commands.
SSH_RO = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=6", "-o", "StrictHostKeyChecking=yes", "-o", "UpdateHostKeys=no",
          "-o", "ControlMaster=no", "-o", "ControlPath=none", "-o", "PermitLocalCommand=no"]


def version_of(skill_md):
    m = re.search(r'version:\s*"?([\d.]+)"?', Path(skill_md).read_text()) if Path(skill_md).exists() else None
    return m.group(1) if m else None


def drift(a, b):
    """Files that differ between two trees, ignoring caches."""
    out, cmp = [], filecmp.dircmp(a, b, ignore=["__pycache__", ".pytest_cache"])
    stack = [("", cmp)]
    while stack:
        rel, c = stack.pop()
        out += [f"{rel}{n}" for n in c.diff_files + c.left_only + c.right_only]
        stack += [(f"{rel}{n}/", sub) for n, sub in c.subdirs.items()]
    return sorted(out)


def check(name, ok, detail="", fix="", level="fail"):
    return {"check": name, "status": "ok" if ok else level, "detail": detail, "fix": "" if ok else fix}


def run_checks(repo=None, remotes=(), now=None):
    claude = HOME / ".claude"
    skill = claude / "skills" / "subagent-pool"
    res = []
    ver = version_of(skill / "SKILL.md")
    res.append(check("skill installed", ver is not None, f"v{ver}" if ver else str(skill),
                     "copy skills/subagent-pool from the repo into ~/.claude/skills/"))
    if repo and ver:
        rskill = Path(repo) / "skills" / "subagent-pool"
        diff = drift(rskill, skill) if rskill.is_dir() else ["<repo not found>"]
        res.append(check("skill matches repo", not diff, ", ".join(diff[:5]) or f"v{version_of(rskill / 'SKILL.md')}",
                         f"rsync -a --exclude __pycache__ {rskill}/ {skill}/  (after a backup)"))
        for a in CORE_AGENTS:
            src, dst = Path(repo) / "agents" / f"{a}.agent.md", claude / "agents" / f"{a}.agent.md"
            if src.exists() and dst.exists():
                res.append(check(f"{a} matches repo", filecmp.cmp(src, dst, shallow=False), "",
                                 f"cp {src} {dst}"))
    for a in CORE_AGENTS:
        res.append(check(f"agent {a}", (claude / "agents" / f"{a}.agent.md").exists(), "",
                         f"copy agents/{a}.agent.md into ~/.claude/agents/"))
    has_codex_agent = (claude / "agents" / "codex-agent.agent.md").exists()
    res.append(check("codex (optional)", has_codex_agent and shutil.which("codex") is not None,
                     "agent + CLI" if has_codex_agent else "codex-agent not installed",
                     "optional: install codex CLI / codex-agent, the pool runs Claude-only without it", "warn"))
    settings = claude / "settings.json"
    try:
        hooked = "cost_tracker" in json.dumps(json.loads(settings.read_text()).get("hooks", {}))
    except (OSError, ValueError):
        hooked = False
    res.append(check("cost hook", hooked, str(settings), "see assets/hooks.md (optional)", "warn"))
    ledger = claude / "metrics" / "costs.jsonl"
    if hooked:
        age = ((now or time.time()) - ledger.stat().st_mtime) / 3600 if ledger.exists() else None
        res.append(check("cost ledger fresh", age is not None and age < 48,
                         "missing" if age is None else f"last write {age:.0f} h ago",
                         "finish a session; if still stale run the hook command by hand to see its error", "warn"))
    store = claude / "pool-instincts"
    res.append(check("instincts store", True, "present" if store.exists() else "empty (created on first add)"))
    for host in remotes:
        try:
            p = subprocess.run(["ssh", *SSH_RO, host,
                                "grep -m1 version ~/.claude/skills/subagent-pool/SKILL.md"],
                               capture_output=True, text=True, timeout=15)
            m = re.search(r"([\d.]+)", p.stdout)
            rv = m.group(1) if p.returncode == 0 and m else None
            err = (p.stderr.strip().splitlines() or ["no answer"])[-1]
        except (OSError, subprocess.SubprocessError) as exc:
            rv, err = None, str(exc)
        res.append(check(f"remote {host}", rv is not None and rv == ver,
                         f"v{rv}" if rv else err,
                         "unreachable: try the WireGuard alias or restart sshd there" if rv is None
                         else f"remote has v{rv}, local v{ver}: rsync the skill there"))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo")
    ap.add_argument("--remote", action="append", default=[])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    res = run_checks(args.repo, args.remote)
    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        mark = {"ok": "✓", "warn": "!", "fail": "✗"}
        for r in res:
            print(f"{mark[r['status']]} {r['check']}" + (f" — {r['detail']}" if r["detail"] else ""))
            if r["fix"]:
                print(f"    fix: {r['fix']}")
    return 1 if any(r["status"] == "fail" for r in res) else 0


if __name__ == "__main__":
    sys.exit(main())
