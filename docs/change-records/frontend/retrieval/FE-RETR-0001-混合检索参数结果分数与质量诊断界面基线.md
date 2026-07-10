# FE-RETR-0001｜混合检索参数、结果分数与质量诊断界面基线

## 需求

- 提供可调参数的检索测试界面。
- 让用户理解检索结果质量和潜在风险。

## 功能

- 设置知识库、Top K、查询改写、HyDE 和 Reranker。
- 展示结果文本、来源、页码和各检索分数。
- 展示结果覆盖率、置信度、风险和改进建议。

## 实现逻辑

- `features/retrieval/api.ts` 调用后端混合检索接口。
- `RagSearchPanel.tsx` 管理参数、加载状态、结果卡片和诊断指标。
- `pages/search/Search.tsx` 将检索面板作为独立页面展示。
- `entities/retrieval/model.ts` 定义检索结果字段。

## 代码范围

- `frontend/src/features/retrieval/`
- `frontend/src/entities/retrieval/`
- `frontend/src/pages/search/`

## 依赖边界

- Feature 可以依赖知识库和检索实体。
- 检索实体不得依赖 Feature 或页面。
