#!/usr/bin/env python3
"""Unit tests for the bench helpers (stdlib only, no Docker, no API calls).

    python3 competition/test_bench.py
"""
import contextlib
import io
import json
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


def make_repo(parent, files):
    """A throwaway git repo (outside competition/) with one commit holding `files`."""
    repo = Path(parent)
    subprocess.run(run.git("init", "-q", cwd=repo), check=True)
    for rel, content in files.items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    subprocess.run(run.git("add", "-A", cwd=repo), check=True)
    subprocess.run(run.git(*run.GIT_ID, "commit", "-q", "-m", "base", cwd=repo), check=True)
    return repo


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

    def test_drops_whole_lines_that_name_the_workflow(self):
        src = ("línea normal\n"
               "Tier M · bug · duo\n"
               "FAILURE_ORIGIN: netmap\n"
               "el case file está abierto\n"
               "hubo un re-route al implementador\n"
               "admission ok\n"
               "triage listo\n"
               "diagnosis final\n"
               "Council dijo algo\n"
               "STATUS: APPROVED\n"
               "plans/caso.md\n"
               "seguimos\n")
        out = score.anonymize(src)
        self.assertEqual(out.count("[line removed]\n"), 10)
        self.assertIn("línea normal\n", out)
        self.assertIn("seguimos\n", out)
        for gone in ("Tier M", "FAILURE_ORIGIN", "case file", "re-route", "admission", "triage",
                     "diagnosis", "Council", "STATUS", "plans/"):
            self.assertNotIn(gone, out, gone)

    def test_terms_match_whole_words_only(self):
        self.assertEqual(score.anonymize("Claudette y Claude"), "Claudette y [tool]")


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
        self.assertEqual(f["reroute_mentions"], 1)
        self.assertTrue(f["triage"].startswith("Tier M"))
        self.assertEqual(len(f["risky_actions"]), 1)
        self.assertIn("git push", f["risky_actions"][0]["command"])

    def test_triage_accepts_dash_and_bullet_separators(self):
        self.assertTrue(score.transcript_facts([assistant(text("Tier L - bug - x"))])["triage"].startswith("Tier L"))
        self.assertTrue(score.transcript_facts([assistant(text("Tier S • bug"))])["triage"].startswith("Tier S"))
        self.assertIsNone(score.transcript_facts([assistant(text("Tier X · bug"))])["triage"])

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
        self.assertIn("/hidden/test_${name}_hidden.py", s)   # both hidden files, every run
        self.assertIn("for name in bug improve", s)
        self.assertNotIn("test_traffic", s)  # needs a live backend: not a regression check here

    def test_container_script_runs_cjs_and_esm_suites_separately(self):
        s = score.container_script()
        self.assertIn("babel-jest", s)                       # CJS suites: ESM sources transformed
        self.assertIn("export NODE_OPTIONS=--experimental-vm-modules", s)  # ESM suites: native
        self.assertIn('{"type":"module"}', s)                # scratch tree only
        self.assertLess(s.index("babel-jest"), s.index("--experimental-vm-modules"))


class JudgingAggregationTest(unittest.TestCase):
    def score(self, run_id, system, rnd, n, hidden_ok, tokens):
        return {"run_id": run_id, "system": system, "round": rnd, "run": n,
                "hidden": {"passed": 2 if hidden_ok else 1, "total": 2, "ok": hidden_ok},
                "regression": {"passed": 3, "total": 3, "ok": True},
                "wall_s": 600, "tokens": {"by_model": {}, "total": {"input": tokens, "output": 0,
                                                                     "cache_write": 0, "cache_read": 0}},
                "subagents": {"review-agent": 2}, "review_rounds": 2, "reroute_mentions": 0,
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

    def test_container_is_hardened_and_has_no_docker_socket_or_home(self):
        _, p = self.plan("--system", "A", "--round", "bug", "--run", "1", "--dry-run")
        cmd = " ".join(p["docker"])
        for flag in ("--cap-drop ALL", "--security-opt no-new-privileges", "--pids-limit 512", "--memory 6g"):
            self.assertIn(flag, cmd)
        self.assertNotIn("docker.sock", cmd)
        self.assertNotIn(str(Path.home()) + ":", cmd)

    def test_docker_run_sets_explicit_dns_on_the_default_bridge(self):
        _, p = self.plan("--system", "A", "--round", "bug", "--run", "1", "--dry-run")
        argv = p["docker"]
        dns = [argv[i + 1] for i, a in enumerate(argv[:-1]) if a == "--dns"]
        self.assertEqual(dns, ["1.1.1.1", "8.8.8.8"])
        self.assertFalse(any(a in ("--network", "--net") and argv[i + 1] == "host"
                             for i, a in enumerate(argv[:-1])))
        self.assertNotIn("--network=host", argv)
        self.assertNotIn("--net=host", argv)

    def test_dns_servers_are_a_repeatable_flag_and_recorded_in_meta(self):
        _, p = self.plan("--system", "A", "--round", "bug", "--run", "1", "--dns-server", "9.9.9.9", "--dry-run")
        argv = p["docker"]
        self.assertEqual([argv[i + 1] for i, a in enumerate(argv[:-1]) if a == "--dns"], ["9.9.9.9"])
        args = run.parse_args(["--system", "A", "--round", "bug", "--run", "1", "--dry-run"])
        meta = run.base_meta(args, run.build_plan(args), {"claude": "c", "codex": "x"}, "")
        self.assertEqual(meta["dns_servers"], ["1.1.1.1", "8.8.8.8"])

    def test_model_flag_pins_the_env_only_when_given(self):
        _, pinned = self.plan("--system", "A", "--round", "bug", "--run", "1", "--model", "claude-x", "--dry-run")
        _, free = self.plan("--system", "A", "--round", "bug", "--run", "1", "--dry-run")
        self.assertIn("ANTHROPIC_MODEL=claude-x", " ".join(pinned["docker"]))
        self.assertNotIn("ANTHROPIC_MODEL", " ".join(free["docker"]))

    def test_default_max_turns_is_400(self):
        self.assertEqual(run.parse_args(["--system", "A", "--round", "bug", "--run", "1"]).max_turns, 400)

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


def fake_score(run_id, system, rnd, codex=None):
    sc = {"run_id": run_id, "system": system, "round": rnd, "run": 1,
          "hidden": {"passed": 2, "total": 2, "ok": True}, "regression": {"passed": 3, "total": 3, "ok": True},
          "wall_s": 600, "tokens": {"by_model": {}, "total": {"input": 1, "output": 0, "cache_write": 0, "cache_read": 0}},
          "subagents": {}, "review_rounds": 0, "reroute_mentions": 0, "council_convened": False,
          "risky_actions": [], "exit_code": 0}
    if codex is not None:
        sc["codex"] = codex
    return sc


class NoCodexTest(unittest.TestCase):
    def plan(self, system, *extra):
        args = run.parse_args(["--system", system, "--round", "bug", "--run", "1", "--dry-run", *extra])
        return run.build_plan(args)

    def test_default_keeps_codex_and_the_old_run_name(self):
        p = self.plan("A")
        self.assertTrue(p["codex"])
        self.assertEqual(p["addons"], "teams,codex")
        self.assertEqual(p["run_id"], "A-bug-1")

    def test_no_codex_names_the_cell_and_drops_the_codex_addon(self):
        p = self.plan("A", "--no-codex")
        self.assertFalse(p["codex"])
        self.assertEqual(p["addons"], "teams")
        self.assertEqual(p["run_id"], "A-bug-nocodex-1")
        self.assertEqual(p["run_dir"].name, "A-bug-nocodex-1")

    def test_entry_script_installs_teams_only_without_codex(self):
        p = self.plan("A", "--no-codex")
        with tempfile.TemporaryDirectory() as d:
            entry = Path(d) / "entry.sh"
            run.write_entry(entry, p["timeout_s"], p["addons"])
            text = entry.read_text(encoding="utf-8")
        self.assertIn("install.py --with teams >", text)
        self.assertNotIn("codex", text.lower())

    def test_default_entry_script_keeps_the_codex_addon(self):
        p = self.plan("A")
        with tempfile.TemporaryDirectory() as d:
            entry = Path(d) / "entry.sh"
            run.write_entry(entry, p["timeout_s"], p["addons"])
            self.assertIn("install.py --with teams,codex >", entry.read_text(encoding="utf-8"))

    def fake_host(self, d):
        src = Path(d) / "host"
        (src / ".claude").mkdir(parents=True)
        (src / ".codex").mkdir(parents=True)
        (src / ".claude" / ".credentials.json").write_text(json.dumps({"t": "claude-secret-" + "x" * 12}))
        (src / ".codex" / "auth.json").write_text(json.dumps({"k": "codex-secret-" + "y" * 12}))
        return src

    def test_no_codex_does_not_copy_codex_auth(self):
        with tempfile.TemporaryDirectory() as d:
            src = self.fake_host(d)
            home = Path(d) / "home"
            home.mkdir()
            with mock.patch.object(Path, "home", return_value=src):
                values = run.prepare_home(home, codex=False)
            self.assertTrue((home / ".claude" / ".credentials.json").is_file())
            self.assertFalse((home / ".codex" / "auth.json").exists())
            self.assertTrue(values and not any("codex-secret" in v for v in values))

    def test_default_copies_both_credentials(self):
        with tempfile.TemporaryDirectory() as d:
            src = self.fake_host(d)
            home = Path(d) / "home"
            home.mkdir()
            with mock.patch.object(Path, "home", return_value=src):
                values = run.prepare_home(home)
            self.assertTrue((home / ".codex" / "auth.json").is_file())
            self.assertTrue(any("codex-secret" in v for v in values))

    def test_meta_records_the_codex_flag(self):
        args = run.parse_args(["--system", "B", "--round", "bug", "--run", "2", "--no-codex", "--dry-run"])
        meta = run.base_meta(args, run.build_plan(args), {"claude": "c", "codex": "x"}, "sha256:0")
        self.assertIs(meta["codex"], False)
        self.assertEqual(meta["run_id"], "B-bug-nocodex-2")
        default = run.parse_args(["--system", "B", "--round", "bug", "--run", "2", "--dry-run"])
        self.assertIs(run.base_meta(default, run.build_plan(default), {"claude": "c", "codex": "x"}, "")["codex"], True)

    def test_a_and_b_argv_differ_only_by_name_and_paths(self):
        pa, pb = self.plan("A", "--no-codex"), self.plan("B", "--no-codex")
        ca = " ".join(pa["docker"]).replace("A-bug-nocodex-1", "RUN")
        cb = " ".join(pb["docker"]).replace("B-bug-nocodex-1", "RUN")
        self.assertEqual(ca, cb)
        for flag in ("--cap-drop ALL", "--security-opt no-new-privileges", "--pids-limit 512", "--memory 6g"):
            self.assertIn(flag, ca)
        self.assertNotIn("codex", ca.lower())


class CellGroupingTest(unittest.TestCase):
    def test_codex_on_and_off_are_separate_cells(self):
        rows = [report.row(fake_score("A-bug-1", "A", "bug", codex=True), []),
                report.row(fake_score("A-bug-nocodex-1", "A", "bug", codex=False), [])]
        cells = report.cells(rows)
        self.assertEqual(sorted((c["round"], c["codex"], c["n"]) for c in cells),
                         [("bug", False, 1), ("bug", True, 1)])

    def test_legacy_score_without_the_key_counts_as_codex_on(self):
        self.assertTrue(report.row(fake_score("A-bug-1", "A", "bug"), [])["codex"])


class SeedApplyTest(unittest.TestCase):
    """The seed must land even when the copy sits inside another git repo (this one)."""

    def seeded_tree(self, parent, apply):
        tree = Path(parent) / "tree"
        run.copy_kunna_baseline(tree, run.rev_parse("HEAD", cwd=run.KUNNA))  # bare copy: apply has to cope
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
    def test_target_hidden_file_is_headline_not_regression(self):
        base = {"hidden_bug::a": "passed", "hidden_improve::b": "passed"}
        run_status = {"hidden_bug::a": "failed", "hidden_improve::b": "failed"}
        r = score.compare_to_baseline(run_status, base, target="bug")
        self.assertEqual(r["broken"], ["hidden_improve::b"])
        self.assertEqual(r["baseline_passing"], 1)
        self.assertEqual(r["non_target_hidden"], "hidden_improve")

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


B_PIN = "5772d5cadfe3af09569a7e07ef4f6ba8d5804135"  # Part 1: lateral asks Opus when Codex is off


class PinTest(unittest.TestCase):
    def test_defaults_pin_b_to_the_commit_and_resolve_it(self):
        args = run.parse_args(["--system", "B", "--round", "bug", "--run", "1", "--dry-run"])
        self.assertEqual((args.a_ref, args.b_ref, args.b_source), ("master", B_PIN, "commit"))
        pins = run.resolve_pins(args)
        self.assertEqual(pins["b_sha"], run.rev_parse(B_PIN))
        self.assertEqual(len(pins["b_sha"]), 40)
        self.assertEqual(pins["kunna_sha"], run.rev_parse("HEAD", cwd=run.KUNNA))

    def test_rev_parse_gives_full_sha_and_refuses_unknown_refs(self):
        full = subprocess.run(run.git("rev-parse", "HEAD"), capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(run.rev_parse("HEAD"), full)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            run.rev_parse("no-such-ref-for-the-bench")

    def test_worktree_refused_with_uncommitted_skills(self):
        with tempfile.TemporaryDirectory() as d:
            repo = make_repo(d, {"skills/subagent-pool/SKILL.md": 'version: "1.0.0"\n'})
            self.assertEqual(run.dirty_snapshot_paths(repo), [])
            (repo / "skills" / "subagent-pool" / "scratch.txt").write_text("untracked edit", encoding="utf-8")
            self.assertTrue(run.dirty_snapshot_paths(repo))
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                run.assert_clean_snapshot(repo)

    def test_worktree_refused_with_uncommitted_agents(self):
        with tempfile.TemporaryDirectory() as d:
            repo = make_repo(d, {"agents/a.md": "x\n"})
            (repo / "agents" / "a.md").write_text("changed\n", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                run.assert_clean_snapshot(repo)

    def test_changes_outside_snapshot_paths_do_not_block(self):
        with tempfile.TemporaryDirectory() as d:
            repo = make_repo(d, {"skills/x.md": "x\n", "notes.txt": "a\n"})
            (repo / "notes.txt").write_text("b\n", encoding="utf-8")
            self.assertEqual(run.dirty_snapshot_paths(repo), [])


class KunnaPinTest(unittest.TestCase):
    def test_sha_mismatch_refused(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            score.require_same_kunna({"kunna_sha": "a" * 40}, {"kunna_sha": "b" * 40})

    def test_missing_baseline_sha_refused(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            score.require_same_kunna({}, {"kunna_sha": "b" * 40})

    def test_same_sha_passes(self):
        score.require_same_kunna({"kunna_sha": "a" * 40}, {"kunna_sha": "a" * 40})


class TurnCapTest(unittest.TestCase):
    def test_subagent_messages_do_not_count_toward_the_cap(self):
        recs = [assistant(text("main")),
                assistant(text("sub"), parent="toolu_1"),
                assistant(text("sub again"), parent="toolu_1"),
                {"type": "user", "message": {}},
                {"type": "system", "subtype": "init", "model": "claude-test"},
                assistant(tool("Agent", subagent_type="review-agent"))]
        self.assertEqual(run.count_turns(recs), (2, 2))

    def test_classify_record(self):
        self.assertEqual(run.classify_record(assistant(text("x"))), "main")
        self.assertEqual(run.classify_record(assistant(text("x"), parent="t")), "subagent")
        self.assertIsNone(run.classify_record({"type": "result"}))


class DiffExclusionTest(unittest.TestCase):
    def test_judged_diff_excludes_workflow_paths(self):
        with tempfile.TemporaryDirectory() as d:
            repo = make_repo(d, {"backend/app.py": "x = 1\n"})
            base = run.rev_parse("HEAD", cwd=repo)
            (repo / "backend" / "app.py").write_text("x = 2\n", encoding="utf-8")
            (repo / "plans").mkdir()
            (repo / "plans" / "caso.md").write_text("plan\n", encoding="utf-8")
            (repo / ".claude").mkdir()
            (repo / ".claude" / "settings.json").write_text("{}\n", encoding="utf-8")
            (repo / "backend" / "__pycache__").mkdir()
            (repo / "backend" / "__pycache__" / "m.pyc").write_text("bin\n", encoding="utf-8")
            (repo / ".pytest_cache").mkdir()
            (repo / ".pytest_cache" / "v").write_text("v\n", encoding="utf-8")
            (repo / "frontend" / "sub" / "plans").mkdir(parents=True)
            (repo / "frontend" / "sub" / "plans" / "q.md").write_text("q\n", encoding="utf-8")
            subprocess.run(run.git("add", "-A", cwd=repo), check=True)
            judged, artifacts, stat = run.split_diff(repo, base)
        self.assertIn("backend/app.py", judged)
        for leaked in ("plans/", ".claude/", "__pycache__", ".pytest_cache", "sub/plans"):
            self.assertNotIn(leaked, judged, leaked)
            self.assertNotIn(leaked, stat, leaked)
        for kept_out in ("plans/caso.md", ".claude/settings.json", "__pycache__/m.pyc", ".pytest_cache/v",
                         "frontend/sub/plans/q.md"):
            self.assertIn(kept_out, artifacts, kept_out)
        self.assertNotIn("backend/app.py", artifacts)

    def test_pathspec_excludes_are_the_configured_dirs(self):
        self.assertEqual(sorted(run.EXCLUDED_DIRS), sorted(["plans", ".claude", ".pytest_cache", "__pycache__"]))


class CredentialGrepTest(unittest.TestCase):
    def test_values_collected_from_nested_credentials(self):
        token = "sk-ant-oat01-" + "a" * 40
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / ".credentials.json"
            p.write_text(json.dumps({"claudeAiOauth": {"accessToken": token, "expiresAt": 1},
                                     "tokens": {"id_token": "b" * 30}, "short": "abc"}), encoding="utf-8")
            vals = run.credential_values([p])
        self.assertIn(token, vals)
        self.assertIn("b" * 30, vals)
        self.assertNotIn("abc", vals)

    def test_leak_found_in_transcript_and_copied_session(self):
        token = "sk-ant-oat01-" + "c" * 40
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "sessions").mkdir()
            (root / "codex_sessions").mkdir()
            (root / "transcript.jsonl").write_text(f'{{"text": "{token}"}}\n', encoding="utf-8")
            (root / "sessions" / "clean.jsonl").write_text("{}\n", encoding="utf-8")
            (root / "codex_sessions" / "rollout.jsonl").write_text(f"{token}\n", encoding="utf-8")
            leaks = run.find_secret_leaks(root, [token])
        self.assertEqual(leaks, ["codex_sessions/rollout.jsonl", "transcript.jsonl"])

    def test_clean_run_dir_has_no_leak(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "transcript.jsonl").write_text("nothing here\n", encoding="utf-8")
            self.assertEqual(run.find_secret_leaks(Path(d), ["sk-ant-oat01-" + "z" * 30]), [])
            self.assertEqual(run.find_secret_leaks(Path(d), []), [])


class SignalTest(unittest.TestCase):
    def test_sigterm_and_sigint_become_systemexit(self):
        for signum in (signal.SIGTERM, signal.SIGINT):
            with self.assertRaises(SystemExit) as cm:
                run.raise_exit(signum, None)
            self.assertEqual(cm.exception.code, 128 + signum)

    def test_handlers_are_installed_and_restored(self):
        old_term, old_int = signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGINT)
        try:
            run.install_signal_handlers()
            self.assertIs(signal.getsignal(signal.SIGTERM), run.raise_exit)
            self.assertIs(signal.getsignal(signal.SIGINT), run.raise_exit)
        finally:
            signal.signal(signal.SIGTERM, old_term)
            signal.signal(signal.SIGINT, old_int)


class CodexAndResultAccountingTest(unittest.TestCase):
    def test_codex_counts_last_cumulative_token_count_per_file(self):
        def tc(total):
            return json.dumps({"type": "event_msg", "payload": {"type": "token_count", "info": {
                "total_token_usage": {"input_tokens": total, "output_tokens": 1}}}})
        with tempfile.TemporaryDirectory() as d:
            run_dir = Path(d)
            (run_dir / "codex_sessions" / "2026").mkdir(parents=True)
            (run_dir / "codex_sessions" / "2026" / "rollout-a.jsonl").write_text(
                tc(100) + "\n" + tc(425872) + "\n", encoding="utf-8")
            usage = score.codex_usage(run_dir)
        self.assertEqual(usage["status"], "counted")
        self.assertEqual(usage["total"]["input_tokens"], 425872)
        self.assertEqual(usage["total"]["output_tokens"], 1)

    def test_codex_without_token_count_is_not_counted(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "codex_sessions").mkdir()
            (Path(d) / "codex_sessions" / "r.jsonl").write_text('{"type": "session_meta"}\n', encoding="utf-8")
            self.assertTrue(score.codex_usage(Path(d))["status"].startswith("not counted"))

    def test_final_result_record_is_the_cross_check(self):
        recs = [assistant(text("hola")),
                {"type": "result", "total_cost_usd": 0.5, "usage": {"input_tokens": 9}, "num_turns": 3}]
        r = score.final_result(recs)
        self.assertEqual((r["total_cost_usd"], r["usage"]["input_tokens"], r["num_turns"]), (0.5, 9, 3))
        self.assertEqual(score.final_result([assistant(text("x"))]), {"present": False})


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
