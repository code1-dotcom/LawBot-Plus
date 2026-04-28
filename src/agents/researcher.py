"""Researcher Agent - 法律知识检索"""
from typing import Optional
from langchain_core.prompts import ChatPromptTemplate

from src.agents.llm_client import llm_client
from src.agents.state import AgentState
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ResearcherAgent:
    """研究Agent - 负责法律知识检索"""
    
    SYSTEM_PROMPT = """你是一位专业的法律研究员。你的职责是：

1. 根据Planner提供的检索式，从法律知识库中检索相关内容
2. 评估检索结果的相关性和权威性
3. 整理检索到的法条、案例供后续分析使用

## 检索策略
- 优先检索法律法规原文
- 关注司法解释和指导性案例
- 注意法条时效性（现行有效/已废止）

## 输出格式
请输出：
1. 检索到的关键法条和依据
2. 每条依据的相关性评分（1-10）
3. 来源说明（法律名称、条款号、发布时间）
"""

    def __init__(self):
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT),
            ("human", "检索式: {query}\n\n请执行检索并整理结果。")
        ])
    
    async def research(self, state: AgentState) -> AgentState:
        """执行检索任务"""
        logger.info(f"[Researcher] 开始检索: {state.rewritten_query}")

        try:
            # 调用RAG知识库进行实际检索
            from src.rag.knowledge_base import legal_kb

            search_query = state.rewritten_query or state.user_input
            logger.info(f"[Researcher] 执行RAG检索: {search_query}")

            # 执行混合检索
            retrieved, tokenized_query = await legal_kb.retrieve(
                query=search_query,
                top_k=10,
                use_rewrite=False  # 已经由planner改写过了
            )
            # 保存分词结果到状态
            state.tokenized_query = tokenized_query

            # 转换格式
            real_docs = []
            for idx, doc in enumerate(retrieved):
                real_docs.append({
                    "id": idx + 1,
                    "title": doc.get("metadata", {}).get("title", ""),
                    "content": doc.get("content", ""),
                    "hybrid_score": float(doc.get("hybrid_score", 0.0)),  # 原始混合分数
                    "relevance_score": float(doc.get("relevance_score", 0.5)),
                    "source": doc.get("metadata", {}).get("source", ""),
                    "article": doc.get("metadata", {}).get("article", ""),
                    "domain": doc.get("metadata", {}).get("domain", ""),
                    "keywords": doc.get("metadata", {}).get("keywords", []),
                    "vector_score": doc.get("vector_score", 0),
                    "bm25_score": doc.get("bm25_score", 0)
                })

            state.retrieved_docs = real_docs
            state.reasoning_chain.append(f"检索完成，找到{len(real_docs)}条相关依据")

            if real_docs:
                top_doc = real_docs[0]
                state.reasoning_chain.append(f"最相关: {top_doc.get('source', '')} {top_doc.get('article', '')}")

            state.current_agent = "analyst"
            logger.info(f"[Researcher] 检索完成，找到{len(real_docs)}条结果")

        except Exception as e:
            logger.error(f"[Researcher] 检索失败: {e}")
            state.error = str(e)
            state.retrieved_docs = []
            state.current_agent = "researcher"

        return state
    
    async def rerank(self, state: AgentState) -> AgentState:
        """对检索结果进行重排"""
        logger.info("[Researcher] 开始重排...")

        try:
            from src.rag.reranker import reranker_model

            if state.retrieved_docs:
                query = state.rewritten_query or state.user_input
                doc_texts = [doc.get("content", "") for doc in state.retrieved_docs]

                reranked = await reranker_model.arerank(query, doc_texts, top_k=5)

                all_scores = [score for _, score in reranked]
                max_rerank_score = max(all_scores) if all_scores else 0.0

                logger.info(
                    "[Researcher] 重排: raw_rerank=%s, hybrid=%s",
                    all_scores[:3],
                    [doc.get("hybrid_score", 0) for doc in state.retrieved_docs[:3]]
                )

                if all(s < 0.05 for s in all_scores):
                    logger.warning(
                        "[Researcher] 所有 rerank 分数均 < 0.05，回退到 hybrid_score"
                    )
                    reranked_docs = [
                        {**doc, "rerank_score": doc.get("hybrid_score", 0.0)}
                        for doc in state.retrieved_docs[:5]
                    ]
                else:
                    max_possible = max(max_rerank_score, 0.5)

                    reranked_docs = []
                    for doc_idx, rerank_score in reranked:
                        doc = state.retrieved_docs[doc_idx].copy()
                        normalized_rerank = rerank_score / max_possible if max_possible > 0 else 0.0
                        hybrid = doc.get("hybrid_score", 0.0)
                        final_score = hybrid * 0.6 + normalized_rerank * 0.4
                        doc["rerank_score"] = final_score
                        reranked_docs.append(doc)
                        logger.info(
                            "[Researcher] 融合: rerank=%.3f norm=%.3f hybrid=%.3f final=%.3f",
                            rerank_score, normalized_rerank, hybrid, final_score
                        )

                state.reranked_docs = reranked_docs
                logger.info(
                    "[Researcher] reranked_docs 设置完成: count=%d, scores=%s",
                    len(reranked_docs),
                    [d.get("rerank_score", 0) for d in reranked_docs[:3]]
                )
                state.reasoning_chain.append("重排完成，保留Top %d条" % len(reranked_docs))

                logger.info("[Researcher] 重排完成，返回%d条", len(state.reranked_docs))
            else:
                state.reranked_docs = []
                logger.warning("[Researcher] retrieved_docs 为空，无法重排")

        except Exception as e:
            logger.error("[Researcher] 重排失败: %s", e)
            state.reranked_docs = state.retrieved_docs[:5] if state.retrieved_docs else []

        return state


# 全局Researcher实例
researcher_agent = ResearcherAgent()
