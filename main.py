"""入口：启动选关界面。

    .venv/bin/python main.py          
    source .venv/bin/activate         
    python main.py                    

交付检查见 RULE.md §五。
"""

import sys
from pathlib import Path

LEVELS_DIR = Path(__file__).resolve().parent / "levels"

try:
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
    )
    raise SystemExit(1)


def main() -> int:
    """启动游戏；进入选关界面后由 pygame 主循环接管。"""
    Game(levels_dir=LEVELS_DIR).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
