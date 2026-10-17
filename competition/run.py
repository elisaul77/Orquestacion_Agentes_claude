#!/usr/bin/env python3
"""A/B bench runner: the same kuNNA challenge against two subagent-pool versions, one container each.

    python3 competition/run.py --system A|B --round bug|improve --run N [--dry-run]

  A = subagent-pool from git `master`          (--a-ref, default master)
  B = subagent-pool from `feat/case-flow`      (--b-source worktree = the working tree, default;
                                                --b-source commit = git archive of --b-ref)
  Both run in the same image (competition/Dockerfile) with the same prompt (prompts/<round>.md).

Per run, under competition/runs/<system>-<round>-<N>/:
  skillrepo/   read-only snapshot of skills/ and agents/ (mounted at /skillrepo)
  kunna/       fresh kuNNA copy, git initialised, seed applied for round bug, baseline committed
  out/         install.log, stderr.log
  transcript.jsonl  stream-json from `claude -p`
  sessions/    Claude session JSONL copied out of the temp HOME (token accounting)
  final.diff, diffstat.txt, prompt.md, entry.sh, meta.json

Credentials: copied into a temp HOME OUTSIDE the repo (never under competition/), chmod 600,
removed and the HOME deleted in a finally block. Nothing secret is written to the run dir.
kuNNA is read from git HEAD (the working tree is never touched). Its path: $KUNNA_REPO.
"""
import argparse
import datetime as dt
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
KUNNA = Path(os.environ.get("KUNNA_REPO", "/home/elisaul77/Documentos/Docker/kunna"))
IMAGE = os.environ.get("KUNNA_BENCH_IMAGE", "kunna-bench:1")
ROUNDS = ("bug", "improve")
SEED = {"bug": HERE / "seed" / "bug.patch"}
SNAPSHOT_PATHS = ("skills", "agents")
DEFAULT_TIMEOUT_MIN = 45
DEFAULT_MAX_TURNS = 250
HOST_GRACE_S = 180            # the host waits this much longer than claude's own timeout before killing
ENTRY_ADDONS = "teams,codex"
GIT_ID = ["-c", "user.name=bench", "-c", "user.email=bench@localhost", "-c", "commit.gpgsign=false"]
VERSION_RE = re.compile(r'version:\s*"?([\d.]+)')
CLAUDE_JSON = {  # skips first-run onboarding inside the temp HOME; no credentials here
    "hasCompletedOnboarding": True,
    "bypassPermissionsModeAccepted": True,
    "projects": {"/work": {"hasTrustDialogAccepted": True}},
}


# ---------- helpers ----------

def git(*args, cwd=REPO):
    return ["git", "-C", str(cwd), *args]


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_version(root):
    skill = Path(root) / "skills" / "subagent-pool" / "SKILL.md"
    m = VERSION_RE.search(skill.read_text(encoding="utf-8"))
    return m.group(1) if m else "unknown"


def extract_tar(data, dest):
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        if hasattr(tarfile, "data_filter"):
            tar.extractall(dest, filter="data")
        else:
            tar.extractall(dest)  # noqa: S202 - trusted: our own git archive output


def snapshot_from_commit(ref, dest):
    data = subprocess.run(git("archive", "--format=tar", ref, *SNAPSHOT_PATHS),
                          check=True, capture_output=True).stdout
    extract_tar(data, dest)


def snapshot_from_worktree(dest):
    listing = subprocess.run(git("ls-files", "-z", "-co", "--exclude-standard"),
                             check=True, capture_output=True).stdout.decode("utf-8")
    copied = 0
    for rel in filter(None, listing.split("\0")):
        if not rel.startswith(tuple(p + "/" for p in SNAPSHOT_PATHS)):
            continue
        src = REPO / rel
        if not src.is_file() or "__pycache__" in rel:
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        copied += 1
    if copied == 0:
        raise SystemExit("worktree snapshot copied no files: check the repo layout")


def apply_seed(tree, patch):
    """Apply the seeded bug inside the copy's OWN repo and prove it landed.

    `git apply` run inside a subdirectory of another repo silently skips paths outside that
    subdirectory and still exits 0, so the copy must be a repo of its own (git init) first.
    """
    subprocess.run(git("init", "-q", cwd=tree), check=True)  # idempotent; makes the tree its own top level
    subprocess.run(git("apply", "--whitespace=nowarn", str(patch), cwd=tree), check=True)
    rev = subprocess.run(git("apply", "--reverse", "--check", str(patch), cwd=tree),
                         capture_output=True, text=True)
    if rev.returncode != 0:
        raise SystemExit(f"seed {patch.name} did not land in {tree}: {rev.stderr.strip()}")


def copy_kunna_baseline(dest, base_ref="HEAD"):
    data = subprocess.run(git("archive", "--format=tar", base_ref, cwd=KUNNA),
                          check=True, capture_output=True).stdout
    extract_tar(data, dest)


def write_entry(path, timeout_s):
    script = f"""#!/bin/bash
# Generated by competition/run.py. Runs inside the bench container.
set -uo pipefail
export PYTHONDONTWRITEBYTECODE=1
OUT=/bench/out
echo "[entry] install.py --with {ENTRY_ADDONS} from /skillrepo" >&2
if ! python3 /skillrepo/skills/subagent-pool/scripts/install.py --with {ENTRY_ADDONS} > "$OUT/install.log" 2>&1; then
  echo "[entry] install.py failed, see out/install.log" >&2
  exit 90
fi
cd /work
timeout --signal=TERM --kill-after=60 {timeout_s} \\
  claude -p "$(cat /bench/prompt.md)" --output-format stream-json --verbose --dangerously-skip-permissions
rc=$?
echo "[entry] claude exit $rc" >&2
exit $rc
"""
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def docker_argv(name, uid, gid, dirs, timeout_s):
    return [
        "docker", "run", "--rm", "--name", name,
        "--user", f"{uid}:{gid}",
        "-e", "HOME=/bench/home",
        "-e", "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1",
        "-e", f"BENCH_TIMEOUT_S={timeout_s}",
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-v", f"{dirs['skillrepo']}:/skillrepo:ro",
        "-v", f"{dirs['kunna']}:/work",
        "-v", f"{dirs['home']}:/bench/home",
        "-v", f"{dirs['prompt']}:/bench/prompt.md:ro",
        "-v", f"{dirs['entry']}:/bench/entry.sh:ro",
        "-v", f"{dirs['out']}:/bench/out",
        "-w", "/work",
        IMAGE, "bash", "/bench/entry.sh",
    ]


def credential_pairs():
    home = Path.home()
    return [
        (home / ".claude" / ".credentials.json", Path(".claude") / ".credentials.json"),
        (home / ".codex" / "auth.json", Path(".codex") / "auth.json"),
    ]


def prepare_home(home):
    """Temp HOME with credentials (chmod 600) and a minimal ~/.claude.json. Raises if a credential is missing."""
    for src, _ in credential_pairs():
        if not src.is_file():
            raise SystemExit(f"missing {src}: log in on the host first (claude / codex login)")
    for src, rel in credential_pairs():
        dst = home / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        dst.chmod(0o600)
    (home / ".claude.json").write_text(json.dumps(CLAUDE_JSON, indent=2), encoding="utf-8")


def remove_credentials(home):
    for _, rel in credential_pairs():
        (home / rel).unlink(missing_ok=True)


def copy_sessions(home, dest):
    projects = home / ".claude" / "projects"
    if not projects.is_dir():
        return 0
    n = 0
    for f in projects.rglob("*.jsonl"):
        target = dest / f.relative_to(projects)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, target)
        n += 1
    return n


# ---------- plan (shared by dry-run and real run) ----------

def build_plan(args):
    run_id = f"{args.system}-{args.round}-{args.run}"
    run_dir = HERE / "runs" / run_id
    timeout_s = int(args.timeout_min * 60)
    dirs = {
        "skillrepo": run_dir / "skillrepo",
        "kunna": run_dir / "kunna",
        "home": Path("<temp HOME, outside repo, created at run start>"),
        "prompt": run_dir / "prompt.md",
        "entry": run_dir / "entry.sh",
        "out": run_dir / "out",
    }
    ref = args.a_ref if args.system == "A" else args.b_ref
    if args.system == "A" or args.b_source == "commit":
        snap = f"git archive {ref} {' '.join(SNAPSHOT_PATHS)} | tar -x -C {dirs['skillrepo']}"
    else:
        snap = f"copy tracked+untracked files under {' '.join(p + '/' for p in SNAPSHOT_PATHS)} of the working tree -> {dirs['skillrepo']}"
    kunna_cmds = [f"git -C {KUNNA} archive --format=tar HEAD | tar -x -C {dirs['kunna']}",
                  f"git -C {dirs['kunna']} init -q"]
    if args.round in SEED:
        kunna_cmds.append(f"git -C {dirs['kunna']} apply {SEED[args.round]} && "
                          f"git -C {dirs['kunna']} apply --reverse --check {SEED[args.round]}  # seeded bug, verified")
    kunna_cmds.append(f"git -C {dirs['kunna']} add -A && git {' '.join(GIT_ID)} commit -q -m 'bench baseline'")
    prompt_path = HERE / "prompts" / f"{args.round}.md"
    prompt = prompt_path.read_text(encoding="utf-8")
    return {
        "run_id": run_id, "run_dir": run_dir, "timeout_s": timeout_s, "dirs": dirs,
        "ref": ref, "snapshot": snap, "kunna_cmds": kunna_cmds,
        "docker": docker_argv(f"kunna-bench-{run_id}", os.getuid(), os.getgid(), dirs, timeout_s),
        "prompt": prompt, "prompt_path": prompt_path,
    }


def print_dry_run(args, plan):
    def say(msg):
        print(f"[dry-run] {msg}")
    say(f"run id: {plan['run_id']}  (nothing is created, nothing is executed)")
    say(f"run dir: {plan['run_dir']}")
    say(f"skill snapshot ({args.system}, ref={plan['ref']}): {plan['snapshot']}")
    say("version guard: read skills/subagent-pool/SKILL.md from both snapshots; refuse if equal "
        "(override: --allow-same-version)")
    for c in plan["kunna_cmds"]:
        say(f"kuNNA: {c}")
    say(f"temp HOME: mkdtemp outside the repo (mode 700); copy {Path('~/.claude/.credentials.json')} and "
        f"{Path('~/.codex/auth.json')} (chmod 600); write minimal ~/.claude.json")
    say(f"entry script: {plan['run_dir'] / 'entry.sh'} (runs install.py --with {ENTRY_ADDONS}, then claude -p)")
    say(f"claude env: CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1, timeout {plan['timeout_s']} s, "
        f"host kill at +{HOST_GRACE_S} s, max assistant messages {args.max_turns} (host-side guard)")
    say("docker command:")
    print("  " + shlex.join(plan["docker"]))
    say(f"after the run: docker kill on timeout/turn limit; git add -A && git diff --cached <base> "
        f"-> final.diff; copy sessions; delete credentials; delete temp HOME")
    say(f"prompt: {plan['prompt_path']} ({len(plan['prompt'])} chars, sha256 {sha256_text(plan['prompt'])[:16]})")
    print("----- prompt (exact) -----")
    print(plan["prompt"], end="" if plan["prompt"].endswith("\n") else "\n")
    print("----- end prompt -----")


# ---------- real run ----------

class Pump(threading.Thread):
    """Copies container stdout to transcript.jsonl and counts assistant messages (host-side turn guard)."""

    def __init__(self, stream, path, max_turns, on_limit):
        super().__init__(daemon=True)
        self.stream, self.path, self.max_turns, self.on_limit = stream, path, max_turns, on_limit
        self.assistant = 0
        self.turn_limit_hit = False
        self.error = None

    def run(self):
        try:
            with open(self.path, "wb") as f:
                for line in iter(self.stream.readline, b""):
                    f.write(line)
                    f.flush()
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(rec, dict) and rec.get("type") == "assistant":
                        self.assistant += 1
                        if self.assistant > self.max_turns and not self.turn_limit_hit:
                            self.turn_limit_hit = True
                            self.on_limit()
        except Exception as exc:  # reported in meta.json, not swallowed
            self.error = repr(exc)


def docker_kill(name):
    subprocess.run(["docker", "kill", name], capture_output=True, check=False)


def execute(args, plan):
    run_dir, dirs = plan["run_dir"], plan["dirs"]
    if run_dir.exists():
        raise SystemExit(f"{run_dir} already exists: pick another --run N (no overwrites)")
    probe = subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True)
    if probe.returncode != 0:
        raise SystemExit(f"image {IMAGE} not found: build it with docker build -t {IMAGE} {HERE}")
    if not (KUNNA / ".git").exists():
        raise SystemExit(f"kuNNA repo not found at {KUNNA} (set KUNNA_REPO)")

    run_dir.mkdir(parents=True)
    started = time.monotonic()
    meta = {"run_id": plan["run_id"], "system": args.system, "round": args.round, "run": args.run,
            "ref": plan["ref"], "b_source": args.b_source if args.system == "B" else "commit",
            "image": IMAGE, "started_utc": utc_now(), "prompt_sha256": sha256_text(plan["prompt"]),
            "timeout_s": plan["timeout_s"], "max_turns": args.max_turns}
    home = Path(tempfile.mkdtemp(prefix=f"kunna-bench-{plan['run_id']}-home-"))
    home.chmod(0o700)
    dirs["home"] = home
    try:
        # 1. skill snapshot + version guard (before any container)
        if args.system == "A" or args.b_source == "commit":
            snapshot_from_commit(plan["ref"], dirs["skillrepo"])
        else:
            snapshot_from_worktree(dirs["skillrepo"])
        meta["skill_version"] = read_version(dirs["skillrepo"])
        if args.system == "A":
            meta["a_version"] = meta["skill_version"]
        else:  # B: compare with A's version as committed on --a-ref
            a_text = subprocess.run(git("show", f"{args.a_ref}:skills/subagent-pool/SKILL.md"),
                                    check=True, capture_output=True).stdout.decode("utf-8")
            meta["a_version"] = VERSION_RE.search(a_text).group(1)
            if meta["a_version"] == meta["skill_version"] and not args.allow_same_version:
                raise SystemExit(f"skill versions equal (A {meta['a_version']} == B {meta['skill_version']}): "
                                 "the comparison would measure nothing. Commit the B change or pass "
                                 "--allow-same-version")

        # 2. kuNNA copy: baseline, seed, git init and commit (diffs are measured from here)
        copy_kunna_baseline(dirs["kunna"])
        subprocess.run(git("init", "-q", cwd=dirs["kunna"]), check=True)
        if args.round in SEED:
            apply_seed(dirs["kunna"], SEED[args.round])
        subprocess.run(git("add", "-A", cwd=dirs["kunna"]), check=True)
        subprocess.run(git(*GIT_ID, "commit", "-q", "-m", "bench baseline", cwd=dirs["kunna"]), check=True)
        base_sha = subprocess.run(git("rev-parse", "HEAD", cwd=dirs["kunna"]), check=True,
                                  capture_output=True, text=True).stdout.strip()
        meta["base_sha"] = base_sha

        # 3. prompt, entry script, output dir, temp HOME with credentials
        dirs["out"].mkdir()
        shutil.copyfile(plan["prompt_path"], dirs["prompt"])
        write_entry(dirs["entry"], plan["timeout_s"])
        prepare_home(home)

        # 4. run the container
        name = f"kunna-bench-{plan['run_id']}"
        argv = docker_argv(name, os.getuid(), os.getgid(), dirs, plan["timeout_s"])
        meta["docker"] = shlex.join(argv)
        with open(dirs["out"] / "stderr.log", "wb") as err:
            proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=err)
            pump = Pump(proc.stdout, run_dir / "transcript.jsonl", args.max_turns,
                        on_limit=lambda: docker_kill(name))
            pump.start()
            timed_out = False
            try:
                proc.wait(timeout=plan["timeout_s"] + HOST_GRACE_S)
            except subprocess.TimeoutExpired:
                timed_out = True
                docker_kill(name)
                proc.wait()
            pump.join()
        if pump.error:
            raise SystemExit(f"transcript pump failed: {pump.error}")
        meta.update(exit_code=proc.returncode, timed_out=timed_out, turn_limit_hit=pump.turn_limit_hit,
                    assistant_messages=pump.assistant)

        # 5. outcome: diff vs baseline, session transcripts
        subprocess.run(git("add", "-A", cwd=dirs["kunna"]), check=True)
        diff = subprocess.run(git("diff", "--cached", "--binary", base_sha, cwd=dirs["kunna"]),
                              check=True, capture_output=True, text=True).stdout
        (run_dir / "final.diff").write_text(diff, encoding="utf-8")
        stat = subprocess.run(git("diff", "--cached", "--stat", base_sha, cwd=dirs["kunna"]),
                              check=True, capture_output=True, text=True).stdout
        (run_dir / "diffstat.txt").write_text(stat, encoding="utf-8")
        meta["session_files"] = copy_sessions(home, run_dir / "sessions")
    finally:
        # credentials never outlive the run, even on error
        remove_credentials(home)
        shutil.rmtree(home)
        meta["wall_s"] = round(time.monotonic() - started, 1)
        meta["ended_utc"] = utc_now()
        (run_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return meta


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--system", required=True, choices=("A", "B"))
    ap.add_argument("--round", required=True, choices=ROUNDS)
    ap.add_argument("--run", required=True, type=int)
    ap.add_argument("--dry-run", action="store_true", help="print commands and the prompt; run nothing")
    ap.add_argument("--timeout-min", type=float, default=DEFAULT_TIMEOUT_MIN)
    ap.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS,
                    help="host-side cap on assistant messages (claude has no --max-turns flag)")
    ap.add_argument("--a-ref", default="master")
    ap.add_argument("--b-ref", default="feat/case-flow")
    ap.add_argument("--b-source", choices=("worktree", "commit"), default="worktree",
                    help="worktree = working tree (has the uncommitted v9.11.0 SKILL.md); commit = git archive of --b-ref")
    ap.add_argument("--allow-same-version", action="store_true")
    args = ap.parse_args(argv)
    if args.run < 1:
        ap.error("--run must be >= 1")
    if args.max_turns < 1 or args.timeout_min <= 0:
        ap.error("--max-turns and --timeout-min must be positive")
    return args


def main(argv=None):
    args = parse_args(argv)
    plan = build_plan(args)
    if args.dry_run:
        print_dry_run(args, plan)
        return 0
    meta = execute(args, plan)
    print(f"run {meta['run_id']}: exit {meta['exit_code']}, wall {meta['wall_s']} s, "
          f"timed_out={meta['timed_out']}, turn_limit_hit={meta['turn_limit_hit']}")
    print(f"dir: {plan['run_dir']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
