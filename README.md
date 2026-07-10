# AI Research Paper Writing Assistant with PDF RAG

一个用于论文阅读、知识检索、证据问答和辅助写作的本地 Web 应用。

## 能做什么

- 创建多个论文知识库并上传 PDF。
- 将 PDF 解析为可检索内容，保留页码、图片和图表摘要。
- 使用向量检索、BM25 和 RRF 查找相关证据。
- 可选启用查询改写、HyDE 和 BGE Reranker。
- 基于论文证据进行流式问答，并显示来源和页码。
- 保存对话历史，通过人工确认维护长期记忆。
- 创建论文写作项目，生成大纲和章节内容。
- 对章节进行评审、润色和引用校验。
- 在网页中配置 API Key、模型和 Base URL。

## 可以达到的效果

- 把分散的论文整理成可搜索、可追溯的个人知识库。
- 快速定位与问题相关的原文、页码和图表。
- 生成带证据来源的回答，降低脱离论文内容回答的风险。
- 复用知识库材料生成论文大纲和章节初稿。
- 通过评审和引用校验发现论证、结构及证据问题。
- 所有 PDF、数据库和 API Key 默认保存在本地，不提交到仓库。

## 环境要求

- Windows PowerShell
- Python 3.13 或更高版本
- [uv](https://docs.astral.sh/uv/)
- Node.js 18 或更高版本
- 可用的 DashScope 和 DeepSeek 兼容 API Key
- 可选 CUDA GPU，仅本地运行 BGE Reranker 时需要

## 安装

```powershell
git clone https://github.com/wyhsx322/-pdf-rag.git
cd -pdf-rag

uv sync
.venv\Scripts\python.exe -m pip install fastapi "uvicorn[standard]" python-multipart

cd frontend
npm install
cd ..
```

## 配置

复制环境变量模板：

```powershell
copy .env.example .env
```

编辑 `.env`：

```env
DASHSCOPE_API_KEY=your_dashscope_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

也可以启动后进入“设置”页面填写 API Key、模型名称和 Base URL。

## 启动

推荐使用一键启动脚本：

```powershell
.\start.ps1
```

启动后访问：

- 应用：`http://127.0.0.1:5173`
- API 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/api/health`

如需手动启动：

```powershell
# 后端
.venv\Scripts\python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8000

# 前端，另开一个终端
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

## 使用流程

### 建立论文知识库

1. 打开“知识库”。
2. 创建知识库并上传 PDF。
3. 选择切分参数，执行文档处理。
4. 等待文档状态变为已入库。

### 检索和问答

1. 在“检索”页面测试关键词与检索参数。
2. 在问答页面选择知识库。
3. 输入问题，查看流式答案、来源、页码和相关图表。

### 辅助论文写作

1. 打开“论文写作”并创建项目。
2. 绑定提供写作证据的知识库。
3. 生成并确认论文大纲。
4. 按章节生成内容，执行评审和引用校验。
5. 根据评审结果继续修改或重新生成。

## 本地数据说明

以下内容不会提交到 GitHub：

- `.env` 和本地模型配置
- 上传的 PDF
- SQLite 数据库
- Markdown、图片、切片和向量库
- 日志及前端构建产物

不要在提交中加入真实 API Key、论文原文件或本地数据库。
