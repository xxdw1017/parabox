"""自检：确认“能启动 + 找得到关卡 + 能渲染 + 能走一步”。

打包成 exe 之后在目标电脑上先跑一次：

    递归之箱 ／ RecursiveBox.exe --selftest

退出码 0 = 通过；结果同时写到程序旁边的 `selftest_report.txt`（窗口模式下看不到控制台，
这个文件就是唯一的凭证）。无显示设备的机器也能跑：SDL 走 dummy 驱动。
"""

from __future__ import annotations

import os
from pathlib import Path

from src import paths


def run(levels_dir=None) -> int:
    """跑一次自检，返回进程退出码（0 通过 / 1 失败）。"""
    # 必须在 import pygame 之前设置，dummy 驱动让无头机器也能跑
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    import pygame

    from src import render
    from src.game import Game

    directory = Path(levels_dir) if levels_dir is not None else paths.levels_dir()
    lines = [f"关卡目录：{directory}"]
    code = 0
    try:
        pygame.init()
        game = Game(levels_dir=directory)
        fonts = render.load_fonts()
        surface = pygame.Surface(game.window)
        game.draw(surface, fonts)                       # 选关界面
        lines.append(f"发现关卡：{len(game.entries)} 个")
        if not game.entries:
            raise RuntimeError("关卡目录里没有可用关卡")
        if not game.start_level(0):
            raise RuntimeError("第一关无法载入（数据非法？）")
        game.draw(surface, fonts)                       # 游玩界面
        for _ in range(3):
            game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
        game.draw(surface, fonts)                       # 内层 / 通关界面都不该崩
        lines.append(f"渲染与移动：OK（步数 {game.state['moves']}）")
        lines.append("SELFTEST OK")
    except Exception as exc:                            # 自检失败必须说清是哪一步
        code = 1
        lines.append(f"SELFTEST FAILED：{type(exc).__name__}: {exc}")
    finally:
        try:
            pygame.quit()
        except Exception:
            pass

    report = "\n".join(lines)
    print(report, flush=True)
    try:
        (paths.app_dir() / "selftest_report.txt").write_text(report + "\n", encoding="utf-8")
    except OSError:
        pass                                            # 写在只读目录里也不该让自检失败
    return code
