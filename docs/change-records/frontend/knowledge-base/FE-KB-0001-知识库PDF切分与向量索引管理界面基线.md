# FE-KB-0001｜知识库、PDF、切分与向量索引管理界面基线

## 需求

- 让用户完成知识库、PDF、切分和向量索引的可视化管理。
- 长任务必须提供明确状态和进度反馈。

## 功能

- 创建、查看和删除知识库。
- 上传、筛选、处理和删除 PDF。
- 配置切分方式、长度、重叠和分隔符。
- 预览 chunk，查看向量统计并重建索引。

## 实现逻辑

- `KnowledgeBases.tsx` 管理知识库列表和创建流程。
- `KnowledgeBaseDetail.tsx` 组合文档、切分、处理和索引操作。
- `DocumentRow`、`UploadZone`、`ChunkPreview`、`SeparatorEditor` 等组件封装页面内交互。
- `entities/knowledge-base` 提供领域模型与 API。

## 代码范围

- `frontend/src/pages/knowledge-base/`
- `frontend/src/entities/knowledge-base/`

## 依赖边界

- 页面依赖实体 API、检索 Feature 和通用 UI。
- 知识库实体不得依赖页面组件。
