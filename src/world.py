"""世界 / 关卡数据结构：解析、校验与查询。

纯逻辑层：只依赖标准库，禁止 import pygame（见 AGENTS.md 分层依赖规则）。

职责划分（见 AGENTS.md 目录结构）：
- 本模块 = 数据层：关卡 JSON 的解析与校验、世界树的查找、目标点统计；
- logic.py = 推箱子 / 链推动 / 胜利判定；
- nested.py = 内部世界的进入 / 退出 / 搬运 / 自引用校验。

「口」的规则（本模型的核心，配合 entity.py）：
- 内层世界的宽高必须是**奇数**，四条边的中心格即口位；
- 某条边有口 ⟺ 该边中心格不是墙；
- 边缘环上除四个中心格外必须都是墙，避免“半个口”这种歧义。
"""

from __future__ import annotations

import json
from pathlib import Path

from src.entity import (DIRS, FLOOR, GOAL, PLAYER_START, TILE_CHARS, WALL,
                        box_at, has_inner_world, side_center)


class LevelError(ValueError):
    """关卡数据非法。"""


def _cell_list(value, where: str, name: str):
    if not isinstance(value, list) or len(value) != 2 or not all(isinstance(v, int) for v in value):
        raise LevelError(f"{where}: {name} 需要 [x, y] 两个整数")
    return [value[0], value[1]]


def _check_inner_border(world: dict, where: str) -> None:
    """内层世界的边缘环：除四条边的中心格外必须都是墙。"""
    centers = {side_center(world, side) for side in DIRS}
    for y in range(world["h"]):
        for x in range(world["w"]):
            if x not in (0, world["w"] - 1) and y not in (0, world["h"] - 1):
                continue
            if (x, y) in centers:
                continue
            if world["tiles"][y][x] != WALL:
                raise LevelError(
                    f"{where}: 内层世界边缘 ({x}, {y}) 必须是墙（只有四条边的中心格可以是口）")


def parse_world(data: dict, where: str = "world", is_inner: bool = False) -> dict:
    """把关卡 JSON 里的一个世界解析成世界 dict；数据非法时抛 LevelError。

    is_inner=True 表示这是某个箱子的 inner_world：宽高必须是奇数，边缘环受口规则约束。
    """
    if not isinstance(data, dict):
        raise LevelError(f"{where}: 必须是对象")
    w, h = data.get("w"), data.get("h")
    if not isinstance(w, int) or not isinstance(h, int) or w < 3 or h < 3:
        raise LevelError(f"{where}: w / h 必须是 >= 3 的整数")
    if is_inner and (w % 2 == 0 or h % 2 == 0):
        raise LevelError(f"{where}: 内层世界的宽高必须是奇数（口在边的中心格上），当前 {w}x{h}")
    rows = data.get("tiles")
    if not isinstance(rows, list) or len(rows) != h:
        raise LevelError(f"{where}: tiles 需要 {h} 行")
    tiles = []
    for y, row in enumerate(rows):
        if not isinstance(row, str) or len(row) != w:
            raise LevelError(f"{where}: 第 {y} 行需要 {w} 个字符")
        for ch in row:
            if ch not in TILE_CHARS:
                raise LevelError(f"{where}: 第 {y} 行出现未知字符 {ch!r}")
        tiles.append(list(row))

    starts = [(x, y) for y, row in enumerate(tiles) for x, ch in enumerate(row) if ch == PLAYER_START]
    if len(starts) > 1:
        raise LevelError(f"{where}: 玩家起点 P 只能有一个")
    for x, y in starts:
        tiles[y][x] = FLOOR

    world = {"w": w, "h": h, "tiles": tiles, "boxes": {},
             "start": list(starts[0]) if starts else None}
    if is_inner:
        _check_inner_border(world, where)

    boxes_data = data.get("boxes", []) or []
    if not isinstance(boxes_data, list):
        raise LevelError(f"{where}: boxes 必须是数组")
    for i, raw in enumerate(boxes_data):
        if not isinstance(raw, dict):
            raise LevelError(f"{where}: boxes[{i}] 必须是对象")
        uid = raw.get("uid")
        if not isinstance(uid, str) or not uid:
            raise LevelError(f"{where}: boxes[{i}] 缺少非空 uid")
        if uid in world["boxes"]:
            raise LevelError(f"{where}: 箱子 uid 重复：{uid}")
        at = _cell_list(raw.get("at"), f"{where}.{uid}", "at")
        x, y = at
        if not (0 <= x < w and 0 <= y < h):
            raise LevelError(f"{where}.{uid}: at 越界")
        if tiles[y][x] == WALL:
            raise LevelError(f"{where}.{uid}: 箱子不能放在墙上")
        if box_at(world, x, y) is not None:
            raise LevelError(f"{where}.{uid}: 两个箱子不能放在同一格")
        if world["start"] is not None and world["start"] == [x, y]:
            raise LevelError(f"{where}.{uid}: 箱子不能压在玩家起点上")
        inner_data = raw.get("inner_world")
        inner = parse_world(inner_data, f"{where}.{uid}.inner_world", is_inner=True) \
            if inner_data is not None else None
        world["boxes"][uid] = {"uid": uid, "x": x, "y": y, "inner_world": inner}
    return world


def parse_level(data: dict) -> dict:
    """解析整份关卡数据，返回 {"name", "title", "hint", "state"}。"""
    if not isinstance(data, dict) or "world" not in data:
        raise LevelError("关卡数据缺少 world 字段")
    root = parse_world(data["world"], "world")
    if count_goals(root) == 0:
        raise LevelError("关卡至少需要一个目标点 g")
    return {
        "name": data.get("name", "level"),
        "title": data.get("title", ""),
        "hint": data.get("hint", ""),
        "state": new_state(root),
    }


def load_level(path) -> dict:
    """从 JSON 文件读取关卡；返回 parse_level 的结构。"""
    with Path(path).open(encoding="utf-8") as fp:
        return parse_level(json.load(fp))


def new_state(root: dict, start: list | None = None) -> dict:
    """以某个世界为根构造初始游戏状态。"""
    cell = start if start is not None else (root.get("start") or first_free_cell(root))
    if cell is None:
        raise LevelError("世界为空，找不到可放置玩家的格子")
    return {"root": root,
            "player": {"path": [], "x": cell[0], "y": cell[1]},
            "return_stack": [], "moves": 0}


def find_world(root: dict, path) -> dict:
    """按路径（uid 列表）找到世界；路径不存在时抛 KeyError。"""
    world = root
    for uid in path:
        world = world["boxes"][uid]["inner_world"]
    return world


def find_box(root: dict, path, uid: str) -> dict:
    """按路径 + uid 找到箱子；不存在时抛 KeyError。"""
    return find_world(root, path)["boxes"][uid]


def active_world(state: dict) -> dict:
    """玩家当前所在的世界。"""
    return find_world(state["root"], state["player"]["path"])


def iter_worlds(world: dict, path=()):
    """深度优先遍历世界树，产出 (path, world)。"""
    yield list(path), world
    for uid in sorted(world["boxes"]):
        inner = world["boxes"][uid]["inner_world"]
        if inner is not None:
            yield from iter_worlds(inner, list(path) + [uid])


def validate_nesting(world: dict) -> list[str]:
    """校验嵌套结构，返回错误信息列表（空列表 = 合法）。

    唯一的硬性校验是自引用 / 循环嵌套：某个箱子的 inner_world 直接或间接地包含它自己，
    递归遍历与绘制会无限循环（见 nested-world 技能）。深度本身不设上限。
    """
    errors = []

    def walk(w: dict, ancestors: list[dict]):
        for uid in sorted(w["boxes"]):
            box = w["boxes"][uid]
            if any(box is a for a in ancestors):
                errors.append(f"自引用：箱子 {uid} 的 inner_world 直接或间接包含自身")
                continue
            inner = box["inner_world"]
            if inner is not None:
                walk(inner, ancestors + [box])

    walk(world, [])
    return errors


def count_goals(world: dict) -> int:
    """统计世界树中所有目标点的数量。"""
    total = 0
    for _, w in iter_worlds(world):
        for row in w["tiles"]:
            total += sum(1 for ch in row if ch == GOAL)
    return total


def covered_goals(world: dict) -> int:
    """统计被箱子盖住的目标点数量（含所有层）。"""
    total = 0
    for _, w in iter_worlds(world):
        for box in w["boxes"].values():
            if w["tiles"][box["y"]][box["x"]] == GOAL:
                total += 1
    return total


def all_goals_covered(world: dict) -> bool:
    """所有层的目标点是否都被箱子盖住。"""
    return count_goals(world) > 0 and count_goals(world) == covered_goals(world)


def first_free_cell(world: dict):
    """按行优先返回第一个没有箱子的空地 / 目标点；没有则 None。"""
    for y in range(world["h"]):
        for x in range(world["w"]):
            if world["tiles"][y][x] == WALL:
                continue
            if box_at(world, x, y) is None:
                return (x, y)
    return None


def inner_boxes(world: dict) -> list[dict]:
    """返回所有携带内部世界的箱子（按路径排序），用于统计与测试。"""
    found = []
    for path, w in iter_worlds(world):
        for uid in sorted(w["boxes"]):
            if has_inner_world(w["boxes"][uid]):
                found.append((path, w["boxes"][uid]))
    return found
