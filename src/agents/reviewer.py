"""Reviewer Agent - AI审核与风险评估"""

from src.agents.state import AgentState
from src.config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ReviewerAgent:
    """审核Agent - 负责基于检索指标计算置信度与风险评估"""

    def __init__(self):
        self.settings = get_settings()
    
    async def review(self, state: AgentState) -> AgentState:
        """执行审核任务（基于检索指标计算置信度，不依赖 LLM 主观评分）"""
        logger.info("[Reviewer] 开始审核，基于检索指标计算置信度...")

        # ---- 早退出：检索结果为空 ----
        if not state.reranked_docs:
            logger.info("[Reviewer] 检索结果为空，置信度=0.0")
            state.confidence_score = 0.0
            state.risk_level = "low"
            state.needs_review = False
            state.reasoning_chain.append("检索结果为空，置信度=0.0")
            state.current_agent = "memory"
            return state

        # ---- 数学计算置信度（基于 rerank_score，不依赖 LLM 主观评分） ----
        rerank_scores = [doc.get("rerank_score", doc.get("score", 0)) for doc in state.reranked_docs]
        avg_score = sum(rerank_scores) / len(rerank_scores)
        max_score = max(rerank_scores)

        # 基础分 = 加权平均（avg 权重 0.6，max 权重 0.4）
        base = avg_score * 0.6 + max_score * 0.4

        # 文档数量奖励：1-3 条 +0.05，4-5 条 +0.10
        count_bonus = min(len(state.reranked_docs) / 5, 1.0) * 0.10

        # 答案内容惩罚：提及"无法回答"、无具体法条则降分
        analysis = state.analysis_result or ""
        no_answer_phrases = [
            "无法回答", "无法提供", "无法找到", "暂无", "没有找到",
            "无法进行法律分析", "知识库中暂未找到",
        ]
        has_answer_content = not any(p in analysis for p in no_answer_phrases) and len(analysis) >= 50
        content_penalty = 0.0 if has_answer_content else -0.20

        raw_confidence = base + count_bonus + content_penalty
        state.confidence_score = max(0.0, min(1.0, round(raw_confidence, 3)))

        # ---- 风险等级评估（基于检索质量，非 LLM） ----
        if state.confidence_score >= 0.75:
            state.risk_level = "low"
        elif state.confidence_score >= 0.50:
            state.risk_level = "medium"
        else:
            state.risk_level = "high"

        # ---- HITL 触发条件 ----
        state.needs_review = (
            state.confidence_score < self.settings.hitl_confidence_threshold
            or state.risk_level in ("high", "critical")
        )

        logger.info(
            f"[Reviewer] 审核完成: avg={avg_score:.3f} max={max_score:.3f} "
            f"docs={len(state.reranked_docs)} score={state.confidence_score:.3f} "
            f"risk={state.risk_level} hitl={state.needs_review}"
        )
        state.reasoning_chain.append(
            f"审核通过: 检索质量={state.confidence_score:.3f}, "
            f"风险={state.risk_level}, 文档数={len(state.reranked_docs)}"
        )

        state.current_agent = "memory" if not state.needs_review else "reviewer"
        return state
    
# 全局Reviewer实例
reviewer_agent = ReviewerAgent()
