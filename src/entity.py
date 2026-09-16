"""玩家、箱子与「口」的数据结构。

纯逻辑层：只依赖标准库，禁止 import pygame（见 AGENTS.md 分层依赖规则）。

世界状态一律用嵌套 dict 表示（见 AGENTS.md 代码约定）：

    世界 = {
        "w": int, "h": int,
        "tiles": [[str]],            # "#" 墙 / "." 空地 / "g" 箱子目标点 / "G" 玩家站位点
        "boxes": {uid: 箱子},
        "start": [x, y] | None,      # 解析前是 "P" 的位置，即玩家起点
    }
    箱子 = {"uid": str, "x": int, "y": int, "inner_world": 世界 | None}
    玩家 = {"path": [uid, ...], "x": int, "y": int}   # path 是玩家所在世界的路径

**口（door）由内层地图的边缘决定，不看方向字段**：
- 内层世界的宽高必须是奇数，四条边的**中心格**就是该边的口位；
- 某条边有口 ⟺ 该边中心格不是墙（墙限制进出）；
- 边缘环上除四个中心格以外必须都是墙（由 `world.parse_world` 校验，避免歧义）。

箱子 dict 就是 nested-world 技能里的 `WorldContainer`：它持有 `inner_world`。
坐标一律用 `(x, y)` 元组表示格子坐标，不用像素坐标做逻辑。
"""

from __future__ import annotations

DIRS = ("up", "down", "left", "right")
DELTA = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
_OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}

WALL = "#"
FLOOR = "."
GOAL = "g"                  # 箱子要盖住的目标点
PLAYER_GOAL = "G"           # 玩家最终要站在的目标点（整关最多一个）
PLAYER_START = "P"
TILE_CHARS = (WALL, FLOOR, GOAL, PLAYER_GOAL, PLAYER_START)


def opposite(direction: str) -> str:
    """返回反方向；direction 非法时抛 KeyError。"""
    return _OPPOSITE[direction]


def step(cell: tuple[int, int], direction: str) -> tuple[int, int]:
    """返回 cell 沿 direction 走一格后的格子坐标。"""
    dx, dy = DELTA[direction]
    return (cell[0] + dx, cell[1] + dy)


def make_player(path, x: int, y: int) -> dict:
    """构造玩家状态；path 是玩家所在世界的路径（[] 表示最外层）。"""
    return {"path": list(path), "x": x, "y": y}


def make_box(uid: str, x: int, y: int, inner_world: dict | None = None) -> dict:
    """构造箱子（WorldContainer）：带 inner_world 即可进入，口由内层地图边缘决定。"""
    return {"uid": uid, "x": x, "y": y, "inner_world": inner_world}


def in_bounds(world: dict, x: int, y: int) -> bool:
    """格子是否在世界范围内。"""
    return 0 <= x < world["w"] and 0 <= y < world["h"]


def tile_at(world: dict, x: int, y: int) -> str:
    """取地形；越界一律当作墙。"""
    if not in_bounds(world, x, y):
        return WALL
    return world["tiles"][y][x]


def is_wall(world: dict, x: int, y: int) -> bool:
    """该格是不是墙（越界也是）。"""
    return tile_at(world, x, y) == WALL


def is_goal(world: dict, x: int, y: int) -> bool:
    """该格是不是箱子目标点（小写 g）。"""
    return tile_at(world, x, y) == GOAL


def is_player_goal(world: dict, x: int, y: int) -> bool:
    """该格是不是玩家站位目标点（大写 G）。"""
    return tile_at(world, x, y) == PLAYER_GOAL


def box_at(world: dict, x: int, y: int):
    """返回占据该格的箱子，没有则返回 None。"""
    for box in world["boxes"].values():
        if box["x"] == x and box["y"] == y:
            return box
    return None


# ---------------------------------------------------------------- 口（door）

def side_center(world: dict, side: str) -> tuple[int, int]:
    """某条边中心格的坐标；内层宽高为奇数，所以中心格唯一。"""
    if side == "up":
        return (world["w"] // 2, 0)
    if side == "down":
        return (world["w"] // 2, world["h"] - 1)
    if side == "left":
        return (0, world["h"] // 2)
    if side == "right":
        return (world["w"] - 1, world["h"] // 2)
    raise KeyError(side)


def has_door(world: dict, side: str) -> bool:
    """这条边有没有口：中心格不是墙就有。"""
    return tile_at(world, *side_center(world, side)) != WALL


def door_sides(world: dict) -> list[str]:
    """这个世界四边里有口的那些边（顺序固定为 up/down/left/right）。"""
    return [side for side in DIRS if has_door(world, side)]


def entry_door(inner_world: dict, direction: str):
    """朝 direction 走进这个世界时用的口。

    口在该方向**对侧**那条边上（从下方推进去 → 走内层底边的口，继续往上走进房间）。
    返回 `(side, (x, y))`；这条边没口就返回 None。
    """
    side = opposite(direction)
    if not has_door(inner_world, side):
        return None
    return side, side_center(inner_world, side)


def exit_side_at(world: dict, cell: tuple[int, int]):
    """站在 cell 上能否出去：该格是某条边的中心口就返回那条边（= 外侧方向），否则 None。"""
    for side in DIRS:
        if has_door(world, side) and side_center(world, side) == tuple(cell):
            return side
    return None


def has_inner_world(box: dict) -> bool:
    """该箱子是否携带内部世界（不管有没有口）。"""
    return box.get("inner_world") is not None


def is_openable(box: dict) -> bool:
    """该箱子是否可进出：有内部世界，且至少一条边有口。"""
    inner = box.get("inner_world")
    return inner is not None and bool(door_sides(inner))


def chain_from(world: dict, start: tuple[int, int], direction: str) -> dict:
    """从 start 起沿 direction 收集连续箱子链。

    返回 {"boxes": [...], "sink": 箱子|None, "front": (x, y)}：
    - boxes 按“离玩家由近到远”排列；
    - sink 是链尾前方那个“口正对着我们”的箱子（链尾箱子会被推进它的口，不计入 boxes）；
    - front 是链尾前方的第一格（空地，或 sink 所在格）。
    """
    boxes = []
    cell = start
    prev_cell = None
    while True:
        box = box_at(world, *cell)
        if box is None:
            return {"boxes": boxes, "sink": None, "front": cell}
        if prev_cell is not None and is_openable(box) \
                and has_door(box["inner_world"], opposite(direction)):
            return {"boxes": boxes, "sink": box, "front": cell}
        boxes.append(box)
        prev_cell = cell
        cell = step(cell, direction)


def can_advance(world: dict, chain: dict) -> bool:
    """箱子链能否推进一格。

    - 链尾前方是空地 / 目标点 → True；
    - 链尾前方是 sink（口正对着我们的箱子）→ 链尾那个箱子会被推进它的口，也 True；
    - 链尾前方是墙 → False（整条链不动，玩家也不动）。
    """
    if chain["sink"] is not None:
        return bool(chain["boxes"])
    return not is_wall(world, chain["front"][0], chain["front"][1])


def boxes_of(world: dict) -> list[dict]:
    """当前世界的箱子列表（按 uid 排序，保证顺序稳定）。"""
    return [world["boxes"][uid] for uid in sorted(world["boxes"])]
