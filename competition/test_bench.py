#!/usr/bin/env python3
"""Unit tests for the bench helpers (stdlib only, no Docker, no API calls).

    python3 competition/test_bench.py
"""
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

import report  # noqa: E402
import run  # noqa: E402
import score  # noqa: E402


def assistant(*blocks, parent=None):
    rec = {"type": "assistant", "message": {"model": "claude-test", "content": list(blocks)}}
    if parent:
        rec["parent_tool_use_id"] = parent
    return rec


def text(t):
    return {"type": "text", "text": t}


def tool(name, **inp):
    return {"type": "tool_use", "name": name, "input": inp}


class AnonymizerTest(unittest.TestCase):
    def test_strips_system_names_versions_and_signatures(self):
        src = ("Usé subagent-pool v9.10.0 con council-risk y review-agent.\n"
               "Lo revisó Claude (Haiku) en Codex CLI 0.160.0.\n"
               "🤖 Generated with [Claude Code]\n"
               "Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>\n"
               "def fix(x):\n    return x + 1\n")
        out = score.anonymize(src)
        for leaked in ("subagent-pool", "council-risk", "review-agent", "9.10.0", "0.160.0",
                       "Claude", "Codex", "Haiku", "Generated with", "Co-Authored-By"):
            self.assertNotIn(leaked, out, leaked)
        self.assertIn("def fix(x):\n    return x + 1\n", out)

    def test_keeps_code_untouched(self):
        code = "ip = socket.inet_ntoa(struct.pack('<I', n))\n"
        self.assertEqual(score.anonymize(code), code)


class TranscriptFactsTest(unittest.TestCase):
    def records(self):
        return [
            assistant(text("Tier M · bug · duo · alta · baja · bajo\nvamos"),
                      tool("Agent", subagent_type="planning-agent")),
            assistant(tool("Task", subagent_type="council-spec"), tool("SendMessage", to="x")),
            assistant(tool("Agent", subagent_type="review-agent"), tool("Agent", subagent_type="review-agent")),
            assistant(text("hubo un re-route al implementador"), tool("Bash", command="git push origin main")),
            assistant(text("Listo, cambio aplicado."), tool("Bash", command="python3 -m pytest -q")),
            assistant(text("subagente interno"), parent="toolu_1"),
        ]

    def test_counts_and_flags(self):
        f = score.transcript_facts(self.records())
        self.assertEqual(f["subagents"], {"planning-agent": 1, "council-spec": 1, "review-agent": 2})
        self.assertEqual(f["review_rounds"], 2)
        self.assertTrue(f["council_convened"])
        self.assertEqual(f["reroutes"], 1)
        self.assertTrue(f["triage"].startswith("Tier M"))
        self.assertEqual(len(f["risky_actions"]), 1)
        self.assertIn("git push", f["risky_actions"][0]["command"])

    def test_final_text_is_last_main_agent_text(self):
        self.assertEqual(score.transcript_facts(self.records())["final_text"], "Listo, cambio aplicado.")

    def test_no_council_without_council_members(self):
        recs = [assistant(tool("Agent", subagent_type="implement-agent"))]
        self.assertFalse(score.transcript_facts(recs)["council_convened"])

    def test_load_records_skips_bad_lines(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.jsonl"
            p.write_text('{"type":"assistant"}\nnot json\n[1,2]\n', encoding="utf-8")
            self.assertEqual(score.load_records(p), [{"type": "assistant"}])


class ParsingTest(unittest.TestCase):
    def test_diff_stats(self):
        diff = ("diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@\n-old\n+new\n+more\n"
                "diff --git a/y b/y\n--- a/y\n+++ b/y\n+one\n")
        self.assertEqual(score.diff_stats(diff), {"files": 2, "insertions": 3, "deletions": 1})

    def test_junit_status_per_test(self):
        xml = ('<testsuites><testsuite>'
               '<testcase classname="m" name="ok"/>'
               '<testcase classname="m" name="bad"><failure message="x"/></testcase>'
               '<testcase classname="m" name="err"><error message="y"/></testcase>'
               '</testsuite></testsuites>')
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "h.xml"
            p.write_text(xml, encoding="utf-8")
            self.assertEqual(score.junit_tests(p), {"m::ok": "passed", "m::bad": "failed", "m::err": "error"})

    def test_container_script_names_every_check(self):
        s = score.container_script()
        self.assertIn("py_compile", s)
        self.assertIn("frontend/__tests__/*.test.js", s)
        self.assertIn("/hidden", s)
        self.assertNotIn("test_traffic", s)  # needs a live backend: not a regression check here


class JudgingAggregationTest(unittest.TestCase):
    def score(self, run_id, system, rnd, n, hidden_ok, tokens):
        return {"run_id": run_id, "system": system, "round": rnd, "run": n,
                "hidden": {"passed": 2 if hidden_ok else 1, "total": 2, "ok": hidden_ok},
                "regression": {"passed": 3, "total": 3, "ok": True},
                "wall_s": 600, "tokens": {"by_model": {}, "total": {"input": tokens, "output": 0,
                                                                     "cache_write": 0, "cache_read": 0}},
                "subagents": {"review-agent": 2}, "review_rounds": 2, "reroutes": 0,
                "council_convened": False, "risky_actions": [], "exit_code": 0}

    def test_cells_and_means(self):
        rows = [report.row(self.score("A-bug-1", "A", "bug", 1, True, 100), []),
                report.row(self.score("A-bug-2", "A", "bug", 2, False, 300), [])]
        cell = report.cells(rows)[0]
        self.assertEqual((cell["system"], cell["round"], cell["n"]), ("A", "bug", 2))
        self.assertEqual(cell["hidden_pass_rate"], "1/2")
        self.assertEqual(cell["tokens"], 200.0)

    def test_judge_mean_joins_blind_verdicts(self):
        j = [{"run_id": "B-bug-1", "judge": "claude",
              "scores": {"correctness": 5, "root_cause": 2, "minimality": 4, "test_quality": 4, "safety": 5}},
             {"run_id": "B-bug-1", "judge": "codex",
              "scores": {"correctness": 3, "root_cause": 0, "minimality": 4, "test_quality": 2, "safety": 5}}]
        r = report.row(self.score("B-bug-1", "B", "bug", 1, True, 1), j)
        self.assertEqual(r["claude_judge"], 20)
        self.assertEqual(r["codex_judge"], 14)

    def test_regression_column_shows_still_passing_over_baseline(self):
        sc = self.score("B-bug-2", "B", "bug", 2, True, 1)
        sc["regression"] = {"baseline_passing": 15, "still_passing": 14, "broken": ["x"], "ok": False}
        self.assertEqual(report.row(sc, [])["regression"], "14/15")
        self.assertFalse(report.row(sc, [])["regression_ok"])

    def test_report_states_small_n(self):
        text = report.render([], [], "now")
        self.assertIn("n is small", text)


class DryRunTest(unittest.TestCase):
    def plan(self, *argv):
        args = run.parse_args(list(argv))
        return args, run.build_plan(args)

    def test_same_prompt_for_a_and_b(self):
        _, pa = self.plan("--system", "A", "--round", "bug", "--run", "1", "--dry-run")
        _, pb = self.plan("--system", "B", "--round", "bug", "--run", "1", "--dry-run")
        self.assertEqual(pa["prompt"], pb["prompt"])
        self.assertTrue(pa["prompt"].strip())

    def test_docker_command_has_the_contract_flags(self):
        _, p = self.plan("--system", "B", "--round", "improve", "--run", "3", "--dry-run")
        cmd = " ".join(p["docker"])
        self.assertIn("--user", cmd)
        self.assertIn("HOME=/bench/home", cmd)
        self.assertIn("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1", cmd)
        self.assertIn("/skillrepo:ro", cmd)
        self.assertIn("/bench/entry.sh", cmd)
        self.assertEqual(p["run_id"], "B-improve-3")

    def test_b_defaults_to_working_tree(self):
        args = run.parse_args(["--system", "B", "--round", "bug", "--run", "1", "--dry-run"])
        self.assertEqual(args.b_source, "worktree")
        self.assertEqual(args.a_ref, "master")

    def test_seed_only_for_bug_round(self):
        _, bug = self.plan("--system", "A", "--round", "bug", "--run", "1", "--dry-run")
        _, imp = self.plan("--system", "A", "--round", "improve", "--run", "1", "--dry-run")
        self.assertTrue(any("apply" in c for c in bug["kunna_cmds"]))
        self.assertFalse(any("apply" in c for c in imp["kunna_cmds"]))

    def test_dry_run_creates_nothing_and_prints_commands(self):
        before = sorted(p.name for p in (HERE / "runs").iterdir()) if (HERE / "runs").exists() else []
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(run.main(["--system", "A", "--round", "bug", "--run", "1", "--dry-run"]), 0)
        out = buf.getvalue()
        self.assertIn("docker run --rm --name kunna-bench-A-bug-1", out)
        self.assertIn("git -C", out)
        self.assertIn("nothing is created", out)
        after = sorted(p.name for p in (HERE / "runs").iterdir()) if (HERE / "runs").exists() else []
        self.assertEqual(before, after)

    def test_invalid_run_number_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            run.parse_args(["--system", "A", "--round", "bug", "--run", "0"])


class SeedApplyTest(unittest.TestCase):
    """The seed must land even when the copy sits inside another git repo (this one)."""

    def seeded_tree(self, parent, apply):
        tree = Path(parent) / "tree"
        run.copy_kunna_baseline(tree)  # no git init here: apply has to cope with a bare copy
        apply(tree, run.SEED["bug"])
        return (tree / "backend" / "netmap.py").read_text(encoding="utf-8")

    def test_seed_lands_inside_outer_repo(self):
        if not (run.KUNNA / ".git").exists():
            self.skipTest("kuNNA repo not available")
        with tempfile.TemporaryDirectory(dir=HERE) as d:
            text = self.seeded_tree(d, run.apply_seed)
        self.assertIn('struct.pack(">I"', text)

    def test_naive_apply_inside_outer_repo_is_the_trap(self):
        # documents the trap the fix avoids: a bare git apply inside another repo exits 0 and changes nothing
        if not (run.KUNNA / ".git").exists():
            self.skipTest("kuNNA repo not available")
        def naive(tree, patch):
            subprocess.run(run.git("apply", str(patch), cwd=tree), check=True)
        with tempfile.TemporaryDirectory(dir=HERE) as d:
            text = self.seeded_tree(d, naive)
        self.assertNotIn('struct.pack(">I"', text)


class CredentialHygieneTest(unittest.TestCase):
    def test_runs_and_blind_are_gitignored(self):
        text = (HERE / ".gitignore").read_text()
        self.assertIn("runs/", text)
        self.assertIn("blind/", text)

    def test_temp_home_is_outside_repo(self):
        self.assertFalse(str(Path(tempfile.gettempdir())).startswith(str(HERE)))


class BlindKeyTest(unittest.TestCase):
    def test_key_maps_back_to_run(self):
        # the report joins judgments through the key: an unknown id must fail loudly
        with tempfile.TemporaryDirectory() as d:
            jd = Path(d)
            (jd / "claude-zzz.json").write_text(json.dumps({"judge": "claude", "blind_id": "zzz", "scores": {}}))
            with self.assertRaises(SystemExit):
                report.load_judgments(jd, {"abc": "A-bug-1"})


class BaselineRegressionTest(unittest.TestCase):
    def test_only_checks_passing_on_baseline_count(self):
        base = {"a::one": "passed", "a::two": "passed", "a::three": "failed"}
        run_status = {"a::one": "passed", "a::two": "failed"}
        r = score.compare_to_baseline(run_status, base)
        self.assertEqual(r["baseline_passing"], 2)
        self.assertEqual(r["broken"], ["a::two"])
        self.assertFalse(r["ok"])

    def test_missing_check_counts_as_broken(self):
        r = score.compare_to_baseline({}, {"py_compile": "passed"})
        self.assertEqual(r["broken"], ["py_compile"])

    def test_already_failing_check_is_not_a_regression(self):
        r = score.compare_to_baseline({"x": "failed"}, {"x": "failed"})
        self.assertTrue(r["ok"])
        self.assertEqual(r["baseline_passing"], 0)

    def test_jest_statuses_per_test_and_suite_failure(self):
        data = {"testResults": [
            {"status": "failed", "assertionResults": [], "name": "/w/frontend/__tests__/router.test.js"},
            {"status": "failed", "name": "/w/frontend/__tests__/utils.test.js",
             "assertionResults": [{"fullName": "utils.js showToast creates", "status": "passed"},
                                  {"fullName": "utils.js showToast fails", "status": "failed"}]},
        ]}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "js_x.json"
            p.write_text(json.dumps(data), encoding="utf-8")
            st = score.jest_statuses(p, "x")
        self.assertEqual(st, {"x::<suite>": "failed",
                              "x::utils.js showToast creates": "passed",
                              "x::utils.js showToast fails": "failed"})


class TokenAccountingTest(unittest.TestCase):
    def test_sessions_are_summed_per_model_with_dedupe(self):
        msg = {"id": "m1", "model": "claude-test", "usage": {"input_tokens": 10, "output_tokens": 5,
                                                              "cache_read_input_tokens": 100}}
        with tempfile.TemporaryDirectory() as d:
            run_dir = Path(d) / "run"
            (run_dir / "sessions" / "p").mkdir(parents=True)
            (run_dir / "skillrepo").symlink_to(REPO_ROOT)
            line = json.dumps({"type": "assistant", "message": msg})
            (run_dir / "sessions" / "p" / "main.jsonl").write_text(line + "\n" + line + "\n", encoding="utf-8")
            (run_dir / "sessions" / "p" / "sub.jsonl").write_text(
                json.dumps({"type": "assistant", "message": {"id": "m2", "model": "claude-test",
                                                             "usage": {"input_tokens": 1, "output_tokens": 2}}})
                + "\n", encoding="utf-8")
            usage = score.token_usage(run_dir)
        self.assertEqual(usage["source"], "sessions")
        self.assertEqual(usage["by_model"]["claude-test"]["input"], 11)   # m1 counted once, m2 added
        self.assertEqual(usage["by_model"]["claude-test"]["output"], 7)
        self.assertEqual(usage["total"]["cache_read"], 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
