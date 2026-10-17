#!/usr/bin/env python3
"""A/B bench runner: the same kuNNA challenge against two subagent-pool versions, one container each.

    python3 competition/run.py --system A|B --round bug|improve --run N [--dry-run] [--model M]

  A = subagent-pool from git `master`          (--a-ref, default master)
  B = subagent-pool from git `4de0831` (v9.11.0 case flow)   (--b-ref, default 4de0831)
      --b-source commit   (default) git archive of --b-ref
      --b-source worktree explicit only; refuses if skills/ or agents/ have uncommitted changes
  Both run in the same image (competition/Dockerfile) with the same prompt (prompts/<round>.md).

Every ref is resolved ONCE with `git rev-parse` before anything runs; the resolved shas (a_sha, b_sha,
kunna_sha) are written to meta.json and used for every later step.

Per run, under competition/runs/<system>-<round>-<N>/:
  skillrepo/        read-only snapshot of skills/ and agents/ (mounted at /skillrepo)
  kunna/            fresh kuNNA copy (git archive <kunna_sha>), git initialised, seed applied for round bug
  out/              install.log, stderr.log
  transcript.jsonl  stream-json from `claude -p`
  sessions/         Claude session JSONL copied out of the temp HOME (token accounting)
  codex_sessions/   Codex rollout JSONL copied out of the temp HOME (token accounting, if any)
  final.diff, diffstat.txt   judged material: plans/, .claude/, caches excluded
  artifacts.diff    the excluded paths (never shown to judges)
  prompt.md, entry.sh, meta.json

Credentials: copied into a temp HOME OUTSIDE the repo (never under competition/), chmod 600, removed
and the HOME deleted in a finally block. After every run the run dir is grepped for the credential
values; a hit fails the run with exit 3.
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
import signal
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
EXCLUDED_DIRS = ("plans", ".claude", ".pytest_cache", "__pycache__")  # never in the judged diff
DEFAULT_A_REF = "master"
DEFAULT_B_REF = "4de0831"
DEFAULT_KUNNA_REF = "HEAD"
DEFAULT_TIMEOUT_MIN = 45
DEFAULT_MAX_TURNS = 400       # counts main-agent assistant messages only (no parent_tool_use_id)
HOST_GRACE_S = 180            # the host waits this much longer than claude's own timeout before killing
ENTRY_ADDONS = "teams,codex"
CREDENTIAL_EXIT = 3
GIT_ID = ["-c", "user.name=bench", "-c", "user.email=bench@localhost", "-c", "commit.gpgsign=false"]
# container hardening: default bridge network (the container can reach the host LAN); no home dir and no
# docker socket are mounted; only the temp HOME (credentials, chmod 600) and the run dir are bind-mounted
HARDENING = ["--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--pids-limit", "512", "--memory", "6g"]
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


# ---------- pins (B1, B2) ----------

def rev_parse(ref, cwd=REPO):
    """Resolve a ref to a full commit sha, or refuse."""
    proc = subprocess.run(git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", cwd=cwd),
                          capture_output=True, text=True)
    sha = proc.stdout.strip()
    if proc.returncode != 0 or not sha:
        raise SystemExit(f"cannot resolve ref {ref!r} in {cwd}: {proc.stderr.strip() or 'unknown ref'}")
    return sha


def dirty_snapshot_paths(repo=REPO):
    out = subprocess.run(git("status", "--porcelain", "--", *SNAPSHOT_PATHS, cwd=repo),
                         check=True, capture_output=True, text=True).stdout
    return [line for line in out.splitlines() if line.strip()]


def assert_clean_snapshot(repo=REPO):
    dirty = dirty_snapshot_paths(repo)
    if dirty:
        raise SystemExit("refusing --b-source worktree: uncommitted changes under skills/ or agents/:\n  "
                         + "\n  ".join(dirty) + "\nCommit them, or use --b-source commit (the default).")


def resolve_pins(args):
    """Every ref resolved once. Worktree mode is only allowed when it equals HEAD and skills/agents are clean."""
    pins = {
        "a_ref": args.a_ref, "a_sha": rev_parse(args.a_ref),
        "b_ref": args.b_ref, "b_sha": rev_parse(args.b_ref),
        "kunna_ref": args.kunna_ref, "kunna_sha": rev_parse(args.kunna_ref, cwd=KUNNA),
    }
    if args.system == "B" and args.b_source == "worktree":
        assert_clean_snapshot(REPO)
        head = rev_parse("HEAD")
        if pins["b_sha"] != head:
            raise SystemExit(f"--b-source worktree snapshots the working tree, which is HEAD ({head[:7]}); "
                             f"--b-ref {args.b_ref} resolves to {pins['b_sha'][:7]}. Use --b-source commit.")
    return pins


def extract_tar(data, dest):
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        if hasattr(tarfile, "data_filter"):
            tar.extractall(dest, filter="data")
        else:
            tar.extractall(dest)  # noqa: S202 - trusted: our own git archive output


def snapshot_from_commit(sha, dest):
    data = subprocess.run(git("archive", "--format=tar", sha, *SNAPSHOT_PATHS),
                          check=True, capture_output=True).stdout
    extract_tar(data, dest)


def snapshot_from_worktree(dest):
    assert_clean_snapshot(REPO)
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


def copy_kunna_baseline(dest, sha):
    """kuNNA at an exact commit (B2): never HEAD, so the copy is reproducible."""
    data = subprocess.run(git("archive", "--format=tar", sha, cwd=KUNNA),
                          check=True, capture_output=True).stdout
    extract_tar(data, dest)


# ---------- blind hygiene (B4): judged diff excludes workflow artifacts ----------

def excluded_pathspecs():
    return [f":(exclude,glob)**/{d}/**" for d in EXCLUDED_DIRS]


def included_pathspecs():
    return [f":(glob)**/{d}/**" for d in EXCLUDED_DIRS]


def staged_diff(cwd, base, *pathspec, stat=False):
    mode = "--stat" if stat else "--binary"
    return subprocess.run(git("diff", "--cached", mode, base, "--", *pathspec, cwd=cwd),
                          check=True, capture_output=True, text=True).stdout


def split_diff(cwd, base):
    """(judged diff, excluded diff, judged stat) of the staged tree against base."""
    judged = staged_diff(cwd, base, ".", *excluded_pathspecs())
    artifacts = staged_diff(cwd, base, *included_pathspecs())
    stat = staged_diff(cwd, base, ".", *excluded_pathspecs(), stat=True)
    return judged, artifacts, stat


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


def docker_argv(name, uid, gid, dirs, timeout_s, model=None):
    argv = [
        "docker", "run", "--rm", "--name", name,
        *HARDENING,
        "--user", f"{uid}:{gid}",
        "-e", "HOME=/bench/home",
        "-e", "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1",
        "-e", f"BENCH_TIMEOUT_S={timeout_s}",
        "-e", "PYTHONDONTWRITEBYTECODE=1",
    ]
    if model:  # pinned only when asked; otherwise the CLI default is used and recorded from the init record
        argv += ["-e", f"ANTHROPIC_MODEL={model}"]
    argv += [
        "-v", f"{dirs['skillrepo']}:/skillrepo:ro",
        "-v", f"{dirs['kunna']}:/work",
        "-v", f"{dirs['home']}:/bench/home",
        "-v", f"{dirs['prompt']}:/bench/prompt.md:ro",
        "-v", f"{dirs['entry']}:/bench/entry.sh:ro",
        "-v", f"{dirs['out']}:/bench/out",
        "-w", "/work",
        IMAGE, "bash", "/bench/entry.sh",
    ]
    return argv


def credential_pairs():
    home = Path.home()
    return [
        (home / ".claude" / ".credentials.json", Path(".claude") / ".credentials.json"),
        (home / ".codex" / "auth.json", Path(".codex") / "auth.json"),
    ]


def _json_strings(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _json_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _json_strings(v)
    elif isinstance(obj, str):
        yield obj


def credential_values(paths):
    """Secret-looking strings (>= 20 chars, no spaces) inside the credential files, for the leak grep."""
    values = set()
    for p in paths:
        for s in _json_strings(json.loads(Path(p).read_text(encoding="utf-8"))):
            if len(s) >= 20 and not any(ch.isspace() for ch in s):
                values.add(s)
    return sorted(values)


def find_secret_leaks(root, values):
    """Relative paths under root that contain any credential value. Empty list = clean."""
    leaks = []
    encoded = [v.encode("utf-8") for v in values]
    if not encoded:
        return leaks
    for f in sorted(Path(root).rglob("*")):
        if not f.is_file():
            continue
        data = f.read_bytes()
        if any(needle in data for needle in encoded):
            leaks.append(str(f.relative_to(root)))
    return leaks


def prepare_home(home):
    """Temp HOME with credentials (chmod 600) and a minimal ~/.claude.json. Returns the secret values."""
    for src, _ in credential_pairs():
        if not src.is_file():
            raise SystemExit(f"missing {src}: log in on the host first (claude / codex login)")
    for src, rel in credential_pairs():
        dst = home / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        dst.chmod(0o600)
    (home / ".claude.json").write_text(json.dumps(CLAUDE_JSON, indent=2), encoding="utf-8")
    return credential_values([src for src, _ in credential_pairs()])


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


def copy_codex_sessions(home, dest):
    """Only the rollout JSONL under ~/.codex/sessions. auth.json is never copied."""
    sessions = home / ".codex" / "sessions"
    if not sessions.is_dir():
        return 0
    n = 0
    for f in sessions.rglob("*.jsonl"):
        target = dest / f.relative_to(sessions)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, target)
        n += 1
    return n


# ---------- stream records: turn cap (B3) ----------

def classify_record(rec):
    """'main' | 'subagent' | None. Only main-agent assistant messages count toward --max-turns."""
    if not isinstance(rec, dict) or rec.get("type") != "assistant":
        return None
    return "subagent" if rec.get("parent_tool_use_id") else "main"


def count_turns(records):
    main = sum(1 for r in records if classify_record(r) == "main")
    sub = sum(1 for r in records if classify_record(r) == "subagent")
    return main, sub


# ---------- signals (N5) ----------

def raise_exit(signum, _frame):
    """SIGTERM/SIGINT become SystemExit so the finally block (kill, credentials, HOME, meta) still runs."""
    raise SystemExit(128 + signum)


def install_signal_handlers():
    signal.signal(signal.SIGTERM, raise_exit)
    signal.signal(signal.SIGINT, raise_exit)


# ---------- plan (shared by dry-run and real run) ----------

def build_plan(args):
    pins = resolve_pins(args)
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
    ref_sha = pins["a_sha"] if args.system == "A" else pins["b_sha"]
    if args.system == "A" or args.b_source == "commit":
        snap = f"git archive {ref_sha} {' '.join(SNAPSHOT_PATHS)} | tar -x -C {dirs['skillrepo']}"
    else:
        snap = f"copy tracked+untracked files under {' '.join(p + '/' for p in SNAPSHOT_PATHS)} of the working tree -> {dirs['skillrepo']}"
    kunna_cmds = [f"git -C {KUNNA} archive --format=tar {pins['kunna_sha']} | tar -x -C {dirs['kunna']}",
                  f"git -C {dirs['kunna']} init -q"]
    if args.round in SEED:
        kunna_cmds.append(f"git -C {dirs['kunna']} apply {SEED[args.round]} && "
                          f"git -C {dirs['kunna']} apply --reverse --check {SEED[args.round]}  # seeded bug, verified")
    kunna_cmds.append(f"git -C {dirs['kunna']} add -A && git {' '.join(GIT_ID)} commit -q -m 'bench baseline'")
    prompt_path = HERE / "prompts" / f"{args.round}.md"
    prompt = prompt_path.read_text(encoding="utf-8")
    return {
        "run_id": run_id, "run_dir": run_dir, "timeout_s": timeout_s, "dirs": dirs,
        "pins": pins, "ref_sha": ref_sha, "snapshot": snap, "kunna_cmds": kunna_cmds,
        "docker": docker_argv(f"kunna-bench-{run_id}", os.getuid(), os.getgid(), dirs, timeout_s, args.model),
        "prompt": prompt, "prompt_path": prompt_path,
    }


def print_dry_run(args, plan):
    def say(msg):
        print(f"[dry-run] {msg}")
    p = plan["pins"]
    say(f"run id: {plan['run_id']}  (nothing is created, nothing is executed)")
    say(f"run dir: {plan['run_dir']}")
    say(f"pins: A {args.a_ref} = {p['a_sha']}; B {args.b_ref} = {p['b_sha']} (source {args.b_source if args.system == 'B' else 'commit'}); "
        f"kuNNA {args.kunna_ref} = {p['kunna_sha']}")
    say(f"skill snapshot ({args.system}, sha={plan['ref_sha']}): {plan['snapshot']}")
    say("version guard: read skills/subagent-pool/SKILL.md from both snapshots; refuse if equal "
        "(override: --allow-same-version)")
    for c in plan["kunna_cmds"]:
        say(f"kuNNA: {c}")
    say(f"temp HOME: mkdtemp outside the repo (mode 700); copy {Path('~/.claude/.credentials.json')} and "
        f"{Path('~/.codex/auth.json')} (chmod 600); write minimal ~/.claude.json")
    say(f"entry script: {plan['run_dir'] / 'entry.sh'} (runs install.py --with {ENTRY_ADDONS}, then claude -p)")
    say(f"model: {args.model or 'CLI default (not pinned; the init record of the stream is recorded)'}")
    say("versions: claude and codex versions are read from the image before the run (recorded in meta.json)")
    say(f"claude env: CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1, timeout {plan['timeout_s']} s, "
        f"host kill at +{HOST_GRACE_S} s, max main-agent messages {args.max_turns} (subagent messages logged, not capped)")
    say(f"container hardening: {' '.join(HARDENING)}; default bridge network; no docker socket, no home dir")
    say("docker command:")
    print("  " + shlex.join(plan["docker"]))
    say(f"after the run: judged diff = excluding {', '.join(EXCLUDED_DIRS)} -> final.diff; the rest -> artifacts.diff; "
        f"copy sessions (Claude and Codex); delete credentials; delete temp HOME; grep run dir for credential values (exit {CREDENTIAL_EXIT} on a hit)")
    say(f"prompt: {plan['prompt_path']} ({len(plan['prompt'])} chars, sha256 {sha256_text(plan['prompt'])[:16]})")
    print("----- prompt (exact) -----")
    print(plan["prompt"], end="" if plan["prompt"].endswith("\n") else "\n")
    print("----- end prompt -----")


# ---------- real run ----------

class Pump(threading.Thread):
    """Copies container stdout to transcript.jsonl; counts turns (host-side cap) and records the init model."""

    def __init__(self, stream, path, max_turns, on_limit):
        super().__init__(daemon=True)
        self.stream, self.path, self.max_turns, self.on_limit = stream, path, max_turns, on_limit
        self.assistant = 0            # main-agent assistant messages: the cap counts these only
        self.subagent_assistant = 0   # logged, not capped
        self.model_reported = None
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
                    if not isinstance(rec, dict):
                        continue
                    if rec.get("type") == "system" and rec.get("subtype") == "init" and self.model_reported is None:
                        self.model_reported = rec.get("model")
                    kind = classify_record(rec)
                    if kind == "subagent":
                        self.subagent_assistant += 1
                    elif kind == "main":
                        self.assistant += 1
                        if self.assistant > self.max_turns and not self.turn_limit_hit:
                            self.turn_limit_hit = True
                            self.on_limit()
        except Exception as exc:  # reported in meta.json, not swallowed
            self.error = repr(exc)


def docker_kill(name):
    subprocess.run(["docker", "kill", name], capture_output=True, check=False)


def image_versions():
    """claude and codex versions as installed in the bench image (no model call)."""
    proc = subprocess.run(["docker", "run", "--rm", "--entrypoint", "bash", IMAGE, "-c",
                           "claude --version; echo ---; codex --version"],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"cannot read tool versions from {IMAGE}: {proc.stderr.strip()}")
    claude, _, codex = proc.stdout.partition("---")
    return {"claude": claude.strip() or "unknown", "codex": codex.strip() or "unknown"}


def execute(args, plan):
    run_dir, dirs, pins = plan["run_dir"], plan["dirs"], plan["pins"]
    if run_dir.exists():
        raise SystemExit(f"{run_dir} already exists: pick another --run N (no overwrites)")
    probe = subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True, text=True)
    if probe.returncode != 0:
        raise SystemExit(f"image {IMAGE} not found: build it with docker build -t {IMAGE} {HERE}")
    if not (KUNNA / ".git").exists():
        raise SystemExit(f"kuNNA repo not found at {KUNNA} (set KUNNA_REPO)")
    versions = image_versions()

    run_dir.mkdir(parents=True)
    started = time.monotonic()
    name = f"kunna-bench-{plan['run_id']}"
    meta = {"run_id": plan["run_id"], "system": args.system, "round": args.round, "run": args.run,
            "a_ref": pins["a_ref"], "a_sha": pins["a_sha"], "b_ref": pins["b_ref"], "b_sha": pins["b_sha"],
            "b_source": args.b_source if args.system == "B" else "commit",
            "skill_sha": plan["ref_sha"],
            "kunna_ref": pins["kunna_ref"], "kunna_sha": pins["kunna_sha"],
            "image": IMAGE,
            "claude_version": versions["claude"], "codex_version": versions["codex"],
            "model_requested": args.model, "model_reported": None,
            "started_utc": utc_now(), "prompt_sha256": sha256_text(plan["prompt"]),
            "timeout_s": plan["timeout_s"], "max_turns": args.max_turns, "hardening": HARDENING}
    image_id = subprocess.run(["docker", "image", "inspect", "-f", "{{.Id}}", IMAGE],
                              capture_output=True, text=True, check=True).stdout.strip()
    meta["image_id"] = image_id
    home = Path(tempfile.mkdtemp(prefix=f"kunna-bench-{plan['run_id']}-home-"))
    home.chmod(0o700)
    dirs["home"] = home
    proc, pump, secret_values = None, None, []
    try:
        # 1. skill snapshot + version guard (before any container)
        if args.system == "A" or args.b_source == "commit":
            snapshot_from_commit(plan["ref_sha"], dirs["skillrepo"])
        else:
            snapshot_from_worktree(dirs["skillrepo"])
        meta["skill_version"] = read_version(dirs["skillrepo"])
        if args.system == "A":
            meta["a_version"] = meta["skill_version"]
        else:  # B: compare with A's version as committed on a_sha
            a_text = subprocess.run(git("show", f"{pins['a_sha']}:skills/subagent-pool/SKILL.md"),
                                    check=True, capture_output=True).stdout.decode("utf-8")
            meta["a_version"] = VERSION_RE.search(a_text).group(1)
            if meta["a_version"] == meta["skill_version"] and not args.allow_same_version:
                raise SystemExit(f"skill versions equal (A {meta['a_version']} == B {meta['skill_version']}): "
                                 "the comparison would measure nothing. Commit the B change or pass "
                                 "--allow-same-version")

        # 2. kuNNA copy at the pinned sha: baseline, seed, git init and commit (diffs are measured from here)
        copy_kunna_baseline(dirs["kunna"], pins["kunna_sha"])
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
        secret_values = prepare_home(home)

        # 4. run the container
        argv = docker_argv(name, os.getuid(), os.getgid(), dirs, plan["timeout_s"], args.model)
        meta["docker"] = shlex.join(argv)
        timed_out = False
        with open(dirs["out"] / "stderr.log", "wb") as err:
            proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=err)
            pump = Pump(proc.stdout, run_dir / "transcript.jsonl", args.max_turns,
                        on_limit=lambda: docker_kill(name))
            pump.start()
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
                    assistant_messages=pump.assistant, subagent_assistant_messages=pump.subagent_assistant,
                    model_reported=pump.model_reported)

        # 5. outcome: judged diff vs baseline, artifacts apart
        subprocess.run(git("add", "-A", cwd=dirs["kunna"]), check=True)
        judged, artifacts, stat = split_diff(dirs["kunna"], base_sha)
        (run_dir / "final.diff").write_text(judged, encoding="utf-8")
        (run_dir / "artifacts.diff").write_text(artifacts, encoding="utf-8")
        (run_dir / "diffstat.txt").write_text(stat, encoding="utf-8")
    finally:
        # kill anything still running (SIGTERM/SIGINT, errors), then keep the evidence before the HOME goes
        if proc is not None and proc.poll() is None:
            docker_kill(name)
            proc.wait()
        meta["session_files"] = copy_sessions(home, run_dir / "sessions")
        meta["codex_session_files"] = copy_codex_sessions(home, run_dir / "codex_sessions")
        # credentials never outlive the run, even on error
        remove_credentials(home)
        shutil.rmtree(home)
        meta["wall_s"] = round(time.monotonic() - started, 1)
        meta["ended_utc"] = utc_now()
        # N5: the run dir must not contain any credential value
        leaks = find_secret_leaks(run_dir, secret_values)
        meta["credential_leaks"] = leaks
        (run_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if leaks:
            raise SystemExit(f"{CREDENTIAL_EXIT}: credential value found in {leaks}: the run is not usable, "
                             "delete those files and fix the leak before scoring")
    return meta


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--system", required=True, choices=("A", "B"))
    ap.add_argument("--round", required=True, choices=ROUNDS)
    ap.add_argument("--run", required=True, type=int)
    ap.add_argument("--dry-run", action="store_true", help="print commands and the prompt; run nothing")
    ap.add_argument("--timeout-min", type=float, default=DEFAULT_TIMEOUT_MIN)
    ap.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS,
                    help="host-side cap on main-agent assistant messages (subagent messages are not counted)")
    ap.add_argument("--model", default=None,
                    help="pin the model through ANTHROPIC_MODEL; default: CLI default, recorded from the stream")
    ap.add_argument("--a-ref", default=DEFAULT_A_REF)
    ap.add_argument("--b-ref", default=DEFAULT_B_REF)
    ap.add_argument("--kunna-ref", default=DEFAULT_KUNNA_REF, help="kuNNA commit to test (resolved once)")
    ap.add_argument("--b-source", choices=("commit", "worktree"), default="commit",
                    help="commit = git archive of --b-ref (default); worktree = working tree, explicit only, "
                         "refused while skills/ or agents/ have uncommitted changes")
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
    install_signal_handlers()
    meta = execute(args, plan)
    print(f"run {meta['run_id']}: exit {meta['exit_code']}, wall {meta['wall_s']} s, "
          f"timed_out={meta['timed_out']}, turn_limit_hit={meta['turn_limit_hit']}, "
          f"model={meta['model_reported']}")
    print(f"dir: {plan['run_dir']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
