#!/usr/bin/env python3
"""Mirror Claude agent files (*.agent.md) into Codex agent roles (*.agent.toml) (subagent-pool v9.8).

    python3 sync_codex_agents.py [--src DIR ...] [--dest DIR] [--check] [--only NAME ...]

Codex `collaboration.spawn_agent` can use custom roles from ~/.codex/agents/*.toml (name, description,
developer_instructions). Codex re-reads that folder on every `codex exec`, so a synced role is usable at once.
Each generated file starts with `# generated-by: subagent-pool sync · source-sha256: <hash>`; --check compares that
hash with the source and lists stale/missing/foreign roles without writing (exit 1 if any; also when an --only
name has no source agent). Files without the marker are
never overwritten (they belong to someone else). Default src: ~/.claude/agents; codex-agent is skipped (it is the
Claude-side bridge to Codex, not a Codex role), and so are council-* agents (they debate through Claude's SendMessage).
"""
import argparse
import hashlib
import re
import sys
from pathlib import Path

SKIP = {"codex-agent"}
SKIP_PREFIX = ("council-",)  # council members need Claude's SendMessage; Codex has no equivalent role tool
MARK = "# generated-by: subagent-pool sync · source-sha256: "


def parse(md_text):
    """(name, description, body) from an .agent.md file; description may be a folded YAML block."""
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", md_text, re.S)
    if not m:
        raise ValueError("no frontmatter")
    front, body = m.groups()
    name = re.search(r"^name:\s*(.+)$", front, re.M)
    if not name:
        raise ValueError("no name")
    desc = ""
    d = re.search(r"^description:\s*(.*)$", front, re.M)
    if d:
        first = d.group(1).strip()
        block = re.match(r"^([>|])[+-]?\d?\s*(#.*)?$", first)
        if block:
            raw = []
            for line in front[d.end():].splitlines()[1:]:
                if line.strip() and not line.startswith((" ", "\t")):
                    break
                raw.append(line)
            ind = min((len(l) - len(l.lstrip()) for l in raw if l.strip()), default=0)
            raw = [l[ind:] for l in raw]
            while raw and not raw[-1].strip():
                raw.pop()
            if block.group(1) == "|":
                desc = "\n".join(raw)
            else:  # folded: lines join with spaces, blank lines and more-indented lines keep their breaks
                paras, cur = [], []
                for l in raw:
                    if not l.strip() or l.startswith((" ", "\t")):
                        if cur:
                            paras.append(" ".join(cur))
                            cur = []
                        if l.strip():
                            paras.append(l)
                    else:
                        cur.append(l.strip())
                if cur:
                    paras.append(" ".join(cur))
                desc = "\n".join(paras)
        else:
            q = first[:1]
            desc = first[1:-1] if q in "'\"" and len(first) > 1 and first.endswith(q) else first
    n = name.group(1).strip()
    if n[:1] in "'\"" and len(n) > 1 and n.endswith(n[0]):
        n = n[1:-1]
    return n, desc, body.strip() + "\n"


def _esc(s, keep):
    """TOML basic-string escaping: backslash, quote, and every control char (U+0000-001F, U+007F) except `keep`."""
    out = []
    for ch in s:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch in keep:
            out.append(ch)
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append({"\n": "\\n", "\t": "\\t", "\r": "\\r"}.get(ch, f"\\u{ord(ch):04X}"))
        else:
            out.append(ch)
    return "".join(out)


def toml_str(s):
    return '"' + _esc(s, "") + '"'


def toml_multiline(s):
    return '"""\n' + _esc(s, "\n\t") + '"""'


def render(md_text):
    name, desc, body = parse(md_text)
    sha = hashlib.sha256(md_text.encode()).hexdigest()
    out = (f"{MARK}{sha}\n"
           f"name = {toml_str(name)}\n"
           f"description = {toml_str(desc)}\n"
           f"developer_instructions = {toml_multiline(body)}\n")
    return name, sha, out


def plan(srcs, dest, only=()):
    """[(name, action, target, content)] with action in create|update|ok|foreign."""
    rows = []
    for src in srcs:
        for f in sorted(Path(src).glob("*.md")):
            text = f.read_text()
            try:
                name, sha, content = render(text)
            except ValueError:
                continue
            if name in SKIP or name.startswith(SKIP_PREFIX) or (only and name not in only):
                continue
            target = Path(dest) / f"{name}.agent.toml"
            if not target.exists():
                action = "create"
            else:
                first = target.read_text().splitlines()[:1]
                if not first or not first[0].startswith(MARK):
                    action = "foreign"
                elif first[0] == MARK + sha:
                    action = "ok"
                else:
                    action = "update"
            rows.append((name, action, target, content))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", action="append")
    ap.add_argument("--dest", default=str(Path.home() / ".codex" / "agents"))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--only", action="append", default=[])
    args = ap.parse_args(argv)
    srcs = args.src or [str(Path.home() / ".claude" / "agents")]
    rows = plan(srcs, args.dest, set(args.only))
    missing = sorted(set(args.only) - {r[0] for r in rows})
    for name in missing:
        print(f"missing-source: {name} (no agent with that name in {', '.join(srcs)})")
    stale = len(missing)
    for name, action, target, content in rows:
        if action in ("create", "update"):
            stale += 1
            if not args.check:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
        print(f"{action if args.check or action in ('ok', 'foreign') else action + 'd'}: {name} → {target}")
    if any(a == "foreign" for _, a, _, _ in rows):
        print("foreign = existing file without the sync marker (e.g. Codex's own import); left untouched."
              " Delete it to let sync manage that role.")
    foreign = sum(a == "foreign" for _, a, _, _ in rows)
    if args.check:
        return 1 if stale or foreign else 0
    return 1 if missing or foreign else 0


if __name__ == "__main__":
    sys.exit(main())
