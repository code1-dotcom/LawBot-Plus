"""知识库上传服务 - 处理文件上传、去重、索引"""
import json
import hashlib
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict

from src.rag.knowledge_base import legal_kb
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class UploadResult:
    """上传结果"""
    success: bool
    total_records: int = 0
    new_records: int = 0
    duplicates: int = 0
    merged_records: int = 0
    message: str = ""
    error: Optional[str] = None


class KnowledgeBaseUploader:
    """知识库上传处理器"""

    def __init__(self):
        self.json_dir = Path(__file__).parent / "json"
        self.processed_dir = Path(__file__).parent / "processed"
        self.json_dir.mkdir(exist_ok=True)
        self.processed_dir.mkdir(exist_ok=True)

    async def process_upload(self, file_content: str, filename: str) -> UploadResult:
        """处理上传的文件

        Args:
            file_content: 文件内容 (JSON字符串)
            filename: 原始文件名

        Returns:
            UploadResult: 处理结果
        """
        try:
            # 1. 解析文件内容
            data = self._parse_file_content(file_content, filename)
            if not data:
                return UploadResult(
                    success=False,
                    error="文件格式错误，无法解析JSON内容"
                )

            # 2. 转换为标准格式
            documents = self._normalize_documents(data)
            if not documents:
                return UploadResult(
                    success=False,
                    error="未找到有效的法律条文数据"
                )

            logger.info(f"解析到 {len(documents)} 条法律条文")

            # 3. 加载现有文档数量用于统计
            existing_count = sum(1 for f in self.json_dir.glob("*.json"))

            # 4. 保存上传文件到 json 目录（去重脚本会从该目录加载所有文件）
            self._save_to_json_dir(documents, filename)

            # 5. 统计新文档（去重前）
            new_docs_count = len(documents)

            # 6. 运行完整去重流程（会合并所有json目录下的文件）
            self._run_full_dedup()

            # 7. 重新索引知识库
            latest_file = self._get_latest_processed_file()
            if latest_file:
                await self._reindex_knowledge_base(latest_file)

            # 8. 读取去重后的统计数据
            stats = {"total": new_docs_count, "new": new_docs_count, "duplicates": 0, "merged": 0}
            report_file = list(self.processed_dir.glob("dedup_report_*.json"))
            if report_file:
                latest_report = sorted(report_file)[-1]
                with open(latest_report, "r", encoding="utf-8") as f:
                    report_data = json.load(f)
                    stats["total"] = report_data.get("statistics", {}).get("after_dedup", new_docs_count)
                    stats["new"] = report_data.get("statistics", {}).get("duplicates_removed", 0)

            return UploadResult(
                success=True,
                total_records=stats["total"],
                new_records=new_docs_count,
                duplicates=stats.get("duplicates", 0),
                merged_records=stats.get("merged", 0),
                message=f"成功添加 {new_docs_count} 条法律条文，知识库已更新"
            )

        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            return UploadResult(success=False, error=f"JSON格式错误: {str(e)}")
        except Exception as e:
            logger.error(f"处理上传失败: {e}")
            return UploadResult(success=False, error=str(e))

    def _parse_file_content(self, content: str, filename: str) -> List[Dict]:
        """解析文件内容"""
        try:
            data = json.loads(content)

            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                if "data" in data:
                    return data["data"]
                elif "documents" in data:
                    return data["documents"]
                elif "records" in data:
                    return data["records"]
                else:
                    # 单个文档
                    return [data]
        except json.JSONDecodeError:
            pass

        return []

    def _normalize_documents(self, data: List[Dict]) -> List[Dict]:
        """标准化文档格式"""
        normalized = []
        for item in data:
            # 提取必要字段
            content = item.get("content") or item.get("text") or item.get("条款内容", "")
            title = item.get("title") or item.get("name") or item.get("法条名称", "")
            source = item.get("source") or item.get("法律名称", item.get("law", ""))
            article = item.get("article") or item.get("条款号", item.get("clause", ""))

            # 跳过空内容
            if not content or not article:
                continue

            # 规范化
            doc = {
                "title": self._clean_text(title),
                "content": self._clean_text(content),
                "source": self._clean_text(source),
                "article": self._clean_text(article),
                "domain": item.get("domain", "民事"),
                "doc_type": item.get("doc_type", "law"),
                "keywords": item.get("keywords", self._extract_keywords(content))
            }
            normalized.append(doc)

        return normalized

    def _clean_text(self, text: str) -> str:
        """清理文本"""
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _extract_keywords(self, content: str) -> List[str]:
        """提取关键词"""
        # 简单的关键词提取
        keywords = []
        patterns = [
            r'([\u4e00-\u9fa5]{2,4})(?:规定|应当|可以|不得|必须)',
            r'第(\d+)条',
            r'([\u4e00-\u9fa5]{2,4})责任',
            r'([\u4e00-\u9fa5]{2,4})义务',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, content)
            keywords.extend(matches[:3])
        return list(set(keywords))[:5]

    def _load_existing_documents(self) -> List[Dict]:
        """加载现有文档"""
        existing = []
        json_files = list(self.json_dir.glob("*.json"))
        for json_file in json_files:
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        existing.extend(data)
            except Exception as e:
                logger.warning(f"加载现有文档失败 {json_file.name}: {e}")
        return existing

    def _deduplicate_merge(self, existing: List[Dict], new_docs: List[Dict]) -> Tuple[List[Dict], Dict]:
        """去重合并"""
        stats = {"total": len(new_docs), "new": 0, "duplicates": 0, "merged": 0}

        # 构建现有文档的哈希集合
        existing_hashes = set()
        existing_keys = {}
        for doc in existing:
            key = self._compute_key(doc)
            existing_hashes.add(self._compute_hash(doc))
            existing_keys[key] = doc

        # 处理新文档
        merged_docs = list(existing)
        new_unique = []

        for doc in new_docs:
            key = self._compute_key(doc)
            doc_hash = self._compute_hash(doc)

            if key in existing_keys:
                # 已存在，检查是否需要合并
                stats["duplicates"] += 1
                stats["merged"] += 1
            else:
                # 新文档
                new_unique.append(doc)
                merged_docs.append(doc)
                stats["new"] += 1

        return merged_docs, stats

    def _compute_key(self, doc: Dict) -> str:
        """计算文档唯一键"""
        source = doc.get("source", "")
        article = doc.get("article", "")
        return f"{source}|{article}"

    def _compute_hash(self, doc: Dict) -> str:
        """计算内容哈希"""
        content = f"{doc.get('source', '')}|{doc.get('article', '')}|{doc.get('content', '')}"
        return hashlib.md5(content.encode()).hexdigest()

    def _save_to_json_dir(self, documents: List[Dict], filename: str):
        """保存到 json 目录"""
        # 清理文件名
        safe_name = re.sub(r'[^\w\u4e00-\u9fa5]', '_', filename)
        if safe_name.endswith('.json'):
            safe_name = safe_name[:-5]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.json_dir / f"uploaded_{safe_name}_{timestamp}.json"

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(documents, f, ensure_ascii=False, indent=2)

        logger.info(f"保存上传文件到: {output_file}")

    def _run_full_dedup(self):
        """运行完整去重流程"""
        try:
            from src.rag.deduplication import LegalDeduplicator

            deduplicator = LegalDeduplicator(input_dir=str(self.json_dir))
            deduplicator.run()

            logger.info("去重流程完成")
        except Exception as e:
            logger.error(f"去重流程失败: {e}")

    def _get_latest_processed_file(self) -> Optional[Path]:
        """获取最新的处理后文件"""
        processed_files = sorted(self.processed_dir.glob("deduplicated_*.json"))
        if processed_files:
            return processed_files[-1]
        return None

    async def _reindex_knowledge_base(self, file_path: Path):
        """重新索引知识库"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            documents = []
            for item in data:
                documents.append({
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

            legal_kb.index_legal_documents(documents)
            logger.info(f"知识库重新索引完成: {len(documents)} 条")

        except Exception as e:
            logger.error(f"重新索引失败: {e}")

    def get_knowledge_base_stats(self) -> Dict:
        """获取知识库统计信息"""
        stats = {
            "total_documents": 0,
            "source_count": defaultdict(int),
            "latest_file": None,
            "json_files_count": len(list(self.json_dir.glob("*.json")))
        }

        # 统计已处理的文档
        latest = self._get_latest_processed_file()
        if latest:
            try:
                with open(latest, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    stats["total_documents"] = len(data)
                    for doc in data:
                        source = doc.get("source", "未知")
                        stats["source_count"][source] += 1
                    stats["latest_file"] = latest.name
            except Exception as e:
                logger.error(f"读取统计信息失败: {e}")

        stats["source_count"] = dict(stats["source_count"])
        return stats


# 全局实例
knowledge_base_uploader = KnowledgeBaseUploader()
