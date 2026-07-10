# RAG-CHUNK-0001｜Markdown 页码、图表保留与文本切分规则基线

## 需求

- 将 Markdown 转为适合检索的结构化 chunk。
- 保留页码、图表引用和必要上下文。

## 功能

- 解析 Markdown 页码。
- 清理参考文献尾部和无效文本。
- 支持递归、句子、段落和固定长度切分。
- 提取图表标题、类型、文件和页码关系。

## 实现逻辑

- `splitter.py` 根据切分方式、长度、重叠和分隔符生成 chunk。
- `figures.py` 从 Markdown 中提取图表引用，并将图表信息关联到对应页面和片段。
- 切分结果以 JSON 形式交给向量存储模块。

## 代码范围

- `server/rag/chunking/splitter.py`
- `server/rag/chunking/figures.py`
- `server/api/routes/chunking.py`

## 依赖边界

- 仅依赖 `core` 和本模块内部工具。
- 不调用检索、生成或 API 路由。
