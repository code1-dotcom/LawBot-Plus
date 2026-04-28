"""RAG 评估埋点 Celery 任务

无侵入埋点：工作流完成后将 RAG 输入输出写入 RetrievalEvalLog，
供离线 RAGAS 批量评估管线使用。

字段映射：
  query           ← 用户问题
  reranked_doc_ids ← 重排文档的 title/article 组合
  retrieved_doc_ids ← 重排前原始检索文档
  relevance_scores  ← 重排得分列表
  final_selected_doc_id ← 取 reranked_docs 第一条的 id（如有）
  user_feedback   ← 默认为 None，后续由人工标注补充
"""

from celery import Task
from sqlalchemy.orm import Session

from src.celery_app import celery_app
from src.db.database import SyncSessionLocal
from src.db.models import RetrievalEvalLog
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _extract_doc_identifiers(reranked_docs: list[dict]) -> list[str]:
    """从重排文档列表中提取 title/article 组合字符串，供离线评估回溯使用。"""
    identifiers = []
    for doc in reranked_docs:
        title = doc.get("title") or doc.get("source") or ""
        article = doc.get("article") or ""
        identifiers.append(f"{title}::{article}" if article else title)
    return identifiers


def _extract_retrieved_doc_ids(retrieved_docs: list[dict]) -> list[str] | None:
    """从原始检索文档列表中提取标识符。"""
    if not retrieved_docs:
        return None
    return _extract_doc_identifiers(retrieved_docs)


@celery_app.task(
    bind=True,
    name="lawbot.log_rag_eval_data",
    max_retries=3,
    default_retry_delay=10,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def log_rag_eval_data(
    self: Task,
    query: str,
    reranked_docs: list[dict],
    final_answer: str,
    retrieved_docs: list[dict] | None = None,
) -> dict:
    """
    将 RAG 工作流产生的输入输出写入评估日志表。

    Args:
        query: 用户原始问题
        reranked_docs: 重排后的文档列表，每项为 dict，至少包含 title/content/score
        final_answer: AI 生成的最终回答
        retrieved_docs: 重排前的原始检索文档（可选，用于分析检索阶段质量）

    Returns:
        {"status": "ok", "log_id": <id>} 或 {"status": "error", "detail": ...}
    """
    logger.info(f"[RAGEval] 埋点写入: query={query[:50]}...")

    try:
        db: Session = SyncSessionLocal()
        try:
            # 提取文档标识符
            reranked_doc_ids = _extract_doc_identifiers(reranked_docs)
            retrieved_doc_ids = _extract_retrieved_doc_ids(retrieved_docs) if retrieved_docs else None

            # 提取重排得分
            relevance_scores = [
                doc.get("rerank_score") or doc.get("score") or 0.0
                for doc in reranked_docs
            ]

            # 取 top-1 文档 ID
            final_selected_doc_id: int | None = None
            if reranked_docs:
                first_doc = reranked_docs[0]
                final_selected_doc_id = first_doc.get("id")

            # 写入评估日志
            log_entry = RetrievalEvalLog(
                query=query,
                retrieved_doc_ids=retrieved_doc_ids,
                relevance_scores=relevance_scores,
                reranked_doc_ids=reranked_doc_ids,
                final_selected_doc_id=final_selected_doc_id,
                final_answer=final_answer,
                user_feedback=None,
            )
            db.add(log_entry)
            db.commit()
            db.refresh(log_entry)

            logger.info(f"[RAGEval] 写入成功: log_id={log_entry.id}")
            return {"status": "ok", "log_id": log_entry.id}

        finally:
            db.close()

    except Exception as exc:
        # 异常仅记录日志，不向上传播，避免阻塞主业务
        logger.warning(f"[RAGEval] 写入失败（将自动重试第 {self.request.retries + 1} 次）: {exc}")
        raise  # Celery 自动重试，超过 max_retries 后任务标记为 FAILURE
