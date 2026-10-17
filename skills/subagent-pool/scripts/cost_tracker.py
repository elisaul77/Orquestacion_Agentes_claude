#!/usr/bin/env python3
"""Per-session token ledger for Claude Code (subagent-pool v9.6).

Hook mode (Stop hook, JSON on stdin with `session_id` and `transcript_path`):
    python3 cost_tracker.py hook
  Sums usage of the main transcript plus `<session>/subagents/*.jsonl`, per model, and appends ONE
  cumulative snapshot row to ~/.claude/metrics/costs.jsonl. Never fails the session: errors exit 0.

Report mode:
    python3 cost_tracker.py report [--days N] [--csv]
  Takes the latest snapshot per session and aggregates by day and model.
  Cost is only estimated when ~/.claude/metrics/prices.json exists:
    {"claude-opus-5-5": {"input": 5, "output": 25, "cache_write": 6.25, "cache_read": 0.5}, ...}  (USD per MTok)
  No guessed prices are shipped: tokens are the measurement, dollars are optional.
"""
import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

METRICS = Path(os.environ.get("POOL_METRICS_DIR", Path.home() / ".claude" / "metrics"))
LEDGER = METRICS / "costs.jsonl"
PRICES = METRICS / "prices.json"
FIELDS = ("input", "output", "cache_write", "cache_read")


def usage_by_model(paths):
    """Sum usage per model across transcripts. Streaming repeats a message id: count each id once."""
    seen, totals = set(), {}
    for path in paths:
        try:
            lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            msg = rec.get("message") if isinstance(rec, dict) else None
            if rec.get("type") != "assistant" or not isinstance(msg, dict):
                continue
            usage, mid = msg.get("usage") or {}, msg.get("id")
            if not usage or (mid and mid in seen):
                continue
            if mid:
                seen.add(mid)
            t = totals.setdefault(msg.get("model") or "unknown", dict.fromkeys(FIELDS, 0))
            t["input"] += usage.get("input_tokens") or 0
            t["output"] += usage.get("output_tokens") or 0
            t["cache_write"] += usage.get("cache_creation_input_tokens") or 0
            t["cache_read"] += usage.get("cache_read_input_tokens") or 0
    totals.pop("<synthetic>", None)
    return totals


def transcripts_for(transcript_path):
    main = Path(transcript_path)
    subdir = main.with_suffix("") / "subagents"
    return [main, *sorted(subdir.glob("*.jsonl"))] if subdir.is_dir() else [main]


def hook(stdin_text):
    data = json.loads(stdin_text or "{}")
    tp = data.get("transcript_path")
    if not tp:
        return None
    row = {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "session_id": data.get("session_id") or Path(tp).stem,
        "cwd": data.get("cwd"),
        "models": usage_by_model(transcripts_for(tp)),
    }
    METRICS.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    return row


def latest_rows(rows):
    by = {}
    for r in rows:
        k = r.get("session_id")
        if k not in by or str(r.get("timestamp")) > str(by[k].get("timestamp")):
            by[k] = r
    return list(by.values())


def cost(model, t, prices):
    p = prices.get(model)
    if not p:
        return None
    return sum(t[f] * p.get(f, 0) for f in FIELDS) / 1e6


def report(rows, prices, days=None, as_csv=False, today=None):
    rows = latest_rows(rows)
    if days:
        cutoff = ((today or dt.date.today()) - dt.timedelta(days=days - 1)).isoformat()
        rows = [r for r in rows if str(r.get("timestamp", ""))[:10] >= cutoff]
    agg = {}
    for r in rows:
        day = str(r.get("timestamp", ""))[:10]
        for model, t in (r.get("models") or {}).items():
            a = agg.setdefault((day, model), dict.fromkeys(FIELDS, 0) | {"sessions": 0})
            for f in FIELDS:
                a[f] += t.get(f, 0)
            a["sessions"] += 1
    out = []
    if as_csv:
        out.append("day,model,sessions," + ",".join(FIELDS) + ",usd")
    else:
        out.append(f"{'day':<10} {'model':<26} {'ses':>4} {'input':>9} {'output':>9} {'c.write':>10} {'c.read':>12} {'usd':>8}")
    total_usd, priced = 0.0, True
    for (day, model), a in sorted(agg.items()):
        usd = cost(model, a, prices)
        priced &= usd is not None
        total_usd += usd or 0
        u = "" if usd is None else f"{usd:.2f}"
        if as_csv:
            out.append(f"{day},{model},{a['sessions']}," + ",".join(str(a[f]) for f in FIELDS) + f",{u}")
        else:
            out.append(f"{day:<10} {model:<26} {a['sessions']:>4} {a['input']:>9} {a['output']:>9} "
                       f"{a['cache_write']:>10} {a['cache_read']:>12} {u or '-':>8}")
    if not as_csv:
        out.append(f"sessions: {len(rows)} · total usd: " + (f"{total_usd:.2f}" if priced and agg else
                   f"{total_usd:.2f} (partial — models missing from {PRICES})" if agg else "-"))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("hook")
    r = sub.add_parser("report")
    r.add_argument("--days", type=int)
    r.add_argument("--csv", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "hook":
        try:
            hook(sys.stdin.read())
        except Exception as exc:  # a broken ledger must never block a session
            print(f"cost_tracker: {exc}", file=sys.stderr)
        return 0
    if not LEDGER.exists():
        print(f"No ledger yet: {LEDGER}. Enable the Stop hook and finish a session.")
        return 0
    rows = [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]
    prices = json.loads(PRICES.read_text()) if PRICES.exists() else {}
    print(report(rows, prices, args.days, args.csv))
    return 0


if __name__ == "__main__":
    sys.exit(main())
