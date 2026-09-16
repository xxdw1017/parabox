"""Pygame 绘制：多层世界渲染、箱内缩略图、活动层高亮。

**渲染层只读游戏状态，禁止修改**（RULE.md §一.8 / AGENTS.md 分层依赖规则）。
配色与绘制规则见 world-rendering 技能（`.dsh/skills/world-rendering/SKILL.md`），
本模块的 PALETTE 与那份文档必须保持一致（RULE.md §五）。
"""

from __future__ import annotations

import pygame

from src import world as W
from src.entity import DELTA, door_sides, side_center

TILE = 64                      # 格子边长上限
MIN_THUMB_TILE = 4             # 缩略图格子边长下限：低于此值只画色块
THUMB_MARGIN = 0.12            # 缩略图相对格子的内缩比例
HUD_H = 64                     # 底部 HUD 高度

PALETTE = {
    "bg": "#111420",           # 两份 PPT 的页面底色
    "floor": "#1B2740",        # 关卡示例图深蓝 #16386B 调暗
    "wall": "#3E7BB5",         # 关卡示例图亮块 #245B93 提亮（与地面 >= 3:1）
    "goal": "#6CC77A",         # PPT 强调色
    "player": "#F5A623",       # PPT 强调色
    "box": "#EBEEF5",          # PPT 正文色
    "brand": "#BF0072",        # logo / favicon 主色
    "door": "#7FB2FF",         # PPT 链接色
    "text": "#EBEEF5",
    "muted": "#98A2B8",
    "active": "#F5A623",       # 活动层高亮
    "panel": "#1C2132",        # PPT 卡片色
    "danger": "#FF6B6B",       # PPT 强调色（非法关卡提示）
}

_CACHE: dict[str, tuple[int, int, int]] = {}


def rgb(value: str):
    """#RRGGBB → (r, g, b)，带缓存。"""
    if value not in _CACHE:
        value = value.lstrip("#")
        _CACHE[value] = tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    return _CACHE[value]


def relative_luminance(color) -> float:
    """WCAG 相对亮度。"""
    channels = []
    for raw in color:
        c = raw / 255
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(color_a, color_b) -> float:
    """WCAG 对比度（1.0 ~ 21.0）。"""
    la, lb = relative_luminance(color_a), relative_luminance(color_b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def palette_contrasts() -> dict:
    """各可读性指标的实测值，供测试断言与调色参考。"""
    floor = rgb(PALETTE["floor"])
    return {
        "wall/floor": contrast_ratio(rgb(PALETTE["wall"]), floor),
        "player/floor": contrast_ratio(rgb(PALETTE["player"]), floor),
        "goal/floor": contrast_ratio(rgb(PALETTE["goal"]), floor),
        "box/floor": contrast_ratio(rgb(PALETTE["box"]), floor),
        "door/floor": contrast_ratio(rgb(PALETTE["door"]), floor),
        "text/bg": contrast_ratio(rgb(PALETTE["text"]), rgb(PALETTE["bg"])),
        "muted/bg": contrast_ratio(rgb(PALETTE["muted"]), rgb(PALETTE["bg"])),
        "brand/box": contrast_ratio(rgb(PALETTE["brand"]), rgb(PALETTE["box"])),
    }


def load_fonts(sizes=(16, 18, 22, 28)) -> dict:
    """加载中文字体（找不到就退回 pygame 默认字体）。"""
    pygame.font.init()
    path = None
    for name in ("PingFang SC", "Hiragino Sans GB", "Heiti SC", "Microsoft YaHei", "SimHei"):
        found = pygame.font.match_font(name)
        if found:
            path = found
            break
    if path is None:
        import os
        for candidate in ("/System/Library/Fonts/PingFang.ttc",
                          "/System/Library/Fonts/Supplemental/Songti.ttc"):
            if os.path.exists(candidate):
                path = candidate
                break
    return {size: pygame.font.Font(path, size) for size in sizes}


def world_tile_size(world: dict, area_w: int, area_h: int) -> int:
    """按可用区域算出格子边长：小世界不放大，大世界不溢出。"""
    return max(MIN_THUMB_TILE, min(TILE, area_w // world["w"], area_h // world["h"]))


def thumbnail_rect(px: int, py: int, tile: int, inner: dict):
    """箱内缩略图在格子 (px, py, tile) 里的居中矩形。

    返回 `(x, y, w, h, inner_tile)`；等比缩放、不超出格子，每深一层重复同样规则。
    """
    if inner is None or inner["w"] <= 0 or inner["h"] <= 0:
        return (px, py, 0, 0, 0.0)
    margin = max(2, int(tile * THUMB_MARGIN))
    avail = tile - 2 * margin
    if avail <= 0:
        return (px, py, 0, 0, 0.0)
    inner_tile = avail / max(inner["w"], inner["h"])
    w = max(1, int(inner_tile * inner["w"]))
    h = max(1, int(inner_tile * inner["h"]))
    return (px + (tile - w) // 2, py + (tile - h) // 2, w, h, inner_tile)


def draw_box(surface, box: dict, px: int, py: int, tile: int) -> None:
    """画一个箱子：填充 + 描边 + 每条有口的边画缺口 + 内层缩略图（递归）。"""
    rect = pygame.Rect(px + 2, py + 2, max(2, tile - 4), max(2, tile - 4))
    radius = max(2, tile // 8)
    pygame.draw.rect(surface, rgb(PALETTE["box"]), rect, border_radius=radius)
    inner = box["inner_world"]
    outline = PALETTE["brand"] if inner is not None else PALETTE["muted"]
    pygame.draw.rect(surface, rgb(outline), rect, max(2, tile // 16), border_radius=radius)

    if inner is not None:
        seg = max(3, tile // 5)
        width = max(3, tile // 10)
        for side in door_sides(inner):                       # 口在哪条边就画在哪条边
            dx, dy = DELTA[side]
            if dx:
                x = rect.right if dx > 0 else rect.left
                pygame.draw.line(surface, rgb(PALETTE["door"]),
                                 (x, rect.centery - seg // 2), (x, rect.centery + seg // 2), width)
            else:
                y = rect.bottom if dy > 0 else rect.top
                pygame.draw.line(surface, rgb(PALETTE["door"]),
                                 (rect.centerx - seg // 2, y), (rect.centerx + seg // 2, y), width)
        x0, y0, w, h, inner_tile = thumbnail_rect(px, py, tile, inner)
        if inner_tile >= MIN_THUMB_TILE:
            draw_world(surface, inner, (x0, y0), int(inner_tile), player=None, active=False)
        elif w and h:
            pygame.draw.rect(surface, rgb(PALETTE["floor"]), pygame.Rect(x0, y0, w, h))


def draw_world(surface, world: dict, origin, tile: int, player=None,
               active: bool = False, mark_doors: bool = False) -> None:
    """画一个世界：地形 → 口 → 箱子（含缩略图）→ 玩家 → 活动层高亮。"""
    ox, oy = origin
    line = max(1, tile // 32)
    for y in range(world["h"]):
        for x in range(world["w"]):
            cell = pygame.Rect(ox + x * tile, oy + y * tile, tile, tile)
            wall = world["tiles"][y][x] == "#"
            pygame.draw.rect(surface, rgb(PALETTE["wall"] if wall else PALETTE["floor"]), cell)
            if tile >= 16:
                pygame.draw.rect(surface, rgb(PALETTE["bg"]), cell, line)
            if world["tiles"][y][x] == "g":
                pygame.draw.circle(surface, rgb(PALETTE["goal"]), cell.center,
                                   max(3, tile // 5), max(2, tile // 16))

    if mark_doors:                                            # 站在内层时标出可以走出去的口
        for side in door_sides(world):
            cell = side_center(world, side)
            mark = pygame.Rect(ox + cell[0] * tile, oy + cell[1] * tile, tile, tile)
            pygame.draw.rect(surface, rgb(PALETTE["door"]), mark, max(3, tile // 10))

    for uid in sorted(world["boxes"]):
        box = world["boxes"][uid]
        draw_box(surface, box, ox + box["x"] * tile, oy + box["y"] * tile, tile)

    if player is not None:
        center = (ox + player[0] * tile + tile // 2, oy + player[1] * tile + tile // 2)
        pygame.draw.circle(surface, rgb(PALETTE["player"]), center, max(3, int(tile * 0.32)))

    if active:
        border = pygame.Rect(ox, oy, world["w"] * tile, world["h"] * tile)
        pygame.draw.rect(surface, rgb(PALETTE["active"]), border, max(2, tile // 16))


def draw_hud(surface, state: dict, fonts: dict, title: str = "") -> None:
    """关卡名、步数、当前层级、操作提示。"""
    width, height = surface.get_size()
    path = state["player"]["path"]
    name = fonts[22].render(title or "递归之箱", True, rgb(PALETTE["text"]))
    surface.blit(name, (24, height - HUD_H + 18))
    steps = fonts[18].render(f"步数 {state['moves']}", True, rgb(PALETTE["muted"]))
    surface.blit(steps, (width - steps.get_width() - 24, 16))
    hint = fonts[16].render("方向键 / WASD 移动 · U 撤销 · R 重置 · ESC 选关",
                            True, rgb(PALETTE["muted"]))
    surface.blit(hint, (width - hint.get_width() - 24, height - HUD_H + 24))
    if path:
        crumb = " › ".join(["外层"] + path)
        text = fonts[16].render(f"当前层：{crumb}", True, rgb(PALETTE["active"]))
        surface.blit(text, (24, 16))


def draw_win(surface, state: dict, fonts: dict) -> None:
    """通关遮罩 + 步数。"""
    width, height = surface.get_size()
    overlay = pygame.Surface((width, height), pygame.SRCALPHA)
    overlay.fill((17, 20, 32, 210))
    surface.blit(overlay, (0, 0))
    lines = [(fonts[28], "通关！", PALETTE["goal"]),
             (fonts[22], f"总步数 {state['moves']}", PALETTE["text"]),
             (fonts[18], "Enter 返回选关", PALETTE["muted"])]
    y = height // 2 - 60
    for font, text, color in lines:
        rendered = font.render(text, True, rgb(color))
        surface.blit(rendered, ((width - rendered.get_width()) // 2, y))
        y += rendered.get_height() + 12


def draw_scene(surface, state: dict, fonts: dict, title: str = "", won: bool = False) -> None:
    """画一帧：当前活动世界 + HUD（+ 通关遮罩）。只读 state。"""
    surface.fill(rgb(PALETTE["bg"]))
    width, height = surface.get_size()
    world = W.find_world(state["root"], state["player"]["path"])
    tile = world_tile_size(world, width - TILE, height - HUD_H - TILE)
    ox = (width - world["w"] * tile) // 2
    oy = (height - HUD_H - world["h"] * tile) // 2
    player = (state["player"]["x"], state["player"]["y"])
    draw_world(surface, world, (ox, oy), tile, player=player, active=True,
               mark_doors=bool(state["player"]["path"]))
    draw_hud(surface, state, fonts, title)
    if won:
        draw_win(surface, state, fonts)
