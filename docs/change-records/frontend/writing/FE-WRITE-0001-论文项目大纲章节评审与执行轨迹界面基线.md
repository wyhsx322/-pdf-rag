# FE-WRITE-0001｜论文项目、大纲、章节评审与执行轨迹界面基线

## 需求

- 提供论文项目、大纲、章节和评审的完整工作区。
- 展示智能体执行过程并支持人工确认。

## 功能

- 创建、查看和删除论文项目。
- 绑定知识库并生成大纲。
- 按章节写作、保存、评审和引用校验。
- 查看 Agent Trace、评分和待确认状态。

## 实现逻辑

- `ThesisProject.tsx` 管理项目列表和创建表单。
- `ThesisWorkspace.tsx` 负责大纲、章节列表、工作流和执行轨迹。
- `SectionWorkspace.tsx` 提供单章节编辑、生成、评审和保存界面。
- 页面通过 `/api/agent` 系列接口驱动后端工作流。

## 代码范围

- `frontend/src/pages/writing/`
- `server/api/routes/agent.py`
- `server/writing/`

## 依赖边界

- 页面只组合 API 数据和 UI 状态。
- Agent 业务规则由后端写作模块实现。
