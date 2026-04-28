"""测试加班费检索"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.rag.knowledge_base import legal_kb
from src.rag.query_rewriter import query_rewriter


async def test_overtime_search():
    print("=" * 60)
    print(">> 测试：企业加班应该支付几倍工资")
    print("=" * 60)

    # 加载最新知识库
    processed_dir = Path(r"F:\26_01\项目\LawBot\src\rag\processed")
    dedup_files = sorted(processed_dir.glob("deduplicated_*.json"))
    latest = dedup_files[-1]

    import json
    with open(latest, "r", encoding="utf-8") as f:
        data = json.load(f)

    docs = []
    for item in data:
        docs.append({
            "content": item.get("content", ""),
            "metadata": {
                "title": item.get("title", ""),
                "source": item.get("source", ""),
                "article": item.get("article", ""),
                "domain": item.get("domain", ""),
                "doc_type": item.get("doc_type", ""),
                "keywords": item.get("keywords", [])
            }
        })

    legal_kb.index_legal_documents(docs)
    print(f">> 知识库加载完成: {len(docs)} 条\n")

    # 测试查询
    query = "企业加班应该支付几倍工资"

    # 1. 查询改写
    print(">> 1. 查询改写:")
    rewritten = await query_rewriter.rewrite(query)
    print(f"    原始查询: {query}")
    print(f"    改写后: {rewritten.get('rewritten_query', 'N/A')}")
    print(f"    意图: {rewritten.get('intent', 'N/A')}\n")

    # 2. 检索
    print(">> 2. 混合检索:")
    results = await legal_kb.retrieve(query, top_k=10)

    if not results:
        print("    [警告] 检索返回 0 条结果!")
    else:
        print(f"    检索到 {len(results)} 条结果:")
        for i, doc in enumerate(results[:5], 1):
            content = doc.get("content", "")[:100]
            score = doc.get("relevance_score", 0)
            print(f"    [{i}] 分数={score:.3f} | {doc.get('metadata', {}).get('source', '')} {doc.get('metadata', {}).get('article', '')}")
            print(f"        内容: {content}...")

    # 3. 相关性检查
    print("\n>> 3. 相关性检查 (阈值=0.15):")
    LOW_QUALITY_THRESHOLD = 0.15

    if not results:
        print("    无检索结果，跳过检查")
    else:
        max_score = max(doc.get("relevance_score", 0) for doc in results)
        relevant_count = sum(1 for doc in results if doc.get("relevance_score", 0) >= LOW_QUALITY_THRESHOLD)
        print(f"    最高相关度: {max_score:.3f}")
        print(f"    超过阈值({LOW_QUALITY_THRESHOLD})的数量: {relevant_count}")
        print(f"    相关性检查: {'通过' if relevant_count >= 1 and max_score >= LOW_QUALITY_THRESHOLD else '失败'}")

    # 4. 直接搜索关键词
    print("\n>> 4. 关键词直接搜索:")
    overtime_keywords = ["加班费", "加班工资", "150%", "200%", "300%", "延长工作时间"]
    for kw in overtime_keywords:
        count = sum(1 for doc in docs if kw in doc["content"])
        print(f"    '{kw}': {count} 条")


if __name__ == "__main__":
    asyncio.run(test_overtime_search())
