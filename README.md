# 学术论文 PDF RAG 与论文写作助手

面向论文阅读、文献检索和论文写作的本地 Web 应用。系统提供 PDF 入库、图文解析、混合检索、流式问答、长期记忆、模型配置，以及基于多智能体的论文大纲与章节写作工作流。

## 主要能力

- **知识库管理**：创建工作、学习、个人知识库，上传多篇 PDF，按知识库隔离文档、向量和对话。
- **PDF 处理流水线**：PDF 转 Markdown，提取图片，生成图表摘要，按页切分文本并写入 ChromaDB。
- **混合检索**：DashScope `text-embedding-v4` 向量检索 + `jieba`/BM25 关键词检索 + RRF 融合，可选 Query Rewrite、HyDE 和 BGE Reranker。
- **RAG 问答**：基于 DeepSeek 兼容接口流式生成回答，返回文本来源、页码、chunk、图表引用和长期记忆使用情况。
- **长期记忆**：从对话中生成候选记忆，支持人工批准或拒绝，并在后续问答中注入相关记忆。
- **论文写作助手**：创建论文项目，绑定多个知识库，生成/确认大纲，按章节写作、评审、引用校验、润色，并记录 Agent Trace。
- **运行时模型配置**：在前端配置 DashScope、DeepSeek API Key，以及生成、向量、查询改写、视觉、Reranker 模型。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | FastAPI, Uvicorn, SQLite |
| 前端 | React 18, TypeScript, Vite, Tailwind CSS, Radix UI, Zustand |
| 向量库 | ChromaDB 本地持久化 |
| PDF 解析 | marker-pdf |
| Embedding | DashScope `text-embedding-v4` |
| 查询增强 | Qwen `qwen-turbo` |
| 图表摘要 | Qwen `qwen-vl-plus` |
| 问答生成 | DeepSeek `deepseek-chat` |
| 可选精排 | `BAAI/bge-reranker-v2-m3` |
| 检索评测 | Recall@K, Precision@K, MRR, NDCG@K |

## 目录结构

```text
PDF_1.0/
├── server/                  # FastAPI 应用、API 路由、数据库和论文写作 Agent
│   ├── main.py              # 应用入口、路由注册、图片静态服务
│   ├── database.py          # SQLite 表结构和连接管理
│   ├── routers/             # kb、documents、chunking、search、chat、agent 等接口
│   └── agents/              # 文献、提纲、写作、评审、引用校验、工作流
├── test/                    # RAG 核心算法、处理流水线、评测脚本
│   ├── pipeline.py          # PDF -> Markdown -> chunks -> ChromaDB
│   ├── hybrid_search.py     # 向量 + BM25 + RRF + 可选 reranker
│   ├── query_processor.py   # Query Rewrite、关键词提取、HyDE
│   └── eval_*.py            # 检索、提示词、写作轨迹评测
├── frontend/                # React 前端
│   └── src/
│       ├── pages/           # Chat、Knowledge、Search、Writing、Settings
│       ├── components/      # 通用组件和业务组件
│       ├── api/client.ts    # REST/SSE API 封装
│       └── store/           # 前端状态
├── docs/                    # 项目文档和规划材料
├── data/                    # SQLite 数据库，运行时生成，不应提交
├── output/                  # Markdown、图片、切片、ChromaDB 等产物，不应提交
├── primary_datas/           # 上传的原始 PDF，不应提交
├── start.ps1                # Windows 一键启动脚本
├── pyproject.toml           # Python/uv 依赖
└── frontend/package.json    # 前端依赖和脚本
```

## 环境要求

- Windows PowerShell
- Python `>=3.13`
- [uv](https://docs.astral.sh/uv/)（推荐用于安装 Python 依赖）
- Node.js `>=18`
- 可选 CUDA GPU：仅在启用本地 BGE Reranker 时需要，CPU 也可运行但会更慢

## 安装

```powershell
git clone https://github.com/wyhsx322/-pdf-rag.git
cd -pdf-rag

# 安装 Python 依赖
uv sync

# 如缺少 Web 服务依赖，可补装
.venv\Scripts\python.exe -m pip install fastapi "uvicorn[standard]" python-multipart

# 安装前端依赖
cd frontend
npm install
cd ..
```

## 配置

复制示例环境变量文件并填写真实 Key：

```powershell
copy .env.example .env
```

必需配置：

```env
DASHSCOPE_API_KEY=sk-xxxxxxxx
DEEPSEEK_API_KEY=sk-xxxxxxxx
```

也可以启动后进入前端「设置」页面配置 API Key 和模型。前端保存的运行时配置会写入 `server/runtime_config.json`，该文件可能包含明文密钥，只应保留在本地，不要提交到 GitHub。

## 启动

推荐使用一键脚本：

```powershell
.\start.ps1
```

脚本会启动：

- 前端：`http://127.0.0.1:5173/writing`
- 后端：`http://127.0.0.1:8000`
- API 文档：`http://127.0.0.1:8000/docs`

手动启动：

```powershell
# 窗口 1：后端
.venv\Scripts\python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8000

# 窗口 2：前端
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

## 前端页面

| 路径 | 说明 |
| --- | --- |
| `/` | RAG 问答，支持引用、图表来源、长期记忆候选审批 |
| `/knowledge` | 知识库列表、创建和删除 |
| `/knowledge/:id` | 文档上传、批量处理、切片预览、向量统计、重建索引 |
| `/search` | 混合检索调试，展示诊断指标和得分 |
| `/writing` | 论文项目管理，绑定知识库和研究方法 |
| `/writing/:id` | 大纲生成、Agent 工作流、章节写作与评审 |
| `/writing/:id/section/:sid` | 单章节写作、润色、格式和图片替换 |
| `/settings` | API Key、模型和连接测试 |

## 关键 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | `/api/kb` | 列出或创建知识库 |
| GET/DELETE | `/api/kb/{kb_id}` | 获取或删除知识库 |
| GET/POST | `/api/kb/{kb_id}/documents` | 列出或上传 PDF |
| POST | `/api/kb/{kb_id}/batch-import` | 从本地目录批量导入 PDF |
| POST | `/api/kb/{kb_id}/batch-process` | 批量解析、切片和入库，SSE 返回进度 |
| POST | `/api/chunk/preview` | 预览切片效果 |
| POST | `/api/documents/{doc_id}/process` | 单文档完整处理 |
| POST | `/api/documents/{doc_id}/chunk` | 单文档切片并入库 |
| GET/DELETE | `/api/documents/{doc_id}/vector-stats`、`/api/documents/{doc_id}/vectors` | 查看或删除向量 |
| POST | `/api/documents/{doc_id}/reindex` | 重建文档索引 |
| POST | `/api/search` | 混合检索 |
| POST | `/api/chat` | 流式 RAG 问答 |
| GET/POST | `/api/conversations` | 对话历史管理 |
| GET/PUT/POST | `/api/settings`、`/api/settings/test` | 模型配置和连接测试 |
| GET/POST | `/api/memory/long-term/*` | 长期记忆候选、条目和使用记录 |
| GET/POST/DELETE | `/api/agent/projects*` | 论文项目、大纲、章节写作、评审、引用校验和工作流 |

完整接口以启动后的 Swagger 文档为准：`http://127.0.0.1:8000/docs`。

## 数据处理流程

1. 上传或批量导入 PDF，原文保存到 `primary_datas/`。
2. `marker-pdf` 将 PDF 解析为 Markdown，并提取图片到 `output/markd_demo/`。
3. Qwen-VL 对图表生成结构化摘要，摘要作为可检索 chunk 参与入库。
4. 文本按页切分，保留页码、来源、图片、脚注等元数据。
5. DashScope 生成 1024 维向量，写入知识库级 ChromaDB 集合。
6. 检索时执行向量召回和 BM25 召回，使用 RRF 融合，可选 Query Rewrite、HyDE、Reranker。
7. 问答时将 Top-K 证据、对话历史和长期记忆传入生成模型，SSE 流式返回答案与来源。

## 评测

```powershell
# 检索评测
.venv\Scripts\python.exe -m test.eval_retrieval

# 启用本地 Reranker 的检索评测
.venv\Scripts\python.exe -m test.eval_retrieval --with-reranker

# 多智能体写作轨迹评测
.venv\Scripts\python.exe -m test.eval_trajectory
```

评测依赖本地已有的知识库、向量数据和有效 API Key。

## Git 与数据安全

以下内容属于本地运行数据或敏感信息，不应提交：

- `.env`
- `server/runtime_config.json`
- `data/`
- `output/`
- `primary_datas/`
- `frontend/dist/`
- `*.log`
- `frontend/tsconfig.tsbuildinfo`

当前仓库已有 `.gitignore` 忽略多数运行目录；提交前仍建议使用 `git status --short` 检查是否误暂存了密钥、数据库、PDF 或构建产物。

## License

MIT
