"""Analyst Agent - 法律分析与推理"""
from langchain_core.prompts import ChatPromptTemplate

from src.agents.llm_client import analysis_llm
from src.agents.state import AgentState
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AnalystAgent:
    """分析Agent - 负责法律逻辑推理与结论生成"""
    
    SYSTEM_PROMPT = """你是一位经验丰富的法律分析师。你的职责是：

1. 结合检索到的法律依据，进行严谨的法律逻辑推理
2. 分析问题的法律性质、构成要件、责任划分
3. 评估各方权利义务关系
4. 给出初步的法律意见和风险提示

## 推理原则
- 以法律条文为依据，避免主观臆断
- 区分法律事实和法律观点
- 明确不确定性范围
- 考虑多种可能性

## 输出格式
请输出：
1. 法律分析过程（推理链）
2. 初步结论
3. 法律依据列表
4. 风险提示（如有）
"""

    USER_PROMPT = """用户问题：{user_input}

检索到的法律依据：
{documents}

长期记忆上下文：
{memory_context}

请进行法律分析。"""

    def __init__(self):
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT),
            ("human", self.USER_PROMPT)
        ])
    
    async def analyze(self, state: AgentState) -> AgentState:
        """执行分析任务"""
        logger.info("[Analyst] 开始法律分析...")

        # 防御性检查：检索结果为空时禁止生成回答，防止复用旧状态
        if not state.reranked_docs or len(state.reranked_docs) == 0:
            logger.warning("[Analyst] RAG检索结果为空，无法生成回答")
            state.analysis_result = "抱歉，当前知识库中暂未找到与您问题相关的法律依据，无法进行法律分析。"
            state.reasoning_chain.append("=== 检索结果为空 ===")
            state.reasoning_chain.append("知识库中未找到相关法条，无法生成分析结果")
            state.current_agent = "reviewer"
            return state

        try:
            # 构建文档上下文
            docs_context = "\n\n".join([
                f"[{i+1}] {doc.get('title', '未知')} - {doc.get('article', '')}\n"
                f"内容: {doc.get('content', '')}\n"
                f"相关性: {doc.get('relevance_score', 0)}"
                for i, doc in enumerate(state.reranked_docs)
            ])
            
            # 构建记忆上下文
            memory_context = state.memory_context.get("summary", "无历史记忆")
            
            # 构建消息
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": self.USER_PROMPT.format(
                    user_input=state.user_input,
                    documents=docs_context,
                    memory_context=memory_context
                )}
            ]
            
            # 调用LLM进行推理分析
            response = await analysis_llm.ainvoke(messages)
            
            state.analysis_result = response
            state.reasoning_chain.append("法律分析完成")
            state.current_agent = "reviewer"
            
            logger.info("[Analyst] 分析完成")
            
        except Exception as e:
            logger.error(f"[Analyst] 分析失败: {e}")
            state.error = str(e)
            state.current_agent = "analyst"
        
        return state


# 全局Analyst实例
analyst_agent = AnalystAgent()
