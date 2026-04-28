"""知识库上传 API 路由"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
import json

from src.rag.upload_service import knowledge_base_uploader
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/knowledge", tags=["知识库管理"])


class UploadResponse(BaseModel):
    """上传响应"""
    success: bool
    message: str
    total_records: int = 0
    new_records: int = 0
    duplicates: int = 0
    merged_records: int = 0
    error: Optional[str] = None


class KnowledgeStatsResponse(BaseModel):
    """知识库统计响应"""
    total_documents: int
    source_count: Dict[str, int]
    latest_file: Optional[str]
    json_files_count: int


class BatchUploadRequest(BaseModel):
    """批量上传请求"""
    documents: List[Dict] = Field(..., description="法律文档列表")
    source_name: Optional[str] = Field(None, description="来源名称，如：劳动法")


@router.post("/upload", response_model=UploadResponse)
async def upload_knowledge_file(
    file: UploadFile = File(..., description="JSON格式的法律条文文件")
):
    """上传知识库文件

    支持格式：
    - 单个文档：{"title": "...", "content": "...", "article": "第X条", "source": "法律名称"}
    - 文档列表：[{...}, {...}]
    - 标准格式：{"data": [{...}]}
    """
    logger.info(f"收到上传请求: {file.filename}")

    # 检查文件类型
    if not file.filename.endswith('.json'):
        raise HTTPException(
            status_code=400,
            detail="只支持 JSON 格式文件"
        )

    # 读取文件内容
    try:
        content = await file.read()
        file_content = content.decode('utf-8')
    except Exception as e:
        logger.error(f"读取文件失败: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"读取文件失败: {str(e)}"
        )

    # 处理上传
    result = await knowledge_base_uploader.process_upload(file_content, file.filename)

    if not result.success:
        raise HTTPException(
            status_code=500,
            detail=result.error
        )

    logger.info(f"上传处理完成: {result.new_records} 条新数据")

    return UploadResponse(
        success=True,
        message=result.message,
        total_records=result.total_records,
        new_records=result.new_records,
        duplicates=result.duplicates,
        merged_records=result.merged_records
    )


@router.post("/batch", response_model=UploadResponse)
async def batch_upload_knowledge(
    request: BatchUploadRequest
):
    """批量上传知识文档（JSON请求体方式）

    适用于前端直接发送文档数据
    """
    logger.info(f"收到批量上传请求: {len(request.documents)} 条文档")

    # 转换为 JSON 字符串
    file_content = json.dumps(request.documents, ensure_ascii=False)
    filename = f"batch_{request.source_name or 'documents'}.json"

    # 处理上传
    result = await knowledge_base_uploader.process_upload(file_content, filename)

    if not result.success:
        raise HTTPException(
            status_code=500,
            detail=result.error
        )

    return UploadResponse(
        success=True,
        message=result.message,
        total_records=result.total_records,
        new_records=result.new_records,
        duplicates=result.duplicates,
        merged_records=result.merged_records
    )


@router.get("/stats", response_model=KnowledgeStatsResponse)
async def get_knowledge_stats():
    """获取知识库统计信息"""
    stats = knowledge_base_uploader.get_knowledge_base_stats()
    return KnowledgeStatsResponse(**stats)


@router.post("/reindex")
async def reindex_knowledge_base():
    """手动触发知识库重新索引"""
    try:
        from src.rag.knowledge_base import legal_kb
        import json
        from pathlib import Path

        processed_dir = Path(__file__).parent.parent / "rag" / "processed"
        dedup_files = sorted(processed_dir.glob("deduplicated_*.json"))

        if not dedup_files:
            raise HTTPException(
                status_code=404,
                detail="未找到已处理的知识库文件"
            )

        latest = dedup_files[-1]
        with open(latest, "r", encoding="utf-8") as f:
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

        return {
            "success": True,
            "message": f"重新索引完成，共 {len(documents)} 条文档",
            "total_documents": len(documents),
            "source_file": latest.name
        }

    except Exception as e:
        logger.error(f"重新索引失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
