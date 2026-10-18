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
    repo.mkdir(parents=True, exist_ok=True)
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
        self.assertIn("for name in bug improve bug2", s)
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


class ClaudeMdTest(unittest.TestCase):
    """--claude-md: the routing table add-on is installed in the bench container (cell suffix -cmd)."""

    def plan(self, system, *extra, rnd="improve"):
        args = run.parse_args(["--system", system, "--round", rnd, "--run", "1", "--dry-run", *extra])
        return run.build_plan(args)

    def test_default_has_no_claude_md(self):
        p = self.plan("A", rnd="bug")
        self.assertFalse(p["claude_md"])
        self.assertEqual(p["addons"], "teams,codex")
        self.assertEqual(p["run_id"], "A-bug-1")

    def test_claude_md_adds_the_addon_and_the_cmd_suffix(self):
        p = self.plan("A", "--claude-md")
        self.assertTrue(p["claude_md"])
        self.assertEqual(p["addons"], "teams,codex,claude-md")
        self.assertEqual(p["run_id"], "A-improve-cmd-1")

    def test_no_codex_with_claude_md_uses_the_combined_suffix(self):
        p = self.plan("A", "--no-codex", "--claude-md")
        self.assertEqual(p["addons"], "teams,claude-md")
        self.assertEqual(p["run_id"], "A-improve-nocodex-cmd-1")
        self.assertEqual(p["run_dir"].name, "A-improve-nocodex-cmd-1")
        self.assertFalse(p["codex"])

    def test_entry_script_installs_claude_md(self):
        p = self.plan("A", "--no-codex", "--claude-md")
        with tempfile.TemporaryDirectory() as d:
            entry = Path(d) / "entry.sh"
            run.write_entry(entry, p["timeout_s"], p["addons"])
            text = entry.read_text(encoding="utf-8")
        self.assertIn("install.py --with teams,claude-md >", text)
        self.assertNotIn("codex", text.lower())

    def test_meta_records_claude_md(self):
        on = run.parse_args(["--system", "B", "--round", "improve", "--run", "1", "--no-codex", "--claude-md", "--dry-run"])
        meta = run.base_meta(on, run.build_plan(on), {"claude": "c", "codex": "x"}, "")
        self.assertIs(meta["claude_md"], True)
        self.assertEqual(meta["run_id"], "B-improve-nocodex-cmd-1")
        off = run.parse_args(["--system", "B", "--round", "improve", "--run", "1", "--dry-run"])
        self.assertIs(run.base_meta(off, run.build_plan(off), {"claude": "c", "codex": "x"}, "")["claude_md"], False)

    def test_a_and_b_argv_differ_only_by_name_and_paths_with_claude_md(self):
        pa, pb = self.plan("A", "--no-codex", "--claude-md"), self.plan("B", "--no-codex", "--claude-md")
        ca = " ".join(pa["docker"]).replace("A-improve-nocodex-cmd-1", "RUN")
        cb = " ".join(pb["docker"]).replace("B-improve-nocodex-cmd-1", "RUN")
        self.assertEqual(ca, cb)
        self.assertEqual(pa["addons"], pb["addons"])


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
        self.assertEqual(r["non_target_hidden"], ["hidden_bug2", "hidden_improve"])

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


B_PIN = "aebd9ac855050888d823734d44705e4b548458d0"  # v9.11.0: case flow, FAILURE_ORIGIN routing


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


class ImproveOrchRoundTest(unittest.TestCase):
    ORCH_LINE = ("Orquesta esto con subagent-pool (procede sin project-context; "
                 "el proyecto no tiene .claude/project-context.md):")

    def plan(self, *argv):
        return run.build_plan(run.parse_args(list(argv)))

    def test_prompt_is_orchestration_line_then_byte_identical_improve_body(self):
        orch = (HERE / "prompts" / "improve-orch.md").read_bytes()
        improve = (HERE / "prompts" / "improve.md").read_bytes()
        self.assertEqual(orch.split(b"\n", 2)[0].decode("utf-8"), self.ORCH_LINE)
        self.assertEqual(orch.split(b"\n", 2)[1], b"")
        self.assertEqual(orch.split(b"\n", 2)[2], improve)
        self.assertEqual(orch, self.ORCH_LINE.encode("utf-8") + b"\n\n" + improve)

    def test_round_is_accepted_and_scored_on_the_improve_hidden_file(self):
        self.assertIn("improve-orch", run.ROUNDS)
        self.assertEqual(run.HIDDEN_FOR_ROUND["improve-orch"], "improve")
        self.assertEqual(run.HIDDEN_FOR_ROUND["improve"], "improve")
        self.assertEqual(run.HIDDEN_FOR_ROUND["bug"], "bug")
        self.assertIn(run.HIDDEN_FOR_ROUND["improve-orch"], score.HIDDEN_FILES)
        self.assertEqual(set(run.HIDDEN_FOR_ROUND), set(run.ROUNDS))

    def test_plan_uses_the_orch_prompt_and_no_seed(self):
        p = self.plan("--system", "A", "--round", "improve-orch", "--run", "1", "--no-codex",
                      "--claude-md", "--dry-run")
        self.assertEqual(p["prompt"], (HERE / "prompts" / "improve-orch.md").read_text(encoding="utf-8"))
        self.assertTrue(p["prompt"].startswith(self.ORCH_LINE + "\n\n"))
        self.assertEqual(p["run_id"], "A-improve-orch-nocodex-cmd-1")
        self.assertFalse(any("bug.patch" in c for c in p["kunna_cmds"]))

    def test_cross_hidden_for_orch_round_is_the_bug_file(self):
        base = {"hidden_bug::a": "passed", "hidden_improve::b": "passed"}
        target = run.HIDDEN_FOR_ROUND["improve-orch"]
        r = score.compare_to_baseline({"hidden_bug::a": "failed", "hidden_improve::b": "failed"},
                                      base, target=target, cross=score.REGRESSION_CROSS["improve-orch"])
        self.assertEqual(r["non_target_hidden"], ["hidden_bug"])
        self.assertEqual(r["broken"], ["hidden_bug::a"])


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


class Bug2OrchRoundTest(unittest.TestCase):
    """bug2-orch: a decoy and a real cause. The prompt names no file or function; the hidden file is bug2."""
    ORCH_LINE = ImproveOrchRoundTest.ORCH_LINE
    # names of the real and decoy sites, file names and the internals a prompt must not hand over
    FORBIDDEN = ("netmap", ".py", "collect", "_addresses", "_hex_to_addr", "_read_tcp", "ip_owner",
                 "IPAddress", "Gateway", "_host_ips", "net.get", "backend/", "seed", "decoy", "hidden")

    def plan(self, *argv):
        return run.build_plan(run.parse_args(list(argv)))

    def test_prompt_first_line_blank_line_then_a_body_without_file_names(self):
        lines = (HERE / "prompts" / "bug2-orch.md").read_text(encoding="utf-8").split("\n")
        self.assertEqual(lines[0], self.ORCH_LINE)
        self.assertEqual(lines[1], "")
        body = "\n".join(lines[2:])
        self.assertTrue(body.strip())
        for term in self.FORBIDDEN:
            self.assertNotIn(term, body, f"prompt body must not contain {term!r}")

    def test_round_wiring(self):
        self.assertIn("bug2-orch", run.ROUNDS)
        self.assertEqual(run.HIDDEN_FOR_ROUND["bug2-orch"], "bug2")
        self.assertEqual(score.HIDDEN_FILES["bug2"], "test_bug2_hidden.py")
        self.assertTrue((HERE / "hidden" / score.HIDDEN_FILES["bug2"]).is_file())
        self.assertEqual(set(run.HIDDEN_FOR_ROUND), set(run.ROUNDS))
        self.assertEqual(set(score.REGRESSION_CROSS), set(run.ROUNDS))

    def test_plan_applies_only_the_bug2_seed_and_the_orch_prompt(self):
        p = self.plan("--system", "B", "--round", "bug2-orch", "--run", "1", "--no-codex", "--claude-md", "--dry-run")
        self.assertEqual(p["run_id"], "B-bug2-orch-nocodex-cmd-1")
        self.assertEqual(p["prompt"], (HERE / "prompts" / "bug2-orch.md").read_text(encoding="utf-8"))
        applies = [c for c in p["kunna_cmds"] if " apply " in c]
        self.assertEqual(len(applies), 1)  # one command: apply, then the reverse check of the same seed
        self.assertIn("bug2.patch", applies[0])
        mounts = " ".join(p["docker"])
        for proof in ("bug2-decoy-fix", "bug2-real-fix"):
            self.assertNotIn(proof, mounts)
            self.assertNotIn(proof, " ".join(p["kunna_cmds"]))

    def test_cross_regression_is_the_two_other_hidden_files(self):
        base = {"hidden_bug::a": "passed", "hidden_improve::b": "passed", "hidden_bug2::c": "passed",
                "py_compile": "passed"}
        run_status = {"hidden_bug::a": "failed", "hidden_improve::b": "passed", "hidden_bug2::c": "failed",
                      "py_compile": "passed"}
        r = score.compare_to_baseline(run_status, base, target="bug2", cross=score.REGRESSION_CROSS["bug2-orch"])
        self.assertEqual(r["non_target_hidden"], ["hidden_bug", "hidden_improve"])
        self.assertEqual(r["broken"], ["hidden_bug::a"])          # the headline bug2 check is not regression
        self.assertEqual(r["baseline_passing"], 3)

    def test_seed_applies_and_both_proof_patches_apply_on_top_of_it(self):
        if not (run.KUNNA / ".git").exists():
            self.skipTest("kuNNA repo not available")
        with tempfile.TemporaryDirectory(dir=HERE) as d:
            tree = Path(d) / "tree"
            run.copy_kunna_baseline(tree, run.rev_parse("HEAD", cwd=run.KUNNA))
            run.apply_seed(tree, run.SEED["bug2-orch"])
            for patch in ("bug2-decoy-fix.patch", "bug2-real-fix.patch"):
                subprocess.run(run.git("apply", "--check", str(HERE / "seed" / patch), cwd=tree), check=True)
        names = [l.split(" b/")[-1] for l in (HERE / "seed" / "bug2.patch").read_text().splitlines()
                 if l.startswith("diff --git ")]
        self.assertEqual(names, ["backend/netmap.py"])            # the seed touches one file only

    def test_function_span_and_diff_touch_the_decoy_only_when_it_changes_it(self):
        src = "X = 1\n\n\ndef collect():\n    return 1\n\n\ndef other():\n    pass\n"
        self.assertEqual(score.function_span(src, "collect"), (4, 5))
        self.assertIsNone(score.function_span(src, "missing"))
        in_collect = ("diff --git a/backend/netmap.py b/backend/netmap.py\n--- a/backend/netmap.py\n"
                      "+++ b/backend/netmap.py\n@@ -4,2 +4,2 @@\n def collect():\n-    return 1\n+    return 2\n")
        in_other = ("diff --git a/backend/netmap.py b/backend/netmap.py\n--- a/backend/netmap.py\n"
                    "+++ b/backend/netmap.py\n@@ -8,2 +8,2 @@\n def other():\n-    pass\n+    return 0\n")
        self.assertTrue(score.diff_touches_span(in_collect, "backend/netmap.py", 4, 5))
        self.assertFalse(score.diff_touches_span(in_other, "backend/netmap.py", 4, 5))
        self.assertFalse(score.diff_touches_span(in_collect, "backend/other.py", 4, 5))

    def test_decoy_check_on_a_real_git_diff(self):
        with tempfile.TemporaryDirectory(dir=HERE) as d:
            repo = make_repo(Path(d) / "kunna", {"backend/netmap.py":
                "def _addresses(net):\n    return []\n\n\ndef collect(c):\n    return {}\n"})
            base = subprocess.run(run.git("rev-parse", "HEAD", cwd=repo), capture_output=True, text=True,
                                  check=True).stdout.strip()
            meta = {"round": "bug2-orch", "base_sha": base}
            path = repo / "backend" / "netmap.py"
            path.write_text(path.read_text().replace("return []", "return [1]"), encoding="utf-8")
            helper_diff = subprocess.run(run.git("diff", cwd=repo), capture_output=True, text=True).stdout
            self.assertFalse(score.decoy_check(Path(d), meta, helper_diff)["touched"])
            path.write_text(path.read_text().replace("return {}", "return {'x': 1}"), encoding="utf-8")
            decoy_diff = subprocess.run(run.git("diff", cwd=repo), capture_output=True, text=True).stdout
            result = score.decoy_check(Path(d), meta, decoy_diff)
            self.assertTrue(result["touched"])
            self.assertEqual(result["function"], "collect")
        self.assertIsNone(score.decoy_check(Path("/nonexistent"), {"round": "bug"}, ""))

    def test_review_facts_from_a_synthetic_transcript(self):
        def use(uid, sub=None, **inp):
            return {"type": "tool_use", "id": uid, "name": "Agent", "input": dict(inp, subagent_type=sub)}
        def result(uid, body):
            return {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": uid, "content": body}]}}
        def msg(*blocks, parent=None):
            rec = {"type": "assistant", "message": {"content": list(blocks)}}
            if parent:
                rec["parent_tool_use_id"] = parent
            return rec
        recs = [
            msg(use("p1", "planning-agent")),
            result("p1", "FACTS\nHYPOTHESES\nFALSIFIER: the map would still show external links\n"),
            msg(use("i1", "implement-agent")),
            msg(use("r1", "review-agent")),
            result("r1", "Checks ran.\nSTATUS: NEEDS_REVISION\nFAILURE_ORIGIN: diagnosis\n"),
            msg(use("n1", "planning-agent", description="re-diagnosis")),  # main agent, after the failed review
            msg(use("p2", "planning-agent"), parent="x"),
            msg(text("STATUS: APPROVED | NEEDS_REVISION | FAILED")),
            msg(use("r2", "review-agent")),
            result("r2", "STATUS: APPROVED\nFAILURE_ORIGIN: none\n"),
            msg(use("r3", "review-agent")),
            result("r3", "STATUS: FAILED\n"),
        ]
        f = score.review_facts(recs)
        self.assertEqual([v["status"] for v in f["verdicts"]], ["NEEDS_REVISION", "APPROVED", "FAILED"])
        self.assertEqual(f["failure_origins"], {"diagnosis": 1, "none": 1, "missing": 1})
        self.assertEqual(f["needs_revision_loops"], 1)
        self.assertEqual(f["failed_reviews"], 2)
        self.assertEqual(f["redispatch_after_failed_review"], 1)  # n1 is main-agent: counted (after the failed review)
        self.assertTrue(f["falsifier_appeared"])
        self.assertGreaterEqual(f["falsifier_mentions"], 1)

    def test_no_redispatch_without_a_failed_review_and_no_falsifier(self):
        recs = [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "r1", "name": "Agent", "input": {"subagent_type": "review-agent"}}]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "r1", "content": "STATUS: APPROVED\nFAILURE_ORIGIN: none"}]}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "p1", "name": "Agent", "input": {"subagent_type": "planning-agent"}}]}},
        ]
        f = score.review_facts(recs)
        self.assertEqual(f["redispatch_after_failed_review"], 0)
        self.assertEqual(f["failed_reviews"], 0)
        self.assertFalse(f["falsifier_appeared"])

    def test_score_run_without_docker_reports_the_decoy_and_the_review_facts(self):
        with tempfile.TemporaryDirectory(dir=HERE) as d:
            run_dir = Path(d) / "B-bug2-orch-nocodex-1"
            repo = make_repo(run_dir / "kunna", {"backend/netmap.py":
                "def _addresses(net):\n    return []\n\n\ndef collect(c):\n    return {}\n"})
            base = subprocess.run(run.git("rev-parse", "HEAD", cwd=repo), capture_output=True, text=True,
                                  check=True).stdout.strip()
            (run_dir / "skillrepo").symlink_to(REPO_ROOT)
            meta = {"run_id": run_dir.name, "system": "B", "round": "bug2-orch", "run": 1, "base_sha": base,
                    "codex": False}
            (run_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
            (run_dir / "transcript.jsonl").write_text(json.dumps(assistant(text("listo"))) + "\n", encoding="utf-8")
            path = repo / "backend" / "netmap.py"
            path.write_text(path.read_text().replace("return {}", "return {'x': 1}"), encoding="utf-8")
            diff = subprocess.run(run.git("diff", cwd=repo), capture_output=True, text=True).stdout
            (run_dir / "final.diff").write_text(diff, encoding="utf-8")
            res = score.score_run(run_dir, no_docker=True)
        self.assertTrue(res["decoy_touched"])
        self.assertIsNone(res["real_fixed"])          # no docker: hidden not run
        self.assertEqual(res["review"]["verdicts"], [])
        self.assertIn("decoy", res)


class PinV911Test(unittest.TestCase):
    def test_b_pin_is_aebd9ac_and_it_is_version_9_11_0(self):
        self.assertEqual(run.DEFAULT_B_REF, "aebd9ac855050888d823734d44705e4b548458d0")
        self.assertEqual(run.DEFAULT_B_REF, B_PIN)
        self.assertEqual(run.rev_parse(B_PIN), B_PIN)
        text_b = subprocess.run(run.git("show", f"{B_PIN}:skills/subagent-pool/SKILL.md"),
                                capture_output=True, text=True, check=True).stdout
        self.assertEqual(run.VERSION_RE.search(text_b).group(1), "9.11.0")


if __name__ == "__main__":
    unittest.main(verbosity=2)
