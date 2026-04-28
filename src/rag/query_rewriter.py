"""查询改写器 - 将用户问题转化为法言法语"""
from typing import Dict
from src.agents.llm_client import llm_client
from src.utils.logger import get_logger

logger = get_logger(__name__)


class QueryRewriter:
    """查询改写器 - 使用LLM将自然语言问题转化为检索式"""
    
    SYSTEM_PROMPT = """你是一位专业的法律检索专家。你的任务是将用户的法律问题改写成适合检索的查询式。

## 改写原则
1. 使用法言法语而非口语化表达
2. 提取核心法律概念和术语
3. 补充相关法律名称和条款
4. 分解复杂问题为多个检索点

## 示例
- 用户问题: 朋友借我钱不还怎么办？
  改写: 民间借贷纠纷 逾期不还款 诉讼时效 起诉流程

- 用户问题: 离婚后孩子抚养费怎么算？
  改写: 子女抚养费 计算标准 离婚后抚养义务 最高人民法院司法解释

## 输出格式
请输出JSON格式：
{
    "rewritten_query": "改写后的检索式",
    "key_terms": ["关键词1", "关键词2"],
    "legal_basis": ["可能的法律依据"],
    "query_type": "case_retrieval/law_search/procedure_query"
}
"""
    
    async def rewrite(self, query: str) -> Dict:
        """改写查询"""
        logger.info(f"查询改写: {query[:50]}...")
        
        try:
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": f"用户问题: {query}\n\n请改写为检索式。"}
            ]
            
            response = await llm_client.ainvoke(messages)
            
            # 解析JSON响应
            import json
            try:
                result = json.loads(response)
            except json.JSONDecodeError:
                # 降级处理
                result = {
                    "rewritten_query": query,
                    "key_terms": [],
                    "legal_basis": [],
                    "query_type": "general"
                }
            
            return result
            
        except Exception as e:
            logger.error(f"查询改写失败: {e}")
            return {
                "rewritten_query": query,
                "key_terms": [],
                "legal_basis": [],
                "query_type": "general"
            }


# 全局查询改写器
query_rewriter = QueryRewriter()
