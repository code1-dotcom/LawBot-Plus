"""Planner Agent - 任务规划与意图识别"""
from langchain_core.prompts import ChatPromptTemplate

from src.agents.llm_client import llm_client
from src.agents.state import AgentState
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PlannerAgent:
    """规划Agent - 负责任务分解与意图识别"""
    
    SYSTEM_PROMPT = """你是一位专业的法律AI助手规划专家。你的职责是：

1. 理解用户的法律问题意图
2. 将复杂问题分解为可执行的子任务
3. 生成适合RAG检索的法言法语查询

## 任务类型识别
- 案由识别：民事/刑事/行政/执行等
- 法条检索：查找相关法律条文
- 风险评估：评估法律风险和后果
- 流程咨询：诉讼程序、时效等
- 文书生成：起诉状、答辩状等

## 输出格式
请按以下JSON格式输出：
{
    "intent": "主要意图类型",
    "subtasks": ["子任务1", "子任务2", ...],
    "rewritten_query": "改写后的法言法语检索式",
    "requires_calculation": true/false,
    "requires_templates": true/false
}
"""

    USER_PROMPT = """用户问题：{user_input}

请分析这个法律问题并输出规划结果。"""

    def __init__(self):
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT),
            ("human", self.USER_PROMPT)
        ])
    
    async def plan(self, state: AgentState) -> AgentState:
        """执行规划任务"""
        logger.info(f"[Planner] 开始规划任务: {state.user_input[:50]}...")
        
        # 敏感内容检查
        from src.agents.workflow import check_sensitive_content
        is_sensitive, reject_msg = check_sensitive_content(state.user_input)
        if is_sensitive:
            logger.info(f"[Planner] 敏感内容检测，拒绝回答")
            state.final_answer = reject_msg
            state.needs_review = False
            state.confidence_score = 0.0
            state.reasoning_chain.append("敏感内容检测：直接拒绝")
            return state
        
        try:
            # 构建消息
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": self.USER_PROMPT.format(user_input=state.user_input)}
            ]
            
            # 调用LLM
            response = await llm_client.ainvoke(messages)
            
            # 解析响应
            import json
            try:
                plan_result = json.loads(response)
                state.rewritten_query = plan_result.get("rewritten_query", state.user_input)
                state.reasoning_chain.append(f"规划完成: 意图={plan_result.get('intent')}")
                state.current_agent = "researcher"
                logger.info(f"[Planner] 规划完成，检索式: {state.rewritten_query}")
            except json.JSONDecodeError:
                # 如果解析失败，使用原始输入
                state.rewritten_query = state.user_input
                state.reasoning_chain.append("规划完成（使用原始查询）")
                state.current_agent = "researcher"
                logger.warning("[Planner] 规划结果解析失败，使用原始查询")
                
        except Exception as e:
            logger.error(f"[Planner] 规划失败: {e}")
            state.error = str(e)
            state.current_agent = "planner"  # 保持当前Agent
        
        return state


# 全局Planner实例
planner_agent = PlannerAgent()
