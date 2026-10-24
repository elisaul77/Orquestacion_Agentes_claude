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

    # ---- v9.12.0 (STRUCTURAL: these prove the rules are written; routing behavior is measured in competition/) ----

    @staticmethod
    def _section(text, start, end):
        """Text from the heading `start` up to (not including) the heading `end`."""
        head = text.index(start)
        return text[head: text.index(end, head)]

    WARNINGS_CONTRACT = 'WARNINGS: {anything noticed but not fixed — edge cases, risks, follow-ups — or "none"}'

    # M1 (v9.12 binding review): the Conductor can't drop a NEEDS_REVISION finding on its own.
    def test_M1_review_finding_is_binding(self):
        self.assertIn("A review finding is binding", self.skill)
        self.assertIn("may not drop, downgrade or defer a NEEDS_REVISION finding on its own", self.skill)
        self.assertIn("recorded risk", self.skill)
        self.assertIn("A NEEDS_REVISION finding is binding", self.agents_md)

    # M2 (v9.12 warnings): WARNINGS in the implement contract (agent, prompts, AgentArchitect template),
    # an open-WARNINGS rule in SKILL §7, and a ruling on every item in the review contract.
    def test_M2_warnings_in_implement_contract_and_review(self):
        implement = read(AGENTS_DIR / "implement-agent.agent.md")
        architect = read(AGENTS_DIR / "AgentArchitect.agent.md")
        prompts_impl = self._section(self.prompts, "## 2. implement-agent", "## 3. review-agent")
        self.assertIn(self.WARNINGS_CONTRACT, implement)
        self.assertIn(self.WARNINGS_CONTRACT, prompts_impl)
        self.assertIn(self.WARNINGS_CONTRACT, architect, "AgentArchitect Implementer template must carry WARNINGS")
        self.assertIn("Open WARNINGS block closing the phase", self.skill)
        self.assertIn("must rule on every WARNINGS item", self.review)
        self.assertIn("WARNINGS_RULING:", self.review)
        self.assertIn("WARNINGS_RULING:", self._section(self.prompts, "## 3. review-agent", "## 3b."))

    # M3 (v9.12 no git by the Conductor): delegate all git; a merge is Approve-tier and an ambiguous yes is no.
    def test_M3_conductor_never_runs_git_and_merge_is_approve(self):
        self.assertIn("Never run git yourself", self.skill)
        self.assertIn("an ambiguous answer is not approval", self.skill)
        approve = lines_with(self.skill, "| **approve**")
        self.assertTrue(approve, "SKILL.md must keep the Approve row")
        self.assertTrue(any("`git merge`" in ln for ln in approve), "the Approve row must name `git merge`")

    # M4 (v9.12 inline falsifier): a self-diagnosed fix still states a hypothesis and what would disprove it.
    def test_M4_inline_falsifier_for_self_diagnosis(self):
        self.assertIn("If you diagnose a fix yourself (no planning-agent), still write one line", self.skill)
        self.assertIn("the implementer turns it into the failing test first", self.skill)
        prompts_impl = self._section(self.prompts, "## 2. implement-agent", "## 3. review-agent")
        self.assertIn("Hypothesis / falsifier:", prompts_impl)

    # M5 (v9.12 explicit orchestration): a tier S triage on an explicit "orchestrate" is said out loud.
    def test_M5_explicit_orchestration_is_said_not_dropped(self):
        self.assertIn("If the user explicitly asked to orchestrate and triage says tier S", self.skill)
        self.assertIn("never drop below the review step", self.skill)

    # M7 (v9.12 experimental labels): unmeasured parts are labelled in both READMEs; a measured note exists.
    def test_M7_readme_experimental_labels_and_measured_note(self):
        labels = (
            ("README.md", self.readme, "experimental — written and reviewed, not yet measured in real runs",
             "### What was measured"),
            ("README.es.md", self.readme_es, "experimental — escrito y revisado, aún no medido en ejecuciones reales",
             "### Qué se midió"),
        )
        for name, text, label, heading in labels:
            self.assertGreaterEqual(text.count(label), 3,
                                    f"{name} must label FAILURE_ORIGIN routing, consult and the lateral's second voice")
            self.assertIn(heading, text, f"{name} must carry a short measured note")


    # ---- v9.12.0 revision 1 (review fixes: warnings inside the decision tree, accepted risks, schema, reviewer template)

    @staticmethod
    def _schema_strict_problems(node, path="$"):
        """Every object with `properties` must list every property in `required`, and forbid extras (OpenAI strict mode)."""
        problems = []
        if isinstance(node, dict):
            if "properties" in node:
                if node.get("additionalProperties") is not False:
                    problems.append(f"{path}: additionalProperties must be false")
                missing = set(node["properties"]) - set(node.get("required", []))
                if missing:
                    problems.append(f"{path}: not in required: {sorted(missing)}")
                for key, sub in node["properties"].items():
                    problems += CaseFlowTest._schema_strict_problems(sub, f"{path}.{key}")
            if "items" in node:
                problems += CaseFlowTest._schema_strict_problems(node["items"], f"{path}[]")
        return problems

    # M8 (rev1 item 1): the decision tree itself routes WARNINGS before an APPROVED phase advances.
    def test_M8_warnings_inside_decision_tree(self):
        tree = self._section(self.skill, "**Review routing.**", "Cap: at most 3 re-routes")
        self.assertIn("APPROVED with any `must fix`", tree)
        self.assertIn("treat as NEEDS_REVISION (implementation)", tree)
        self.assertIn("APPROVED with `acceptable` warnings", tree)
        self.assertIn("explicitly accepts them", tree)
        self.assertIn("same implementation loop counter", tree)
        self.assertIn("escalates to the user", tree)
        self.assertIn("never retried silently or dropped", tree)
        self.assertIn("Open WARNINGS block closing the phase", self.skill)
        self.assertIn("must fix", self._section(self.skill, "**Open WARNINGS block", "Cap: at most 3"))

    # M9 (rev1 item 2): accepted risks are a case-file field, written only after an explicit user answer.
    def test_M9_accepted_risks_field_and_line(self):
        self.assertTrue(lines_with(self.skill, "case file", "accepted risks"),
                        "the one-line case-file field list must carry `accepted risks`")
        self.assertIn("ACCEPTED_RISK: {item} — {user's words} — {date}", self.skill)
        self.assertIn("marks the ledger row accepted", self.skill)
        self.assertIn("only after an explicit user answer", self.skill)

    # M10 (rev1 item 3): reviewer disagreement is settled by a clarifying question, never a unilateral call.
    def test_M10_reviewer_disagreement_has_no_unilateral_decision(self):
        section = self._section(self.skill, "## 10b.", "## 11.")
        self.assertNotIn("you decide", section.lower())
        self.assertIn("ask the reviewer with the weaker evidence one clarifying question", section)
        self.assertIn("if still split, the user decides", section)
        self.assertIn("Never drop a NEEDS_REVISION finding yourself", section)

    # M11 (rev1 item 4): the Codex verdict schema requires warnings and warnings_ruling; strict mode holds.
    def test_M11_codex_schema_requires_warnings_keys(self):
        import json
        schema = json.loads(read(SKILL / "assets" / "codex-verdict.schema.json"))
        for key in ("warnings", "warnings_ruling"):
            self.assertIn(key, schema["properties"], f"schema must define {key}")
            self.assertEqual(schema["properties"][key]["type"], "array")
            self.assertEqual(schema["properties"][key]["items"], {"type": "string"})
            self.assertIn(key, schema["required"], f"schema must require {key}")
        self.assertEqual(self._schema_strict_problems(schema), [])

    # M12 (rev1 item 4): the codex relay brief and return contract carry WARNINGS and WARNINGS_RULING.
    def test_M12_codex_agent_relays_warnings(self):
        codex = read(AGENTS_DIR / "optional" / "codex-agent.agent.md")
        self.assertIn("`warnings`", codex, "the brief must tell Codex to fill or [] warnings")
        self.assertIn("`warnings_ruling`", codex)
        self.assertTrue(lines_with(codex, "warnings: <"), "return contract needs a WARNINGS: line")
        self.assertIn("WARNINGS_RULING: <", codex)

    # M13 (rev1 item 5): the AgentArchitect Reviewer template rules on every warning.
    def test_M13_architect_reviewer_template_rules_warnings(self):
        architect = read(AGENTS_DIR / "AgentArchitect.agent.md")
        reviewer = self._section(architect, "**Reviewer:**", "## Return contract")
        self.assertIn("WARNINGS item", reviewer)
        self.assertIn("fixed / acceptable / must fix", reviewer)
        self.assertIn("a must fix makes the verdict at least NEEDS_REVISION", reviewer)
        self.assertIn("WARNINGS_RULING:", reviewer)

    # M14 (rev1 item 6): the review verdict table names the must-fix rule.
    def test_M14_review_table_must_fix_row(self):
        self.assertTrue(lines_with(self.review, "|", "must fix", "at least", "NEEDS_REVISION"),
                        "review-agent verdict table needs the row: must fix WARNINGS ruling => at least NEEDS_REVISION")

    # M15 (rev1 item 7): the implement brief makes the falsifier line required when the Conductor diagnosed the fix.
    def test_M15_falsifier_line_required_for_conductor_diagnosis(self):
        prompts_impl = self._section(self.prompts, "## 2. implement-agent", "## 3. review-agent")
        self.assertTrue(lines_with(prompts_impl, "hypothesis / falsifier:", "required when the conductor diagnosed"),
                        "prompts.md §2 must make the falsifier line required when the Conductor diagnosed the fix")
        self.assertIn('otherwise "n/a"', prompts_impl)

    # M16 (rev2): every implementer WARNINGS item needs exactly one ruling, checked before any verdict rule.
    def test_M16_ruling_coverage_is_first_in_decision_tree(self):
        tree = self._section(self.skill, "**Review routing.**", "Cap: at most 3 re-routes")
        self.assertIn("Ruling coverage", tree)
        self.assertIn("every WARNINGS item from the implementer must have exactly one ruling", tree)
        self.assertIn("ask the reviewer once for the missing rulings", tree)
        self.assertIn("still missing → escalate to the user", tree)
        self.assertIn("Do not advance the phase meanwhile", tree)
        self.assertLess(tree.index("Ruling coverage"), tree.index("APPROVED with any `must fix`"),
                        "the ruling-coverage check must come before the APPROVED rule (first match wins)")
        self.assertLess(tree.index("Ruling coverage"), tree.index("FAILED → consult the user"),
                        "the ruling-coverage check applies to any verdict, FAILED included")
        self.assertTrue(lines_with(self.review, "WARNINGS_RULING", "empty", "only when WARNINGS is \"none\""),
                        "review-agent must state that an empty WARNINGS_RULING is valid only when WARNINGS is none")

    # ---- v9.13.0 (spec-anchored specs + EARS requirement IDs)

    # S1: specs/NNN-slug/ with spec/plan/tasks lives in the repo, and the spec is synced before Gate 2.
    def test_S1_spec_folder_and_sync_before_gate2(self):
        for f in ("specs/NNN-slug/", "spec.md", "plan.md", "tasks.md", "Spec sync before Gate 2"):
            self.assertIn(f, self.skill, f"SKILL.md must describe {f}")
        self.assertIn("Spec sync", self.prompts, "prompts.md needs the spec sync brief")
        self.assertTrue(lines_with(self.skill, "Never edit an RF", "user's decision"),
                        "the sync must never rewrite an RF to excuse a failing criterion")
        self.assertTrue(lines_with(self.skill, "Gate 2", "spec sync"), "Gate 2 must come after the spec sync")

    # S2: RF-n in EARS, cited by ledger rows, tasks, implement and review contracts.
    def test_S2_rf_ids_in_ears_traced_everywhere(self):
        for pat in ("When <trigger>", "While <state>", "If <condition>, then", "Where <feature>"):
            self.assertIn(pat, self.skill, f"SKILL.md must list the EARS pattern {pat}")
        self.assertIn("| # | RF | Criterion |", self.skill, "the criteria ledger needs an RF column")
        self.assertIn("Covers: {RF-n", self.prompts, "the implement brief must name the RF-n it covers")
        self.assertIn("{RF-n or n/a}", self.review, "review-agent CRITERIA must cite the RF-n")
        self.assertIn("RF-n", self.planning, "planning-agent must draft RF-n requirements")


if __name__ == "__main__":
    unittest.main()
