"""`src/paths.py`：源码运行与 PyInstaller 打包两种情形下的目录解析。"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src import paths


class TestDevLayout(unittest.TestCase):
    """源码运行：一切以项目根目录为准。"""

    def test_app_dir_is_project_root(self):
        self.assertEqual(paths.app_dir(), paths.project_root())
        self.assertTrue((paths.app_dir() / "main.py").is_file())

    def test_bundle_dir_is_project_root(self):
        self.assertEqual(paths.bundle_dir(), paths.project_root())

    def test_not_frozen(self):
        self.assertFalse(paths.is_frozen())

    def test_levels_dir_holds_shipped_levels(self):
        directory = paths.levels_dir()
        self.assertTrue((directory / "level_01.json").is_file())
        self.assertTrue((directory / "level_02.json").is_file())

    def test_asset_path(self):
        self.assertEqual(paths.asset_path("favicon.ico").name, "favicon.ico")
        self.assertEqual(paths.asset_path("favicon.ico").parent.name, "assets")


class TestFrozenLayout(unittest.TestCase):
    """模拟 PyInstaller：sys.frozen=True、_MEIPASS=解包目录、sys.executable=exe 路径。"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve()      # macOS 上 /var 是 /private/var 的软链，先归一化
        self.meipass = root / "_MEI12345"
        (self.meipass / "levels").mkdir(parents=True)
        (self.meipass / "levels" / "level_01.json").write_text("{}", encoding="utf-8")
        (self.meipass / "assets").mkdir()
        self.exe_dir = root / "dist"
        self.exe_dir.mkdir()
        self.exe = self.exe_dir / ("RecursiveBox.exe" if sys.platform == "win32" else "RecursiveBox")
        self.exe.write_text("", encoding="utf-8")

        for patcher in (
            mock.patch.object(sys, "frozen", True, create=True),
            mock.patch.object(sys, "_MEIPASS", str(self.meipass), create=True),
            mock.patch.object(sys, "executable", str(self.exe)),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_frozen_dirs(self):
        self.assertTrue(paths.is_frozen())
        self.assertEqual(paths.app_dir(), self.exe_dir)
        self.assertEqual(paths.bundle_dir(), self.meipass)

    def test_falls_back_to_bundled_levels(self):
        self.assertEqual(paths.levels_dir(), self.meipass / "levels")

    def test_external_levels_next_to_exe_win(self):
        """exe 旁边放 levels/ 就能覆盖内置关卡（临时加关卡不用重新打包）。"""
        external = self.exe_dir / "levels"
        external.mkdir()
        self.assertEqual(paths.levels_dir(), external)

    def test_asset_path_inside_bundle(self):
        self.assertEqual(paths.asset_path("favicon.ico"), self.meipass / "assets" / "favicon.ico")


if __name__ == "__main__":
    unittest.main()
