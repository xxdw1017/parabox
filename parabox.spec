# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：Windows 单文件 exe / macOS 可执行文件（+ .app）。

构建（不要直接敲 pyinstaller，用脚本，它还会自检产物）：
    python tools/build_app.py             # 单文件
    python tools/build_app.py --onedir    # 目录模式（启动更快，但文件多）

产物：dist/RecursiveBox.exe（Windows）/ dist/RecursiveBox（macOS）
要点：
- `levels/` 一起打进包里（`datas`），所以 exe 不依赖外部文件；
- exe 旁边另放一个 `levels/` 会**覆盖**内置关卡，方便临时加关卡（见 src/paths.py）；
- `console=False`：不弹黑框；自检结果写 `selftest_report.txt`。
"""

import os
import sys

ROOT = SPECPATH                                        # noqa: F821  PyInstaller 注入
NAME = "RecursiveBox"
ICON = os.path.join(ROOT, "assets", "favicon.ico")
ONEDIR = os.environ.get("PARABOX_ONEDIR") == "1"

a = Analysis(                                          # noqa: F821
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[(os.path.join(ROOT, "levels"), "levels")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "tests"],
    noarchive=False,
)
pyz = PYZ(a.pure)                                      # noqa: F821

common = dict(
    name=NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                                     # 双击运行不弹控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON if sys.platform == "win32" and os.path.exists(ICON) else None,
)

if ONEDIR:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **common)   # noqa: F821
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=NAME)  # noqa: F821
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], **common)     # noqa: F821

if sys.platform == "darwin" and ONEDIR:                 # macOS：目录模式才出可双击的 .app
    # BUNDLE 必须包 COLLECT 的结果（包 EXE 会得到一个 Frameworks 为空的 .app，跑不起来）；
    # 单文件模式不生成 .app，直接从终端运行 dist/RecursiveBox。
    app = BUNDLE(                                      # noqa: F821
        coll,
        name=f"{NAME}.app",
        bundle_identifier="com.xxdw1017.parabox",
        info_plist={
            "CFBundleName": "递归之箱",
            "CFBundleDisplayName": "递归之箱",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
        },
    )
