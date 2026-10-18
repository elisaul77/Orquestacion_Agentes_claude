"""STRUCTURAL checks only: they prove the rules are written, not that a model routes correctly (see eval_routing.py).

Each test maps to an acceptance criterion (A#) in plans/council/case-flow/spec.md. Assertions use stable keywords,
so the wording around them can change without touching the test.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / "skills" / "subagent-pool"
AGENTS_DIR = ROOT / "agents"

OLD_ROUTE_PHRASE = "any tier touching security triggers, public API, data or money"
AXES = ("urgency", "effort", "uncertainty", "risk")
CASE_FILE_FIELDS = ("objective", "classification", "owner", "status", "hypotheses",
                    "evidence", "decisions", "changes", "verification", "next action")
DIAGNOSIS_FIELDS = ("FACTS", "HYPOTHESES", "EVIDENCE", "MISSING", "PROPOSED_INTERVENTION", "FALSIFIER")
CORE_AGENTS = {"planning-agent", "implement-agent", "review-agent", "AgentArchitect",
               "council-spec", "council-architect", "council-lateral", "council-risk"}


def read(path):
    return path.read_text(encoding="utf-8")


def lines_with(text, *words):
    """Lines (lowercased) that contain every given word (lowercased)."""
    wanted = [w.lower() for w in words]
    return [ln for ln in text.lower().splitlines() if all(w in ln for w in wanted)]


class CaseFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read(SKILL / "SKILL.md")
        cls.agents_md = read(ROOT / "AGENTS.md")
        cls.readme = read(ROOT / "README.md")
        cls.readme_es = read(ROOT / "README.es.md")
        cls.prompts = read(SKILL / "assets" / "prompts.md")
        cls.review = read(AGENTS_DIR / "review-agent.agent.md")
        cls.planning = read(AGENTS_DIR / "planning-agent.agent.md")

    # A1 (AC1): the old security/API/data/money => council rule is gone from every user-facing doc.
    def test_A1_old_council_trigger_removed(self):
        for name, text in (("SKILL.md", self.skill), ("AGENTS.md", self.agents_md),
                           ("README.md", self.readme), ("README.es.md", self.readme_es)):
            self.assertNotIn(OLD_ROUTE_PHRASE.lower(), text.lower(), name)

    # A2 (AC2): a triage section names the four axes on one line; urgency never removes controls.
    def test_A2_triage_axes_and_urgency_rule(self):
        self.assertIn("triage", self.skill.lower())
        self.assertTrue(lines_with(self.skill, *AXES),
                        "one SKILL.md line must name all four axes: urgency, effort, uncertainty, risk")
        self.assertTrue(lines_with(self.skill, "urgency", "never removes controls"),
                        "a sentence must say urgency never removes controls")

    # A3 (AC3): council needs an open important decision; Tier L without one maps to single.
    def test_A3_council_requires_open_important_decision(self):
        self.assertTrue(lines_with(self.skill, "|", "council", "open important decision"),
                        "SKILL.md plan-level row for council must name the open important decision")
        self.assertTrue(lines_with(self.skill, "|", "tier l", "no open", "single"),
                        "SKILL.md row: Tier L with no open decision maps to single")
        for name, text in (("AGENTS.md", self.agents_md), ("README.md", self.readme)):
            self.assertIn("open important decision", text.lower(), name)

    # A4 (AC4): Consult = one specialist, one bounded question; no new agent files.
    def test_A4_consult_definition_and_agent_set_unchanged(self):
        self.assertTrue(lines_with(self.skill, "consult", "one specialist", "one bounded question"),
                        "SKILL.md must define Consult as one specialist, one bounded question")
        names = {p.name[: -len(".agent.md")] for p in AGENTS_DIR.glob("*.agent.md")}
        self.assertEqual(names, CORE_AGENTS, "agents/ must keep exactly the current agents")
        optional = {p.name for p in (AGENTS_DIR / "optional").glob("*.agent.md")}
        self.assertEqual(optional, {"codex-agent.agent.md"})

    # A5 (AC5): FAILURE_ORIGIN with the same enumerated value set on one line in review-agent, prompts.md and SKILL.md.
    def test_A5_failure_origin_in_three_contracts(self):
        for name, text in (("review-agent.agent.md", self.review), ("prompts.md", self.prompts),
                           ("SKILL.md", self.skill)):
            self.assertIsNotNone(
                re.search(r"FAILURE_ORIGIN[^\n]*implementation\s*\|\s*diagnosis\s*\|\s*scope\s*\|\s*none", text),
                f"{name} must list FAILURE_ORIGIN as implementation | diagnosis | scope | none on one line")

    # A6 (AC6): VERIFIED is not DEPLOYED; closing never authorizes publish or deploy; Approve row unchanged.
    def test_A6_verified_is_not_deployed_and_approve_row_kept(self):
        self.assertTrue(lines_with(self.skill, "VERIFIED", "DEPLOYED", "never authorizes"),
                        "one sentence must say closing never authorizes publish or deploy")
        self.assertIn("Delete/overwrite data, migrations, secrets, prod config, `git push`, publishing, deploys",
                      self.skill)

    # A7 (AC7): diagnosis block fields and the 2-round evidence bound.
    def test_A7_diagnosis_block_and_loop_bound(self):
        for name, text in (("prompts.md", self.prompts), ("planning-agent.agent.md", self.planning)):
            for field in DIAGNOSIS_FIELDS:
                self.assertIn(field, text, f"{name} must carry {field}")
        self.assertIn("2 rounds without new evidence", self.skill)

    # A8 (AC8): re-triage when the diagnosis changes scope or risk, stated on one line.
    def test_A8_retriage_trigger(self):
        self.assertTrue(lines_with(self.skill, "re-triage", "scope", "risk"),
                        "one SKILL.md line must say re-triage happens when scope or risk changes")

    # A9 (AC9): case-file fields in one line of the state file; tier S has no case file.
    def test_A9_case_file_fields_and_tier_s_exemption(self):
        self.assertTrue(lines_with(self.skill, "case file", *CASE_FILE_FIELDS),
                        "one SKILL.md line must name the case file and all ten fields")
        self.assertTrue(lines_with(self.skill, "tier s", "no case file"),
                        "SKILL.md must say tier S has no case file")

    # A13 (AC13): one global cap of 3 re-routes per case that survives re-triage, all on one line.
    def test_A13_global_reroute_cap_survives_retriage(self):
        cap = r"(cap|max\w*|at most)\D{0,40}\b(3|three)\b[^\n]*re-?rout|re-?rout[^\n]*\b(3|three)\b"
        scope_words = ("global", "per case", "whole case")
        ok = any(re.search(cap, ln, re.I) and "re-triage" in ln.lower()
                 and any(w in ln.lower() for w in scope_words)
                 for ln in self.skill.splitlines())
        self.assertTrue(ok, "one SKILL.md line must state the cap of 3 re-routes, re-triage, "
                            "and global / per case / whole case")

    # R1 (review fix 1): consult and specialty review share one discriminator, `mode=consult specialty=<x>`.
    def test_R1_consult_discriminator_in_prompts_and_review_agent(self):
        for name, text in (("prompts.md", self.prompts), ("review-agent.agent.md", self.review)):
            self.assertTrue(lines_with(text, "mode=consult", "specialty="),
                            f"{name} must carry the discriminator mode=consult specialty=<x>")
        self.assertIn("Consult mode", self.review, "review-agent must have a Consult mode section")

    # R1b (review fix 1): `mode=<specialty>` is a specialty review with a STATUS verdict, never a consult.
    # A line that names both `mode=<specialty>` and a consult is only accepted when it also spells `mode=consult`.
    def test_R1b_specialty_mode_is_never_called_a_consult(self):
        bad = re.compile(r"mode=<specialty>[^\n]{0,40}consult", re.I)
        docs = [p for p in SKILL.rglob("*.md") if "__pycache__" not in p.parts]
        docs += list(AGENTS_DIR.rglob("*.md")) + [ROOT / "AGENTS.md"] + list(ROOT.glob("README*.md"))
        offenders = []
        for path in docs:
            for lineno, line in enumerate(read(path).splitlines(), 1):
                if bad.search(line) and "mode=consult" not in line.lower():
                    offenders.append(f"{path.relative_to(ROOT)}:{lineno}")
        self.assertEqual(offenders, [], "`mode=<specialty>` must be a specialty review (STATUS verdict); "
                                        "a consult is `mode=consult specialty=<x>`")

    # R2 (review fix 2): the review frontmatter routes NEEDS_REVISION by FAILURE_ORIGIN, not always to implement-agent.
    def test_R2_review_frontmatter_routes_by_failure_origin(self):
        frontmatter = self.review.split("---", 2)[1]
        self.assertNotIn("re-invoke implement-agent", frontmatter)
        self.assertNotIn("If it returns NEEDS_REVISION", " ".join(frontmatter.split()),
                         "the frontmatter sentence must not leave NEEDS_REVISION dangling after 'If it returns'")
        self.assertTrue(lines_with(frontmatter, "NEEDS_REVISION is routed by FAILURE_ORIGIN"),
                        "review-agent frontmatter must say NEEDS_REVISION is routed by FAILURE_ORIGIN")

    # R2b (review fix 2): the revision template is titled for the implementation origin only.
    def test_R2b_revision_template_names_implementation_origin(self):
        self.assertIn("## 4. Revision after NEEDS_REVISION with FAILURE_ORIGIN: implementation (max 2 per phase)",
                      self.prompts)

    # R3 (triage fix 3): the exact triage template, the first-output rule, and the tier S form.
    def test_R3_triage_line_template_and_first_output(self):
        template = ("Tier {S|M|L} · {operation} · {single|duo|council} · urgency {low|normal|high} · "
                    "uncertainty {low|med|high} · risk {low|med|high} — {one-clause reason}")
        self.assertIn(template, self.skill)
        self.assertIn("Post the triage line", self.skill)
        self.assertIn("1. Post the triage line.", self.skill)
        self.assertIn("Tier S · {operation} — direct", self.skill)
        self.assertTrue(lines_with(self.skill, "classification", "triage"),
                        "the case file classification field must take the triage line")


if __name__ == "__main__":
    unittest.main()
