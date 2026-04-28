"""Memory Manager - 记忆管理模块"""
from typing import Optional
from src.agents.state import AgentState
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MemoryManager:
    """记忆管理器 - 负责短期会话与长期记忆"""
    
    def __init__(self):
        self.short_term_memory: dict = {}  # 简单内存存储，后续可接入Redis
        self.max_history = 10  # 最大历史记录数
    
    async def update_short_term(self, state: AgentState) -> AgentState:
        """更新短期记忆"""
        logger.info(f"[Memory] 更新短期记忆: session={state.session_id}")

        # 构建会话键
        session_key = f"session:{state.session_id}"

        # 新请求开始时，清理旧的历史记录，确保不同 session_id 的状态完全隔离
        existing_history = self.short_term_memory.get(session_key, [])

        # 如果是新会话的第一条消息，清空历史（防止跨 session 污染）
        if not existing_history:
            self.short_term_memory[session_key] = []

        # 获取当前会话历史（最多保留 max_history 条）
        history = self.short_term_memory.get(session_key, [])

        # 添加新记录
        history.append({
            "user_input": state.user_input,
            "analysis_result": state.analysis_result,
            "final_answer": state.final_answer,
            "timestamp": str(state.created_at)
        })

        # 限制历史长度
        if len(history) > self.max_history:
            history = history[-self.max_history:]

        self.short_term_memory[session_key] = history

        # 构建上下文摘要（仅包含当前会话的历史）
        if history:
            state.memory_context = {
                "summary": f"用户在此会话中问了{len(history)}个问题",
                "recent_topics": [h.get("user_input", "")[:50] for h in history[-3:]]
            }

        return state
    
    async def update_long_term(self, state: AgentState) -> AgentState:
        """更新长期记忆（待接入向量数据库）"""
        logger.info(f"[Memory] 更新长期记忆...")
        
        # TODO: 实现长期记忆向量存储
        # 1. 生成关键信息的embedding
        # 2. 存储到PostgreSQL/pgvector
        # 3. 支持相似度检索
        
        state.reasoning_chain.append("长期记忆更新完成")
        return state
    
    async def retrieve_context(self, state: AgentState) -> AgentState:
        """检索相关记忆上下文"""
        logger.info(f"[Memory] 检索记忆上下文...")
        
        # TODO: 实现向量相似度检索
        # 目前返回空上下文
        
        return state


# 全局Memory Manager实例
memory_manager = MemoryManager()
