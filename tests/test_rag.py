"""RAG模块测试"""
import pytest
from src.rag.hybrid_search import HybridSearchPipeline
from src.rag.embedding import EmbeddingModel


class TestRAG:
    """测试RAG检索"""
    
    @pytest.fixture
    def sample_docs(self):
        return [
            {
                "content": "民法典第一千一百六十五条：行为人因过错侵害他人民事权益造成损害的，应当承担侵权责任。",
                "metadata": {"domain": "民事", "source": "民法典"}
            },
            {
                "content": "最高人民法院关于审理人身损害赔偿案件适用法律若干问题的解释第十七条：受害人遭受人身损害，可以请求赔偿医疗费、误工费等合理费用。",
                "metadata": {"domain": "民事", "source": "司法解释"}
            },
            {
                "content": "民事诉讼法第一百一十九条规定，起诉必须符合下列条件：（一）原告是与本案有直接利害关系的公民、法人和其他组织；",
                "metadata": {"domain": "程序", "source": "民事诉讼法"}
            }
        ]
    
    def test_bm25_search(self, sample_docs):
        """测试BM25检索"""
        from src.rag.bm25_search import BM25Search
        
        bm25 = BM25Search()
        bm25.index(sample_docs)
        
        results = bm25.search("侵权责任", top_k=2)
        
        assert len(results) <= 2
        assert all(isinstance(idx, int) and isinstance(score, float) for idx, score in results)
    
    def test_embedding_model(self):
        """测试Embedding模型"""
        # 跳过实际模型测试（需要下载模型）
        pytest.skip("需要下载Embedding模型")
    
    def test_hybrid_search_pipeline(self, sample_docs):
        """测试混合检索管道"""
        pipeline = HybridSearchPipeline()
        pipeline.index_documents(sample_docs)
        
        assert pipeline.document_count == 3
