"""MCP工具服务器 - 标准化外部能力网关"""
from typing import List, Dict, Optional, Any
from fastmcp import FastMCP

from src.utils.logger import get_logger

logger = get_logger(__name__)

# 创建FastMCP实例
mcp_server = FastMCP("LawBot-Legal-Tools")


@mcp_server.tool()
async def legal_rag_search(
    query: str,
    top_k: int = 5,
    domain: Optional[str] = None
) -> List[Dict[str, Any]]:
    """法律RAG检索工具
    
    Args:
        query: 检索查询
        top_k: 返回数量
        domain: 法律领域过滤
        
    Returns:
        检索结果列表
    """
    from src.rag.knowledge_base import legal_kb
    
    logger.info(f"[MCP] legal_rag_search: {query[:50]}...")
    
    results = await legal_kb.retrieve(
        query=query,
        top_k=top_k,
        domain_filter=domain
    )
    
    return results


@mcp_server.tool()
async def calculate_statute_of_limitations(
    case_type: str,
    event_date: str,
    claim_date: Optional[str] = None
) -> Dict[str, Any]:
    """诉讼时效计算器
    
    Args:
        case_type: 案件类型 (民间借贷/人身损害/合同纠纷等)
        event_date: 事件发生日期 (YYYY-MM-DD)
        claim_date: 主张权利日期，默认当前日期
        
    Returns:
        时效计算结果
    """
    from datetime import datetime, timedelta
    
    logger.info(f"[MCP] 计算诉讼时效: {case_type}")
    
    # 诉讼时效表（年）
    statute_map = {
        "民间借贷": 3,
        "人身损害": 3,
        "合同纠纷": 3,
        "建设工程": 3,
        "物业服务": 3,
        "离婚纠纷": 3,
        "继承纠纷": 3,
        "知识产权": 3,
        "产品质量": 2,
        "短期时效": 1,
    }
    
    case_type = case_type or "合同纠纷"
    years = statute_map.get(case_type, 3)
    
    event_dt = datetime.strptime(event_date, "%Y-%m-%d")
    claim_dt = datetime.strptime(claim_date, "%Y-%m-%d") if claim_date else datetime.now()
    
    deadline = event_dt + timedelta(days=years * 365)
    
    # 判断是否超过时效
    is_expired = claim_dt > deadline
    days_remaining = (deadline - claim_dt).days
    
    result = {
        "case_type": case_type,
        "statute_years": years,
        "event_date": event_date,
        "deadline": deadline.strftime("%Y-%m-%d"),
        "is_expired": is_expired,
        "days_remaining": days_remaining,
        "advice": "已超过诉讼时效" if is_expired else f"剩余{days_remaining}天"
    }
    
    logger.info(f"[MCP] 时效计算完成: {result['advice']}")
    return result


@mcp_server.tool()
async def calculate_compensation(
    case_type: str,
    damages: Dict[str, float]
) -> Dict[str, Any]:
    """赔偿计算器
    
    Args:
        case_type: 案件类型
        damages: 损失明细
        
    Returns:
        赔偿计算结果
    """
    logger.info(f"[MCP] 计算赔偿: {case_type}")
    
    # 基础计算逻辑
    total = sum(damages.values())
    
    # 责任比例（简化）
    liability_factor = 1.0
    
    if case_type == "交通事故":
        # 交强险限额
        liability_factor = 0.8
    elif case_type == "医疗损害":
        liability_factor = 0.7
    elif case_type == "产品质量":
        liability_factor = 0.9
    
    final_amount = total * liability_factor
    
    result = {
        "case_type": case_type,
        "damages_breakdown": damages,
        "subtotal": total,
        "liability_factor": liability_factor,
        "final_compensation": round(final_amount, 2),
        "currency": "人民币(元)"
    }
    
    logger.info(f"[MCP] 赔偿计算完成: {final_amount}")
    return result


@mcp_server.tool()
async def generate_legal_document(
    doc_type: str,
    params: Dict[str, Any]
) -> str:
    """法律文书生成工具
    
    Args:
        doc_type: 文书类型 (起诉状/答辩状/上诉状/申请书)
        params: 生成参数
        
    Returns:
        生成的文书内容
    """
    from src.agents.llm_client import analysis_llm
    
    logger.info(f"[MCP] 生成法律文书: {doc_type}")
    
    templates = {
        "起诉状": """民事起诉状

原告：{plaintiff}，{identity}
被告：{defendant}，{identity}
诉讼请求：
{claims}

事实与理由：
{facts}

此致
{court}

具状人：{plaintiff}
{date}
""",
        "答辩状": """民事答辩状

答辩人：{respondent}，{identity}
因{plaintiff}诉{case_name}一案，答辩如下：

一、关于{issue1}的答辩：
{response1}

二、关于{issue2}的答辩：
{response2}

此致
{court}

答辩人：{respondent}
{date}
""",
    }
    
    template = templates.get(doc_type, templates["起诉状"])
    
    try:
        # 使用LLM增强文书内容
        messages = [
            {"role": "system", "content": "你是一位专业的法律文书起草人。请根据提供的信息生成规范的法律文书。"},
            {"role": "user", "content": f"文书类型: {doc_type}\n参数: {params}\n\n请生成完整的法律文书内容。"}
        ]
        
        enhanced = await analysis_llm.ainvoke(messages)
        logger.info(f"[MCP] 文书生成完成")
        return enhanced
        
    except Exception as e:
        logger.error(f"[MCP] 文书生成失败: {e}")
        # 返回基础模板
        return template.format(**params)


@mcp_server.tool()
def search_legal_reference(
    keyword: str,
    law_type: Optional[str] = None
) -> List[Dict[str, str]]:
    """法律法规检索（模拟）
    
    Args:
        keyword: 关键词
        law_type: 法律类型
        
    Returns:
        相关法规列表
    """
    logger.info(f"[MCP] 检索法规: {keyword}")
    
    # 模拟数据
    references = [
        {
            "title": "中华人民共和国民法典",
            "article": "第1165条",
            "content": "行为人因过错侵害他人民事权益造成损害的，应当承担侵权责任。",
            "effective_date": "2021-01-01",
            "status": "现行有效"
        },
        {
            "title": "最高人民法院关于审理人身损害赔偿案件适用法律若干问题的解释",
            "article": "第17条",
            "content": "受害人遭受人身损害，可以请求赔偿医疗费、误工费、护理费等合理费用。",
            "effective_date": "2022-05-01",
            "status": "现行有效"
        }
    ]
    
    return references


def run_mcp_server():
    """启动MCP服务器"""
    logger.info("启动MCP工具服务器...")
    mcp_server.run()
