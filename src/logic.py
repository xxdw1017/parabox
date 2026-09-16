"""推箱子：移动、箱子链推动、吸入调度、箱子穿口、胜利判定。

纯逻辑层：只依赖标准库，禁止 import pygame（见 AGENTS.md 分层依赖规则）。

一次 move() 的判定顺序（见 push-box-logic / nested-world 技能）：
1. 站在口格上朝口的外侧走 → 退出内层；
2. 前方是墙 → 不动；
3. 前方没有箱子 → 走一格；
4. 内层里，链尾箱子正站在口格上并朝口外推 → 把它推出到外层；
5. 箱子链推得动 → 整条链前进一格（链尾可能被推进别人的口）；
6. 推不动 → 先看是否触发吸入，再看玩家能不能从口进入箱子，都不满足则不动。
"""

from __future__ import annotations

import copy

from src import nested
from src import world as W
from src.entity import (DELTA, box_at, can_advance, chain_from, entry_door,
                        exit_side_at, has_door, is_openable, is_wall,
                        make_player, opposite, step)


def check_win(state: dict) -> bool:
    """胜利判定：所有层的目标点都被箱子盖住（AGENTS.md「胜利判定」）。"""
    return W.all_goals_covered(state["root"])


def collect_chain(state: dict, direction: str) -> dict:
    """玩家朝 direction 推时，前方那条箱子链（含 sink：口正对着我们的箱子）。"""
    world = W.active_world(state)
    player = state["player"]
    return chain_from(world, step((player["x"], player["y"]), direction), direction)


def can_swallow(world: dict, first: dict, chain: dict, direction: str) -> bool:
    """推不动时是否触发吸入：first 的口正对推动方向，且口上顶着推不开的箱子。"""
    if not is_openable(first):
        return False
    if not has_door(first["inner_world"], direction):
        return False
    if len(chain["boxes"]) < 2:
        return False
    cell = step((first["x"], first["y"]), direction)
    blocker = box_at(world, cell[0], cell[1])
    return blocker is not None and blocker["uid"] == chain["boxes"][1]["uid"]


def can_enter(state: dict, box: dict, direction: str) -> bool:
    """玩家能否进入箱子：对侧边的内层边缘有口，玩家站在外侧相邻格并朝箱子走。"""
    if not is_openable(box):
        return False
    if entry_door(box["inner_world"], direction) is None:
        return False
    side = opposite(direction)
    outer = step((box["x"], box["y"]), side)
    player = state["player"]
    return (player["x"], player["y"]) == outer


def move(state: dict, direction: str) -> dict:
    """玩家朝 direction 走一步，返回新状态（不修改传入的 state）。"""
    if direction not in DELTA:
        raise KeyError(direction)
    world = W.active_world(state)
    player = state["player"]

    # 1) 站在口格上、朝口的外侧走 = 退出内层
    if exit_side_at(world, (player["x"], player["y"])) == direction:
        return nested.exit_world(state)

    x, y = step((player["x"], player["y"]), direction)

    # 2) 前方是墙
    if is_wall(world, x, y):
        return state

    chain = chain_from(world, (x, y), direction)

    # 3) 前方没有箱子：走一格
    if not chain["boxes"]:
        return _walk(state, x, y)

    # 4) 内层里，链尾箱子站在口格上并朝口外推 → 推出外层
    end = chain["boxes"][-1]
    if exit_side_at(world, (end["x"], end["y"])) == direction:
        result = nested.push_out(state, end)
        if result is state:
            return state
        return _advance(result, direction, [b["uid"] for b in chain["boxes"][:-1]])

    # 5) 推得动：整条链前进一格（链尾可能被推进别人的口）
    if can_advance(world, chain):
        if chain["sink"] is not None:
            result = nested.push_into_inner(state, chain["sink"], chain["boxes"][-1])
            if result is state:
                return state                                  # 口被占且推不开 → 不动
            return _advance(result, direction, [b["uid"] for b in chain["boxes"][:-1]])
        return _advance(state, direction, [b["uid"] for b in chain["boxes"]])

    # 6) 推不动：先吸入，再考虑进入箱子
    first = chain["boxes"][0]
    if can_swallow(world, first, chain, direction):
        result = nested.swallow(state, first, chain["boxes"][1])
        if result is not state:
            return result
    if can_enter(state, first, direction):
        return nested.enter_world(state, first, direction)
    return state


def _walk(state: dict, x: int, y: int) -> dict:
    """玩家走到相邻空格。"""
    new = copy.deepcopy(state)
    player = new["player"]
    new["player"] = make_player(player["path"], x, y)
    new["moves"] += 1
    return new


def _advance(state: dict, direction: str, box_uids) -> dict:
    """整条链（按 uid）前进一格，玩家同时前进一步。"""
    new = copy.deepcopy(state)
    world = W.active_world(new)
    for uid in box_uids:
        box = world["boxes"][uid]
        box["x"], box["y"] = step((box["x"], box["y"]), direction)   # inner_world 随箱子平移
    player = new["player"]
    dx, dy = DELTA[direction]
    new["player"] = make_player(player["path"], player["x"] + dx, player["y"] + dy)
    new["moves"] += 1
    return new
