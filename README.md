# 学术论文 RAG 系统

> 面向研究生和科研人员的学术论文智能问答平台。支持多文档知识库管理、四阶段混合检索、多视角查询增强和多模态图文问答，提供完整的前后端和检索评测框架。

---

## 检索评测结果

8 条跨论文测试查询，覆盖精确匹配、方法检索、理论框架检索、跨文档联合查询四类场景：

| 检索策略 | Recall@5 | Recall@10 | MRR | NDCG@10 |
|---------|:-------:|:-------:|:---:|:-------:|
| A — 向量 + BM25 + RRF（基线） | 0.7917 | 0.8542 | 0.6667 | 0.8191 |
| C — RRF + 查询多视角改写 ★ | **0.8542** | **0.9271** | **0.7917** | **0.8767** |
| D — RRF + 改写 + BGE-Reranker | 0.8333 | 0.9167 | 0.7917 | 0.8699 |

查询改写（C 组）将 Recall@10 从 85.4% 提升至 **92.7%**，且无需 GPU 资源。

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                  前端（React 18 + TypeScript + Tailwind CSS）     │
│                                                                 │
│  知识库管理   文档处理进度   智能切片预览   检索测试   多轮问答    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ REST API / Server-Sent Events
┌──────────────────────────▼──────────────────────────────────────┐
│                      后端（FastAPI + Uvicorn）                    │
│                                                                 │
│  /api/kb  /api/documents  /api/chunk  /api/search  /api/chat   │
└───────┬──────────────────┬──────────────────┬───────────────────┘
        │                  │                  │
        ▼                  ▼                  ▼
  ┌──────────┐    ┌──────────────┐    ┌────────────────────────┐
  │  SQLite  │    │   ChromaDB   │    │    算法层（test/）        │
  │  元数据   │    │  1024维向量  │    │                        │
  │  对话历史 │    │  KB级单集合  │    │  PDF → Markdown        │
  │  用量日志 │    │  cosine相似度│    │  图片提取 + VL摘要      │
  └──────────┘    └──────────────┘    │  文本切分 → 向量入库    │
                                      └────────────────────────┘
```

### 四阶段混合检索流程

```
用户查询
   │
   ├─[预处理] QueryProcessor（Qwen-turbo）
   │   ├─ 多视角改写：生成 2-3 个语义变体，扩大向量检索覆盖面
   │   ├─ 关键词提取：提取 3-5 个核心术语，增强 BM25 精准度
   │   └─ HyDE（可选）：生成假设学术段落，缩小 query-doc 语义鸿沟
   │
   ├─[第一路] 向量检索
   │   DashScope text-embedding-v4（1024维）→ ChromaDB cosine → Top-20
   │
   ├─[第二路] BM25 关键词检索
   │   jieba 中文分词 → rank-bm25 → Top-20
   │
   ├─[融合] RRF 倒数排名融合（K=60）
   │   只依赖排名而非原始分数，消除两路分数量纲差异，无需手动调权重
   │
   └─[可选精排] BGE-Reranker v2-m3（Cross-Encoder，本地 GPU）
       对 Top-20 候选进行逐对精排，无需额外 API 调用
```

---

## 功能特性

### 文档处理流水线
- **PDF 解析**：marker-pdf 保留公式、表格、图片的原始布局
- **多模态图片摘要**：Qwen-VL-Plus 为每张图表生成结构化描述（含图表类型、关键元素），摘要文本参与向量检索
- **智能文本切分**：表格整块保护（临时替换为占位符后还原），自动移除参考文献段，脚注独立存储至 chunk 元数据
- **四种切片策略**：recursive / sentence / paragraph / fixed，chunk_size 和 overlap 在线可调，切片效果实时预览
- **SHA-256 去重**：上传时校验文件哈希，跳过已入库的相同文件

### RAG 问答
- DeepSeek-chat 流式生成，Server-Sent Events 实时推送
- 系统提示词包含 Chain-of-Thought 思维链 + 2 个学术领域 Few-shot 示例
- 回答强制结构化：核心结论 → 详细分析（分点标注来源）→ 不同观点 → 局限性说明
- 自动引用来源（文件名 + 页码 + chunk_id），聊天界面内联展示论文图片
- 多轮对话记忆（最近 20 条消息上下文）

### 工程能力
- **KB 级单集合架构**：同一知识库所有文档共用一个 ChromaDB 集合，通过 `doc_id` 元数据字段过滤，避免集合数量随文档增长而爆炸
- **批量处理 SSE**：批量入库时逐文档实时推送处理进度（解析/切分/向量化三步）
- **成本追踪**：自动记录每次 embedding、问答的 token 消耗和费用估算，支持按模型/操作聚合查询
- **检索评测框架**：Recall@K、Precision@K、MRR、NDCG@K 四项指标，A/C/D 策略组横向对比

---

## 技术栈

| 层次 | 技术选型 |
|------|---------|
| 后端框架 | FastAPI + Uvicorn |
| 前端框架 | React 18 + TypeScript + Tailwind CSS + Vite |
| 向量数据库 | ChromaDB（本地持久化，cosine 相似度） |
| 关系数据库 | SQLite（元数据 + 对话历史 + 用量日志） |
| Embedding 模型 | DashScope text-embedding-v4（1024 维） |
| Reranker 模型 | BAAI/bge-reranker-v2-m3（本地 GPU 推理） |
| 问答 LLM | DeepSeek-chat（流式输出） |
| 查询增强 LLM | Qwen-turbo（改写 / 关键词提取，低延迟） |
| 多模态 LLM | Qwen-VL-Plus（图表摘要） |
| PDF 解析 | marker-pdf 1.6.1 |
| 文本切分 | langchain-text-splitters（递归分割） |
| 关键词检索 | rank-bm25 + jieba 中文分词 |
| 深度学习 | PyTorch 2.5 + sentence-transformers 4.x |
| 包管理 | uv（Python 3.13+） |

---

## 快速开始

### 环境要求

- Python >= 3.13，推荐使用 [uv](https://docs.astral.sh/uv/)
- Node.js >= 18
- CUDA GPU（BGE-Reranker 本地推理，可选；CPU 模式较慢）

### 1. 克隆与安装

```powershell
git clone https://github.com/wyhsx322/-pdf-rag.git
cd -pdf-rag

# 创建虚拟环境并安装 Python 依赖（uv 会自动处理 PyTorch CUDA 版本）
uv sync

# 安装 Web 服务依赖（fastapi / uvicorn 未写入 pyproject.toml，需单独安装）
.venv\Scripts\python.exe -m pip install fastapi "uvicorn[standard]" python-multipart

# 安装前端依赖
cd frontend && npm install && cd ..
```

### 2. 配置 API Key

```powershell
# 复制示例文件并填写 Key（Windows）
copy .env.example .env
# 用记事本或编辑器打开 .env，填入真实 Key
```

```env
DASHSCOPE_API_KEY=sk-xxxxxxxx   # 阿里云 DashScope（embedding + Qwen 系列）
DEEPSEEK_API_KEY=sk-xxxxxxxx    # DeepSeek（问答生成）
```

申请地址：[DashScope](https://dashscope.console.aliyun.com/apiKey) | [DeepSeek](https://platform.deepseek.com/api_keys)

### 3. 启动服务

#### 方式一：一键启动（推荐，Windows PowerShell）

```powershell
.\start.ps1
```

脚本会自动弹出两个终端窗口分别运行后端和前端。

#### 方式二：手动分窗口启动

```powershell
# 窗口 1 — 后端（http://localhost:8000，API 文档见 /docs）
.venv\Scripts\python.exe -m uvicorn server.main:app --reload --host 0.0.0.0 --port 8000

# 窗口 2 — 前端（http://localhost:5173）
cd frontend
npm run dev
```

> **注意**：必须使用项目虚拟环境（`.venv`）中的 Python，系统环境没有所需依赖。
> 不要直接运行 `uvicorn`，应使用 `python -m uvicorn`。

### 4. 运行检索评测

```powershell
# A/C 两组对比（无需 GPU，约 2 分钟）
.venv\Scripts\python.exe -m test.eval_retrieval

# 加入 Reranker B/D 组（需要 CUDA GPU）
.venv\Scripts\python.exe -m test.eval_retrieval --with-reranker
```

---

## 项目结构

```
PDF_1.0/
├── server/                     # FastAPI 后端
│   ├── main.py                 # 应用入口、路由注册、图片安全服务
│   ├── database.py             # SQLite 连接与表结构初始化
│   ├── models.py               # Pydantic 请求 / 响应模型
│   ├── usage_tracker.py        # Token 用量追踪与费用估算
│   └── routers/
│       ├── kb.py               # 知识库 CRUD（含向量库级联删除）
│       ├── documents.py        # 上传、删除、重建索引、向量统计
│       ├── chunking.py         # 切片预览、执行、批量处理（SSE）
│       ├── search.py           # 混合检索（四阶段流程）
│       ├── chat.py             # 流式 RAG 问答（SSE）
│       ├── conversations.py    # 对话历史管理
│       └── usage.py            # 用量与费用统计查询
│
├── test/                       # 核心算法层（与 FastAPI 解耦）
│   ├── config.py               # 集中配置（模型名、路径、超参数）
│   ├── pipeline.py             # 完整三步流水线编排
│   ├── document_processor.py   # 文档处理门面类
│   ├── vector_store.py         # ChromaDB 增删查（批量编码 + 重试机制）
│   ├── hybrid_search.py        # 四阶段混合检索实现
│   ├── query_processor.py      # 查询改写 / 关键词提取 / HyDE
│   ├── text_splitter.py        # Markdown 切分（表格保护、脚注提取）
│   ├── rag_generator.py        # RAG 答案生成
│   ├── prompt_templates.py     # CoT + Few-shot + 文献综述提示词模板
│   ├── figure_extractor.py     # 图片引用提取与页码推算
│   ├── image_summarizer.py     # Qwen-VL 图片摘要生成
│   ├── single_file_parser.py   # PDF → Markdown（marker-pdf 封装）
│   └── eval_retrieval.py       # 检索评测（Recall / Precision / MRR / NDCG）
│
├── frontend/                   # React 前端
│   └── src/
│       ├── pages/              # 5 个主页面（知识库/文档/切片/检索/问答）
│       ├── components/         # 可复用 UI 组件（约 12 个）
│       ├── api/client.ts       # Axios 封装（含 SSE 流处理）
│       └── types/index.ts      # TypeScript 类型定义
│
├── data/paper_rag.db           # SQLite 数据库（gitignore，运行时自动创建）
├── primary_datas/              # 上传的 PDF 原文件（gitignore，运行时生成）
├── output/                     # 解析/切片/向量化产物（gitignore，运行时生成）
│   ├── markd_demo/             # PDF 解析产物（.md + 图片目录）
│   ├── split_demo/             # 分块 JSON 产物
│   └── chroma_demo/            # ChromaDB 持久化数据（KB 级分目录）
├── .env                        # API Key 配置（gitignore，不可提交）
├── .env.example                # API Key 模板（需复制为 .env 并填入真实 Key）
├── start.ps1                   # Windows 一键启动脚本（同时启动前后端）
└── pyproject.toml              # Python 项目配置（uv + PyTorch CUDA 索引）
```

---

## API 接口概览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/kb` | 列出所有知识库（含文档数量） |
| POST | `/api/kb` | 创建知识库 |
| DELETE | `/api/kb/{kb_id}` | 删除知识库（级联删除文档和向量） |
| POST | `/api/kb/{kb_id}/documents` | 上传 PDF（支持多文件） |
| POST | `/api/kb/{kb_id}/batch-process` | 批量处理流水线（SSE 进度流） |
| POST | `/api/chunk/preview` | 切片效果实时预览 |
| POST | `/api/documents/{doc_id}/chunk` | 单文档切片与入库 |
| DELETE | `/api/documents/{doc_id}` | 删除文档（含产物和向量） |
| POST | `/api/documents/{doc_id}/reindex` | 重建文档向量索引 |
| POST | `/api/search` | 混合检索（支持 rewrite / HyDE / reranker 开关） |
| POST | `/api/chat` | 流式 RAG 问答（SSE） |
| GET | `/api/usage/stats` | 用量与成本统计 |

完整接口文档：启动后访问 [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 关键设计决策

**为什么选 KB 级单集合而非每文档一个 ChromaDB 集合？**
文档级集合方案在知识库文档数量增长时会产生大量集合对象，管理成本高且跨文档查询需合并多集合结果。单集合方案通过 `doc_id` 元数据字段过滤，查询时可精确指定文档范围，集合数量与知识库数量线性相关而非与文档数相关。

**为什么用 RRF 而不是加权平均融合两路检索？**
向量相似度分数（0~1 cosine）和 BM25 分数量纲完全不同，直接加权需要针对每个数据集手动调参，且对查询分布敏感。RRF 只依赖候选在各路结果中的排名，鲁棒性更强，无需调参，是融合异构检索系统的标准方案。

**为什么 BGE-Reranker 不设为默认必选项？**
评测显示 Reranker（D 组）在部分查询上 Recall 反而略低于纯改写方案（C 组），原因是 Cross-Encoder 有时会过度关注字面匹配而忽略语义相关性。加之 Reranker 需要 GPU 内存和额外推理时间，故保留为可选项，由用户根据场景决定是否启用。

**为什么查询改写用 Qwen-turbo 而不用 DeepSeek？**
改写任务输入输出均较短，Qwen-turbo 延迟约 200ms，DeepSeek-chat 约 800ms。将轻量任务（改写/关键词提取）和重量任务（最终问答生成）路由至不同模型，在保证效果的同时将端到端延迟降低约 600ms。

---

## License

MIT
