#!/usr/bin/env python3
"""Aggregate score.json and blind judge verdicts into competition/REPORT.md.

    python3 competition/report.py            # reads runs/*/score.json, judgments/*.json, runs/blind_key.json

Judge verdict file (written by hand from the judge's output, one per judge per blind id):
    judgments/<judge>-<blind_id>.json
    {"judge": "claude|codex", "blind_id": "a1b2c3",
     "scores": {"correctness": 1-5, "root_cause": 0-2, "minimality": 1-5, "test_quality": 1-5, "safety": 1-5},
     "verdict": "pass|partial|fail", "notes": "..."}
"""
import datetime as dt
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
JUDGE_KEYS = ("correctness", "root_cause", "minimality", "test_quality", "safety")
CAVEAT = ("**n is small.** Each cell has a handful of runs (see the n column). With n this small a "
          "difference between systems is an observation to repeat, not a result. Variance between runs of the "
          "same system is not measured here; treat means as indicative and check the per-run rows.")


def mean(values):
    vals = [v for v in values if v is not None]
    return round(statistics.mean(vals), 2) if vals else None


def load_scores(runs_dir):
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(runs_dir.glob("*/score.json"))]


def load_judgments(judg_dir, key):
    out = []
    for p in sorted(judg_dir.glob("*.json")) if judg_dir.is_dir() else []:
        j = json.loads(p.read_text(encoding="utf-8"))
        run_id = key.get(j.get("blind_id"))
        if run_id is None:
            raise SystemExit(f"{p.name}: blind_id {j.get('blind_id')!r} not in runs/blind_key.json")
        j["run_id"] = run_id
        out.append(j)
    return out


def judge_mean(judgments, run_id, judge):
    rows = [j for j in judgments if j["run_id"] == run_id and j.get("judge") == judge]
    if not rows:
        return None
    total = [sum(j["scores"][k] for k in JUDGE_KEYS) for j in rows]
    return mean(total)


def row(score, judgments):
    h, g = score.get("hidden") or {}, score.get("regression") or {}
    tok = score["tokens"]["total"]
    tokens = sum(tok.values())
    subs = sum(score.get("subagents", {}).values())
    return {
        "run_id": score["run_id"], "system": score["system"], "round": score["round"], "run": score["run"],
        "codex": score.get("codex", True),
        "hidden": f"{h.get('passed', '-')}/{h.get('total', '-')}",
        "hidden_ok": h.get("ok"),
        "regression": f"{g.get('still_passing', '-')}/{g.get('baseline_passing', '-')}",
        "regression_ok": g.get("ok"),
        "wall_min": round((score.get("wall_s") or 0) / 60, 1),
        "tokens": tokens, "subagents": subs, "reviews": score.get("review_rounds", 0),
        "reroute_mentions": score.get("reroute_mentions", 0), "council": bool(score.get("council_convened")),
        "risky": len(score.get("risky_actions") or []), "exit": score.get("exit_code"),
        "claude_judge": judge_mean(judgments, score["run_id"], "claude"),
        "codex_judge": judge_mean(judgments, score["run_id"], "codex"),
    }


def cells(rows):
    grouped = {}
    for r in rows:
        grouped.setdefault((r["system"], r["round"], r["codex"]), []).append(r)
    out = []
    for (system, rnd, codex), rs in sorted(grouped.items()):
        out.append({
            "system": system, "round": rnd, "codex": codex, "n": len(rs),
            "hidden_pass_rate": f"{sum(1 for r in rs if r['hidden_ok'])}/{len(rs)}",
            "regression_ok": f"{sum(1 for r in rs if r['regression_ok'])}/{len(rs)}",
            "wall_min": mean([r["wall_min"] for r in rs]),
            "tokens": mean([r["tokens"] for r in rs]),
            "subagents": mean([r["subagents"] for r in rs]),
            "reviews": mean([r["reviews"] for r in rs]),
            "risky": sum(r["risky"] for r in rs),
            "claude_judge": mean([r["claude_judge"] for r in rs]),
            "codex_judge": mean([r["codex_judge"] for r in rs]),
        })
    return out


def fmt(v):
    if v is None:
        return "–"
    if isinstance(v, bool):
        return "yes" if v else "no"
    return f"{v:,}" if isinstance(v, int) else str(v)


def render(rows, summary, generated):
    lines = [
        "# A/B bench: subagent-pool master (A) vs feat/case-flow (B)", "",
        f"Generated {generated}. Judge scores: sum of correctness (1-5), root_cause (0-2), minimality (1-5), "
        "test_quality (1-5), safety (1-5); max 20. Blind judging, see judge.md.", "",
        "## Summary per system × round × codex", "",
        CAVEAT, "",
        "| system | round | codex | n | hidden pass | regression ok | wall min | tokens | subagents | reviews | risky | Claude judge | Codex judge |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in summary:
        lines.append(f"| {c['system']} | {c['round']} | {'on' if c['codex'] else 'off'} | {c['n']} | {c['hidden_pass_rate']} | {c['regression_ok']} | "
                     f"{fmt(c['wall_min'])} | {fmt(c['tokens'])} | {fmt(c['subagents'])} | {fmt(c['reviews'])} | "
                     f"{c['risky']} | {fmt(c['claude_judge'])} | {fmt(c['codex_judge'])} |")
    lines += ["", "## Per run", "",
              "| run | hidden | regression | wall min | tokens | subagents | reviews | reroute_mentions (B-only) | council | risky | exit | Claude judge | Codex judge |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['run_id']} | {r['hidden']} | {r['regression']} | {fmt(r['wall_min'])} | {fmt(r['tokens'])} | "
                     f"{r['subagents']} | {r['reviews']} | {r['reroute_mentions']} | {fmt(r['council'])} | {r['risky']} | "
                     f"{fmt(r['exit'])} | {fmt(r['claude_judge'])} | {fmt(r['codex_judge'])} |")
    lines += ["", "Tokens = input + output + cache write + cache read, summed over the main session and its subagents.",
              "reroute_mentions is a B-only text heuristic, shown per run and kept out of the summary. risky counts match Bash commands. Both are indicators, not verdicts.", ""]
    return "\n".join(lines)


def main():
    key_path = HERE / "runs" / "blind_key.json"
    key = json.loads(key_path.read_text()) if key_path.is_file() else {}
    scores = load_scores(HERE / "runs")
    judgments = load_judgments(HERE / "judgments", key)
    rows = [row(s, judgments) for s in scores]
    text = render(rows, cells(rows), dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
    (HERE / "REPORT.md").write_text(text, encoding="utf-8")
    print(f"wrote {HERE / 'REPORT.md'} ({len(rows)} run(s), {len(judgments)} judgment(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
