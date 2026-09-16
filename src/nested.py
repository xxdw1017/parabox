"""嵌套世界：进入 / 退出 / 箱子穿口（外→内、内→外）/ 自引用校验。

纯逻辑层：只依赖标准库，禁止 import pygame（见 AGENTS.md 分层依赖规则）。

口（door）由内层地图边缘决定（见 entity.py / world.py）：
- 内层宽高为奇数，四条边的中心格是口位；中心格是墙 → 这条边没口；
- 玩家/箱子朝方向 d 穿口 → 走的是**对侧**那条边的口（从下方推进去 → 内层底边的口）。

约定：
- 公开函数一律“先复制再改”，不修改传入的 state；
- 操作被拒绝时返回**传入的那个 state**（用 `result is state` 判断是否生效）；
- 返回栈记录 `(world_ref, box_uid)`：world_ref 是父世界的路径，退出时用 box_uid 现查箱子的位置；
- 搬运统一走 `_transfer_inplace()`，两条进入路径（吸入 / 推入别人的口）共用同一套落点与 validate_nesting()。
"""

from __future__ import annotations

import copy

from src import world as W
from src.entity import (DELTA, box_at, can_advance, chain_from, entry_door,
                        exit_side_at, has_door, is_openable, is_wall,
                        make_player, opposite, side_center, step)


def _side_of(parent_box: dict, child_box: dict):
    """child 在 parent 的哪一侧（只有相邻才有值）。"""
    delta = (child_box["x"] - parent_box["x"], child_box["y"] - parent_box["y"])
    for side, value in DELTA.items():
        if delta == value:
            return side
    return None


def _parent_of(state: dict, path):
    """返回 (父世界, 容器箱子)；path 为空时返回 (None, None)。"""
    if not path:
        return None, None
    parent = W.find_world(state["root"], path[:-1])
    return parent, parent["boxes"][path[-1]]


def _push_inward_inplace(world: dict, cell, direction: str) -> bool:
    """口格被箱子占住时，把那个箱子朝 direction（房间内侧）推一格。

    口格本来就空、或成功推开返回 True；推不动返回 False。
    """
    blocker = box_at(world, cell[0], cell[1])
    if blocker is None:
        return True
    target = step((blocker["x"], blocker["y"]), direction)
    if is_wall(world, target[0], target[1]) or box_at(world, target[0], target[1]) is not None:
        return False
    blocker["x"], blocker["y"] = target
    return True


def _clear_outer_cell_inplace(state: dict, parent: dict, cell, direction: str) -> bool:
    """让父世界的 cell 空出来：被箱子占住就按推动规则朝 direction 推开（可连锁）。"""
    if box_at(parent, cell[0], cell[1]) is None:
        return True
    chain = chain_from(parent, cell, direction)
    if not can_advance(parent, chain):
        return False
    boxes = [parent["boxes"][b["uid"]] for b in chain["boxes"]]
    if chain["sink"] is not None:
        if not _transfer_inplace(state, parent, chain["sink"], boxes[-1], bump=False):
            return False
        boxes = boxes[:-1]
    for b in boxes:
        b["x"], b["y"] = step((b["x"], b["y"]), direction)
    return True


def _enter_inplace(state: dict, box: dict, direction: str) -> bool:
    """玩家朝 direction 走进 box 的内部世界，落在对侧边的口格上。"""
    if not is_openable(box):
        return False
    path = list(state["player"]["path"])
    parent = W.find_world(state["root"], path)
    target = parent["boxes"].get(box["uid"])
    if target is None or not is_openable(target):
        return False
    door = entry_door(target["inner_world"], direction)
    if door is None:
        return False                       # 这一侧的内层边缘是墙 → 进不去
    _side, cell = door
    if not _push_inward_inplace(target["inner_world"], cell, direction):
        return False                       # 口被箱子占住且推进去也推不动
    state["return_stack"].append({"path": path, "box_uid": target["uid"]})
    state["player"] = make_player(path + [target["uid"]], cell[0], cell[1])
    state["moves"] += 1
    return True


def _exit_inplace(state: dict) -> bool:
    """玩家从内层退到外层：站在口格上朝口的外侧走，落点 = 外层箱子该侧的相邻格。"""
    path = list(state["player"]["path"])
    if not path:
        return False
    world = W.find_world(state["root"], path)
    side = exit_side_at(world, (state["player"]["x"], state["player"]["y"]))
    if side is None:
        return False                       # 没站在口上
    parent, container = _parent_of(state, path)
    cell = step((container["x"], container["y"]), side)
    if is_wall(parent, cell[0], cell[1]):
        return False                       # 外层那一格是墙 → 出不去
    if not _clear_outer_cell_inplace(state, parent, cell, side):
        return False                       # 外面被箱子堵住且推不动
    state["return_stack"].pop()
    state["player"] = make_player(path[:-1], cell[0], cell[1])
    state["moves"] += 1
    return True


def _transfer_inplace(state: dict, world: dict, target_box: dict, box: dict,
                      bump: bool = True) -> bool:
    """把 box（连同它的 inner_world）搬进 target_box 的内部世界。

    落点 = 面朝 box 那条边的口格；口格被占则先把占位箱子朝房间内侧推一格。
    操作完成后调用 validate_nesting()，出现自引用 / 循环嵌套就回滚。
    """
    if target_box is box or not is_openable(target_box):
        return False
    if world["boxes"].get(box["uid"]) is not box:
        return False
    side = _side_of(target_box, box)
    if side is None or not has_door(target_box["inner_world"], side):
        return False                       # 不是相邻，或那个方向没有口
    inner = target_box["inner_world"]
    cell = side_center(inner, side)
    if not _push_inward_inplace(inner, cell, opposite(side)):
        return False
    old = (box["x"], box["y"])
    del world["boxes"][box["uid"]]
    box["x"], box["y"] = cell
    inner["boxes"][box["uid"]] = box
    if W.validate_nesting(state["root"]):
        del inner["boxes"][box["uid"]]
        box["x"], box["y"] = old
        world["boxes"][box["uid"]] = box
        return False
    if bump:
        state["moves"] += 1
    return True


def _push_out_inplace(state: dict, box: dict) -> bool:
    """把内层站在口格上的箱子推出到外层，落点 = 外层箱子该侧的相邻格。"""
    path = list(state["player"]["path"])
    if not path:
        return False
    world = W.find_world(state["root"], path)
    side = exit_side_at(world, (box["x"], box["y"]))
    if side is None:
        return False                       # 箱子不在口格上
    parent, container = _parent_of(state, path)
    cell = step((container["x"], container["y"]), side)
    if is_wall(parent, cell[0], cell[1]):
        return False
    if not _clear_outer_cell_inplace(state, parent, cell, side):
        return False
    old = (box["x"], box["y"])
    del world["boxes"][box["uid"]]
    box["x"], box["y"] = cell
    parent["boxes"][box["uid"]] = box
    if W.validate_nesting(state["root"]):
        del parent["boxes"][box["uid"]]
        box["x"], box["y"] = old
        world["boxes"][box["uid"]] = box
        return False
    state["moves"] += 1
    return True


def enter_world(state: dict, box: dict, direction: str) -> dict:
    """玩家朝 direction 走进箱子的内部世界。条件不满足时返回传入的 state。"""
    new = copy.deepcopy(state)
    return new if _enter_inplace(new, box, direction) else state


def exit_world(state: dict) -> dict:
    """玩家从当前内层世界退出到外层（站在口格上朝外走）。出不去时返回传入的 state。"""
    new = copy.deepcopy(state)
    return new if _exit_inplace(new) else state


def transfer_into(state: dict, target_box: dict, box: dict) -> dict:
    """把 box 搬进 target_box 的内部世界（源世界 = 玩家当前所在世界）。"""
    new = copy.deepcopy(state)
    world = W.active_world(new)
    target = world["boxes"].get(target_box["uid"])
    child = world["boxes"].get(box["uid"])
    if target is None or child is None:
        return state
    return new if _transfer_inplace(new, world, target, child) else state


def push_out(state: dict, box: dict) -> dict:
    """把内层站在口格上的箱子推出到外层（玩家与箱子共用同一个口）。"""
    new = copy.deepcopy(state)
    world = W.active_world(new)
    target = world["boxes"].get(box["uid"])
    if target is None:
        return state
    return new if _push_out_inplace(new, target) else state


def swallow(state: dict, parent_box: dict, child_box: dict) -> dict:
    """推不动时的吸入：口正对着的、推不开的箱子被吸进 parent_box 的内部世界。

    与 push_into_inner() 共用同一套落点与 validate_nesting()。
    """
    return transfer_into(state, parent_box, child_box)


def push_into_inner(state: dict, sink_box: dict, box: dict) -> dict:
    """普通推动路径：链尾箱子贴着别人的口，被推入那个箱子的内部世界。

    与 swallow() 共用同一套落点与 validate_nesting()。
    """
    return transfer_into(state, sink_box, box)
