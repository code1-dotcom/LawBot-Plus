"""HITL服务层"""
import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import HITLTask, TaskStatus
from src.agents.state import AgentState
from src.config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class HITLService:
    """HITL人工审核服务"""
    
    def __init__(self):
        self.enabled = settings.hitl_enabled
    
    async def create_review_task(
        self,
        db: AsyncSession,
        state: AgentState
    ) -> HITLTask:
        """创建审核任务"""
        logger.info(f"[HITL] 创建审核任务: {state.task_id}")
        
        task = HITLTask(
            task_id=state.task_id,
            session_id=state.session_id,
            user_question=state.user_input,
            agent_reasoning="\n".join(state.reasoning_chain),
            suggested_answer=state.analysis_result or "",
            confidence_score=state.confidence_score,
            risk_level=state.risk_level,
            status="pending"
        )
        
        db.add(task)
        await db.commit()
        await db.refresh(task)
        
        logger.info(f"[HITL] 审核任务创建成功: {task.id}")
        return task
    
    async def get_pending_tasks(
        self,
        db: AsyncSession,
        reviewer: Optional[str] = None,
        limit: int = 20
    ) -> List[HITLTask]:
        """获取待审核任务"""
        from sqlalchemy import select
        
        query = select(HITLTask).where(
            HITLTask.status == "pending"
        ).order_by(HITLTask.created_at.desc()).limit(limit)
        
        if reviewer:
            query = query.where(HITLTask.assigned_reviewer == reviewer)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def approve_task(
        self,
        db: AsyncSession,
        task_id: str,
        comments: Optional[str] = None
    ) -> HITLTask:
        """批准任务"""
        logger.info(f"[HITL] 批准任务: {task_id}")
        
        task = await self._get_task(db, task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        
        task.status = "approved"
        task.reviewer_comments = comments
        task.reviewed_at = datetime.now()
        task.original_answer = task.suggested_answer
        
        await db.commit()
        await db.refresh(task)
        
        return task
    
    async def reject_task(
        self,
        db: AsyncSession,
        task_id: str,
        comments: str
    ) -> HITLTask:
        """拒绝/修改任务"""
        logger.info(f"[HITL] 拒绝任务: {task_id}")
        
        task = await self._get_task(db, task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        
        task.status = "rejected"
        task.reviewer_comments = comments
        task.reviewed_at = datetime.now()
        task.original_answer = task.suggested_answer
        
        await db.commit()
        await db.refresh(task)
        
        return task
    
    async def modify_and_approve(
        self,
        db: AsyncSession,
        task_id: str,
        modified_answer: str,
        comments: Optional[str] = None
    ) -> HITLTask:
        """修改后批准"""
        logger.info(f"[HITL] 修改并批准任务: {task_id}")
        
        task = await self._get_task(db, task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        
        task.status = "modified"
        task.reviewer_comments = comments
        task.modified_answer = modified_answer
        task.reviewed_at = datetime.now()
        
        await db.commit()
        await db.refresh(task)
        
        return task
    
    async def get_task_result(
        self,
        db: AsyncSession,
        task_id: str
    ) -> dict:
        """获取审核结果"""
        task = await self._get_task(db, task_id)
        if not task:
            return {"status": "not_found"}
        
        return {
            "status": task.status,
            "answer": task.modified_answer or task.suggested_answer if task.status != "rejected" else None,
            "original_answer": task.original_answer,
            "reviewer_comments": task.reviewer_comments,
            "reviewed_at": task.reviewed_at.isoformat() if task.reviewed_at else None
        }
    
    async def _get_task(self, db: AsyncSession, task_id: str) -> Optional[HITLTask]:
        """获取任务"""
        from sqlalchemy import select
        
        result = await db.execute(
            select(HITLTask).where(HITLTask.task_id == task_id)
        )
        return result.scalar_one_or_none()


# 全局HITL服务实例
hitl_service = HITLService()
