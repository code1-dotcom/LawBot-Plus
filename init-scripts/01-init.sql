-- LawBot+ Database Initialization Script
-- 创建pgvector扩展和基础表结构

-- 启用pgvector扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 创建向量表用于文档embedding存储
CREATE TABLE IF NOT EXISTS document_embeddings (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    embedding vector(1024),  -- BGE-large-zh 生成的1024维向量
    content text NOT NULL,
    metadata jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建向量索引（使用HNSW算法，适合高维向量最近邻搜索）
CREATE INDEX IF NOT EXISTS idx_embeddings_hnsw 
ON document_embeddings 
USING hnsw (embedding vector_cosine_ops);

-- 创建全文检索索引
CREATE INDEX IF NOT EXISTS idx_embeddings_content_gin 
ON document_embeddings 
USING gin (to_tsvector('chinese', content));

-- 创建智能体对话历史表
CREATE TABLE IF NOT EXISTS conversation_history (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB,
    token_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conversation_session 
ON conversation_history(session_id, created_at);

-- 创建HITL审查任务表
CREATE TABLE IF NOT EXISTS hitl_tasks (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(64) UNIQUE NOT NULL,
    session_id VARCHAR(64) NOT NULL,
    user_question TEXT NOT NULL,
    agent_reasoning TEXT NOT NULL,
    suggested_answer TEXT NOT NULL,
    confidence_score FLOAT,
    risk_level VARCHAR(20),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'modified')),
    reviewer_comments TEXT,
    original_answer TEXT,
    modified_answer TEXT,
    assigned_reviewer VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_hitl_tasks_status 
ON hitl_tasks(status, created_at);

-- 创建检索评估日志表
CREATE TABLE IF NOT EXISTS retrieval_eval_logs (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    retrieved_doc_ids INTEGER[],
    relevance_scores FLOAT[],
    reranked_doc_ids INTEGER[],
    final_selected_doc_id INTEGER,
    user_feedback INTEGER CHECK (user_feedback BETWEEN 1 AND 5),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 授予权限
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO lawbot;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO lawbot;
