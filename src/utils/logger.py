"""日志配置模块"""
import sys
from pathlib import Path

from loguru import logger

from src.config import get_settings


def setup_logging():
    """配置Loguru日志"""
    settings = get_settings()

    # 移除默认处理器
    logger.remove()

    # 控制台输出（带颜色）
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.log_level,
        colorize=True,
    )

    # 文件输出
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        log_path,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=settings.log_level,
        rotation="100 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
    )

    return logger


def get_logger(name: str = None):
    """获取日志记录器"""
    if name:
        return logger.bind(name=name)
    return logger
