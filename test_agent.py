"""测试 Agent 工作流"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.workflow import run_legal_consultation


async def load_knowledge_base():
    """加载知识库"""
    from src.rag.knowledge_base import legal_kb
    import json

    # 知识库文件路径
    kb_path = Path(r"F:\26_01\项目\LawBot\src\rag\processed")
    dedup_files = sorted(kb_path.glob("deduplicated_*.json"))

    print(f">> 查找目录: {kb_path}")
    print(f">> 找到文件: {[f.name for f in dedup_files]}")

    if dedup_files:
        latest = dedup_files[-1]
        print(f">> 加载知识库: {latest.name}")

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
        print(f">> 知识库加载完成: {len(docs)} 条")
        return True
    else:
        print(">> 警告：未找到知识库文件")
        return False


async def test_consultation():
    print("=" * 60)
    print(">> LawBot+ Agent Workflow Test")
    print("=" * 60)

    # 先加载知识库
    await load_knowledge_base()

    # 测试问题
    test_question = "民间借贷纠纷怎么处理？"

    print(f"\n>> 测试问题: {test_question}")
    print(">> 正在处理...\n")

    try:
        result = await run_legal_consultation(
            user_input=test_question,
            session_id="test-session-001"
        )

        print("=" * 60)
        print(">> 返回结果:")
        print("=" * 60)
        print(f"\n状态: needs_review={result.needs_review}, confidence={result.confidence}")
        print(f"\n答案:\n{result.answer}")
        print(f"\n来源数量: {len(result.sources)}")

        if result.reasoning_chain:
            print(f"\n推理链 ({len(result.reasoning_chain)} 步):")
            for i, step in enumerate(result.reasoning_chain[:10], 1):
                print(f"  {i}. {step[:150]}")

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_consultation())
