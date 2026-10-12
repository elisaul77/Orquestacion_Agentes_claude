"""Tests for skills_lib.py (run: python3 -B -m unittest discover -s skills/subagent-pool/scripts -v)."""
import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

import skills_lib as sl

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "skills-probadas-template")

SHA = "ab" * 20  # 40 lowercase hex chars
OTHER_SHA = "1f" * 20
URL = "https://github.com/example/skill-x"
BAD_URL = "https://github.com/example/skill-bad"


def good_index(skill_id="skill-x"):
    return {
        "id": skill_id,
        "name": skill_id,
        "source_url": URL,
        "commit": SHA,
        "date": "2026-10-12",
        "reviewer": "gpt-6-astra",
        "verdict": "APPROVED",
        "report": "reports/%s.md" % skill_id,
        "path": "skills/%s/" % skill_id,
    }


def good_veto(skill_id="skill-bad"):
    return {
        "id": skill_id,
        "source_url": BAD_URL,
        "commit": SHA,
        "date": "2026-10-12",
        "reviewer": "claude-fable-5-1",
        "verdict": "REJECTED",
        "reason": "reads ~/.ssh and posts it to a remote host",
    }


def with_field(entry, key, value):
    changed = dict(entry)
    changed[key] = value
    return changed


def without_field(entry, key):
    changed = dict(entry)
    del changed[key]
    return changed


def write_library(directory, index=None, vetadas=None):
    """Write index.json / vetadas.json; a None argument writes nothing for that file."""
    if index is not None:
        with open(os.path.join(directory, "index.json"), "w", encoding="utf-8") as f:
            json.dump(index, f)
    if vetadas is not None:
        with open(os.path.join(directory, "vetadas.json"), "w", encoding="utf-8") as f:
            json.dump(vetadas, f)


class EntryValidationTests(unittest.TestCase):
    def test_valid_index_entry_has_no_errors(self):
        self.assertEqual(sl.check_entry(good_index(), "index"), [])

    def test_valid_veto_entry_has_no_errors(self):
        self.assertEqual(sl.check_entry(good_veto(), "veto"), [])

    def test_short_commit_rejected(self):
        errors = sl.check_entry(with_field(good_index(), "commit", "ab" * 19), "index")
        self.assertTrue(any("commit" in e for e in errors))

    def test_uppercase_commit_rejected(self):
        errors = sl.check_entry(with_field(good_index(), "commit", "AB" * 20), "index")
        self.assertTrue(any("commit" in e for e in errors))

    def test_non_hex_commit_rejected(self):
        errors = sl.check_entry(with_field(good_index(), "commit", "zz" * 20), "index")
        self.assertTrue(any("commit" in e for e in errors))

    def test_bad_date_rejected(self):
        for bad in ("2026-13-01", "12/10/2026", "2026-1-5", "2026-10-12T10:00:00Z"):
            errors = sl.check_entry(with_field(good_index(), "date", bad), "index")
            self.assertTrue(any("date" in e for e in errors), bad)

    def test_index_verdict_must_be_approved(self):
        errors = sl.check_entry(with_field(good_index(), "verdict", "REJECTED"), "index")
        self.assertTrue(any("verdict" in e for e in errors))

    def test_unknown_verdict_rejected(self):
        errors = sl.check_entry(with_field(good_index(), "verdict", "MAYBE"), "index")
        self.assertTrue(any("verdict" in e for e in errors))

    def test_veto_verdict_must_be_rejected_or_doubtful(self):
        errors = sl.check_entry(with_field(good_veto(), "verdict", "APPROVED"), "veto")
        self.assertTrue(any("verdict" in e for e in errors))
        self.assertEqual(sl.check_entry(with_field(good_veto(), "verdict", "DOUBTFUL"), "veto"), [])

    def test_empty_reviewer_rejected(self):
        for value in ("", "   "):
            errors = sl.check_entry(with_field(good_index(), "reviewer", value), "index")
            self.assertTrue(any("reviewer" in e for e in errors), repr(value))

    def test_reviewer_must_be_claude_fable_or_codex_slug(self):
        for bad in ("anybody", "gpt-6", "gpt-6-luna-extra", "claude-fable-5-2", "GPT-6-astra", "gpt-6-astra\n"):
            errors = sl.check_entry(with_field(good_index(), "reviewer", bad), "index")
            self.assertTrue(any("reviewer" in e for e in errors), repr(bad))
            errors = sl.check_entry(with_field(good_veto(), "reviewer", bad), "veto")
            self.assertTrue(any("reviewer" in e for e in errors), repr(bad))

    def test_reviewer_accepts_claude_fable_and_codex_slugs(self):
        for good in ("gpt-6-astra", "gpt-5.5-sol", "gpt-6-terra", "gpt-6-luna", "claude-fable-5-1"):
            self.assertEqual(sl.check_entry(with_field(good_index(), "reviewer", good), "index"), [], good)

    def test_missing_required_fields_rejected(self):
        for key in ("id", "source_url", "commit", "date", "reviewer", "verdict", "name", "report", "path"):
            errors = sl.check_entry(without_field(good_index(), key), "index")
            self.assertTrue(any(key in e for e in errors), key)
        for key in ("id", "source_url", "commit", "date", "reviewer", "verdict", "reason"):
            errors = sl.check_entry(without_field(good_veto(), key), "veto")
            self.assertTrue(any(key in e for e in errors), key)

    def test_missing_reason_rejected_for_veto(self):
        errors = sl.check_entry(without_field(good_veto(), "reason"), "veto")
        self.assertTrue(any("reason" in e for e in errors))

    def test_path_traversal_id_rejected(self):
        errors = sl.check_entry(with_field(good_index("../evil"), "name", "../evil"), "index")
        self.assertTrue(any("id" in e for e in errors))

    def test_name_must_match_id(self):
        errors = sl.check_entry(with_field(good_index(), "name", "other"), "index")
        self.assertTrue(any("name" in e for e in errors))

    def test_report_and_path_must_follow_layout(self):
        errors = sl.check_entry(with_field(good_index(), "report", "x.md"), "index")
        self.assertTrue(any("report" in e for e in errors))
        errors = sl.check_entry(with_field(good_index(), "path", "skills/other/"), "index")
        self.assertTrue(any("path" in e for e in errors))

    def test_non_https_source_rejected(self):
        errors = sl.check_entry(with_field(good_index(), "source_url", "http://x/y"), "index")
        self.assertTrue(any("source_url" in e for e in errors))

    def test_unknown_field_rejected(self):
        errors = sl.check_entry(with_field(good_index(), "comit", SHA), "index")
        self.assertTrue(any("comit" in e for e in errors))

    def test_non_object_entry_rejected(self):
        self.assertTrue(sl.check_entry("not-a-dict", "index"))


class DocumentValidationTests(unittest.TestCase):
    def test_empty_documents_are_valid(self):
        self.assertEqual(sl.validate_document({"version": 1, "skills": []}, "index"), [])
        self.assertEqual(sl.validate_document({"version": 1, "vetadas": []}, "veto"), [])

    def test_wrong_version_rejected(self):
        self.assertTrue(sl.validate_document({"version": 2, "skills": []}, "index"))

    def test_list_key_must_be_list(self):
        self.assertTrue(sl.validate_document({"version": 1, "skills": {}}, "index"))
        self.assertTrue(sl.validate_document([], "index"))

    def test_duplicate_id_rejected(self):
        doc = {"version": 1, "skills": [good_index("dup"), good_index("dup")]}
        errors = sl.validate_document(doc, "index")
        self.assertTrue(any("duplicate" in e for e in errors))


class DirectoryValidationTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_template_is_valid_and_empty(self):
        self.assertEqual(sl.validate_dir(TEMPLATE), [])
        index, vetadas, errors = sl.read_library(TEMPLATE)
        self.assertEqual(errors, [])
        # Invariant: the public repo ships templates only, never real library contents.
        self.assertEqual(index["skills"], [])
        self.assertEqual(vetadas["vetadas"], [])

    def test_valid_library_passes(self):
        write_library(self.dir, {"version": 1, "skills": [good_index()]},
                      {"version": 1, "vetadas": [good_veto()]})
        self.assertEqual(sl.validate_dir(self.dir), [])

    def test_missing_file_reported(self):
        write_library(self.dir, index={"version": 1, "skills": []})
        errors = sl.validate_dir(self.dir)
        self.assertTrue(any("vetadas.json" in e and "missing" in e for e in errors))

    def test_invalid_json_reported(self):
        write_library(self.dir, index={"version": 1, "skills": []}, vetadas={"version": 1, "vetadas": []})
        with open(os.path.join(self.dir, "index.json"), "w", encoding="utf-8") as f:
            f.write("{not json")
        errors = sl.validate_dir(self.dir)
        self.assertTrue(any("index.json" in e and "invalid JSON" in e for e in errors))

    def test_source_both_approved_and_vetoed_rejected(self):
        write_library(self.dir, {"version": 1, "skills": [good_index()]},
                      {"version": 1, "vetadas": [with_field(good_veto(), "source_url", URL)]})
        errors = sl.validate_dir(self.dir)
        self.assertTrue(any("vetadas.json" in e and URL in e for e in errors))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(sl.main(["skills_lib.py", "validate", self.dir]), 1)

    def test_cli_validate_exit_codes(self):
        write_library(self.dir, {"version": 1, "skills": []}, {"version": 1, "vetadas": []})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sl.main(["skills_lib.py", "validate", self.dir]), 0)
        write_library(self.dir, {"version": 1, "skills": [with_field(good_index(), "commit", "x")]},
                      {"version": 1, "vetadas": []})
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(sl.main(["skills_lib.py", "validate", self.dir]), 1)


class LookupTests(unittest.TestCase):
    def setUp(self):
        self.index = {"version": 1, "skills": [good_index("skill-x")]}
        self.vetadas = {"version": 1, "vetadas": [good_veto("skill-bad")]}

    def test_approved_lookup(self):
        result = sl.lookup("skill-x", self.index, self.vetadas)
        self.assertEqual(result["outcome"], "approved")
        self.assertEqual(result["entry"]["id"], "skill-x")

    def test_vetoed_lookup(self):
        result = sl.lookup("skill-bad", self.index, self.vetadas)
        self.assertEqual(result["outcome"], "vetoed")
        self.assertEqual(result["entry"]["reason"], good_veto()["reason"])

    def test_unknown_lookup(self):
        result = sl.lookup("nope", self.index, self.vetadas)
        self.assertEqual(result, {"outcome": "unknown", "entry": None})

    def test_vetoed_beats_approved_when_both_present(self):
        index = {"version": 1, "skills": [good_index("dual")]}
        vetadas = {"version": 1, "vetadas": [good_veto("dual")]}
        result = sl.lookup("dual", index, vetadas)
        self.assertEqual(result["outcome"], "vetoed")

    def test_vetoed_by_source_url_beats_approved_id(self):
        index = {"version": 1, "skills": [good_index("foo")]}
        vetadas = {"version": 1, "vetadas": [with_field(good_veto("bar"), "source_url", URL)]}
        result = sl.lookup("foo", index, vetadas)
        self.assertEqual(result["outcome"], "vetoed")
        self.assertEqual(result["entry"]["id"], "bar")

    def test_is_vetada_matches_url_regardless_of_commit(self):
        self.assertTrue(sl.is_vetada(BAD_URL, self.vetadas))
        self.assertFalse(sl.is_vetada(URL, self.vetadas))

    def test_needs_review_false_when_pinned_equals_upstream(self):
        self.assertFalse(sl.needs_review(URL, SHA, self.index, self.vetadas))

    def test_needs_review_true_when_upstream_moved(self):
        self.assertTrue(sl.needs_review(URL, OTHER_SHA, self.index, self.vetadas))

    def test_needs_review_true_for_unknown_source(self):
        self.assertTrue(sl.needs_review("https://github.com/example/new", SHA, self.index, self.vetadas))

    def test_needs_review_false_for_vetoed_source(self):
        self.assertFalse(sl.needs_review(BAD_URL, OTHER_SHA, self.index, self.vetadas))


class ExtensionPointTests(unittest.TestCase):
    def test_extra_checks_hook_is_applied(self):
        def reject_all(entry, kind):
            return ["hook says no"]

        sl.EXTRA_CHECKS.append(reject_all)
        try:
            errors = sl.check_entry(good_index(), "index")
        finally:
            sl.EXTRA_CHECKS.remove(reject_all)
        self.assertIn("hook says no", errors)
        self.assertEqual(sl.check_entry(good_index(), "index"), [])


OFFICIAL_URL = "https://github.com/anthropics/skills/tree/main/skills/pdf"


def good_candidate(**overrides):
    candidate = {
        "name": "pdf",
        "source_url": OFFICIAL_URL,
        "last_update": "2026-09-15",
        "model": "claude-opus-5-5",
    }
    candidate.update(overrides)
    return candidate


class OfficialSourceTests(unittest.TestCase):
    def test_official_sources_file_lists_vendor_repos_and_skills_sh_discovery_only(self):
        entries = {e["url"]: e for e in sl.load_official_sources()}
        for url in ("https://github.com/anthropics/skills", "https://github.com/openai/skills",
                    "https://github.com/vercel-labs/agent-skills"):
            self.assertIn(url, entries)
            self.assertFalse(entries[url]["discovery_only"], url)
        self.assertTrue(entries["https://skills.sh"]["discovery_only"])

    def test_vendor_repo_paths_are_official(self):
        for url in (OFFICIAL_URL, "https://github.com/openai/skills", "https://github.com/vercel-labs/agent-skills/tree/main/x"):
            self.assertTrue(sl.official(url), url)

    def test_case_insensitive_github_owner_is_official(self):
        self.assertTrue(sl.official("https://GitHub.com/Anthropics/Skills"))

    def test_skills_sh_is_discovery_only_not_official(self):
        self.assertFalse(sl.official("https://skills.sh/anthropics/skills/pdf"))

    def test_lookalike_hosts_and_owners_rejected(self):
        bad = [
            "https://github.com/anthropics-evil/skills",
            "https://github.com/anthropics/skills-evil",
            "https://github.com.evil.com/anthropics/skills",
            "https://evil.com/github.com/anthropics/skills",
            "https://github.com@evil.com/anthropics/skills",
            "https://anthropics@github.com/anthropics/skills",
            "https://github.com:8443/anthropics/skills",
            "http://github.com/anthropics/skills",
            "https://github.com/someone/skills",
            "https://github.com/anthropics",
            "https://github.com/",
            "not a url",
            "",
        ]
        for url in bad:
            self.assertFalse(sl.official(url), repr(url))

    def test_official_uses_explicit_sources(self):
        custom = [{"url": "https://github.com/example/skills", "discovery_only": False}]
        self.assertTrue(sl.official("https://github.com/example/skills", custom))
        self.assertFalse(sl.official(OFFICIAL_URL, custom))


class FreshnessTests(unittest.TestCase):
    def test_updated_after_release_is_kept(self):
        self.assertTrue(sl.freshness("2026-10-01", "2026-09-01"))
        self.assertEqual(sl.freshness_status("2026-10-01", "2026-09-01"), "keep")

    def test_same_day_is_kept(self):
        self.assertEqual(sl.freshness_status("2026-09-01", "2026-09-01"), "keep")

    def test_updated_before_release_is_skipped(self):
        self.assertFalse(sl.freshness("2026-08-01", "2026-09-01"))
        self.assertEqual(sl.freshness_status("2026-08-01", "2026-09-01"), "skip")

    def test_unknown_release_is_not_skipped_but_flagged(self):
        self.assertEqual(sl.freshness_status("2026-08-01", None), "unknown")
        self.assertTrue(sl.freshness("2026-08-01", None))

    def test_bad_dates_raise(self):
        with self.assertRaises(ValueError):
            sl.freshness_status("2026-13-01", "2026-09-01")
        with self.assertRaises(ValueError):
            sl.freshness_status("2026-09-01", "yesterday")

    def test_release_table_parses_rows_and_todo(self):
        text = (
            "## Model release dates\n\n"
            "| Model | Release date |\n"
            "|---|---|\n"
            "| `claude-opus-5-5` | 2026-07-01 (verify) |\n"
            "| `claude-sonnet-5-5` | TODO (verify) |\n"
            "| not a model row | 2026-01-01 |\n"
            "## Other section\n"
            "| `claude-haiku-5-5` | 2026-02-01 |\n"
        )
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "lib.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            releases = sl.load_model_releases(path)
        self.assertEqual(releases, {"claude-opus-5-5": "2026-07-01", "claude-sonnet-5-5": None})

    def test_real_release_table_lists_required_models(self):
        releases = sl.load_model_releases()
        for model in ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-1"):
            self.assertIn(model, releases)
            value = releases[model]
            self.assertTrue(value is None or sl.DATE_RE.match(value), model)


class CandidateTests(unittest.TestCase):
    def test_valid_candidate_with_known_release_is_reviewable(self):
        with mock.patch.dict(sl.MODEL_RELEASES, {"claude-opus-5-5": "2026-09-01"}, clear=True):
            outcome = sl.candidate_outcome(good_candidate())
        self.assertEqual(outcome, {"outcome": "review", "errors": [], "flags": []})

    def test_stale_candidate_is_skipped(self):
        with mock.patch.dict(sl.MODEL_RELEASES, {"claude-opus-5-5": "2026-10-01"}, clear=True):
            outcome = sl.candidate_outcome(good_candidate(last_update="2026-09-15"))
        self.assertEqual(outcome["outcome"], "skip")
        self.assertTrue(any("stale" in e for e in outcome["errors"]))

    def test_unknown_release_is_flagged_not_skipped(self):
        with mock.patch.dict(sl.MODEL_RELEASES, {"claude-opus-5-5": None}, clear=True):
            outcome = sl.candidate_outcome(good_candidate())
        self.assertEqual(outcome["outcome"], "review")
        self.assertTrue(any("claude-opus-5-5" in f for f in outcome["flags"]))

    def test_non_official_candidate_is_skipped(self):
        with mock.patch.dict(sl.MODEL_RELEASES, {"claude-opus-5-5": None}, clear=True):
            outcome = sl.candidate_outcome(good_candidate(source_url="https://skills.sh/x/y/pdf"))
        self.assertEqual(outcome["outcome"], "skip")
        self.assertTrue(any("official" in e for e in outcome["errors"]))

    def test_candidate_missing_or_bad_fields_rejected(self):
        for key in ("name", "source_url", "last_update", "model"):
            errors = sl.check_candidate(without_field(good_candidate(), key))
            self.assertTrue(any(key in e for e in errors), key)
        self.assertTrue(sl.check_candidate(good_candidate(last_update="12/09/2026")))
        self.assertTrue(sl.check_candidate(with_field(good_candidate(), "extra", 1)))
        self.assertTrue(sl.check_candidate("not-a-dict"))

    def test_candidate_hook_is_registered_and_ignores_library_entries(self):
        self.assertTrue(any(hook is sl.candidate_hook for hook in sl.EXTRA_CHECKS))
        self.assertEqual(sl.check_entry(good_index(), "index"), [])
        self.assertEqual(sl.check_entry(good_veto(), "veto"), [])


class VerdictTests(unittest.TestCase):
    def good_verdict(self, **overrides):
        verdict = {
            "verdict": "APPROVED",
            "reviewer": "gpt-6-astra",
            "commit": SHA,
            "source_url": OFFICIAL_URL,
            "reasons": ["no network calls", "no shell risks found"],
        }
        verdict.update(overrides)
        return verdict

    def test_valid_verdict_passes(self):
        self.assertEqual(sl.check_verdict(self.good_verdict()), [])
        self.assertEqual(sl.check_verdict(self.good_verdict(verdict="DOUBTFUL", reviewer="claude-fable-5-1")), [])

    def test_bad_verdict_fields_rejected(self):
        self.assertTrue(sl.check_verdict(self.good_verdict(verdict="MAYBE")))
        self.assertTrue(sl.check_verdict(self.good_verdict(reviewer="someone")))
        self.assertTrue(sl.check_verdict(self.good_verdict(commit="short")))
        self.assertTrue(sl.check_verdict(self.good_verdict(source_url=BAD_URL)))
        self.assertTrue(sl.check_verdict(self.good_verdict(reasons="just a string")))
        self.assertTrue(sl.check_verdict(self.good_verdict(reasons=["ok", ""])))
        self.assertTrue(sl.check_verdict(self.good_verdict(reasons=["x"] * 21)))
        self.assertTrue(sl.check_verdict(without_field(self.good_verdict(), "reasons")))
        self.assertTrue(sl.check_verdict(with_field(self.good_verdict(), "extra", 1)))

    def test_cli_official_and_check_verdict_exit_codes(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sl.main(["skills_lib.py", "official", OFFICIAL_URL]), 0)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(sl.main(["skills_lib.py", "official", "https://skills.sh/a/b"]), 1)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "verdict.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.good_verdict(), f)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(sl.main(["skills_lib.py", "check-verdict", path]), 0)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.good_verdict(verdict="MAYBE"), f)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(sl.main(["skills_lib.py", "check-verdict", path]), 1)


class SplitReviewTests(unittest.TestCase):
    def answer(self, **overrides):
        data = {
            "verdict": "APPROVED",
            "reviewer": "gpt-6-astra",
            "commit": SHA,
            "source_url": OFFICIAL_URL,
            "reasons": ["no network calls"],
            "report": "# Report\n\n## Verdict rationale\nClean.\n",
        }
        data.update(overrides)
        return data

    def test_split_returns_verdict_without_report(self):
        verdict, report = sl.split_review(self.answer(), SHA, OFFICIAL_URL)
        self.assertNotIn("report", verdict)
        self.assertEqual(verdict["verdict"], "APPROVED")
        self.assertIn("Verdict rationale", report)

    def test_split_rejects_missing_report(self):
        data = self.answer()
        del data["report"]
        with self.assertRaises(ValueError):
            sl.split_review(data, SHA, OFFICIAL_URL)

    def test_split_rejects_commit_or_source_mismatch(self):
        with self.assertRaises(ValueError):
            sl.split_review(self.answer(), OTHER_SHA, OFFICIAL_URL)
        with self.assertRaises(ValueError):
            sl.split_review(self.answer(), SHA, "https://github.com/openai/skills")

    def test_split_rejects_extra_fields(self):
        with self.assertRaises(ValueError):
            sl.split_review(self.answer(extra="x"), SHA, OFFICIAL_URL)

    def test_cli_split_review_writes_report(self):
        with tempfile.TemporaryDirectory() as d:
            review = os.path.join(d, "review.json")
            report = os.path.join(d, "report.md")
            with open(review, "w", encoding="utf-8") as f:
                json.dump(self.answer(), f)
            with contextlib.redirect_stdout(io.StringIO()):
                code = sl.main(["skills_lib.py", "split-review", review, report, SHA, OFFICIAL_URL])
            self.assertEqual(code, 0)
            with open(report, encoding="utf-8") as f:
                self.assertIn("Clean.", f.read())
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(sl.main(["skills_lib.py", "split-review", review, report, OTHER_SHA, OFFICIAL_URL]), 1)

    def test_cli_candidate_prints_outcome(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "candidate.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(good_candidate(source_url="https://skills.sh/a/b"), f)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(sl.main(["skills_lib.py", "candidate", path]), 0)
            self.assertEqual(json.loads(out.getvalue())["outcome"], "skip")


if __name__ == "__main__":
    unittest.main()
