"""Embedding模型封装 - 支持本地BGE模型"""
from typing import List, Optional
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer

from src.config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EmbeddingModel:
    """本地Embedding模型封装"""

    def __init__(
        self,
        model_name: str = None,
        model_path: str = None,
        dimension: int = None
    ):
        self.settings = get_settings()
        self.model_name = model_name or self.settings.embedding_model_name
        self.model_path = model_path or self.settings.embedding_model_path
        self.dimension = dimension or self.settings.embedding_dimension
        self._model = None

    @property
    def model(self) -> SentenceTransformer:
        """懒加载模型"""
        if self._model is None:
            logger.info(f"加载Embedding模型: {self.model_name}")
            model_dir = Path(self.model_path)

            # 检查本地模型是否存在
            if model_dir.exists() and (model_dir / "config.json").exists():
                logger.info(f"从本地加载模型: {self.model_path}")
                self._model = SentenceTransformer(str(model_dir.resolve()))
            else:
                logger.info(f"本地模型不存在，从HuggingFace下载: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)

            logger.info(f"Embedding模型加载完成，维度: {self.dimension}")
        return self._model

    def encode(self, texts: List[str], normalize: bool = True) -> np.ndarray:
        """编码文本为向量"""
        if isinstance(texts, str):
            texts = [texts]

        embeddings = self.model.encode(
            texts,
            normalize_embeddings=normalize,
            convert_to_numpy=True,
            show_progress_bar=False
        )
        return embeddings

    async def aencode(self, texts: List[str], normalize: bool = True) -> np.ndarray:
        """异步编码"""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.encode, texts, normalize)

    def get_dimension(self) -> int:
        """获取向量维度"""
        return self.dimension


# 全局Embedding实例
embedding_model = EmbeddingModel()
