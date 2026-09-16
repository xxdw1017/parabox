"""一条命令打包 + 自检：PyInstaller → 跑一次 `--selftest` → 报告产物路径与大小。

    .venv/bin/python tools/build_app.py             # 单文件（Windows 出 .exe）
    .venv/bin/python tools/build_app.py --onedir    # 目录模式（启动更快）
    .venv/bin/python tools/build_app.py --no-selftest

Windows 上可以直接双击 `build_windows.bat`：它会建虚拟环境、装依赖、再调用本脚本。
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "parabox.spec"
NAME = "RecursiveBox"
EXE_SUFFIX = ".exe" if os.name == "nt" else ""


def artifact(one_dir: bool) -> Path:
    """打包产物的可执行文件路径。"""
    if one_dir:
        return ROOT / "dist" / NAME / f"{NAME}{EXE_SUFFIX}"
    return ROOT / "dist" / f"{NAME}{EXE_SUFFIX}"


def main() -> int:
    parser = argparse.ArgumentParser(description="打包《递归之箱》")
    parser.add_argument("--onedir", action="store_true", help="打目录包（启动更快，文件多）")
    parser.add_argument("--no-selftest", action="store_true", help="跳过打包后的自检")
    args = parser.parse_args()

    try:
        import PyInstaller  # noqa: F401
    except ModuleNotFoundError:
        print("缺少 PyInstaller，先安装：\n    python -m pip install pyinstaller", file=sys.stderr)
        return 2

    env = dict(os.environ, PARABOX_ONEDIR="1" if args.onedir else "0")
    # PyInstaller 默认把缓存写到用户目录（Windows 的 %APPDATA%）：放到项目内更好清、
    # 也让"打包产物只依赖项目目录"这件事成立。
    env.setdefault("PYINSTALLER_CONFIG_DIR", str(ROOT / ".pyinstaller-cache"))
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(SPEC)]
    print("$ " + " ".join(cmd), flush=True)
    if subprocess.run(cmd, cwd=ROOT, env=env).returncode != 0:
        print("打包失败：PyInstaller 返回非 0", file=sys.stderr)
        return 1

    target = artifact(args.onedir)
    if not target.is_file():
        print(f"打包失败：没找到产物 {target}", file=sys.stderr)
        return 1

    print(f"\n产物：{target}")
    print(f"大小：{target.stat().st_size / 1024 / 1024:.1f} MB"
          + (f"（目录共 {sum(f.stat().st_size for f in target.parent.rglob('*') if f.is_file()) / 1024 / 1024:.1f} MB）"
             if args.onedir else ""))

    if args.no_selftest:
        return 0

    # 在无显示环境下自检产物：确认“能启动 + 关卡带上了 + 能渲染能走”
    run_env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    result = subprocess.run([str(target), "--selftest"], cwd=target.parent,
                            env=run_env, capture_output=True, text=True, timeout=180)
    print("\n--- 产物自检 ---")
    # 窗口模式的 exe 没有控制台，标准输出可能是空的 → 退回读它写的报告文件
    output = result.stdout.strip() or result.stderr.strip()
    report = target.parent / "selftest_report.txt"
    if not output and report.is_file():
        output = report.read_text(encoding="utf-8").strip()
    print(output or "(没有输出，也不见 selftest_report.txt)")
    if result.returncode != 0:
        print(f"\n自检未通过（退出码 {result.returncode}）：先别拿去投屏", file=sys.stderr)
        return 1
    print("\n自检通过：这个包在别的电脑上双击就能跑。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
