#!/bin/bash
# LawBot+ 启动脚本 (Linux/macOS)

set -e

echo "========================================"
echo "       LawBot+ 启动脚本"
echo "========================================"
echo ""

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到Python，请先安装Python 3.10+"
    exit 1
fi

# 检查conda环境
if conda env list | grep -q "lawbot-plus"; then
    echo "[✓] 找到conda环境: lawbot-plus"
    source ~/miniconda3/etc/profile.d/conda.sh  # 调整路径
    conda activate lawbot-plus
else
    echo "[提示] 未找到lawbot-plus环境，继续使用当前环境"
fi

# 安装依赖
echo ""
echo "[2/4] 安装依赖..."
pip install -r requirements.txt -q

# 启动Docker中间件
echo ""
echo "[3/4] 启动Docker中间件..."
docker compose -f docker-compose.middleware.yml up -d || echo "[提示] Docker服务可能未运行"

# 启动服务
echo ""
echo "[4/4] 启动服务..."
echo ""
echo "请选择启动模式:"
echo "  [1] 启动API服务 (http://localhost:8000)"
echo "  [2] 启动Web界面 (http://localhost:8001)"
echo "  [3] 启动MCP工具服务器"
echo "  [4] 启动全部服务"
echo ""

read -p "请输入选项 [1-4]: " mode

case $mode in
    1)
        echo "启动API服务..."
        python -m src.main api
        ;;
    2)
        echo "启动Web界面..."
        streamlit run src/api/streamlit_app.py
        ;;
    3)
        echo "启动MCP服务器..."
        python -m src.main mcp
        ;;
    4)
        echo "启动全部服务..."
        python -m src.main api &
        sleep 2
        streamlit run src/api/streamlit_app.py &
        ;;
esac
