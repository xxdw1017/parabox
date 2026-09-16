@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo   递归之箱 · Windows 打包（双击本文件即可）
echo ============================================
echo.

rem ---- 1. 找一个可用的 Python ----
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% --version >nul 2>nul
if not %errorlevel%==0 (
  echo [x] 没找到 Python。
  echo     办法一：装 Python 3.12（安装时勾选 Add python.exe to PATH），再双击本文件。
  echo     办法二：把代码 push 到 GitHub，在仓库的 Actions 里下载云端构建好的 exe
  echo             ^(见 PACKAGING.md^)。
  echo.
  pause
  exit /b 1
)

rem ---- 2. 建一个独立的打包环境，装依赖 ----
if not exist .venv-build (
  echo [1/4] 建立打包环境 .venv-build ...
  %PY% -m venv .venv-build || (echo [x] 建虚拟环境失败 & pause & exit /b 1)
)
call .venv-build\Scripts\activate.bat

echo [2/4] 安装 pygame 与 pyinstaller（第一次会下载，稍等）...
python -m pip install --upgrade pip >nul
python -m pip install pygame==2.6.1 pyinstaller || (echo [x] 依赖安装失败，检查网络 & pause & exit /b 1)

rem ---- 3. 跑测试，再打包并自检 ----
echo [3/4] 单元测试 ...
python -m unittest discover tests -q || (echo [x] 测试未通过，先修代码再打包 & pause & exit /b 1)

echo [4/4] 打包（几分钟）...
python tools\build_app.py || (echo [x] 打包或自检失败，看上面的输出 & pause & exit /b 1)

echo.
echo ============================================
echo   完成：dist\RecursiveBox.exe
echo   拷到 U 盘 / 直接双击就能玩；投屏前可先跑
echo     dist\RecursiveBox.exe --selftest
echo   同目录会生成 selftest_report.txt
echo ============================================
start "" "dist"
pause
