import unittest

from trim_output import trim


class TrimOutputTest(unittest.TestCase):
    def test_keeps_failures_and_summary_drops_noise(self):
        lines = [f"test_{i} PASSED" for i in range(350)] + [
            "===== FAILURES =====", "___ test_a ___", "AssertionError: 1 != 2",
            "===== 1 failed, 350 passed in 2s ====="]
        out = trim(lines)
        self.assertIn("AssertionError: 1 != 2", out)
        self.assertIn("===== 1 failed, 350 passed in 2s =====", out)
        self.assertLess(len(out), 20)
        self.assertTrue(out[0].startswith("[trim_output] 354 lines"))
        self.assertNotIn("test_5 PASSED", out)

    def test_failure_line_mentioning_passed_is_kept(self):
        lines = ["test_a PASSED"] * 5 + ["AssertionError: expected PASSED got FAILED"]
        self.assertIn("AssertionError: expected PASSED got FAILED", trim(lines, context=0))

    def test_real_unittest_message_with_ok_and_dashes_survives(self):
        import io, unittest as ut
        msg = "\n".join([*(f"diagnostic {i:03}" for i in range(80)), "ok", "-" * 70,
                         *(f"diagnostic {i:03}" for i in range(80, 200))])

        class T(ut.TestCase):
            def test_a(self):
                pass

            def test_b(self):
                self.fail(msg)
        buf = io.StringIO()
        ut.TextTestRunner(stream=buf, verbosity=2).run(ut.defaultTestLoader.loadTestsFromTestCase(T))
        out = trim(buf.getvalue().splitlines(), context=0, max_lines=5)
        for i in range(200):
            self.assertTrue(any(f"diagnostic {i:03}" in l for l in out), i)

    def test_all_green_shows_tail(self):
        lines = ["."] * 100 + ["Ran 100 tests in 0.1s", "", "OK"]
        out = trim(lines)
        self.assertIn("OK", out)
        self.assertIn("Ran 100 tests in 0.1s", out)

    def test_never_caps_failure_lines(self):
        lines = [f"ERROR case {i}" for i in range(500)]
        out = trim(lines, context=0, max_lines=40)
        self.assertEqual(sum(l.startswith("ERROR case") for l in out), 500)

    def test_caps_only_context(self):
        lines = (["noise line"] * 3 + ["ERROR x"]) * 50
        out = trim(lines, context=3, max_lines=60)
        self.assertEqual(sum(l == "ERROR x" for l in out), 50)
        self.assertLessEqual(sum(l == "noise line" for l in out), 10)

    def test_unittest_traceback_block_kept_whole(self):
        detail = [f"    continuation line {i} of a long diff" for i in range(40)]
        lines = ["." * 30, "=" * 70, "FAIL: test_x (t.T)", "-" * 70, "Traceback (most recent call last):",
                 '  File "t.py", line 9, in test_x', "AssertionError: lists differ", *detail, "",
                 "-" * 70, "Ran 31 tests in 0.1s", "", "FAILED (failures=1)"]
        out = trim(lines, context=1, max_lines=10)
        for d in detail:
            self.assertIn(d, out)
        self.assertIn("FAILED (failures=1)", out)

    def test_pytest_failure_section_kept_whole(self):
        detail = [f"E       RuntimeError detail {i}" for i in range(90)] + [f"    frame {i}" for i in range(20)]
        lines = ["tests/test_a.py ....F", "=" * 20 + " FAILURES " + "=" * 20, "_" * 10 + " test_boom " + "_" * 10,
                 "    def test_boom():", ">       raise RuntimeError('x')", *detail,
                 "=" * 10 + " short test summary info " + "=" * 10, "FAILED tests/test_a.py::test_boom",
                 "=" * 10 + " 1 failed, 4 passed in 0.2s " + "=" * 10]
        out = trim(lines)
        for d in detail:
            self.assertIn(d, out)
        self.assertIn("FAILED tests/test_a.py::test_boom", out)


if __name__ == "__main__":
    unittest.main()
