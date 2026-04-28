"""LawBot+ 启动入口"""
import os
import sys
import argparse
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="LawBot+ 启动器")
    parser.add_argument(
        "service",
        choices=["api", "ui", "mcp", "all"],
        help="启动的服务: api(API服务), ui(前端界面), mcp(MCP工具), all(全部)"
    )
    parser.add_argument("--host", default="0.0.0.0", help="服务地址")
    parser.add_argument("--port", type=int, default=8000, help="服务端口")
    parser.add_argument("--reload", action="store_true", help="开发模式热重载")
    
    args = parser.parse_args()
    
    logger.info(f"启动服务: {args.service}")
    
    if args.service == "api" or args.service == "all":
        run_api(args)
    
    if args.service == "ui" or args.service == "all":
        run_ui(args)
    
    if args.service == "mcp":
        run_mcp()


def run_api(args):
    """启动API服务"""
    import uvicorn
    from src.config import get_settings
    
    settings = get_settings()
    logger.info(f"启动API服务: {args.host}:{args.port}")
    
    uvicorn.run(
        "src.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload or settings.log_level == "DEBUG",
        log_level=settings.log_level.lower()
    )


def run_ui(args):
    """启动Streamlit UI"""
    logger.info("启动Streamlit UI...")
    
    os.system(f"streamlit run src/api/streamlit_app.py --server.address {args.host} --server.port {args.port + 1}")


def run_mcp():
    """启动MCP服务器"""
    from src.mcp.server import run_mcp_server
    logger.info("启动MCP服务器...")
    run_mcp_server()


if __name__ == "__main__":
    main()
