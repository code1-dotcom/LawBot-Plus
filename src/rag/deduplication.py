"""
企业级法律条文去重脚本 - 方案二：双重保障去重

功能：
1. 第一层：精确去重 - 基于 (source + article) 唯一标识
2. 第二层：智能合并 - 相同条款不同表述时合并保留最完整版本
3. 第三层：质量检查 - 法条覆盖率分析、缺失条款报告

使用方式：
    python -m src.rag.deduplication
"""

import json
import re
import hashlib
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime
import argparse


@dataclass
class DeduplicationReport:
    """去重报告"""
    total_records: int = 0
    after_dedup: int = 0
    duplicates_removed: int = 0
    merged_records: int = 0
    quality_issues: List[str] = field(default_factory=list)
    missing_articles: Dict[str, List[str]] = field(default_factory=dict)
    coverage_rate: Dict[str, float] = field(default_factory=dict)
    processing_time: float = 0.0


@dataclass
class LegalDocument:
    """法律文档数据结构"""
    title: str
    content: str
    source: str
    article: str
    domain: str = "民事"
    doc_type: str = "law"
    keywords: List[str] = field(default_factory=list)
    _hash: str = ""

    @classmethod
    def from_dict(cls, data: Dict) -> "LegalDocument":
        """从字典创建"""
        return cls(
            title=data.get("title", ""),
            content=data.get("content", ""),
            source=data.get("source", ""),
            article=data.get("article", ""),
            domain=data.get("domain", "民事"),
            doc_type=data.get("doc_type", "law"),
            keywords=data.get("keywords", [])
        )

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "title": self.title,
            "content": self.content,
            "source": self.source,
            "article": self.article,
            "domain": self.domain,
            "doc_type": self.doc_type,
            "keywords": self.keywords
        }

    def compute_hash(self) -> str:
        """计算内容哈希"""
        content_str = f"{self.source}|{self.article}|{self.content}"
        return hashlib.md5(content_str.encode()).hexdigest()

    @property
    def unique_key(self) -> str:
        """唯一标识键"""
        return f"{self.source}|{self.article}"

    def normalize_content(self) -> str:
        """规范化内容"""
        content = self.content
        # 移除多余空格
        content = re.sub(r'\s+', ' ', content)
        # 移除特殊字符
        content = content.strip()
        return content


class LegalDeduplicator:
    """企业级法律条文去重器"""

    # 优先级：法律原文 > 司法解释 > 行政法规
    SOURCE_PRIORITY = {
        "law": 1,
        "interpretation": 2,
        "regulation": 3,
        "default": 4
    }

    def __init__(self, input_dir: str = None):
        self.input_dir = Path(input_dir) if input_dir else Path(__file__).parent / "json"
        self.output_dir = self.input_dir.parent / "processed"
        self.output_dir.mkdir(exist_ok=True)

        self.documents: List[LegalDocument] = []
        self.report = DeduplicationReport()

    def load_documents(self) -> int:
        """加载所有JSON文件"""
        json_files = sorted(self.input_dir.glob("*.json"))
        
        for json_file in json_files:
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                if isinstance(data, list):
                    for item in data:
                        doc = LegalDocument.from_dict(item)
                        if doc.content and doc.article:  # 跳过空内容
                            self.documents.append(doc)
                elif isinstance(data, dict) and "data" in data:
                    for item in data["data"]:
                        doc = LegalDocument.from_dict(item)
                        if doc.content and doc.article:
                            self.documents.append(doc)
                            
            except json.JSONDecodeError as e:
                print(f"[WARN] JSON parse error {json_file.name}: {e}")
            except Exception as e:
                print(f"[WARN] Load file failed {json_file.name}: {e}")

        self.report.total_records = len(self.documents)
        print(f"[LOAD] Loaded {len(self.documents)} legal documents")
        return len(self.documents)

    def layer1_exact_deduplication(self) -> int:
        """第一层：精确去重"""
        seen_keys: Set[str] = set()
        seen_hashes: Set[str] = set()
        unique_docs: List[LegalDocument] = []
        duplicates = 0

        for doc in self.documents:
            key = doc.unique_key
            doc_hash = doc.compute_hash()
            
            # 检查是否重复
            if key in seen_keys or doc_hash in seen_hashes:
                duplicates += 1
                continue
            
            seen_keys.add(key)
            seen_hashes.add(doc_hash)
            unique_docs.append(doc)

        self.documents = unique_docs
        self.report.duplicates_removed = duplicates
        print(f"[DEDUP-L1] Exact dedup: removed {duplicates} duplicates, remaining {len(self.documents)}")
        return duplicates

    def layer2_smart_merge(self) -> int:
        """第二层：智能合并"""
        # 按 article 分组
        article_groups: Dict[str, List[LegalDocument]] = defaultdict(list)
        for doc in self.documents:
            # 提取纯数字条款号用于分组
            article_num = self._extract_article_number(doc.article)
            if article_num:
                key = f"{doc.source}|{article_num}"
                article_groups[key].append(doc)

        merged_docs: List[LegalDocument] = []
        merged_count = 0

        for key, docs in article_groups.items():
            if len(docs) == 1:
                merged_docs.append(docs[0])
            else:
                # 多条相同条款，智能合并
                merged = self._merge_documents(docs)
                merged_docs.append(merged)
                merged_count += 1

        self.documents = merged_docs
        self.report.merged_records = merged_count
        print(f"[DEDUP-L2] Smart merge: merged {merged_count} groups, remaining {len(self.documents)}")
        return merged_count

    def _extract_article_number(self, article: str) -> Optional[str]:
        """提取条款号"""
        # 匹配第XXX条 格式
        match = re.search(r'第(\d+[条款项])', article)
        if match:
            return match.group(1)
        return None

    def _merge_documents(self, docs: List[LegalDocument]) -> LegalDocument:
        """合并多条相同条款"""
        # 按来源优先级排序
        docs_sorted = sorted(
            docs,
            key=lambda x: (self.SOURCE_PRIORITY.get(x.doc_type, 99), -len(x.content))
        )
        
        # 保留最完整、内容最长的版本
        best = docs_sorted[0]
        
        # 合并关键词
        all_keywords: Set[str] = set()
        for doc in docs:
            all_keywords.update(doc.keywords)
        
        best.keywords = list(all_keywords)[:10]  # 限制关键词数量
        return best

    def layer3_quality_check(self) -> DeduplicationReport:
        """第三层：质量检查"""
        report = self.report

        # 1. 检测法条编号格式
        invalid_articles = []
        for doc in self.documents:
            if not re.match(r'第[\d一二三四五六七八九十百]+[条款项章节节]', doc.article):
                invalid_articles.append((doc.article, doc.source))
        
        if invalid_articles:
            report.quality_issues.append(f"Found {len(invalid_articles)} articles with invalid format")

        # 2. Coverage analysis
        coverage = self._analyze_coverage()
        report.coverage_rate = coverage

        # 3. Missing articles detection
        missing = self._detect_missing_articles()
        report.missing_articles = missing

        # 4. Short content check
        short_content = [d for d in self.documents if len(d.content) < 20]
        if short_content:
            report.quality_issues.append(f"Found {len(short_content)} articles with short content")

        print(f"[DEDUP-L3] Quality check completed:")
        print(f"   - Coverage: {len(coverage)} laws")
        for law, rate in coverage.items():
            print(f"     * {law}: {rate:.1f}%")
        
        if missing:
            print(f"   - Missing gaps: {sum(len(v) for v in missing.values())} ranges")
        
        return report

    def _analyze_coverage(self) -> Dict[str, float]:
        """分析各法律覆盖率"""
        # 定义预期条款数量（简化版，完整需要维护完整法律条款清单）
        expected_counts = {
            "中华人民共和国民法典": 1260,
            "中华人民共和国劳动法": 107,
            "中华人民共和国劳动合同法": 89,
            "中华人民共和国公司法": 218,
            "中华人民共和国消费者权益保护法": 69,
            "中华人民共和国道路交通安全法": 115,
            "中华人民共和国刑法": 452,
            "中华人民共和国刑事诉讼法": 127,
            "中华人民共和国民事诉讼法": 112,
        }

        # 按法律分组统计
        law_counts: Dict[str, int] = defaultdict(int)
        for doc in self.documents:
            law_counts[doc.source] += 1

        coverage = {}
        for law, expected in expected_counts.items():
            actual = law_counts.get(law, 0)
            coverage[law] = min(100.0, (actual / expected) * 100) if expected > 0 else 0.0

        return coverage

    def _detect_missing_articles(self) -> Dict[str, List[str]]:
        """检测可能的缺失条款"""
        missing = {}
        
        # 按法律分组
        law_articles: Dict[str, Set[str]] = defaultdict(set)
        for doc in self.documents:
            law_articles[doc.source].add(doc.article)

        # 检测民法典连续条款中的间隔（简化检测）
        minguo_articles = law_articles.get("中华人民共和国民法典", set())
        if minguo_articles:
            article_nums = []
            for art in minguo_articles:
                match = re.search(r'第(\d+)条', art)
                if match:
                    article_nums.append(int(match.group(1)))
            
            article_nums.sort()
            
            # 检测缺失区间（假设条款号连续）
            gaps = []
            for i in range(len(article_nums) - 1):
                diff = article_nums[i + 1] - article_nums[i]
                if diff > 10:  # 超过10条的间隔可能是缺失
                    gaps.append(f"{article_nums[i]}-{article_nums[i+1]}")
            
            if gaps:
                missing["中华人民共和国民法典"] = gaps

        return missing

    def save_results(self, filename: str = None) -> str:
        """保存去重后的结果"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"deduplicated_{timestamp}.json"

        output_path = self.output_dir / filename
        
        # 转换为字典列表
        result = [doc.to_dict() for doc in self.documents]
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        self.report.after_dedup = len(result)
        print(f"[SAVE] Saved deduplicated results to: {output_path}")
        return str(output_path)

    def save_report(self, filename: str = None) -> str:
        """保存去重报告"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"dedup_report_{timestamp}.json"

        output_path = self.output_dir / filename
        
        report_data = {
            "generated_at": datetime.now().isoformat(),
            "statistics": {
                "total_records": self.report.total_records,
                "after_dedup": self.report.after_dedup,
                "duplicates_removed": self.report.duplicates_removed,
                "merged_records": self.report.merged_records,
                "dedup_rate": f"{(self.report.duplicates_removed / self.report.total_records * 100):.2f}%" if self.report.total_records > 0 else "0%",
            },
            "quality_issues": self.report.quality_issues,
            "coverage_rate": self.report.coverage_rate,
            "missing_articles": self.report.missing_articles,
            "processing_time_seconds": self.report.processing_time
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        print(f"[SAVE] Saved dedup report to: {output_path}")
        return str(output_path)

    def run(self) -> Tuple[List[LegalDocument], DeduplicationReport]:
        """运行完整去重流程"""
        import time
        start_time = time.time()

        print("=" * 60)
        print(">> Enterprise Legal Document Deduplication System - Plan 2")
        print("=" * 60)

        # Step 1: Load data
        print("\n>> Step 1: Loading data...")
        self.load_documents()

        # Step 2: Exact deduplication
        print("\n>> Step 2: Exact deduplication...")
        self.layer1_exact_deduplication()

        # Step 3: Smart merge
        print("\n>> Step 3: Smart merge...")
        self.layer2_smart_merge()

        # Step 4: Quality check
        print("\n>> Step 4: Quality check...")
        self.layer3_quality_check()

        # Step 5: Save results
        print("\n>> Step 5: Saving results...")
        self.save_results()
        self.save_report()

        # 统计
        self.report.processing_time = time.time() - start_time

        print("\n" + "=" * 60)
        print(">> DEDUP COMPLETED!")
        print(f"   Original records: {self.report.total_records}")
        print(f"   After dedup: {self.report.after_dedup}")
        print(f"   Duplicates removed: {self.report.duplicates_removed}")
        print(f"   Merged groups: {self.report.merged_records}")
        print(f"   Dedup rate: {(self.report.duplicates_removed / self.report.total_records * 100):.2f}%" if self.report.total_records > 0 else "0%")
        print(f"   Processing time: {self.report.processing_time:.2f}s")
        print("=" * 60)

        return self.documents, self.report


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description="法律条文去重工具")
    parser.add_argument("--input", "-i", default=None, help="输入目录路径")
    parser.add_argument("--output", "-o", default=None, help="输出文件名")
    args = parser.parse_args()

    # 运行去重
    deduplicator = LegalDeduplicator(input_dir=args.input)
    documents, report = deduplicator.run()

    return documents, report


if __name__ == "__main__":
    main()
