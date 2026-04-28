"""Reranker模型封装 - BGE Reranker"""
from typing import List, Tuple
import numpy as np

from src.config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RerankerModel:
    """交叉编码器Reranker封装"""
    
    def __init__(
        self,
        model_name: str = None,
        model_path: str = None,
        top_k: int = None
    ):
        self.settings = get_settings()
        self.model_name = model_name or self.settings.reranker_model_name
        self.model_path = model_path or self.settings.reranker_model_path
        self.top_k = top_k or self.settings.rag_rerank_top_k
        self._model = None
    
    @property
    def model(self):
        """懒加载模型"""
        if self._model is None:
            logger.info(f"加载Reranker模型: {self.model_name}")
            try:
                from flagembedding import FlagReranker
                self._model = FlagReranker(str(self.model_path), use_cpu=True)
            except Exception as e:
                logger.warning(f"Reranker模型加载失败: {e}，将使用BM25排序")
                self._model = None
            logger.info("Reranker模型加载完成")
        return self._model
    
    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: int = None
    ) -> List[Tuple[int, float]]:
        """对文档进行重排，返回(doc_index, score)列表"""
        top_k = top_k or self.top_k
        
        if not documents:
            return []
        
        if self.model is None:
            # Reranker 不可用时，返回极低分数（表示"无真实语义相关性"）
            # 绝不能返回位置假分（1.0, 0.9...），否则会误导置信度计算
            return [(i, 0.01) for i in range(min(len(documents), top_k))]
        
        try:
            # FlagReranker使用句子对输入
            pairs = [[query, doc] for doc in documents]
            scores = self.model.compute_score(pairs, normalize=True)
            
            # 按分数降序排序
            doc_scores = list(enumerate(scores))
            doc_scores.sort(key=lambda x: x[1], reverse=True)
            
            return doc_scores[:top_k]
            
        except Exception as e:
            logger.error(f"Reranker计算失败: {e}")
            # 异常时返回极低分数，不返回虚假高分
            return [(i, 0.01) for i in range(len(documents))]
    
    async def arerank(
        self,
        query: str,
        documents: List[str],
        top_k: int = None
    ) -> List[Tuple[int, float]]:
        """异步重排"""
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(
            None, self.rerank, query, documents, top_k
        )


# 全局Reranker实例
reranker_model = RerankerModel()
