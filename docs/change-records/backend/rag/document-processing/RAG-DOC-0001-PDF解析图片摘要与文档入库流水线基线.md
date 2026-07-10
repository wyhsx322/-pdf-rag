# RAG-DOC-0001｜PDF 解析、图片摘要与文档入库流水线基线

## 需求

- 将原始 PDF 转换为可切分、可索引、可追踪的内容。
- 文档处理状态和中间产物必须可定位。

## 功能

- PDF 转 Markdown。
- 提取图片与元数据。
- 调用视觉模型生成图片和图表摘要。
- 编排切分、向量入库、重建和删除索引。

## 实现逻辑

- `pdf_parser.py` 使用 marker-pdf 解析单个 PDF。
- `image_summarizer.py` 编码图片并调用视觉模型生成摘要。
- `pipeline.py` 串联解析、增强、切分和向量入库步骤。
- `processor.py` 根据数据库文档记录计算路径、更新状态并向 API 提供处理门面。

## 代码范围

- `server/rag/document_processing/`
- `primary_datas/`
- `output/` 中的解析与中间产物

## 依赖边界

- 可以依赖 `chunking`、`retrieval` 和 `core`。
- 不负责回答生成和页面交互。
