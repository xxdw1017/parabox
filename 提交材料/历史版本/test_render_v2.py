"""渲染层 / 选关界面 / 主循环状态机的测试。

需要 pygame（项目内 `.venv`）；没装时整组自动跳过，保证
`python -m unittest discover tests -v` 在任何环境都能跑完（RULE.md §一.1）。
"""

import copy
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")      # 无头渲染
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from src import logic, render, ui
    from src import world as W
    from src.game import Game
    HAVE_PYGAME = True
except ImportError:                                     # pragma: no cover
    HAVE_PYGAME = False

ROOT = Path(__file__).resolve().parent.parent
LEVELS = ROOT / "levels"
SKILL_DOC = ROOT / ".dsh" / "skills" / "world-rendering" / "SKILL.md"


def key(code):
    """构造一个 KEYDOWN 事件。"""
    return pygame.event.Event(pygame.KEYDOWN, key=code)


def empty_world(w=5, h=5):
    return {"w": w, "h": h, "tiles": [["."] * w for _ in range(h)],
            "boxes": {}, "start": None, "entry": None, "entry_dir": None}


@unittest.skipUnless(HAVE_PYGAME, "未安装 pygame")
class TestPalette(unittest.TestCase):
    def test_contrast_targets(self):
        ratios = render.palette_contrasts()
        self.assertGreaterEqual(ratios["wall/floor"], 3.0, ratios)
        for name in ("player/floor", "goal/floor", "box/floor", "door/floor", "text/bg", "muted/bg"):
            self.assertGreaterEqual(ratios[name], 4.5, ratios)
        self.assertGreaterEqual(ratios["brand/box"], 3.0, ratios)

    def test_palette_matches_skill_doc(self):
        """代码里的每个颜色都要在 world-rendering 技能里出现（RULE.md §五）。"""
        doc = SKILL_DOC.read_text(encoding="utf-8")
        for name, value in render.PALETTE.items():
            self.assertIn(value, doc, f"配色 {name}={value} 未写进技能文档")


@unittest.skipUnless(HAVE_PYGAME, "未安装 pygame")
class TestGeometry(unittest.TestCase):
    def test_thumbnail_fits_inside_cell(self):
        x, y, w, h, tile = render.thumbnail_rect(100, 200, 64, empty_world(5, 5))
        self.assertGreaterEqual(x, 100)
        self.assertGreaterEqual(y, 200)
        self.assertLessEqual(x + w, 164)
        self.assertLessEqual(y + h, 264)
        self.assertAlmostEqual(w / h, 1.0, delta=0.2)
        self.assertAlmostEqual(tile, 10.0, delta=0.5)

    def test_thumbnail_keeps_aspect_ratio(self):
        _, _, w, h, _ = render.thumbnail_rect(0, 0, 64, empty_world(6, 3))
        self.assertAlmostEqual(w / h, 2.0, delta=0.25)

    def test_thumbnail_scales_down_and_hits_floor(self):
        """每深一层缩略图更小；小到下限就不再递归（只画色块）。"""
        _, _, w1, _, tile1 = render.thumbnail_rect(0, 0, 64, empty_world(5, 5))
        _, _, _, _, tile2 = render.thumbnail_rect(0, 0, int(tile1), empty_world(3, 3))
        self.assertLess(tile2, tile1)
        self.assertLess(tile2, render.MIN_THUMB_TILE)

    def test_thumbnail_empty_world(self):
        self.assertEqual(render.thumbnail_rect(0, 0, 64, None), (0, 0, 0, 0, 0.0))

    def test_world_tile_size_caps_and_fits(self):
        self.assertEqual(render.world_tile_size(empty_world(5, 5), 2000, 2000), render.TILE)
        self.assertLessEqual(render.world_tile_size(empty_world(50, 50), 640, 640), 12)


@unittest.skipUnless(HAVE_PYGAME, "未安装 pygame")
class TestDraw(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.surface = pygame.Surface((800, 450))
        cls.fonts = render.load_fonts()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_fonts_render_cjk(self):
        self.assertIn(22, self.fonts)
        self.assertGreater(self.fonts[22].size("递归之箱")[0], 0)

    def test_draw_scene_is_read_only(self):
        """RULE.md §一.8：渲染层只读，画完状态必须一模一样。"""
        state = W.load_level(LEVELS / "level_01.json")["state"]
        before = copy.deepcopy(state)
        render.draw_scene(self.surface, state, self.fonts, "测试关卡")
        self.assertEqual(state, before)

    def test_draw_every_step_including_inner_world(self):
        state = W.load_level(LEVELS / "level_01.json")["state"]
        render.draw_scene(self.surface, state, self.fonts, "t")
        for _ in range(5):
            state = logic.move(state, "up")
            render.draw_scene(self.surface, state, self.fonts, "t")     # 含箱内缩略图那一帧

    def test_draw_player_goal_marker(self):
        """玩家站位点（方框，站上后填实）能正常画出来，且不改状态。"""
        root = W.parse_world({"w": 5, "h": 4, "tiles": ["#####", "#gG.#", "#...#", "#####"],
                              "boxes": [{"uid": "b1", "at": [1, 1]}]})
        state = W.new_state(root, start=[2, 2])
        before = copy.deepcopy(state)
        render.draw_scene(self.surface, state, self.fonts, "G 测试")
        self.assertEqual(state, before)
        render.draw_scene(self.surface, W.new_state(root, start=[2, 1]), self.fonts, "G 测试")

    def test_draw_win_overlay(self):
        state = W.load_level(LEVELS / "level_01.json")["state"]
        render.draw_win(self.surface, state, self.fonts)

    def test_draw_nested_two_levels(self):
        """深度 2 的缩略图也能画（不设层数上限）。"""
        state = W.load_level(LEVELS / "level_01.json")["state"]
        for direction in ["up", "up", "up"]:
            state = logic.move(state, direction)
        render.draw_scene(self.surface, state, self.fonts, "t")
        self.assertEqual(state["player"]["path"], ["b1"])


@unittest.skipUnless(HAVE_PYGAME, "未安装 pygame")
class TestMenu(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.fonts = render.load_fonts()
        self.surface = pygame.Surface((800, 450))

    def tearDown(self):
        pygame.quit()

    def test_list_levels(self):
        entries = ui.list_levels(LEVELS)
        self.assertTrue(any(e["name"] == "level_01" and e["ok"] for e in entries))

    def test_list_levels_marks_broken_level(self):
        """非法关卡不阻断选关（level-loading 技能）。"""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "level_99.json").write_text(
                '{"name": "bad", "world": {"w": 3, "h": 3, "tiles": ["###", "#x#", "###"]}}',
                encoding="utf-8")
            entries = ui.list_levels(tmp)
        self.assertEqual(len(entries), 1)
        self.assertFalse(entries[0]["ok"])
        self.assertTrue(entries[0]["error"])

    def test_menu_command_navigation(self):
        self.assertEqual(ui.menu_command(key(pygame.K_DOWN), 0, 2), ("select", 1))
        self.assertEqual(ui.menu_command(key(pygame.K_UP), 0, 2), ("select", 1))
        self.assertEqual(ui.menu_command(key(pygame.K_RETURN), 1, 2), ("start", 1))
        self.assertEqual(ui.menu_command(key(pygame.K_ESCAPE), 0, 2), ("quit", None))
        self.assertIsNone(ui.menu_command(key(pygame.K_SPACE), 0, 0))
        self.assertEqual(ui.menu_command(key(pygame.K_ESCAPE), 0, 0), ("quit", None))

    def test_draw_menu_and_cards(self):
        entries = ui.list_levels(LEVELS)
        rects = ui.card_rects(self.surface.get_size(), len(entries))
        self.assertEqual(len(rects), len(entries))
        ui.draw_menu(self.surface, entries, 0, self.fonts)
        ui.draw_menu(self.surface, [], 0, self.fonts)          # 空关卡列表也不能崩


@unittest.skipUnless(HAVE_PYGAME, "未安装 pygame")
class TestGameFlow(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.fonts = render.load_fonts()
        self.surface = pygame.Surface((640, 360))
        self.game = Game(levels_dir=LEVELS)

    def tearDown(self):
        pygame.quit()

    def test_menu_to_play_and_draw(self):
        self.assertEqual(self.game.scene, "menu")
        self.game.draw(self.surface, self.fonts)
        self.game.handle_event(key(pygame.K_RETURN))
        self.assertEqual(self.game.scene, "play")
        self.game.draw(self.surface, self.fonts)

    def test_play_to_win_and_back(self):
        self.game.start_level(0)
        for code in (pygame.K_UP, pygame.K_UP, pygame.K_UP, pygame.K_UP, pygame.K_UP):
            self.game.handle_event(key(code))
            self.game.draw(self.surface, self.fonts)
        self.assertEqual(self.game.scene, "win")
        self.assertTrue(self.game.won)
        self.assertEqual(self.game.state["moves"], 5)
        self.game.handle_event(key(pygame.K_RETURN))
        self.assertEqual(self.game.scene, "menu")

    def test_undo_and_reset(self):
        self.game.start_level(0)
        self.game.handle_event(key(pygame.K_UP))
        self.assertEqual(self.game.state["moves"], 1)
        self.assertTrue(self.game.undo())
        self.assertEqual(self.game.state["moves"], 0)
        self.game.handle_event(key(pygame.K_UP))
        self.game.handle_event(key(pygame.K_UP))
        self.assertTrue(self.game.reset())
        self.assertEqual(self.game.state["moves"], 0)
        self.assertEqual(self.game.history, [])

    def test_esc_returns_to_menu(self):
        self.game.start_level(0)
        self.game.handle_event(key(pygame.K_ESCAPE))
        self.assertEqual(self.game.scene, "menu")

    def test_quit_from_menu_stops_loop(self):
        self.assertTrue(self.game.running)
        self.game.handle_event(key(pygame.K_ESCAPE))
        self.assertFalse(self.game.running)

    def test_broken_level_cannot_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "level_99.json").write_text('{"world": {}}', encoding="utf-8")
            game = Game(levels_dir=tmp)
        self.assertFalse(game.entries[0]["ok"])
        self.assertFalse(game.start_level(0))
        self.assertEqual(game.scene, "menu")


if __name__ == "__main__":
    unittest.main()
