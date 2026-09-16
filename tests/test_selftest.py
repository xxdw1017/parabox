"""打包自检：真实关卡目录必须通过；空目录必须失败（确认 exe 真把 levels/ 带上了）。"""

import tempfile
import unittest
from pathlib import Path

from src import paths, selftest

try:
    import pygame  # noqa: F401
    HAVE_PYGAME = True
except ModuleNotFoundError:
    HAVE_PYGAME = False

LEVELS = paths.project_root() / "levels"


@unittest.skipUnless(HAVE_PYGAME, "未安装 pygame")
class TestSelfTest(unittest.TestCase):
    def setUp(self):
        self.report = paths.app_dir() / "selftest_report.txt"
        if self.report.exists():
            self.report.unlink()
        self.addCleanup(lambda: self.report.exists() and self.report.unlink())

    def test_passes_on_real_levels(self):
        self.assertEqual(selftest.run(LEVELS), 0)

    def test_fails_when_levels_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertNotEqual(selftest.run(tmp), 0)

    def test_writes_report_next_to_program(self):
        selftest.run(LEVELS)
        self.assertTrue(self.report.is_file())
        self.assertIn("SELFTEST OK", self.report.read_text(encoding="utf-8"))

    def test_report_records_level_count(self):
        selftest.run(LEVELS)
        text = self.report.read_text(encoding="utf-8")
        self.assertIn("发现关卡：2 个", text)


if __name__ == "__main__":
    unittest.main()
