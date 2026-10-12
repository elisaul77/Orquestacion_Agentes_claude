"""Tests for codex-models.py (run: python3 -m unittest discover -s skills/subagent-pool/scripts -v)."""
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "fixtures", "models_cache.sample.json")

_spec = importlib.util.spec_from_file_location(
    "codex_models", os.path.join(HERE, "codex-models.py"))
cm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cm)

FIXTURE_FETCHED = datetime(2026, 10, 12, 18, 5, 35, tzinfo=timezone.utc)


def write_cache(directory, models, fetched_at=None):
    path = os.path.join(directory, "models_cache.json")
    payload = {"models": models}
    if fetched_at is not None:
        payload["fetched_at"] = fetched_at
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return path


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class ResolveFixtureTests(unittest.TestCase):
    def test_fixture_picks_latest_per_role(self):
        result = cm.resolve(FIXTURE, now=FIXTURE_FETCHED + timedelta(days=1))
        self.assertEqual(result["source"], "cache")
        self.assertEqual(result["plan"], "gpt-6-astra")
        self.assertEqual(result["review"], "gpt-6-astra")
        self.assertEqual(result["implement"], "gpt-6-sol")
        self.assertEqual(result["implement-light"], "gpt-6-luna")
        self.assertEqual(result["fetched_at"], "2026-10-12T18:05:35.650595741Z")
        self.assertNotIn("note", result)

    def test_terra_is_never_used_for_a_role(self):
        result = cm.resolve(FIXTURE, now=FIXTURE_FETCHED + timedelta(days=1))
        for role in ("plan", "review", "implement", "implement-light"):
            self.assertNotIn("terra", result[role])


class VersionOrderingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def resolve_models(self, models):
        path = write_cache(self.tmp.name, models, iso(FIXTURE_FETCHED))
        return cm.resolve(path, now=FIXTURE_FETCHED + timedelta(days=1))

    def test_numeric_tuple_order_6_1_beats_6_beats_5_6(self):
        result = self.resolve_models([
            {"slug": "gpt-5.6-sol", "visibility": "list"},
            {"slug": "gpt-6-sol", "visibility": "list"},
            {"slug": "gpt-6.1-sol", "visibility": "list"},
        ])
        self.assertEqual(result["implement"], "gpt-6.1-sol")

    def test_ten_beats_nine_not_string_order(self):
        result = self.resolve_models([
            {"slug": "gpt-9-sol", "visibility": "list"},
            {"slug": "gpt-10-sol", "visibility": "list"},
        ])
        self.assertEqual(result["implement"], "gpt-10-sol")

    def test_hidden_models_are_ignored_even_if_newer(self):
        result = self.resolve_models([
            {"slug": "gpt-6-sol", "visibility": "list"},
            {"slug": "gpt-7-sol", "visibility": "hide"},
        ])
        self.assertEqual(result["implement"], "gpt-6-sol")

    def test_non_family_slugs_are_ignored(self):
        result = self.resolve_models([
            {"slug": "gpt-reserve", "visibility": "list"},
            {"slug": "gpt-7.0-preview", "visibility": "list"},
            {"slug": "codex-auto-review", "visibility": "list"},
            {"slug": "gpt-6-luna", "visibility": "list"},
        ])
        self.assertIsNone(result["implement"])
        self.assertEqual(result["implement-light"], "gpt-6-luna")

    def test_missing_family_gives_null_role_and_note(self):
        result = self.resolve_models([{"slug": "gpt-6-astra", "visibility": "list"}])
        self.assertEqual(result["plan"], "gpt-6-astra")
        self.assertIsNone(result["implement"])
        self.assertIn("implement", result["note"])


class FallbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def assert_default(self, result):
        self.assertEqual(result["source"], "default")
        for role in ("plan", "review", "implement", "implement-light"):
            self.assertIsNone(result[role])
        self.assertIn("note", result)

    def test_missing_file_falls_back(self):
        result = cm.resolve(os.path.join(self.tmp.name, "nope.json"))
        self.assert_default(result)

    def test_corrupt_json_falls_back(self):
        path = os.path.join(self.tmp.name, "models_cache.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("{not json")
        self.assert_default(cm.resolve(path))

    def test_wrong_shape_falls_back(self):
        path = os.path.join(self.tmp.name, "models_cache.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(["unexpected"], f)
        self.assert_default(cm.resolve(path))

    def test_bad_fetched_at_falls_back(self):
        path = write_cache(self.tmp.name, [{"slug": "gpt-6-sol", "visibility": "list"}], "yesterday")
        self.assert_default(cm.resolve(path))

    def test_stale_cache_older_than_14_days_falls_back(self):
        path = write_cache(self.tmp.name, [{"slug": "gpt-6-sol", "visibility": "list"}],
                           iso(FIXTURE_FETCHED))
        self.assert_default(cm.resolve(path, now=FIXTURE_FETCHED + timedelta(days=15)))

    def test_cache_13_days_old_is_still_used(self):
        path = write_cache(self.tmp.name, [{"slug": "gpt-6-sol", "visibility": "list"}],
                           iso(FIXTURE_FETCHED))
        result = cm.resolve(path, now=FIXTURE_FETCHED + timedelta(days=13))
        self.assertEqual(result["source"], "cache")
        self.assertEqual(result["implement"], "gpt-6-sol")

    def test_main_exits_zero_on_missing_cache_and_prints_json(self):
        buf = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            code = cm.main(["--cache", os.path.join(self.tmp.name, "nope.json")])
        self.assertEqual(code, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["source"], "default")
        self.assertIsNone(data["plan"])
        self.assertIn("fallback", err.getvalue().lower())

    def test_env_var_overrides_default_cache_path(self):
        path = write_cache(self.tmp.name, [{"slug": "gpt-6-sol", "visibility": "list"}],
                           iso(datetime.now(timezone.utc)))
        old = os.environ.get("CODEX_MODELS_CACHE")
        os.environ["CODEX_MODELS_CACHE"] = path
        self.addCleanup(lambda: os.environ.pop("CODEX_MODELS_CACHE", None) if old is None
                        else os.environ.__setitem__("CODEX_MODELS_CACHE", old))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cm.main([])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(buf.getvalue())["implement"], "gpt-6-sol")


if __name__ == "__main__":
    unittest.main()
