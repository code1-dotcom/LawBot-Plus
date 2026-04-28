# LawBot+：带人类介入的多智能体法律咨询系统 - 项目架构设计

## 1. 项目概述
LawBot+ 是一个面向法律领域的 **人机协同多智能体系统**。系统深度融合 2025-2026 年企业级 RAG 与 Agent 最佳实践，通过引入高级检索、动态知识库、标准化 MCP 工具调用、持久化记忆及主动式 HITL 机制，在保障法律专业性的同时，彻底解决大模型幻觉与高风险决策难题。系统采用 **阿里百炼免费 API** 作为核心推理底座，通过 **轻量化部署策略（仅中间件容器化）**，确保项目开箱即用、稳定可靠。

## 2. 核心设计原则
| 原则                 | 说明                                                         |
| :------------------- | :----------------------------------------------------------- |
| **领域专业性**       | 深度集成结构化法律知识库，结合父子文档索引与摘要增强，确保回答具备法理依据与精准溯源能力。 |
| **高级检索与重排**   | 采用查询理解改写、混合检索、多路召回与交叉编码器重排序，实现语义与术语的双重高精准匹配。 |
| **多智能体协作**     | 基于 LangGraph 状态机实现角色专业化（规划/检索/分析/审核），通过 MCP 协议标准化通信与任务委派。 |
| **人机协同 (HITL)**  | Agent 在低置信度或高风险节点主动暂停，无缝推送至专家审查端，支持修正/批准后恢复工作流。 |
| **持久化记忆与治理** | 维护短期会话上下文与长期用户/案例记忆；全链路日志追踪、内置评估管道，保障合规、可审计与持续优化。 |
| **轻量化工程部署**   | 核心服务原生 Python 运行，仅 Redis/PostgreSQL 等中间件 Docker 化；统一接入阿里百炼 API，免除本地 GPU 与模型量化负担。 |

## 3. 系统整体架构
系统采用 **分层微服务架构**，核心流向如下：
```mermaid
graph TD
    A[用户] -->|HTTP/WebSocket| B(Web UI / Client)
    B --> C[API Gateway & FastAPI]
    C --> D[LawBot+ Application Service]
    D --> E[Multi-Agent Core Engine (LangGraph)]
    E --> F[MCP Tool Server (FastMCP)]
    E --> G[Advanced RAG Pipeline]
    E --> H[阿里百炼 LLM API]
    D --> I[HITL Review Service]
    D --> J[Task Queue (Celery)]
    E --> K[Memory & State Store]
    F --> L[External Legal APIs / Calculators]
    G --> M[Vector DB (pgvector)]
    G --> N[Doc Store (PostgreSQL)]
    K --> O[Session & Long-term Memory DB]
    D --> P[Observability & Eval Pipeline]
    style A fill:#9f9,stroke:#333
    style B fill:#ccf,stroke:#333
    style C fill:#cfc,stroke:#333
    style D fill:#fcc,stroke:#333
    style E fill: #ffc,stroke:#333
    style F fill:#cff,stroke:#333
    style G fill:#cff,stroke:#333
    style H fill:#f9f,stroke:#333
    style I fill:#fcc,stroke:#333
    style J fill:#cfc,stroke:#333
    style K fill:#cff,stroke:#333
    style L fill:#ccc,stroke:#333
    style M fill:#ccc,stroke:#333
    style N fill:#ccc,stroke:#333
    style O fill:#ccc,stroke:#333
    style P fill:#ffd,stroke:#333
```

## 4. 核心模块详细设计

### 4.1 用户交互层 (UI Layer)
- **职责**: 提供法律咨询对话界面、多智能体协作过程可视化、专家审查工作台及评估看板。
- **技术选型**: `Streamlit` / `Gradio` (支持快速迭代与组件化)
- **核心功能**:
  - 实时流式展示 Agent 思考链、检索来源与重排结果。
  - **HITL 专家端**: 独立视图展示待审任务、AI 推理依据、风险等级，支持一键批准/批注修改。
  - **溯源与评估面板**: 清晰展示最终答案引用的法条/案例片段，内置人工打分与自动化指标反馈。

### 4.2 API 网关与应用服务层 (API & Application Layer)
- **职责**: 请求路由、异步任务调度、HITL 协调、全链路日志与监控。
- **技术选型**: `FastAPI`, `Celery`, `Redis`
- **核心组件**:
  - **FastAPI 服务**: 提供 `/chat`, `/task/{id}`, `/review` 等 REST/WebSocket 接口。接收请求后生成 `task_id`，推入 Celery 队列。
  - **Celery 异步队列**: 处理耗时 Agent 工作流与 RAG 检索。支持失败重试、优先级调度。
  - **HITL 审查服务**: 当 Agent 状态 `needs_review=True` 时，冻结工作流，持久化待审数据，通过 WebSocket 推送至专家端。专家提交后自动注入状态并恢复执行。
  - **可观测性集成**: 对接 OpenTelemetry 或 LangSmith，记录每个节点的 Token 消耗、延迟、工具调用参数。

### 4.3 核心智能体引擎层 (Core Agent Engine Layer)
- **职责**: 系统大脑，负责任务规划、状态流转、记忆管理与多智能体协同。
- **技术选型**: `LangGraph`, `LangChain`, `MCP Client`
- **核心组件**:
  - **状态定义 (`StateGraph`)**: 包含 `user_input`, `rewritten_query`, `messages`, `current_agent`, `needs_review`, `confidence_score`, `final_answer`, `sources`, `memory_context`。
  - **智能体节点**:
    - `Planner (规划者)`: 意图识别 → 任务分解（案由识别/法条检索/风险比对/文书生成）→ 路由决策。
    - `Researcher (研究员)`: 调用高级 RAG Pipeline 获取多源法律依据，支持元数据过滤与版本追溯。
    - `Analyst (分析师)`: 结合检索上下文与长期记忆，进行逻辑推理与初步结论生成。
    - `Reviewer (AI审核者)`: 基于规则与置信度阈值评估风险。高风险/低置信度 → 触发 HITL；安全 → 直接输出。
    - `Memory Manager`: 维护短期会话窗口，并将关键结论/用户偏好写入长期记忆库（向量/图结构）。
  - **LLM 集成**: 统一接入 **阿里百炼 API**（如 `qwen-turbo`, `qwen-plus`），支持 OpenAI 兼容协议调用。通过 LangChain `ChatOpenAI` 适配，配置 API Key 与速率限制。

### 4.4 MCP 工具服务器 (MCP Tool Server)
- **职责**: 外部能力标准化网关，提供安全、隔离、可插拔的工具调用。
- **技术选型**: `FastMCP`
- **核心工具**:
  - `legal_rag_search`: 封装高级 RAG 查询逻辑。
  - `legal_calculator`: 诉讼时效、赔偿金、违约金计算。
  - `doc_template_gen`: 起诉状/答辩状/合同模板生成。
  - `external_api_proxy`: 安全代理官方裁判文书网、国家法律法规数据库。
- **安全机制**: 工具调用前进行权限校验（RBAC），执行环境采用沙箱隔离，严格限制文件系统与网络访问，防止越权操作。

### 4.5 高级 RAG 知识库 (Advanced RAG Knowledge Base)
- **职责**: 提供准确、可溯源、动态更新的法律事实锚点。
- **技术选型**: `LlamaIndex` / `LangChain`, `PostgreSQL` + `pgvector`
- **核心能力**:
  - **查询理解与改写**: 检索前进行意图分类、实体抽取、同义词/法言法语改写。
  - **混合检索与重排序**: 向量检索（BGE-Embedding） + BM25 关键词检索 → 多路结果融合 → `bge-reranker` 交叉编码器精细化打分。
  - **父子文档索引**: 文档按语义切块（子文档）用于检索，保留父章节上下文用于生成，解决碎片化问题。
  - **动态知识库管理**: 支持增量更新（无需全量重建）、多版本控制（记录法规生效/废止时间）、元数据过滤（按密级/部门/地域/时间筛选）。
  - **可观测与评估**: 内置检索相关性评估管道，自动记录命中率、重排准确率，支持 TruLens 或人工抽检。

### 4.6 数据与知识层 (Data & Knowledge Layer)
- **职责**: 持久化存储业务数据、向量索引、记忆状态与审计日志。
- **技术选型**: `PostgreSQL`, `Redis`
- **数据表设计**:
  - `tasks`: 任务ID、状态、耗时、Token统计、创建/更新时间。
  - `conversations` & `messages`: 完整对话历史、AI 推理链、引用来源。
  - `documents` & `versions`: 原始法律文档、切块元数据、版本号、生效状态、访问权限。
  - `vectors` (`pgvector`): 存储文档 Embedding，支持元数据联合查询。
  - `long_term_memory`: 用户画像、历史案例摘要、高频问题偏好。
  - `eval_logs`: 检索质量评分、人工修正记录、Agent 决策置信度。
- **缓存与代理 (Redis)**: Celery Broker/Backend、高频查询缓存、会话状态临时存储。

## 5. 关键工作流：企业级人机协同咨询流程
1. **用户提问**: 通过 Web UI 提交复杂法律问题。
2. **任务分发**: FastAPI 生成 `task_id`，推入 Celery 队列，返回轮询/WS 连接。
3. **规划与改写**: `Planner` 拆解子任务，`Query Rewriter` 生成法言法语检索式。
4. **高级检索**: `Researcher` 触发混合检索 → 多路召回 → `bge-reranker` 重排 → 提取父子上下文。
5. **推理与分析**: `Analyst` 结合重排结果、元数据过滤与长期记忆，生成初步意见。
6. **AI 风险评估**: `Reviewer` 校验置信度与风险等级。若触发阈值：
   - 工作流暂停，状态存入 DB。
   - HITL 服务推送至专家端，展示完整推理链与依据。
7. **专家审查 (HITL)**: 律师核对法条适用性、修正逻辑漏洞或一键批准。
8. **工作流恢复**: 专家意见注入 Agent 状态，`Analyst` 融合后生成终稿。
9. **记忆更新与评估**: 关键结论写入长期记忆库，评估管道记录本次交互质量。
10. **结果交付**: 终稿与溯源片段存入 DB，Celery 标记完成，用户端实时展示。

## 6. 部署与运维策略（轻量化实践）
| 模块                                                      | 部署方式                                                | 说明                                                         |
| :-------------------------------------------------------- | :------------------------------------------------------ | :----------------------------------------------------------- |
| **核心应用服务** (FastAPI, Celery Worker, MCP Server, UI) | **原生 Python 运行**                                    | 使用 `venv`/`conda` 管理依赖，提供 `requirements.txt` 与一键启动脚本 `run.sh`。无需 Docker，降低本地/服务器运行门槛。 |
| **中间件** (PostgreSQL, Redis)                            | **Docker Compose 容器化**                               | 仅对状态服务进行容器隔离，保证数据一致性与快速环境搭建。提供 `docker-compose.middleware.yml`。 |
| **大模型推理**                                            | **阿里百炼 API**                                        | 统一通过环境变量 `DASHSCOPE_API_KEY` 接入免费/配额模型。免除本地 GPU、vLLM、模型量化配置，开箱即用且成本可控。 |
| **监控与日志**                                            | **本地文件 + 可选云平台**                               | 默认输出结构化 JSON 日志至 `logs/` 目录，集成 LangSmith/OpenTelemetry 可选插件，便于调试与审计。 |
| **启动命令示例**                                          | `pip install -r requirements.txt && python -m src.main` | 中间件通过 `docker compose -f docker-compose.middleware.yml up -d` 启动后，直接运行主程序即可完整跑通。 |

> **架构演进说明**：本设计严格对齐 2025-2026 年企业级 RAG/Agent 标准，在保留原 LawBot+ 多智能体协作与 HITL 核心优势的基础上，全面升级了检索精度、记忆管理、工具安全与可观测性，并通过 **API 云端化 + 中间件容器化** 策略，实现“零 GPU 依赖、低运维成本、高可用交付”的工程目标。