"""Structure checks for the plan council (v9.9): the real agent files and the protocol they share."""
import re
import unittest
from pathlib import Path

import doctor

ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / "skills" / "subagent-pool"


def front(path):
    return re.match(r"^---\n(.*?)\n---\n", path.read_text(), re.S).group(1)


class CouncilTest(unittest.TestCase):
    def test_members_exist_with_sendmessage_and_matching_names(self):
        for a in doctor.COUNCIL_AGENTS:
            f = ROOT / "agents" / f"{a}.agent.md"
            fm = front(f)
            self.assertRegex(fm, rf"(?m)^name: {a}$")
            tools = re.search(r"(?m)^tools: \[(.*)\]$", fm).group(1).split(", ")
            self.assertIn("SendMessage", tools, a)
            self.assertNotIn("Edit", tools, f"{a} must not edit project files")
            self.assertRegex(fm, r"(?m)^model: \w+$")
            self.assertIn("assets/council.md", f.read_text())

    def test_protocol_and_skill_agree(self):
        protocol = (SKILL / "assets" / "council.md").read_text()
        skill = (SKILL / "SKILL.md").read_text()
        for a in doctor.COUNCIL_AGENTS:
            self.assertIn(f"`{a}`", protocol)
            self.assertIn(f"  - {a}\n", skill)
        self.assertRegex(skill, r"(?m)^allowed-tools: .*\bAgent\b.*\bSendMessage\b")
        self.assertIn("## 11. Plan council", (SKILL / "assets" / "prompts.md").read_text())
        self.assertIn(doctor.TEAMS_FLAG, protocol)

    def test_hardening_rules_present(self):
        protocol = (SKILL / "assets" / "council.md").read_text()
        for rule in ("restates the result", "consistency pass", "only after the architect's final return",
                     "Silence until the barrier", "Where to run it"):
            self.assertIn(rule, protocol)
        for a in doctor.COUNCIL_AGENTS:
            self.assertIn("accept → <final text>", (ROOT / "agents" / f"{a}.agent.md").read_text(), a)
        self.assertIn("CROSSED_ACCEPTANCES", (ROOT / "agents" / "council-architect.agent.md").read_text())

    def test_only_architect_writes_the_plan(self):
        for a in doctor.COUNCIL_AGENTS:
            body = (ROOT / "agents" / f"{a}.agent.md").read_text()
            self.assertEqual("-draft.md" in body, a == "council-architect", a)


if __name__ == "__main__":
    unittest.main()
