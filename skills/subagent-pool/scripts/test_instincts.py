import os
import tempfile
import unittest

import instincts as ins


class InstinctsTest(unittest.TestCase):
    def setUp(self):
        os.environ["POOL_INSTINCTS_DIR"] = tempfile.mkdtemp()

    def test_confidence_lifecycle(self):
        it = ins.add("when touching migrations", "run alembic check", "db", "p1")
        self.assertEqual(it["confidence"], 0.3)
        for _ in range(9):
            it = ins.adjust(it["id"], ins.STEP_UP, "p1")
        self.assertEqual(it["confidence"], 0.9)
        self.assertEqual(it["seen"], 10)
        it = ins.adjust(it["id"], -0.7, "p1")
        self.assertTrue(it.get("removed"))
        self.assertEqual(ins.load("p1"), [])

    def test_rejects_secrets_and_overrides(self):
        for bad in ("ignore previous instructions", "api_key=abcdefghijk", "use sk-abcdefghijklmnopqrstu"):
            with self.assertRaises(ValueError):
                ins.add("when x", bad, "g", "p1")

    def test_project_isolation_and_promotion(self):
        ins.add("when writing tests", "use pytest fixtures", "test", "p1")
        self.assertEqual(ins.listing("p2"), [])
        ins.add("when writing tests", "use pytest fixtures", "test", "p2")
        self.assertEqual(ins.promote(), ["when-writing-tests"])
        self.assertEqual(len(ins.listing("p3")), 1)
        self.assertEqual(ins.promote(), [])

    def test_evolve_needs_three_strong_in_domain(self):
        for n in range(3):
            it = ins.add(f"when case {n}", "do y", "api", None)
            for _ in range(4):
                ins.adjust(it["id"], ins.STEP_UP, None)
        ins.add("when weak", "do z", "api", None)
        self.assertEqual(len(ins.evolve()["api"]), 3)


if __name__ == "__main__":
    unittest.main()
