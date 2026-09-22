"""logic.py / nested.py 的单元测试：推箱子、链推动、吸入、穿口（双向）、进出内层世界、胜利判定。

口模型：内层世界四条边的中心格是口位；中心格是墙 → 这条边没口（墙限制进出）。
朝方向 d 穿口 → 走的是对侧那条边的口（从下方推进去 → 内层底边的口）。

测试名对齐两份技能文档（push-box-logic / nested-world）里的测试要求。
"""

import copy
import unittest
from pathlib import Path

from src import logic, nested
from src import world as W
from src.entity import make_player

LEVEL_01 = Path(__file__).resolve().parent.parent / "levels" / "level_01.json"


def room(door="down", w=5, h=5, boxes=(), walls=()):
    """内层世界：边缘全墙，只在指定边的中心格开口；walls 可加内部墙。"""
    grid = [["#"] * w for _ in range(h)]
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            grid[y][x] = "."
    for x, y in walls:
        grid[y][x] = "#"
    if door:
        centers = {"up": (w // 2, 0), "down": (w // 2, h - 1),
                   "left": (0, h // 2), "right": (w - 1, h // 2)}
        x, y = centers[door]
        grid[y][x] = "."
    return {"w": w, "h": h, "tiles": ["".join(r) for r in grid], "boxes": list(boxes)}


def state_of(rows, boxes=(), player=None):
    """由 ASCII 地图构造初始状态；player 可覆盖地图里的 P。"""
    root = W.parse_world({"w": len(rows[0]), "h": len(rows), "tiles": list(rows),
                          "boxes": list(boxes)})
    if player is not None:
        root["start"] = list(player)
    return W.new_state(root)


def inside(state, path, x, y):
    """把玩家直接放进某个内层世界（测试用）。"""
    state["return_stack"] = [{"path": list(path[:-1]), "box_uid": path[-1]}]
    state["player"] = make_player(list(path), x, y)
    return state


def pcell(state):
    p = state["player"]
    return (p["x"], p["y"])


def bcell(state, uid):
    box = W.active_world(state)["boxes"][uid]
    return (box["x"], box["y"])


class TestPushBox(unittest.TestCase):
    """push-box-logic 技能要求的用例。"""

    def test_push_single_box(self):
        st = state_of(["#####", "#P..#", "#####"], [{"uid": "b1", "at": [2, 1]}])
        new = logic.move(st, "right")
        self.assertEqual(bcell(new, "b1"), (3, 1))
        self.assertEqual(pcell(new), (2, 1))
        self.assertEqual(new["moves"], 1)
        self.assertEqual(pcell(st), (1, 1))             # 原状态不被修改

    def test_push_box_chain(self):
        st = state_of(["#######", "#P....#", "#######"],
                      [{"uid": "b1", "at": [2, 1]}, {"uid": "b2", "at": [3, 1]},
                       {"uid": "b3", "at": [4, 1]}])
        new = logic.move(st, "right")
        self.assertEqual([bcell(new, u) for u in ("b1", "b2", "b3")],
                         [(3, 1), (4, 1), (5, 1)])
        self.assertEqual(pcell(new), (2, 1))

    def test_push_chain_blocked_by_wall(self):
        st = state_of(["######", "#P...#", "######"],
                      [{"uid": "b1", "at": [2, 1]}, {"uid": "b2", "at": [3, 1]},
                       {"uid": "b3", "at": [4, 1]}])
        self.assertIs(logic.move(st, "right"), st)

    def test_push_box_into_inner_world(self):
        """链尾箱子贴着别人的口 → 被推进那个箱子的内部世界，落在该侧中心口格。"""
        st = state_of(["#####", "#P..#", "#####"],
                      [{"uid": "bX", "at": [2, 1]},
                       {"uid": "sink", "at": [3, 1], "inner_world": room("left")}])
        new = logic.move(st, "right")
        outer = W.active_world(new)
        self.assertNotIn("bX", outer["boxes"])
        moved = outer["boxes"]["sink"]["inner_world"]["boxes"]["bX"]
        self.assertEqual((moved["x"], moved["y"]), (0, 2))
        self.assertEqual(pcell(new), (2, 1))

    def test_push_box_into_box(self):
        """两个箱子的链推入 sink：贴着口的那个进去，其余前移一格。"""
        st = state_of(["######", "#P...#", "######"],
                      [{"uid": "b1", "at": [2, 1]}, {"uid": "b2", "at": [3, 1]},
                       {"uid": "sink", "at": [4, 1], "inner_world": room("left")}])
        new = logic.move(st, "right")
        outer = W.active_world(new)
        self.assertIn("b2", outer["boxes"]["sink"]["inner_world"]["boxes"])
        self.assertEqual(bcell(new, "b1"), (3, 1))
        self.assertEqual(bcell(new, "sink"), (4, 1))
        self.assertEqual(pcell(new), (2, 1))

    def test_swallow_box_at_entrance(self):
        """推不动时：口正对着的、推不开的箱子被吸入本箱子的内部世界。"""
        st = state_of(["######", "#P..##", "######"],
                      [{"uid": "A", "at": [2, 1], "inner_world": room("right")},
                       {"uid": "B", "at": [3, 1]}])
        new = logic.move(st, "right")
        outer = W.active_world(new)
        self.assertEqual(list(outer["boxes"]), ["A"])
        moved = outer["boxes"]["A"]["inner_world"]["boxes"]["B"]
        self.assertEqual((moved["x"], moved["y"]), (4, 2))       # 右边中心口
        self.assertEqual(pcell(new), (1, 1))
        self.assertEqual(new["moves"], 1)

    def test_swallow_requires_entrance_facing_push(self):
        """口不在推动方向上时不吸入、也不动。"""
        st = state_of(["######", "#P..##", "######"],
                      [{"uid": "A", "at": [2, 1], "inner_world": room("up")},
                       {"uid": "B", "at": [3, 1]}])
        self.assertIs(logic.move(st, "right"), st)
        self.assertEqual(bcell(st, "B"), (3, 1))

    def test_no_swallow_when_chain_can_move(self):
        st = state_of(["#######", "#P....#", "#######"],
                      [{"uid": "A", "at": [2, 1], "inner_world": room("right")},
                       {"uid": "B", "at": [3, 1]}])
        new = logic.move(st, "right")
        self.assertEqual(bcell(new, "A"), (3, 1))
        self.assertEqual(bcell(new, "B"), (4, 1))
        self.assertEqual(W.active_world(new)["boxes"]["A"]["inner_world"]["boxes"], {})

    def test_collect_chain_reports_sink(self):
        st = state_of(["######", "#P...#", "######"],
                      [{"uid": "b1", "at": [2, 1]},
                       {"uid": "sink", "at": [3, 1], "inner_world": room("left")}])
        chain = logic.collect_chain(st, "right")
        self.assertEqual([b["uid"] for b in chain["boxes"]], ["b1"])
        self.assertEqual(chain["sink"]["uid"], "sink")

    def test_can_swallow_needs_blocker_on_entrance(self):
        st = state_of(["######", "#P..##", "######"],
                      [{"uid": "A", "at": [2, 1], "inner_world": room("right")},
                       {"uid": "B", "at": [3, 1]}])
        world = W.active_world(st)
        chain = logic.collect_chain(st, "right")
        self.assertTrue(logic.can_swallow(world, chain["boxes"][0], chain, "right"))
        self.assertFalse(logic.can_swallow(world, chain["boxes"][0], chain, "left"))

    def test_move_into_wall_does_nothing(self):
        st = state_of(["###", "#P#", "###"])
        self.assertIs(logic.move(st, "right"), st)

    def test_move_does_not_mutate_input(self):
        st = state_of(["#####", "#P..#", "#####"], [{"uid": "b1", "at": [2, 1]}])
        before = copy.deepcopy(st)
        logic.move(st, "right")
        self.assertEqual(st, before)

    def test_move_rejects_unknown_direction(self):
        st = state_of(["###", "#P#", "###"])
        with self.assertRaises(KeyError):
            logic.move(st, "north")


class TestNestedWorld(unittest.TestCase):
    """nested-world 技能要求的用例（含箱子双向穿口）。"""

    @staticmethod
    def enter_fixture():
        """A 在 (2,1)、内层左边有口（口位 (0,2)），A 前方是墙 → 推不动 → 可进入。"""
        return state_of(["#####", "#P.#.", "#####"],
                        [{"uid": "A", "at": [2, 1], "inner_world": room("left")}])

    def test_enter_box(self):
        st = self.enter_fixture()
        new = logic.move(st, "right")
        self.assertEqual(new["player"]["path"], ["A"])
        self.assertEqual(pcell(new), (0, 2))                     # 左边中心口
        self.assertEqual(new["return_stack"], [{"path": [], "box_uid": "A"}])
        self.assertIs(W.active_world(new), new["root"]["boxes"]["A"]["inner_world"])
        self.assertEqual(new["moves"], 1)

    def test_enter_requires_entrance_cell(self):
        """这一侧的内层边缘是墙 → 进不去。"""
        st = state_of(["#####", "#P.#.", "#####"],
                      [{"uid": "A", "at": [2, 1], "inner_world": room("up")}])
        self.assertIs(logic.move(st, "right"), st)
        self.assertEqual(st["player"]["path"], [])

    def test_can_enter_checks_cell_and_direction(self):
        st = self.enter_fixture()
        box = W.active_world(st)["boxes"]["A"]
        self.assertTrue(logic.can_enter(st, box, "right"))
        self.assertFalse(logic.can_enter(st, box, "left"))
        self.assertFalse(logic.can_enter(st, box, "up"))

    def test_enter_creates_return_stack(self):
        st = self.enter_fixture()
        new = nested.enter_world(st, W.active_world(st)["boxes"]["A"], "right")
        self.assertIsNot(new, st)
        self.assertEqual(new["return_stack"], [{"path": [], "box_uid": "A"}])
        self.assertEqual(st["return_stack"], [])

    def test_enter_refused_for_plain_box(self):
        st = state_of(["#####", "#P..#", "#####"], [{"uid": "b1", "at": [2, 1]}])
        self.assertIs(nested.enter_world(st, W.active_world(st)["boxes"]["b1"], "right"), st)

    def test_enter_when_door_occupied_pushes_it_inward(self):
        """口上停着箱子时，先把那个箱子往房间里推一格，玩家再进去。"""
        st = state_of(["#####", "#P.#.", "#####"],
                      [{"uid": "A", "at": [2, 1],
                        "inner_world": room("left", boxes=[{"uid": "Z", "at": [0, 2]}])}])
        new = logic.move(st, "right")
        self.assertEqual(pcell(new), (0, 2))
        inner = W.find_world(new["root"], ["A"])
        self.assertEqual((inner["boxes"]["Z"]["x"], inner["boxes"]["Z"]["y"]), (1, 2))

    def test_enter_refused_when_door_blocked_inside(self):
        st = state_of(["#####", "#P.#.", "#####"],
                      [{"uid": "A", "at": [2, 1],
                        "inner_world": room("left", walls=[(1, 2)],
                                            boxes=[{"uid": "Z", "at": [0, 2]}])}])
        self.assertIs(logic.move(st, "right"), st)

    def test_sealed_box_cannot_be_entered(self):
        """四面全墙的箱子进不去。"""
        st = state_of(["#####", "#P.#.", "#####"],
                      [{"uid": "A", "at": [2, 1], "inner_world": room(door=None)}])
        self.assertIs(logic.move(st, "right"), st)

    def test_door_is_decided_by_inner_edge(self):
        """口由内层边缘决定：多开一条边就能从两个方向进。"""
        inner = room("left")
        inner["tiles"][4] = "##.##"                              # 再开一个底边口
        boxes = [{"uid": "A", "at": [2, 1], "inner_world": inner}]
        from_left = logic.move(state_of(["#####", "#P.#.", "#...#", "#####"], boxes,
                                        player=[1, 1]), "right")
        self.assertEqual(from_left["player"]["path"], ["A"])
        from_below = logic.move(state_of(["#####", "#...#", "#...#", "#####"], boxes,
                                         player=[2, 2]), "up")
        self.assertEqual(from_below["player"]["path"], ["A"])
        self.assertEqual(pcell(from_below), (2, 4))              # 底边中心口

    def test_exit_box(self):
        st = self.enter_fixture()
        inside_state = logic.move(st, "right")
        back = logic.move(inside_state, "left")                  # 站在口上朝口外走
        self.assertEqual(back["player"]["path"], [])
        self.assertEqual(pcell(back), (1, 1))
        self.assertEqual(back["return_stack"], [])
        self.assertEqual(bcell(back, "A"), (2, 1))
        self.assertEqual(back["moves"], 2)

    def test_exit_to_open_tile(self):
        st = logic.move(self.enter_fixture(), "right")
        back = nested.exit_world(st)
        self.assertIsNot(back, st)
        self.assertEqual(pcell(back), (1, 1))
        self.assertEqual(back["player"]["path"], [])

    def test_exit_pushes_box(self):
        """外层落点被箱子占据 → 推开它再出去。"""
        st = state_of(["#####", "#...#", "#####"],
                      [{"uid": "A", "at": [3, 1], "inner_world": room("left")},
                       {"uid": "Z", "at": [2, 1]}])
        inside(st, ["A"], 0, 2)
        back = nested.exit_world(st)
        self.assertIsNot(back, st)
        self.assertEqual(bcell(back, "Z"), (1, 1))
        self.assertEqual(pcell(back), (2, 1))
        self.assertEqual(back["player"]["path"], [])

    def test_exit_blocked_by_wall(self):
        st = state_of(["#####", "##..#", "#####"],
                      [{"uid": "A", "at": [2, 1], "inner_world": room("left")}])
        inside(st, ["A"], 0, 2)
        self.assertIs(nested.exit_world(st), st)
        self.assertEqual(st["player"]["path"], ["A"])

    def test_exit_without_stack_does_nothing(self):
        st = state_of(["###", "#P#", "###"])
        self.assertIs(nested.exit_world(st), st)

    def test_box_moves_with_inner_world(self):
        """推动箱子，内部世界整体随箱子平移，内部实体相对位置不变。"""
        st = state_of(["#####", "#P..#", "#####"],
                      [{"uid": "A", "at": [2, 1],
                        "inner_world": room("down", boxes=[{"uid": "a1", "at": [1, 1]}])}])
        new = logic.move(st, "right")
        box = W.active_world(new)["boxes"]["A"]
        self.assertEqual((box["x"], box["y"]), (3, 1))
        self.assertEqual((box["inner_world"]["boxes"]["a1"]["x"],
                          box["inner_world"]["boxes"]["a1"]["y"]), (1, 1))
        self.assertEqual(W.validate_nesting(new["root"]), [])

    def test_push_box_deeper_nesting(self):
        """玩家已在内层，再把内层的箱子推入另一个箱子的内部 → 深度 +1（不设上限）。"""
        st = state_of(["#####", "#P..#", "#####"],
                      [{"uid": "A", "at": [2, 1],
                        "inner_world": room("down", boxes=[
                            {"uid": "B", "at": [2, 2]},
                            {"uid": "C", "at": [3, 2], "inner_world": room("left")}])}])
        inside(st, ["A"], 1, 2)
        new = logic.move(st, "right")
        self.assertIn("B", W.find_world(new["root"], ["A", "C"])["boxes"])
        self.assertEqual(list(W.find_world(new["root"], ["A"])["boxes"]), ["C"])
        self.assertEqual(pcell(new), (2, 2))

    def test_transfer_into_shares_coordinates_and_validation(self):
        """吸入与推入共用同一个搬运原语：落点是对应边的中心口格。"""
        st = state_of(["#####", "#P..#", "#####"],
                      [{"uid": "A", "at": [2, 1], "inner_world": room("right")},
                       {"uid": "B", "at": [3, 1]}])
        new = nested.swallow(st, W.active_world(st)["boxes"]["A"], W.active_world(st)["boxes"]["B"])
        moved = new["root"]["boxes"]["A"]["inner_world"]["boxes"]["B"]
        self.assertEqual((moved["x"], moved["y"]), (4, 2))

    def test_transfer_into_full_inner_world_is_refused(self):
        """口被占、占位箱子又推不进房间 → 拒绝搬运。"""
        st = state_of(["#####", "#P..#", "#####"],
                      [{"uid": "A", "at": [2, 1],
                        "inner_world": room("right", walls=[(3, 2)],
                                            boxes=[{"uid": "fill", "at": [4, 2]}])},
                       {"uid": "B", "at": [3, 1]}])
        res = nested.transfer_into(st, W.active_world(st)["boxes"]["A"],
                                   W.active_world(st)["boxes"]["B"])
        self.assertIs(res, st)
        self.assertEqual(list(W.active_world(st)["boxes"]), ["A", "B"])

    def test_reject_self_nesting(self):
        """搬运会让箱子进入自己的内部世界时，操作被拒绝且状态不变。"""
        st = state_of(["#####", "#...#", "#####"],
                      [{"uid": "A", "at": [2, 1], "inner_world": room("down")},
                       {"uid": "B", "at": [3, 1], "inner_world": room("left")}])
        box_a = st["root"]["boxes"]["A"]
        box_b = st["root"]["boxes"]["B"]
        box_a["inner_world"]["boxes"]["A"] = box_a                # 人为制造自引用
        res = nested.transfer_into(st, box_b, box_a)
        self.assertIs(res, st)
        self.assertIs(st["root"]["boxes"]["A"], box_a)
        self.assertNotIn("A", box_b["inner_world"]["boxes"])

    def test_push_box_out_of_inner_world(self):
        """内层的箱子站在口格上、朝口外推 → 被推出到外层（与玩家同一个口）。"""
        st = state_of(["#####", "#...#", "#...#", "#...#", "#####"],
                      [{"uid": "A", "at": [3, 1],
                        "inner_world": room("down", boxes=[{"uid": "W", "at": [2, 4]}])}])
        inside(st, ["A"], 2, 3)
        new = logic.move(st, "down")
        self.assertIsNot(new, st)
        self.assertIn("W", new["root"]["boxes"])                  # 箱子已经在外层
        self.assertEqual((new["root"]["boxes"]["W"]["x"], new["root"]["boxes"]["W"]["y"]),
                         (3, 2))                                  # 外层箱子该侧的相邻格
        self.assertNotIn("W", W.find_world(new["root"], ["A"])["boxes"])
        self.assertEqual(pcell(new), (2, 4))

    def test_push_box_out_requires_clear_outer_cell(self):
        """外层落点被顶死的箱子占住 → 推不出去，玩家也不动。"""
        st = state_of(["#####", "#...#", "#...#", "#####"],
                      [{"uid": "A", "at": [3, 1],
                        "inner_world": room("down", boxes=[{"uid": "W", "at": [2, 4]}])},
                       {"uid": "Z", "at": [3, 2]}])
        inside(st, ["A"], 2, 3)
        self.assertIs(logic.move(st, "down"), st)
        self.assertIn("W", W.find_world(st["root"], ["A"])["boxes"])


class TestWinAndLevel(unittest.TestCase):
    """胜利判定与可通关性（RULE.md §五：至少一个关卡可完整通关）。"""

    def test_level_01_solution_wins(self):
        state = W.load_level(LEVEL_01)["state"]
        for _ in range(5):
            state = logic.move(state, "up")
        self.assertTrue(logic.check_win(state))
        self.assertEqual(state["moves"], 5)
        self.assertEqual(state["player"]["path"], ["b1"])

    def test_check_win_requires_player_on_goal(self):
        """有 G 时：箱子都到位还不够，玩家必须站上去。"""
        st = state_of(["#####", "#gG.#", "#...#", "#####"],
                      [{"uid": "b1", "at": [1, 1]}], player=[2, 2])
        self.assertFalse(logic.check_win(st))            # 箱子已在 g 上，但玩家没站在 G
        st = logic.move(st, "up")                        # (2,2) → (2,1) = G
        self.assertTrue(logic.check_win(st))

    def test_check_win_false_initially(self):
        self.assertFalse(logic.check_win(W.load_level(LEVEL_01)["state"]))

    def test_check_win_needs_every_layer(self):
        """只盖住外层目标点还不算赢。"""
        state = W.load_level(LEVEL_01)["state"]
        for _ in range(2):
            state = logic.move(state, "up")
        self.assertFalse(logic.check_win(state))

    def test_moves_counter_only_counts_accepted_actions(self):
        state = W.load_level(LEVEL_01)["state"]
        state = logic.move(state, "left")                        # (2,4) 是空地
        self.assertEqual(state["moves"], 1)
        blocked = logic.move(state, "down")                      # (2,5) 是墙 → 不计数
        self.assertIs(blocked, state)
        self.assertEqual(blocked["moves"], 1)


if __name__ == "__main__":
    unittest.main()
