"""法律条文数据加载脚本 - 离线版（不依赖外部模型）"""
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import get_logger

logger = get_logger(__name__)


def load_processed_json(processed_dir: Path) -> list:
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


def main():
    print("=" * 60)
    print(">> LawBot+ Data Loader (Offline Mode)")
    print("=" * 60)
    
    json_dir = project_root / "src" / "rag" / "json"
    processed_dir = project_root / "src" / "rag" / "processed"
    
    # 加载数据
    documents = load_processed_json(processed_dir)
    
    if not documents:
        print("[ERROR] No documents loaded!")
        return
    
    # 保存到统一位置（用于后续处理）
    output_path = processed_dir / "knowledge_base.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(documents, f, ensure_ascii=False, indent=2)
    
    print(f"\n>> SUCCESS!")
    print(f"   Total documents: {len(documents)}")
    print(f"   Output: {output_path}")
    
    # 统计
    domain_count = {}
    for doc in documents:
        domain = doc.get("domain", "未知")
        domain_count[domain] = domain_count.get(domain, 0) + 1
    
    print("\n>> Domain Distribution:")
    for domain, count in sorted(domain_count.items(), key=lambda x: -x[1]):
        print(f"   {domain}: {count}")
    
    print("=" * 60)
    return documents


if __name__ == "__main__":
    main()
