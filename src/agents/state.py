"""Agent系统状态定义 - LangGraph状态机核心"""
from typing import Annotated, Literal, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class AgentState(BaseModel):
    """多智能体协作状态"""
    
    # ===== 对话上下文 =====
    session_id: str = Field(description="会话ID")
    user_input: str = Field(description="用户原始输入")
    rewritten_query: Optional[str] = Field(default=None, description="改写后的检索query")
    tokenized_query: Optional[list[str]] = Field(default=None, description="分词后的检索词列表")
    
    # ===== 消息历史 =====
    messages: list[dict] = Field(default_factory=list, description="对话历史")
    
    # ===== 当前执行状态 =====
    current_agent: Literal["planner", "researcher", "analyst", "reviewer", "memory", "tools"] = Field(
        default="planner", description="当前活跃的Agent"
    )
    
    # ===== 检索结果 =====
    retrieved_docs: list[dict] = Field(default_factory=list, description="检索到的文档")
    reranked_docs: list[dict] = Field(default_factory=list, description="重排后的文档")
    relevance_check_passed: bool = Field(default=True, description="相关性检查是否通过")
    
    # ===== 分析与推理 =====
    analysis_result: Optional[str] = Field(default=None, description="分析师推理结果")
    reasoning_chain: list[str] = Field(default_factory=list, description="推理链")
    
    # ===== 审核与HITL =====
    needs_review: bool = Field(default=False, description="是否需要人工审核")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="置信度")
    risk_level: Literal["low", "medium", "high", "critical"] = Field(
        default="low", description="风险等级"
    )
    
    # ===== 最终输出 =====
    final_answer: Optional[str] = Field(default=None, description="最终回答")
    sources: list[dict] = Field(default_factory=list, description="引用来源")
    
    # ===== 工具调用 =====
    tool_calls: list[dict] = Field(default_factory=list, description="工具调用记录")
    tool_results: list[dict] = Field(default_factory=list, description="工具执行结果")
    needs_tool: bool = Field(default=False, description="是否需要调用工具")
    
    # ===== 记忆上下文 =====
    memory_context: dict = Field(default_factory=dict, description="长期记忆上下文")
    
    # ===== 元数据 =====
    task_id: Optional[str] = Field(default=None, description="任务ID")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # ===== 错误处理 =====
    error: Optional[str] = Field(default=None, description="错误信息")
    retry_count: int = Field(default=0, description="重试次数")


class AgentResponse(BaseModel):
    """Agent响应模型"""
    answer: str
    sources: list[dict] = Field(default_factory=list)
    confidence: float
    needs_review: bool = False
    reasoning_chain: list[str] = Field(default_factory=list)
    extra_data: dict = Field(default_factory=dict)
    rewritten_query: Optional[str] = None
    tokenized_query: list[str] = Field(default_factory=list)
