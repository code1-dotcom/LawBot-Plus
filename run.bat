@echo off
chcp 65001 > nul
echo ========================================
echo        LawBot+ 启动脚本
echo ========================================
echo.

REM 检查Python
python --version > nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.10+
    pause
    exit /b 1
)

REM 检查conda环境
echo [1/4] 检查conda环境...
call conda info --envs | findstr "lawbot-plus" > nul
if errorlevel 1 (
    echo [警告] 未找到lawbot-plus环境，是否继续使用当前环境?
    set /p confirm="按Enter继续，或Ctrl+C退出: "
)

REM 安装依赖
echo.
echo [2/4] 安装依赖...
pip install -r requirements.txt -q

REM 检查Docker
echo.
echo [3/4] 检查Docker服务...
docker info > nul 2>&1
if errorlevel 1 (
    echo [警告] Docker未运行，是否启动中间件服务?
    set /p confirm="按Enter启动，或Ctrl+C跳过: "
    docker compose -f docker-compose.middleware.yml up -d
) else (
    echo [提示] Docker已运行
    docker compose -f docker-compose.middleware.yml up -d
)

REM 启动服务
echo.
echo [4/4] 启动服务...
echo.
echo 请选择启动模式:
echo   [1] 启动API服务 (http://localhost:8000)
echo   [2] 启动Web界面 (http://localhost:8001)
echo   [3] 启动MCP工具服务器
echo   [4] 启动全部服务
echo.

set /p mode="请输入选项 [1-4]: "

if "%mode%"=="1" goto :api
if "%mode%"=="2" goto :ui
if "%mode%"=="3" goto :mcp
if "%mode%"=="4" goto :all
goto :end

:api
echo 启动API服务...
python -m src.main api
goto :end

:ui
echo 启动Web界面...
streamlit run src/api/streamlit_app.py
goto :end

:mcp
echo 启动MCP服务器...
python -m src.main mcp
goto :end

:all
echo 启动全部服务...
start "LawBot-API" cmd /c "python -m src.main api"
timeout /t 2 > nul
start "LawBot-UI" cmd /c "streamlit run src/api/streamlit_app.py"
goto :end

:end
pause
