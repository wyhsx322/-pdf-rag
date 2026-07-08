# PDF RAG 论文知识库与写作助手

一个面向学术论文阅读、检索、问答和写作的本地 Web 应用。项目支持 PDF 入库、图文解析、混合检索、流式 RAG 问答、长期记忆、模型配置，以及多智能体论文大纲和章节写作流程。

仓库地址：[wyhsx322/-pdf-rag](https://github.com/wyhsx322/-pdf-rag)

## 功能特性

- **PDF 知识库**：创建多个知识库，上传 PDF，管理文档状态、切片和向量索引。
- **文档处理流水线**：PDF 转 Markdown，提取图片，生成图表摘要，按页切分文本并写入 ChromaDB。
- **混合检索**：向量检索、BM25 关键词检索、RRF 融合，可选 Query Rewrite、HyDE 和 BGE Reranker。
- **流式 RAG 问答**：基于知识库证据生成答案，并返回来源、页码、chunk 和图表引用。
- **论文写作助手**：创建论文项目，绑定知识库，生成大纲，按章节写作、评审、润色和校验引用。
- **长期记忆**：从问答中提取候选记忆，经人工确认后用于后续回答。
- **运行时配置**：前端设置页可配置 API Key、模型名称和 base URL。

## 技术栈

| 模块 | 技术 |
| --- | --- |
| 后端 | FastAPI, Uvicorn, SQLite |
| 前端 | React 18, TypeScript, Vite, Tailwind CSS, Radix UI, Zustand |
| 向量库 | ChromaDB |
| PDF 解析 | marker-pdf |
| 检索 | DashScope Embedding, jieba, rank-bm25, RRF |
| 生成模型 | DeepSeek Chat compatible API |
| 查询增强 | Qwen Turbo compatible API |
| 图像理解 | Qwen VL compatible API |
| 可选精排 | BAAI/bge-reranker-v2-m3 |
| 包管理 | uv, npm |

## 项目结构

```text
PDF_1.0/
├── server/                  # FastAPI 后端、路由、数据库、写作 Agent
│   ├── main.py              # 应用入口
│   ├── database.py          # SQLite 初始化和连接
│   ├── routers/             # kb、documents、search、chat、agent、settings 等接口
│   └── agents/              # 大纲、写作、评审、引用校验和工作流
├── test/                    # RAG 核心算法与评测脚本
│   ├── pipeline.py          # PDF -> Markdown -> chunks -> ChromaDB
│   ├── hybrid_search.py     # 向量 + BM25 + RRF + 可选 reranker
│   ├── query_processor.py   # Query Rewrite、关键词提取、HyDE
│   └── eval_*.py            # 检索、提示词和写作轨迹评测
├── frontend/                # React 前端
│   └── src/
│       ├── pages/           # Chat、Knowledge、Search、Writing、Settings
│       ├── components/      # 业务组件和 UI 组件
│       ├── api/             # REST/SSE API 封装
│       └── store/           # 前端状态管理
├── docs/                    # 项目文档
├── .env.example             # 环境变量模板
├── pyproject.toml           # Python 依赖配置
├── start.ps1                # Windows 一键启动脚本
└── README.md
```

运行时目录不会提交到 GitHub：

- `data/`：SQLite 数据库
- `output/`：Markdown、图片、切片、ChromaDB 等生成产物
- `primary_datas/`：上传的原始 PDF
- `.env`：本地 API Key
- `server/runtime_config.json`：本地模型配置

## 环境要求

- Windows PowerShell
- Python 3.13 或更高版本
- [uv](https://docs.astral.sh/uv/)
- Node.js 18 或更高版本
- 可选 CUDA GPU：仅启用本地 BGE Reranker 时需要

## 快速开始

### 1. 克隆仓库

```powershell
git clone https://github.com/wyhsx322/-pdf-rag.git
cd -pdf-rag
```

### 2. 安装后端依赖

```powershell
uv sync
```

如果 Web 服务依赖未被安装，可补充安装：

```powershell
.venv\Scripts\python.exe -m pip install fastapi "uvicorn[standard]" python-multipart
```

### 3. 安装前端依赖

```powershell
cd frontend
npm install
cd ..
```

### 4. 配置环境变量

```powershell
copy .env.example .env
```

编辑 `.env`，填入你的本地 Key：

```env
DASHSCOPE_API_KEY=your_dashscope_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

也可以在启动后进入前端 `Settings` 页面配置。API Key 会写入本地 `.env`；模型名称和 base URL 会写入本地 `server/runtime_config.json`。这两个文件都不会提交。

### 5. 启动服务

推荐使用一键脚本：

```powershell
.\start.ps1
```

手动启动：

```powershell
# 后端
.venv\Scripts\python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8000

# 前端
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

访问地址：

- 前端：`http://127.0.0.1:5173`
- 后端健康检查：`http://127.0.0.1:8000/api/health`
- API 文档：`http://127.0.0.1:8000/docs`

## 主要页面

| 路径 | 说明 |
| --- | --- |
| `/` | RAG 问答 |
| `/knowledge` | 知识库列表 |
| `/knowledge/:id` | 文档上传、处理、切片和索引管理 |
| `/search` | 混合检索调试 |
| `/writing` | 论文项目管理 |
| `/writing/:id` | 大纲、写作、评审和 Agent Trace |
| `/writing/:id/section/:sid` | 单章节工作区 |
| `/settings` | API Key、模型配置和连接测试 |

## 核心 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET / POST | `/api/kb` | 列出或创建知识库 |
| GET / DELETE | `/api/kb/{kb_id}` | 获取或删除知识库 |
| GET / POST | `/api/kb/{kb_id}/documents` | 列出或上传 PDF |
| POST | `/api/kb/{kb_id}/batch-process` | 批量处理文档，SSE 返回进度 |
| POST | `/api/chunk/preview` | 预览切片效果 |
| POST | `/api/documents/{doc_id}/process` | 单文档完整处理 |
| POST | `/api/search` | 混合检索 |
| POST | `/api/chat` | 流式 RAG 问答 |
| GET / PUT | `/api/settings` | 查看或更新本地配置 |
| POST | `/api/settings/test` | 测试模型供应商连接 |
| GET / POST | `/api/agent/projects` | 论文项目管理 |

完整接口请以 Swagger 文档为准：`http://127.0.0.1:8000/docs`。

## 评测

```powershell
# 检索评测
.venv\Scripts\python.exe -m test.eval_retrieval

# 启用本地 reranker
.venv\Scripts\python.exe -m test.eval_retrieval --with-reranker

# 写作轨迹评测
.venv\Scripts\python.exe -m test.eval_trajectory
```

评测需要本地已有知识库、向量数据和有效 API Key。

## 上传前安全检查

本仓库默认忽略以下敏感或大体积内容：

- `.env`、`.env.*`
- `server/runtime_config.json`
- `data/`
- `output/`
- `primary_datas/`
- `*.db`、`*.sqlite`、`*.sqlite3`
- `*.log`
- `node_modules/`、`frontend/dist/`
- `.venv/`、`.uv-cache/`

提交前建议执行：

```powershell
git status --short
git diff --cached --name-only
```

不要提交真实 API Key、数据库、上传 PDF、向量库、日志或本地 IDE/工具状态。

## 常见问题

### 为什么没有把 PDF 放进仓库？

`primary_datas/` 是用户上传的原始论文目录，通常包含版权内容和隐私数据，因此不应提交。需要演示数据时，建议单独提供脱敏样例或下载脚本。

### 为什么 `.env` 不提交？

`.env` 包含真实 API Key，只能保存在本地。仓库只提供 `.env.example` 作为配置模板。

### Reranker 是否必须开启？

不是。默认检索已经包含向量检索、BM25 和 RRF。BGE Reranker 会增加本地推理成本，适合需要更强精排且有 GPU 的场景。

## License

MIT
