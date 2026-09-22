"""把仓库打成课程提交压缩包（按 `提交材料/压缩包清单.md` 的结构）。

用法：
    .venv/bin/python 提交材料/打包提交材料.py                     # 输出 ~/Desktop/递归之箱.zip
    .venv/bin/python 提交材料/打包提交材料.py --name B01递归之箱    # 组号确定后带上组号

包含：源工程（含 .git 历史）、提交材料（个人文档 PDF、历史版本导出、脚本）、演示视频、
      汇报 PPT；若 `提交材料/应用程序/` 下有 exe 也会一起打包。
排除：.venv、__pycache__、构建产物、原始 .mov 录制、系统临时文件。
"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "提交材料"          # 也可用 --out 指定（沙箱限制：本进程只能写工作区内）
EXCLUDE_DIRS = {".venv", "__pycache__", "build", "dist", ".pyinstaller-cache", ".git"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".mov", ".zip", ".DS_Store"}


def wanted(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDE_DIRS for part in rel.parts[:-1]):
        return False
    if path.suffix in EXCLUDE_SUFFIX or path.name in {".DS_Store"}:
        return False
    return path.is_file()


def main() -> int:
    ap = argparse.ArgumentParser(description="打包课程提交材料")
    ap.add_argument("--name", default="递归之箱", help="压缩包名（不含 .zip）")
    ap.add_argument("--out", type=Path, default=OUT_DIR, help="输出目录（默认 提交材料/）")
    ap.add_argument("--keep-git", action="store_true", default=True,
                    help="包含 .git（默认包含，用于证明规则/测试的版本演化）")
    args = ap.parse_args()

    excludes = set(EXCLUDE_DIRS)
    if args.keep_git:
        excludes.discard(".git")

    out = args.out / f"{args.name}.zip"
    files = [p for p in ROOT.rglob("*") if p.is_file()
             and not any(part in excludes for part in p.relative_to(ROOT).parts[:-1])
             and p.suffix not in EXCLUDE_SUFFIX and p.name != ".DS_Store"]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in files:
            z.write(p, Path(args.name) / p.relative_to(ROOT))

    size = out.stat().st_size / 1024 / 1024
    has_exe = (ROOT / "提交材料/应用程序/RecursiveBox.exe").exists()
    has_video = (ROOT / "提交材料/演示视频/递归之箱_演示_董长坤.mp4").exists()
    has_pdf = (ROOT / "提交材料/递归之箱_个人文档_董长坤.pdf").exists()
    print(f"已生成：{out}（{len(files)} 个文件，{size:.1f} MB）")
    print("清单自检：")
    for name, ok, hint in (("应用程序 RecursiveBox.exe", has_exe, "把 Windows 上打好的 exe 拷进 提交材料/应用程序/"),
                           ("演示视频 mp4", has_video, "缺视频"),
                           ("个人文档 PDF", has_pdf, "跑 生成个人文档PDF.py")):
        print(f"  {'✅' if ok else '❌'} {name}" + ("" if ok else f"　← {hint}"))
    if not args.keep_git:
        print("  （未包含 .git：版本演化仅靠 提交材料/历史版本/ 体现）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
