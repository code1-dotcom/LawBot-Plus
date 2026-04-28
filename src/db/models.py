"""数据库模型定义"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String, Text, Integer, Float, Boolean, DateTime, ForeignKey,
    JSON, Index, CheckConstraint, Enum as SQLEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ARRAY
import enum

from src.db.database import Base


class TaskStatus(str, enum.Enum):
    """任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REVIEWING = "reviewing"  # 待审核


class HITLStatus(str, enum.Enum):
    """HITL审核状态"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


class Document(Base):
    """法律文档表"""
    __tablename__ = "documents"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)  # law/case/template
    domain: Mapped[Optional[str]] = mapped_column(String(50))  # 民事/刑事/行政
    source: Mapped[Optional[str]] = mapped_column(String(200))  # 法律名称等
    article: Mapped[Optional[str]] = mapped_column(String(100))  # 条款号
    effective_date: Mapped[Optional[str]] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="active")  # active/expired
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    chunks: Mapped[List["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Document(id={self.id}, title={self.title})>"


class DocumentChunk(Base):
    """文档分块表（用于RAG检索）"""
    __tablename__ = "document_chunks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # pgvector存储（实际使用 pgvector 扩展）
    embedding: Mapped[Optional[List[float]]] = mapped_column(JSON)  # 简化：存储为JSON
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    
    # 关系
    document: Mapped["Document"] = relationship(back_populates="chunks")
    
    __table_args__ = (
        Index("idx_chunks_document_id", "document_id"),
    )


class Conversation(Base):
    """会话表"""
    __tablename__ = "conversations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="active")
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    messages: Mapped[List["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Conversation(id={self.id}, session_id={self.session_id})>"


class Message(Base):
    """消息表"""
    __tablename__ = "messages"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20), CheckConstraint("role IN ('user', 'assistant', 'system', 'tool')"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[Optional[list]] = mapped_column(JSON)
    reasoning_chain: Mapped[Optional[list]] = mapped_column(JSON)
    token_count: Mapped[Optional[int]] = mapped_column(Integer)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON)
    rewritten_query: Mapped[Optional[str]] = mapped_column(Text)
    tokenized_query: Mapped[Optional[list]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    
    # 关系
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    
    def __repr__(self):
        return f"<Message(id={self.id}, role={self.role})>"


class Task(Base):
    """任务表"""
    __tablename__ = "tasks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_input: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.PENDING.value)
    result: Mapped[Optional[dict]] = mapped_column(JSON)
    error: Mapped[Optional[str]] = mapped_column(Text)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    token_used: Mapped[Optional[int]] = mapped_column(Integer)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    def __repr__(self):
        return f"<Task(id={self.id}, task_id={self.task_id}, status={self.status})>"


class HITLTask(Base):
    """HITL审核任务表"""
    __tablename__ = "hitl_tasks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_question: Mapped[str] = mapped_column(Text, nullable=False)
    agent_reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_answer: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default=HITLStatus.PENDING.value)
    reviewer_comments: Mapped[Optional[str]] = mapped_column(Text)
    original_answer: Mapped[Optional[str]] = mapped_column(Text)
    modified_answer: Mapped[Optional[str]] = mapped_column(Text)
    assigned_reviewer: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    __table_args__ = (
        Index("idx_hitl_status_created", "status", "created_at"),
    )
    
    def __repr__(self):
        return f"<HITLTask(id={self.id}, task_id={self.task_id}, status={self.status})>"


class RetrievalEvalLog(Base):
    """检索评估日志"""
    __tablename__ = "retrieval_eval_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_doc_ids: Mapped[Optional[list]] = mapped_column(JSON)
    relevance_scores: Mapped[Optional[list]] = mapped_column(JSON)
    reranked_doc_ids: Mapped[Optional[list]] = mapped_column(JSON)
    final_selected_doc_id: Mapped[Optional[int]] = mapped_column(Integer)
    user_feedback: Mapped[Optional[int]] = mapped_column(Integer)  # 1-5分
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class LongTermMemory(Base):
    """长期记忆表"""
    __tablename__ = "long_term_memory"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    memory_type: Mapped[str] = mapped_column(String(50))  # user_profile/case_summary/preference
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Optional[list]] = mapped_column(JSON)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    __table_args__ = (
        Index("idx_memory_session_type", "session_id", "memory_type"),
    )
