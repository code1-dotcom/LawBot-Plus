# LawBot+

基于LangGraph的多智能体法律咨询系统，支持人机协同审核（HITL）、高级RAG检索、MCP工具协议。

## 系统要求

- Python 3.10+
- Conda 环境: `lawbot-plus`
- Docker & Docker Compose（用于PostgreSQL和Redis）
- 显存 4GB+（如使用本地Embedding模型）

## 快速开始

### 1. 环境配置

```bash
# 创建并激活conda环境
conda create -n lawbot-plus python=3.11
conda activate lawbot-plus

# 安装依赖
pip install -r requirements.txt
```

### 2. 启动中间件

```bash
# 启动PostgreSQL + Redis
docker compose -f docker-compose.middleware.yml up -d
```

### 3. 配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑.env文件，填入你的阿里百炼API Key
# DASHSCOPE_API_KEY=your_api_key_here
```

### 4. 下载Embedding模型（可选）

RTX 3050 4G推荐使用轻量模型：

```bash
# BGE-small-zh-v1.5 (512维，4G显存可运行)
# 下载地址: https://www.modelscope.cn/models/BAAI/bge-small-zh-v1.5

# BGE-reranker-base
# 下载地址: https://www.modelscope.cn/models/BAAI/bge-reranker-base
```

将模型解压到 `./models/` 目录。

### 5. 启动服务

```bash
# Windows
run.bat

# Linux/macOS
chmod +x run.sh
./run.sh
```

服务地址：
- API文档: http://localhost:8000/docs
- Web界面: http://localhost:8000
- WebSocket: ws://localhost:8000/ws/{session_id}

## 项目结构

```
LawBot/
├── src/
│   ├── agents/          # 多智能体核心
│   │   ├── workflow.py  # LangGraph工作流
│   │   ├── planner.py   # 规划Agent
│   │   ├── researcher.py# 检索Agent
│   │   ├── analyst.py   # 分析Agent
│   │   ├── reviewer.py  # 审核Agent
│   │   └── memory_manager.py
│   ├── rag/             # 高级RAG
│   │   ├── embedding.py # 向量模型
│   │   ├── reranker.py  # 交叉编码器
│   │   ├── hybrid_search.py # 混合检索
│   │   └── knowledge_base.py
│   ├── mcp/             # MCP工具服务器
│   ├── api/             # FastAPI服务
│   ├── db/              # 数据库模型
│   ├── hitl/            # HITL审核服务
│   └── config/          # 配置管理
├── tests/               # 测试
├── models/              # 本地模型
├── logs/                # 日志
├── docker-compose.middleware.yml
└── requirements.txt
```

## 核心功能

### 多智能体协作

```
用户输入 → Planner(规划) → Researcher(检索) → Analyst(分析) → Reviewer(审核)
                                                              ↓
                                                    [置信度低/高风险?]
                                                              ↓
                                                    HITL人工审核 ←→ Memory(记忆)
                                                              ↓
                                                          Finalize(输出)
```

### HITL人工审核

当系统置信度低于阈值或检测到高风险关键词时，会暂停工作流等待人工审核。

审核API:
```bash
# 获取待审核列表
GET /hitl/tasks

# 提交审核结果
POST /hitl/review
{
    "task_id": "xxx",
    "action": "approve|reject|modify",
    "modified_answer": "修改后的答案",
    "comments": "审核意见"
}
```

### MCP工具

系统提供以下MCP工具：
- `legal_rag_search`: 法律知识检索
- `calculate_statute_of_limitations`: 诉讼时效计算
- `calculate_compensation`: 赔偿计算
- `generate_legal_document`: 法律文书生成

## API示例

```python
import requests

# 法律咨询
response = requests.post("http://localhost:8000/chat", json={
    "message": "朋友借我钱不还怎么办？"
})
print(response.json())
```

## 许可证

MIT License
