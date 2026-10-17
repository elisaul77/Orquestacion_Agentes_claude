#!/usr/bin/env python3
"""Install or update the subagent-pool stack into ~/.claude (v9.10). Safe to re-run.

    python3 skills/subagent-pool/scripts/install.py [--dry-run] [--with teams,cost-hook,codex,claude-md]

Core (always): back up what is installed, copy the skills (subagent-pool, arquitec-dev-ia, graphify) and the agents.
Optional add-ons, only when named in --with (ask the user first; each is independent):
  teams      "env": {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"} in settings.json (council debates by message)
  cost-hook  Stop hook running cost_tracker.py (token ledger)
  codex      codex-agent + Codex roles synced into ~/.codex/agents (needs the `codex` CLI, logged in)
  claude-md  routing table appended to ~/.claude/CLAUDE.md between markers (replaced on re-run, removable)
settings.json is merged, never overwritten. Ends with doctor's checks and RESTART_REQUIRED: Claude Code loads agent
files when a session starts, so new agents are not callable until the user restarts it.
Exit code: 0 installed (warnings allowed), 1 a requirement failed or doctor reported a failure.
"""
import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SKILLS = ("subagent-pool", "arquitec-dev-ia", "graphify")
ADDONS = ("teams", "cost-hook", "codex", "claude-md")
TEAMS_FLAG = "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"
HOOK_CMD = "python3 ~/.claude/skills/subagent-pool/scripts/cost_tracker.py hook"
BEGIN, END = "<!-- subagent-pool:begin -->", "<!-- subagent-pool:end -->"
IGNORE = shutil.ignore_patterns("__pycache__", ".pytest_cache")


class Installer:
    def __init__(self, home, repo=REPO, addons=(), dry=False, which=shutil.which):
        self.home, self.repo, self.addons, self.dry, self.which = Path(home), Path(repo), set(addons), dry, which
        self.claude = self.home / ".claude"
        self.log, self.warnings = [], []

    def do(self, msg, fn=None):
        self.log.append(("would " if self.dry else "") + msg)
        if fn and not self.dry:
            fn()

    def requirements(self):
        ok = sys.version_info >= (3, 10)
        if not ok:
            self.log.append(f"FAIL python {sys.version.split()[0]} < 3.10")
        if not (self.repo / "skills" / "subagent-pool" / "SKILL.md").exists():
            self.log.append(f"FAIL not a subagent-pool checkout: {self.repo}")
            ok = False
        if not self.which("claude"):
            self.warnings.append("claude CLI not on PATH (fine if Claude Code runs as an app)")
        if "codex" in self.addons and not self.which("codex"):
            self.warnings.append("codex CLI not found: skipping the codex add-on (npm i -g @openai/codex && codex login)")
            self.addons.discard("codex")
        md = self.claude / "CLAUDE.md"
        if "claude-md" in self.addons and md.exists():
            t = md.read_text()
            nb, ne = t.count(BEGIN), t.count(END)
            if (nb, ne) not in ((0, 0), (1, 1)) or (nb == 1 and t.index(BEGIN) > t.index(END)):
                self.log.append(f"FAIL {md} has broken subagent-pool markers ({nb} begin, {ne} end): fix them by hand, "
                                "nothing was changed")
                ok = False
        return ok

    def backup(self):
        skill = self.claude / "skills" / "subagent-pool"
        ver = "none"
        if (skill / "SKILL.md").exists():
            import re
            m = re.search(r'version:\s*"?([\d.]+)', (skill / "SKILL.md").read_text())
            ver = m.group(1) if m else "unknown"
        targets = [self.claude / "skills" / s for s in SKILLS] + [self.claude / "settings.json", self.claude / "CLAUDE.md"]
        targets += [self.claude / "agents" / f.name for f in self._agent_sources()]
        if "codex" in self.addons:  # sync may update roles it generated; keep the old ones
            targets += sorted((self.home / ".codex" / "agents").glob("*.toml"))
        existing = [t for t in targets if t.exists()]
        if not existing:
            return None
        base = self.claude / "backups" / f"subagent-pool-{ver}-{time.strftime('%Y%m%d-%H%M%S')}"
        dest, n = base, 1
        while dest.exists():  # two runs in the same second must not merge into one backup
            dest, n = base.with_name(f"{base.name}-{n}"), n + 1

        def run():
            for t in existing:
                out = dest / (t.relative_to(self.claude) if self.claude in t.parents else Path("codex-agents") / t.name)
                out.parent.mkdir(parents=True, exist_ok=True)
                (shutil.copytree(t, out, ignore=IGNORE) if t.is_dir() else shutil.copy2(t, out))
        self.do(f"back up {len(existing)} item(s) to {dest}", run)
        return dest

    def _agent_sources(self):
        files = sorted((self.repo / "agents").glob("*.agent.md"))
        if "codex" in self.addons:
            files.append(self.repo / "agents" / "optional" / "codex-agent.agent.md")
        return files

    def copy(self):
        for s in SKILLS:
            src, dst = self.repo / "skills" / s, self.claude / "skills" / s
            def replace(src=src, dst=dst):  # replace, not overlay: files removed upstream must go (backup has them)
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst, ignore=IGNORE)
            self.do(f"install skill {s} → {dst}", replace)
        agents = self.claude / "agents"
        for f in self._agent_sources():
            self.do(f"copy agent {f.name}", lambda f=f: (agents.mkdir(parents=True, exist_ok=True),
                                                        shutil.copy2(f, agents / f.name)))

    def merge_settings(self):
        if not self.addons & {"teams", "cost-hook"}:
            return
        path = self.claude / "settings.json"
        try:
            cfg = json.loads(path.read_text()) if path.exists() else {}
        except ValueError:
            self.warnings.append(f"{path} is not valid JSON: left untouched, add the add-ons by hand")
            return
        changed = []
        if "teams" in self.addons and (cfg.get("env") or {}).get(TEAMS_FLAG) != "1":
            cfg.setdefault("env", {})[TEAMS_FLAG] = "1"
            changed.append("teams flag")
        stop = json.dumps((cfg.get("hooks") or {}).get("Stop", []))
        if "cost-hook" in self.addons and "cost_tracker.py hook" not in stop:
            cfg.setdefault("hooks", {}).setdefault("Stop", []).append(
                {"hooks": [{"type": "command", "command": HOOK_CMD, "timeout": 10, "async": True}]})
            changed.append("cost hook")
        if not changed:
            self.log.append("settings.json already has the requested add-ons")
            return

        def run():
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
            os.replace(tmp, path)
        self.do(f"merge into settings.json: {', '.join(changed)}", run)

    def codex_roles(self):
        if "codex" not in self.addons:
            return
        if self.dry:
            self.log.append("would sync Codex roles from ~/.claude/agents")
            return
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import sync_codex_agents as sca
        args = ["--src", str(self.claude / "agents"), "--dest", str(self.home / ".codex" / "agents")]
        if sca.main(args) != 0:
            self.warnings.append("some Codex roles are foreign (Codex's own import): back them up and delete them, then re-run")
        else:
            self.log.append("synced Codex roles")

    def claude_md(self):
        if "claude-md" not in self.addons:
            return
        path = self.claude / "CLAUDE.md"
        block = f"{BEGIN}\n{(self.repo / 'skills/subagent-pool/assets/claude-md-block.md').read_text().strip()}\n{END}\n"
        text = path.read_text() if path.exists() else ""
        if BEGIN in text and END in text:
            head, rest = text.split(BEGIN, 1)
            new = head + block + rest.split(END, 1)[1].lstrip("\n")
            verb = "replace"
        else:
            new = text + ("\n" if text and not text.endswith("\n") else "") + ("\n" if text else "") + block
            verb = "append"
        if new == text:
            self.log.append("CLAUDE.md routing block already current")
            return
        self.do(f"{verb} the routing block in {path}", lambda: (path.parent.mkdir(parents=True, exist_ok=True),
                                                             path.write_text(new)))

    def doctor(self):
        if self.dry:
            return []
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import doctor
        doctor.HOME = self.home
        return doctor.run_checks(str(self.repo))

    def run(self):
        if not self.requirements():
            return 1, None, []
        dest = self.backup()
        self.copy()
        self.merge_settings()
        self.codex_roles()
        self.claude_md()
        checks = self.doctor()
        return (1 if any(c["status"] == "fail" for c in checks) else 0), dest, checks


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--home", default=str(Path.home()))
    ap.add_argument("--with", dest="addons", default="", help="comma list: " + ",".join(ADDONS))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    addons = [a for a in args.addons.split(",") if a]
    bad = [a for a in addons if a not in ADDONS]
    if bad:
        ap.error(f"unknown add-on(s): {', '.join(bad)}")
    inst = Installer(args.home, addons=addons, dry=args.dry_run)
    code, dest, checks = inst.run()
    for line in inst.log:
        print(("✗ " if line.startswith("FAIL") else "• ") + line)
    for w in inst.warnings:
        print(f"! {w}")
    mark = {"ok": "✓", "warn": "!", "fail": "✗"}
    for c in checks:
        print(f"{mark[c['status']]} {c['check']}" + (f" — {c['detail']}" if c["detail"] else ""))
        if c["fix"]:
            print(f"    fix: {c['fix']}")
    print(f"STATUS: {'DRY_RUN' if args.dry_run else ('INSTALLED' if code == 0 else 'FAILED')}")
    print(f"ADDONS: {', '.join(sorted(inst.addons)) or 'none'}")
    print(f"BACKUP: {(str(dest) + (' (planned)' if args.dry_run else '')) if dest else 'none (nothing installed before)'}")
    print(f"RESTART_REQUIRED: {'no' if args.dry_run else 'yes — restart Claude Code so the agents load'}")
    return code


if __name__ == "__main__":
    sys.exit(main())
