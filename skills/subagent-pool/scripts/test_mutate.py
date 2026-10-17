import os
import tempfile
import unittest
from pathlib import Path

import mutate


class MutateTest(unittest.TestCase):
    def test_mutation_changes_code(self):
        code, line, desc = mutate.mutate("def f(a):\n    return a < 3\n", 0)
        self.assertIn(">=", code)
        self.assertEqual(desc, "Lt")

    def test_weak_tests_leave_survivors_strong_tests_kill(self):
        d = Path(tempfile.mkdtemp())
        (d / "lib.py").write_text("def big(a):\n    return a > 10\n")
        (d / "test_lib.py").write_text("import unittest\nfrom lib import big\n"
                                       "class T(unittest.TestCase):\n    def test(self):\n        self.assertTrue(big(50))\n")
        self.assertEqual(mutate.main([str(d / "lib.py")]), 1)
        (d / "test_lib.py").write_text("import unittest\nfrom lib import big\nclass T(unittest.TestCase):\n"
                                       "    def test(self):\n        self.assertTrue(big(11))\n        self.assertFalse(big(10))\n")
        self.assertEqual(mutate.main([str(d / "lib.py")]), 0)
        self.assertEqual((d / "lib.py").read_text(), "def big(a):\n    return a > 10\n")


class IsolationTest(unittest.TestCase):
    def test_pick_respects_limit(self):
        self.assertEqual(len(mutate.pick(5, 2)), 2)
        self.assertEqual(mutate.pick(5, 0), [0, 1, 2, 3, 4])
        self.assertEqual(len(mutate.pick(7, 3)), 3)

    def test_relative_writes_and_imports_stay_in_copy(self):
        d = Path(tempfile.mkdtemp())
        (d / "lib.py").write_text("def big(a):\n    return a > 10\n")
        (d / "test_lib.py").write_text(
            "import unittest\nfrom pathlib import Path\nfrom lib import big\n"
            "class T(unittest.TestCase):\n    def test(self):\n        Path('written.txt').write_text('x')\n"
            "        self.assertTrue(big(11))\n        self.assertFalse(big(10))\n")
        cwd = os.getcwd()
        os.chdir(d)
        try:
            self.assertEqual(mutate.main([str(d / "lib.py")]), 0)
        finally:
            os.chdir(cwd)
        self.assertFalse((d / "written.txt").exists())
        self.assertEqual((d / "lib.py").read_text(), "def big(a):\n    return a > 10\n")


if __name__ == "__main__":
    unittest.main()
