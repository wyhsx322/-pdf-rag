# BE-API-0001｜HTTP、SSE 接口及业务编排基线

## 需求

- 对前端提供稳定的 HTTP、SSE 和数据校验接口。
- 路由按知识库、文档、检索、问答、写作等业务拆分。

## 功能

- 管理知识库、PDF、切片、索引和对话。
- 提供混合检索、流式 RAG 问答、记忆和用量接口。
- 提供论文项目、大纲、章节、评审及引用校验接口。
- 提供本地模型设置和连接测试。

## 实现逻辑

- `schemas.py` 定义跨路由复用的 Pydantic 数据模型。
- `routes/` 下每个文件注册一个明确业务域的 FastAPI Router。
- 路由完成参数校验、数据库对象读取和下层服务编排。
- 长任务通过 SSE 持续返回处理、问答或 Agent 事件。

## 代码范围

- `server/api/schemas.py`
- `server/api/routes/`
- `server/main.py`

## 依赖边界

- 可以依赖 `core`、`rag`、`memory` 和 `writing`。
- 其他业务模块不得反向依赖 API 路由。
