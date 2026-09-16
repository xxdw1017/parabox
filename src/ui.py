"""选关界面：扫描关卡文件、画卡片、把按键翻译成语义命令。

只读关卡文件（非法关卡不阻断选关，见 level-loading 技能），不修改游戏状态。
"""

from __future__ import annotations

from pathlib import Path

import pygame

from src import world as W
from src.render import PALETTE, rgb

CARD_W = 520
CARD_H = 96
CARD_GAP = 18
TOP = 150


def list_levels(directory) -> list[dict]:
    """扫描目录下的 `*.json`，返回 [{path, name, title, ok, error}]（按文件名排序）。"""
    entries = []
    for path in sorted(Path(directory).glob("*.json")):
        try:
            level = W.load_level(path)
            entries.append({"path": path, "name": level["name"],
                            "title": level["title"] or path.stem, "ok": True, "error": ""})
        except Exception as exc:                       # 非法关卡：标记为不可用，继续列其余关卡
            entries.append({"path": path, "name": path.stem, "title": path.stem,
                            "ok": False, "error": str(exc)})
    return entries


def card_rects(screen_size, count: int, scroll: int = 0) -> list:
    """卡片矩形（垂直排列，居中）。"""
    width, height = screen_size
    x = (width - CARD_W) // 2
    return [pygame.Rect(x, TOP + i * (CARD_H + CARD_GAP) - scroll, CARD_W, CARD_H)
            for i in range(count)]


def menu_command(event, index: int, count: int):
    """把按键翻译成 ("select", i) / ("start", i) / ("quit", None)；无关按键返回 None。"""
    if event.type != pygame.KEYDOWN:
        return None
    if count <= 0:
        return ("quit", None) if event.key == pygame.K_ESCAPE else None
    if event.key in (pygame.K_UP, pygame.K_w):
        return ("select", (index - 1) % count)
    if event.key in (pygame.K_DOWN, pygame.K_s):
        return ("select", (index + 1) % count)
    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
        return ("start", index)
    if event.key == pygame.K_ESCAPE:
        return ("quit", None)
    return None


def draw_menu(surface, entries: list, index: int, fonts: dict) -> None:
    """画选关界面：标题 + 关卡卡片（当前选中卡片高亮描边）。"""
    surface.fill(rgb(PALETTE["bg"]))
    width, _ = surface.get_size()
    title = fonts[28].render("递归之箱 · 选关", True, rgb(PALETTE["text"]))
    surface.blit(title, (48, 40))
    sub = fonts[16].render("Patrick's Parabox 关卡复刻 · Python + Pygame", True, rgb(PALETTE["muted"]))
    surface.blit(sub, (48, 84))
    if not entries:
        empty = fonts[18].render("levels/ 下没有可用关卡", True, rgb(PALETTE["danger"]))
        surface.blit(empty, ((width - empty.get_width()) // 2, TOP))
        return
    for i, (entry, rect) in enumerate(zip(entries, card_rects(surface.get_size(), len(entries)))):
        selected = i == index
        pygame.draw.rect(surface, rgb(PALETTE["panel"]), rect, border_radius=12)
        pygame.draw.rect(surface, rgb(PALETTE["active"] if selected else PALETTE["muted"]),
                         rect, 3 if selected else 1, border_radius=12)
        name = fonts[22].render(entry["title"], True,
                                rgb(PALETTE["text"] if entry["ok"] else PALETTE["danger"]))
        surface.blit(name, (rect.x + 20, rect.y + 16))
        detail = entry["path"].name if entry["ok"] else f"无法加载：{entry['error'][:40]}"
        info = fonts[16].render(detail, True, rgb(PALETTE["muted"]))
        surface.blit(info, (rect.x + 20, rect.y + 54))
    tip = fonts[16].render("↑ / ↓ 选择 · Enter 开始 · ESC 退出", True, rgb(PALETTE["muted"]))
    surface.blit(tip, ((width - tip.get_width()) // 2, surface.get_height() - 48))
