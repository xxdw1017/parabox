"""主循环与状态机：选关 → 游玩 → 通关。

职责边界（AGENTS.md 分层依赖规则）：
- 本模块只做“编排”：把按键交给 logic/nested，把状态交给 render/ui；
- 游戏规则一律走 logic.py（禁止在渲染层或本模块里重写规则）。
"""

from __future__ import annotations

import copy
from pathlib import Path

import pygame

from src import logic, render, ui
from src import world as W

WINDOW = (1280, 720)
FPS = 60
KEY_MAP = {
    pygame.K_UP: "up", pygame.K_w: "up",
    pygame.K_DOWN: "down", pygame.K_s: "down",
    pygame.K_LEFT: "left", pygame.K_a: "left",
    pygame.K_RIGHT: "right", pygame.K_d: "right",
}


class Game:
    """一个关卡集合 + 三种场景（menu / play / win）。"""

    def __init__(self, levels_dir, window=WINDOW, fps=FPS):
        self.levels_dir = Path(levels_dir)
        self.window = window
        self.fps = fps
        self.running = True
        self.scene = "menu"
        self.index = 0
        self.level = None
        self.initial = None
        self.state = None
        self.history = []
        self.won = False
        self.reload_levels()

    # ---------- 选关 ----------
    def reload_levels(self) -> None:
        """重新扫描关卡目录（非法关卡会被标记为不可用）。"""
        self.entries = ui.list_levels(self.levels_dir)
        self.index = min(self.index, max(0, len(self.entries) - 1))

    def start_level(self, index: int) -> bool:
        """载入并开始某一关；关卡不可用时返回 False。"""
        if not 0 <= index < len(self.entries):
            return False
        entry = self.entries[index]
        if not entry["ok"]:
            return False
        self.level = W.load_level(entry["path"])
        self.initial = copy.deepcopy(self.level["state"])
        self.state = self.level["state"]
        self.history = []
        self.won = False
        self.scene = "play"
        return True

    # ---------- 游玩 ----------
    def step(self, direction: str) -> bool:
        """走一步；被规则拒绝的操作不进撤销栈。"""
        if self.scene != "play" or self.state is None:
            return False
        new_state = logic.move(self.state, direction)
        if new_state is self.state:
            return False
        self.history.append(self.state)
        self.state = new_state
        if logic.check_win(self.state):
            self.won = True
            self.scene = "win"
        return True

    def undo(self) -> bool:
        """撤销一步。"""
        if not self.history:
            return False
        self.state = self.history.pop()
        self.won = False
        if self.scene == "win":
            self.scene = "play"
        return True

    def reset(self) -> bool:
        """重置本关到初始状态。"""
        if self.initial is None:
            return False
        self.state = copy.deepcopy(self.initial)
        self.history = []
        self.won = False
        self.scene = "play"
        return True

    def back_to_menu(self) -> None:
        self.scene = "menu"
        self.won = False

    # ---------- 事件 ----------
    def handle_event(self, event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if self.scene == "menu":
            command = ui.menu_command(event, self.index, len(self.entries))
            if command is None:
                return
            action, value = command
            if action == "select":
                self.index = value
            elif action == "start":
                self.start_level(value)
            elif action == "quit":
                self.running = False
        elif self.scene == "play":
            if event.key in KEY_MAP:
                self.step(KEY_MAP[event.key])
            elif event.key == pygame.K_u:
                self.undo()
            elif event.key == pygame.K_r:
                self.reset()
            elif event.key == pygame.K_ESCAPE:
                self.back_to_menu()
        elif self.scene == "win":
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_ESCAPE):
                self.back_to_menu()

    # ---------- 绘制 ----------
    def draw(self, surface, fonts) -> None:
        if self.scene == "menu":
            ui.draw_menu(surface, self.entries, self.index, fonts)
        else:
            render.draw_scene(surface, self.state, fonts,
                              self.level["title"] if self.level else "", won=self.won)

    # ---------- 主循环 ----------
    def run(self) -> None:
        """启动窗口并进入主循环（RULE.md §五：`python main.py` 能启动并进入选关界面）。"""
        pygame.init()
        screen = pygame.display.set_mode(self.window)
        pygame.display.set_caption("递归之箱 · Patrick's Parabox 关卡复刻")
        clock = pygame.time.Clock()
        fonts = render.load_fonts()
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                else:
                    self.handle_event(event)
            self.draw(screen, fonts)
            pygame.display.flip()
            clock.tick(self.fps)
        pygame.quit()
