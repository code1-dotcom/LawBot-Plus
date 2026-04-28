[TOC]



# LawBot+

> 基于 LangGraph 的生产级法律咨询多智能体系统

**LawBot+** 是一个以法律咨询为核心场景的 AI Agent 应用，采用 **多智能体协作 + 混合 RAG 检索 + 人机协同审核 (HITL)** 的技术架构。系统由 FastAPI 后端（LangGraph 工作流引擎 + MCP 工具协议）、Next.js 前端以及 Docker 中间件组成，可一键部署至生产环境。

---

## 技术栈

### 后端

| 层级 | 技术 | 版本要求 | 用途 |
|------|------|----------|------|
| **Agent 编排** | LangGraph | >= 0.2.0 | 多智能体状态机工作流 |
| **LLM 调用** | LangChain + DashScope SDK | >= 0.3.0 / >= 1.20.0 | 阿里百炼 API 集成 |
| **工具协议** | MCP + FastMCP | >= 1.0.0 / >= 0.1.0 | 标准化工具注册与调用 |
| **向量检索** | sentence-transformers + pgvector | >= 3.3.0 | 本地 BGE 向量嵌入 |
| **关键词检索** | rank-BM25 + jieba | >= 0.2.2 | 混合检索中的 BM25 成分 |
| **重排模型** | FlagEmbedding (BGE-Reranker) | >= 1.3.0 | 交叉编码器二阶段重排 |
| **Web 框架** | FastAPI + Uvicorn | >= 0.115.0 | 异步 REST/WebSocket API |
| **异步队列** | Celery + Redis | >= 5.4.0 | 任务调度与缓存 |
| **数据库** | PostgreSQL 16 + pgvector | - | 结构化数据 + 向量存储 |
| **会话存储** | Redis | 7.x | 实时会话缓存 |
| **配置管理** | pydantic-settings | >= 2.7.0 | 类型安全的配置读取 |
| **日志追踪** | Loguru + OpenTelemetry | >= 0.7.3 | 结构化日志与可观测性 |
| **评估框架** | TruLens + Ragas | >= 0.18.0 | RAG 效果离线评估 |

### 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| Next.js | 15.1.0 | React 全栈框架 |
| React | 19.0.0 | UI 组件库 |
| TailwindCSS | 3.4.17 | 原子化 CSS |
| Radix UI | (多种) | 无头 UI 组件 |
| Vercal AI SDK | 4.0.0 | 流式响应处理 |
| Lucide React | 0.468.0 | 图标库 |

### 中间件

| 服务 | 镜像 | 说明 |
|------|------|------|
| PostgreSQL | `pgvector/pgvector:pg16` | 含 pgvector 扩展，向量检索支持 |
| Redis | `redis:7-alpine` | 缓存、消息队列、Socket 存储 |

---

## 系统架构

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'fontSize': '13px' }}}%%
flowchart TB
    subgraph UI["用户交互层"]
        WEB["Next.js Web UI<br/>(http://localhost:3000)"]
        DOCS["FastAPI Docs<br/>(http://localhost:8000/docs)"]
    end

    subgraph Gateway["API 网关层"]
        FASTAPI["FastAPI<br/>/chat · /sessions · /hitl/* · /ws/*"]
    end

    subgraph AgentEngine["核心智能体引擎 (LangGraph)"]
        subgraph Nodes["工作流节点"]
            P["Planner<br/>意图拆解 & 查询改写"]
            R["Researcher<br/>MCP 工具调用"]
            RR["Reranker<br/>BGE-Reranker 重排"]
            RC["Relevance Check<br/>相关性过滤"]
            A["Analyst<br/>法律分析与推理"]
            RV["Reviewer<br/>置信度 & 风险评估"]
            HITL["HITL<br/>人工审核暂停节点"]
            MEM["Memory<br/>长期记忆写入"]
            F["Finalize<br/>答案组装"]
        end

        P --> R
        R --> RR --> RC
        RC -->|"通过"| A
        RC -->|"不通过"| F
        A --> RV
        RV -->|"置信度低 / 高风险"| HITL
        RV -->|"置信度高 & 低风险"| F
        HITL -.->|"审核通过"| F
        HITL -.->|"驳回重生成"| P
        F --> MEM
        MEM -.-> P
    end

    subgraph Tools["工具层 (MCP Protocol)"]
        MCP["MCP Server (FastMCP)"]
        RAG["legal_rag_search"]
        LIM["calculate_statute_of_limitations"]
        COMP["calculate_compensation"]
        DOC["generate_legal_document"]
        MCP --> RAG
        MCP --> LIM
        MCP --> COMP
        MCP --> DOC
    end

    subgraph RAGLayer["混合 RAG 管道"]
        subgraph Retrieval["混合检索"]
            VEC["向量检索<br/>(BGE-small-zh-v1.5, 512维)"]
            BM25["BM25 检索<br/>(jieba 分词)"]
            FUS["分数融合<br/>(0.5 × 向量 + 0.5 × BM25)"]
        end
        subgraph Rerank["重排阶段"]
            RERANK["BGE-Reranker<br/>交叉编码器二阶段排序"]
        end
        VEC --> FUS
        BM25 --> FUS
        FUS --> RERANK
    end

    subgraph Data["数据层"]
        PG["PostgreSQL 16<br/>+ pgvector (向量索引)"]
        RED["Redis 7<br/>(缓存 + 队列)"]
    end

    subgraph LLM["大语言模型"]
        TURBO["qwen-turbo<br/>(对话)"]
        PLUS["qwen-plus<br/>(分析 + 审核)"]
    end

    UI --> FASTAPI
    FASTAPI --> AgentEngine
    AgentEngine --> Tools
    AgentEngine --> RAGLayer
    RAGLayer --> PG
    AgentEngine --> LLM
    FASTAPI -.-> RED
    Tools -.-> PG
```

### 关键设计决策

**LangGraph 状态机** — 所有 Agent 节点（Planner、Researcher、Analyst、Reviewer）共享 `AgentState`，通过条件边（Conditional Edge）实现动态路由：置信度低于阈值或命中高风险关键词时自动暂停于 `HITL` 节点，等待人工审核。

**混合 RAG** — 采用向量检索（语义相似度）+ BM25（关键词精确匹配）分数等权融合，再经交叉编码器重排，兼顾语义理解与关键词命中。

**MCP 协议** — 统一封装法律工具（检索、时效计算、赔偿计算、文书生成），通过 FastMCP 暴露为标准化工具，供 LangGraph 动态选择调用。

---

## 一键本地启动

### 前置条件

- Python 3.10+
- Docker & Docker Compose
- 阿里百炼 API Key（[申请地址](https://dashscope.console.aliyun.com/)）
- 显存 4GB+（使用本地 Embedding 模型）

### 步骤 1：克隆并安装依赖

```bash
# 克隆项目
git clone <your-repo-url> LawBot
cd LawBot

# 创建并激活 conda 环境（推荐）
conda create -n lawbot-plus python=3.11
conda activate lawbot-plus

# 安装 Python 依赖
pip install -r requirements.txt

# 安装前端依赖
cd frontend
npm install
cd ..
```

### 步骤 2：启动中间件（Docker）

```bash
# 启动 PostgreSQL + Redis
docker compose up -d

# 验证服务就绪
docker compose ps
```

> 容器启动后，PostgreSQL 监听 `5432`，Redis 监听 `6379`，数据卷持久化存储。

### 步骤 3：配置环境变量

```bash
# 复制配置模板
cp .env.example .env   # 或直接编辑项目根目录的 .env 文件

# 必填：填入阿里百炼 API Key
# DASHSCOPE_API_KEY=your_api_key_here
```

### 步骤 4：下载 Embedding 模型（可选）

本地 Embedding 模型可提升检索质量并降低 API 调用成本：

| 模型 | 维度 | 显存要求 | 下载地址 |
|------|------|----------|----------|
| `BAAI/bge-small-zh-v1.5` | 512 维 | 4GB | [ModelScope](https://www.modelscope.cn/models/BAAI/bge-small-zh-v1.5) |
| `BAAI/bge-reranker-base` | - | 2GB | [ModelScope](https://www.modelscope.cn/models/BAAI/bge-reranker-base) |

将解压后的模型放入 `./models/` 目录，并确认 `.env` 中的路径配置：

```bash
# .env 示例
EMBEDDING_MODEL_PATH=./models/bge-small-zh-v1.5
RERANKER_MODEL_PATH=./models/bge-reranker-base
```

### 步骤 5：启动服务

**Windows：**

```bash
run.bat
```

**Linux / macOS：**

```bash
chmod +x run.sh
./run.sh
```

脚本提供四种启动模式：

| 选项 | 启动内容 | 访问地址 |
|------|----------|----------|
| `1` | FastAPI 后端服务 | http://localhost:8000/docs |
| `2` | Streamlit Web 界面 | http://localhost:8001 |
| `3` | MCP 工具服务器 | 内部服务 |
| `4` | 全部服务（API + UI） | http://localhost:8000 + http://localhost:8001 |

**手动启动（如需细粒度控制）：**

```bash
# 终端 1：启动 FastAPI
python -m src.main api --host 0.0.0.0 --port 8000

# 终端 2：启动 Streamlit UI
streamlit run src/api/streamlit_app.py --server.port 8001

# 终端 3：启动 MCP 服务器
python -m src.main mcp
```

### 步骤 6：启动 Next.js 前端

```bash
cd frontend
npm run dev
# 访问 http://localhost:3000
```

---

## 环境变量说明

所有配置项均通过 `.env` 文件读取（支持环境变量覆盖）。关键变量如下：

| 变量 | 是否必填 | 默认值 | 说明 |
|------|----------|--------|------|
| `DASHSCOPE_API_KEY` | **是** | - | 阿里百炼 API 密钥 |
| `DASHSCOPE_BASE_URL` | 否 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | API 端点 |
| `LLM_MODEL_NAME` | 否 | `qwen-turbo` | 对话模型 |
| `ANALYSIS_MODEL_NAME` | 否 | `qwen-plus` | 分析/审核模型 |
| `DATABASE_URL` | 否 | `postgresql+asyncpg://lawbot:lawbot@localhost:5432/lawbot` | 异步数据库连接 |
| `DATABASE_URL_SYNC` | 否 | `postgresql+psycopg2://...` | 同步数据库连接 |
| `REDIS_URL` | 否 | `redis://localhost:6379/0` | Redis 连接 URL |
| `CELERY_BROKER_URL` | 否 | `redis://localhost:6379/1` | Celery 消息代理 |
| `CELERY_RESULT_BACKEND` | 否 | `redis://localhost:6379/2` | Celery 结果后端 |
| `EMBEDDING_MODEL_NAME` | 否 | `BAAI/bge-small-zh-v1.5` | Embedding 模型名 |
| `EMBEDDING_MODEL_PATH` | 否 | `./models/bge-small-zh-v1.5` | 本地模型路径 |
| `EMBEDDING_DIMENSION` | 否 | `512` | 向量维度 |
| `RERANKER_MODEL_NAME` | 否 | `BAAI/bge-reranker-base` | Reranker 模型名 |
| `RERANKER_MODEL_PATH` | 否 | `./models/bge-reranker-base` | Reranker 本地路径 |
| `HITL_ENABLED` | 否 | `true` | 是否启用 HITL 审核 |
| `HITL_CONFIDENCE_THRESHOLD` | 否 | `0.75` | 触发审核的置信度阈值 |
| `HITL_RISK_KEYWORDS` | 否 | 见下方默认值 | 触发审核的高风险关键词 |
| `RAG_TOP_K` | 否 | `10` | 混合检索候选数 |
| `RAG_RERANK_TOP_K` | 否 | `5` | 重排后返回文档数 |
| `RAG_CHUNK_SIZE` | 否 | `512` | 文档分块 token 数 |
| `BM25_K1` | 否 | `1.5` | BM25 词频饱和参数 |
| `BM25_B` | 否 | `0.75` | BM25 文档长度归一化参数 |
| `LANGCHAIN_TRACING_V2` | 否 | `false` | 启用 LangSmith 链路追踪 |
| `LANGCHAIN_API_KEY` | 否 | - | LangSmith API Key（可选） |
| `LOG_LEVEL` | 否 | `INFO` | 日志级别 |
| `APP_HOST` | 否 | `0.0.0.0` | 服务监听地址 |
| `APP_PORT` | 否 | `8000` | 服务监听端口 |

> **默认 HITL_RISK_KEYWORDS**: `["死刑", "无期", "重大财产", "强制执行", "判决"]`
>
> 生产部署请务必修改所有默认密码（数据库密码、Redis 密码见 `docker-compose.yml`）。

---

## Docker 生产部署

### 方式一：仅中间件（本地开发）

```bash
docker compose up -d
```

### 方式二：完整容器化（前后端分离）

创建 `docker-compose.prod.yml`：

```yaml
version: "3.9"

services:
  # --- 中间件 ---
  postgres:
    image: pgvector/pgvector:pg16
    container_name: lawbot-postgres
    environment:
      POSTGRES_DB: lawbot
      POSTGRES_USER: lawbot
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-lawbot_secure_pass_2024}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U lawbot -d lawbot"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - lawbot-network

  redis:
    image: redis:7-alpine
    container_name: lawbot-redis
    command: >
      redis-server
      --appendonly yes
      --requirepass ${REDIS_PASSWORD:-redis_password_2024}
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    networks:
      - lawbot-network

  # --- FastAPI 后端 ---
  api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: lawbot-api
    command: python -m src.main api --host 0.0.0.0 --port 8000
    environment:
      DASHSCOPE_API_KEY: ${DASHSCOPE_API_KEY}
      DATABASE_URL: postgresql+asyncpg://lawbot:${POSTGRES_PASSWORD:-lawbot_secure_pass_2024}@postgres:5432/lawbot
      DATABASE_URL_SYNC: postgresql+psycopg2://lawbot:${POSTGRES_PASSWORD:-lawbot_secure_pass_2024}@postgres:5432/lawbot
      REDIS_URL: redis://:${REDIS_PASSWORD:-redis_password_2024}@redis:6379/0
      CELERY_BROKER_URL: redis://:${REDIS_PASSWORD:-redis_password_2024}@redis:6379/1
      CELERY_RESULT_BACKEND: redis://:${REDIS_PASSWORD:-redis_password_2024}@redis:6379/2
      HITL_ENABLED: "true"
      HITL_CONFIDENCE_THRESHOLD: "0.75"
      LOG_LEVEL: INFO
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./models:/app/models:ro
      - ./logs:/app/logs
    restart: unless-stopped
    networks:
      - lawbot-network

  # --- Streamlit UI ---
  ui:
    build:
      context: .
      dockerfile: Dockerfile.streamlit
    container_name: lawbot-ui
    command: streamlit run src/api/streamlit_app.py --server.port 8501 --server.address 0.0.0.0
    environment:
      API_BASE_URL: http://api:8000
    ports:
      - "8501:8501"
    depends_on:
      - api
    restart: unless-stopped
    networks:
      - lawbot-network

  # --- Next.js 前端 (建议使用 Vercel 部署) ---
  # 前端推荐独立构建后部署至 Vercel
  # 前端 .env.local: NEXT_PUBLIC_API_URL=https://your-domain.com

volumes:
  postgres_data:
  redis_data:

networks:
  lawbot-network:
    driver: bridge
```

**构建并启动：**

```bash
# 设置环境变量
export DASHSCOPE_API_KEY=your_api_key
export POSTGRES_PASSWORD=your_secure_password
export REDIS_PASSWORD=your_redis_password

# 构建镜像
docker compose -f docker-compose.prod.yml build

# 启动全部服务
docker compose -f docker-compose.prod.yml up -d

# 查看日志
docker compose -f docker-compose.prod.yml logs -f
```

### 方式三：Vercel 前端部署

```bash
cd frontend

# 创建 .env.local
echo "NEXT_PUBLIC_API_URL=https://your-api-domain.com" > .env.local

# 部署到 Vercel
vercel --prod
```

---

## 核心功能详解

### 混合 RAG 检索管道

```
用户查询
    │
    ├─── 向量检索 (BGE-small-zh-v1.5, cosine similarity)
    │        │
    │        └── top_k=10
    │
    ├─── BM25 检索 (jieba 分词, k1=1.5, b=0.75)
    │        │
    │        └── top_k=10
    │
    ├─── 分数融合 (0.5 × 向量得分 + 0.5 × BM25 得分)
    │        │
    │        └── top_k=10 候选
    │
    └─── BGE-Reranker 重排
             │
             └── top_k=5 最终上下文
```

### LangGraph 状态机流程

```mermaid
stateDiagram-v2
    [*] --> Planner: 用户输入
    Planner --> Researcher: 改写查询
    Researcher --> Reranker: 工具结果
    Reranker --> RelevanceCheck: 重排候选
    RelevanceCheck --> Analyst: 相关
    RelevanceCheck --> [*]: 不相关
    Analyst --> Reviewer: 法律分析
    Reviewer --> Finalize: 置信度高 & 低风险
    Reviewer --> HITL: 置信度低 或 高风险
    HITL --> Finalize: 审核通过
    HITL --> Planner: 驳回重生成
    Finalize --> Memory: 写入记忆
    Memory --> [*]
```

### HITL 人工审核

当以下任一条件满足时，工作流暂停于 `HITL` 节点，等待人工介入：

1. **置信度低于阈值**（默认 0.75）
2. **命中高风险关键词**：死刑、无期、重大财产、强制执行、判决 等
3. **Reviewer 判定需要人工确认**

审核 API：

```bash
# 获取待审核列表
curl http://localhost:8000/hitl/tasks

# 提交审核结果
curl -X POST http://localhost:8000/hitl/review \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "uuid-xxx",
    "action": "approve",
    "modified_answer": "（可选）修改后的答案",
    "comments": "审核意见：此回答准确无误"
  }'

# 获取审核结果
curl http://localhost:8000/hitl/result/{task_id}
```

`action` 支持三种操作：

| 操作 | 含义 |
|------|------|
| `approve` | 直接使用 AI 答案 |
| `reject` | 驳回，要求重新生成 |
| `modify` | 人工修正后批准，使用修正后的答案 |

### MCP 工具

| 工具名称 | 功能 |
|----------|------|
| `legal_rag_search` | 法律知识库混合检索 |
| `calculate_statute_of_limitations` | 诉讼时效智能计算 |
| `calculate_compensation` | 赔偿金额计算 |
| `generate_legal_document` | 法律文书生成 |

---

## API 调用示例

### HTTP 咨询接口

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "朋友借我钱不还，金额5万元，有微信聊天记录和转账记录，我该怎么维权？",
    "session_id": "sess-001"
  }'
```

### WebSocket 实时通信

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/sess-001");

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: "chat",
    message: "朋友欠我钱不还怎么办？"
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === "stream") {
    process.stdout.write(data.content);  // 流式输出
  } else if (data.type === "done") {
    console.log("\n[完整回答]", data.answer);
    console.log("[置信度]", data.confidence);
    console.log("[来源]", data.sources);
  }
};
```

### Python SDK 调用

```python
import requests

# 同步咨询
resp = requests.post("http://localhost:8000/chat", json={
    "message": "公司拖欠工资三个月，可以申请劳动仲裁吗？",
    "session_id": "sess-002"
})
result = resp.json()
print(result["answer"])
print(f"置信度: {result['confidence']:.2%}")
print(f"需要审核: {result['needs_review']}")
```

---

## 项目结构

```
LawBot/
├── src/
│   ├── agents/                    # 多智能体核心 (LangGraph)
│   │   ├── workflow.py            # 工作流编译与节点定义
│   │   ├── state.py               # AgentState 状态模型
│   │   ├── planner.py             # 规划 Agent（意图拆解、查询改写）
│   │   ├── researcher.py           # 检索 Agent（MCP 工具调用）
│   │   ├── analyst.py              # 分析 Agent（法律推理）
│   │   ├── reviewer.py             # 审核 Agent（置信度评估）
│   │   ├── memory_manager.py       # 记忆管理（短期 + 长期）
│   │   ├── llm_client.py           # LLM 客户端（阿里百炼封装）
│   │   └── tools/                  # Agent 专用工具定义
│   ├── rag/                        # 混合 RAG 检索
│   │   ├── hybrid_search.py         # 向量+BM25 融合检索管道
│   │   ├── reranker.py             # BGE-Reranker 重排
│   │   ├── embedding.py            # 向量嵌入模型
│   │   ├── bm25_search.py          # BM25 关键词检索
│   │   ├── query_rewriter.py       # 查询改写（Query Enhancement）
│   │   └── knowledge_base.py        # 知识库接口
│   ├── hitl/                       # HITL 人工审核服务
│   │   └── service.py              # 审核任务管理（创建/批准/驳回）
│   ├── mcp/                        # MCP 工具协议服务器
│   │   └── server.py               # FastMCP 工具注册与暴露
│   ├── api/                        # FastAPI 应用
│   │   ├── main.py                 # 应用入口、路由注册
│   │   ├── tools_api.py            # 工具相关 API
│   │   ├── knowledge_api.py        # 知识库管理 API
│   │   └── session_store.py         # Redis 会话存储
│   ├── db/                         # 数据库层
│   │   ├── models.py               # SQLAlchemy ORM 模型
│   │   └── database.py             # 异步数据库连接
│   ├── config/                     # 配置管理
│   │   └── settings.py             # pydantic-settings 统一配置
│   └── utils/                      # 工具函数
├── frontend/                       # Next.js 前端
│   ├── app/                        # App Router 页面
│   │   ├── page.tsx                # 主聊天页面
│   │   └── knowledge/              # 知识库管理页面
│   ├── components/                 # React 组件
│   │   ├── chat/                   # 聊天组件（消息气泡、输入框）
│   │   ├── sidebar/                # 侧边栏（会话列表）
│   │   └── ui/                     # Radix UI 基础组件
│   └── lib/
│       └── api.ts                  # API 客户端封装
├── tests/                          # 测试
├── models/                         # 本地 Embedding / Reranker 模型
├── logs/                           # 日志输出目录
├── docker-compose.yml              # 中间件 Docker 配置
├── Dockerfile                      # API 镜像构建
├── Dockerfile.streamlit            # Streamlit UI 镜像构建
├── requirements.txt                # Python 依赖
├── run.bat / run.sh               # 一键启动脚本
└── .env                           # 环境变量配置（勿提交至 VCS）
```

---

## License

MIT License
