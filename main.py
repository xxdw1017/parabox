"""入口：启动选关界面（或跑一次自检）。

    .venv/bin/python main.py             启动游戏
    .venv/bin/python main.py --selftest  不开窗口自检（打包后确认关卡带上了）
    source .venv/bin/activate && python main.py

打包与投屏见 PACKAGING.md；交付检查见 RULE.md §五。
"""

import sys

from src import paths

LEVELS_DIR = paths.levels_dir()

try:
    from src import selftest
    from src.game import Game
except ModuleNotFoundError as exc:                      # 没装 pygame：给一句人话，而不是一堆 traceback
    if exc.name != "pygame" or __name__ != "__main__":
        raise
    sys.stderr.write(
        "启动失败：当前 Python 里没有 pygame。\n"
        f"  当前解释器：{sys.executable}\n"
        "  请用项目内虚拟环境启动：\n"
        "      .venv/bin/python main.py\n"
        "  或先激活虚拟环境再用默认命令：\n"
        "      source .venv/bin/activate && python main.py\n"
        "  IDE（VS Code）：把解释器切到 ./.venv/bin/python。\n"
        "  只想确认关卡数据没问题：.venv/bin/python main.py --selftest\n"
    )
    raise SystemExit(1)


def main(argv=None) -> int:
    """启动游戏；带 `--selftest` 时改为跑一次不开窗口的自检。"""
    args = sys.argv[1:] if argv is None else list(argv)
    if "--selftest" in args:
        return selftest.run(LEVELS_DIR)
    Game(levels_dir=LEVELS_DIR).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
