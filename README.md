# 论文 RAG 系统

基于检索增强生成（RAG）的学术论文智能问答系统。支持 PDF 论文的自动解析、智能切片、向量化存储、混合检索和多轮对话问答。

## 核心功能

- **知识库管理** — 创建/删除知识库（工作/学习/个人类型），上传和管理 PDF 论文
- **PDF 智能解析** — 基于 marker-pdf 将 PDF 转换为 Markdown，自动提取文中图片并生成 AI 摘要
- **智能切片** — 支持递归、句子、段落、固定长度四种切片策略，自动识别并移除参考文献，保护表格结构
- **混合检索** — 语义向量检索 + BM25 关键词检索双路召回，RRF 融合排序，可选 BGE-Reranker 重排序
- **查询增强** — LLM 驱动的多视角查询改写、关键词提取、HyDE 假设文档生成
- **RAG 对话问答** — 基于 DeepSeek-Chat 的流式生成回答，严格来源引用，支持多轮对话记忆
- **用量统计** — 各模型 Token 消耗与费用估算，支持按操作类型聚合查询

## 技术架构

```
前端 (React + TypeScript + Vite + Tailwind CSS)
        │
        ▼
后端 (FastAPI Python)
        │
        ├── 知识库管理 ──► SQLite
        ├── 文档处理   ──► marker-pdf (PDF → Markdown)
        ├── 切片服务   ──► langchain-text-splitters
        ├── 检索服务   ──► ChromaDB 向量库 + BM25
        ├── 对话服务   ──► DeepSeek / DashScope LLM
        └── 用量追踪   ──► SQLite
```

## 流水线架构

```
PDF 论文
  │
  ├── marker-pdf 解析 ──► Markdown（含页码标记）
  │                         │
  │                         ├── 文本切片 ──► JSON Chunks
  │                         │                  │
  │                         │                  ▼
  │                         │          DashScope Embedding
  │                         │                  │
  │                         │                  ▼
  │                         │          ChromaDB 向量库
  │                         │
  │                         └── 图片提取 ──► qwen-vl-plus 摘要
  │                                               │
  │                                               ▼
  │                                       向量化存储（可检索）
  │
  └── SHA256 哈希注册表（增量更新，跳过未修改文件）
```

## 支持的模型

| 模型 | 提供商 | 用途 |
|------|--------|------|
| `text-embedding-v4` (1024维) | DashScope（阿里云） | 文本向量化 |
| `qwen-turbo` | DashScope | 查询改写、关键词提取 |
| `qwen-vl-plus` | DashScope | 图片摘要（多模态） |
| `deepseek-chat` | DeepSeek | RAG 答案生成 |
| `BAAI/bge-reranker-v2-m3` | 本地（ModelScope） | 检索结果重排序 |

## 快速开始

### 环境要求

- Python >= 3.13
- Node.js >= 18
- CUDA 12.6（用于本地 BGE-Reranker 模型推理）

### 1. 克隆项目

```bash
git clone https://github.com/wyhsx322/-pdf-rag.git
cd -pdf-rag
```

### 2. 配置 API Key

在项目根目录创建 `.env` 文件：

```env
DASHSCOPE_API_KEY=your_dashscope_api_key
DEEPSEEK_API_KEY=your_deepseek_api_key
```

> 申请地址：[DashScope API Key](https://dashscope.console.aliyun.com/apiKey) | [DeepSeek API Key](https://platform.deepseek.com/api_keys)

### 3. 安装 Python 依赖

```bash
# 使用 uv 包管理器
uv sync
```

### 4. 安装前端依赖

```bash
cd frontend
npm install
```

### 5. 启动服务

**后端**（默认 http://127.0.0.1:8000）：

```bash
uvicorn server.main:app --reload --host 127.0.0.1 --port 8000
```

**前端**（默认 http://localhost:5173）：

```bash
cd frontend
npm run dev
```

访问 http://localhost:5173 即可使用。

## 项目结构

```
PDF_1.0/
├── server/                  # FastAPI 后端
│   ├── main.py              # 应用入口、路由注册
│   ├── database.py          # SQLite 数据库初始化
│   ├── models.py            # Pydantic 数据模型
│   ├── usage_tracker.py     # Token 用量与费用追踪
│   └── routers/             # API 路由
│       ├── kb.py            # 知识库 CRUD
│       ├── documents.py     # 文档上传/管理
│       ├── chunking.py      # 切片配置与执行
│       ├── search.py        # 混合检索
│       ├── chat.py          # 流式 RAG 问答
│       ├── usage.py         # 用量查询
│       └── conversations.py # 对话历史管理
├── frontend/                # React 前端
│   └── src/
│       ├── pages/           # 页面组件
│       ├── components/      # 通用组件
│       ├── api/             # API 请求封装
│       └── types/           # TypeScript 类型定义
├── test/                    # 核心处理逻辑
│   ├── config.py            # 集中配置
│   ├── pipeline.py          # 流水线编排
│   ├── single_file_parser.py # PDF 解析
│   ├── text_splitter.py     # 文本切片
│   ├── figure_extractor.py  # 图片提取
│   ├── image_summarizer.py  # 图片 AI 摘要
│   ├── vector_store.py      # 向量存储
│   ├── hybrid_search.py     # 混合检索
│   ├── query_processor.py   # 查询增强
│   ├── rag_generator.py     # RAG 生成
│   ├── eval_retrieval.py    # 检索评测
│   └── document_processor.py # 文档处理门面
└── primary_datas/           # 原始论文 PDF 数据
```

## License

MIT
