"""LawBot+ 多智能体法律咨询系统"""

__version__ = "1.0.0"
__author__ = "LawBot Team"

from src.config import get_settings
from src.agents.workflow import run_legal_consultation
from src.rag.knowledge_base import legal_kb

__all__ = [
    "get_settings",
    "run_legal_consultation",
    "legal_kb"
]
