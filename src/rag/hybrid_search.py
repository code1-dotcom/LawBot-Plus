"""混合检索管道 - 向量检索 + BM25 + Reranker"""
from typing import List, Dict, Optional, Callable
import numpy as np

from src.rag.embedding import embedding_model
from src.rag.reranker import reranker_model
from src.rag.bm25_search import bm25_search
from src.config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class HybridSearchPipeline:
    """混合检索管道
    
    结合向量检索、BM25关键词检索与交叉编码器重排
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.embedding = embedding_model
        self.reranker = reranker_model
        self.bm25 = bm25_search
        
        # 索引状态
        self._indexed = False
        self._document_embeddings: Optional[np.ndarray] = None
        self._documents: List[dict] = []
    
    def index_documents(self, documents: List[dict]):
        """索引文档
        
        Args:
            documents: 文档列表，每项需包含:
                - content: 文本内容
                - metadata: 元数据（可选）
        """
        if not documents:
            logger.warning("索引空文档集")
            return
        
        self._documents = documents
        
        # 1. 构建BM25索引
        self.bm25.index(documents)
        
        # 2. 生成向量嵌入
        contents = [doc.get("content", "") for doc in documents]
        self._document_embeddings = self.embedding.encode(contents)
        
        self._indexed = True
        logger.info(f"文档索引完成: {len(documents)}篇")
    
    async def search(
        self,
        query: str,
        top_k: int = None,
        rerank: bool = True,
        vector_weight: float = 0.5,
        bm25_weight: float = 0.5,
        filter_func: Optional[Callable] = None
    ) -> tuple[List[dict], List[str]]:
        """混合检索

        Args:
            query: 查询文本
            top_k: 返回数量
            rerank: 是否重排
            vector_weight: 向量检索权重
            bm25_weight: BM25权重
            filter_func: 过滤函数

        Returns:
            Tuple of (检索结果列表，按相关性排序, 分词后的检索词列表)
        """
        top_k = top_k or self.settings.rag_top_k
        
        if not self._indexed:
            logger.warning("索引未构建，执行空检索")
            return []
        
        logger.info(f"执行混合检索: {query[:50]}...")

        # 1. 向量检索
        query_vector = self.embedding.encode(query)
        # 确保是一维向量
        if len(query_vector.shape) > 1:
            query_vector = query_vector[0]
        vector_scores = self._cosine_similarity(query_vector, self._document_embeddings)
        
        # 2. BM25检索
        bm25_scores_raw, tokenized_query = self.bm25.search(query, top_k * 2)
        bm25_scores = np.zeros(len(self._documents))
        for idx, score in bm25_scores_raw:
            bm25_scores[idx] = score
        
        # 归一化BM25分数
        if bm25_scores.max() > 0:
            bm25_scores = bm25_scores / bm25_scores.max()
        
        # 3. 分数融合
        combined_scores = vector_weight * vector_scores + bm25_weight * bm25_scores
        
        # 4. 获取Top-K候选
        top_indices = np.argsort(combined_scores)[::-1][:top_k * 2]
        
        # 5. 应用过滤
        if filter_func:
            top_indices = [
                idx for idx in top_indices 
                if filter_func(self._documents[idx])
            ][:top_k]
        
        # 6. 获取文档内容用于重排
        candidate_docs = [self._documents[idx] for idx in top_indices]
        candidate_texts = [doc.get("content", "") for doc in candidate_docs]
        
        # 7. 交叉编码器重排
        if rerank and candidate_texts:
            reranked = await self.reranker.arerank(query, candidate_texts, top_k)
            
            # 组装最终结果
            results = []
            for doc_idx, rerank_score in reranked:
                doc = candidate_docs[doc_idx]
                doc["hybrid_score"] = float(combined_scores[top_indices[doc_idx]])  # 保存原始混合分数
                doc["relevance_score"] = float(rerank_score)
                doc["vector_score"] = float(vector_scores[top_indices[doc_idx]])
                doc["bm25_score"] = float(bm25_scores[top_indices[doc_idx]])
                results.append(doc)
        else:
            # 不重排，直接按融合分数排序
            results = []
            for idx in top_indices[:top_k]:
                doc = self._documents[idx]
                doc["relevance_score"] = float(combined_scores[idx])
                doc["vector_score"] = float(vector_scores[idx])
                doc["bm25_score"] = float(bm25_scores[idx])
                results.append(doc)
        
        logger.info(f"检索完成，返回 {len(results)} 条结果")
        return results, tokenized_query
    
    def _cosine_similarity(
        self,
        query_vector: np.ndarray,
        doc_vectors: np.ndarray
    ) -> np.ndarray:
        """计算余弦相似度"""
        # 归一化
        query_norm = query_vector / (np.linalg.norm(query_vector) + 1e-8)
        doc_norms = doc_vectors / (np.linalg.norm(doc_vectors, axis=1, keepdims=True) + 1e-8)
        
        # 点积即余弦相似度
        return np.dot(doc_norms, query_norm)
    
    def add_documents(self, documents: List[dict]):
        """增量添加文档"""
        if not self._indexed:
            self.index_documents(documents)
            return
        
        # 重新索引（简化实现）
        all_docs = self._documents + documents
        self.index_documents(all_docs)
        logger.info(f"增量添加 {len(documents)} 篇文档")
    
    @property
    def document_count(self) -> int:
        """文档数量"""
        return len(self._documents)


# 全局混合检索管道
hybrid_search = HybridSearchPipeline()
