import json
import tempfile
import unittest
from pathlib import Path

import install


def which_none(name):
    return None


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.claude = self.home / ".claude"

    def run_inst(self, addons=(), dry=False, which=which_none):
        inst = install.Installer(self.home, addons=addons, dry=dry, which=which)
        return inst, inst.run()

    def test_dry_run_writes_nothing(self):
        inst, (code, dest, _) = self.run_inst(["teams", "cost-hook", "claude-md"], dry=True)
        self.assertEqual(code, 0)
        self.assertFalse(self.claude.exists())
        self.assertTrue(all(l.startswith("would ") for l in inst.log), inst.log)

    def test_fresh_install_core_passes_doctor(self):
        inst, (code, dest, checks) = self.run_inst()
        self.assertEqual(code, 0, [c for c in checks if c["status"] == "fail"])
        self.assertIsNone(dest)
        self.assertTrue((self.claude / "skills/subagent-pool/SKILL.md").exists())
        for a in ("planning-agent", "council-risk", "AgentArchitect"):
            self.assertTrue((self.claude / "agents" / f"{a}.agent.md").exists(), a)
        self.assertFalse((self.claude / "agents/codex-agent.agent.md").exists())
        self.assertFalse(list(self.claude.rglob("__pycache__")))
        self.assertFalse((self.claude / "settings.json").exists())

    def test_settings_merge_keeps_existing_and_is_idempotent(self):
        self.claude.mkdir()
        orig = {"permissions": {"allow": ["Bash(git *)"]}, "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "x"}]}]},
                "env": {"OTHER": "1"}}
        (self.claude / "settings.json").write_text(json.dumps(orig))
        self.run_inst(["teams", "cost-hook"])
        self.run_inst(["teams", "cost-hook"])
        cfg = json.loads((self.claude / "settings.json").read_text())
        self.assertEqual(cfg["permissions"], orig["permissions"])
        self.assertEqual(cfg["env"], {"OTHER": "1", install.TEAMS_FLAG: "1"})
        self.assertEqual(json.dumps(cfg["hooks"]).count("cost_tracker"), 1)
        self.assertEqual(len(cfg["hooks"]["Stop"]), 2)

    def test_invalid_settings_left_untouched(self):
        self.claude.mkdir()
        (self.claude / "settings.json").write_text("{not json")
        inst, _ = self.run_inst(["teams"])
        self.assertEqual((self.claude / "settings.json").read_text(), "{not json")
        self.assertTrue(any("not valid JSON" in w for w in inst.warnings))

    def test_backup_before_overwrite(self):
        self.run_inst()
        agent = self.claude / "agents/review-agent.agent.md"
        agent.write_text("local edit")
        _, (_, dest, _) = self.run_inst()
        self.assertIsNotNone(dest)
        self.assertEqual((dest / "agents/review-agent.agent.md").read_text(), "local edit")
        self.assertTrue((dest / "skills/subagent-pool/SKILL.md").exists())
        self.assertNotEqual(agent.read_text(), "local edit")

    def test_claude_md_block_appended_once_and_replaced(self):
        self.claude.mkdir()
        md = self.claude / "CLAUDE.md"
        md.write_text("# Mine\n\nkeep this\n")
        self.run_inst(["claude-md"])
        self.run_inst(["claude-md"])
        text = md.read_text()
        self.assertEqual(text.count(install.BEGIN), 1)
        self.assertTrue(text.startswith("# Mine\n\nkeep this\n"))
        md.write_text(text.replace("Direct — no orchestration", "STALE") + "tail\n")
        self.run_inst(["claude-md"])
        text = md.read_text()
        self.assertNotIn("STALE", text)
        self.assertTrue(text.endswith("tail\n"))

    def test_codex_skipped_without_cli(self):
        inst, (code, _, _) = self.run_inst(["codex"])
        self.assertEqual(code, 0)
        self.assertNotIn("codex", inst.addons)
        self.assertFalse((self.claude / "agents/codex-agent.agent.md").exists())

    def test_codex_installs_bridge_and_roles(self):
        inst, (code, _, _) = self.run_inst(["codex"], which=lambda n: "/usr/bin/" + n)
        self.assertTrue((self.claude / "agents/codex-agent.agent.md").exists())
        roles = {p.name for p in (self.home / ".codex/agents").glob("*.toml")}
        self.assertIn("review-agent.agent.toml", roles)
        self.assertFalse([r for r in roles if r.startswith(("council-", "codex-agent"))])

    def test_broken_markers_fail_before_any_change(self):
        self.claude.mkdir()
        md = self.claude / "CLAUDE.md"
        for bad in (f"mine\n{install.BEGIN}\npersonal\n", f"{install.END}\nmine\n{install.BEGIN}\n",
                    f"{install.BEGIN}\na\n{install.END}\n{install.BEGIN}\nb\n{install.END}\n"):
            md.write_text(bad)
            inst, (code, _, _) = self.run_inst(["claude-md"])
            self.assertEqual(code, 1, bad)
            self.assertEqual(md.read_text(), bad)
            self.assertFalse((self.claude / "skills").exists(), "nothing installed before the check")

    def test_codex_roles_backed_up(self):
        which = lambda n: "/usr/bin/" + n
        self.run_inst(["codex"], which=which)
        role = self.home / ".codex/agents/review-agent.agent.toml"
        old = role.read_text()
        (self.claude / "agents/review-agent.agent.md").write_text("---\nname: review-agent\ndescription: x\n---\nnew\n")
        _, (_, dest, _) = self.run_inst(["codex"], which=which)
        self.assertEqual((dest / "codex-agents/review-agent.agent.toml").read_text(), old)

    def test_files_removed_upstream_are_pruned(self):
        self.run_inst()
        stale = self.claude / "skills/subagent-pool/assets/old-removed.md"
        stale.write_text("gone upstream")
        _, (code, dest, checks) = self.run_inst()
        self.assertFalse(stale.exists())
        self.assertTrue((dest / "skills/subagent-pool/assets/old-removed.md").exists())
        self.assertEqual(code, 0, [c for c in checks if c["status"] == "fail"])

    def test_unrelated_cost_tracker_mention_does_not_block_hook(self):
        self.claude.mkdir()
        (self.claude / "settings.json").write_text(json.dumps(
            {"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "echo cost_tracker"}]}]}}))
        self.run_inst(["cost-hook"])
        cfg = json.loads((self.claude / "settings.json").read_text())
        self.assertIn("cost_tracker.py hook", json.dumps(cfg["hooks"]["Stop"]))

    def test_dry_run_with_codex_imports_nothing(self):
        import sys
        sys.modules.pop("sync_codex_agents", None)
        self.run_inst(["codex"], dry=True, which=lambda n: "/usr/bin/" + n)
        self.assertNotIn("sync_codex_agents", sys.modules)

    def test_unknown_addon_rejected(self):
        with self.assertRaises(SystemExit):
            install.main(["--home", str(self.home), "--with", "teams,bogus", "--dry-run"])


if __name__ == "__main__":
    unittest.main()
