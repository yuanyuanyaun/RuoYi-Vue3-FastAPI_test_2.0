@echo off
setlocal enabledelayedexpansion
cd /d %~dp0

REM ============================================================
REM  RuoYi-Vue3-FastAPI 被测系统一键启动脚本（Windows）
REM  用法：双击本文件即可；脚本会自动检查环境并给出提示
REM
REM  【前置环境】（脚本会自动检查，缺失会提示你安装）
REM    1. Python 3.10+（安装时勾选 Add python.exe to PATH）
REM    2. MySQL 8.x（本机 3306 端口）
REM    3. Redis（本机 6379 端口，无需密码）
REM    4. 端口 9099 空闲
REM ============================================================

REM ================= 可配置项 =================
set "DB_NAME=ruoyi-fastapi"
set "DB_PWD=123456"
REM 若你的 MySQL root 密码不同，请修改上面的 DB_PWD
REM ============================================

echo.
echo ============================================================
echo    RuoYi-Vue3-FastAPI 一键启动（Windows）
echo ============================================================
echo.

REM ---------- 1. 检查 Python ----------
echo [1/9] 检查 Python ...
set "PY_CMD="
py -3 --version >nul 2>&1 && set "PY_CMD=py -3"
if not defined PY_CMD python --version >nul 2>&1 && set "PY_CMD=python"
if not defined PY_CMD (
    echo   [缺少] 未找到 Python。
    echo   请安装 Python 3.10 或更高版本：https://www.python.org/downloads/
    echo   安装时务必勾选 "Add python.exe to PATH"。
    pause & exit /b 1
)
echo   [OK] 已找到 Python

REM ---------- 2. 检查 MySQL 客户端 ----------
echo [2/9] 检查 MySQL 客户端 ...
set "MYSQL="
where mysql >nul 2>&1 && set "MYSQL=mysql"
if not defined MYSQL if exist "D:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" set "MYSQL=D:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"
if not defined MYSQL if exist "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" set "MYSQL=C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"
if not defined MYSQL if exist "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe" set "MYSQL=C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe"
if not defined MYSQL (
    echo   [缺少] 未找到 MySQL 客户端。
    echo   请安装 MySQL 8.x：https://dev.mysql.com/downloads/installer/
    echo   安装完成后把 mysql.exe 所在目录加入 PATH，或修改本脚本 MYSQL 变量。
    pause & exit /b 1
)
echo   [OK] 已找到 MySQL

REM ---------- 3. 检查 MySQL 连接 ----------
echo [3/9] 检查 MySQL 连接（root 密码）...
"%MYSQL%" -uroot -p%DB_PWD% -e "SELECT 1;" >nul 2>&1
if errorlevel 1 (
    echo   [提示] MySQL 连接失败：root 密码不是 %DB_PWD%。
    echo   请编辑本文件顶部 DB_PWD=... 改为你的 MySQL root 密码后重试。
    pause & exit /b 1
)
echo   [OK] MySQL 连接成功

REM ---------- 4. 检查 Redis ----------
echo [4/9] 检查 Redis ...
powershell -NoProfile -Command "if ((Test-NetConnection 127.0.0.1 -Port 6379 -WarningAction SilentlyContinue).TcpTestSucceeded) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo   [缺少] 未检测到 Redis（127.0.0.1:6379）。
    echo   请安装并启动 Redis for Windows：https://github.com/tporadowski/redis/releases
    echo   安装后需在"服务"中启动 Redis 服务。
    pause & exit /b 1
)
echo   [OK] Redis 连接成功

REM ---------- 5. 检查端口 9099 ----------
echo [5/9] 检查端口 9099 ...
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 9099 -State Listen -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }" >nul 2>&1
if errorlevel 1 (
    echo   [提示] 端口 9099 已被占用，请先关闭占用该端口的程序再重试。
    pause & exit /b 1
)
echo   [OK] 端口 9099 空闲

REM ---------- 6. 创建虚拟环境并安装依赖 ----------
echo [6/9] 创建虚拟环境并安装依赖（首次较慢，请耐心等待）...
if not exist venv (
    %PY_CMD% -m venv venv
)
call venv\Scripts\activate.bat
python -m pip install -r requirements.txt -q --timeout 60 --retries 5
if errorlevel 1 (
    echo   [错误] 依赖安装失败。请把报错信息反馈给项目作者。
    pause & exit /b 1
)
echo   [OK] 依赖安装完成

REM ---------- 7. 初始化数据库 ----------
echo [7/9] 初始化数据库（建库 / 导种子数据 / 关验证码）...
"%MYSQL%" -uroot -p%DB_PWD% -e "CREATE DATABASE IF NOT EXISTS `%DB_NAME%` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;" >nul 2>&1
if errorlevel 1 (
    echo   [错误] 创建数据库失败，请检查 MySQL 权限。
    pause & exit /b 1
)
set "HAS_TABLE=0"
"%MYSQL%" -uroot -p%DB_PWD% -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='%DB_NAME%' AND table_name='sys_user';" > "%TEMP%\ruoyi_has_table.txt" 2>nul
set /p HAS_TABLE=<"%TEMP%\ruoyi_has_table.txt"
if "%HAS_TABLE%"=="0" (
    "%MYSQL%" --default-character-set=utf8mb4 -uroot -p%DB_PWD% %DB_NAME% < sql\ruoyi-fastapi.sql
    echo   [OK] 种子数据导入完成
) else (
    echo   [OK] 数据库已存在，跳过导入（如需重置：手动删除 %DB_NAME% 库后重跑本脚本）
)
"%MYSQL%" --default-character-set=utf8mb4 -uroot -p%DB_PWD% %DB_NAME% -e "UPDATE sys_config SET config_value='false' WHERE config_key='sys.account.captchaEnabled';" >nul 2>&1
echo   [OK] 验证码已关闭（登录无需验证码）

REM ---------- 8. 生成配置 ----------
echo [8/9] 生成 .env.dev 配置 ...
if not exist .env.dev (
    copy .env.dev.example .env.dev >nul
    echo   [OK] 已从模板生成 .env.dev
) else (
    echo   [OK] .env.dev 已存在，保持不动

REM ---------- 9. 检查 Redis 认证 ----------
echo [9/9] 检查 Redis 认证 ...
python check_redis.py
if errorlevel 1 (
    echo   [提示] Redis 连接失败：请检查 .env.dev 中的 REDIS_PASSWORD 等配置后重试。
    pause & exit /b 1
)
echo   [OK] Redis 认证通过
)

REM ---------- 启动 ----------
echo.
echo ============================================================
echo   启动后端（端口 9099）...
echo.
echo   看到 "Uvicorn running on http://0.0.0.0:9099" 即启动成功
echo   验证：浏览器打开 http://127.0.0.1:9099/docs
echo   登录测试：POST http://127.0.0.1:9099/login  admin / admin123
echo   停止：在此窗口按 Ctrl+C
echo ============================================================
echo.
powershell -NoProfile -Command "$env:PYTHONIOENCODING='utf-8'; [Console]::OutputEncoding=[Text.Encoding]::UTF8; & '.\venv\Scripts\ruoyi.exe' app run --env=dev 2>&1 | Tee-Object -FilePath '.\run.log'"
pause
