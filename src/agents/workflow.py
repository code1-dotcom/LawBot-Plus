"""LangGraph工作流编排 - 核心状态机"""
import uuid
import json
from typing import Literal, Union

from langgraph.graph import StateGraph, END

from src.agents.state import AgentState, AgentResponse
from src.agents.planner import planner_agent
from src.agents.researcher import researcher_agent
from src.agents.analyst import analyst_agent
from src.agents.reviewer import reviewer_agent
from src.agents.memory_manager import memory_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)


# 敏感话题列表（直接拒绝）
SENSITIVE_TOPICS = [
    # 毒品相关
    "海洛因", "冰毒", "可卡因", "大麻", "摇头丸", "麻古", "K粉", "吗啡", "杜冷丁",
    "毒品", "制毒", "贩毒", "吸毒", "种毒", "走私毒品", "运输毒品",
    # 犯罪相关
    "杀人", "故意杀人", "过失致人死亡", "故意伤害致人死亡",
    "抢劫", "抢夺", "盗窃", "诈骗", "贪污", "受贿", "行贿",
    "绑架", "拐卖", "拐骗", "组织卖淫", "强迫卖淫",
    # 政治敏感
    "分裂国家", "颠覆国家政权", "煽动颠覆", "泄密", "间谍",
    "台独", "藏独", "疆独", "港独",
    # 暴力恐怖
    "恐怖主义", "爆炸", "纵火", "投毒",
    "黑社会", "组织黑社会", "黑恶势力",
]

# 低质量检索阈值（rerank_score 归一化到 [0,1]）
# 单文档最高分低于 SEMANTIC_MIN_SCORE 则视为语义不相关
LOW_QUALITY_THRESHOLD = 0.30
# 语义相关最低门槛：top-1 doc 的 rerank_score 必须达到此值
SEMANTIC_MIN_SCORE = 0.40


def check_sensitive_content(user_input: str) -> tuple[bool, str]:
    """检查敏感内容"""
    user_input_lower = user_input.lower()
    for topic in SENSITIVE_TOPICS:
        if topic.lower() in user_input_lower:
            return True, f"您的问题涉及敏感话题「{topic}」，LawBot+ 专注于提供正当法律咨询服务，暂不回答此类问题。如有需要，建议您通过正当法律途径寻求专业律师帮助。"
    return False, ""


def check_relevance(state: AgentState) -> bool:
    """检查检索结果是否与问题语义相关。

    两层检查：
    1. 最高 rerank_score 必须 >= SEMANTIC_MIN_SCORE（防止"1+1"匹配到随机法条也过检）
    2. 至少有一条文档的 rerank_score >= LOW_QUALITY_THRESHOLD
    """
    if not state.reranked_docs:
        return False

    # 检查最高相关度（核心：top-1 必须有意义）
    max_score = 0
    for doc in state.reranked_docs:
        score = doc.get("rerank_score", doc.get("score", 0))
        max_score = max(max_score, score)

    # 语义相关最低门槛：top-1 必须达到
    if max_score < SEMANTIC_MIN_SCORE:
        logger.info(f"[RelevanceCheck] top-1 rerank_score={max_score:.3f} < {SEMANTIC_MIN_SCORE}，语义不相关")
        return False

    # 数量门槛：至少有一条高于阈值
    relevant_count = sum(
        1 for doc in state.reranked_docs
        if doc.get("rerank_score", doc.get("score", 0)) >= LOW_QUALITY_THRESHOLD
    )

    return relevant_count >= 1


def state_to_dict(state: AgentState) -> dict:
    """将AgentState转换为字典"""
    return state.model_dump()


async def planner_node(state: AgentState) -> dict:
    """规划节点"""
    result = await planner_agent.plan(state)
    return state_to_dict(result)


async def researcher_node(state: AgentState) -> AgentState:
    """检索节点"""
    return await researcher_agent.research(state)


async def reranker_node(state: AgentState) -> AgentState:
    """重排节点"""
    return await researcher_agent.rerank(state)


async def tool_decision_node(state: AgentState) -> AgentState:
    """工具决策节点 - 判断是否需要调用工具"""
    logger.info("[ToolDecision] 检查是否需要调用工具...")
    
    from src.agents.tool_agent import determine_tool_use, execute_tool_call, synthesize_with_tools
    
    needs_tool, tool_name, params = await determine_tool_use(state)
    
    if needs_tool and tool_name:
        logger.info(f"[ToolDecision] 需要调用工具: {tool_name}, 参数: {params}")
        state.needs_tool = True
        
        # 执行工具调用
        result = await execute_tool_call(tool_name, params)
        state.tool_results.append({
            "tool": tool_name,
            "params": params,
            "result": result
        })
        
        # 记录到推理链
        state.reasoning_chain.append(f"=== 工具调用 ===")
        state.reasoning_chain.append(f"工具: {tool_name}")
        state.reasoning_chain.append(f"参数: {json.dumps(params, ensure_ascii=False)}")
        
        if result.get("success"):
            state.reasoning_chain.append(f"结果: {json.dumps(result.get('result', {}), ensure_ascii=False)}")
            # 使用工具结果合成最终回答
            state.final_answer = await synthesize_with_tools(state)
        else:
            state.reasoning_chain.append(f"错误: {result.get('error', '未知错误')}")
    else:
        logger.info("[ToolDecision] 不需要调用工具")
        state.needs_tool = False
    
    return state


async def relevance_check_node(state: AgentState) -> AgentState:
    """相关性检查节点"""
    logger.info("[RelevanceCheck] 检查检索结果相关性...")

    # 调试：打印 reranked_docs 状态
    rd = state.reranked_docs
    scores = [d.get("rerank_score", 0) for d in rd] if rd else []
    logger.info("[RelevanceCheck] reranked_docs=%s, scores=%s", len(rd) if rd else 0, scores[:5])

    # ---- 第一步：检测非法律问题（无论 reranked_docs 是否为空） ----
    NON_LAW_KEYWORDS = [
        "天气", "气温", "下雨", "晴天", "温度", "湿度", "风力",
        "新闻", "热点", "热搜", "今日头条",
        "娱乐", "明星", "电影", "音乐", "歌曲", "电视剧",
        "体育", "足球", "篮球", "比赛", "比分",
        "美食", "菜谱", "做法", "做饭", "吃什么",
        "旅游", "景点", "攻略", "酒店", "机票",
        "购物", "价格", "优惠", "打折", "京东", "淘宝",
        "股票", "基金", "期货", "汇率", "比特币", "加密货币",
        "闲聊", "你好", "在吗", "聊天", "今天", "昨天", "明天",
        "生日", "礼物", "祝福",
    ]
    user_input_lower = state.user_input.lower()
    non_law_hits = [kw for kw in NON_LAW_KEYWORDS if kw in user_input_lower]
    if non_law_hits:
        logger.info(f"[RelevanceCheck] 检测到非法律问题关键词: {non_law_hits}")
        state.relevance_check_passed = False
        state.final_answer = (
            "您好，我是 LawBot+ 法律咨询助手，专注于法律相关问题的分析和解答。\n\n"
            f"您的问题「{state.user_input}」似乎与法律领域不太相关，"
            "我的知识库中无法找到相关的法律条文来回答您的问题。\n\n"
            "如果您有法律方面的问题（如合同纠纷、劳动争议、婚姻财产、交通事故等），"
            "欢迎继续向我咨询，我会尽力为您提供参考意见。"
        )
        state.needs_review = False
        state.confidence_score = 0.0
        state.reasoning_chain.append(f"非法律问题检测: {non_law_hits}，置信度设为0.0")
        return state

    # ---- 第二步：检索结果为空 ----
    if not state.reranked_docs or len(state.reranked_docs) == 0:
        logger.warning("[RelevanceCheck] 检索结果为空，跳过分析")
        state.relevance_check_passed = False
        state.final_answer = (
            "抱歉，我的知识库中暂时没有找到与您问题相关的法律条文或案例，无法为您提供准确的法律分析。\n\n"
            "建议您：\n"
            "1. 换个方式描述您的问题\n"
            "2. 咨询更专业的律师\n"
            "3. 如涉及具体案件，建议通过正当法律途径寻求帮助"
        )
        state.needs_review = False
        state.confidence_score = 0.0
        state.reasoning_chain.append("=== 检索结果为空 ===")
        state.reasoning_chain.append("知识库中未找到相关法条，无法生成分析结果")
        return state

    # ---- 第三步：检索质量语义检查 ----
    if check_relevance(state):
        logger.info("[RelevanceCheck] 检索结果相关，继续分析")
        state.relevance_check_passed = True
    else:
        logger.info("[RelevanceCheck] 检索结果不相关，返回无法回答")
        state.relevance_check_passed = False
        state.final_answer = (
            "抱歉，我的知识库中暂时没有找到与您问题相关的法律条文或案例，无法为您提供准确的法律分析。\n\n"
            "建议您：\n"
            "1. 换个方式描述您的问题\n"
            "2. 咨询更专业的律师\n"
            "3. 如涉及具体案件，建议通过正当法律途径寻求帮助"
        )
        state.needs_review = False
        state.confidence_score = 0.0

    return state


async def analyst_node(state: AgentState) -> AgentState:
    """分析节点"""
    return await analyst_agent.analyze(state)


async def reviewer_node(state: AgentState) -> AgentState:
    """审核节点"""
    return await reviewer_agent.review(state)


async def memory_node(state: AgentState) -> AgentState:
    """记忆节点"""
    return await memory_manager.update_short_term(state)


def hitl_node(state: AgentState) -> AgentState:
    """HITL节点 - 暂停等待人工审核"""
    logger.info("[HITL] 触发人工审核，暂停工作流...")
    # 实际暂停由外部服务处理
    return state


async def finalize_node(state: AgentState) -> AgentState:
    """最终答案生成节点"""
    logger.info("[Finalize] 生成最终答案...")
    
    # 如果已经有最终答案（如敏感内容拒绝或知识库无法回答），直接返回
    if state.final_answer:
        logger.info("[Finalize] 使用预设答案（敏感拒绝/知识库无答案）")
        state.reasoning_chain.append("=== 直接回答 ===")
        state.reasoning_chain.append(state.final_answer)
        return state
    
    # 使用 LLM 生成简洁的总结性回复
    from src.agents.llm_client import llm_client
    
    prompt = f"""你是一个专业的法律咨询助手。请根据以下信息，生成一个简洁、专业的法律咨询回复。

## 用户问题
{state.user_input}

## 详细分析过程（仅供参考）
{state.analysis_result or "未进行详细分析"}

## 风险等级
{state.risk_level or "low"}

## 检索到的法律依据
{chr(10).join([f"- {doc.get('content', '')}" for doc in state.reranked_docs]) if state.reranked_docs else "无相关法律依据"}

请生成一个简洁的回复（200-500字），包括：
1. 一句话总结结论
2. 2-3条核心要点或建议
3. 相关法条名称（如有）

回复要简洁专业，直接回答问题，不要重复分析过程。

回复格式使用Markdown。"""
    
    try:
        final_answer = await llm_client.client.ainvoke([
            {"role": "system", "content": "你是一个专业的法律咨询助手。回复要简洁有力。"},
            {"role": "user", "content": prompt}
        ])
        if hasattr(final_answer, 'content'):
            state.final_answer = final_answer.content
        else:
            state.final_answer = str(final_answer)
    except Exception as e:
        logger.error(f"[Finalize] 生成答案失败: {e}")
        state.final_answer = f"## 结论\n\n{state.analysis_result[:500]}..." if state.analysis_result else "暂无相关法律依据可供参考。"
    
    # 保存完整分析过程到 reasoning_chain 中，供前端展示"思考过程"
    state.reasoning_chain.append("=== 详细分析过程 ===")
    state.reasoning_chain.append(state.analysis_result or "")
    state.reasoning_chain.append("=== 法律依据 ===")
    for doc in state.reranked_docs:
        state.reasoning_chain.append(f"- {doc.get('title', '')}: {doc.get('content', '')[:100]}...")
    
    state.sources = [
        {
            "id": doc.get("id") or f"source-{idx}",
            "title": doc.get("title", ""),
            "content": doc.get("content", ""),
            "source": doc.get("source", ""),
            "article": doc.get("article", "")
        }
        for idx, doc in enumerate(state.reranked_docs)
    ]

    # ===== RAG 评估埋点（无侵入，不阻塞主流程）=====
    try:
        from src.tasks.rag_eval import log_rag_eval_data
        log_rag_eval_data.delay(
            query=state.user_input,
            reranked_docs=state.reranked_docs,
            final_answer=state.final_answer,
            retrieved_docs=state.retrieved_docs,
        )
    except Exception as hitl_exc:
        logger.warning(f"[RAGEval] 埋点失败，不影响主流程: {hitl_exc}")

    return state


def should_relevance_check(state: AgentState) -> Literal["analyst", "no_relevance"]:
    """判断是否相关性检查"""
    # 如果已经有最终答案（如敏感内容拒绝），直接结束
    if state.final_answer:
        return "no_relevance"
    # 如果调用了工具并得到结果，跳过法律分析
    if state.needs_tool and state.tool_results:
        last_result = state.tool_results[-1]
        if last_result.get("result", {}).get("success"):
            return "no_relevance"
    if check_relevance(state):
        return "analyst"
    return "no_relevance"


def should_continue(state: AgentState) -> Literal["hitl", "finalize"]:
    """判断是否需要HITL"""
    if state.needs_review:
        return "hitl"
    return "finalize"


def should_skip_to_final(state: AgentState) -> Literal["researcher", "memory"]:
    """判断是否跳过检索"""
    # 如果已经有最终答案（如敏感内容拒绝），直接跳到记忆
    if state.final_answer:
        return "memory"
    return "researcher"


def create_workflow() -> StateGraph:
    """创建LangGraph工作流"""
    
    # 创建状态图
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("planner", planner_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("reranker", reranker_node)
    workflow.add_node("tool_decision", tool_decision_node)
    workflow.add_node("relevance_check", relevance_check_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("memory", memory_node)
    workflow.add_node("hitl", hitl_node)
    workflow.add_node("finalize", finalize_node)
    
    # 设置入口
    workflow.set_entry_point("planner")
    
    # planner -> 条件边：敏感内容跳到memory，否则继续researcher
    workflow.add_conditional_edges(
        "planner",
        should_skip_to_final,
        {
            "researcher": "researcher",
            "memory": "memory"
        }
    )
    
    workflow.add_edge("researcher", "reranker")
    workflow.add_edge("reranker", "tool_decision")
    
    # 工具决策后 -> 直接检查是否有最终答案
    def after_tool_decision(state: AgentState) -> str:
        # 如果工具调用成功并生成了最终答案，直接跳到memory
        if state.final_answer and state.needs_tool:
            logger.info("[ToolDecision] 工具已生成答案，跳过检索分析")
            return "memory"
        return "relevance_check"
    
    workflow.add_conditional_edges(
        "tool_decision",
        after_tool_decision,
        {"memory": "memory", "relevance_check": "relevance_check"}
    )
    
    # 相关性检查 -> analyst 或 memory
    workflow.add_conditional_edges(
        "relevance_check",
        should_relevance_check,
        {
            "analyst": "analyst",
            "no_relevance": "memory"
        }
    )
    
    workflow.add_edge("analyst", "reviewer")
    workflow.add_conditional_edges(
        "reviewer",
        should_continue,
        {
            "hitl": "hitl",
            "finalize": "memory"
        }
    )
    workflow.add_edge("hitl", "memory")  # HITL后继续到记忆
    workflow.add_edge("memory", "finalize")
    workflow.add_edge("finalize", END)
    
    return workflow


# 创建工作流实例
lawbot_workflow = create_workflow()

# 编译工作流（不使用 checkpointer，每次请求状态完全隔离）
compiled_workflow = lawbot_workflow.compile()


async def run_legal_consultation(
    user_input: str,
    session_id: str = None,
    task_id: str = None
) -> AgentResponse:
    """运行法律咨询工作流"""
    
    # 生成ID
    session_id = session_id or str(uuid.uuid4())
    task_id = task_id or str(uuid.uuid4())
    
    logger.info(f"开始法律咨询: task_id={task_id}, session={session_id}")
    
    # 初始化状态
    initial_state = AgentState(
        session_id=session_id,
        user_input=user_input,
        task_id=task_id
    )
    
    # 运行工作流
    config = {"configurable": {"thread_id": session_id}}
    
    try:
        # 使用 ainvoke 获取完整最终状态
        final_state = await compiled_workflow.ainvoke(initial_state, config)
        
        # final_state 是最终状态字典
        return AgentResponse(
            answer=final_state.get("final_answer", "处理完成"),
            sources=final_state.get("sources", []),
            confidence=final_state.get("confidence_score", 0.0),
            needs_review=final_state.get("needs_review", False),
            reasoning_chain=final_state.get("reasoning_chain", []),
            extra_data={
                "task_id": task_id,
                "session_id": session_id,
                "risk_level": final_state.get("risk_level", "unknown")
            },
            rewritten_query=final_state.get("rewritten_query") or None,
            tokenized_query=final_state.get("tokenized_query") or [],
        )
        
    except Exception as e:
        logger.error(f"工作流执行失败: {e}")
        raise


# 导出
__all__ = [
    "compiled_workflow",
    "run_legal_consultation",
    "create_workflow",
    "AgentState"
]
