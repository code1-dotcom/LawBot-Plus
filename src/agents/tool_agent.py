"""Tool Agent - 工具调用决策"""
import re
import json
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate

from src.agents.llm_client import llm_client
from src.agents.state import AgentState
from src.agents.tools import tool_manager, ToolRegistry
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ToolAgent:
    """工具Agent - 决定是否需要调用工具"""
    
    SYSTEM_PROMPT = """你是一个智能助手，负责判断用户问题是否需要调用外部工具。

## 可用工具
{available_tools}

## 判断规则
1. 如果问题涉及实时信息（天气、新闻、股票、汇率等），需要调用工具
2. 如果问题只涉及法律条文、案例分析，不需要调用工具
3. 如果问题与法律无关但需要实时信息，调用对应工具
4. 如果不确定，最好调用工具

## 输出格式
请输出JSON格式：
{{
    "needs_tool": true/false,
    "tool_name": "工具名称（如需调用）",
    "parameters": {{"参数名": "参数值"}},
    "reason": "判断理由"
}}

注意：
- 只选择一个最合适的工具
- parameters要包含工具所需的所有参数
- 如果不需要工具，tool_name和parameters可为空"""


class ToolCaller:
    """工具调用器"""
    
    SYSTEM_PROMPT = """你是一个工具调用助手。根据用户问题和工具结果，生成最终回答。

## 用户问题
{user_input}

## 工具调用结果
{tool_results}

请根据工具结果，用自然语言回答用户问题。如果工具调用失败，也要合理回复。"""


async def extract_location(text: str) -> Optional[str]:
    """从文本中提取位置信息"""
    # 常见位置模式
    patterns = [
        r'([^市县区]+)市?([^区县城]+)区?',
        r'([^市县]+)市',
        r'([^县]+)县',
        r'在(.+?)(?:的|天气|怎么样|如何)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            # 返回最具体的匹配
            for g in reversed(match.groups()):
                if g:
                    return g.strip()
    
    return None


async def determine_tool_use(state: AgentState) -> tuple[bool, Optional[str], dict]:
    """判断是否需要使用工具"""
    
    # 获取已启用的工具
    enabled_tools = await tool_manager.get_enabled_tools()
    if not enabled_tools:
        return False, None, {}
    
    # 构建工具描述
    tools_desc = []
    tool_map = {}
    for tool in enabled_tools:
        desc = f"- {tool.name}: {tool.description}"
        if tool.tool_type == "weather":
            desc += " (参数: location - 城市名称)"
        tools_desc.append(desc)
        tool_map[tool.name] = tool
    
    if not tools_desc:
        return False, None, {}
    
    system_prompt = f"""你是一个智能助手，负责判断用户问题是否需要调用外部工具。

## 可用工具
{chr(10).join(tools_desc)}

## 判断规则
1. 如果问题涉及实时信息（天气、新闻、股票、汇率等），需要调用工具
2. 如果问题只涉及法律条文、案例分析，不需要调用工具
3. 如果问题与法律无关但需要实时信息，调用对应工具
4. 如果不确定，最好调用工具

## 输出格式
请输出JSON格式：
{{
    "needs_tool": true/false,
    "tool_name": "工具名称（如需调用）",
    "parameters": {{"参数名": "参数值"}},
    "reason": "判断理由"
}}

注意：
- 只选择一个最合适的工具
- parameters要包含工具所需的所有参数
- 如果不需要工具，tool_name和parameters可为空"""
    
    # 调用LLM判断
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"用户问题：{state.user_input}"}
    ]
    
    try:
        response = await llm_client.ainvoke(messages)
        result = json.loads(response)
        
        needs_tool = result.get("needs_tool", False)
        tool_name = result.get("tool_name")
        parameters = result.get("parameters", {})
        
        # 特殊处理：天气工具的位置参数
        if tool_name and tool_name in tool_map:
            tool = tool_map[tool_name]
            if tool.tool_type == "weather" and "location" not in parameters:
                location = await extract_location(state.user_input)
                if location:
                    parameters["location"] = location
        
        return needs_tool, tool_name, parameters
        
    except Exception as e:
        logger.error(f"判断工具使用失败: {e}")
        return False, None, {}


async def execute_tool_call(tool_name: str, parameters: dict) -> dict:
    """执行工具调用"""
    from src.agents.tools import tool_manager
    
    # 查找工具
    tools = await tool_manager.list_tools()
    tool = None
    for t in tools:
        if t.name == tool_name and t.enabled:
            tool = t
            break
    
    if not tool:
        return {"success": False, "error": f"未找到工具: {tool_name}"}
    
    # 执行工具
    result = await ToolRegistry.execute_tool(tool, parameters)
    return result


async def synthesize_with_tools(state: AgentState) -> str:
    """使用工具结果合成回答"""
    
    # 构建工具结果描述
    results_text = []
    for tr in state.tool_results:
        if tr.get("success"):
            result = tr.get("result", {})
            if isinstance(result, dict):
                for k, v in result.items():
                    results_text.append(f"- {k}: {v}")
        else:
            results_text.append(f"- 错误: {tr.get('error', '未知错误')}")
    
    if not results_text:
        return state.final_answer or "暂无相关信息"
    
    # 调用LLM生成回答
    prompt = f"用户问题：{state.user_input}\n\n工具结果：\n" + "\n".join(results_text)
    
    messages = [
        {"role": "system", "content": """你是一个智能助手，根据工具查询结果回答用户问题。
请用自然、简洁的语言回答。如果结果中有穿衣建议等相关内容，也要一并包含。"""},
        {"role": "user", "content": prompt}
    ]
    
    try:
        response = await llm_client.ainvoke(messages)
        return response
    except Exception as e:
        logger.error(f"合成回答失败: {e}")
        return "\n".join(results_text)


# 全局实例
tool_agent = ToolAgent()
tool_caller = ToolCaller()
