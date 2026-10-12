"""Tests for skills_lib.py (run: python3 -B -m unittest discover -s skills/subagent-pool/scripts -v)."""
import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
