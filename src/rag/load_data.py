"""法律条文数据加载脚本 - 完整版（加载模型+索引数据）"""
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.rag.hybrid_search import hybrid_search
from src.utils.logger import get_logger

logger = get_logger(__name__)


def load_json_files(processed_dir: Path) -> list:
    """加载已去重的JSON文件"""
    dedup_files = sorted(processed_dir.glob("deduplicated_*.json"))
    if not dedup_files:
        logger.warning("未找到去重后的文件")
        return []
    
    latest_dedup = dedup_files[-1]
    logger.info(f"加载文件: {latest_dedup.name}")
    
    with open(latest_dedup, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    logger.info(f"加载完成: {len(data)} 条法律条文")
    return data


def index_documents(documents: list) -> bool:
    """索引文档到向量库"""
    docs_for_index = []
    
    for item in documents:
        doc = {
            "content": item.get("content", ""),
            "metadata": {
                "title": item.get("title", ""),
                "source": item.get("source", ""),
                "article": item.get("article", ""),
                "domain": item.get("domain", ""),
                "doc_type": item.get("doc_type", ""),
                "keywords": item.get("keywords", [])
            }
        }
        docs_for_index.append(doc)
    
    # 索引文档
    hybrid_search.index_documents(docs_for_index)
    logger.info(f"索引完成: {len(docs_for_index)} 篇文档")
    
    return True


def main():
    print("=" * 60)
    print(">> LawBot+ Data Loader (Full Mode)")
    print("=" * 60)
    
    processed_dir = project_root / "src" / "rag" / "processed"
    
    # 加载数据
    documents = load_json_files(processed_dir)
    
    if not documents:
        print("[ERROR] No documents loaded!")
        return
    
    print(f"\n>> Indexing {len(documents)} documents...")
    print(">> Loading Embedding model...")
    
    # 索引文档（会自动加载模型）
    success = index_documents(documents)
    
    if success:
        print(f"\n>> SUCCESS! {len(documents)} documents indexed.")
        
        # 统计
        domain_count = {}
        for doc in documents:
            domain = doc.get("domain", "未知")
            domain_count[domain] = domain_count.get(domain, 0) + 1
        
        print("\n>> Domain Distribution:")
        for domain, count in sorted(domain_count.items(), key=lambda x: -x[1])[:10]:
            print(f"   {domain}: {count}")
    else:
        print("\n>> FAILED to index documents!")
    
    print("=" * 60)
    return documents


if __name__ == "__main__":
    main()
