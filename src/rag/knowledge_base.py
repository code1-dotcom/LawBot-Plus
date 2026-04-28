"""法律知识库 - RAG检索入口"""
from typing import List, Dict, Optional
from src.rag.hybrid_search import hybrid_search
from src.rag.query_rewriter import query_rewriter
from src.utils.logger import get_logger

logger = get_logger(__name__)


class LegalKnowledgeBase:
    """法律知识库检索接口"""
    
    def __init__(self):
        self.search_pipeline = hybrid_search
        self.query_rewriter = query_rewriter
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        domain_filter: Optional[str] = None,
        use_rewrite: bool = True
    ) -> tuple[List[Dict], List[str]]:
        """检索法律知识

        Args:
            query: 用户问题
            top_k: 返回数量
            domain_filter: 领域过滤（民事/刑事/行政）
            use_rewrite: 是否使用查询改写

        Returns:
            Tuple of (相关法律文档列表, 分词后的检索词列表)
        """
        # 查询改写
        tokenized_query = []
        if use_rewrite:
            rewritten = await self.query_rewriter.rewrite(query)
            search_query = rewritten.get("rewritten_query", query)
            logger.info(f"查询改写: {query} -> {search_query}")
        else:
            search_query = query
        
        # 过滤函数
        filter_func = None
        if domain_filter:
            def filter_func(doc):
                return doc.get("metadata", {}).get("domain") == domain_filter
            logger.info(f"应用领域过滤: {domain_filter}")
        
        # 执行检索
        results, tokenized_query = await self.search_pipeline.search(
            query=search_query,
            top_k=top_k,
            filter_func=filter_func
        )

        return results, tokenized_query
    
    def index_legal_documents(self, documents: List[Dict]):
        """索引法律文档"""
        self.search_pipeline.index_documents(documents)
        logger.info(f"法律知识库索引完成: {len(documents)}篇")
    
    def add_legal_document(self, document: Dict):
        """添加单个法律文档"""
        self.search_pipeline.add_documents([document])
        logger.info(f"添加文档: {document.get('title', 'unknown')}")


# 全局知识库实例
legal_kb = LegalKnowledgeBase()
