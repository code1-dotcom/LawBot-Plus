"""LLM客户端 - 统一接入阿里百炼API"""
from typing import Optional

from langchain_openai import ChatOpenAI

from src.config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class LLMClient:
    """阿里百炼API客户端封装"""

    def __init__(
        self,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ):
        settings = get_settings()
        self.model = model if model is not None else settings.llm_model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client: Optional[ChatOpenAI] = None

    @property
    def client(self) -> ChatOpenAI:
        """懒加载LLM客户端"""
        if self._client is None:
            settings = get_settings()
            self._client = ChatOpenAI(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_key=settings.dashscope_api_key,
                base_url=settings.dashscope_base_url,
            )
            logger.info(f"LLM客户端初始化完成: {self.model}")
        return self._client

    async def ainvoke(self, messages: list[dict]) -> str:
        """异步调用LLM"""
        try:
            response = await self.client.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            raise

    def invoke(self, messages: list[dict]) -> str:
        """同步调用LLM"""
        try:
            response = self.client.invoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            raise


# 全局LLM实例 - 从 settings 读取模型名称
_settings = get_settings()
llm_client = LLMClient(model=_settings.llm_model_name, temperature=0.7)

# 分析用LLM（更高质量）
analysis_llm = LLMClient(model=_settings.analysis_model_name, temperature=0.3)

# 审核用LLM（更低温度）
review_llm = LLMClient(model=_settings.analysis_model_name, temperature=0.1)
