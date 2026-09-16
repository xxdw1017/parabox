"""entity.py / world.py 的单元测试：数据结构、口（door）规则、关卡解析、嵌套校验、目标点统计。

口模型：内层世界宽高必须是奇数，四条边的中心格是口位；中心格是墙 → 这条边没口。
"""

import unittest
from pathlib import Path

from src import world as W
from src.entity import (DIRS, box_at, boxes_of, can_advance, chain_from, door_sides,
                        entry_door, exit_side_at, has_door, has_inner_world, in_bounds,
                        is_goal, is_openable, is_wall, make_box, make_player, opposite,
                        side_center, step, tile_at)

LEVEL_01 = Path(__file__).resolve().parent.parent / "levels" / "level_01.json"


def tiny_world(rows, boxes=(), **extra):
    """构造一个最小世界的测试辅助（默认当外层：不受内层边缘规则约束）。"""
    data = {"w": len(rows[0]), "h": len(rows), "tiles": list(rows), "boxes": list(boxes)}
    data.update(extra)
    return W.parse_world(data)


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


class TestEntity(unittest.TestCase):
    def test_opposite_and_step(self):
        self.assertEqual(opposite("up"), "down")
        self.assertEqual(step((2, 3), "left"), (1, 3))
        self.assertEqual(step((2, 3), "down"), (2, 4))
        for d in DIRS:
            self.assertEqual(opposite(opposite(d)), d)

    def test_tile_at_out_of_bounds_is_wall(self):
        w = tiny_world(["###", "#.#", "###"])
        self.assertTrue(is_wall(w, -1, 1))
        self.assertTrue(is_wall(w, 3, 1))
        self.assertEqual(tile_at(w, 1, 1), ".")

    def test_in_bounds_is_goal_and_make_player(self):
        w = tiny_world(["#####", "#.g.#", "#####"])
        self.assertTrue(in_bounds(w, 4, 2))
        self.assertFalse(in_bounds(w, 5, 2))
        self.assertTrue(is_goal(w, 2, 1))
        self.assertFalse(is_goal(w, 1, 1))
        p = make_player(["A"], 3, 4)
        self.assertEqual((p["path"], p["x"], p["y"]), (["A"], 3, 4))

    def test_box_at_and_boxes_of(self):
        w = tiny_world(["#####", "#...#", "#####"],
                       boxes=[{"uid": "b2", "at": [1, 1]}, {"uid": "b1", "at": [2, 1]}])
        self.assertEqual(box_at(w, 1, 1)["uid"], "b2")
        self.assertIsNone(box_at(w, 3, 1))
        self.assertEqual([b["uid"] for b in boxes_of(w)], ["b1", "b2"])

    def test_chain_from_collects_consecutive_boxes(self):
        w = tiny_world(["#######", "#.....#", "#######"],
                       boxes=[{"uid": "b1", "at": [1, 1]},
                              {"uid": "b2", "at": [2, 1]},
                              {"uid": "b3", "at": [3, 1]}])
        chain = chain_from(w, (1, 1), "right")
        self.assertEqual([b["uid"] for b in chain["boxes"]], ["b1", "b2", "b3"])
        self.assertIsNone(chain["sink"])
        self.assertEqual(chain["front"], (4, 1))

    def test_chain_from_stops_before_sink_box(self):
        """链尾前方是“口正对着我们”的箱子时，它是 sink，不算进链。"""
        w = tiny_world(["#######", "#.....#", "#######"],
                       boxes=[{"uid": "b1", "at": [1, 1]},
                              {"uid": "b2", "at": [2, 1]},
                              {"uid": "b3", "at": [3, 1], "inner_world": room("left")}])
        chain = chain_from(w, (1, 1), "right")
        self.assertEqual([b["uid"] for b in chain["boxes"]], ["b1", "b2"])
        self.assertEqual(chain["sink"]["uid"], "b3")
        self.assertEqual(chain["front"], (3, 1))
        self.assertTrue(can_advance(w, chain))

    def test_can_advance_open_and_blocked(self):
        open_world = tiny_world(["######", "#....#", "######"],
                                boxes=[{"uid": "b1", "at": [1, 1]}])
        self.assertTrue(can_advance(open_world, chain_from(open_world, (1, 1), "right")))
        blocked = tiny_world(["###", "#.#", "###"], boxes=[{"uid": "b1", "at": [1, 1]}])
        self.assertFalse(can_advance(blocked, chain_from(blocked, (1, 1), "left")))


class TestDoors(unittest.TestCase):
    def test_side_center(self):
        w = room("down")
        self.assertEqual(side_center(w, "up"), (2, 0))
        self.assertEqual(side_center(w, "down"), (2, 4))
        self.assertEqual(side_center(w, "left"), (0, 2))
        self.assertEqual(side_center(w, "right"), (4, 2))
        with self.assertRaises(KeyError):
            side_center(w, "north")

    def test_has_door_and_door_sides(self):
        self.assertEqual(door_sides(room("down")), ["down"])
        self.assertEqual(door_sides(room("left")), ["left"])
        self.assertEqual(door_sides(room("up", walls=[(2, 4)])), ["up"])
        sealed = room(door=None)
        self.assertEqual(door_sides(sealed), [])
        self.assertFalse(has_door(sealed, "down"))

    def test_entry_door_uses_opposite_side(self):
        """从下方推进去 → 走内层底边的口。"""
        self.assertEqual(entry_door(room("down"), "up"), ("down", (2, 4)))
        self.assertIsNone(entry_door(room("down"), "down"))       # 顶边没口
        self.assertEqual(entry_door(room("up"), "down"), ("up", (2, 0)))

    def test_exit_side_at(self):
        w = room("down")
        self.assertEqual(exit_side_at(w, (2, 4)), "down")
        self.assertIsNone(exit_side_at(w, (2, 3)))                # 不在口上
        self.assertIsNone(exit_side_at(room(door=None), (2, 4)))  # 封死

    def test_is_openable_and_has_inner_world(self):
        self.assertTrue(is_openable({"uid": "b", "x": 0, "y": 0, "inner_world": room("down")}))
        self.assertFalse(is_openable({"uid": "b", "x": 0, "y": 0, "inner_world": room(door=None)}))
        self.assertFalse(is_openable(make_box("plain", 0, 0)))
        self.assertTrue(has_inner_world({"uid": "b", "x": 0, "y": 0, "inner_world": room(door=None)}))


class TestParseLevel01(unittest.TestCase):
    def setUp(self):
        self.level = W.load_level(LEVEL_01)
        self.root = self.level["state"]["root"]

    def test_load_level_01(self):
        self.assertEqual(self.level["name"], "level_01")
        self.assertEqual((self.root["w"], self.root["h"]), (7, 6))
        self.assertEqual(self.root["start"], [3, 4])
        b1 = self.root["boxes"]["b1"]
        self.assertEqual((b1["x"], b1["y"]), (3, 3))
        self.assertIsNotNone(b1["inner_world"])

    def test_inner_world_structure(self):
        inner = self.root["boxes"]["b1"]["inner_world"]
        self.assertEqual((inner["w"], inner["h"]), (5, 5))
        self.assertEqual(door_sides(inner), ["down"])             # 底边中心开口
        self.assertEqual(entry_door(inner, "up"), ("down", (2, 4)))
        self.assertEqual(list(inner["boxes"]), ["b1a"])
        self.assertEqual((inner["boxes"]["b1a"]["x"], inner["boxes"]["b1a"]["y"]), (2, 2))
        self.assertEqual(inner["tiles"][1][2], "g")               # 内层目标点

    def test_level_01_scope_one_inner_box(self):
        """本关只放 1 个带内部空间的箱子（AGENTS.md 深度策略）。"""
        self.assertEqual(len(W.inner_boxes(self.root)), 1)

    def test_new_state_player_on_start(self):
        st = self.level["state"]
        self.assertEqual(st["player"]["path"], [])
        self.assertEqual((st["player"]["x"], st["player"]["y"]), (3, 4))
        self.assertEqual(st["moves"], 0)
        self.assertIs(W.active_world(st), self.root)

    def test_goal_count_is_recursive(self):
        self.assertEqual(W.count_goals(self.root), 2)
        self.assertEqual(W.covered_goals(self.root), 0)
        self.assertFalse(W.all_goals_covered(self.root))


class TestParseErrors(unittest.TestCase):
    def test_rejects_unknown_tile(self):
        with self.assertRaises(W.LevelError):
            tiny_world(["###", "#x#", "###"])

    def test_rejects_wrong_row_width(self):
        with self.assertRaises(W.LevelError):
            tiny_world(["###", "#.#.", "###"])
        with self.assertRaises(W.LevelError):
            tiny_world(["###", "#.#"])

    def test_rejects_too_small_world(self):
        with self.assertRaises(W.LevelError):
            tiny_world(["##", "##"])

    def test_rejects_two_player_starts(self):
        with self.assertRaises(W.LevelError):
            tiny_world(["#####", "#P.P#", "#####"])

    def test_rejects_box_on_wall(self):
        with self.assertRaises(W.LevelError):
            tiny_world(["###", "#.#", "###"], boxes=[{"uid": "b1", "at": [0, 0]}])

    def test_rejects_box_out_of_bounds(self):
        with self.assertRaises(W.LevelError):
            tiny_world(["###", "#.#", "###"], boxes=[{"uid": "b1", "at": [9, 9]}])

    def test_rejects_duplicate_uid(self):
        with self.assertRaises(W.LevelError):
            tiny_world(["#####", "#...#", "#####"],
                       boxes=[{"uid": "b1", "at": [1, 1]}, {"uid": "b1", "at": [2, 1]}])

    def test_rejects_missing_uid(self):
        with self.assertRaises(W.LevelError):
            tiny_world(["#####", "#...#", "#####"], boxes=[{"at": [1, 1]}])

    def test_rejects_box_on_player_start(self):
        with self.assertRaises(W.LevelError):
            tiny_world(["#####", "#.#P#", "#####"], boxes=[{"uid": "b1", "at": [3, 1]}])

    def test_rejects_even_inner_world(self):
        """口在边的中心格上 → 内层宽高必须是奇数。"""
        with self.assertRaises(W.LevelError):
            tiny_world(["#####", "#...#", "#####"],
                       boxes=[{"uid": "b1", "at": [1, 1],
                               "inner_world": {"w": 4, "h": 4,
                                               "tiles": ["####", "#..#", "#..#", "####"],
                                               "boxes": []}}])

    def test_rejects_border_opening_off_center(self):
        """内层边缘只有四条边的中心格可以是口，别的位置开洞要报错。"""
        with self.assertRaises(W.LevelError):
            tiny_world(["#####", "#...#", "#####"],
                       boxes=[{"uid": "b1", "at": [1, 1],
                               "inner_world": {"w": 5, "h": 5,
                                               "tiles": ["#####", "#...#", "#...#", "#...#", "#.###"],
                                               "boxes": []}}])

    def test_allows_sealed_inner_world(self):
        """四面全墙是合法数据（只是进不去）。"""
        root = tiny_world(["#####", "#...#", "#####"],
                          boxes=[{"uid": "b1", "at": [1, 1], "inner_world": room(door=None)}])
        self.assertEqual(door_sides(root["boxes"]["b1"]["inner_world"]), [])
        self.assertFalse(is_openable(root["boxes"]["b1"]))

    def test_parse_level_requires_goal(self):
        with self.assertRaises(W.LevelError):
            W.parse_level({"world": {"w": 3, "h": 3, "tiles": ["###", "#.#", "###"], "boxes": []}})

    def test_parse_level_requires_world(self):
        with self.assertRaises(W.LevelError):
            W.parse_level({"name": "x"})


class TestNestingValidation(unittest.TestCase):
    def test_validate_nesting_ok_for_level_01(self):
        root = W.load_level(LEVEL_01)["state"]["root"]
        self.assertEqual(W.validate_nesting(root), [])

    def test_validate_nesting_detects_self_reference(self):
        inner = W.parse_world(room("down"), "inner", is_inner=True)
        box = make_box("b1", 1, 1, inner)
        inner["boxes"]["b1"] = box                      # 箱子装自己
        root = tiny_world(["#####", "#...#", "#####"])
        root["boxes"]["b1"] = box
        errors = W.validate_nesting(root)
        self.assertEqual(len(errors), 1)
        self.assertIn("自引用", errors[0])

    def test_validate_nesting_detects_indirect_cycle(self):
        a_inner = W.parse_world(room("down"), "a", is_inner=True)
        b_inner = W.parse_world(room("down"), "b", is_inner=True)
        box_a, box_b = make_box("a", 1, 1, a_inner), make_box("b", 1, 1, b_inner)
        a_inner["boxes"]["b"] = box_b
        b_inner["boxes"]["a"] = box_a                   # a -> b -> a
        root = tiny_world(["#####", "#...#", "#####"])
        root["boxes"]["a"] = box_a
        self.assertTrue(any("自引用" in e for e in W.validate_nesting(root)))


class TestWorldLookup(unittest.TestCase):
    def setUp(self):
        self.state = W.load_level(LEVEL_01)["state"]
        self.root = self.state["root"]

    def test_find_world_and_box(self):
        inner = W.find_world(self.root, ["b1"])
        self.assertEqual((inner["w"], inner["h"]), (5, 5))
        self.assertIs(W.find_box(self.root, [], "b1"), self.root["boxes"]["b1"])
        self.assertIs(W.find_box(self.root, ["b1"], "b1a"), inner["boxes"]["b1a"])
        with self.assertRaises(KeyError):
            W.find_world(self.root, ["nope"])

    def test_active_world_follows_player_path(self):
        self.assertIs(W.active_world(self.state), self.root)
        self.state["player"]["path"] = ["b1"]
        self.assertIs(W.active_world(self.state), self.root["boxes"]["b1"]["inner_world"])

    def test_iter_worlds(self):
        self.assertEqual([p for p, _ in W.iter_worlds(self.root)], [[], ["b1"]])

    def test_first_free_cell_skips_walls_and_boxes(self):
        w = tiny_world(["####", "#..#", "####"], boxes=[{"uid": "b1", "at": [1, 1]}])
        self.assertEqual(W.first_free_cell(w), (2, 1))
        full = tiny_world(["###", "#.#", "###"], boxes=[{"uid": "b1", "at": [1, 1]}])
        self.assertIsNone(W.first_free_cell(full))

    def test_all_goals_covered_needs_every_layer(self):
        root = self.root
        root["boxes"]["b1"]["x"], root["boxes"]["b1"]["y"] = 3, 1
        self.assertFalse(W.all_goals_covered(root))
        root["boxes"]["b1"]["inner_world"]["boxes"]["b1a"]["x"] = 2
        root["boxes"]["b1"]["inner_world"]["boxes"]["b1a"]["y"] = 1
        self.assertTrue(W.all_goals_covered(root))


if __name__ == "__main__":
    unittest.main()
