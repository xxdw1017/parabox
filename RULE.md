# RULE.md

## 一、通用行为准则
1. 每次修改 `src/` 下代码后，必须运行 `python -m unittest discover tests -v` 并通过，才允许结束当前任务。
2. 测试失败时，优先修测试或修代码，禁止在测试未通过的情况下继续添加新功能。
3. 禁止自动执行 `git push`、`git reset --hard`、`git clean -fd` 等不可逆操作。
4. 禁止删除 `levels/` 下已有文件，只能新增或修改。
5. 禁止引入 Pygame 以外的游戏引擎或重型依赖；新增依赖前必须说明理由并等待确认。
6. 禁止一次性重写整个文件；修改应尽量小步，每次改动后跑测试。
7. 禁止在未说明影响范围的情况下修改 `src/logic.py`、`src/world.py`、`src/nested.py` 的核心函数。
8. 禁止在渲染层（`render.py`、`ui.py`）中修改游戏状态，渲染层只读。

## 二、涉及游戏机制时的行为规范
游戏机制细节不在本文件中定义，Agent 应按以下指引去对应 Skill 中查找，不得自行发挥：

- 推箱子移动、箱子链推动、碰撞判定 → 查 `.dsh/skills/push-box-logic/SKILL.md`
- 箱子内部世界进入/退出、箱子被推入其他箱子内部、嵌套深度 → 查 `.dsh/skills/nested-world/SKILL.md`
- 多层世界渲染、箱子内部缩略图、活动层高亮 → 查 `.dsh/skills/world-rendering/SKILL.md`
- 关卡 JSON 格式、加载校验 → 查 `.dsh/skills/level-loading/SKILL.md`

若 SKILL.md 中未覆盖某种情况，Agent 不得自行扩展机制，应先说明“当前 Skill 未覆盖”，等待确认后再决定是补 Skill 还是改实现。

## 三、修改前必须确认
1. 修改移动规则前，先列出会受影响的测试用例。
2. 删除任何函数前，先确认没有测试和其他模块引用。
3. 修改关卡 JSON 格式前，先同步更新 `level-loading/SKILL.md` 中的格式定义。
4. 修改嵌套深度相关逻辑前，先确认 `nested-world/SKILL.md` 中的规则，不得擅自放宽或收紧深度限制。

## 四、代码质量约束
1. 逻辑层（`logic.py`、`world.py`、`nested.py`）必须是纯 Python，不依赖 Pygame。
2. 渲染层只读游戏状态，不写。
3. 新增函数必须有对应 unittest 测试。
4. 新增关卡只改 `levels/*.json`，不改代码。

## 五、交付检查
提交前必须确认：
- `python main.py` 能启动并进入选关界面。
- 至少一个关卡可完整通关。
- 所有测试通过。
- 演示视频已录制。
- 三个规则文件（AGENTS.md、各 SKILL.md、RULE.md）与当前实现一致。
