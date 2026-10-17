import json
import os
import tempfile
import time
import unittest
from pathlib import Path

import doctor


class DoctorTest(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        doctor.HOME = self.home
        self.repo = Path(tempfile.mkdtemp())
        for base in (self.home / ".claude", self.repo):
            sk = base / "skills" / "subagent-pool"
            sk.mkdir(parents=True)
            (sk / "SKILL.md").write_text('version: "9.7.0"\n')
            (base / "agents").mkdir(parents=True)
            for a in doctor.CORE_AGENTS:
                (base / "agents" / f"{a}.agent.md").write_text(a)

    def status(self, res, name):
        return next(r for r in res if r["check"] == name)["status"]

    def test_clean_install_passes(self):
        res = doctor.run_checks(str(self.repo))
        self.assertFalse([r for r in res if r["status"] == "fail"], res)
        self.assertEqual(self.status(res, "cost hook"), "warn")

    def test_drift_and_missing_agent_fail_with_fix(self):
        (self.home / ".claude/skills/subagent-pool/SKILL.md").write_text('version: "9.6.0"\n')
        (self.home / ".claude/agents/review-agent.agent.md").unlink()
        res = doctor.run_checks(str(self.repo))
        self.assertEqual(self.status(res, "skill matches repo"), "fail")
        self.assertEqual(self.status(res, "agent review-agent"), "fail")
        self.assertTrue(all(r["fix"] for r in res if r["status"] == "fail"))

    def test_stale_ledger_warns(self):
        c = self.home / ".claude"
        (c / "settings.json").write_text(json.dumps({"hooks": {"Stop": [{"hooks": [{"command": "cost_tracker.py hook"}]}]}}))
        (c / "metrics").mkdir()
        (c / "metrics/costs.jsonl").write_text("{}\n")
        res = doctor.run_checks(now=time.time() + 72 * 3600)
        self.assertEqual(self.status(res, "cost ledger fresh"), "warn")

    def test_ssh_probe_is_read_only(self):
        from unittest import mock
        with mock.patch("doctor.subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0, stdout='version: "9.7.0"', stderr="")
            doctor.run_checks(remotes=["h"])
        argv = run.call_args[0][0]
        for opt in ("UpdateHostKeys=no", "ControlMaster=no", "ControlPath=none", "PermitLocalCommand=no",
                    "StrictHostKeyChecking=yes", "BatchMode=yes"):
            self.assertIn(opt, argv)

    def test_fresh_ledger_ok_and_boundary(self):
        c = self.home / ".claude"
        (c / "settings.json").write_text(json.dumps({"hooks": {"Stop": [{"hooks": [{"command": "cost_tracker.py hook"}]}]}}))
        (c / "metrics").mkdir()
        led = c / "metrics/costs.jsonl"
        led.write_text("{}\n")
        mt = led.stat().st_mtime
        self.assertEqual(self.status(doctor.run_checks(now=mt + 47 * 3600), "cost ledger fresh"), "ok")
        self.assertEqual(self.status(doctor.run_checks(now=mt + 49 * 3600), "cost ledger fresh"), "warn")

    def test_remote_version_mismatch_and_ssh_error(self):
        from unittest import mock
        with mock.patch("doctor.subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0, stdout='version: "9.7.0"', stderr="")
            self.assertEqual(self.status(doctor.run_checks(remotes=["h"]), "remote h"), "ok")
            run.return_value = mock.Mock(returncode=0, stdout='version: "9.5.0"', stderr="")
            r = next(x for x in doctor.run_checks(remotes=["h"]) if x["check"] == "remote h")
            self.assertEqual((r["status"], r["detail"]), ("fail", "v9.5.0"))
            run.return_value = mock.Mock(returncode=255, stdout='version: "9.7.0"', stderr="boom\nPermission denied")
            r = next(x for x in doctor.run_checks(remotes=["h"]) if x["check"] == "remote h")
            self.assertEqual((r["status"], r["detail"]), ("fail", "Permission denied"))

    def test_agent_content_drift_and_codex(self):
        from unittest import mock
        (self.home / ".claude/agents/review-agent.agent.md").write_text("changed")
        res = doctor.run_checks(str(self.repo))
        self.assertEqual(self.status(res, "review-agent matches repo"), "fail")
        self.assertEqual(self.status(res, "skill matches repo"), "ok")
        (self.home / ".claude/agents/codex-agent.agent.md").write_text("x")
        with mock.patch("doctor.shutil.which", return_value="/usr/bin/codex"):
            self.assertEqual(self.status(doctor.run_checks(), "codex (optional)"), "ok")
        with mock.patch("doctor.shutil.which", return_value=None):
            self.assertEqual(self.status(doctor.run_checks(), "codex (optional)"), "warn")

    def test_unreachable_remote_fails(self):
        res = doctor.run_checks(remotes=["nonexistent.invalid"])
        self.assertEqual(self.status(res, "remote nonexistent.invalid"), "fail")


if __name__ == "__main__":
    unittest.main()
