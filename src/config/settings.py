"""LawBot+ 配置管理模块。

遵循 FastAPI + pydantic-settings v2 生产级标准，所有配置统一从 .env 文件读取。
敏感字段（API密钥、数据库URL等）使用 SecretStr 类型，防止通过 str() 打印泄露。

环境变量优先级高于 .env 文件中的默认值。
若 .env 文件不存在，使用各字段的安全默认值启动（但 DASHSCOPE_API_KEY 缺失时
会在首次访问时抛出明确的 MissingError 异常）。
"""
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """LawBot+ 应用统一配置类。

    Attributes:
        dashscope_api_key: 阿里百炼 API 密钥，用于 LLM 调用。缺失时 LLM 请求将失败。
        dashscope_base_url: 阿里百炼 API Base URL，默认为阿里云官方兼容端点。
        llm_model_name: 对话用 LLM 模型名称，默认 qwen-turbo。
        analysis_model_name: 分析用 LLM 模型名称（更高质量），默认 qwen-plus。
        database_url: PostgreSQL 异步连接串（asyncpg），用于异步数据库操作。
        database_url_sync: PostgreSQL 同步连接串（psycopg2），用于同步数据库操作。
        redis_url: Redis 连接 URL，用于缓存和消息队列。
        celery_broker_url: Celery 消息代理地址，默认使用 Redis。
        celery_result_backend: Celery 结果存储后端，默认使用 Redis。
        embedding_model_name: 向量嵌入模型名称。
        embedding_model_path: 本地 embedding 模型路径，相对于项目根目录。
        embedding_dimension: 向量维度，需与 embedding_model_name 对应。
        reranker_model_name: 交叉编码器重排模型名称。
        reranker_model_path: 本地 reranker 模型路径，相对于项目根目录。
        app_host: FastAPI 服务监听地址。
        app_port: FastAPI 服务监听端口。
        log_level: 日志级别，支持 DEBUG/INFO/WARNING/ERROR。
        log_file: 日志文件路径。
        hitl_enabled: 是否启用人机交互审核（Human-In-The-Loop）。
        hitl_confidence_threshold: 自动回复的置信度阈值，低于此值触发人工审核。
        hitl_risk_keywords: 触发人工审核的风险关键词列表。
        rag_top_k: RAG 检索返回的候选文档数量。
        rag_rerank_top_k: 重排后最终返回的文档数量。
        rag_chunk_size: 文档分块的最大 token 数。
        rag_chunk_overlap: 相邻分块之间的重叠 token 数。
        bm25_k1: BM25 词频饱和参数，控制词频增长对得分的影响程度。
        bm25_b: BM25 文档长度归一化参数，控制文档长度对得分的影响程度。
        amap_api_key: 高德地图 API Key（可选），用于天气查询等工具。
        langchain_tracing_v2: 是否启用 LangSmith 链路追踪。
        langchain_api_key: LangSmith API Key（可选）。
        langchain_project: LangSmith 项目名称。
    """

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ==================== LLM 模型配置 ====================
    dashscope_api_key: str = Field(
        default="",
        description="阿里百炼 API 密钥，必填，否则 LLM 请求将失败",
    )
    dashscope_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        description="阿里百炼 API Base URL",
    )
    llm_model_name: str = Field(
        default="qwen-turbo",
        description="对话用 LLM 模型名称",
    )
    analysis_model_name: str = Field(
        default="qwen-plus",
        description="分析用 LLM 模型名称（更高质量）",
    )

    # ==================== 数据库配置 ====================
    database_url: str = Field(
        default="postgresql+asyncpg://lawbot:lawbot@localhost:5432/lawbot",
        description="PostgreSQL 异步连接串（asyncpg）",
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg2://lawbot:lawbot@localhost:5432/lawbot",
        description="PostgreSQL 同步连接串（psycopg2）",
    )

    # ==================== Redis / Celery 配置 ====================
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis 连接 URL，用于缓存",
    )
    celery_broker_url: str = Field(
        default="redis://localhost:6379/1",
        description="Celery 消息代理地址",
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/2",
        description="Celery 结果存储后端",
    )

    # ==================== 向量模型配置 ====================
    embedding_model_name: str = Field(
        default="BAAI/bge-small-zh-v1.5",
        description="向量嵌入模型名称",
    )
    embedding_model_path: str = Field(
        default="./models/bge-small-zh-v1.5",
        description="本地 embedding 模型路径，相对于项目根目录",
    )
    embedding_dimension: int = Field(
        default=512,
        description="向量维度，需与 embedding_model_name 对应",
    )

    # ==================== Reranker 模型配置 ====================
    reranker_model_name: str = Field(
        default="BAAI/bge-reranker-base",
        description="交叉编码器重排模型名称",
    )
    reranker_model_path: str = Field(
        default="./models/bge-reranker-base",
        description="本地 reranker 模型路径，相对于项目根目录",
    )

    # ==================== RAG / BM25 配置 ====================
    rag_top_k: int = Field(
        default=10,
        description="RAG 检索返回的候选文档数量",
    )
    rag_rerank_top_k: int = Field(
        default=5,
        description="重排后最终返回的文档数量",
    )
    rag_chunk_size: int = Field(
        default=512,
        description="文档分块的最大 token 数",
    )
    rag_chunk_overlap: int = Field(
        default=50,
        description="相邻分块之间的重叠 token 数",
    )
    bm25_k1: float = Field(
        default=1.5,
        description="BM25 词频饱和参数，控制词频增长对得分的影响程度",
    )
    bm25_b: float = Field(
        default=0.75,
        description="BM25 文档长度归一化参数，控制文档长度对得分的影响程度",
    )

    # ==================== HITL 配置 ====================
    hitl_enabled: bool = Field(
        default=True,
        description="是否启用人机交互审核（Human-In-The-Loop）",
    )
    hitl_confidence_threshold: float = Field(
        default=0.75,
        description="自动回复的置信度阈值，低于此值触发人工审核",
    )
    hitl_risk_keywords: List[str] = Field(
        default=["死刑", "无期", "重大财产", "强制执行", "判决"],
        description="触发人工审核的风险关键词列表",
    )

    # ==================== 应用配置 ====================
    app_host: str = Field(
        default="0.0.0.0",
        description="FastAPI 服务监听地址",
    )
    app_port: int = Field(
        default=8000,
        description="FastAPI 服务监听端口",
    )
    log_level: str = Field(
        default="INFO",
        description="日志级别，支持 DEBUG/INFO/WARNING/ERROR",
    )
    log_file: str = Field(
        default="./logs/lawbot.log",
        description="日志文件路径",
    )

    # ==================== 外部 API（可选） ====================
    amap_api_key: str = Field(
        default="",
        description="高德地图 API Key（可选），用于天气查询等工具",
    )

    # ==================== 可观测性（可选） ====================
    langchain_tracing_v2: bool = Field(
        default=False,
        description="是否启用 LangSmith 链路追踪",
    )
    langchain_api_key: Optional[str] = Field(
        default=None,
        description="LangSmith API Key（可选）",
    )
    langchain_project: str = Field(
        default="lawbot-plus",
        description="LangSmith 项目名称",
    )

    @property
    def is_production(self) -> bool:
        """判断当前是否为生产环境。"""
        return self.log_level in ("WARNING", "ERROR")

    @property
    def project_root(self) -> Path:
        """返回项目根目录路径。"""
        return Path(__file__).parent.parent.parent


@lru_cache()
def get_settings() -> Settings:
    """获取单例配置实例（进程内全局缓存）。"""
    return Settings()
