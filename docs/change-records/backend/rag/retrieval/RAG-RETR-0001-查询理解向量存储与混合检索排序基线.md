# RAG-RETR-0001｜查询理解、向量存储与混合检索排序基线

## 需求

- 从知识库中返回与查询最相关且可追溯的证据。
- 同时利用语义相关性和关键词相关性。

## 功能

- 查询意图识别、改写、关键词提取和 HyDE 判断。
- Embedding 生成和 ChromaDB collection 管理。
- 向量检索、BM25、RRF 融合和可选 Reranker。
- 输出文本、来源、页码、图表和各阶段分数。

## 实现逻辑

- `query.py` 调用轻量模型生成结构化查询理解结果。
- `vector_store.py` 批量生成向量并管理 ChromaDB 数据。
- `hybrid.py` 合并向量与 BM25 排名，通过 RRF 融合，可选执行 BGE 精排。

## 代码范围

- `server/rag/retrieval/query.py`
- `server/rag/retrieval/vector_store.py`
- `server/rag/retrieval/hybrid.py`
- `server/api/routes/search.py`

## 依赖边界

- 可以依赖 `prompts` 和 `core`。
- 不负责最终答案生成或 PDF 解析。
