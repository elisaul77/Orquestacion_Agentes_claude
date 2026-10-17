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

    def test_unreachable_remote_fails(self):
        res = doctor.run_checks(remotes=["nonexistent.invalid"])
        self.assertEqual(self.status(res, "remote nonexistent.invalid"), "fail")


if __name__ == "__main__":
    unittest.main()
