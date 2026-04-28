"""BM25关键词检索"""
import re
from typing import List, Tuple

import jieba
from rank_bm25 import BM25Okapi

from src.config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _build_legal_dictionary() -> List[str]:
    """构建法律领域自定义词典，供初始化时加载到 jieba。"""
    return [
        "无过错责任",
        "抵押权",
        "追及效力",
        "连带责任",
        "善意取得",
        "举证责任",
        "加班费",
        "劳动合同",
        "违约责任",
        "诉讼时效",
    ]


class BM25Search:
    """BM25全文检索"""

    def __init__(self, k1: float | None = None, b: float | None = None) -> None:
        """初始化 BM25 检索器。

        Args:
            k1: BM25 词频饱和参数，若为 None 则从 settings 读取。
            b: BM25 文档长度归一化参数，若为 None 则从 settings 读取。
        """
        settings = get_settings()
        self.k1 = k1 if k1 is not None else settings.bm25_k1
        self.b = b if b is not None else settings.bm25_b
        self.bm25: BM25Okapi | None = None
        self.documents: List[dict] = []
        self.corpus: List[str] = []

        for word in _build_legal_dictionary():
            jieba.add_word(word)
    
    def index(self, documents: List[dict]):
        """构建索引
        
        Args:
            documents: 文档列表，每项需包含content字段
        """
        self.documents = documents
        self.corpus = [doc.get("content", "") for doc in documents]
        
        if self.corpus:
            tokenized_corpus = [self._tokenize(text) for text in self.corpus]
            self.bm25 = BM25Okapi(tokenized_corpus)
            logger.info(f"BM25索引构建完成，文档数: {len(documents)}")
        else:
            logger.warning("BM25索引构建失败：空文档集")
    
    def _tokenize(self, text: str) -> List[str]:
        """使用 jieba 精确模式对中文法律文本进行分词。

        Args:
            text: 待分词的原始文本。

        Returns:
            清洗后的词语列表，过滤了标点、纯数字及长度小于 2 的词条。
        """
        tokens = jieba.lcut(text, cut_all=False)
        cleaned: List[str] = []
        for token in tokens:
            stripped = token.strip()
            if not stripped:
                continue
            if stripped.isdigit():
                continue
            if len(stripped) < 2:
                continue
            cleaned.append(stripped)
        return cleaned
    
    def search(
        self,
        query: str,
        top_k: int = 10
    ) -> Tuple[List[Tuple[int, float]], List[str]]:
        """搜索

        Returns:
            Tuple of (List of (doc_index, score), tokenized_query)
        """
        if self.bm25 is None:
            logger.warning("BM25索引未构建")
            return [], []

        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        # 返回排序后的(doc_index, score)
        doc_scores = list(enumerate(scores))
        doc_scores.sort(key=lambda x: x[1], reverse=True)

        return doc_scores[:top_k], tokenized_query
    
    def search_with_filter(
        self,
        query: str,
        top_k: int = 10,
        filter_func=None
    ) -> Tuple[List[Tuple[int, float]], List[str]]:
        """带过滤的搜索

        Returns:
            Tuple of (List of (doc_index, score), tokenized_query)
        """
        results, tokenized_query = self.search(query, top_k * 2)  # 获取更多结果用于过滤

        if filter_func:
            filtered = []
            for idx, score in results:
                doc = self.documents[idx]
                if filter_func(doc):
                    filtered.append((idx, score))
                if len(filtered) >= top_k:
                    break
            return filtered, tokenized_query

        return results[:top_k], tokenized_query


# 全局BM25实例
bm25_search = BM25Search()
