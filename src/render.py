"""Pygame 绘制：多层世界渲染、箱内缩略图、活动层高亮。

**渲染层只读游戏状态，禁止修改**（RULE.md §一.8 / AGENTS.md 分层依赖规则）。
配色与绘制规则见 world-rendering 技能（`.dsh/skills/world-rendering/SKILL.md`），
本模块的 PALETTE 与那份文档必须保持一致（RULE.md §五）。

美术风格：纯色平涂（不用贴图、不用渐变）。色相约定：
墙=淡灰、外层空地=深灰、内部空间=深黄、玩家=洋红、含内部空间的方块=黄、普通方块=蓝；
方块或玩家站在判定点上时，边框/外圈发亮。

判定点形状与大小（2026-09-17 定稿）：
- `g`（箱子判定点）= **方框**，大小与方块一致（方块压上去时正好重合）；
- `G`（玩家判定点）= **圆环**，大小与玩家一致（玩家站上去时正好同圈）；
- 不再额外画"入口小横线"：口本身在内层地图上是墙上的缺口，看得见。
"""

from __future__ import annotations

import pygame

from src import world as W
from src.entity import GOAL, PLAYER_GOAL

TILE = 64                      # 格子边长上限
MIN_THUMB_TILE = 4             # 缩略图格子边长下限：低于此值只画色块
THUMB_MARGIN = 0.12            # 缩略图相对格子的内缩比例
HUD_H = 64                     # 底部 HUD 高度
PLAYER_RATIO = 0.32            # 玩家圆半径 / 格子边长

PALETTE = {
    "bg": "#14161A",           # 世界之外的底色
    "floor": "#2A2E33",        # 外层空地：深灰
    "floor_inner": "#453A0D",  # 内部空间：深黄
    "wall": "#B9C0C7",         # 墙：淡灰
    "player": "#FF8AD0",       # 玩家：洋红（偏亮以保证对比度）
    "eye": "#14161A",          # 玩家的两只小圆眼：近黑
    "box_open": "#F2C744",     # 含内部空间的方块：黄
    "box_plain": "#6FA8FF",    # 普通方块：蓝
    "goal": "#6CC77A",         # 判定点标记（g 画方框、G 画圆环）
    "glow": "#FFFFFF",         # 判定点达成时的亮边
    "edge": "#14161A",         # 方块默认描边（纯色块靠它压住边界）
    "text": "#EBEEF5",         # HUD 正文
    "muted": "#98A2B8",        # HUD 次要文字
    "active": "#F5A623",       # 活动层高亮
    "panel": "#1C2132",        # 选关卡片
    "danger": "#FF6B6B",       # 非法关卡提示
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
    """各可读性指标的实测值，供测试断言与调色参考（两种地面都要查）。"""
    floors = {"floor": rgb(PALETTE["floor"]), "inner": rgb(PALETTE["floor_inner"])}
    out = {}
    for name in ("wall", "player", "box_open", "box_plain", "goal", "glow"):
        for label, floor in floors.items():
            out[f"{name}/{label}"] = contrast_ratio(rgb(PALETTE[name]), floor)
    out["text/bg"] = contrast_ratio(rgb(PALETTE["text"]), rgb(PALETTE["bg"]))
    out["muted/bg"] = contrast_ratio(rgb(PALETTE["muted"]), rgb(PALETTE["bg"]))
    return out


def load_fonts(sizes=(16, 18, 22, 28)) -> dict:
    """加载中文字体（找不到就退回 pygame 默认字体）。"""
    pygame.font.init()
    path = None
    for name in ("PingFang SC", "Hiragino Sans GB", "Heiti SC", "Microsoft YaHei",
                 "Microsoft YaHei UI", "SimHei", "Noto Sans CJK SC", "WenQuanYi Micro Hei"):
        found = pygame.font.match_font(name)
        if found:
            path = found
            break
    if path is None:
        import os
        # 系统字体匹配失败时直接找字体文件：macOS / Windows / Linux 各留一条路，
        # 保证打包成 exe 拿到别人电脑上也不会画成方块。
        for candidate in ("/System/Library/Fonts/PingFang.ttc",
                          "/System/Library/Fonts/Supplemental/Songti.ttc",
                          "C:/Windows/Fonts/msyh.ttc",
                          "C:/Windows/Fonts/msyh.ttf",
                          "C:/Windows/Fonts/simhei.ttf",
                          "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                          "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"):
            if os.path.exists(candidate):
                path = candidate
                break
    return {size: pygame.font.Font(path, size) for size in sizes}


def world_tile_size(world: dict, area_w: int, area_h: int) -> int:
    """按可用区域算出格子边长：小世界不放大，大世界不溢出。"""
    return max(MIN_THUMB_TILE, min(TILE, area_w // world["w"], area_h // world["h"]))


def box_rect(px: int, py: int, tile: int) -> pygame.Rect:
    """方块的矩形（判定点方框也用同一个，保证大小与方块一致）。"""
    return pygame.Rect(px + 2, py + 2, max(2, tile - 4), max(2, tile - 4))


def player_radius(tile: int) -> int:
    """玩家圆的半径（判定点圆环也用同一个，保证大小与玩家一致）。"""
    return max(3, int(tile * PLAYER_RATIO))


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


def draw_box(surface, box: dict, px: int, py: int, tile: int, on_goal: bool = False) -> None:
    """画一个方块：纯色平涂 + 描边 + 内层缩略图（不画入口横线）。

    - 含内部空间 = 黄，普通 = 蓝；
    - 默认描边近黑；**站在判定点上时描边换成亮色并加粗、再套一圈亮线**。
    """
    rect = box_rect(px, py, tile)
    radius = max(2, tile // 8)
    inner = box["inner_world"]
    fill = PALETTE["box_open"] if inner is not None else PALETTE["box_plain"]
    pygame.draw.rect(surface, rgb(fill), rect, border_radius=radius)

    if on_goal:                                   # 判定点达成：亮边加粗 + 外圈亮线
        pygame.draw.rect(surface, rgb(PALETTE["glow"]), rect,
                         max(4, tile // 8), border_radius=radius)
        ring = max(2, tile // 16)
        pygame.draw.rect(surface, rgb(PALETTE["glow"]), rect.inflate(ring, ring), 1,
                         border_radius=radius)
    else:
        pygame.draw.rect(surface, rgb(PALETTE["edge"]), rect,
                         max(2, tile // 16), border_radius=radius)

    if inner is not None:
        x0, y0, w, h, inner_tile = thumbnail_rect(px, py, tile, inner)
        if inner_tile >= MIN_THUMB_TILE:
            draw_world(surface, inner, (x0, y0), int(inner_tile), player=None, active=False, inner=True)
        elif w and h:
            pygame.draw.rect(surface, rgb(PALETTE["floor_inner"]), pygame.Rect(x0, y0, w, h))


def draw_world(surface, world: dict, origin, tile: int, player=None,
               active: bool = False, inner: bool = False) -> None:
    """画一个世界：地形 → 判定点 → 方块（含缩略图）→ 玩家 → 活动层高亮。

    `inner=True` 表示这是箱子的内部空间：空地画成深黄（外层是深灰）。
    """
    ox, oy = origin
    line = max(1, tile // 32)
    floor = PALETTE["floor_inner"] if inner else PALETTE["floor"]
    for y in range(world["h"]):
        for x in range(world["w"]):
            cell = pygame.Rect(ox + x * tile, oy + y * tile, tile, tile)
            ch = world["tiles"][y][x]
            pygame.draw.rect(surface, rgb(PALETTE["wall"] if ch == "#" else floor), cell)
            if tile >= 16:
                pygame.draw.rect(surface, rgb(PALETTE["bg"]), cell, line)
            if ch == GOAL:                                     # 箱子判定点：方框（与方块同大）
                goal_box = box_rect(cell.x, cell.y, tile)
                pygame.draw.rect(surface, rgb(PALETTE["goal"]), goal_box,
                                 max(2, tile // 16), border_radius=max(2, tile // 8))
            elif ch == PLAYER_GOAL:                            # 玩家判定点：圆环（与玩家同大）
                pygame.draw.circle(surface, rgb(PALETTE["goal"]), cell.center,
                                   player_radius(tile), max(2, tile // 16))

    for uid in sorted(world["boxes"]):
        box = world["boxes"][uid]
        on_goal = world["tiles"][box["y"]][box["x"]] == GOAL   # 方块压在判定点上 → 亮边
        draw_box(surface, box, ox + box["x"] * tile, oy + box["y"] * tile, tile, on_goal=on_goal)

    if player is not None:
        center = (ox + player[0] * tile + tile // 2, oy + player[1] * tile + tile // 2)
        radius = player_radius(tile)
        if world["tiles"][player[1]][player[0]] == PLAYER_GOAL:   # 玩家站上判定点 → 外圈发亮
            pygame.draw.circle(surface, rgb(PALETTE["glow"]), center,
                               radius + max(2, tile // 16), max(2, tile // 12))
        pygame.draw.circle(surface, rgb(PALETTE["player"]), center, radius)
        if radius >= 6:                                          # 两只黑色小圆眼（太小就不画）
            eye_radius = max(2, int(radius * 0.22))
            dx = max(2, int(radius * 0.38))
            dy = max(2, int(radius * 0.30))
            for sx in (-1, 1):
                pygame.draw.circle(surface, rgb(PALETTE["eye"]),
                                   (center[0] + sx * dx, center[1] - dy), eye_radius)

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
    overlay.fill((20, 22, 26, 210))
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
    path = state["player"]["path"]
    world = W.find_world(state["root"], path)
    tile = world_tile_size(world, width - TILE, height - HUD_H - TILE)
    ox = (width - world["w"] * tile) // 2
    oy = (height - HUD_H - world["h"] * tile) // 2
    player = (state["player"]["x"], state["player"]["y"])
    draw_world(surface, world, (ox, oy), tile, player=player, active=True, inner=bool(path))
    draw_hud(surface, state, fonts, title)
    if won:
        draw_win(surface, state, fonts)
