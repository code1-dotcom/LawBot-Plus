"""Celery任务队列配置"""
from celery import Celery
from src.config import get_settings

settings = get_settings()

# 创建Celery应用
celery_app = Celery(
    "lawbot",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["src.tasks"]
)

# Celery配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5分钟超时
    task_soft_time_limit=240,  # 4分钟软超时
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)


@celery_app.task(bind=True, name="lawbot.process_legal_query")
def process_legal_query(self, user_input: str, session_id: str, task_id: str):
    """处理法律查询任务"""
    import asyncio
    from src.agents.workflow import run_legal_consultation
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(
            run_legal_consultation(
                user_input=user_input,
                session_id=session_id,
                task_id=task_id
            )
        )
        return {
            "status": "completed",
            "answer": result.answer,
            "sources": result.sources,
            "confidence": result.confidence,
            "needs_review": result.needs_review
        }
    finally:
        loop.close()
