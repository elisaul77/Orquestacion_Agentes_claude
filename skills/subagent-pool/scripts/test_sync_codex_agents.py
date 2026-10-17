import tempfile
import unittest

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None
from pathlib import Path

import sync_codex_agents as s

AGENT = """---
name: review-agent
description: >
  Reviews code and returns
  APPROVED or "FAILED".
tools: [Read]
model: sonnet
---

# Review Agent

Use `\\d+` and a triple ''' quote and \"\"\" too.
"""


class SyncTest(unittest.TestCase):
    def setUp(self):
        self.src, self.dest = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        (self.src / "review-agent.agent.md").write_text(AGENT)
        (self.src / "codex-agent.agent.md").write_text("---\nname: codex-agent\ndescription: x\n---\nbody\n")
        (self.src / "notes.md").write_text("no frontmatter here")

    @unittest.skipIf(tomllib is None, "tomllib needs Python 3.11+")
    def test_render_is_valid_toml_and_roundtrips(self):
        name, _, content = s.render(AGENT)
        data = tomllib.loads(content)
        self.assertEqual(name, "review-agent")
        self.assertEqual(data["description"], 'Reviews code and returns APPROVED or "FAILED".')
        self.assertIn("triple ''' quote and \"\"\" too", data["developer_instructions"])
        self.assertIn("`\\d+`", data["developer_instructions"])

    def test_create_check_update_cycle(self):
        args = ["--src", str(self.src), "--dest", str(self.dest)]
        self.assertEqual(s.main(args + ["--check"]), 1)
        self.assertFalse((self.dest / "review-agent.agent.toml").exists())
        self.assertEqual(s.main(args), 0)
        self.assertTrue((self.dest / "review-agent.agent.toml").exists())
        self.assertFalse((self.dest / "codex-agent.agent.toml").exists())
        self.assertEqual(s.main(args + ["--check"]), 0)
        (self.src / "review-agent.agent.md").write_text(AGENT + "\nnew rule\n")
        self.assertEqual([r[1] for r in s.plan([self.src], self.dest)], ["update"])
        s.main(args)
        self.assertIn("new rule", (self.dest / "review-agent.agent.toml").read_text())

    def test_foreign_file_never_overwritten(self):
        foreign = self.dest / "review-agent.agent.toml"
        foreign.write_text('name = "review-agent"\ndescription = "old import"\n')
        s.main(["--src", str(self.src), "--dest", str(self.dest)])
        self.assertIn("old import", foreign.read_text())
        self.assertEqual([r[1] for r in s.plan([self.src], self.dest)], ["foreign"])

    def test_quoted_description_keeps_inner_quotes(self):
        _, desc, _ = s.parse("---\nname: 'a'\ndescription: 'says \"hi\"'\n---\nb\n")
        self.assertEqual(desc, 'says "hi"')
        self.assertEqual(s.parse("---\nname: x\ndescription: ends \"q\"\n---\nb\n")[1], 'ends "q"')

    @unittest.skipIf(tomllib is None, "tomllib needs Python 3.11+")
    def test_control_characters_roundtrip(self):
        nasty = "esc\x1b one\x01 del\x7f cr\r tab\t quote\" \'\'\' \"\"\" back\\slash"
        md = f"---\nname: n\ndescription: d{nasty}\n---\n{nasty}\n"
        data = tomllib.loads(s.render(md)[2])
        self.assertEqual(data["developer_instructions"], nasty + "\n")
        self.assertEqual(data["description"], "d" + nasty)

    def test_yaml_block_indicators(self):
        md = "---\nname: n\ndescription: >+ # note\n  one\n  two\n\n  three\n    keep\n---\nb\n"
        self.assertEqual(s.parse(md)[1], "one two\nthree\n  keep")
        md = "---\nname: n\ndescription: |\n  a\n  b\n---\nb\n"
        self.assertEqual(s.parse(md)[1], "a\nb")

    def test_check_fails_on_foreign_and_missing_only(self):
        args = ["--src", str(self.src), "--dest", str(self.dest)]
        s.main(args)
        self.assertEqual(s.main(args + ["--check"]), 0)
        self.assertEqual(s.main(args + ["--check", "--only", "NoSuchAgent"]), 1)
        (self.dest / "review-agent.agent.toml").write_text('name = "review-agent"\n')
        self.assertEqual(s.main(args + ["--check"]), 1)

    def test_only_filter(self):
        (self.src / "x.agent.md").write_text("---\nname: VidPlanner\ndescription: plans\n---\nbody\n")
        rows = s.plan([self.src], self.dest, {"VidPlanner"})
        self.assertEqual([r[0] for r in rows], ["VidPlanner"])


if __name__ == "__main__":
    unittest.main()
