# 打包与投屏（Windows 电脑）

目标：**在自己那台 Windows 电脑上双击一个 exe 就能玩**，不需要装 Python、不需要联网。

---

## 一、拿到 exe（二选一）

### 方案 A：在自己的 Windows 上本地打包（推荐，离线可用）

1. 把整个项目文件夹拷到 Windows 电脑（U 盘 / 网盘都行）。
2. 双击 **`build_windows.bat`**。
   它会自动：建打包环境 `.venv-build` → 装 `pygame` 与 `pyinstaller` → 跑单元测试 → 打包 → 自检产物。
3. 完成后产物在 **`dist\RecursiveBox.exe`**，脚本会自动打开 `dist` 文件夹。

> 前提：这台 Windows 上装了 Python 3.12（安装时勾选 *Add python.exe to PATH*）。
> 没有 Python 就只能走方案 B。

### 方案 B：让 GitHub 云端构建（手边没 Python 时）

1. 把代码 push 到 `https://github.com/xxdw1017/parabox`（VS Code 里 Publish / Sync）。
2. 打开仓库页面 → **Actions** → 左侧 **build-windows** → 选最新一次成功的运行。
3. 页面底部 **Artifacts** → 下载 **RecursiveBox-windows**（一个 zip）。
4. 解压得到 `RecursiveBox.exe`。

云端构建同样会先跑 121 个单元测试、再打包、再自检，任何一步失败都不会产出可下载的包。
配置见 `.github/workflows/build.yml`。

---

## 二、在 Windows 上运行

- 双击 `RecursiveBox.exe` → 直接进入选关界面（窗口 1280×720，固定尺寸）。
- 首次运行 Windows 可能弹 **"Windows 已保护你的电脑"**（SmartScreen）：
  点 **更多信息 → 仍要运行**。这是因为 exe 没有代码签名证书，不是病毒。
- 操作：`方向键 / WASD` 移动 · `U` 撤销 · `R` 重置 · `ESC` 回选关 · `Enter` 开始。

## 三、投屏前先自检一次

```
RecursiveBox.exe --selftest
```

不开窗口跑一遍"能不能启动 / 关卡在不在 / 能不能渲染和移动"，退出码 0 表示通过，
并在 exe 旁边生成 **`selftest_report.txt`**（窗口模式下看不到控制台，这个文件就是凭证）：

```
关卡目录：...\levels
发现关卡：2 个
渲染与移动：OK（步数 3）
SELFTEST OK
```

> 如果报告里写"没找到关卡"，说明 exe 没把 `levels/` 打进去 —— 不要在课上用这个包。

## 四、投屏与分辨率

- 程序窗口固定 **1280×720**（渲染约定如此，不做自适应缩放）。投屏时：
  - 笔记本分辨率设为 **1920×1080**（或 1366×768 以上）再投，窗口能完整显示；
  - 若投影仪只支持 **1024×768**，窗口会被裁掉一部分 —— 用"复制"模式前先把笔记本分辨率调到 1280×720 或更低。
- 游戏内 `ESC` 之后是选关界面，`↑/↓` 选关、`Enter` 开始，适合课上按顺序演示两关。

## 五、临时加 / 换关卡不用重新打包

exe 旁边的 `levels/` 目录**优先于**打包内置的那份：

```
dist\
├── RecursiveBox.exe
└── levels\            ← 手动新建，放 level_03.json 等
    └── level_03.json
```

没有这个目录时用的是打包内置的关卡（`levels/level_01.json`、`level_02.json`）。
关卡格式见 README「关卡数据格式」。

## 六、常见问题

| 现象 | 原因 / 处理 |
|---|---|
| 双击没反应 / 一闪而过 | 关掉杀毒软件的"误报拦截"，或在命令行里跑一次看报错；先跑 `--selftest` 确认包是好的 |
| SmartScreen 拦住了 | 更多信息 → 仍要运行（未签名 exe 的正常提示） |
| 界面里中文是方块 | 目标机器缺中文字体；Windows 一般自带微软雅黑，若被精简版系统删掉，装一个即可 |
| 启动要等 2~4 秒 | 单文件 exe 需要先解包，正常现象；想更快可改用 `--onedir` |
| 投屏时窗口比屏幕大 | 见上面「四、投屏与分辨率」 |
| 没有任何声音 | 预期行为：当前版本没有音效（README「已知限制」） |

## 七、打包原理（一句话版）

`parabox.spec` 让 PyInstaller 把 `main.py` + `src/` + `levels/` + Python 解释器 + SDL 一起塞进
单个 exe；`src/paths.py` 负责在"源码运行 / 打包运行"两种情况下都找到关卡目录；
`src/selftest.py` 提供 `--selftest` 自检，所以"包是不是好的"不靠肉眼判断。

相关文件：

```
parabox.spec                 PyInstaller 配置（单文件 / 目录模式、图标、打入 levels/）
tools/build_app.py           打包 + 自检一条命令
build_windows.bat            Windows 上双击即可（建环境 → 装依赖 → 测试 → 打包 → 自检）
.github/workflows/build.yml  云端构建 Windows exe（备份方案）
src/paths.py                 运行位置解析（frozen / _MEIPASS / exe 旁边的 levels）
src/selftest.py              --selftest 自检实现
```
