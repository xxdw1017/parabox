"""运行位置解析：源码运行与 PyInstaller 打包（onefile / onedir）都能找到关卡。

打包后有两类目录，不能混为一谈：
- `bundle_dir()`：**只读的打包资源**（PyInstaller 解包目录 `sys._MEIPASS`），内含 `levels/`；
- `app_dir()`：**可执行程序所在目录**（Windows 上是 exe 旁边），用户可以往里放东西。

关卡目录优先取 exe 旁边的 `levels/`（临时加关卡、覆盖内置关卡都方便），
没有才回退到打包内置的那份。源码运行时两者都指向项目根目录。
"""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    """是否运行在 PyInstaller 打出来的包里。"""
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    """源码运行时的项目根目录（本文件位于 `<root>/src/paths.py`）。"""
    return Path(__file__).resolve().parent.parent


def app_dir() -> Path:
    """入口程序所在目录：打包后是 exe 旁边，源码运行时是项目根目录。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return project_root()


def bundle_dir() -> Path:
    """打包资源目录：onefile 的解包目录 / onedir 的 `_internal`；源码运行时即项目根目录。"""
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) if base else project_root()


def levels_dir() -> Path:
    """关卡目录：优先 exe 旁边的 `levels/`，否则用打包内置的 `levels/`。"""
    external = app_dir() / "levels"
    if external.is_dir():
        return external
    return bundle_dir() / "levels"


def asset_path(name: str) -> Path:
    """`assets/` 下的素材路径（窗口图标等，随包一起打进 `bundle_dir()`）。"""
    return bundle_dir() / "assets" / name
