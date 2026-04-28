"""FastAPI应用主入口"""
import uuid
import time
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import asyncio
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db.database import get_db, init_db, close_db
from src.db.models import Task, TaskStatus
from src.agents.workflow import run_legal_consultation
from src.hitl.service import hitl_service
from src.utils.logger import setup_logging, get_logger

# 初始化日志
setup_logging()
logger = get_logger(__name__)

settings = get_settings()


# ============== Pydantic模型 ==============

class ChatRequest(BaseModel):
    """聊天请求"""
    message: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[str] = None
    use_hitl: bool = True


class ChatResponse(BaseModel):
    """聊天响应"""
    task_id: str
    session_id: str
    status: str
    message: Optional[str] = None
    result: Optional[dict] = None
    rewritten_query: Optional[str] = None
    tokenized_query: Optional[list[str]] = None


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None


class HITLTaskResponse(BaseModel):
    """HITL任务响应"""
    id: int
    task_id: str
    user_question: str
    agent_reasoning: str
    suggested_answer: str
    confidence_score: float
    risk_level: str
    status: str
    created_at: str


class ReviewRequest(BaseModel):
    """审核请求"""
    task_id: str
    action: str = Field(..., pattern="^(approve|reject|modify)$")
    modified_answer: Optional[str] = None
    comments: Optional[str] = None


# ============== FastAPI应用 ==============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动
    logger.info("LawBot+ 服务启动中...")

    # 尝试初始化数据库（PostgreSQL不可用时跳过）
    try:
        await init_db()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.warning(f"数据库连接失败，会话存储将使用内存模式: {e}")

    # 加载法律知识库
    try:
        from src.rag.knowledge_base import legal_kb
        from pathlib import Path
        import json

        processed_dir = Path(__file__).parent.parent / "rag" / "processed"
        dedup_files = sorted(processed_dir.glob("deduplicated_*.json"))

        if dedup_files:
            latest = dedup_files[-1]
            logger.info(f"加载知识库: {latest.name}")

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
            logger.info(f"知识库加载完成: {len(docs)} 条法律条文")
        else:
            logger.warning("未找到知识库文件，跳过加载")
    except Exception as e:
        logger.error(f"加载知识库失败: {e}")

    # 初始化默认工具
    from src.agents.tools import init_default_tools, init_default_skills
    await init_default_tools()
    await init_default_skills()
    logger.info("默认工具和技能已初始化")

    yield

    # 关闭
    logger.info("LawBot+ 服务关闭中...")
    await close_db()
    logger.info("数据库连接已关闭")


app = FastAPI(
    title="LawBot+ API",
    description="带人工审核的多智能体法律咨询系统",
    version="1.0.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from src.api.tools_api import router as tools_router, skill_router
from src.api.knowledge_api import router as knowledge_router
from src.api.session_store import session_store

app.include_router(tools_router)
app.include_router(skill_router)
app.include_router(knowledge_router)


# ============== API路由 ==============

@app.get("/")
async def root():
    """根路径"""
    return {"message": "LawBot+ API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


# ============== 会话管理 API ==============

from pydantic import BaseModel
from typing import List, Optional

class SessionSaveRequest(BaseModel):
    """保存会话请求"""
    session_id: str
    messages: List[dict]
    title: Optional[str] = None


class SessionUpdateRequest(BaseModel):
    """更新会话请求"""
    messages: List[dict]
    title: Optional[str] = None


@app.post("/sessions")
async def save_session(request: SessionSaveRequest):
    """保存会话"""
    from src.api.session_store import session_store
    
    session_id = await session_store.save_conversation(
        request.session_id,
        request.messages,
        request.title
    )
    return {"session_id": session_id}


@app.get("/sessions")
async def list_sessions(limit: int = 20, offset: int = 0):
    """获取会话列表"""
    from src.api.session_store import session_store
    
    sessions = await session_store.list_conversations(limit, offset)
    return sessions


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """获取指定会话"""
    from src.api.session_store import session_store
    
    session = await session_store.get_conversation(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    from src.api.session_store import session_store
    
    await session_store.delete_conversation(session_id)
    return {"status": "success"}


@app.put("/sessions/{session_id}")
async def update_session(session_id: str, request: SessionUpdateRequest):
    """更新会话"""
    from src.api.session_store import session_store

    await session_store.update_conversation(session_id, request.messages)
    return {"status": "success"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """法律咨询接口"""
    session_id = request.session_id or str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    
    logger.info(f"收到咨询请求: session={session_id}, task={task_id}")
    
    # 创建任务记录
    task = Task(
        task_id=task_id,
        session_id=session_id,
        user_input=request.message,
        status=TaskStatus.PENDING.value,
        needs_review=request.use_hitl
    )
    db.add(task)
    await db.commit()
    
    # 异步执行工作流
    try:
        # 直接执行（生产环境应使用Celery队列）
        result = await run_legal_consultation(
            user_input=request.message,
            session_id=session_id,
            task_id=task_id
        )
        
        # 更新任务状态
        task.status = TaskStatus.COMPLETED.value if not result.needs_review else TaskStatus.REVIEWING.value
        task.result = {
            "answer": result.answer,
            "sources": result.sources,  # 已经是字典列表
            "confidence": result.confidence,
            "reasoning_chain": result.reasoning_chain
        }
        task.needs_review = result.needs_review
        task.confidence_score = result.confidence
        
        # 如果需要审核，创建HITL任务
        if result.needs_review and result.extra_data:
            from src.hitl.service import hitl_service
            from src.agents.state import AgentState
            
            # 从 extra_data 创建 AgentState 用于 HITL
            hitl_state = AgentState(
                session_id=session_id,
                user_input=request.message,
                task_id=task_id,
                analysis_result=result.answer,
                reasoning_chain=result.reasoning_chain,
                confidence_score=result.confidence,
                risk_level=result.extra_data.get("risk_level", "medium")
            )
            await hitl_service.create_review_task(db, hitl_state)
        
        await db.commit()
        
        # 追加到会话历史
        try:
            from src.api.session_store import session_store
            existing = await session_store.get_conversation(session_id)
            existing_messages = existing.get("messages", []) if existing else []
            updated_messages = existing_messages + [
                {"role": "user", "content": request.message},
                {"role": "assistant", "content": result.answer, "sources": result.sources,
                 "reasoning_chain": result.reasoning_chain, "confidence": result.confidence,
                 "needs_review": result.needs_review,
                 "extra_data": result.extra_data,
                 "rewritten_query": result.rewritten_query,
                 "tokenized_query": result.tokenized_query}
            ]
            await session_store.save_conversation(session_id, updated_messages)
            logger.info(f"会话已保存: {session_id}")
        except Exception as save_err:
            logger.warning(f"保存会话失败: {save_err}")
        
        return ChatResponse(
            task_id=task_id,
            session_id=session_id,
            status=task.status,
            message="处理完成" if not result.needs_review else "待审核",
            result={
                "answer": result.answer,
                "sources": result.sources,
                "confidence": result.confidence,
                "reasoning_chain": result.reasoning_chain
            },
            rewritten_query=result.rewritten_query,
            tokenized_query=result.tokenized_query
        )
        
    except Exception as e:
        logger.error(f"处理失败: {e}")
        task.status = TaskStatus.FAILED.value
        task.error = str(e)
        await db.commit()
        raise HTTPException(status_code=500, detail=str(e))


async def generate_stream_response(user_input: str, session_id: str, task_id: str):
    """流式生成响应"""
    import json
    
    # 发送开始事件
    yield {"event": "status", "data": json.dumps({"status": "planning", "message": "开始分析问题..."})}
    
    try:
        # 执行工作流，但实时发送每个节点的输出
        from src.agents.workflow import compiled_workflow
        from src.agents.state import AgentState
        
        initial_state = AgentState(
            session_id=session_id,
            user_input=user_input,
            task_id=task_id
        )
        config = {"configurable": {"thread_id": session_id}}
        
        full_answer = ""
        sources = []
        reasoning_chain = []
        
        # 使用 ainvoke 获取完整状态
        final_state = await compiled_workflow.ainvoke(initial_state, config)
        
        # 获取结果
        full_answer = final_state.get("final_answer", "处理完成")
        sources = final_state.get("sources", [])
        reasoning_chain = final_state.get("reasoning_chain", [])
        confidence = final_state.get("confidence_score", 0.0)
        needs_review = final_state.get("needs_review", False)
        risk_level = final_state.get("risk_level", "unknown")
        rewritten_query = final_state.get("rewritten_query", user_input)
        tokenized_query = final_state.get("tokenized_query", [])

        # 流式发送答案（逐字符或逐词）
        yield {"event": "status", "data": json.dumps({"status": "streaming", "message": "生成回答中..."})}

        # 将答案分成小块发送
        chunk_size = 20  # 每块字符数
        for i in range(0, len(full_answer), chunk_size):
            chunk = full_answer[i:i+chunk_size]
            yield {"event": "token", "data": json.dumps({"content": chunk})}
            await asyncio.sleep(0.01)  # 小延迟以实现流式效果

        # 发送完成事件
        yield {
            "event": "done",
            "data": json.dumps({
                "sources": sources,
                "confidence": confidence,
                "needs_review": needs_review,
                "risk_level": risk_level,
                "session_id": session_id,
                "task_id": task_id,
                "rewritten_query": rewritten_query,
                "tokenized_query": tokenized_query
            })
        }
        
        # 保存会话到 session_store
        try:
            from src.api.session_store import session_store
            existing = await session_store.get_conversation(session_id)
            existing_messages = existing.get("messages", []) if existing else []
            updated_messages = existing_messages + [
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": full_answer, "sources": sources,
                 "reasoning_chain": reasoning_chain, "confidence": confidence,
                 "needs_review": needs_review, "risk_level": risk_level,
                 "rewritten_query": rewritten_query, "tokenized_query": tokenized_query}
            ]
            await session_store.save_conversation(session_id, updated_messages)
            logger.info(f"会话已保存: {session_id}")
        except Exception as save_err:
            logger.warning(f"保存会话失败: {save_err}")
        
    except Exception as e:
        logger.error(f"流式处理失败: {e}")
        yield {"event": "error", "data": json.dumps({"message": str(e)})}


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """流式法律咨询接口"""
    session_id = request.session_id or str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    
    logger.info(f"收到流式咨询请求: session={session_id}, task={task_id}")
    
    # 创建任务记录
    task = Task(
        task_id=task_id,
        session_id=session_id,
        user_input=request.message,
        status=TaskStatus.PENDING.value,
        needs_review=request.use_hitl
    )
    db.add(task)
    await db.commit()
    
    async def event_generator():
        try:
            async for event in generate_stream_response(request.message, session_id, task_id):
                yield event
        finally:
            # 工作流完成后更新数据库
            await db.refresh(task)
            task.status = TaskStatus.COMPLETED.value
            await db.commit()
    
    return EventSourceResponse(event_generator())


@app.get("/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str, db: AsyncSession = Depends(get_db)):
    """获取任务状态"""
    from sqlalchemy import select
    
    result = await db.execute(
        select(Task).where(Task.task_id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return TaskStatusResponse(
        task_id=task.task_id,
        status=task.status,
        result=task.result,
        error=task.error
    )


# ============== HITL API ==============

@app.get("/hitl/tasks", response_model=List[HITLTaskResponse])
async def list_hitl_tasks(
    reviewer: Optional[str] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """获取待审核任务列表"""
    tasks = await hitl_service.get_pending_tasks(db, reviewer, limit)
    
    return [
        HITLTaskResponse(
            id=t.id,
            task_id=t.task_id,
            user_question=t.user_question,
            agent_reasoning=t.agent_reasoning,
            suggested_answer=t.suggested_answer,
            confidence_score=t.confidence_score,
            risk_level=t.risk_level,
            status=t.status,
            created_at=t.created_at.isoformat()
        )
        for t in tasks
    ]


@app.post("/hitl/review")
async def review_task(request: ReviewRequest, db: AsyncSession = Depends(get_db)):
    """审核任务"""
    try:
        if request.action == "approve":
            task = await hitl_service.approve_task(db, request.task_id, request.comments)
        elif request.action == "reject":
            if not request.comments:
                raise HTTPException(status_code=400, detail="拒绝时必须提供理由")
            task = await hitl_service.reject_task(db, request.task_id, request.comments)
        else:  # modify
            if not request.modified_answer:
                raise HTTPException(status_code=400, detail="修改时必须提供新答案")
            task = await hitl_service.modify_and_approve(
                db, request.task_id, request.modified_answer, request.comments
            )
        
        return {"status": "success", "task_id": task.task_id, "new_status": task.status}
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/hitl/result/{task_id}")
async def get_hitl_result(task_id: str, db: AsyncSession = Depends(get_db)):
    """获取审核结果"""
    result = await hitl_service.get_task_result(db, task_id)
    
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return result


# ============== WebSocket 支持 ==============

class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
    
    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[session_id] = websocket
    
    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
    
    async def send_message(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(message)


manager = ConnectionManager()


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket实时通信"""
    await manager.connect(session_id, websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            
            # 解析消息
            import json
            message_data = json.loads(data)
            
            if message_data.get("type") == "chat":
                # 处理聊天
                result = await run_legal_consultation(
                    user_input=message_data["message"],
                    session_id=session_id
                )
                
                await manager.send_message(session_id, {
                    "type": "response",
                    "needs_review": result.needs_review,
                    "answer": result.answer,
                    "sources": result.sources,
                    "confidence": result.confidence
                })
                
                if result.needs_review:
                    await manager.send_message(session_id, {
                        "type": "pending_review",
                        "task_id": result.extra_data.get("task_id") if result.extra_data else None
                    })
                    
    except WebSocketDisconnect:
        manager.disconnect(session_id)


# ============== 主程序入口 ==============

def run_server():
    """启动服务器"""
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
        log_level=settings.log_level.lower()
    )


if __name__ == "__main__":
    run_server()
